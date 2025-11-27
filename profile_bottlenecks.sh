#!/bin/bash
# Profile progressive and grayscale bottlenecks

TESTBED="/tmp/jxl-perf"
DECODER="/home/chrome/jxl-perf/jxl-rs/target/release/djxl"

echo "=== Profiling Bottleneck Tests ==="

# Profile progressive (worst case: 2.90x)
echo "[1/2] Profiling progressive.jxl (4064x2704, 2.90x slower)..."
perf record -F 999 -g -- $DECODER "$TESTBED/progressive.jxl" /tmp/progressive_out.png 2>&1 | head -20
perf script > /tmp/progressive_perf.txt
echo "  Saved to /tmp/progressive_perf.txt"

# Profile grayscale (2.60x slower)
echo "[2/2] Profiling grayscale.jxl (200x200, 2.60x slower)..."
perf record -F 999 -g -- $DECODER "$TESTBED/grayscale.jxl" /tmp/grayscale_out.png 2>&1 | head -20
perf script > /tmp/grayscale_perf.txt
echo "  Saved to /tmp/grayscale_perf.txt"

echo ""
echo "=== Top Functions in Progressive ===" 
perf script -i perf.data | head -100 | grep -E "djxl|jxl::" | head -20

echo ""
echo "Profiling complete! Check /tmp/*_perf.txt for details"
