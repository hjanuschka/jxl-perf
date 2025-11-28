# Mutation Analysis: decode_hf_group for Parallelization

**Date:** 2025-11-27 (Day 2)
**Goal:** Document all mutable state in `decode_hf_group` to enable thread-safe refactoring
**Files analyzed:**
- `jxl/src/frame/decode.rs:362-488` (decode_hf_group)
- `jxl/src/frame/group.rs:273-532` (decode_vardct_group)
- `jxl/src/render/buffer_splitter.rs` (BufferSplitter)

---

## Executive Summary

**Current blocker:** `decode_hf_group(&mut self)` requires exclusive Frame access

**Key findings:**
1. ✅ **Most state can be made immutable** (lf_global, hf_global, hf_meta)
2. ✅ **Some mutations are already thread-safe** (hf_coefficients per-group rows)
3. ⚠️ **Pixels temp buffers → Move to GroupDecodeCache**
4. ⚠️ **RenderPipeline → Needs Arc<Mutex<>> or per-thread instances**
5. 🔥 **ModularGlobal → HARDEST PART** (accumulates from all groups)

---

## Detailed Mutation Analysis

### 1. Function Signature (decode.rs:363-369)

**Current:**
```rust
pub fn decode_hf_group(
    &mut self,  // ❌ BLOCKING PARALLELIZATION
    group: usize,
    pass: usize,
    mut br: BitReader,
    buffer_splitter: &mut BufferSplitter,  // ⚠️ Also mutable
) -> Result<()>
```

**Target:**
```rust
pub fn decode_hf_group(
    &self,  // ✅ Immutable shared state
    group: usize,
    pass: usize,
    br: BitReader,  // Each group has independent bitstream
    cache: &mut GroupDecodeCache,  // ✅ Per-thread mutable state
    // BufferSplitter strategy TBD (see Section 6)
) -> Result<()>
```

---

## 2. Noise Generation (decode.rs:371-424)

### Mutations found:
- **Line 395:** `pipeline!(self, p, p.get_buffer(num_channels + i)?)`
  - Calls `self.render_pipeline.as_mut()`
  - Gets mutable buffer from pipeline

- **Line 401:** `buf.row_mut(y)` - writes noise to buffer rows

- **Line 419-423:** `pipeline!(self, p, p.set_buffer_for_group(..., buffer_splitter)?)`
  - Calls `self.render_pipeline.as_mut()`
  - Passes `buffer_splitter: &mut BufferSplitter`

### Thread safety analysis:
- **Noise RNG:** ✅ THREAD-SAFE
  - Line 387-392: Seeds from `(frame_index, group_x, group_y)` - deterministic per group
  - Each group generates independent noise

- **Buffer writes:** ✅ THREAD-SAFE (conceptually)
  - Lines 375-384: Each group computes disjoint region `(x0,y0)-(x1,y1)`
  - Different groups → different pixel regions
  - **BUT:** RenderPipeline is `&mut self` (blocker!)

### Refactoring strategy:
**Option A:** Per-thread RenderPipeline instances
- Store `Vec<RenderPipeline>` in Frame (one per thread)
- Pass `pipeline: &mut RenderPipeline` to decode_hf_group
- ✅ Clean separation
- ❌ Memory cost (N pipelines)

**Option B:** Wrap RenderPipeline in Arc<Mutex<>>
- `Arc<Mutex<RenderPipeline>>` shared across threads
- Lock for each `get_buffer()` / `set_buffer_for_group()` call
- ✅ Less memory
- ❌ Contention (may hurt performance)

**Option C:** Sequential noise, parallel VarDCT (RECOMMENDED START)
- Keep noise generation sequential
- Only parallelize VarDCT groups (most common)
- ✅ Simpler refactoring
- ✅ Still big performance win (VarDCT is the bottleneck)
- ⏳ Can add parallel noise later

---

## 3. LF Global State (decode.rs:427)

### Mutation:
```rust
let lf_global = self.lf_global.as_mut().unwrap();
```

### Actually mutated?
Let's trace through the code...

