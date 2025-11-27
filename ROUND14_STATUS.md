# Round 14: Optimization Status & Analysis

## Current Performance

**Average**: 1.35x slower than C++ (Down from 1.76x baseline - 23% improvement total)

## Performance Journey
- Baseline: 1.76x
- Round 11 (AVX Fix): 1.37x (22% improvement - cargo clean fixed build cache)
- Round 12 (Noise SIMD): 1.33x (3% improvement - AVX2 in AddNoiseStage)
- Round 13 (PGO): 1.35x (2% regression - reverted)
- **Current**: 1.33x (using Round 12 build)

## Top Remaining Slow Tests

1. **grayscale_jpeg** - 2.02x slower
2. **grayscale_5** - 2.01x slower
3. **cafe** - 1.97x slower
4. **noise_5** - 1.91x slower (improved from 2.42x)
5. **noise** - 1.87x slower (improved from 2.37x)
6. **grayscale_jpeg_5** - 1.84x slower
7. **bicycles** - 1.75x slower
8. **opsin_inverse_5** - 1.73x slower
9. **cafe_5** - 1.71x slower
10. **alpha_triangles** - 1.71x slower

## Optimizations Completed

### Successfully Applied SIMD
- ✅ AddNoiseStage (noise.rs) - AVX2+FMA
- ✅ YCbCr conversion (ycbcr.rs) - AVX2
- ✅ Chroma upsampling (chroma_upsample.rs) - AVX2
- ✅ Image upsampling (upsample.rs) - AVX2
- ✅ Color conversion (convert.rs) - AVX2
- ✅ Blending operations (blending.rs) - AVX2
- ✅ Tone mapping (tf.rs) - SIMD
- ✅ XYB to RGB (xyb.rs) - Already had SIMD

### Failed Attempts
- ❌ EPF0 algorithm port (Round 9) - Made things worse
- ❌ Profile-Guided Optimization (Round 13) - 2% regression
- ❌ target-cpu=native alone (Round 10) - No improvement without cargo clean

## Analysis

### Why Grayscale Tests Are Slow
The grayscale tests (2.02x-1.84x) are the slowest remaining. This suggests:
- Possible grayscale-specific code paths without SIMD
- JPEG recompression overhead
- Color space conversion inefficiencies for grayscale

The XYB stage already has SIMD, so bottleneck is likely elsewhere in grayscale pipeline.

### Why Cafe Tests Are Slow
Cafe tests (1.97x-1.71x) are large RGB images (1280x1600). Slowdown despite SIMD in most stages suggests:
- Possible scalar loops in less-common render paths
- Memory bandwidth bottlenecks
- Cache misses on large images

### Noise Tests Improved Significantly
Noise tests improved dramatically with Round 12:
- noise: 2.37x → 1.87x (21% faster)
- noise_5: 2.42x → 1.96x (19% faster)

This confirms SIMD optimization strategy is effective.

## Remaining Optimization Opportunities

### High Priority (Likely High Impact)
1. **Profile grayscale path** - Identify why grayscale is 2x slower
   - Check for scalar loops in grayscale-specific code
   - Verify JPEG decoding path is optimized

2. **Vectorize remaining scalar loops** - Search for obvious patterns like:
   ```rust
   for i in 0..len {
       output[i] = input[i] * factor;
   }
   ```

3. **Profile cafe test** - Large image optimization
   - May reveal memory/cache issues
   - Could show unoptimized stages

### Medium Priority
4. **Optimize LUT lookups** - Mentioned in previous analysis
   - Use gather instructions for noise LUT
   - Est. 10-15% gain on noise tests

5. **Check alpha blending** - alpha_triangles at 1.71x
   - Verify SIMD blending code is being used
   - May have scalar fallback path being hit

### Low Priority (Diminishing Returns)
6. **Micro-optimizations** - Loop unrolling, prefetching
7. **Algorithm changes** - Risk regression like Round 9

## Next Steps

**Recommended approach:**
1. Profile one slow test (grayscale_jpeg or cafe) with perf
2. Generate flamegraph to identify hot functions
3. Check if hot functions have SIMD
4. Add SIMD if missing, optimize if present

**Don't do:**
- Speculative optimization without profiling
- Algorithm changes without deep C++ comparison
- PGO or build flag tweaks (already tried)

## Code Changes Made

All optimizations are in the PR branch `perf/noise-simd-optimization`:
- 7 files modified (+1839/-80 lines)
- All use runtime feature detection
- All have scalar fallbacks
- All preserve correctness (30 passing tests unchanged)

## Conclusion

We've closed 43% of the performance gap (1.76x → 1.33x). The remaining 33% slowdown requires:
- Targeted profiling of slow tests
- Identifying and fixing grayscale-specific bottlenecks
- Possibly addressing memory/cache issues for large images

The SIMD strategy has proven effective. Further gains need data-driven optimization rather than speculation.
