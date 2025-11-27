#!/usr/bin/env python3
"""Extract top functions from flamegraph SVG files."""

import re
import sys
from collections import defaultdict

def parse_flamegraph(filename):
    """Parse SVG flamegraph and extract function samples."""
    functions = defaultdict(int)

    with open(filename, 'r') as f:
        content = f.read()

    # Extract all <g> elements with function names and sample counts
    # Pattern: <title>function_name (X samples, Y.YY%)</title>
    pattern = r'<title>([^(]+)\s*\((\d+)\s+samples?,\s+([\d.]+)%\)</title>'

    for match in re.finditer(pattern, content):
        func_name = match.group(1).strip()
        samples = int(match.group(2))
        percent = float(match.group(3))

        # Skip "all" entries
        if func_name != 'all':
            functions[func_name] = (samples, percent)

    return functions

def print_top_functions(filename, top_n=15):
    """Print top N functions by sample count."""
    functions = parse_flamegraph(filename)

    # Sort by sample count (descending)
    sorted_funcs = sorted(functions.items(), key=lambda x: x[1][0], reverse=True)

    print(f"\n{'='*80}")
    print(f"Top {top_n} functions in {filename}")
    print(f"{'='*80}")
    print(f"{'Function':<60} {'Samples':>8} {'%':>8}")
    print(f"{'-'*80}")

    for func, (samples, percent) in sorted_funcs[:top_n]:
        # Truncate long function names
        display_func = func if len(func) <= 59 else func[:56] + '...'
        print(f"{display_func:<60} {samples:>8} {percent:>7.2f}%")

    return sorted_funcs

if __name__ == '__main__':
    files = ['progressive_flamegraph.svg', 'grayscale_flamegraph.svg', 'noise_flamegraph.svg']

    results = {}
    for filename in files:
        try:
            results[filename] = print_top_functions(filename)
        except FileNotFoundError:
            print(f"Warning: {filename} not found")

    # Print summary
    print(f"\n{'='*80}")
    print("SUMMARY: Common hot functions across all tests")
    print(f"{'='*80}")

    # Find functions that appear in multiple profiles
    all_funcs = set()
    for funcs_list in results.values():
        all_funcs.update([f[0] for f in funcs_list[:10]])

    for func in all_funcs:
        appearances = []
        for filename, funcs_list in results.items():
            func_dict = dict(funcs_list)
            if func in func_dict:
                samples, percent = func_dict[func]
                test_name = filename.replace('_flamegraph.svg', '')
                appearances.append(f"{test_name}: {percent:.1f}%")

        if len(appearances) >= 2:  # Appears in at least 2 tests
            print(f"\n{func}:")
            for app in appearances:
                print(f"  - {app}")
