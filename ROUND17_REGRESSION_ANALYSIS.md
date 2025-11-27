# Round 17: Performance Regression Analysis

## Results

**REGRESSION DETECTED**: Performance got WORSE instead of better!

### Before (Round 12/16)
- Average: **1.35x** slower
- grayscale_jpeg: **2.02x** slower
- grayscale_5: **2.01x** slower

### After (Round 17)
- Average: **1.37x** slower (+0.02x worse)
- grayscale_jpeg: **2.18x** slower (+0.16x worse!)
- grayscale_5: **2.23x** slower (+0.22x worse!)

## Changes Made in Round 17

1. **Fixed BT.709 SIMD call** in `to_linear.rs:74`
   - Before: `tf::bt709_to_linear(&mut row[..xsize])`
   - After: `tf::bt709_to_linear_simd(d, &mut row[..xsize.next_multiple_of(D::F32Vec::LEN)])`

2. **Added PQ SIMD** and updated call in `to_linear.rs:84`
   - Before: `tf::pq_to_linear(intensity_target, &mut row[..xsize])`
   - After: `tf::pq_to_linear_simd(d, intensity_target, &mut row[..xsize.next_multiple_of(D::F32Vec::LEN)])`

## Hypothesis: Why Did This Make Things Worse?

### Most Likely: Buffer Over-Processing

**Problem with `next_multiple_of(D::F32Vec::LEN)`**:

For grayscale images (200x200), xsize = 200:
- `D::F32Vec::LEN` is likely 8 (for AVX2)
- `next_multiple_of(8)` = 200 (already aligned)
- But what if the buffer is exactly 200? We're fine.
- **OR** what if xsize is padded but buffer isn't large enough?

More critically:
```rust
tf::bt709_to_linear_simd(d, &mut row[..xsize.next_multiple_of(D::F32Vec::LEN)]);
```

If `xsize = 200` and `row.len() = 200`, then:
- `xsize.next_multiple_of(8)` = 200
- We're slicing `row[..200]` which is fine

**BUT WAIT**: Looking at sRGB version on line 79:
```rust
tf::srgb_to_linear_simd(d, &mut row[..xsize.next_multiple_of(D::F32Vec::LEN)]);
```

This was ALREADY there! So that's not the issue.

### Second Hypothesis: SIMD Overhead on Small Images

Grayscale images are only 200x200 = 40,000 pixels total. Processing 200 pixels per row with SIMD:
- SIMD processes 8 floats at a time = 25 iterations
- Scalar would be 200 iterations

SIMD overhead includes:
- Runtime feature detection (minimal - cached)
- Vector loading/storing
- Tail handling

For such small buffers, SIMD might actually be SLOWER than scalar due to setup overhead!

### Third Hypothesis: We Introduced a Bug

Possibility: The buffer bounds are wrong and we're:
1. Processing garbage data beyond the buffer
2. Causing cache misses
3. Triggering some other performance issue

### Fourth Hypothesis: Measurement Noise

The benchmark runs 10 times. Variance might explain +0.02x overall, but not +0.16x-0.22x on specific tests.

## Root Cause Investigation Needed

### 1. Check what transfer function grayscale_jpeg actually uses

Does it even use BT.709? Or is it using sRGB which was already SIMD?

### 2. Profile the slow test

Compare perf data between Round 16 and Round 17 to see what changed.

### 3. Check buffer sizes

Are we accessing out of bounds? Are asserts failing silently?

### 4. Test with scalar fallback

Temporarily revert to scalar bt709_to_linear and see if performance improves.

## Immediate Action

**REVERT Round 17 changes** and investigate properly with profiling before making speculative optimizations!

The BT.709 SIMD already existed - we just changed the call site. If it's making things worse, either:
1. The SIMD implementation has issues
2. The call pattern is wrong
3. The tests don't actually use BT.709

**Lesson**: Profile FIRST, optimize SECOND. Speculation led us astray.
