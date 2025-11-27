# Performance Optimization Plan: Achieving 1.0x Parity with C++ libjxl

## Executive Summary

**Current Status**: 1.75x average slowdown vs C++ libjxl (Round 6 baseline)
**Goal**: Reach 1.0x parity (match or beat C++ performance)
**Gap to Close**: ~43% performance improvement needed
**Strategy**: **PROFILE-FIRST** approach - no more speculation!

---

## Benchmark Analysis

### Current Performance (Round 6 Results)

**Worst Performers (>2.5x slower)**:
- progressive: 2.92x slower (4064x2704, 11MP)
- progressive_5: 2.82x slower
- grayscale_public_university: 2.80x slower (2880x1620, 4.7MP)
- grayscale: 2.78x slower (200x200)
- grayscale_5: 2.77x slower
- noise: 2.59x slower (500x606)
- noise_5: 2.55x slower
- bike_5: 2.54x slower (2048x2560, 5.2MP)
- bike: 2.52x slower

**Mid-Range (1.5x-2.5x slower)**:
- cafe_5/cafe: 2.28x / 1.96x
- alpha_premultiplied: 2.26x
- opsin_inverse: 2.17x / 2.13x
- grayscale_jpeg: 1.91x / 2.09x
- bicycles: 1.89x
- alpha_triangles: 1.78x
- upsampling: 1.71x / 1.64x

**Good Performers (<1.5x slower)**:
- delta_palette: 1.48x
- alpha_nonpremultiplied: 1.39x
- lz77_flower: 1.32x
- bench_oriented_brg: 1.18x / 1.12x
- lossless_pfm: 1.17x

**FASTER THAN C++ (!)**:
- animation_icos4d: 0.10x / 0.09x (10x faster!)
- animation_spline: 0.10x / 0.09x (10x faster!)

### Key Observations

1. **Grayscale images are consistently slow** (2.13x-2.80x)
2. **Noise synthesis is slow** (2.55x-2.59x)
3. **Progressive decode is slowest** (2.82x-2.92x)
4. **Large images tend to be slower** (bike 5.2MP, progressive 11MP)
5. **Animation performance is exceptional** - we're doing something RIGHT here!

---

## Critical Bottlenecks Identified

### 🔥 #1: BT.709 Transfer Function - No SIMD (CRITICAL)

**Location**: `jxl-rs/jxl/src/color/tf.rs:150-160`

**Current Code**:
```rust
pub fn bt709_to_linear(samples: &mut [f32]) {
    for s in samples {
        let a = s.abs();
        *s = if a <= 0.081 {
            a / 4.5
        } else {
            crate::util::fast_powf(a.mul_add(1.0 / 1.099, 0.099 / 1.099), 1.0 / 0.45)
        }
        .copysign(*s);
    }
}
```

**Problem**:
- Pure scalar implementation with expensive `fast_powf` calls
- Used by `ToLinearStage` for grayscale images
- Grayscale tests are 2.78x slower on average

**Evidence**:
- `linear_to_bt709_simd` EXISTS in the same file (lines 119-148)
- Shows the pattern works and provides speedup
- BT.709 is only missing the inverse direction

**Fix**: Add `bt709_to_linear_simd()` following existing SIMD pattern

**Expected Impact**:
- 2-2.5x speedup on grayscale tests
- ~10% overall benchmark improvement

**Priority**: **CRITICAL - Do this first**

---

### 🔥 #2: AddNoiseStage - No SIMD (HIGH)

**Location**: `jxl-rs/jxl/src/render/stages/noise.rs:239-298`

**Current Code**: Scalar loop with complex arithmetic (lines 262-296)

**Problem**:
- `ConvolveNoiseStage` HAS AVX2 SIMD (lines 65-172)
- `AddNoiseStage` is pure scalar
- Noise tests are 2.59x slower on average
- Loop contains many FMA operations - perfect for SIMD

**Fix**: Add AVX2+FMA SIMD implementation like `ConvolveNoiseStage`

**Expected Impact**:
- 2-3x speedup on noise tests
- ~8% overall benchmark improvement

**Priority**: **HIGH - Do this second**

---

### 🔥 #3: Progressive Decode Overhead (HIGH)

**Location**: Unknown - requires profiling

**Problem**:
- Progressive tests are THE slowest (2.90x)
- Large 11MP image with multiple progressive passes
- Possible issues:
  - Pipeline overhead per pass
  - Allocations per pass
  - Cache inefficiency
  - LowMemoryRenderPipeline vs SimpleRenderPipeline differences

**Fix**:
1. Profile progressive test with flamegraph
2. Identify specific bottleneck
3. Fix based on findings

**Expected Impact**:
- 2x speedup on progressive tests
- ~12% overall benchmark improvement

