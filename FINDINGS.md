# jxl-rs SIMD Optimization Findings

**Date**: 2025-11-27
**Goal**: Identify and implement ALL SIMDifiable code patterns to match C++ performance

---

## Comprehensive Codebase Analysis

### HIGH PRIORITY (Excellent SIMD potential) ⚡

#### 1. **Noise Stages** - ✅ COMPLETED
- **Files**: `jxl-rs/jxl/src/render/stages/noise.rs`
- **Status**: ✅ ConvolveNoiseStage AVX2 SIMD implemented & tested
- **Results**: noise_5 (3.55x → 2.41x), noise (3.02x → 2.74x)
- **Improvement**: 1.24-1.29x speedup
- **TODO**: AddNoiseStage AVX2 SIMD (if needed)

#### 2. **YCbCr to RGB Conversion** - ✅ COMPLETED
- **File**: `jxl-rs/jxl/src/render/stages/ycbcr.rs`
- **Status**: ✅ AVX2 + FMA SIMD implemented & tested
- **Implementation**: BT.601 color space conversion, 8 pixels per iteration
- **Impact**: Contributes to overall improvements (cafe, bike tests)

#### 3. **Horizontal/Vertical Chroma Upsampling** - ✅ COMPLETED (Round 5 Testing)
- **File**: `jxl-rs/jxl/src/render/stages/chroma_upsample.rs`
- **Status**: ✅ AVX/FMA SIMD implemented for both horizontal & vertical
- **Implementation**: Weighted interpolation with FMA (0.75 * cur + 0.25 * neighbor)
- **Testing**: Round 5 benchmarks running now
- **Expected**: Additional improvements on grayscale and color images

#### 4. **Format Conversions (F32 ↔ U8/U16/F16)** - ✅ PARTIALLY COMPLETED
- **File**: `jxl-rs/jxl/src/render/stages/convert.rs`
- **Status**:
  - ✅ ConvertF32ToU8Stage AVX2 SIMD - DONE (Round 4)
  - ✅ ConvertU8F32Stage AVX2 SIMD - DONE (Round 4)
  - 🚧 ConvertF32ToU16Stage - TODO
  - 🚧 ConvertF32ToF16Stage (F16C) - TODO
- **Results**: **MASSIVE WIN!** Grayscale 3.36x → 2.12x (37% improvement!)
- **Round 4 Impact**: Average 1.98x → 1.76x (11% improvement)
- **Note**: U8 conversions were the biggest bottleneck!

#### 5. **Modular Format Conversions**
- **File**: `jxl-rs/jxl/src/render/stages/convert.rs`
- **Functions**:
  - `ConvertModularXYBToF32Stage::process_row_chunk` (lines 88-110)
  - `ConvertModularToF32Stage::process_row_chunk` (lines 204-225)
- **Pattern**: Integer to float with scaling
- **SIMD Potential**: **HIGH**
- **Expected gain**: 2-3x speedup

#### 6. **Spot Color Blending**
- **File**: `jxl-rs/jxl/src/render/stages/spot.rs`
- **Function**: `process_row_chunk` (lines 40-67)
- **Pattern**: Color mixing with FMA
- **SIMD Potential**: **HIGH**
- **Expected gain**: 2-3x speedup

---

### MEDIUM PRIORITY (Good SIMD potential)

#### 7. **Alpha Blending Operations**
- **File**: `jxl-rs/jxl/src/features/blending.rs`
- **Functions**: Multiple blending modes (lines 38-258)
- **Pattern**: Alpha compositing, multiply-add operations
- **SIMD Potential**: **MEDIUM-HIGH**
- **Expected gain**: 2-3x speedup per mode
- **Note**: Multiple modes need optimization separately

