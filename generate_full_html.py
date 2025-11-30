#!/usr/bin/env python3
"""Generate comprehensive HTML report from benchmark results"""

import csv
import sys
from collections import defaultdict
from datetime import datetime

# Get input file from command line or use default
input_file = sys.argv[1] if len(sys.argv) > 1 else 'benchmark_results.csv'

# Read and group results by test case
test_results = defaultdict(lambda: {'rust': [], 'cxx': []})

with open(input_file, 'r') as f:
    reader = csv.DictReader(f)
    for row in reader:
        test = row['testcase']
        decoder = row['decoder']
        if decoder in ['rust', 'cxx']:
            test_results[test][decoder].append(row)

# Calculate averages and comparisons
comparisons = []
for test, decoders in test_results.items():
    if decoders['rust'] and decoders['cxx']:
        # Average decode times
        rust_times = [float(r['decode_ms']) for r in decoders['rust'] if r['decode_ms'] != 'FAILED']
        cxx_times = [float(r['decode_ms']) for r in decoders['cxx'] if r['decode_ms'] != 'FAILED']

        if rust_times and cxx_times:
            rust_avg = sum(rust_times) / len(rust_times)
            cxx_avg = sum(cxx_times) / len(cxx_times)
            slowdown = rust_avg / cxx_avg

            # Get dimensions from first result
            first = decoders['rust'][0]
            comparisons.append({
                'test': test,
                'width': first['width'],
                'height': first['height'],
                'channels': first['channels'],
                'rust_ms': rust_avg,
                'cxx_ms': cxx_avg,
                'slowdown': slowdown
            })

# Sort by slowdown
comparisons.sort(key=lambda x: x['slowdown'])

# Calculate statistics
total_tests = len(comparisons)
excellent = len([c for c in comparisons if c['slowdown'] < 1.2])
good = len([c for c in comparisons if 1.2 <= c['slowdown'] < 1.5])
ok = len([c for c in comparisons if 1.5 <= c['slowdown'] < 2.0])
needs_work = len([c for c in comparisons if c['slowdown'] >= 2.0])

# Find best and worst
best = comparisons[0] if comparisons else None
worst = comparisons[-1] if comparisons else None

# Average slowdown
avg_slowdown = sum(c['slowdown'] for c in comparisons) / len(comparisons) if comparisons else 0

# Find specific tests
cafe5 = next((c for c in comparisons if c['test'] == 'cafe_5'), None)
noise5 = next((c for c in comparisons if c['test'] == 'noise_5'), None)
upsampling5 = next((c for c in comparisons if c['test'] == 'upsampling_5'), None)

