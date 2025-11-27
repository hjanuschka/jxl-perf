# Findings: Enabling SIMD Dispatch Restored AVX Performance

## Summary
While profiling the progressive benchmark, EPF0/1/2 still dominated execution despite existing SIMD code. Inspecting the build revealed that the `jxl` crate was compiled without its `avx` feature, so the `simd_function!` macro dispatched only to the scalar path. Compiling with `features = ["avx"]` activates the AVX2+FMA implementations already present in the source.

## Change
```toml
# Cargo.toml
[dependencies]
jxl = { path = "jxl-rs/jxl", features = ["avx"] }
```

After rebuilding in release mode, perf reports show the `*_dispatch::avx` variants in use.

## Impact (30 passing tests)
- Average slowdown: **1.39×** (down from ~1.75× baseline)
- Progressive: 1.20× (was ≈2.95×)
- Bike: 1.18×
- Worst remaining case: grayscale_jpeg_5 at 2.38×

Benchmarks re-run via `./run_benchmarks.sh`; report regenerated with `python3 generate_html.py benchmark_results.csv benchmark_failures.txt index.html`.

## Next Steps
- Clean up `unused_unsafe` warnings in SIMD helpers (cosmetic).
- Re-profile grayscale/noise cases now that SIMD is active; focus on algorithmic fixes rather than dispatch bugs.
- Keep the AVX feature on for all future builds; extend to `avx512` if desired once hardware is available.