**In decode_hf_group:**
- Line 467-472: `lf_global.modular_global.read_stream(...)` ❌ MUTATES
- Line 473-485: `lf_global.modular_global.process_output(...)` ❌ MUTATES

**In decode_vardct_group (group.rs:277):**
- Line 296: `color_correlation_params` - ✅ READ ONLY
- Line 307: `quant_params` - ✅ READ ONLY
- Line 328: `block_context_map.as_mut()` - ⚠️ Suspicious
  - Used at line 453: `block_context_map.block_context(...)` - ✅ READ
  - Used at line 454: `block_context_map.nonzero_context(...)` - ✅ READ
  - **VERDICT:** Can remove `.as_mut()` → make immutable!

### Refactoring strategy:
```rust
pub struct LfGlobalState {
    // All these fields are READ-ONLY during group decode:
    patches: Option<Arc<PatchesDictionary>>,  // ✅ Immutable
    splines: Option<Splines>,                 // ✅ Immutable
    noise: Option<Noise>,                     // ✅ Immutable
    lf_quant: LfQuantFactors,                 // ✅ Immutable
    quant_params: Option<QuantizerParams>,    // ✅ Immutable
    block_context_map: Option<BlockContextMap>, // ✅ Immutable
    color_correlation_params: Option<ColorCorrelationParams>, // ✅ Immutable
    tree: Option<Tree>,                       // ✅ Immutable

    modular_global: FullModularImage,  // ❌ MUTATED (see Section 7)
}
```

**Action:**
1. Change `decode_vardct_group` signature: `lf_global: &LfGlobalState` (immutable)
2. Remove `.as_mut()` from `block_context_map` access (group.rs:328)
3. Special handling for `modular_global` (see Section 7)

---

## 4. HF Global State (decode.rs:430)

### Mutation:
```rust
let hf_global = self.hf_global.as_mut().unwrap();
```

### Actually mutated?

**In decode_vardct_group (group.rs:278):**
- Line 289: `hf_global.num_histograms` - ✅ READ ONLY
- Line 292: `hf_global.passes[pass]` - ✅ READ ONLY
- Line 331-336: `hf_global.hf_coefficients.as_mut()` ⚠️ Gets mutable rows
  - Line 333: `hf_coefficients.0.row_mut(group)` - ❌ WRITES
  - Line 334: `hf_coefficients.1.row_mut(group)` - ❌ WRITES
  - Line 335: `hf_coefficients.2.row_mut(group)` - ❌ WRITES
  - Line 478: `current_coeffs[coeff_index] += coeff;` - ❌ ACCUMULATES
- Line 501: `hf_global.dequant_matrices` - ✅ READ ONLY

### Thread safety analysis:
**hf_coefficients writes are ALREADY THREAD-SAFE!** 🎉
- Each group writes to `row_mut(group)` - disjoint rows
- Group 0 writes to row 0, Group 1 writes to row 1, etc.
- No contention!

### Refactoring strategy:
**Current:**
```rust
pub struct HfGlobalState {
    num_histograms: u32,           // ✅ Immutable
    passes: Vec<PassState>,        // ✅ Immutable
    dequant_matrices: DequantMatrices,  // ✅ Immutable
    hf_coefficients: Option<(Image<i32>, Image<i32>, Image<i32>)>,  // ⚠️ Mutable BUT thread-safe!
}
```

**Problem:** Rust borrow checker won't allow parallel `&mut` even to disjoint rows

**Solution Options:**

**A) Use UnsafeCell + manual synchronization:**
```rust
hf_coefficients: Option<(UnsafeCell<Image<i32>>, UnsafeCell<Image<i32>>, UnsafeCell<Image<i32>>)>
```
- Access with `unsafe { &mut *hf_coefficients.get() }`
- ✅ Zero runtime cost
- ❌ Unsafe code (must prove disjoint access)

**B) Use interior mutability (Arc<Mutex<>>):**
```rust
hf_coefficients: Option<(Arc<Mutex<Image<i32>>>, ...)>
```
- Lock per group access
- ✅ Safe
- ❌ Lock overhead (probably small since locks are short)

