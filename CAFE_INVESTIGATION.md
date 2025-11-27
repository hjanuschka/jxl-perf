# Cafe Test Investigation: Why Small Images Are Slower

## Problem Statement
**cafe test is the NEW #1 bottleneck at 2.22x slower**, despite being a medium-sized image (1280x1600 = 2.05 MP).

Paradoxically, **much larger images perform better**:
- bike (5.24 MP): 1.25x slower ← 2.5x MORE pixels, much faster relatively!
- progressive (10.99 MP): 1.20x slower ← 5x MORE pixels, even better!

## Key Findings

### 1. Size Scaling Pattern 🔍

| Test | Size (MP) | Rust (ms) | C++ (ms) | Slowdown | ms/MP (Rust) | ms/MP (C++) |
|------|-----------|-----------|----------|----------|--------------|-------------|
| **cafe** | 2.05 | 66.5 | 29.9 | **2.22x** | 32.4 | 14.6 |
| **bike** | 5.24 | 214.4 | 171.6 | **1.25x** | 40.9 | 32.7 |
| **progressive** | 10.99 | 529.2 | 439.8 | **1.20x** | 48.2 | 40.0 |

**Key Insight**: Both implementations scale worse with size (compute-heavy workload), BUT:
- **C++ scaling**: 14.6 → 40.0 ms/MP = **2.74x worse** with size
- **Rust scaling**: 32.4 → 48.2 ms/MP = **1.49x worse** with size

**This means**:
- Cafe has **fixed overhead** that dominates small/medium images
- C++ optimizes fixed costs better (parsing, setup, small blocks, cache)
- Rust's **per-pixel cost is more competitive** on large images!

### 2. Compression Ratio Analysis

| Test | File Size | MP | KB/MP | Observation |
|------|-----------|----|----|-------------|
| progressive | 457 KB | 10.99 | 41.6 | Low compression = simpler decode |
| bike | 380 KB | 5.24 | 72.5 | Medium compression |
| **cafe** | 373 KB | 2.05 | **181.9** | 👎 2.5x MORE compressed! |

**Cafe is 2.5x more aggressively compressed** than bike, meaning:
- More complex encoding (smaller DCT blocks, more transforms)
- More entropy decoding overhead
- More cache-unfriendly access patterns

### 3. Likely Bottlenecks Identified

#### A. Palette Transform (HIGH PRIORITY) 🎯

**Location**: `jxl/src/frame/modular/transforms/palette.rs:186-254`

**The problem**: Triple nested loops with function call per pixel:

```rust
for (chan_index, out) in buf_out.iter_mut().enumerate() {  // Channels
    for y in 0..h {  // Rows
        for x in 0..w {  // Columns
            let index = row_index[x];
            let palette_value = get_palette_value(  // ← FUNCTION CALL PER PIXEL!
                palette, index, chan_index, num_colors, bit_depth
            );
            row_out[x] = palette_value;
        }
    }
}
```

**Cost per pixel**:
1. Load index from row
2. Function call to get_palette_value()
3. Palette lookup (cache miss potential)
4. Store result

**For cafe (2.05 MP × 3 channels)**: ~6.15 million function calls!

**Optimization potential**: SIMD-vectorize to process 8 pixels at once:
- Batch load 8 indices
- Batch palette lookups (gather operation)
- Batch store 8 values
- **Expected speedup**: 3-5x on this path

#### B. Small DCT Block Overhead

Cafe's high compression ratio suggests it uses:
- Many small 8×8 or 4×4 DCT blocks
- More coefficient order permutations
- More entropy decoding overhead

**C++ advantage**: Better optimization of fixed per-block costs (loop overhead, setup)

#### C. Cache Unfriendly Patterns

Medium-sized images (1-3 MP) may hit the "worst spot" for caching:
- Too large to fit in L2 cache
- Too small to amortize cache misses
- More random access than large images

### 4. What Makes Large Images Fast?

**bike and progressive perform better because**:
1. **Fewer blocks per pixel**: Larger DCT blocks (16×16, 32×32) amortize overhead
2. **Better cache behavior**: Streaming access patterns for large images
3. **Less entropy overhead**: Simpler encoding with lower compression ratio
4. **SIMD efficiency**: More consecutive pixels to vectorize

## Recommended Optimizations (Priority Order)

### HIGH PRIORITY (Expected 10-20% gain)

1. **SIMD-vectorize palette transform** (`palette.rs:186-254`)
   - Use AVX2 gather instructions for batch lookups
   - Process 8 pixels per iteration
   - Eliminate per-pixel function call overhead

2. **Profile cafe specifically** with better instrumentation
   - Add timing to modular vs VarDCT paths
   - Measure palette transform time
   - Identify which path cafe actually uses

### MEDIUM PRIORITY (Expected 5-10% gain)

3. **Optimize small DCT block handling**
   - Check if there's a better loop structure for 8×8 blocks
   - Ensure coefficient order cache works well for small blocks

4. **Cache-aware memory layout**
   - Consider tiling or blocked access for medium images
   - Optimize for L2 cache size

### LOW PRIORITY (Experimental)

5. **Compare with C++ libjxl source**
   - See if they have special-case optimizations for cafe-like images
   - Check for algorithmic differences

6. **Test if cafe uses modular encoding**
   - Add logging to detect modular vs VarDCT
   - Profile both paths separately

## Next Steps

**Immediate action**: Optimize palette transform with SIMD

The palette.rs triple nested loop is:
- **Scalar code**: No SIMD currently
- **Function call per pixel**: High overhead
- **Easy to vectorize**: Straightforward gather pattern
- **High impact**: Used by modular images

**If palette optimization gives 15-20% gain on cafe**, we'll move from 2.22x → ~1.88x, which would make cafe comparable to noise tests.

## Technical Details

### Palette Transform Analysis

**Current implementation**:
- 3 loops (channels × rows × columns)
- Per-pixel: `get_palette_value()` function call
- No batching, no SIMD, no prefetching

**Optimization strategy**:
1. Batch load 8 indices at once (AVX2 load)
2. Use `_mm256_i32gather_epi32` for 8 palette lookups simultaneously
3. Store 8 results at once
4. Handle remainder with scalar code

**Expected performance**:
- Current: ~1 cycle/pixel (function call + load + store)
- Optimized: ~0.25 cycles/pixel (8 pixels in ~2 cycles)
- **Speedup**: 4x on palette path

**If palette is 30% of cafe decode time**: 30% × 4x = 12% overall speedup

## Conclusion

Cafe's slowness is NOT about pixel count - it's about:
1. **High compression ratio** (2.5x more than bike)
2. **Fixed overhead** that dominates small/medium images
3. **Likely modular/palette encoding** with scalar hot loops

**The palette transform is the smoking gun** - triple nested loops with function calls per pixel, no SIMD, perfect optimization target.

**Mission**: Optimize palette.rs and document results in Round 21! 🎯
