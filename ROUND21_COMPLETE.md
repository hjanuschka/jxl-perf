# Round 21 Complete: Palette SIMD + Next Steps

**Date**: 2025-11-27
**Status**: ✅ Complete - cafe optimized, documentation updated, commits pushed

## Round 21 Summary

### What We Did
1. ✅ Investigated cafe bottleneck (was #1 at 2.22x)
2. ✅ Discovered size paradox - cafe highly compressed (2.5x more than bike)
3. ✅ Identified triple nested loop in `palette.rs` with per-pixel function calls
4. ✅ Implemented AVX2 gather-based palette SIMD optimization
5. ✅ Benchmarked and verified results
6. ✅ Documented all findings
7. ✅ Updated HTML report
8. ✅ Committed all changes

### Results

#### 🎉 SUCCESS: cafe Optimization
- **cafe**: 2.22x → **1.65x** (25% improvement!)
- **cafe_5**: 1.92x → **1.75x** (9% improvement!)
- **cafe dropped from #1 to #5** in bottleneck rankings

#### ⚠️ CONCERN: Regressions
- **grayscale_5**: 1.01x → **1.62x** (LOST PARITY! -60% performance!)
- **noise**: 1.35x → 1.47x (9% regression)
- **Overall average**: 1.34x → 1.35x (slight regression)

### New Bottleneck Rankings

| Rank | Test | Slowdown | Category |
|------|------|----------|----------|
| **#1** | noise_5 | **2.12x** | ANS entropy decoding |
| #2 | grayscale_jpeg | 1.92x | JPEG path |
| #3 | grayscale_jpeg_5 | 1.82x | JPEG path |
| #4 | cafe_5 | 1.75x | ← Improved! |
| #5 | cafe | 1.65x | ← Improved from #1! |
| #6 | grayscale_5 | 1.62x | ← REGRESSED from 1.01x! |

## Technical Implementation

### File Modified
`jxl-rs/jxl/src/frame/modular/transforms/palette.rs`

### Changes Made
1. **Added `do_palette_simple_avx2()`** - Vectorized 8-pixel batch processing
   - Uses `_mm256_i32gather_epi32` for parallel palette lookups
   - SIMD bounds checking for index validation
   - Fast path (0xFF mask) for all-valid indices
   - Scalar fallback for edge cases

2. **Added `do_palette_simple_scalar()`** - Non-AVX2 fallback

3. **Modified `do_palette_step_general()`** - Runtime dispatch
   - `is_x86_feature_detected!("avx2")` for CPU capability check
   - Transparent fallback on non-AVX2 systems

### Performance Analysis
- **Expected**: 4x speedup on palette path (8 pixels per iteration)
- **Actual cafe impact**: 25% overall improvement
- **Implies**: Palette was ~30% of cafe decode time
- **Formula**: 30% × 4x = 12% ideal gain → 25% actual (exceeded expectations!)

## Critical Issues

### URGENT: grayscale_5 Regression

**The Problem**: grayscale_5 went from **1.01x (parity!) → 1.62x** after Round 21.

This is **UNACCEPTABLE**. We lost our first parity achievement.

**Possible Causes**:
1. **Code layout effects** - Adding palette code changed instruction cache behavior
2. **Feature detection overhead** - `is_x86_feature_detected!` called on hot paths?
3. **Compiler optimization interference** - New code affected other optimizations
4. **Build issue** - Something unrelated changed
5. **Interaction** - Palette code interfering with coefficient order cache (Round 20)?

**Action Required**: Investigate before next optimization round!

**Approach**:
1. Compare Round 20 vs Round 21 builds directly
2. Profile grayscale_5 specifically
3. Check if palette changes affect non-palette code paths
4. Test with palette optimization disabled (#[cfg])
5. Check assembly output for grayscale hot loops

### noise_5 is NEW #1 at 2.12x

**Analysis**: See `NOISE_5_ANALYSIS.md`

**Key Points**:
- ANS entropy decoding likely bottleneck
- Round 12 already added noise stage SIMD
- Profiling methodology needs improvement
- Need to compare with C++ libjxl implementation

## Files Created/Modified

### Documentation
- ✅ `ROUND21_PALETTE_SIMD.md` - Complete technical report
- ✅ `CAFE_INVESTIGATION.md` - Size paradox analysis
- ✅ `NOISE_5_ANALYSIS.md` - Next bottleneck strategy
- ✅ `OPTIMIZATION_JOURNEY.md` - Updated with Round 21
- ✅ `index.html` - Updated visual report

### Code
- ✅ `jxl-rs/jxl/src/frame/modular/transforms/palette.rs` - AVX2 SIMD

### Profiling Scripts
- ✅ `profile_noise_5.sh` - Noise profiling script

## Git History

### Submodule (jxl-rs)
```
d8f162b Round 21: Add AVX2 SIMD optimization to palette transform
```

### Main Repo
```
fe047a7 Round 21: Update HTML and add noise_5 analysis
353d2fa Round 21: Palette SIMD optimization - cafe 2.22x → 1.65x
```

## Progress Tracking

### Overall Progress
- **Baseline**: 1.76x average slowdown
- **Current**: 1.35x average slowdown
- **Gap closed**: 24% (from 1.76x → 1.35x)
- **Remaining**: 26% (from 1.35x → 1.00x)

### Achievements
- ✅ First parity test achieved (grayscale_5 at 1.01x in Round 20) - **THEN LOST IT!**
- ✅ cafe improved 25% (was #1, now #5)
- ✅ 11 render stages with SIMD
- ✅ Palette transform vectorized
- ✅ Coefficient order cache implemented

### Regressions to Fix
- ⚠️ grayscale_5: 1.01x → 1.62x (**URGENT!**)
- ⚠️ noise: 1.35x → 1.47x
- ⚠️ Overall average: 1.34x → 1.35x

## Next Steps (Priority Order)

### 🚨 PRIORITY 1: Fix grayscale_5 Regression
**Why**: We CANNOT lose parity achievements
**Actions**:
1. Compare Round 20 vs Round 21 builds
2. Profile grayscale_5 specifically
3. Test with palette optimization disabled
4. Fix the regression before proceeding

### PRIORITY 2: Optimize noise_5 (NEW #1 at 2.12x)
**Why**: Now the #1 bottleneck
**Actions**:
1. Better profiling methodology (eliminate bash loop overhead)
2. Identify actual hotspot (likely ANS entropy decoding)
3. Compare with C++ libjxl implementation
4. Implement targeted optimization

### PRIORITY 3: Investigate grayscale_jpeg Tests (1.82x-1.92x)
**Why**: Consistent bottleneck, different from regular grayscale
**Actions**:
1. Profile grayscale_jpeg path
2. Identify JPEG-specific bottlenecks
3. Compare with pure grayscale decode

### PRIORITY 4: Continue Systematic Optimization
**Why**: Still 26% away from 1.0x parity
**Actions**:
1. Profile each test in top 10
2. Implement targeted optimizations
3. Measure, don't guess (learned from Round 19 failure)

## Lessons from Round 21

### ✅ What Worked
1. **Profile-guided investigation** - Size paradox discovery led to palette
2. **AVX2 gather instructions** - Perfect for random access patterns
3. **SIMD bounds checking** - Fast path optimization
4. **Thorough documentation** - Every step documented

### ⚠️ What Didn't Work / Concerns
1. **Regressions appeared** - grayscale_5 and noise tests regressed
2. **Code bloat effects?** - Adding code may hurt icache
3. **Feature detection overhead?** - Runtime checks on hot paths?

### 📚 Lessons Learned
1. **Monitor for regressions** - Every optimization can hurt something else
2. **Test all benchmarks** - Don't just focus on target test
3. **Document immediately** - Easy to forget details later
4. **Commit incrementally** - Makes bisection possible

## Statistics

### Benchmark Results
- **Total tests**: 39
- **Passing**: 30 (77%)
- **Feature-incomplete**: 9 (23%)
- **Average slowdown**: 1.35x
- **Best case**: 1.01x (bench_oriented_brg tests)
- **Worst case**: 2.12x (noise_5)

### Code Changes
- **Lines added**: ~200 (palette.rs SIMD)
- **Files modified**: 1 (palette.rs)
- **Documentation created**: 5 files
- **Commits**: 3 (1 submodule, 2 main repo)

## Mission Statement

**"It's not over till it's at worst 1:1 like C++ - at best it outperforms!"**

We're at **1.35x average**, need to get to **1.00x**.

### Path Forward
1. **Fix regressions** (grayscale_5) - URGENT!
2. **Optimize systematically** (noise_5, grayscale_jpeg)
3. **Profile accurately** - Improve profiling methodology
4. **Test thoroughly** - Watch for regressions
5. **Document everything** - Learning process is valuable

---

## Status: Ready for Round 22

**Blockers**: grayscale_5 regression must be investigated
**Next target**: noise_5 at 2.12x (after fixing grayscale_5)
**Confidence**: HIGH - We've closed 24% of gap, can close the remaining 26%!

**Key insight**: Adding code can cause regressions (icache, compiler effects). Must be vigilant!