**Priority**: **HIGH - Do this third (after profiling)**

---

### 🔥 #4: SpotColorStage - No SIMD (MEDIUM)

**Location**: `jxl-rs/jxl/src/render/stages/spot.rs:61-66`

**Current Code**:
```rust
for idx in 0..xsize {
    let mix = scale * row_s[idx];
    row_r[idx] = mix * self.spot_color[0] + (1.0 - mix) * row_r[idx];
    row_g[idx] = mix * self.spot_color[1] + (1.0 - mix) * row_g[idx];
    row_b[idx] = mix * self.spot_color[2] + (1.0 - mix) * row_b[idx];
}
```

**Problem**:
- Simple scalar loop
- 4 operations × 3 channels = 12 FMA ops per pixel
- AVX2 can do 8 pixels at once

**Fix**: Add AVX2 SIMD - should be trivial

**Expected Impact**:
- 3-4x speedup on spot color images
- ~3-5% on relevant tests

**Priority**: **MEDIUM - Easy win**

---

### 🔥 #5: BlendingStage Allocation (MEDIUM)

**Location**: `jxl-rs/jxl/src/render/stages/blending.rs:116-120`

**Current Code**:
```rust
// TODO(szabadka): Allocate a buffer for this when building the stage instead of when
// executing it.
let mut out = row
    .iter_mut()
    .map(|s| &mut s[..xsize])
    .collect::<Vec<&mut [f32]>>();
```

**Problem**:
- Vec allocation on EVERY row chunk
- TODO comment confirms this is a known issue
- Impacts all alpha-blended images

**Fix**: Move Vec to `BlendingStage` struct, pre-allocate in `new()`

**Expected Impact**:
- 5-10% speedup on alpha tests
- ~3-5% overall improvement

**Priority**: **MEDIUM - Trivial fix**

---

### 🟡 #6: Large Image Performance (MEDIUM)

**Affected Tests**: bike (5.2MP, 2.5x), progressive (11MP, 2.9x)

**Problem**:
- Large images are consistently slower
- Possible cache thrashing
- Memory bandwidth saturation

**Fix**:
1. Profile large image tests
2. Consider tiling/blocking for cache efficiency
3. Check if C++ does something special

**Expected Impact**: 5-10% on large images

**Priority**: **MEDIUM - After profiling**

---

### 🟡 #7: Missing SIMD in Other Stages (LOW-MEDIUM)

**Stages without SIMD**:
- `ConvertModularXYBToF32` - division-heavy, could optimize
- PQ/HLG transfer functions - probably low impact (rare)
- Some conversion stages (F32ToU8/U16) - could use packed integer SIMD

**Priority**: **LOW - Only if profiling shows impact**

---

## ❌ Failed Optimizations - What NOT To Do

### Round 7: Grayscale XYB Optimization

**What we tried**: Compute luminance once, store to all 3 RGB channels

**Result**: 22% REGRESSION (2.13x → 2.61x on grayscale)

**Why it failed**:
- Original code: 3 matrix multiplications + 3 stores
- Optimized code: 1 matrix multiplication + 3 stores
- The 3 stores were MORE expensive than the 2 extra multiplications!

**Lesson**: Memory bandwidth matters. Redundant computation can be faster than redundant stores.

---

### Round 8: BT.709 SIMD with Polynomial Approximation

**What we tried**: Add SIMD to `bt709_to_linear()` using 5th-order rational polynomial approximation

**Result**: 5-19% REGRESSION on grayscale tests
- grayscale: 2.13x → 2.23x (4.7% worse)
- grayscale_5: 2.14x → 2.29x (7.0% worse)
- grayscale_jpeg: 1.83x → 2.17x (18.6% worse)
- **Average: 1.75x → 1.78x**

**Why it failed**:
- Polynomial evaluation (5th order P/Q) requires many operations:
  - 5 multiplies + 5 FMAs for numerator
  - 5 multiplies + 5 FMAs for denominator
  - 1 division
- Scalar `fast_powf` is already heavily optimized
- The polynomial overhead exceeded the benefit of SIMD vectorization

**Code that failed**:
```rust
// Rational polynomial with P[5] and Q[5] coefficients
let a = x.abs();
eval_rational_poly_simd(d, a, P, Q)  // Too much work!
```

**Lesson**: SIMD isn't always faster. Complex approximations can be slower than optimized scalar math.

---

### Key Takeaway: STOP GUESSING, START PROFILING

**Two failed speculative optimizations in a row proves:**
1. Our intuition about bottlenecks is WRONG
2. "Obvious" optimizations can make things worse
3. We MUST use flamegraphs to identify ACTUAL hot spots

**New rule**: NO MORE CODE CHANGES WITHOUT PROFILING DATA FIRST!

---

