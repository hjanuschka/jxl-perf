#!/usr/bin/env python3
"""Analyze parallel benchmark results and calculate speedup."""

import csv
import statistics
from collections import defaultdict

def analyze_results(csv_file):
    # Parse CSV and group by testcase and decoder
    data = defaultdict(lambda: defaultdict(list))

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            testcase = row['testcase']
            decoder = row['decoder']
            decode_ms = float(row['decode_ms'])
            data[testcase][decoder].append(decode_ms)

    print("=== PARALLEL BENCHMARK ANALYSIS ===\n")
    print(f"{'Image':<35} {'Rust (ms)':<12} {'C++ (ms)':<12} {'Rust/C++ Ratio':<15}")
    print("=" * 80)

    rust_times = []
    cxx_times = []
    ratios = []

    for testcase in sorted(data.keys()):
        if 'rust' in data[testcase] and 'cxx' in data[testcase]:
            rust_median = statistics.median(data[testcase]['rust'])
            cxx_median = statistics.median(data[testcase]['cxx'])
            ratio = rust_median / cxx_median

            rust_times.append(rust_median)
            cxx_times.append(cxx_median)
            ratios.append(ratio)

            print(f"{testcase:<35} {rust_median:>10.2f}  {cxx_median:>10.2f}  {ratio:>13.2f}x")

    print("\n" + "=" * 80)
    print(f"Average Rust time: {statistics.mean(rust_times):.2f}ms")
    print(f"Average C++ time:  {statistics.mean(cxx_times):.2f}ms")
    print(f"Average ratio:     {statistics.mean(ratios):.2f}x")
    print(f"Median ratio:      {statistics.median(ratios):.2f}x")

    # Highlight key images
    print("\n=== KEY PARALLELIZABLE IMAGES ===")
    key_images = ['bike', 'bicycles', 'cafe', 'grayscale', 'noise', 'opsin_inverse']
    for img in key_images:
        if img in data and 'rust' in data[img]:
            rust_median = statistics.median(data[img]['rust'])
            cxx_median = statistics.median(data[img]['cxx'])
            ratio = rust_median / cxx_median
            print(f"{img:<20} Rust: {rust_median:>7.2f}ms  C++: {cxx_median:>7.2f}ms  Ratio: {ratio:.2f}x")

if __name__ == '__main__':
    analyze_results('benchmark_results.csv')
