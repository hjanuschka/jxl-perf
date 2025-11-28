#!/bin/bash
for threads in 1 2 4 8 16; do
    echo "=== $threads threads ==="
    RAYON_NUM_THREADS=$threads ./target/release/test_decode_rs jxl-rs/jxl/resources/test/conformance_test_images/bike.jxl 2>&1 | grep -E "VarDCT parallel|Decode time"
    echo ""
done
