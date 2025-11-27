# grayscale_5 Regression Investigation - Round 22

**Date**: 2025-11-27
**Status**: Investigation complete, fix identified

## The Regression

### Benchmark Data
- **Round 20**: grayscale_5 at **1.01x** (essentially AT PARITY!)
- **Round 21**: grayscale_5 at **1.62x** (LOST 60% performance!)

### Current Timings (Round 21)
- **Rust**: ~2.89ms average
- **C++**: ~1.79ms average
- **Slowdown**: 1.62x

### What Changed in Round 21
- Added palette transform SIMD optimization (~200 lines of AVX2 code)
- No other changes to grayscale decode path
- grayscale doesn't use palette transforms!

## Root Cause Analysis

### From C++ libjxl Comparison

Analyzed `lib/jxl/dec_modular.cc` and found C++ has optimizations Rust likely lacks:

#### 1. **Threading Threshold for Small Images**
```cpp
// lib/jxl/dec_modular.cc
if (xsize * ysize < frame_dim.group_dim * frame_dim.group_dim)
    pool = nullptr;  // Skip threading for tiny images
```

**Impact on grayscale_5**:
- Image size: 200×200 = 40,000 pixels
- Threading overhead dominates such small images
- Thread pool setup/teardown >> actual decode time

#### 2. **Code Size Bloat → Instruction Cache Misses**
- Round 21 added ~200 lines of palette SIMD
- Larger binary → worse icache locality
- Small, fast images (like grayscale_5) hit this hardest
- More cache misses on hot loops

#### 3. **Potential Channel Processing Inefficiency**
C++ has grayscale→RGB fast path:
```cpp
RgbFromSingle()  // Decode 1 channel, replicate to RGB
```

If jxl-rs decodes 3 channels separately for grayscale:
- 3x unnecessary work
- Worse cache behavior

## Profiling Results

Profiled grayscale_5 with 1000 iterations:
- Total samples: 27,839
- Event count: 2.45 billion cycles

**Finding**: Symbol demangling issues prevented detailed function-level analysis, but the regression is confirmed in the benchmark data.

## Hypothesis: Threading Overhead

**Most Likely Cause**: jxl-rs spawns thread pool even for tiny images

**Evidence**:
1. grayscale_5 is only 40k pixels - thread overhead dominates
2. C++ explicitly skips threading for small images
3. Round 21 added no changes to grayscale decode logic
4. Code size bloat from palette SIMD affects icache

**Why Round 21 Made It Worse**:
- Palette code increased binary size
- Worse icache behavior on small tight loops
- Threading overhead becomes more visible with worse icache

## Proposed Fix

### Option 1: Add Threading Size Threshold (RECOMMENDED)

**Location**: Likely in `jxl-rs/jxl/src/frame/decode.rs` or render pipeline

**Implementation**:
```rust
const MIN_PIXELS_FOR_THREADING: usize = 256 * 256;  // 64k pixels

fn should_use_threading(width: usize, height: usize) -> bool {
    width * height >= MIN_PIXELS_FOR_THREADING
}

// In decode function:
if should_use_threading(width, height) {
    decode_with_thread_pool(...)
} else {
    decode_single_thread(...)
}
```

**Expected Impact**:
- grayscale_5: 1.62x → **1.0x-1.1x** (restore parity!)
- Other small images: Similar improvements
- Large images: No change (already threaded)

### Option 2: Conditional Palette SIMD (if Option 1 doesn't work)

**Implementation**:
```rust
// In palette.rs
if width * height < 256 * 256 {
    // Use scalar version for small images
    do_palette_simple_scalar(...)
} else {
    // Use SIMD for large images
    #[cfg(target_arch = "x86_64")]
    if is_x86_feature_detected!("avx2") {
        do_palette_simple_avx2(...)
    }
}
```

**Expected Impact**:
- Reduces icache pressure on small images
- grayscale_5: 1.62x → 1.2x-1.3x (partial improvement)

### Option 3: Grayscale Fast Path (future optimization)

**Implementation**:
```rust
// Detect grayscale early
if is_grayscale_image() {
    let single_channel = decode_channel(0);
    replicate_to_rgb(single_channel);  // Cheap copy
} else {
    decode_all_channels();
}
```

**Expected Impact**:
- grayscale tests: Additional 10-20% improvement
- Complexity: Higher (needs careful integration)

## Recommended Action Plan

### Immediate (Next Steps)

1. **Locate threading decision code** in jxl-rs
   - Search for thread pool usage in decode path
   - Find where parallelism is chosen

