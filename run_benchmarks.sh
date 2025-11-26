#!/bin/bash
set -e

# Read testbed path from setup.sh
if [ -f .testbed_path ]; then
    TESTBED_DIR=$(cat .testbed_path)
else
    TESTBED_DIR="${1:-/tmp/jxl-perf}"
    echo "Warning: .testbed_path not found, using default: $TESTBED_DIR"
fi

CONFORMANCE_DIR="$TESTBED_DIR/conformance"
OUTPUT_FILE="benchmark_results.csv"
WARMUP_RUNS=2
BENCHMARK_RUNS=3

echo "=== Running Benchmark Suite ==="
echo "Testbed directory: $TESTBED_DIR"
echo ""

# Verify conformance directory exists
if [ ! -d "$CONFORMANCE_DIR" ]; then
    echo "Error: Conformance test suite not found at $CONFORMANCE_DIR"
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

# Create CSV header
echo "testcase,decoder,width,height,channels,parse_ms,decode_ms,total_ms,throughput_mps" > "$OUTPUT_FILE"

# Check if C++ binary exists
CXX_BINARY="./tools/build/test_decode_cxx"
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
    for ((i=1; i<=WARMUP_RUNS+BENCHMARK_RUNS; i++)); do
        output=$(cargo run --example test_decode_rs --release --quiet -- "$file" 2>&1)

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
    echo "done"

    # Run C++ benchmark if available
    if [ $HAS_CXX -eq 1 ]; then
        echo -n "  C++:   "
        for ((i=1; i<=WARMUP_RUNS+BENCHMARK_RUNS; i++)); do
            output=$($CXX_BINARY "$file" 2>&1)

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
        echo "done"
    fi
done

echo ""
echo "=== Benchmark Complete ==="
echo "Results saved to: $OUTPUT_FILE"
echo ""
echo "To analyze results:"
echo "  python3 analyze_results.py $OUTPUT_FILE"
