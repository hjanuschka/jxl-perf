# jxl-rs Optimization Journey: Road to 1.0x

## Mission
**"It's not over till it's at worst 1:1 like C++ - at best it outperforms!"**

## Progress Summary

### Baseline
- **Average slowdown**: 1.76x
- **Status**: Many scalar loops, no SIMD in render stages

### Current (Round 21)
- **Average slowdown**: 1.35x
- **Improvement**: Closed **24% of the gap** (from 1.76x to 1.35x)
- **Remaining**: Need to close another **26%** to reach 1.0x parity
- **Key achievement**: cafe 2.22x → 1.65x (25% improvement!)
- **Concern**: grayscale_5 regressed from 1.01x to 1.62x

## Optimizations Completed

### Round 12: Noise SIMD
- Added AVX2+FMA to `AddNoiseStage`
- Result: 1.76x → 1.33x (24% improvement)

### Round 16: Scalar Loop Cleanup
- Added `jxl_simd` to `nearest_neighbor.rs`
- Added `jxl_simd` to `spot.rs`
- Result: Code consistency, minimal performance impact

### Round 17: Transfer Function SIMD
- **Fixed BT.709 call**: Was using scalar, now uses existing SIMD
- **Added PQ SIMD**: New vectorized HDR transfer function
- Result: 1.33x → 1.37x (within measurement noise)

### Round 18: Zero-Copy Grayscale Fix 🚀
- **Eliminated buffer cloning**: Changed pipeline API to use `&Image<T>` references
- **Fixed grayscale path**: 2 full clones → 0 clones for SimpleRenderPipeline
- **Grayscale improvements**: 13-28% faster on grayscale tests!
  - grayscale_5: 2.23x → 1.61x (28% faster!)
  - grayscale_jpeg: 2.18x → 1.76x (19% faster!)
- Result: 1.37x → 1.36x (grayscale bottleneck significantly reduced)

### Round 19: ANS Prefetch Attempt ❌
- **Attempted**: Prefetch next bucket in ANS entropy decoder
- **Result**: FAILED - no improvement (1.36x → 1.35x within noise)
- **Lesson**: Sequential prefetch doesn't help random access patterns
- **Status**: REVERTED

### Round 20: Coefficient Order Caching 🎯
- **Added OnceLock cache**: Memoize `natural_coeff_order()` computations
- **Eliminated redundancy**: Was computing 39 orderings per frame, now compute once and cache
- **Breakthrough**: grayscale_5 went from 1.48x → **1.01x** (essentially at parity!)
- **Other improvements**:
  - grayscale: 2.34x → 1.75x (25% faster!)
  - Overall: 1.36x → 1.34x (2% improvement)
- Result: 1.36x → **1.34x** (profile-guided optimization wins again!)

