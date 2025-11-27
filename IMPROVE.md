# jxl-rs Performance Improvement Plan

## Goal
Match libjxl (C++) performance on all conformance test images by optimizing jxl-rs.

## Current Status - UPDATED AFTER OPTIMIZATION #1

### Slowest Tests (Target Order) - **UPDATED**
1. **upsampling_5** - ~~9.00x~~ → **4.12x slower** (42.09ms vs 10.21ms) ✅ **IMPROVED 2.18x**
2. **upsampling** - ~~8.39x~~ → **3.44x slower** (34.90ms vs 10.13ms) ✅ **IMPROVED 2.44x**
3. **cafe** - 3.57x slower (107.89ms vs 30.23ms) ⭐ **CURRENT TARGET**
4. **grayscale** - 3.25x slower (4.97ms vs 1.53ms)
5. **noise** - 3.24x slower (34.32ms vs 10.59ms)
6. **bike** - 3.23x slower (551.99ms vs 170.72ms)
7. **cafe_5** - 3.20x slower (106.42ms vs 33.28ms)
8. **bike_5** - 3.13x slower (571.68ms vs 182.39ms)
9. **progressive** - 3.12x slower (1448.33ms vs 463.63ms)
10. **progressive_5** - 3.12x slower (1385.17ms vs 443.92ms)

**Average slowdown**: 2.19x (was 2.15x - slight regression on some tests, overall improved on upsampling)

### Repository Setup

```bash
# jxl-rs is now a git submodule at ./jxl-rs/
# Cargo.toml uses: jxl = { path = "jxl-rs/jxl" }

# Build
cargo build --release --bin test_decode_rs

# Run benchmarks
./run_benchmarks.sh

# Analyze
python3 analyze_results.py benchmark_results.csv
```

## Methodology for Each Optimization

### 1. Baseline Measurement
```bash
# Run target test 10 times to get stable baseline
for i in {1..10}; do
    ./target/release/test_decode_rs /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl
done
```

### 2. Profile with perf
```bash
# Build with debug symbols
cargo build --release --bin test_decode_rs
RUSTFLAGS="-C force-frame-pointers=yes" cargo build --release --bin test_decode_rs

# Profile
perf record -F 999 --call-graph dwarf ./target/release/test_decode_rs \
    /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl

# Generate report
perf report

# Or flamegraph
cargo install flamegraph
cargo flamegraph --bin test_decode_rs -- \
    /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl
```

### 3. Compare with C++ Implementation
```bash
# Run C++ version
./build/test_decode_cxx /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl

# Profile C++
perf record -F 999 --call-graph dwarf ./build/test_decode_cxx \
    /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl
```

### 4. Identify Bottleneck
- Look for hot functions in perf report
- Compare Rust vs C++ call graphs
- Check for:
  - Unnecessary allocations
  - Missing SIMD optimizations
  - Suboptimal algorithms
  - Bounds checking overhead
  - Iterator inefficiencies

### 5. Apply Fix
- Edit code in `jxl-rs/` submodule
- Rebuild with `cargo build --release --bin test_decode_rs`
- Test: `./target/release/test_decode_rs ...`

### 6. Verify Improvement
```bash
# Re-run benchmark
for i in {1..10}; do
    ./target/release/test_decode_rs /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl
done

# Compare before/after
```

### 7. Ensure Correctness
```bash
# Run conformance check (if available)
# Or visually compare output

# Run all benchmarks to ensure no regressions
./run_benchmarks.sh
python3 analyze_results.py benchmark_results.csv
```

## Target #1: upsampling_5 (9.00x slower)

### Image Details
- **File**: `/tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl`
- **Size**: 800x600
- **Rust decode time**: 88.13ms
- **C++ decode time**: 9.79ms
- **Gap**: 78.34ms (must eliminate this!)

### Hypothesis
"upsampling" in the name suggests this test focuses on the **upsampling filter** stage. This is likely:
- In `jxl-rs/jxl/src/render/stages/upsample.rs` or similar
- Part of the rendering pipeline
- May lack SIMD optimization
- Could have inefficient loop structures

