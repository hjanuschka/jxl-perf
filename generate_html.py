#!/usr/bin/env python3

import csv
import sys
import json
from datetime import datetime
from collections import defaultdict
from statistics import mean, stdev

def load_failures(failures_file):
    """Load failed tests from failures file"""
    failures = set()
    try:
        with open(failures_file, 'r') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    failures.add((parts[0], parts[1]))
    except FileNotFoundError:
        pass
    return failures

def analyze_results(csv_file, failures_file):
    # Load failures
    failures = load_failures(failures_file)

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
    results = []
    for testcase in sorted(data.keys()):
        rust_failed = (testcase, 'rust') in failures
        cxx_failed = (testcase, 'cxx') in failures

        if not data[testcase]['rust'] or not data[testcase]['cxx']:
            # Add entry for failed tests
            if rust_failed:
                results.append({
                    'testcase': testcase,
                    'width': 0,
                    'height': 0,
                    'rust_ms': None,
                    'cxx_ms': None,
                    'slowdown': None,
                    'rust_failed': True,
                    'cxx_failed': cxx_failed,
                })
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
            'rust_failed': rust_failed,
            'cxx_failed': cxx_failed,
        })

    return results, failures

def generate_html(csv_file, failures_file, output_file):
    results, failures = analyze_results(csv_file, failures_file)

    # Calculate summary statistics (only for successful tests)
    successful_results = [r for r in results if r['slowdown'] is not None]
    slowdowns = [r['slowdown'] for r in successful_results]

    # Sort by slowdown (worst first)
    successful_results.sort(key=lambda x: x['slowdown'], reverse=True)

    # Count failures
    rust_failures = sum(1 for r in results if r['rust_failed'])
    cxx_failures = sum(1 for r in results if r['cxx_failed'])

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>jxl-rs Performance Benchmarks</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            line-height: 1.6;
            color: #24292f;
            background: #ffffff;
            padding: 20px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{
            font-size: 2em;
            margin-bottom: 0.5em;
            border-bottom: 2px solid #d0d7de;
            padding-bottom: 0.3em;
        }}
        h2 {{
            font-size: 1.5em;
            margin-top: 1.5em;
            margin-bottom: 0.5em;
            border-bottom: 1px solid #d0d7de;
            padding-bottom: 0.3em;
        }}
        .timestamp {{
            color: #656d76;
            font-size: 0.9em;
            margin-bottom: 1em;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 1em;
            margin: 1em 0;
        }}
        .stat-card {{
            background: #f6f8fa;
            padding: 1em;
            border-radius: 6px;
            border: 1px solid #d0d7de;
        }}
        .stat-label {{
            font-size: 0.85em;
            color: #656d76;
            margin-bottom: 0.25em;
        }}
        .stat-value {{
            font-size: 1.5em;
            font-weight: 600;
        }}
        .stat-value.good {{ color: #1a7f37; }}
        .stat-value.bad {{ color: #cf222e; }}
        .stat-value.warning {{ color: #bf8700; }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 1em 0;
            font-size: 0.9em;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #d0d7de;
        }}
        th {{
            background: #f6f8fa;
            font-weight: 600;
            position: sticky;
            top: 0;
        }}
        tr:hover {{
            background: #f6f8fa;
        }}
        .testcase {{ font-family: monospace; }}
        .number {{ text-align: right; font-family: monospace; }}
        .failed {{ color: #cf222e; font-weight: 600; }}
        .fast {{ color: #1a7f37; }}
        .slow {{ color: #cf222e; }}
        .medium {{ color: #bf8700; }}

        .badge {{
            display: inline-block;
            padding: 2px 8px;
            border-radius: 12px;
            font-size: 0.75em;
            font-weight: 600;
        }}
        .badge.rust {{ background: #dea584; color: #000; }}
        .badge.cxx {{ background: #00599c; color: #fff; }}
        .badge.failed {{ background: #cf222e; color: #fff; }}

        footer {{
            margin-top: 3em;
            padding-top: 1em;
            border-top: 1px solid #d0d7de;
            color: #656d76;
            font-size: 0.85em;
            text-align: center;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>jxl-rs Performance Benchmarks</h1>
        <div class="timestamp">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")}</div>

        <h2>Summary Statistics</h2>
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Tests</div>
                <div class="stat-value">{len(results)}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Rust Failures</div>
                <div class="stat-value {'bad' if rust_failures > 0 else 'good'}">{rust_failures}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">C++ Failures</div>
                <div class="stat-value {'bad' if cxx_failures > 0 else 'good'}">{cxx_failures}</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Avg Slowdown</div>
                <div class="stat-value {'bad' if mean(slowdowns) > 2 else 'warning' if mean(slowdowns) > 1.5 else 'good'}">{mean(slowdowns):.2f}x</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Median Slowdown</div>
                <div class="stat-value">{sorted(slowdowns)[len(slowdowns)//2]:.2f}x</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Worst Case</div>
                <div class="stat-value bad">{max(slowdowns):.2f}x</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Best Case</div>
                <div class="stat-value good">{min(slowdowns):.2f}x</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Std Deviation</div>
                <div class="stat-value">{stdev(slowdowns):.2f}x</div>
            </div>
        </div>

        <h2>Detailed Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test Case</th>
                    <th>Size</th>
                    <th class="number">Rust (ms)</th>
                    <th class="number">C++ (ms)</th>
                    <th class="number">Slowdown</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
'''

    for r in results:
        if r['rust_failed']:
            status = '<span class="badge failed">RUST FAILED</span>'
            rust_ms = '<span class="failed">FAILED</span>'
            cxx_ms = f"{r['cxx_ms']:.2f}" if r['cxx_ms'] is not None else 'N/A'
            slowdown = 'N/A'
            size_str = 'N/A'
        else:
            status = ''
            if r['slowdown'] < 1.0:
                status = '<span class="badge rust">FASTER</span>'
                slowdown_class = 'fast'
            elif r['slowdown'] > 2.0:
                slowdown_class = 'slow'
            elif r['slowdown'] > 1.5:
                slowdown_class = 'medium'
            else:
                slowdown_class = ''

            rust_ms = f"{r['rust_ms']:.2f}"
            cxx_ms = f"{r['cxx_ms']:.2f}"
            slowdown = f'<span class="{slowdown_class}">{r["slowdown"]:.2f}x</span>'
            size_str = f"{r['width']}x{r['height']}"

        html += f'''                <tr>
                    <td class="testcase">{r['testcase']}</td>
                    <td class="number">{size_str}</td>
                    <td class="number">{rust_ms}</td>
                    <td class="number">{cxx_ms}</td>
                    <td class="number">{slowdown}</td>
                    <td>{status}</td>
                </tr>
'''

    html += '''            </tbody>
        </table>

        <footer>
            <p>Benchmarks powered by <a href="https://github.com/libjxl/conformance">libjxl/conformance</a> test suite</p>
            <p>Generated from <a href="https://github.com/hjanuschka/jxl-perf">hjanuschka/jxl-perf</a></p>
        </footer>
    </div>
</body>
</html>
'''

    with open(output_file, 'w') as f:
        f.write(html)

    print(f"HTML report generated: {output_file}")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <benchmark_results.csv> [failures.txt] [output.html]")
        sys.exit(1)

    csv_file = sys.argv[1]
    failures_file = sys.argv[2] if len(sys.argv) > 2 else 'benchmark_failures.txt'
    output_file = sys.argv[3] if len(sys.argv) > 3 else 'index.html'

    generate_html(csv_file, failures_file, output_file)