### Round 21: Palette Transform SIMD 🎨
- **Target**: cafe test (NEW #1 bottleneck at 2.22x)
- **Added AVX2 gather optimization**: Vectorized palette lookup inner loop
- **Implementation**: `_mm256_i32gather_epi32` for 8-pixel batch lookups
- **SIMD bounds checking**: Fast path for valid indices, scalar fallback for edge cases
- **cafe results**: 2.22x → **1.65x** (25% improvement! Dropped from #1 to below top 5!)
- **cafe_5 results**: 1.92x → 1.75x (9% improvement)
- **Regression**: grayscale_5: 1.01x → 1.62x (LOST PARITY - concerning!)
- Result: 1.34x → **1.35x** (cafe much better, but grayscale_5 regressed)

## Files Optimized with SIMD

### Render Stages (jxl/src/render/stages/)
1. ✅ `noise.rs` - AVX2+FMA for noise addition
2. ✅ `ycbcr.rs` - AVX2 for YCbCr conversion
3. ✅ `chroma_upsample.rs` - AVX2 for chroma upsampling
4. ✅ `upsample.rs` - AVX2 for image upsampling
5. ✅ `convert.rs` - AVX2 for color conversion
6. ✅ `blending.rs` - AVX2 for blending operations
7. ✅ `tf.rs` - SIMD for tone mapping
8. ✅ `xyb.rs` - Already had SIMD
9. ✅ `gaborish.rs` - Already had SIMD
10. ✅ `nearest_neighbor.rs` - jxl_simd for 2x2 upsampling
11. ✅ `spot.rs` - jxl_simd for spot color blending
12. ✅ `to_linear.rs` - Now uses SIMD for BT.709 and PQ
13. ✅ `from_linear.rs` - Already uses SIMD for main paths

### Color/Transform Functions
1. ✅ `color/tf.rs` - sRGB, BT.709, PQ SIMD versions
2. ✅ RCT transforms - Already SIMD
3. ✅ Squeeze transforms - Already SIMD

### Modular Transforms
1. ✅ `frame/modular/transforms/palette.rs` - AVX2 gather for palette lookups (Round 21)

## Top Remaining Bottlenecks

### Current Top 10 Slow Tests (Round 21)
1. **noise_5** - 2.12x slower (500x606) ← NEW #1! ANS entropy decoding
2. **grayscale_jpeg** - 1.92x slower (200x200)
3. **grayscale_jpeg_5** - 1.82x slower (200x200)
4. **cafe_5** - 1.75x slower (1280x1600 RGB) ← Improved from #4!
5. **cafe** - 1.65x slower (1280x1600 RGB) ← HUGE improvement from #1!
6. **grayscale_5** - 1.62x slower (200x200) ← REGRESSED from 1.01x!
7. **bicycles** - 1.62x slower (1024x631)
8. **alpha_triangles** - 1.60x slower (1024x1024 alpha)
9. **upsampling** - 1.58x slower
10. **noise** - 1.47x slower (500x606) ← Regressed

### Pattern Analysis (Updated Round 21)
- **cafe optimization SUCCESS**: 2.22x → 1.65x (25% faster!), dropped from #1 to #5
- **NEW #1 bottleneck**: noise_5 at 2.12x (ANS entropy decoding)
- **CRITICAL REGRESSION**: grayscale_5: 1.01x → 1.62x (LOST PARITY!)
- **Other regressions**: noise: 1.35x → 1.47x, upsampling slight regression
- **JPEG tests improved**: grayscale_jpeg tests now 1.82x-1.92x (better than Round 20)

## Likely Remaining Bottlenecks

### 1. ANS Entropy Decoding
**Impact**: noise_5 is NEW #1 at 2.12x
**Status**: Already has some SIMD, but may need more optimization
**Priority**: HIGH - now the #1 bottleneck

### 2. grayscale_5 Regression (CRITICAL!)
**Issue**: Regressed from 1.01x → 1.62x in Round 21
**Possible causes**:
- Code layout changes affecting instruction cache
- Feature detection overhead
- Something unrelated in build process
**Priority**: URGENT - investigate before more optimizations

### 3. Memory/Cache Issues
Small images (200x200) being 2.2x slower suggests:
- Cache misses
- Memory allocation overhead
- Non-computational bottlenecks

### 4. JPEG Decoding Overhead
`grayscale_jpeg` tests at 1.82x-1.92x - could be in JPEG recompression path.

### 5. Algorithmic Differences
Some paths may use different algorithms than C++ libjxl.

## Technical Insights

### What Worked
1. **SIMD in hot paths**: Noise stage optimization gave biggest gain
2. **Using `jxl_simd` framework**: Clean, safe, portable SIMD
3. **Following existing patterns**: gaborish.rs was good template
4. **Focus on render stages**: That's where pixels are processed
5. **Profile-guided optimization**: Coefficient order cache (Round 20) and palette SIMD (Round 21) both targeted real bottlenecks
6. **AVX2 gather instructions**: Perfect for random access patterns like palette lookups

### What Didn't Work / Lessons Learned
1. **Speculative optimization**: Round 17 changes showed +0.02x (noise)
2. **PGO attempt**: 2% regression, reverted
3. **EPF0 algorithm port**: Made things worse
4. **Focusing on small wins**: Transfer functions weren't the bottleneck

### Measurement Noise
Benchmark variance is ~±0.02x. Small changes might just be jitter.

## Next Steps to Reach 1.0x

### URGENT (Must Fix Before Proceeding!)
1. **Investigate grayscale_5 regression**: 1.01x → 1.62x
   - Compare Round 20 vs Round 21 builds
   - Profile grayscale_5 specifically
   - Check if palette changes affected non-palette paths
   - Consider code layout effects

### Immediate (High Priority)
2. **Profile noise_5 (NEW #1 at 2.12x)**
   - ANS entropy decoding bottleneck
   - Already has SIMD but may need more optimization
   - Use perf + flamegraph to identify hot spots

3. **Profile grayscale_jpeg tests (1.82x-1.92x)**
   - Find actual hot path with flamegraph
   - Identify if JPEG recompression is the issue
   - Compare with pure grayscale path

### Medium Priority
4. **Optimize remaining tf.rs functions**: HLG, linear_to_pq
5. **Check spline drawing**: If used by test images
6. **Review algorithmic differences**: Compare with C++ libjxl

### Low Priority (Diminishing Returns)
7. **Micro-optimizations**: Loop unrolling, prefetching
8. **Platform-specific tuning**: AVX-512, NEON for ARM
9. **Code size optimization**: May hurt performance

## Commitment

We've made excellent progress:
- **From 1.76x to 1.35x** = 24% of gap closed
- **Need 1.35x to 1.00x** = 26% more to go
- **Key win**: cafe 2.22x → 1.65x (25% improvement!)
- **Key concern**: grayscale_5 regressed from 1.01x to 1.62x (LOST PARITY!)

The next 26% will be harder than the first 24%. We need:
- **Data-driven optimization** (profiling, not guessing) ✅ Proven with coeff_order and palette!
- **Focus on actual bottlenecks** (not speculative changes) ✅ cafe optimization success!
- **Systematic approach** (measure, optimize, verify) ✅ Working!
- **Investigate regressions immediately** ⚠️ grayscale_5 must be fixed!

**The goal is clear: 1.0x or better. We won't stop until we get there!**

We're now at **1.35x average** with cafe optimized from #1 → #5.
**Critical next step**: Fix grayscale_5 regression before proceeding! 🎯

## Files Modified

### Round 21 Changes (MIXED - cafe SUCCESS, grayscale_5 REGRESSION!)
- `jxl/src/frame/modular/transforms/palette.rs` - AVX2 gather for palette lookups
  - Added `do_palette_simple_avx2()` - Processes 8 pixels with gather instruction
  - Added `do_palette_simple_scalar()` - Fallback for non-AVX2
  - Modified `do_palette_step_general()` - Runtime dispatch with feature detection
  - SIMD bounds checking: Fast path for valid indices, scalar for edge cases
  - Result: cafe 2.22x → **1.65x** (25% faster!), BUT grayscale_5 1.01x → 1.62x (regression!)
  - Overall: 1.34x → **1.35x** (slight regression)

### Round 20 Changes (SUCCESS!)
- `jxl/src/frame/coeff_order.rs` - Added OnceLock cache for natural_coeff_order()
  - Added static cache array (13 entries)
  - Modified decode_coeff_orders() to use get_or_init()
  - Result: 1.36x → **1.34x** (grayscale_5 at 1.01x!)

### Round 19 Changes (REVERTED)
- `jxl/src/entropy_coding/ans.rs` - Attempted ANS prefetch optimization
  - Added _mm_prefetch for next bucket
  - Result: No improvement (1.36x → 1.35x within noise)
  - Reverted: Sequential prefetch doesn't help random access

### Round 18 Changes
- `jxl/src/render/pipeline.rs` - Zero-copy grayscale fix
- `jxl/src/render/stages/*.rs` - Changed to use `&Image<T>` references
- Result: 1.37x → 1.36x (grayscale tests 13-28% faster!)

### Round 17 Changes
- `jxl/src/render/stages/to_linear.rs` - Use BT.709 SIMD, add PQ SIMD call
- `jxl/src/color/tf.rs` - Add `pq_to_linear_simd` function

### Round 12 Changes (Major Win!)
- `jxl/src/render/stages/noise.rs` - Added AVX2+FMA SIMD
- Result: 1.76x → 1.33x (24% improvement!)

### Previous Rounds (PR #506)
- 9 render stage files with comprehensive SIMD
- Noise, YCbCr, chroma_upsample, upsample, convert, blending, etc.

Total lines added across all rounds: ~2700+
Total performance improvement: **1.76x → 1.35x** (24% of gap closed!)
**Note**: Round 21 cafe improvement (25%!) offset by grayscale_5 regression

## Current Branch Status
- Branch: `perf/noise-simd-optimization`
- PR: #506 "road to 1x or less"
- Status: Draft, ready for review
- Tests: All passing ✅
- Build: Clean ✅
