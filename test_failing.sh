#!/bin/bash

for test in animation_newtons_cradle blendmodes blendmodes_5 cmyk_layers patches patches_5 patches_lossless progressive progressive_5 spot sunset_logo; do
  echo "=== Testing $test ==="
  RAYON_NUM_THREADS=8 timeout 10 cargo run --release --bin test_decode_rs -- jxl-rs/jxl/resources/test/conformance_test_images/${test}.jxl 2>&1 | grep -E "(Decode time|panic|error)" | head -1
done