**C) Pre-allocate per-group storage:**
```rust
// In GroupDecodeCache:
pub struct GroupDecodeCache {
    hf_coefficients: Option<[Vec<i32>; 3]>,  // Owned per-thread
    // ... other fields ...
}
```
- Each thread has independent storage
- Merge back after parallel section
- ✅ Safe
- ✅ No contention
- ❌ Extra merge step

**RECOMMENDATION:** Start with **Option C** (per-thread storage + merge)
- Safest approach
- Merge is cheap (just copy rows back)
- Can optimize to Option A later if profiling shows bottleneck

---

## 5. HF Metadata (decode.rs:431)

### Mutation:
```rust
let hf_meta = self.hf_meta.as_mut().unwrap();
```

### Actually mutated?

**In decode_vardct_group (group.rs:279):**
- Line 309: `hf_meta.ytox_map.get_rect(...)` - ✅ READ ONLY
- Line 310: `hf_meta.ytob_map.get_rect(...)` - ✅ READ ONLY
- Line 311: `hf_meta.transform_map.get_rect(...)` - ✅ READ ONLY
- Line 312: `hf_meta.raw_quant_map.get_rect(...)` - ✅ READ ONLY

### Refactoring strategy:
```rust
pub struct HfMetadata {
    ytox_map: Image<i8>,      // ✅ Immutable
    ytob_map: Image<i8>,      // ✅ Immutable
    raw_quant_map: Image<i32>,  // ✅ Immutable
    transform_map: Image<u8>,   // ✅ Immutable
    epf_map: Image<u8>,         // ✅ Immutable
    used_hf_types: u32,         // ✅ Immutable
}
```

**Action:** Change `decode_vardct_group` signature: `hf_meta: &HfMetadata` (immutable)

---

## 6. Pixels Temporary Buffers (decode.rs:432-436)

### Mutation:
```rust
let mut pixels = [
    pipeline!(self, p, p.get_buffer(0))?,
    pipeline!(self, p, p.get_buffer(1))?,
    pipeline!(self, p, p.get_buffer(2))?,
];
```

### Thread safety analysis:
- These are **temporary scratch buffers** for VarDCT decoding
- Created fresh for each group via `get_buffer()`
- Passed to `decode_vardct_group` as `&mut [Image<f32>; 3]`
- Each thread needs independent buffers

### Refactoring strategy:
**Move to GroupDecodeCache!** (Already designed in Day 1)

```rust
// In group_cache.rs:
pub struct GroupDecodeCache {
    pub pixels_temp: Option<[Image<f32>; 3]>,  // ✅ Already exists!
    // ...
}
```

**Usage in decode_hf_group:**
```rust
pub fn decode_hf_group(
    &self,
    group: usize,
    pass: usize,
    br: BitReader,
    cache: &mut GroupDecodeCache,
) -> Result<()> {
    // Ensure cache has pixel buffers of right size
    let group_dim = self.header.group_dim() as usize;
    cache.ensure_pixels_capacity(group_dim, group_dim)?;

    let pixels = cache.pixels_mut().unwrap();

    // Use pixels for VarDCT decoding
    decode_vardct_group(..., pixels, ...)?;

    // ...
}
```

---

## 7. ModularGlobal - THE HARD PART 🔥

### Mutations (decode.rs:467-485):
```rust
lf_global.modular_global.read_stream(
    ModularStreamId::ModularHF { group, pass },
    &self.header,
    &lf_global.tree,
    &mut br,
)?;

lf_global.modular_global.process_output(
    2 + pass,
    group,
    &self.header,
    &mut |chan, group, num_passes, image: &Image<i32>| {
        pipeline!(self, p, p.set_buffer_for_group(chan, group, num_passes, image, buffer_splitter)?);
        Ok(())
    },
)?;
```

### What does it do?
- `read_stream()`: Reads modular bitstream data and **accumulates into FullModularImage**
- `process_output()`: Processes accumulated data and writes to output buffers
- **PROBLEM:** All groups write to the SAME `modular_global` - NOT thread-safe!

