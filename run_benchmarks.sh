#!/bin/bash
set -e

# Read paths from setup.sh
if [ -f .testbed_path ]; then
    TESTBED_DIR=$(cat .testbed_path)
else
    TESTBED_DIR="${1:-/tmp/jxl-perf}"
    echo "Warning: .testbed_path not found, using default: $TESTBED_DIR"
fi

if [ -f .jxl_rs_path ]; then
    JXL_RS_DIR=$(cat .jxl_rs_path)
else
    JXL_RS_DIR="${JXL_RS_DIR:-../jxl-rs}"
    echo "Warning: .jxl_rs_path not found, using default: $JXL_RS_DIR"
fi

CONFORMANCE_DIR="$TESTBED_DIR/conformance"
OUTPUT_FILE="benchmark_results.csv"
FAILED_FILE="benchmark_failures.txt"
WARMUP_RUNS=3
BENCHMARK_RUNS=10
RUST_BINARY="./target/release/test_decode_rs"
CXX_BINARY="./build/test_decode_cxx"

echo "=== Running Benchmark Suite ==="
echo "Testbed directory: $TESTBED_DIR"
echo ""

# Verify conformance directory exists
if [ ! -d "$CONFORMANCE_DIR" ]; then
    echo "Error: Conformance test suite not found at $CONFORMANCE_DIR"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Verify Rust binary exists
if [ ! -f "$RUST_BINARY" ]; then
    echo "Error: Rust benchmark binary not found at $RUST_BINARY"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Find all test files
TEST_FILES=$(find "$CONFORMANCE_DIR" -name "*.jxl" | sort)
NUM_FILES=$(echo "$TEST_FILES" | wc -l)

echo "Found $NUM_FILES test files"
echo "Warmup runs: $WARMUP_RUNS"
echo "Benchmark runs: $BENCHMARK_RUNS"
echo "Output: $OUTPUT_FILE"
echo ""

# Create CSV header and clear failures file
echo "testcase,decoder,width,height,channels,parse_ms,decode_ms,total_ms,throughput_mps" > "$OUTPUT_FILE"
> "$FAILED_FILE"

# Check if C++ binary exists
if [ -f "$CXX_BINARY" ]; then
    HAS_CXX=1
    echo "Both Rust and C++ benchmarks will be run"
else
    HAS_CXX=0
    echo "Only Rust benchmark will be run (C++ binary not found)"
fi

echo ""

count=0
for file in $TEST_FILES; do
    count=$((count + 1))
    testcase=$(basename $(dirname "$file"))
    echo "[$count/$NUM_FILES] Testing: $testcase"

    # Run Rust benchmark
    echo -n "  Rust:  "
    rust_failed=0
    for ((i=1; i<=WARMUP_RUNS+BENCHMARK_RUNS; i++)); do
        set +e
        output=$($RUST_BINARY "$file" 2>&1)
        exit_code=$?
        set -e

        if [ $exit_code -ne 0 ]; then
            echo "FAILED (exit code $exit_code)"
            echo "$testcase,rust,FAILED" >> "$FAILED_FILE"
            rust_failed=1
            break
        fi

        if [ $i -gt $WARMUP_RUNS ]; then
            width=$(echo "$output" | grep "Dimensions:" | cut -d' ' -f2 | cut -d'x' -f1)
            height=$(echo "$output" | grep "Dimensions:" | cut -d' ' -f2 | cut -d'x' -f2)
            channels=$(echo "$output" | grep "Channels:" | awk '{print $2}')
            parse_time=$(echo "$output" | grep "Parse time:" | awk '{print $3}')
            decode_time=$(echo "$output" | grep "Decode time:" | awk '{print $3}')
            total_time=$(echo "$output" | grep "Total time:" | awk '{print $3}')
            throughput=$(echo "$output" | grep "Throughput:" | awk '{print $2}')

            echo "$testcase,rust,$width,$height,$channels,$parse_time,$decode_time,$total_time,$throughput" >> "$OUTPUT_FILE"
        fi
    done
    if [ $rust_failed -eq 0 ]; then
        echo "done"
    fi

    # Run C++ benchmark if available
    if [ $HAS_CXX -eq 1 ]; then
        echo -n "  C++:   "
        cxx_failed=0
        for ((i=1; i<=WARMUP_RUNS+BENCHMARK_RUNS; i++)); do
            set +e
            output=$($CXX_BINARY "$file" 2>&1)
            exit_code=$?
            set -e

            if [ $exit_code -ne 0 ]; then
                echo "FAILED (exit code $exit_code)"
                echo "$testcase,cxx,FAILED" >> "$FAILED_FILE"
                cxx_failed=1
                break
            fi

            if [ $i -gt $WARMUP_RUNS ]; then
                width=$(echo "$output" | grep "Dimensions:" | cut -d' ' -f2 | cut -d'x' -f1)
                height=$(echo "$output" | grep "Dimensions:" | cut -d' ' -f2 | cut -d'x' -f2)
                channels=$(echo "$output" | grep "Channels:" | awk '{print $2}')
                parse_time=$(echo "$output" | grep "Parse time:" | awk '{print $3}')
                decode_time=$(echo "$output" | grep "Decode time:" | awk '{print $3}')
                total_time=$(echo "$output" | grep "Total time:" | awk '{print $3}')
                throughput=$(echo "$output" | grep "Throughput:" | awk '{print $2}')

                echo "$testcase,cxx,$width,$height,$channels,$parse_time,$decode_time,$total_time,$throughput" >> "$OUTPUT_FILE"
            fi
        done
        if [ $cxx_failed -eq 0 ]; then
            echo "done"
        fi
    fi
done

echo ""
echo "=== Benchmark Complete ==="
echo "Results saved to: $OUTPUT_FILE"

if [ -s "$FAILED_FILE" ]; then
    echo "Failures logged to: $FAILED_FILE"
    echo ""
    echo "Failed tests:"
    cat "$FAILED_FILE"
fi

echo ""
echo "To analyze results:"
echo "  python3 analyze_results.py $OUTPUT_FILE"
