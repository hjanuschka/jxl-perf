# Phase 3 Strategy: Achieving 1.0x Performance Parity with C++

**Current Status (Phase 2 Complete):**
- bike: **183.76ms** (Rust) vs **164.75ms** (C++) = **1.12x slower**
- Gap to close: **~19ms** (11.5% improvement needed)
- Parallel VarDCT is working correctly with pre-allocated result slots
- Average slowdown: 1.07x across all tests

## Deep Analysis: Where Are The Remaining 19ms?

### 1. Profile Analysis Needed
We need to profile bike.jxl decoding to identify hotspots:
```bash
perf record -g --call-graph=dwarf ./target/release/test_decode_rs test_images/bike.jxl
perf report --stdio
```

**Expected hotspots to investigate:**
- VarDCT coefficient decoding (ANS entropy decoder)
- DCT/IDCT transformations
- Color space conversions (OpsinInverse)
- Edge Preserving Filter (EPF)
- Memory allocation/copying

### 2. Known Performance Gaps from Benchmark Data

Analyzing worst performers (>1.5x slower):
1. **grayscale**: 2.24x - Not VarDCT, different path
2. **grayscale_jpeg**: 2.11x - JPEG reconstruction path
3. **bicycles**: 1.94x - VarDCT decode (similar to bike!)
4. **noise**: 1.91x - Noise synthesis overhead
5. **alpha_triangles**: 1.89x - Alpha channel handling

**Key insight**: `bicycles` is 1.94x slower and uses VarDCT like bike. This suggests VarDCT decoding itself (not parallelization) is the bottleneck!

### 3. Hypothesis: VarDCT Decoding Core is Slow

**Evidence:**
- Parallel speedup is minimal (~1% from 185ms → 183ms)
- Both bike (1.12x) and bicycles (1.94x) are VarDCT images
- The gap exists even with working parallelization

**Root causes to investigate:**

#### A) ANS Entropy Decoder Performance
The ANS decoder is used for coefficient decoding. Potential issues:
- Table lookups not cache-friendly
- Branch mispredictions in symbol decoding
- Inefficient bit stream reading

**Action**: Profile ANS decoder hotspots and compare with libjxl implementation

#### B) DCT/IDCT Performance
Transform performance differences:
- libjxl uses heavily optimized SIMD DCT
- jxl-rs may not have equivalent SIMD coverage

**Action**: Check if all DCT sizes (8x8, 16x16, 32x32) have SIMD implementations

#### C) Coefficient Dequantization
Quantization/dequantization overhead:
- Array indexing patterns
- Cache misses in quantization tables
- Float vs int conversions

**Action**: Review `DequantBlock` implementation

#### D) Memory Bandwidth Saturation
With 8 threads, we may be memory-bound:
- Each thread reading coefficients from RAM
- Cache thrashing between cores
- Insufficient cache locality

**Action**: Test with different thread counts (1, 2, 4, 8) to see scaling

### 4. Specific Optimization Opportunities

#### Optimization 1: SIMD-Optimize Hot Paths
**Target areas:**
- DCT/IDCT if not fully SIMD'd
- Coefficient dequantization
- Color space conversions

**Expected gain**: 5-10ms (25-50% of gap)

**Implementation:**
```rust
// Example: SIMD dequantization
#[cfg(target_arch = "x86_64")]
unsafe fn dequant_block_avx2(coeffs: &[i32], quant: &[f32], output: &mut [f32]) {
    use std::arch::x86_64::*;
    for i in (0..coeffs.len()).step_by(8) {
        let c = _mm256_loadu_si256(coeffs[i..].as_ptr() as *const __m256i);
        let c_f32 = _mm256_cvtepi32_ps(c);
        let q = _mm256_loadu_ps(&quant[i]);
        let result = _mm256_mul_ps(c_f32, q);
        _mm256_storeu_ps(&mut output[i], result);
    }
}
```

#### Optimization 2: Reduce BitReader Cloning Overhead
Currently we clone BitReader for each group:
```rust
br.clone()  // Line 249 in render.rs
```

**Problem**: BitReader likely contains buffers that get copied

**Solution**: Use reference counting or shared buffer:
```rust
use std::sync::Arc;
let br_shared = Arc::new(br);
// In parallel loop:
let br_ref = Arc::clone(&br_shared);
```

**Expected gain**: 2-3ms

#### Optimization 3: Optimize GroupDecodeCache Usage
Current: Each thread locks to get cache from shared pool
Better: Thread-local storage

