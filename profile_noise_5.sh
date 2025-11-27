#!/bin/bash
# Comprehensive profiling for noise_5 test - NEW #1 bottleneck at 2.12x

INPUT="/tmp/jxl-rs/jxl/resources/test/conformance_test_images/noise_5.jxl"
BINARY="./target/release/jxl-perf"

echo "=== Profiling noise_5 (NEW #1 bottleneck at 2.12x) ==="
echo "Image: noise_5.jxl (500x606)"
echo ""

# Run 200 iterations for good sampling
echo "Running 200 iterations with perf record..."
perf record -F 999 -g --call-graph dwarf -- bash -c "
    for i in {1..200}; do
        $BINARY $INPUT > /dev/null 2>&1
    done
"

echo ""
echo "Generating flamegraph..."
perf script | ~/FlameGraph/stackcollapse-perf.pl | ~/FlameGraph/flamegraph.pl > noise_5_flamegraph.svg

echo ""
echo "Top functions by CPU time:"
perf report --stdio --no-children -n --percent-limit 1 | head -40

echo ""
echo "=== Profiling complete! ==="
echo "Flamegraph: noise_5_flamegraph.svg"
echo "Perf data: perf.data"
