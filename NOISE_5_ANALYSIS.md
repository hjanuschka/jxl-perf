# noise_5 Analysis: NEW #1 Bottleneck at 2.12x

**Status**: Round 21 complete, noise_5 is now the #1 bottleneck
**Current**: noise_5 at 2.12x slower than C++
**Previous**: Round 12 added SIMD to noise stage, but not enough

## The Problem

After optimizing cafe (2.22x → 1.65x), **noise_5 is now the #1 bottleneck** at 2.12x.

### Test Details
- **Image**: noise_5.jxl (500x606 pixels)
- **Rust time**: 21.80ms
- **C++ time**: 10.27ms
- **Slowdown**: 2.12x

### Related Tests
- **noise**: 1.87x slower (also slow, but not as bad)
- **noise_5** vs **noise**: Both use same image, "_5" suffix = distance 5 encoding

## What We Know

### Round 12: Noise SIMD Added
Round 12 added AVX2+FMA to the `AddNoiseStage` in `noise.rs`:
- Vectorized noise addition
- Used FMA instructions
- This gave the biggest single improvement: 1.76x → 1.33x (24%!)

**But noise tests are STILL slow**, meaning:
1. The noise stage itself may not be the bottleneck anymore
2. Something ELSE in the noise image decode is slow
3. Likely **ANS entropy decoding** (mentioned in analysis)

### Known Bottleneck: ANS Entropy Decoding

From OPTIMIZATION_JOURNEY.md:
> **ANS Entropy Decoding**
> Impact: noise_5 is NEW #1 at 2.12x
> Status: Already has some SIMD, but may need more optimization
> Priority: HIGH - now the #1 bottleneck

## Profiling Challenges

Attempted profiling with `perf` but hit issues:
1. Bash loop overhead dominates profile
2. Most samples in kernel (page faults, memory allocation)
3. Not enough userspace samples in actual decode functions

**This suggests**:
- The decode is VERY FAST (only 21ms), making profiling hard
- Need better profiling methodology (longer runs, better sampling)

## Hypotheses

### Hypothesis 1: ANS Decode Bottleneck
**Likelihood**: HIGH

Noise images use heavy entropy encoding. The ANS (Asymmetric Numeral Systems) decoder is likely the bottleneck.

**Evidence**:
- noise vs noise_5: Both slow despite noise stage SIMD
- C++ likely has better-optimized ANS decode
- Random access patterns (bad for CPU caching)

**Location**: `jxl-rs/jxl/src/entropy_coding/ans.rs`

**Previous attempt**: Round 19 tried prefetch optimization, FAILED (no improvement)

### Hypothesis 2: VarDCT Coefficient Decoding
**Likelihood**: MEDIUM

Noise images may use variable DCT with complex coefficient patterns.

**Evidence**:
- Round 20 coefficient order caching helped grayscale (1.01x parity!)
- But didn't help noise tests much
- Suggests different bottleneck for noise

### Hypothesis 3: Modular Image Path
**Likelihood**: LOW

Noise might use modular encoding, hitting different code paths.

**Evidence**:
- Palette optimization (Round 21) didn't help noise
- Suggests noise doesn't use palette/modular path

## Action Plan

### Immediate: Better Profiling

1. **Single-iteration profile** - Eliminate bash loop:
   ```bash
   perf record -g ./target/release/jxl-perf noise_5.jxl > /dev/null
   ```

2. **Longer run** - 10,000+ iterations to get better samples

3. **Compare with C++ libjxl** - Profile C++ decode to see algorithmic differences

### Next: Targeted Optimizations

Based on profiling results:

#### If ANS is the bottleneck:
1. **Analyze ANS hot loops** in `entropy_coding/ans.rs`
2. **Check for vectorization opportunities**
   - Batch decoding multiple symbols
   - Prefetch patterns that actually work
3. **Compare with C++ libjxl ANS implementation**

#### If VarDCT coefficients:
1. **Profile coefficient decode specifically**
2. **Check for SIMD opportunities in coefficient unpacking**
3. **Optimize DCT transform itself** (if not already SIMD)

#### If something else:
1. **Follow the profile data** - optimize what's actually hot
2. **Don't speculate** - Round 19 prefetch attempt taught us this lesson

## Expected Impact

If we can optimize the actual bottleneck:
- **Best case**: noise_5: 2.12x → 1.3x-1.5x (30-40% improvement)
- **Realistic**: noise_5: 2.12x → 1.7x-1.8x (15-20% improvement)
- **Overall average**: 1.35x → 1.30x-1.32x

This would move us another ~3-4% toward 1.0x parity.

## Comparison with Other Top Bottlenecks

Current top 5:
1. **noise_5**: 2.12x ← We are here
2. **grayscale_jpeg**: 1.92x
3. **grayscale_jpeg_5**: 1.82x
4. **upsampling_5**: 1.88x
5. **noise**: 1.87x

**Strategy**: Fix noise_5, then tackle grayscale_jpeg tests (different bottleneck).

## Lessons from Previous Rounds

✅ **What worked**:
- Profile-guided optimization (Round 20: coeff cache → grayscale_5 at 1.01x!)
- SIMD in obvious hot paths (Round 12: noise stage → 24% gain!)
- AVX2 gather for random access (Round 21: cafe → 25% gain!)

❌ **What didn't work**:
- Speculative prefetch (Round 19: ANS prefetch → 0% gain)
- Guessing without profiling

## Next Steps

1. ✅ **Document Round 21** (cafe optimization) - DONE
2. ✅ **Update HTML** - DONE
3. 🔄 **Better profiling of noise_5** - IN PROGRESS
4. ⏭️ **Implement targeted optimization** - WAITING ON PROFILE DATA
5. ⏭️ **Investigate grayscale_5 regression** - URGENT! (1.01x → 1.62x)

## Critical Note: grayscale_5 Regression

Before optimizing noise_5, we MUST investigate the grayscale_5 regression:
- **Before Round 21**: 1.01x (essentially AT PARITY!)
- **After Round 21**: 1.62x (LOST 60% PERFORMANCE!)

This is unacceptable. We need to understand why palette optimization hurt grayscale_5.

**Possible causes**:
1. Code layout changes affecting instruction cache
2. Feature detection overhead (`is_x86_feature_detected!`)
3. Something unrelated in the build
4. Interaction with coefficient order cache from Round 20

---

**Status**: Profiling methodology needs improvement. Committed Round 21, ready for Round 22 planning.