```rust
use rayon::prelude::*;

group_passes
    .par_iter()
    .map_init(
        || super::group_cache::GroupDecodeCache::new(),  // Thread-local init
        |cache, (group, pass, br)| {
            // Use cache directly, no mutex!
            frame_ref.decode_vardct_core(*group, *pass, br.clone(), cache)
        }
    )
    .collect();
```

**Expected gain**: 1-2ms (eliminate mutex overhead)

#### Optimization 4: Profile-Guided Optimization (PGO)
Enable PGO in Cargo.toml:
```toml
[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1

[profile.pgo]
inherits = "release"
```

Then run:
```bash
cargo pgo build
cargo pgo run -- test_images/bike.jxl  # Generate profile
cargo pgo optimize build  # Rebuild with profile
```

**Expected gain**: 3-5ms (15-25% of gap)

#### Optimization 5: Inline Critical Functions
Force inlining of hot path functions:
```rust
#[inline(always)]
pub fn decode_vardct_core(...) -> Result<...> {
    // ...
}

#[inline(always)]
fn decode_ans_symbol(...) -> u32 {
    // ...
}
```

**Expected gain**: 1-2ms

### 5. Memory Bandwidth Optimization

#### Option A: Reduce Memory Allocations
Pre-allocate ALL buffers at frame level:
- Coefficient buffers
- Transform scratch space
- Output image buffers

#### Option B: Improve Cache Locality
Group adjacent VarDCT blocks to same thread:
```rust
// Instead of round-robin, group spatially
let groups_per_thread = num_groups / num_threads;
rayon::scope(|s| {
    for thread_id in 0..num_threads {
        let start = thread_id * groups_per_thread;
        let end = start + groups_per_thread;
        s.spawn(move |_| {
            for group in start..end {
                // Process spatially adjacent groups
            }
        });
    }
});
```

**Expected gain**: 2-4ms

### 6. Priority Action Plan

**Phase 3A: Low-Hanging Fruit (Quick Wins - Week 1)**
1. ✅ Use `map_init` to eliminate cache mutex (1-2ms) - **IMMEDIATE**
2. ✅ Force inline hot functions (1-2ms) - **IMMEDIATE**
3. ✅ Reduce BitReader cloning with Arc (2-3ms) - **1 hour**
4. Profile with perf to identify actual hotspots - **2 hours**

**Phase 3B: SIMD Optimization (Week 2)**
5. Audit all DCT/IDCT paths for SIMD coverage - **1 day**
6. SIMD-optimize dequantization if needed - **2 days**
7. SIMD-optimize color conversions if needed - **1 day**

**Phase 3C: Advanced Optimizations (Week 3)**
8. Profile-Guided Optimization (PGO) - **1 day**
9. Memory bandwidth optimization - **2 days**
10. Cache locality improvements - **1-2 days**

### 7. Expected Results

**Conservative estimate:**
- Phase 3A: 4-7ms improvement → 176-179ms (1.07-1.09x)
- Phase 3B: 5-10ms improvement → 169-174ms (1.03-1.06x)
- Phase 3C: 3-5ms improvement → 164-169ms (0.99-1.03x)

**Total expected**: **164-169ms** → **0.99-1.03x** (MEETING OR BEATING C++!)

**Optimistic estimate** (if profiling reveals major bottleneck):
- Single targeted fix could yield 10-15ms
- Final result: **~160ms** → **0.97x** (3% faster than C++!)

### 8. Measurement & Validation

After each optimization:
1. Run full benchmark suite
2. Verify correctness (no regressions in test passing)
3. Check bike specifically
4. Update this document with actual gains

### 9. Fallback Plan

If we can't reach 1.0x with these optimizations:
1. **Deep dive into libjxl source** - Line-by-line comparison of VarDCT decode path
2. **Assembly analysis** - Compare generated assembly for hot functions
3. **Alternative libraries** - Investigate if libjxl uses external optimized libraries
4. **Compiler flags** - Experiment with -Ctarget-cpu=native and other flags

## Next Session Checklist

- [ ] Implement `map_init` optimization (cache mutex elimination)
- [ ] Add `#[inline(always)]` to decode_vardct_core
- [ ] Run perf profile on bike.jxl
- [ ] Analyze flamegraph for hotspots
- [ ] Prioritize based on profile data
- [ ] Implement top 3 hotspot fixes
- [ ] Re-benchmark and measure progress

---

**Commit tagged as**: `phase2-parallel-vardct`
**Next tag target**: `phase3-parity` (when bike ≤ 1.0x)
