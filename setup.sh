#!/bin/bash
set -e

TESTBED_DIR="${1:-/tmp/jxl-perf}"

echo "=== Performance Baseline Setup ==="
echo "Testbed directory: $TESTBED_DIR"
echo ""

# Create testbed directory if it doesn't exist
mkdir -p "$TESTBED_DIR"

# Clone conformance test suite if not present
CONFORMANCE_DIR="$TESTBED_DIR/conformance"
if [ ! -d "$CONFORMANCE_DIR" ]; then
    echo "Cloning conformance test suite to $CONFORMANCE_DIR..."
    git clone --depth 1 https://github.com/libjxl/conformance.git "$CONFORMANCE_DIR"
else
    echo "Conformance test suite already present at $CONFORMANCE_DIR"
fi

# Count test files
num_tests=$(find "$CONFORMANCE_DIR" -name "*.jxl" | wc -l)
echo "Found $num_tests JXL test files"

# Build Rust benchmark
echo ""
echo "Building Rust benchmark (test_decode_rs)..."
cargo build --example test_decode_rs --release

# Build C++ benchmark
echo ""
echo "Building C++ benchmark (test_decode_cxx)..."
if ! command -v pkg-config &> /dev/null; then
    echo "ERROR: pkg-config not found. Please install it."
    exit 1
fi

if ! pkg-config --exists libjxl; then
    echo "WARNING: libjxl not found via pkg-config."
    echo "Please install libjxl development package:"
    echo "  Ubuntu/Debian: sudo apt install libjxl-dev"
    echo "  Arch: sudo pacman -S libjxl"
    echo "  macOS: brew install jpeg-xl"
    echo ""
    echo "Skipping C++ benchmark build."
    CXX_BUILD_FAILED=1
else
    mkdir -p tools/build
    cd tools/build
    cmake ..
    cmake --build .
    cd ../..
    echo "C++ benchmark built successfully"
    CXX_BUILD_FAILED=0
fi

# Save testbed path for run_benchmarks.sh
echo "$TESTBED_DIR" > .testbed_path

echo ""
echo "=== Setup Complete ==="
echo ""
echo "To test a single file:"
echo "  Rust:  cargo run --example test_decode_rs --release -- $CONFORMANCE_DIR/testcases/bike/input.jxl"
if [ "$CXX_BUILD_FAILED" -eq 0 ]; then
    echo "  C++:   ./tools/build/test_decode_cxx $CONFORMANCE_DIR/testcases/bike/input.jxl"
fi
echo ""
echo "To run full benchmark suite:"
echo "  ./run_benchmarks.sh"
