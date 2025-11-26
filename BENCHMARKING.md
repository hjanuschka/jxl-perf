# Performance Benchmarking Infrastructure

This directory contains tools for comparing jxl-rs (Rust) decode performance against libjxl (C++).

## Quick Start

```bash
# 1. Build both decoders and fetch test images (default: /tmp/jxl-perf)
./setup.sh

# Or specify a custom testbed directory
./setup.sh /path/to/testbed

# 2. Run full benchmark suite (takes ~10-20 minutes)
./run_benchmarks.sh

# 3. Analyze results
python3 analyze_results.py benchmark_results.csv
```

## Files

- `jxl/examples/test_decode_rs.rs` - Rust decoder benchmark binary
- `tools/test_decode_cxx.cpp` - C++ decoder benchmark binary
- `tools/CMakeLists.txt` - Build configuration for C++ binary
- `setup.sh` - One-time setup: builds binaries, fetches test images
- `run_benchmarks.sh` - Runs both decoders on all conformance tests
- `analyze_results.py` - Analyzes CSV results, identifies worst cases
- `performance_plan.md` - Strategic roadmap for performance improvements

## Testbed Directory

By default, test images are stored in `/tmp/jxl-perf/`. You can specify a custom directory:

```bash
./setup.sh /custom/path/to/testbed
```

The testbed contains:
- `conformance/` - Cloned test suite with 39 JXL images

## Test Corpus

Uses the official [libjxl/conformance](https://github.com/libjxl/conformance) test suite (39 images) covering:
- Various encoding modes (VarDCT, Modular)
- Different image sizes
- Animated/static images
- Lossless/lossy compression

## Single File Testing

```bash
# Rust decoder
cargo run --example test_decode_rs --release -- /tmp/jxl-perf/conformance/testcases/bike/input.jxl

# C++ decoder
./tools/build/test_decode_cxx /tmp/jxl-perf/conformance/testcases/bike/input.jxl
```

## Output Format

Both decoders output identical metrics:
- Parse time (header + metadata parsing)
- Decode time (actual image decoding)
- Total time (end-to-end)
- Throughput (megapixels/second)

## GitHub Actions & Pages

The repository includes automated benchmarking via GitHub Actions:
- Runs every 2 hours automatically
- Generates HTML report hosted on GitHub Pages
- Zero infrastructure cost
- Historical data preserved as workflow artifacts

### Setup GitHub Pages

1. Go to repository Settings → Pages
2. Source: Deploy from a branch
3. Branch: `gh-pages` / `/ (root)`
4. Save

Benchmarks will be available at: `https://<username>.github.io/jxl-perf/`

## Requirements

- Rust toolchain (for jxl-rs)
- C++ compiler (for libjxl benchmark)
- pkg-config
- libjxl development package:
  - Ubuntu/Debian: `sudo apt install libjxl-dev`
  - Arch: `sudo pacman -S libjxl`
  - macOS: `brew install jpeg-xl`
