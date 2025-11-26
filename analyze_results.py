#!/usr/bin/env python3

import csv
import sys
from collections import defaultdict
from statistics import mean, stdev

def analyze_results(csv_file):
    # Read all data
    data = defaultdict(lambda: {'rust': [], 'cxx': []})

    with open(csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            testcase = row['testcase']
            decoder = row['decoder']
            decode_time = float(row['decode_ms'])
            total_time = float(row['total_ms'])
            throughput = float(row['throughput_mps'])

            data[testcase][decoder].append({
                'decode_ms': decode_time,
                'total_ms': total_time,
                'throughput_mps': throughput,
                'width': int(row['width']),
                'height': int(row['height']),
            })

    # Calculate statistics
    print("=" * 80)
    print("Performance Comparison: jxl-rs vs libjxl")
    print("=" * 80)
    print()

    results = []
    for testcase in sorted(data.keys()):
        if not data[testcase]['rust'] or not data[testcase]['cxx']:
            continue

        rust_decode = [x['decode_ms'] for x in data[testcase]['rust']]
        cxx_decode = [x['decode_ms'] for x in data[testcase]['cxx']]

        rust_mean = mean(rust_decode)
        cxx_mean = mean(cxx_decode)
        slowdown = rust_mean / cxx_mean if cxx_mean > 0 else 0

        width = data[testcase]['rust'][0]['width']
        height = data[testcase]['rust'][0]['height']

        results.append({
            'testcase': testcase,
            'width': width,
            'height': height,
            'rust_ms': rust_mean,
            'cxx_ms': cxx_mean,
            'slowdown': slowdown,
        })

    # Sort by slowdown (worst first)
    results.sort(key=lambda x: x['slowdown'], reverse=True)

    # Print detailed table
    print(f"{'Testcase':<30} {'Size':>12} {'Rust(ms)':>10} {'C++(ms)':>10} {'Slowdown':>10}")
    print("-" * 80)

    for r in results:
        size_str = f"{r['width']}x{r['height']}"
        print(f"{r['testcase']:<30} {size_str:>12} {r['rust_ms']:>10.2f} {r['cxx_ms']:>10.2f} {r['slowdown']:>9.2f}x")

    print()
    print("=" * 80)
    print("Summary Statistics")
    print("=" * 80)

    slowdowns = [r['slowdown'] for r in results]
    print(f"Average slowdown:    {mean(slowdowns):.2f}x")
    print(f"Median slowdown:     {sorted(slowdowns)[len(slowdowns)//2]:.2f}x")
    print(f"Worst slowdown:      {max(slowdowns):.2f}x ({results[0]['testcase']})")
    print(f"Best slowdown:       {min(slowdowns):.2f}x ({results[-1]['testcase']})")
    print(f"Std dev:             {stdev(slowdowns):.2f}x")
    print()

    # Print top 10 worst cases for targeted optimization
    print("=" * 80)
    print("Top 10 Worst Performance Cases (prioritize for optimization)")
    print("=" * 80)
    for i, r in enumerate(results[:10], 1):
        size_str = f"{r['width']}x{r['height']}"
        print(f"{i:2d}. {r['testcase']:<30} {size_str:>12} - {r['slowdown']:.2f}x slower")

if __name__ == '__main__':
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <benchmark_results.csv>")
        sys.exit(1)

    analyze_results(sys.argv[1])
