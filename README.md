# jxl-perf

Automated performance benchmarking infrastructure for [jxl-rs](https://github.com/libjxl/jxl-rs), comparing Rust decoder performance against the reference C++ implementation ([libjxl](https://github.com/libjxl/libjxl)).

## 📊 Live Benchmarks

**View live performance data:** https://hjanuschka.github.io/jxl-perf/

- Updates automatically every 2 hours
- Zero infrastructure cost (GitHub Actions + Pages)
- Comprehensive test coverage (39 conformance images)
- Historical data preserved as workflow artifacts

## 🚀 Features

- **Automated Benchmarking**: Runs every 2 hours via GitHub Actions
- **Dual Decoder Testing**: Compares jxl-rs (Rust) vs libjxl (C++)
- **Failure Tracking**: Identifies and highlights decoder failures
- **Performance Metrics**: Parse time, decode time, throughput (MP/s)
- **HTML Reports**: Clean, responsive web interface
- **CSV Export**: Machine-readable results for analysis

## 📈 Current Performance

Based on latest benchmarks:
- **Average slowdown**: ~1.83x (Rust vs C++)
- **Median slowdown**: ~1.46x
- **Worst case**: ~3.82x (grayscale_jpeg)
- **Best case**: ~0.07x (animation_spline - Rust is 14x FASTER!)
- **Rust failures**: 16/39 images (conformance bugs to fix)
- **C++ failures**: 0/39 images

## 🛠️ Local Usage

```bash
# Clone and setup
git clone https://github.com/hjanuschka/jxl-perf.git
cd jxl-perf

# Install dependencies (Ubuntu/Debian)
sudo apt-get install libjxl-dev cmake build-essential pkg-config

# Setup (fetches conformance tests, builds binaries)
./setup.sh

# Run benchmarks
./run_benchmarks.sh

# Generate HTML report
python3 generate_html.py benchmark_results.csv benchmark_failures.txt index.html

# Analyze results
python3 analyze_results.py benchmark_results.csv
```

## 📁 Repository Structure

```
.
├── .github/workflows/
│   └── benchmark.yml          # GitHub Actions workflow
├── test_decode_rs.rs          # Rust decoder benchmark
├── test_decode_cxx.cpp        # C++ decoder benchmark
├── CMakeLists.txt             # Build config for C++
├── setup.sh                   # One-time setup script
├── run_benchmarks.sh          # Benchmark runner
├── analyze_results.py         # CLI results analyzer
├── generate_html.py           # HTML report generator
├── performance_plan.md        # Optimization roadmap
└── BENCHMARKING.md           # Detailed documentation
```

## 🎯 Optimization Priorities

Top 10 worst-performing test cases (prioritize for optimization):

1. grayscale_jpeg - 3.82x slower
2. cafe_5 - 3.65x slower
3. cafe - 3.55x slower
4. noise_5 - 3.01x slower
5. noise - 2.78x slower
6. grayscale - 2.54x slower
7. opsin_inverse_5 - 2.06x slower
8. bicycles - 1.91x slower
9. grayscale_jpeg_5 - 1.70x slower
10. opsin_inverse - 1.64x slower

## 📚 Test Corpus

Uses the official [libjxl/conformance](https://github.com/libjxl/conformance) test suite (39 images):
- VarDCT and Modular encoding
- Various image sizes
- Animated and static images
- Lossless and lossy compression
- Alpha channels and blending modes

## 🔧 Configuration

### Custom Test Directory

```bash
./setup.sh /custom/testbed/path
./run_benchmarks.sh
```

### Manual Workflow Trigger

Go to Actions → Performance Benchmarks → Run workflow

## 📝 License

This benchmarking infrastructure is provided as-is for performance testing of jxl-rs.

## 🤝 Contributing

Issues and pull requests welcome! This is a community effort to optimize jxl-rs performance.

---

**Related Projects:**
- [jxl-rs](https://github.com/libjxl/jxl-rs) - Rust JPEG XL decoder
- [libjxl](https://github.com/libjxl/libjxl) - Reference C++ implementation
- [conformance](https://github.com/libjxl/conformance) - Test image suite