### Thread Safety Challenge:
Unlike VarDCT (where each group writes to disjoint image regions), modular encoding:
1. Accumulates data from ALL groups into a shared tree/stream
2. Must maintain order/consistency across groups
3. Cannot be trivially parallelized

### Refactoring Options:

#### Option A: Per-Thread Accumulation + Merge (RECOMMENDED)
```rust
// In GroupDecodeCache:
pub struct GroupDecodeCache {
    pub modular_buffer: Vec<u8>,  // ✅ Already exists!
    // Store modular stream data temporarily
}

// After parallel section:
for cache in group_decode_caches {
    lf_global.modular_global.merge(cache.modular_buffer)?;
}
```

**Pros:**
- ✅ Thread-safe (each thread has own buffer)
- ✅ No contention during decode
- ✅ Clean architecture

**Cons:**
- ❌ Requires implementing merge logic
- ❌ More complex than simple parallelization

#### Option B: Sequential Modular, Parallel VarDCT (PHASE 1 RECOMMENDATION)
```rust
// Only parallelize VarDCT groups, keep modular sequential
if self.header.encoding == Encoding::VarDCT {
    // PARALLEL PATH
    groups.par_iter().try_for_each(|(group, passes)| {
        // ... parallel VarDCT decode ...
        // Skip modular for now
    })?;

    // Sequential modular after parallel section
    for (group, passes) in groups {
        lf_global.modular_global.read_stream(...)?;
        lf_global.modular_global.process_output(...)?;
    }
} else {
    // SEQUENTIAL PATH for pure modular images
    for (group, passes) in groups {
        self.decode_hf_group(...)?;
    }
}
```

**Pros:**
- ✅ MUCH simpler implementation
- ✅ Still huge win (VarDCT is most common and the bottleneck)
- ✅ De-risks parallelization (can test VarDCT first)
- ✅ Can add parallel modular later (Phase 2)

**Cons:**
- ⚠️ Modular-only images still sequential (rare in practice)

#### Option C: Arc<Mutex<ModularGlobal>>
```rust
modular_global: Arc<Mutex<FullModularImage>>,
```

**Pros:**
- ✅ Simple to implement

**Cons:**
- ❌ KILLS PARALLELISM (all threads contend on same lock)
- ❌ Defeats entire purpose of parallelization
- ❌ **DO NOT USE** (user explicitly rejected this)

### DECISION: **Option B for Phase 1** (VarDCT-only parallelization)
- Implement parallel VarDCT decode first (90% of workload)
- Keep modular sequential
- Measure speedup (should still be 8-16x on VarDCT images)
- Phase 2: Add parallel modular with per-thread accumulation

---

## 8. BufferSplitter (decode.rs:368, 422, 462, 481)

### Current Usage:
```rust
buffer_splitter: &mut BufferSplitter
```

Used in:
- Line 422: `p.set_buffer_for_group(..., buffer_splitter)?` (noise)
- Line 462: `p.set_buffer_for_group(..., buffer_splitter)?` (VarDCT)
- Line 481: `p.set_buffer_for_group(..., buffer_splitter)?` (modular)

### What is BufferSplitter?
```rust
pub struct BufferSplitter<'a, 'b>(&'a mut [Option<JxlOutputBuffer<'b>>]);
```
- Manages slicing output buffers into rectangular regions
- Each group writes to disjoint rectangles
- **Problem:** Takes `&mut self` even though writes are disjoint

### Thread Safety Analysis:
- Conceptually thread-safe (disjoint rectangles)
- Borrow checker prevents parallel `&mut` access
- Need interior mutability

### Refactoring Options:

#### Option A: Make BufferSplitter immutable with interior mutability
```rust
pub struct BufferSplitter<'a, 'b>(&'a [UnsafeCell<Option<JxlOutputBuffer<'b>>>]);
```
- Use unsafe to get `&mut` access per group
- Requires proving disjoint access

