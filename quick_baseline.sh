#!/bin/bash
# Quick sequential baseline benchmark

cd /tmp/jxl-perf 2>/dev/null || cd /home/chrome/jxl-perf/test_images

DECODER="/home/chrome/jxl-perf/target/release/test_decode_rs"

echo "=== Sequential Baseline Benchmark ==="
echo ""

for test in bike bicycles cafe grayscale noise; do
    if [ -f "${test}.jxl" ]; then
        echo "Testing: $test"
        # Run 5 times and take median
        times=()
        for i in {1..5}; do
            result=$($DECODER ${test}.jxl 2>&1 | grep "Decode time" | awk '{print $3}' | sed 's/ms//')
            if [ -n "$result" ]; then
                times+=($result)
            fi
        done

        # Sort and get median (3rd of 5)
        IFS=$'\n' sorted=($(sort -n <<<"${times[*]}"))
        median=${sorted[2]}
        echo "  Median: ${median}ms"
        echo ""
    fi
done