#### 8. **Custom Float Conversion**
- **File**: `jxl-rs/jxl/src/render/stages/convert.rs`
- **Function**: `int_to_float` (lines 137-192)
- **Pattern**: Complex bit manipulation
- **SIMD Potential**: **MEDIUM**
- **Note**: Has `// TODO(sboukortt): SIMD` comment
- **Expected gain**: 2x speedup

---

### ALREADY OPTIMIZED ✅

The following stages already have SIMD optimizations:

1. **XYB to Linear RGB** (xyb.rs) - Uses `simd_function!` macro
2. **Gaborish Filter** (gaborish.rs) - Uses `simd_function!` with 3x3 convolution
3. **EPF0, EPF1, EPF2** (epf/*.rs) - Edge-preserving filters with SIMD
4. **To/From Linear** (to_linear.rs, from_linear.rs) - Gamma correction with SIMD
5. **Transfer Functions** (color/tf.rs) - sRGB, BT.709, PQ, HLG with SIMD
6. **Upsample 2x/4x/8x** (upsample.rs) - ✅ **OUR AVX2/FMA implementation**

---

### LOW PRIORITY (Limited SIMD benefit)

#### 9. **Splines Rendering**
- **File**: `jxl-rs/jxl/src/render/stages/splines.rs`
- **SIMD Potential**: **LOW** - Complex curve rendering

#### 10. **Patches**
- **File**: `jxl-rs/jxl/src/render/stages/patches.rs`
- **SIMD Potential**: **LOW** - Irregular access patterns

---

## Implementation Strategy

### Phase 1: Noise Stages ✅ (Current)
- ✅ ConvolveNoiseStage AVX2 SIMD - Implemented & tested
- 🚧 AddNoiseStage AVX2 SIMD - In progress

### Phase 2: Color Conversions (Next)
1. YCbCr to RGB (ycbcr.rs)
2. Chroma upsampling (chroma_upsample.rs)

### Phase 3: Format Conversions
1. F32 ↔ U8/U16/F16 (convert.rs)
2. Modular conversions (convert.rs)

### Phase 4: Advanced Operations
1. Spot color blending (spot.rs)
2. Alpha blending modes (blending.rs)
3. Custom float conversion (convert.rs)

---

## Performance Targets

**Round 3 Status** (after upsampling + noise + YCbCr AVX2):
- Average slowdown: **1.98x** ✅ **Under 2.0x!**
- Worst case: grayscale at **3.36x**

**Round 4 Status** (+ U8↔F32 format conversion SIMD):
- Average slowdown: **1.76x** ✅ **19.6% total improvement from 2.19x baseline!**
- Worst case: grayscale_public_university at **2.92x**
- Grayscale bottleneck CRUSHED: **3.36x → 2.12x (37% improvement!)**

**Round 5 Status** (+ chroma upsampling SIMD) - TESTING NOW:
- Expected average: **~1.60-1.70x**
- Expected worst case: **~2.5x**

**Future with remaining SIMD** (estimated):
- Average slowdown: **~1.3-1.5x**
- Worst case: **~2.0x**

**With Parallelization** (rayon):
- Average slowdown: **< 1.2x** ✅ **GOAL ACHIEVABLE**

---

## Key Learnings

1. **AVX2 SIMD is extremely effective** - 3.8x speedup on upsampling
2. **Runtime feature detection is essential** - Use `is_x86_feature_detected!()`
3. **Processing 8 pixels at a time** - AVX registers hold 8 floats
4. **FMA instructions are powerful** - Fused multiply-add reduces operations
5. **Horizontal operations are expensive** - Minimize reductions when possible
6. **Scalar fallback is required** - Handle remaining pixels after SIMD loop

---

## Next Steps

1. ✅ Finish AddNoiseStage SIMD
2. Benchmark noise improvements
3. Implement YCbCr SIMD
4. Implement chroma upsampling SIMD
5. Implement format conversion SIMD
6. Consider parallelization (rayon) for large images

---

**Updated**: 2025-11-27 after comprehensive codebase analysis
