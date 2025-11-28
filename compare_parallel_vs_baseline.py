#!/usr/bin/env python3
"""Compare parallel (round 30, 8 threads) vs sequential baseline (round 25)."""

import csv
import statistics
from collections import defaultdict

def load_benchmark(csv_file):
    """Load benchmark results from CSV file."""
    data = defaultdict(lambda: defaultdict(list))

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            testcase = row['testcase']
            decoder = row['decoder']
            decode_ms = float(row['decode_ms'])
            data[testcase][decoder].append(decode_ms)

    return data

def main():
    # Load both benchmarks
    print("Loading baseline (round 25)...")
    # Round 25 data should be in benchmark_results.csv from that run
    # For now, let's analyze the current parallel run

    print("Loading parallel (round 30, 8 threads)...")
    parallel_data = load_benchmark('benchmark_results.csv')

    print("\n=== PARALLEL VS C++ COMPARISON (8 threads) ===\n")
    print(f"{'Image':<35} {'Rust (ms)':<12} {'C++ (ms)':<12} {'Speedup':<12} {'Status'}")
    print("=" * 90)

    rust_times = []
    cxx_times = []
    speedups = []

    for testcase in sorted(parallel_data.keys()):
        if 'rust' in parallel_data[testcase] and 'cxx' in parallel_data[testcase]:
            rust_median = statistics.median(parallel_data[testcase]['rust'])
            cxx_median = statistics.median(parallel_data[testcase]['cxx'])
            speedup = cxx_median / rust_median  # >1 means Rust is faster

            rust_times.append(rust_median)
            cxx_times.append(cxx_median)
            speedups.append(speedup)

            status = "✓ FASTER" if speedup > 1.0 else "✗ SLOWER"
            if abs(speedup - 1.0) < 0.05:
                status = "≈ PARITY"

            print(f"{testcase:<35} {rust_median:>10.2f}  {cxx_median:>10.2f}  {speedup:>10.2f}x  {status}")

    print("\n" + "=" * 90)
    print(f"Average Rust time: {statistics.mean(rust_times):.2f}ms")
    print(f"Average C++ time:  {statistics.mean(cxx_times):.2f}ms")
    print(f"Average speedup:   {statistics.mean(speedups):.2f}x")
    print(f"Median speedup:    {statistics.median(speedups):.2f}x")

    faster = sum(1 for s in speedups if s > 1.0)
    slower = sum(1 for s in speedups if s < 1.0)
    parity = sum(1 for s in speedups if 0.95 <= s <= 1.05)

    print(f"\nTests faster than C++: {faster}/{len(speedups)}")
    print(f"Tests at parity:       {parity}/{len(speedups)}")
    print(f"Tests slower than C++: {slower}/{len(speedups)}")

    # Highlight big wins
    print("\n=== TOP 5 SPEEDUPS (Rust faster than C++) ===")
    sorted_by_speedup = sorted(parallel_data.keys(),
                               key=lambda t: statistics.median(parallel_data[t]['cxx']) / statistics.median(parallel_data[t]['rust'])
                               if 'rust' in parallel_data[t] and 'cxx' in parallel_data[t] else 0,
                               reverse=True)

    for testcase in sorted_by_speedup[:5]:
        if 'rust' in parallel_data[testcase] and 'cxx' in parallel_data[testcase]:
            rust_median = statistics.median(parallel_data[testcase]['rust'])
            cxx_median = statistics.median(parallel_data[testcase]['cxx'])
            speedup = cxx_median / rust_median
            print(f"  {testcase:<30} {speedup:.2f}x faster")

    # Highlight biggest slowdowns
    print("\n=== BIGGEST SLOWDOWNS (Rust slower than C++) ===")
    sorted_by_slowdown = sorted(parallel_data.keys(),
                                key=lambda t: statistics.median(parallel_data[t]['rust']) / statistics.median(parallel_data[t]['cxx'])
                                if 'rust' in parallel_data[t] and 'cxx' in parallel_data[t] else 0,
                                reverse=True)

    for testcase in sorted_by_slowdown[:5]:
        if 'rust' in parallel_data[testcase] and 'cxx' in parallel_data[testcase]:
            rust_median = statistics.median(parallel_data[testcase]['rust'])
            cxx_median = statistics.median(parallel_data[testcase]['cxx'])
            slowdown = rust_median / cxx_median
            print(f"  {testcase:<30} {slowdown:.2f}x slower")

if __name__ == '__main__':
    main()
