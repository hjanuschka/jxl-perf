#!/usr/bin/env python3
"""Compare Phase 2 (pre-allocated slots) vs Phase 1 (Mutex<Vec>) vs C++ baseline"""

import csv
import sys
from collections import defaultdict

def load_benchmark_csv(filename):
    """Load CSV and return dict of {testcase: {decoder: median_decode_time}}"""
    results = defaultdict(lambda: defaultdict(list))

    with open(filename, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            testcase = row['testcase']
            decoder = row['decoder']
            if decoder == 'FAILED':
                continue
            decode_time = float(row['decode_ms'])
            results[testcase][decoder].append(decode_time)

    # Compute medians
    medians = {}
    for testcase in results:
        medians[testcase] = {}
        for decoder in results[testcase]:
            times = sorted(results[testcase][decoder])
            median = times[len(times) // 2]
            medians[testcase][decoder] = median

    return medians

def main():
    # Load Phase 1 results (from earlier benchmark)
    print("Loading benchmark results...")
    # We'll need to manually input Phase 1 key results for comparison
    # For now, analyze the current results

    phase2 = load_benchmark_csv('benchmark_results.csv')

    # Compute speedups vs C++
    speedups = []
    phase2_vs_cpp = {}

    for testcase in sorted(phase2.keys()):
        if 'rust' not in phase2[testcase] or 'cxx' not in phase2[testcase]:
            continue

        rust_time = phase2[testcase]['rust']
        cpp_time = phase2[testcase]['cxx']
        speedup = cpp_time / rust_time
        speedups.append(speedup)
        phase2_vs_cpp[testcase] = (rust_time, cpp_time, speedup)

    # Sort by speedup
    sorted_tests = sorted(phase2_vs_cpp.items(), key=lambda x: x[1][2], reverse=True)

    print("\n=== PHASE 2 vs C++ RESULTS ===\n")
    print(f"{'Test':<30} {'Rust (ms)':>10} {'C++ (ms)':>10} {'Speedup':>10}")
    print("-" * 65)

    for testcase, (rust_ms, cpp_ms, speedup) in sorted_tests:
        status = "⚡" if speedup > 1.0 else "🔴"
        print(f"{testcase:<30} {rust_ms:>10.2f} {cpp_ms:>10.2f} {speedup:>9.2f}x {status}")

    # Statistics
    median_speedup = sorted(speedups)[len(speedups) // 2]
    faster_count = sum(1 for s in speedups if s > 1.0)
    total = len(speedups)

    print(f"\n{'='*65}")
    print(f"Median speedup: {median_speedup:.2f}x")
    print(f"Tests faster than C++: {faster_count}/{total} ({100*faster_count/total:.0f}%)")
    print(f"Best speedup: {max(speedups):.2f}x ({sorted_tests[0][0]})")
    print(f"Worst speedup: {min(speedups):.2f}x ({sorted_tests[-1][0]})")

    # Key targets
    print(f"\n=== KEY TARGETS ===")
    for target in ['bike', 'bicycles', 'opsin_inverse', 'noise']:
        if target in phase2_vs_cpp:
            rust_ms, cpp_ms, speedup = phase2_vs_cpp[target]
            print(f"{target}: {speedup:.2f}x (Rust: {rust_ms:.2f}ms, C++: {cpp_ms:.2f}ms)")

if __name__ == '__main__':
    main()