### Investigation Steps

1. **Check what upsampling_5 tests**
```bash
cat /tmp/my-custom-testbed/conformance/testcases/upsampling_5/description.txt
# OR
find /tmp/my-custom-testbed/conformance/testcases/upsampling_5/ -name "*.json" -exec cat {} \;
```

2. **Profile the Rust decoder**
```bash
cargo flamegraph --bin test_decode_rs -- \
    /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl
# Output: flamegraph.svg
```

3. **Search for upsampling code in jxl-rs**
```bash
cd jxl-rs
grep -r "upsample\|Upsample" jxl/src/
```

4. **Compare with libjxl C++ implementation**
```bash
# libjxl is at /tmp/my-custom-testbed/libjxl/
cd /tmp/my-custom-testbed/libjxl/
grep -r "upsample\|Upsample" lib/jxl/
```

5. **Expected bottlenecks**
- Upsampling filter convolution (likely the hot path)
- Chroma upsampling (if image has YCbCr color)
- Lack of SIMD in filter kernels
- Bounds checking in nested loops

### Potential Fixes

#### Option 1: Add SIMD to Upsampling Filter
```rust
// Before (scalar)
for y in 0..height {
    for x in 0..width {
        result[y][x] = filter(input, x, y);
    }
}

// After (SIMD)
use std::simd::*;
for y in 0..height {
    let mut x = 0;
    while x + 8 <= width {
        let pixels = f32x8::from_slice(&input[y][x..x+8]);
        let filtered = simd_filter(pixels);
        filtered.copy_to_slice(&mut result[y][x..x+8]);
        x += 8;
    }
    // Handle remainder
    for x in x..width {
        result[y][x] = filter(input, x, y);
    }
}
```

#### Option 2: Remove Bounds Checking
```rust
// Use unsafe to skip bounds checks in hot loop
unsafe {
    for y in 0..height {
        for x in 0..width {
            *result.get_unchecked_mut((y, x)) =
                filter_unchecked(input, x, y);
        }
    }
}
```

#### Option 3: Optimize Filter Kernel
```rust
// Pre-compute filter coefficients
// Use separable filters (1D horizontal + 1D vertical)
// Cache-friendly access patterns
```

#### Option 4: Multi-threading
```rust
// Use rayon for parallel row processing
use rayon::prelude::*;
result.par_chunks_mut(width)
    .enumerate()
    .for_each(|(y, row)| {
        for x in 0..width {
            row[x] = filter(input, x, y);
        }
    });
```

### Success Criteria
- ✅ Decode time reduced from 88.13ms to < 15ms (< 1.5x C++)
- ✅ All other tests still pass
- ✅ Output image identical to before (pixel-perfect)

### Documentation
After fix, document:
1. What was the bottleneck?
2. What optimization was applied?
3. Before/after timings
4. Any correctness validation done

## Workflow for Subsequent Targets

Once upsampling_5 is fixed:

1. **Commit changes to jxl-rs submodule**
```bash
cd jxl-rs
git add .
git commit -m "Optimize upsampling filter - 9x speedup on upsampling_5"
cd ..
```

2. **Update this file**
```markdown
### Target #1: upsampling_5 ✅ COMPLETE
- Bottleneck: Scalar upsampling filter
- Fix: Added AVX2 SIMD to filter kernel
- Before: 88.13ms
- After: 12.45ms
- Speedup: 7.08x (down from 9.00x to 1.27x vs C++)
```

3. **Move to next target**
```markdown
### Target #2: upsampling (8.39x slower)
...
```

4. **Run full benchmark suite**
```bash
./run_benchmarks.sh
python3 analyze_results.py benchmark_results.csv
```

5. **Check for regressions**
- Ensure no other tests got slower
- Verify overall average slowdown improved

## Tools & Resources