## Implementation Roadmap

### Phase 0: PROFILE FIRST (DO THIS NOW!)

**Before any more code changes:**

1. **Generate flamegraphs for worst cases**:
   ```bash
   # Progressive (2.95x slower)
   perf record -g -F 999 ./target/release/test_decode_rs /tmp/jxl-perf/progressive.jxl
   perf script | stackcollapse-perf.pl | flamegraph.pl > progressive_flamegraph.svg

   # Grayscale (2.23x slower)
   perf record -g -F 999 ./target/release/test_decode_rs /tmp/jxl-perf/grayscale.jxl
   perf script | stackcollapse-perf.pl | flamegraph.pl > grayscale_flamegraph.svg

   # Noise (2.70x slower)
   perf record -g -F 999 ./target/release/test_decode_rs /tmp/jxl-perf/noise.jxl
   perf script | stackcollapse-perf.pl | flamegraph.pl > noise_flamegraph.svg
   ```

2. **Analyze flamegraphs to identify ACTUAL hot spots**:
   - Look for functions taking >5% of total time
   - Identify stages that dominate execution
   - Find unexpected bottlenecks

3. **Only THEN make targeted fixes based on profiling data**

**Why this matters**: Two failed speculative optimizations prove we CANNOT trust our intuition!

---

### Phase 1: Profile-Guided Fixes (Target: 1.50x average)

**After profiling shows the actual bottlenecks:**

**IF profiling shows AddNoiseStage is hot**:
- Add SIMD to `AddNoiseStage` (File: `jxl-rs/jxl/src/render/stages/noise.rs`)
- Follow pattern from `ConvolveNoiseStage`
- Benchmark to verify improvement

**IF profiling shows SpotColorStage is hot**:
- Add SIMD to `SpotColorStage` (File: `jxl-rs/jxl/src/render/stages/spot.rs`)
- Simple AVX2 implementation
- Benchmark to verify improvement

**IF profiling shows BlendingStage allocation overhead**:
- Fix Vec allocation per row (File: `jxl-rs/jxl/src/render/stages/blending.rs`)
- Pre-allocate in struct
- Benchmark to verify improvement

**IF profiling shows something else**:
- Fix THAT instead of our assumptions!

**Benchmark after Phase 1**: Expect 1.50x average (improvement depends on actual fixes)

---

### Phase 2: Deep Investigation (Target: 1.20x average)

**Week 2-3 Tasks**:

5. **Profile and fix progressive decode** (Priority: HIGH)
   - Generate flamegraph: `perf record -g ./jxl_cli progressive.jxl out.png`
   - Analyze flamegraph to identify bottleneck
   - Possible findings:
     - Pipeline setup overhead per pass
     - Allocations per pass
     - Inefficient pass management
   - Fix identified issue

6. **Profile bike/cafe tests** (Priority: MEDIUM)
   - These are "normal" large images - shouldn't be 2.5x slower
   - Flamegraph to identify hot path
   - Likely hitting some inefficient code path

7. **Investigate animation performance** (Priority: LOW)
   - Animations are 10x FASTER than C++!
   - Understand what's optimized here
   - See if we can apply patterns to other tests

8. **Cache optimization for large images** (Priority: MEDIUM)
   - If profiling shows cache issues
   - Consider tiling/blocking strategy
   - Check C++ implementation for patterns

**Benchmark after Phase 2**: Expect 1.20x average (50% improvement from baseline)

---

### Phase 3: Fine-Tuning (Target: 1.0x parity)

**Week 4 Tasks**:

9. **Optimize conversion stages** (if needed)
   - `ConvertModularXYBToF32` - avoid divisions
   - `F32ToU8` / `F32ToU16` - use packed integer SIMD
   - Only if profiling shows impact

10. **Add PQ/HLG SIMD** (if needed)
    - Probably low impact (most images use sRGB/BT.709)
    - Only if profiling shows these are hot

11. **Additional SIMD opportunities**
    - Any stages identified during profiling
    - Apply learnings from animation performance

12. **Final benchmark sweep**
    - Run full benchmark suite
    - Identify any remaining outliers
    - Targeted fixes for worst remaining cases

**Benchmark after Phase 3**: Expect 1.00x average or better!

---

## Execution Strategy

### Development Workflow

For each optimization:

1. **Read the relevant code** to understand current implementation
2. **Implement the fix** following existing SIMD patterns
3. **Build**: `cargo build --release`
4. **Test specific case**: `cargo run --release --bin jxl_cli -- test.jxl out.png`
5. **Run full benchmarks**: `./run_benchmarks.sh`
6. **Analyze results**: `python3 analyze_results.py benchmark_results.csv`
7. **Compare to baseline**: Check if improvement matches expectation
8. **Iterate if needed**

### Profiling Commands

