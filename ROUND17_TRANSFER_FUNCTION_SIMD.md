# Round 17: Transfer Function SIMD Optimizations

## Goal
Continue push toward 1.0x parity with C++ libjxl. Current status: 1.35x average slowdown. Target: 1.0x or better!

## Changes Made

### 1. Fixed BT.709 to Linear - Missing SIMD Call

**File**: `jxl/src/render/stages/to_linear.rs:74`

**Problem**: The code was calling `tf::bt709_to_linear()` (scalar version) even though `tf::bt709_to_linear_simd()` already existed!

**Before**:
```rust
TransferFunction::Bt709 => {
    for row in row {
        tf::bt709_to_linear(&mut row[..xsize]);  // SCALAR!
    }
}
```

**After**:
```rust
TransferFunction::Bt709 => {
    for row in row {
        tf::bt709_to_linear_simd(d, &mut row[..xsize.next_multiple_of(D::F32Vec::LEN)]);
    }
}
```

**Impact**: Likely significant for grayscale_jpeg test (2.02x slow) if it uses BT.709 transfer function.

---

### 2. Added PQ Transfer Function SIMD

**File**: `jxl/src/color/tf.rs:307-323`

**Created**: New `pq_to_linear_simd()` function using existing `eval_rational_poly_simd()` helper

**Implementation**:
```rust
#[inline(always)]
pub fn pq_to_linear_simd<D: SimdDescriptor>(d: D, intensity_target: f32, samples: &mut [f32]) {
    let y_mult = D::F32Vec::splat(d, 10000.0 / intensity_target);

    for vec in samples.chunks_exact_mut(D::F32Vec::LEN) {
        let s = D::F32Vec::load(d, vec);
        let a = s.abs();
        let x = a.mul_add(a, a);  // a + a*a
        let y = eval_rational_poly_simd(d, x, PQ_EOTF_P, PQ_EOTF_Q);
        (y * y_mult).copysign(s).store(vec);
    }

    let remainder = samples.chunks_exact_mut(D::F32Vec::LEN).into_remainder();
    pq_to_linear(intensity_target, remainder);
}
```

**Updated**: `jxl/src/render/stages/to_linear.rs:84` to use SIMD version

**Impact**: Helps HDR images using PQ (Perceptual Quantizer) transfer function

---

## Technical Details

### Why This Matters

Transfer functions convert between:
- **Non-linear encoded values** (e.g., sRGB, BT.709, PQ, HLG)
- **Linear light values** (what math/rendering actually needs)

Every pixel goes through transfer function conversion, making this a hot path.

### What We Optimized

1. **BT.709**: Used by many broadcast/video sources, likely used in grayscale_jpeg
2. **PQ (Perceptual Quantizer)**: HDR standard (ST 2084)
3. **Already optimized**: sRGB, Gamma

### What's Still Scalar

- **HLG (Hybrid Log-Gamma)**: More complex, uses `fast_powf` per pixel
- **linear_to_pq**: Inverse direction (display to file encoding)

## Build and Test Results

**Build**: ✅ Success
```
Finished `release` profile [optimized + debuginfo] target(s) in 21.85s
```

**Tests**: ✅ All 8 to_linear tests passed

**Code Changes**:
- Modified files: 2
- Lines changed: +29/-3
- New functions: 1 (`pq_to_linear_simd`)

## Expected Performance Impact

### Optimistic Case
If grayscale_jpeg uses BT.709 transfer function:
- **Before**: 2.02x slower (scalar loop)
- **After**: Could drop to ~1.5x or better (SIMD)
- **Improvement**: Up to 25% faster

### Realistic Case
- Moderate improvement on BT.709 images
- Visible improvement on PQ/HDR content
- May not solve grayscale bottleneck if it's elsewhere

### Worst Case
- Transfer functions not the bottleneck
- Minimal improvement in average
- Still helps code consistency

## Next Steps

1. **Wait for benchmarks** to see actual impact
2. **If grayscale still 2x slow**:
   - Profile to find real bottleneck
   - May be in JPEG decoding, modular transforms, or memory ops
3. **Consider**:
   - HLG SIMD optimization (more complex)
   - Palette transform SIMD (affects modular images)
   - Actual profiling of slow tests

## Commitment

**"It's not over till it's at worst 1:1 like C++ - at best it outperforms!"**

Current progress:
- Baseline: 1.76x
- Round 12: 1.33x (last measured)
- Round 17: TBD (benchmarking...)

We've closed **43% of the gap** so far. Let's get to 100%!
