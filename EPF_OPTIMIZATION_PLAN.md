# EPF0 Optimization Plan - C++ Algorithm Port

**Date**: 2025-11-27
**Target**: EPF0 stage (37.10% of CPU in progressive test)
**Expected Impact**: 30-50% speedup on progressive images

---

## Problem Identified

The Rust jxl-rs EPF0 implementation uses a **different, less efficient algorithm** than the C++ libjxl reference implementation.

### Current Rust Approach (epf0.rs lines 88-210)

**Algorithm**: Precompute all pairwise differences, then accumulate into SADs

1. **Load phase**: Load ALL 27 pixels from 7x7 window upfront
2. **Compute phase**: Compute 50+ pairwise absolute differences
3. **Accumulate phase**: Combine precomputed differences into 12 SADs
4. **Apply phase**: Use SADs to compute weighted average

**Problems**:
- ❌ High register pressure (50+ intermediate values)
- ❌ Poor cache locality (loads all pixels before computing)
- ❌ More memory traffic (redundant loads)
- ❌ Potential register spills to stack

### C++ Reference Approach (stage_epf.cc lines 130-151)

**Algorithm**: Compute each SAD on-demand with immediate accumulation

For each of 12 neighbor positions:
1. Initialize SAD to zero
2. For each of 5 pixels in plus-shaped kernel:
   - Load center pixel at offset
   - Load neighbor pixel at offset
   - Compute absolute difference
   - **Immediately accumulate** into SAD
3. Store completed SAD

**Advantages**:
- ✅ Lower register pressure (only 1 SAD in-flight at a time)
- ✅ Better cache locality (sequential pixel access)
- ✅ Less memory traffic (lazy loading)
- ✅ No intermediate storage needed

---

## Detailed Algorithm Comparison

### C++ Code Structure

```cpp
// 12 neighbor positions in plus-shaped pattern
constexpr std::array<int, 2> sads_off[12] = {
    {{-2, 0}}, {{-1, -1}}, {{-1, 0}}, {{-1, 1}}, {{0, -2}}, {{0, -1}},
    {{0, 1}},  {{0, 2}},   {{1, -1}}, {{1, 0}},  {{1, 1}},  {{2, 0}},
};

// 3x3 plus-shaped comparison kernel (5 pixels)
constexpr std::array<int, 2> plus_off[] = {
    {{0, 0}}, {{-1, 0}}, {{0, -1}}, {{1, 0}}, {{0, 1}}
};

// Compute SADs
for (size_t c = 0; c < 3; c++) {  // For each color channel
    auto scale = Set(df, lf_.epf_channel_scale[c]);
    for (size_t i = 0; i < 12; i++) {  // For each neighbor
        auto sad = Zero(df);
        for (const auto& off : plus_off) {  // For each pixel in plus
            // Load center pixel with offset
            const auto r11 = LoadU(df, rows[c][3 + off[0]] + x + off[1]);
            // Load neighbor pixel with offset
            const auto c11 = LoadU(df, rows[c][3 + sads_off[i][0] + off[0]] +
                                           x + sads_off[i][1] + off[1]);
            // Accumulate difference
            sad = Add(sad, AbsDiff(r11, c11));
        }
        // Scale and store
        *sads[i] = MulAdd(sad, scale, *sads[i]);
    }
}
```

**Total operations**:
- 3 channels × 12 neighbors × 5 pixels = 180 AbsDiff operations
- 180 load operations (reuses center pixels across neighbors)

### Rust Code Structure

```rust
// Phase 1: Load ALL 27 pixels
let p30 = D::F32Vec::load(d, &input_c[0][3 + x..]);
let p21 = D::F32Vec::load(d, &input_c[1][2 + x..]);
// ... 25 more loads (27 total) ...

// Phase 2: Compute ALL pairwise differences (50+)
let d32_30 = (p32 - p30).abs();
let d32_21 = (p32 - p21).abs();
let d32_31 = (p32 - p31).abs();
// ... 47+ more differences ...

// Phase 3: Accumulate into 12 SADs
sads[0] = scale.mul_add(d32_30 + d23_21 + d33_31 + d43_41 + d32_34, sads[0]);
sads[1] = scale.mul_add(d32_21 + d23_12 + d33_22 + d32_43 + d23_34, sads[1]);
// ... 10 more accumulations ...
```

