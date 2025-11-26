# Performance Improvement Plan for jxl-rs

## Context
Veluca noted that jxl-rs is currently 2-3x slower than libjxl (C++) on some images. This document outlines a strategic approach to identify and fix performance bottlenecks.

## Phase 1: Baseline Measurement (Current Task)

### Objective
Establish reproducible performance baselines for both jxl-rs (Rust) and libjxl (C++) decoders.

### Deliverables

1. **test_decode_rs** - Rust decoder benchmark binary
   - Takes filename as argument
   - Decodes image to RGB8/RGBA8
   - Reports timing metrics:
     - Parse time
     - Decode time
     - Total time
     - Memory usage (if feasible)
   - Location: `jxl/benches/test_decode_rs.rs` or separate binary in `jxl/examples/`

2. **test_decode_cxx** - C++ decoder benchmark binary
   - Same interface as Rust version
   - Uses libjxl API
   - Reports identical metrics
   - Location: `tools/test_decode_cxx.cpp` (needs CMake/build setup)

3. **Conformance Test Suite**
   - Clone https://github.com/libjxl/conformance
   - Contains diverse JXL images:
     - Various encoding modes (VarDCT, Modular)
     - Different sizes
     - With/without ICC profiles
     - Animated/static
     - Lossless/lossy
   - Use as comprehensive test corpus

4. **Benchmark Runner Script**
   - Run both decoders on all conformance images
   - Collect and aggregate results
   - Generate comparison report (CSV/JSON)
   - Identify images with worst performance gap

### Success Criteria
- Both binaries produce consistent timing results
- Reproduce 2-3x slowdown on specific images
- Identify which image types show worst performance

## Phase 2: Profiling & Hotspot Identification

### Tools
- `cargo flamegraph` - Identify Rust hotspots
- `perf` - Linux performance profiling
- `valgrind --tool=callgrind` - Detailed call graphs
- Compare flamegraphs between jxl-rs and libjxl

### Focus Areas
Based on typical decoder bottlenecks:
1. Entropy decoding (ANS/Huffman)
2. Inverse DCT transforms
3. XYB color space conversion
4. Chroma upsampling
5. Memory allocation patterns
6. SIMD utilization

### Expected Outputs
- Flamegraph showing top 10 hotspots
- Percentage breakdown of time per decoder stage
- Specific functions/modules to optimize

## Phase 3: Targeted Optimization

### Strategy
1. Focus on hottest functions first (80/20 rule)
2. Low-hanging fruit:
   - Add `#[inline]` hints where missing
   - Replace bounds checks with unsafe when provably safe
   - Use SIMD intrinsics where applicable
   - Optimize memory allocation (use arenas/pools)

3. Algorithmic improvements:
   - Match libjxl's fast paths
   - Implement lookup tables for expensive computations
   - Cache frequently computed values

4. Structural changes:
   - Reduce abstraction overhead
   - Minimize heap allocations
   - Improve data locality

### Validation
- Re-run benchmarks after each optimization
- Ensure correctness with conformance tests
- Target matching libjxl performance (within 10-20%)

## Phase 4: Continuous Performance Monitoring

### Infrastructure
- Add benchmarks to CI
- Track performance over time
- Prevent regressions
- Use `criterion` for statistical benchmarking

## Initial Hypothesis

Likely performance issues based on Rust/C++ differences:
1. **Bounds checking** - Rust adds runtime checks C++ doesn't
2. **Memory allocation** - Different allocator strategies
3. **SIMD gaps** - libjxl may have more hand-optimized SIMD
4. **Abstraction cost** - Trait objects, generic monomorphization overhead
5. **Entropy decoding** - Critical path, needs careful optimization

## Next Steps

1. ✅ Create perf-baseline branch
2. ✅ Write test_decode_rs binary
3. ✅ Write test_decode_cxx binary (with build setup)
4. ✅ Clone conformance test suite
5. ✅ Create benchmark runner script
6. ⏳ Establish baseline measurements
7. ⏳ Generate comparison report

## References
- libjxl repo: https://github.com/libjxl/libjxl
- Conformance tests: https://github.com/libjxl/conformance
- Rust Performance Book: https://nnethercote.github.io/perf-book/
