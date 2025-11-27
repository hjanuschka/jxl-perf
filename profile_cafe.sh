#!/bin/bash
# Profile cafe test by running it 200 times to get enough samples

INPUT="/tmp/jxl-rs/jxl/resources/test/conformance_test_images/cafe.jxl"
BINARY="./target/release/jxl-perf"

echo "Profiling cafe test (200 iterations)..."
for i in {1..200}; do
    $BINARY $INPUT > /dev/null 2>&1
done
echo "Done"