**Total operations**:
- 3 channels × 27 pixel loads = 81 loads (vs C++'s ~60 effective loads)
- 3 channels × 50+ differences = 150+ AbsDiff operations
- 12 multi-term additions to combine differences

**Extra work**: ~50 more operations than necessary!

---

## Optimization Strategy

### Approach: Port C++ Algorithm to Rust

Replace the current three-phase approach with the C++ on-demand computation pattern.

**Implementation location**: `jxl-rs/jxl/src/render/stages/epf/epf0.rs` lines 88-180

### Pseudocode for New Implementation

```rust
// Define neighbor offsets (same as C++)
const NEIGHBOR_OFFSETS: [(isize, isize); 12] = [
    (-2, 0), (-1, -1), (-1, 0), (-1, 1), (0, -2), (0, -1),
    (0, 1),  (0, 2),   (1, -1), (1, 0),  (1, 1),  (2, 0),
];

// Define plus-shaped kernel (same as C++)
const PLUS_OFFSETS: [(isize, isize); 5] = [
    (0, 0), (-1, 0), (0, -1), (1, 0), (0, 1)
];

// Compute SADs (C++ style)
for input_c in input_rows.iter() {
    let scale = D::F32Vec::splat(d, channel_scale[channel_idx]);

    for (neighbor_idx, &(ny, nx)) in NEIGHBOR_OFFSETS.iter().enumerate() {
        let mut sad = D::F32Vec::splat(d, 0.0);

        for &(oy, ox) in PLUS_OFFSETS.iter() {
            // Load center pixel with offset
            let center = D::F32Vec::load(d, &input_c[3 + oy][3 + x + ox..]);
            // Load neighbor pixel with offset
            let neighbor = D::F32Vec::load(d, &input_c[3 + ny + oy][3 + x + nx + ox..]);
            // Accumulate difference immediately
            sad += (center - neighbor).abs();
        }

        // Scale and accumulate into SAD array
        sads[neighbor_idx] = sad.mul_add(scale, sads[neighbor_idx]);
    }
    channel_idx += 1;
}
```

### Benefits of This Approach

1. **Reduced register pressure**: Only 1 SAD + 2 pixel values in registers at a time
2. **Better memory locality**: Pixels loaded when needed, better cache reuse
3. **Simpler code**: Matches reference implementation exactly
4. **Fewer operations**: ~180 AbsDiff vs current ~150+ (but without extra precomputation overhead)

---

## Implementation Plan

### Step 1: Read Current Implementation
✅ Done - analyzed lines 88-210 of epf0.rs

### Step 2: Create New Implementation
- Replace lines 88-180 with C++ algorithm port
- Keep same interface (input_rows, output_rows, etc.)
- Maintain SIMD using jxl_simd abstractions

### Step 3: Test for Correctness
**Critical**: EPF is an image quality filter. We MUST verify:
1. Visual output matches original (pixel-perfect)
2. No regressions on any test image
3. Early-exit optimization still works (sigma < MIN_SIGMA)

**Test command**:
```bash
# Run single test to check output
./target/release/test_decode_rs testdata/progressive.jxl

# Full benchmark to check no regressions
./run_benchmarks.sh 2>&1 | tee benchmark_round9_epf_algorithm.log

# Compare outputs pixel-by-pixel (if needed)
diff <(od -An -tx1 output_original.raw) <(od -An -tx1 output_optimized.raw)
```

### Step 4: Measure Performance Impact
**Expected improvements**:
- Progressive test (11MP, EPF-heavy): **25-40% faster** (EPF is 60% of time)
- Overall average: **10-20% faster** (EPF-heavy images dominate slowdowns)

**Target metrics**:
- Progressive: 2.95x → **2.15x or better**
- cafe: 3.5x → **2.8x or better**
- Overall average: 1.75x → **1.50x or better**

---

## Risk Assessment

### Low Risk ✅
This optimization is **LOW RISK** because:
1. We're copying a **proven, production algorithm** from libjxl
2. Algorithm is **mathematically equivalent** - computes same SADs, just different order
3. Changes are **localized** to one function in epf0.rs
4. We have **comprehensive test suite** (30 working tests)

### Potential Issues
1. **Rust borrowing rules**: May need to adjust slice access patterns
2. **jxl_simd API differences**: Rust SIMD wrapper may have different APIs than Highway
3. **Index bounds**: Need to ensure array access is safe (Rust enforces this)

### Mitigation
- Test on all 30 working images before declaring success
- If any image shows pixel differences, revert and investigate
- Keep original code in git history for easy rollback

---

## Success Criteria

**Optimization succeeds if**:
1. ✅ All 30 tests still pass (no new failures)
2. ✅ Output images are pixel-identical to baseline
3. ✅ Progressive test improves by ≥20%
4. ✅ No regressions on any test (all tests same speed or faster)
5. ✅ Overall average slowdown improves to ≤1.60x

**If ANY test regresses or produces wrong output → REVERT**

---

## Next Steps

1. ✅ Document current findings (this file)
2. 🔄 Implement C++ algorithm port in epf0.rs
3. ⏳ Build and test for correctness
4. ⏳ Run full benchmark suite
5. ⏳ Analyze results and document in benchmark report

---

## References

- **C++ implementation**: `/tmp/libjxl/lib/jxl/render_pipeline/stage_epf.cc` lines 130-151
- **Current Rust implementation**: `jxl-rs/jxl/src/render/stages/epf/epf0.rs` lines 88-180
- **Profiling results**: `PROFILING_RESULTS.md` (EPF0 = 37.10% CPU)
- **Flamegraph**: `progressive_flamegraph.svg`