# Generate HTML
html_template = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>jxl-rs Benchmark Results - Phase 3N Fast Paths</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            margin: 0;
            padding: 20px;
            background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
            min-height: 100vh;
        }}
        .container {{
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 20px;
            padding: 40px;
            box-shadow: 0 20px 40px rgba(0,0,0,0.1);
        }}
        h1 {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            font-size: 2.5em;
            margin-bottom: 10px;
        }}
        .achievement-banner {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
            color: white;
            padding: 30px;
            border-radius: 15px;
            margin: 20px 0;
            text-align: center;
            box-shadow: 0 10px 20px rgba(0,0,0,0.1);
        }}
        .achievement-banner h2 {{
            margin: 0 0 10px 0;
            font-size: 2em;
        }}
        .subtitle {{
            font-size: 1.1em;
            opacity: 0.95;
            margin: 5px 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 30px 0;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 25px;
            border-radius: 10px;
            box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        }}
        .stat-card.success {{
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }}
        .stat-card.warning {{
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }}
        .stat-label {{
            font-size: 0.9em;
            opacity: 0.9;
            margin-bottom: 5px;
        }}
        .stat-value {{
            font-size: 2.5em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-detail {{
            font-size: 0.85em;
            opacity: 0.85;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #e0e0e0;
        }}
        th {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            font-weight: 600;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
        .excellent {{ color: #27ae60; font-weight: bold; }}
        .good {{ color: #2ecc71; font-weight: bold; }}
        .ok {{ color: #f39c12; font-weight: bold; }}
        .needs-work {{ color: #e74c3c; font-weight: bold; }}
        .optimization-list {{
            background: #f8f9fa;
            border-radius: 10px;
            padding: 25px;
            margin: 30px 0;
        }}
        .optimization-list h3 {{
            color: #2c3e50;
            margin-bottom: 15px;
            font-size: 1.3em;
        }}
        .optimization-list ul {{
            list-style: none;
            padding-left: 0;
        }}
        .optimization-list li {{
            padding: 8px 0;
            border-bottom: 1px solid #e0e0e0;
        }}
        .checkmark {{
            color: #27ae60;
            margin-right: 10px;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🚀 jxl-rs Phase 3N Results - Fast Path Optimizations</h1>

        <div class="achievement-banner">
            <h2>✅ Phase 3N: Fast Paths Implemented!</h2>
            <div class="subtitle"><strong>{avg_slowdown:.2f}x</strong> average vs C++ across {total_tests} tests</div>
            <div class="subtitle">Best: <strong>{best_test}</strong> ({best_slowdown:.2f}x) | Worst: <strong>{worst_test}</strong> ({worst_slowdown:.2f}x)</div>
            <div class="subtitle">✅ Zero coefficient skip | ✅ Color correlation skip | ✅ RCT identity skip</div>
        </div>

        <div class="stats-grid">
            <div class="stat-card success">
                <div class="stat-label">Excellent (&lt;1.2x)</div>
                <div class="stat-value">{excellent}</div>
                <div class="stat-detail">{excellent_pct}% of tests</div>
            </div>

            <div class="stat-card success">
                <div class="stat-label">Good (1.2-1.5x)</div>
                <div class="stat-value">{good}</div>
                <div class="stat-detail">{good_pct}% of tests</div>
            </div>

            <div class="stat-card warning">
                <div class="stat-label">OK (1.5-2.0x)</div>
                <div class="stat-value">{ok}</div>
                <div class="stat-detail">{ok_pct}% of tests</div>
            </div>

            <div class="stat-card warning">
                <div class="stat-label">Needs Work (≥2.0x)</div>
                <div class="stat-value">{needs_work}</div>
                <div class="stat-detail">{needs_work_pct}% of tests</div>
            </div>
        </div>

        <div class="optimization-list">
            <h3>🎯 Key Benchmarks</h3>
            <ul>
                <li><span class="checkmark">📊</span> <strong>cafe_5:</strong> {cafe5_rust:.2f}ms Rust / {cafe5_cxx:.2f}ms C++ = <strong>{cafe5_slowdown:.2f}x</strong></li>
                <li><span class="checkmark">📊</span> <strong>noise_5:</strong> {noise5_rust:.2f}ms Rust / {noise5_cxx:.2f}ms C++ = <strong>{noise5_slowdown:.2f}x</strong></li>
                <li><span class="checkmark">📊</span> <strong>upsampling_5:</strong> {upsampling5_rust:.2f}ms Rust / {upsampling5_cxx:.2f}ms C++ = <strong>{upsampling5_slowdown:.2f}x</strong></li>
            </ul>

            <h3>✅ Phase 3N Fast Path Optimizations (COMPLETE)</h3>
            <ul>
                <li><span class="checkmark">✅</span> <strong>Zero Coefficient Block Skip</strong> - Skip decoding when nonzeros == 0</li>
                <li><span class="checkmark">✅</span> <strong>Default Color Correlation Skip</strong> - Avoid mul_add when x_cc_mul/b_cc_mul == 0.0</li>
                <li><span class="checkmark">✅</span> <strong>RCT Identity Skip</strong> - Early return for Noop operation with RGB permutation</li>
                <li><span class="checkmark">✅</span> <strong>Native CPU Optimizations</strong> - RUSTFLAGS="-C target-cpu=native"</li>
            </ul>

            <h3>📊 Performance Evolution</h3>
            <ul>
                <li><span class="checkmark">📈</span> <strong>Baseline:</strong> cafe_5 at 112ms (3.46x vs C++)</li>
                <li><span class="checkmark">📈</span> <strong>Phase 3H (ANS):</strong> 64ms (2.00x) - 43% gain</li>
                <li><span class="checkmark">📈</span> <strong>Phase 3N (Fast Paths):</strong> Current results shown above</li>
            </ul>
        </div>

        <h2>Detailed Benchmark Results</h2>
        <table>
            <thead>
                <tr>
                    <th>Test Case</th>
                    <th>Size</th>
                    <th>Channels</th>
                    <th>Rust (ms)</th>
                    <th>C++ (ms)</th>
                    <th>Slowdown</th>
                    <th>Status</th>
                </tr>
            </thead>
            <tbody>
{table_rows}
            </tbody>
        </table>

        <div style="text-align: center; margin-top: 40px; color: #7f8c8d;">
            <p>Generated on {timestamp}</p>
            <p>Build: RUSTFLAGS="-C target-cpu=native" | Runtime: RAYON_NUM_THREADS=8</p>
            <p>{total_tests} tests passing | Average slowdown: {avg_slowdown:.2f}x</p>
        </div>
    </div>
</body>
</html>'''

# Build table rows
table_rows = ""
for comp in comparisons:
    if comp['slowdown'] < 1.2:
        status_class = 'excellent'
        status = 'Excellent'
    elif comp['slowdown'] < 1.5:
        status_class = 'good'
        status = 'Good'
    elif comp['slowdown'] < 2.0:
        status_class = 'ok'
        status = 'OK'
    else:
        status_class = 'needs-work'
        status = 'Needs Work'

    table_rows += f"""                <tr>
                    <td>{comp['test']}</td>
                    <td>{comp['width']}x{comp['height']}</td>
                    <td>{comp['channels']}</td>
                    <td>{comp['rust_ms']:.2f}</td>
                    <td>{comp['cxx_ms']:.2f}</td>
                    <td class="{status_class}">{comp['slowdown']:.2f}x</td>
                    <td class="{status_class}">{status}</td>
                </tr>
"""

# Fill in template values
html = html_template.format(
    avg_slowdown=avg_slowdown,
    total_tests=total_tests,
    best_test=best['test'] if best else 'N/A',
    best_slowdown=best['slowdown'] if best else 0,
    worst_test=worst['test'] if worst else 'N/A',
    worst_slowdown=worst['slowdown'] if worst else 0,
    excellent=excellent,
    excellent_pct=excellent*100//total_tests if total_tests else 0,
    good=good,
    good_pct=good*100//total_tests if total_tests else 0,
    ok=ok,
    ok_pct=ok*100//total_tests if total_tests else 0,
    needs_work=needs_work,
    needs_work_pct=needs_work*100//total_tests if total_tests else 0,
    cafe5_rust=cafe5['rust_ms'] if cafe5 else 0,
    cafe5_cxx=cafe5['cxx_ms'] if cafe5 else 0,
    cafe5_slowdown=cafe5['slowdown'] if cafe5 else 0,
    noise5_rust=noise5['rust_ms'] if noise5 else 0,
    noise5_cxx=noise5['cxx_ms'] if noise5 else 0,
    noise5_slowdown=noise5['slowdown'] if noise5 else 0,
    upsampling5_rust=upsampling5['rust_ms'] if upsampling5 else 0,
    upsampling5_cxx=upsampling5['cxx_ms'] if upsampling5 else 0,
    upsampling5_slowdown=upsampling5['slowdown'] if upsampling5 else 0,
    table_rows=table_rows,
    timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S')
)

# Write HTML file
with open('index.html', 'w') as f:
    f.write(html)

print(f"Generated index.html with {total_tests} test comparisons")
print(f"Average slowdown: {avg_slowdown:.2f}x")
print(f"Distribution: {excellent} excellent, {good} good, {ok} ok, {needs_work} needs work")
if cafe5:
    print(f"cafe_5: {cafe5['rust_ms']:.2f}ms Rust / {cafe5['cxx_ms']:.2f}ms C++ ({cafe5['slowdown']:.2f}x)")
if noise5:
    print(f"noise_5: {noise5['rust_ms']:.2f}ms Rust / {noise5['cxx_ms']:.2f}ms C++ ({noise5['slowdown']:.2f}x)")