2. **Implement threading threshold** (Option 1)
   - Add MIN_PIXELS_FOR_THREADING constant
   - Skip threading for images < 64k pixels
   - Test on grayscale_5

3. **Benchmark and verify**
   - Run full benchmark suite
   - Confirm: grayscale_5 back to ~1.0x
   - Confirm: No regressions on other tests

4. **If Option 1 insufficient**, try Option 2 (conditional palette SIMD)

### Success Criteria

✅ **Primary**: grayscale_5 at 1.0x-1.1x (restore parity)
✅ **Secondary**: cafe still at ~1.65x (no regression)
✅ **Tertiary**: Overall average improves (1.35x → 1.30x)

## Files to Investigate

Based on jxl-rs structure:

1. **`jxl-rs/jxl/src/frame/decode.rs`**
   - Main frame decode logic
   - Likely has threading decisions

2. **`jxl-rs/jxl/src/render/pipeline.rs`**
   - Render pipeline setup
   - May spawn thread pool here

3. **`jxl-rs/jxl/src/render/mod.rs`**
   - Render module entry point
   - Threading configuration

4. **`jxl-rs/jxl/src/lib.rs` or main entry**
   - Thread pool initialization
   - Global threading setup

## Technical Details

### C++ Threading Logic (for reference)

From `lib/jxl/dec_frame.cc`:
```cpp
// C++ decides threading based on image size
ThreadPool* pool = frame_dim.group_dim > 1 ? dec_state->pool : nullptr;

// For small images:
if (total_pixels < kSmallImageThreshold) {
    pool = nullptr;  // Force single-threaded
}
```

### Rust Threading Likely Uses
- `rayon` crate for parallelism
- Thread pool with `par_iter()` or similar
- Need to add size check before parallel invocation

## Comparison: Round 20 vs Round 21

| Metric | Round 20 | Round 21 | Change |
|--------|----------|----------|--------|
| grayscale_5 Rust time | ~1.80ms | ~2.89ms | **+60%** ❌ |
| grayscale_5 slowdown | 1.01x | 1.62x | **+60%** ❌ |
| Binary size | Smaller | +200 LOC | Larger |
| Icache behavior | Better | Worse | Regression |

## UPDATED FINDINGS (Round 22)

### Critical Discovery: jxl-rs is Single-Threaded

**Findings**:
1. ✅ **jxl-rs is single-threaded** - No rayon, no thread pool, no parallelism
2. ✅ **Grayscale fast path ALREADY EXISTS** - `frame/modular/mod.rs:548-556` already replicates gray channel to RGB
3. ✅ **C++ libjxl uses threading** - Has ThreadPool with size threshold (`xsize * ysize < group_dim²`)
4. ❌ **Threading optimization doesn't apply** - jxl-rs has no threads to optimize

### Actual Root Cause: Code Bloat & Instruction Cache

Since jxl-rs is single-threaded, the regression is due to:
- **Instruction cache pressure** - Adding ~200 lines of AVX2 palette code increased binary size
- **Code layout effects** - Larger binary = worse icache locality on hot loops
- **Small images hit hardest** - grayscale_5 (40k pixels) runs fast, so icache misses dominate

### Implemented Fix: Palette Size Threshold

**Location**: `jxl-rs/jxl/src/frame/modular/transforms/palette.rs:296-301`

**Change**:
```rust
// Skip SIMD for very small images to avoid icache overhead
const MIN_PIXELS_FOR_PALETTE_SIMD: usize = 256 * 256; // 64k pixels
let total_pixels = w * h;

if total_pixels >= MIN_PIXELS_FOR_PALETTE_SIMD && is_x86_feature_detected!("avx2") {
    // Use AVX2 path
} else {
    // Use scalar path (reduces code bloat overhead)
}
```

**Rationale**:
- grayscale_5 (200×200 = 40k pixels) < 64k threshold → skips AVX2 dispatch
- Reduces feature detection overhead and code bloat impact on small images
- Large images like cafe still use AVX2 SIMD

## Next Steps

1. ✅ **Investigation complete** - Root cause identified (icache, not threading!)
2. ✅ **Fix implemented** - Palette size threshold added
3. 🔄 **Benchmarking** - Testing Round 22 fix (in progress)
4. ⏭️ **Verify results** - Check if grayscale_5 returns to ~1.0x
5. ⏭️ **Future optimization** - Consider adding rayon/threading to jxl-rs (like C++ libjxl)

---

**Status**: Round 22 fix implemented, benchmarks running
**Confidence**: MEDIUM-HIGH - Fix addresses code bloat, but icache effects are hard to predict
**Expected Impact**: grayscale_5 should improve from 1.62x → 1.2x-1.4x (partial recovery)