### Profiling Tools
```bash
# Install tools
cargo install flamegraph
cargo install cargo-flamegraph
sudo apt install linux-perf  # or perf

# Profile with different tools
perf record -F 999 --call-graph dwarf ./target/release/test_decode_rs input.jxl
perf report

cargo flamegraph --bin test_decode_rs -- input.jxl

# cachegrind
valgrind --tool=cachegrind ./target/release/test_decode_rs input.jxl
```

### SIMD Resources
- `std::simd` (nightly Rust)
- `packed_simd` crate
- Check jxl-rs's existing SIMD code in `jxl_simd/`

### libjxl Source
- Location: `/tmp/my-custom-testbed/libjxl/`
- Key files: `lib/jxl/*.cc`, `lib/jxl/*.h`
- Build: Already built at `./build/test_decode_cxx`

### jxl-rs Source Structure
```
jxl-rs/
├── jxl/              # Main decoder library
│   └── src/
│       ├── render/   # Rendering pipeline stages
│       ├── headers/  # Format parsing
│       └── ...
├── jxl_simd/         # SIMD utilities
├── jxl_transforms/   # Color transforms, etc.
└── jxl_macros/       # Proc macros
```

## Progress Tracking

### Completed ✅

#### Target #1: upsampling_5 & upsampling ✅ **2.3x SPEEDUP**
- **File**: `jxl-rs/jxl/src/render/stages/upsample.rs`
- **Bottleneck**: Quintuple nested loops in `process_row_chunk` with redundant min/max calculations
- **Fix Applied**:
  1. Pre-computed min/max once per 5x5 region (moved outside inner loops)
  2. Manually unrolled the innermost 5-element loop
  3. Better memory access patterns for auto-vectorization
- **Results**:
  - **upsampling_5**: 88.13ms → 42.09ms (2.09x faster, 9.00x → 4.12x vs C++)
  - **upsampling**: 87.92ms → 34.90ms (2.52x faster, 8.39x → 3.44x vs C++)
- **Status**: ✅ Complete - Still 4x slower than C++, more work needed

### In Progress 🔄
- **cafe** (3.57x) - Next target

### Pending ⏳
- cafe_5 (3.20x)
- grayscale (3.25x)
- progressive (3.12x)
- bike (3.23x)
- noise (3.24x)
- ... (see updated list below)

## Notes & Learnings

### Performance Patterns
- **Upsampling tests** (upsampling, upsampling_5): Likely filter bottleneck
- **Cafe tests** (cafe, cafe_5): Large image, could be memory bandwidth
- **Grayscale tests**: Should be simpler, maybe overhead in format conversion?
- **Progressive tests**: Large images, progressive decoding overhead?
- **Noise tests**: Entropy decoding? Or noise synthesis?

### Common Optimizations
1. **SIMD** - Most critical for pixel processing
2. **Bounds check elimination** - Use unsafe in hot loops
3. **Memory layout** - Cache-friendly access patterns
4. **Parallel processing** - Use rayon for independent work
5. **Allocation reduction** - Reuse buffers, avoid temporary allocations

### Avoid
- Don't break correctness for speed
- Don't optimize without profiling first
- Don't assume - measure!
- Don't introduce unsafe code without comments explaining why it's safe

## Final Goal

**Target: < 1.2x average slowdown across all 30 passing tests**

Current average: ~2.15x
Need to improve: ~1.79x across the board

Focus on the top 10 slowest tests - they contribute most to the average.

## Quick Reference Commands

```bash
# Build
cargo build --release --bin test_decode_rs

# Test single image
./target/release/test_decode_rs /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl

# Full benchmark
./run_benchmarks.sh

# Analyze
python3 analyze_results.py benchmark_results.csv

# Profile
cargo flamegraph --bin test_decode_rs -- /tmp/my-custom-testbed/conformance/testcases/upsampling_5/input.jxl

# Edit jxl-rs
cd jxl-rs
# make changes...
cd ..
cargo build --release --bin test_decode_rs
```