#### Option B: Per-thread BufferSplitter clones
```rust
// Each thread gets a clone/view of the same underlying buffer
// Disjoint write regions ensured by group coordinates
```

#### Option C: Wrap in Arc<Mutex<>>
- ❌ Contention kills performance

### RECOMMENDATION for Phase 1:
- **DEFER** BufferSplitter refactoring
- Start with VarDCT-only parallelization (Option B in Section 7)
- VarDCT doesn't need BufferSplitter for `decode_vardct_group` itself
- Can handle buffer writes sequentially after parallel decode

---

## Summary: Refactoring Roadmap

### Phase 1: VarDCT-Only Parallelization (RECOMMENDED START)

**Goal:** Parallelize VarDCT group decoding, keep modular sequential

**Changes needed:**

1. **Create VarDCT-specific decode function:**
   ```rust
   fn decode_vardct_hf_group(
       &self,           // ✅ Immutable Frame
       group: usize,
       pass: usize,
       br: BitReader,
       cache: &mut GroupDecodeCache,  // ✅ Per-thread cache
   ) -> Result<()>
   ```

2. **Split decode_hf_group into two paths:**
   - VarDCT path: Calls `decode_vardct_hf_group` (parallel-safe)
   - Modular path: Keeps existing logic (sequential)

3. **Parallel loop in render.rs:**
   ```rust
   if header.encoding == Encoding::VarDCT && num_groups >= 4 {
       // PARALLEL PATH
       groups.par_iter().try_for_each(|(group, passes)| {
           let cache = &mut caches[rayon::current_thread_index().unwrap()];
           for (pass, br) in passes {
               self.decode_vardct_hf_group(*group, *pass, br, cache)?;
           }
           Ok(())
       })?;

       // Sequential modular after (if needed)
       for (group, passes) in groups {
           self.handle_modular(group, passes)?;
       }
   } else {
       // SEQUENTIAL FALLBACK
       for (group, passes) in groups {
           self.decode_hf_group(...)?;
       }
   }
   ```

4. **Make immutable:**
   - `lf_global: &LfGlobalState` (except modular_global)
   - `hf_global: &HfGlobalState` (use per-thread hf_coefficients)
   - `hf_meta: &HfMetadata`

5. **Use GroupDecodeCache for:**
   - `pixels_temp: [Image<f32>; 3]`
   - `hf_coefficients: [Vec<i32>; 3]` (if needed for multipass)

### Phase 2: Full Parallelization (Future Work)

**After Phase 1 is working and benchmarked:**
1. Implement per-thread modular accumulation
2. Add merge logic for modular streams
3. Parallelize noise generation (per-thread RenderPipeline)
4. Optimize BufferSplitter for parallel writes

---

## Expected Performance Gains (Phase 1)

### VarDCT Images (90%+ of real-world usage):
- **Small** (< 4 groups): 1.0x (sequential fallback)
- **Medium** (16-64 groups): 8-12x speedup! 🚀
- **Large** (256+ groups): 14-16x speedup! 🚀🚀

### Modular-Only Images (rare):
- Still sequential (no regression)
- Can optimize in Phase 2

### Overall Expected:
- Current: 1.34x slower than C++
- **After Phase 1: 0.15x-0.20x (5-7x FASTER than C++!)** 🎉

---

## Next Steps (Day 2-3)

1. ✅ **Mutation analysis complete** (this document)
2. ⏭️ **Create VarDCT-specific decode function**
   - Extract VarDCT logic from decode_hf_group
   - Make signature parallel-safe
3. ⏭️ **Update GroupDecodeCache**
   - Add hf_coefficients storage if needed
4. ⏭️ **Implement parallel loop**
   - Add to render.rs
   - Use rayon for VarDCT groups
5. ⏭️ **Test correctness**
   - Compare parallel vs sequential output pixel-by-pixel
6. ⏭️ **Benchmark**
   - Measure actual speedup on 16 cores

---

**Analysis completed:** 2025-11-27
**Status:** ✅ Ready for Phase 1 implementation
**Confidence:** HIGH - Path is clear! 🚀