```bash
# Generate flamegraph
perf record -g -F 999 cargo run --release --bin jxl_cli -- progressive.jxl out.png
perf script | stackcollapse-perf.pl | flamegraph.pl > flamegraph.svg

# Cache analysis
perf stat -e cache-references,cache-misses,L1-dcache-loads,L1-dcache-load-misses \
  cargo run --release --bin jxl_cli -- bike.jxl out.png

# Branch prediction
perf stat -e branches,branch-misses,instructions,cycles \
  cargo run --release --bin jxl_cli -- bike.jxl out.png
```

### Success Criteria

- **Phase 1 Success**: Average slowdown ≤ 1.50x
  - Grayscale tests ≤ 1.5x (from 2.78x)
  - Noise tests ≤ 1.5x (from 2.59x)

- **Phase 2 Success**: Average slowdown ≤ 1.20x
  - Progressive tests ≤ 1.5x (from 2.90x)
  - No test > 2.0x

- **Phase 3 Success**: Average slowdown ≤ 1.00x
  - All major tests within 1.5x
  - Some tests faster than C++

---

## Risk Assessment

### Low Risk Items
- BT.709 SIMD - proven pattern exists
- Allocation fix - trivial change
- SpotColor SIMD - simple code

### Medium Risk Items
- AddNoise SIMD - more complex, but pattern exists
- Progressive profiling - might reveal complex issues

### High Risk Items
- Large image optimization - may require significant refactoring
- Unknown bottlenecks - may find unfixable architectural issues

---

## Contingency Plans

### If Phase 1 doesn't hit 1.50x target:
- Do deeper profiling on remaining slow tests
- Look for additional low-hanging SIMD fruit
- Check if SIMD is actually being used (runtime dispatch issues?)

### If progressive optimization is hard:
- Accept 2x on progressive as edge case
- Focus on more common test cases
- Come back to progressive after other optimizations

### If we plateau before 1.0x:
- Compare with C++ implementation line-by-line
- Consider Rust-specific issues (bounds checks, etc.)
- Profile both Rust and C++ side-by-side

---

## Why This Will Work

### Evidence of Success

1. **Animation tests prove Rust CAN be faster** (10x!)
   - Not a fundamental limitation
   - Shows pipeline can be efficient

2. **Existing SIMD works well**
   - XybStage SIMD is effective
   - Blending SIMD showed good improvement
   - YcbcrToRgb has good SIMD

3. **Clear bottlenecks identified**
   - BT.709 missing SIMD (clear fix)
   - AddNoise missing SIMD (clear fix)
   - Not mysterious performance issues

4. **Low-hanging fruit available**
   - Several stages lack SIMD
   - Known allocation issue
   - Progressive likely has specific bottleneck

### Comparison to Previous Work

- Round 4: Added multi-SIMD → 1.76x (marginal improvement)
- Round 5: AVX2-specific tuning → 1.73x (small improvement)
- Round 6: Blending SIMD + fix → 1.75x (good improvement)
- Round 7: Grayscale "optimization" → 1.80x (regression - reverted)

**Key insight**: Targeted SIMD on hot paths works. Speculative optimizations can backfire.

---

## Timeline

### Conservative Estimate
- Phase 1: 1 week (4 implementations)
- Phase 2: 2 weeks (profiling + fixes)
- Phase 3: 1 week (polish)
- **Total: 4 weeks to 1.0x**

### Aggressive Estimate
- Phase 1: 3 days (straightforward SIMD)
- Phase 2: 1 week (if progressive fix is simple)
- Phase 3: 2 days (if no major issues)
- **Total: 2 weeks to 1.0x**

---

## Measurement and Validation

### Benchmarks to Watch

**Primary metric**: Average slowdown across all tests

**Key test groups**:
- Grayscale: grayscale, grayscale_5, grayscale_jpeg, grayscale_public_university
- Noise: noise, noise_5
- Progressive: progressive, progressive_5
- Large images: bike, bike_5, cafe, cafe_5
- Alpha: alpha_premultiplied, alpha_nonpremultiplied, alpha_triangles

**Victory condition**: Average ≤ 1.0x, no major test > 2.0x

---

## Next Steps

1. ✅ Create this plan document
2. ❌ Tried `bt709_to_linear_simd()` - FAILED (5-19% regression)
3. ❌ Tried grayscale XYB optimization - FAILED (22% regression)
4. ✅ Learned lesson: MUST profile first
5. ⏭️ **NEXT: Generate flamegraphs for progressive, grayscale, and noise tests**
6. ⏭️ Analyze flamegraphs to find ACTUAL bottlenecks
7. ⏭️ Make targeted fixes based on profiling data

**Let's achieve 1.0x parity - but this time with data, not guesses!** 🔬
