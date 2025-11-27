# Rust Performance Optimization Guide

## Overview
This guide covers all major techniques for optimizing Rust code for maximum performance, specifically for CPU-bound numerical workloads like image decoding.

---

## 1. SIMD (Single Instruction, Multiple Data)

**What it is**: Process multiple data elements in parallel using special CPU instructions.

### Techniques

#### A. Auto-Vectorization (Easiest)
Let the compiler automatically use SIMD by writing vectorizable code:

```rust
// BAD - Not vectorizable (iterator overhead, complex pattern)
for i in (0..len).step_by(2) {
    output[i] = input[i] * 2.0 + input[i+1];
}

// GOOD - Vectorizable (simple loop, predictable pattern)
for i in 0..len {
    output[i] = input[i] * 2.0;
}
```

**Tips for auto-vectorization**:
- Use simple loops with predictable bounds
- Unroll manually to help compiler see patterns
- Avoid complex conditionals inside loops
- Use slice operations when possible
- Compiler flag: `RUSTFLAGS="-C target-cpu=native"` to enable AVX2/AVX512

#### B. Explicit SIMD (Portable SIMD - Nightly Rust)
```rust
#![feature(portable_simd)]
use std::simd::*;

fn multiply_simd(input: &[f32], output: &mut [f32]) {
    let chunks = input.chunks_exact(8);
    let remainder = chunks.remainder();

    for (in_chunk, out_chunk) in chunks.zip(output.chunks_exact_mut(8)) {
        let vec = f32x8::from_slice(in_chunk);
        let result = vec * f32x8::splat(2.0);
        result.copy_to_slice(out_chunk);
    }

    // Handle remainder
    for i in 0..remainder.len() {
        output[input.len() - remainder.len() + i] = remainder[i] * 2.0;
    }
}
```

####C. `packed_simd` crate (Stable Rust)
```rust
use packed_simd::*;

fn process_simd(data: &[f32]) -> f32x4 {
    f32x4::from_slice_unaligned(data) * f32x4::splat(2.0)
}
```

#### D. Platform-Specific SIMD
```rust
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;

#[target_feature(enable = "avx2")]
unsafe fn avx2_multiply(a: &[f32], b: &[f32], out: &mut [f32]) {
    for i in (0..a.len()).step_by(8) {
        let va = _mm256_loadu_ps(a.as_ptr().add(i));
        let vb = _mm256_loadu_ps(b.as_ptr().add(i));
        let result = _mm256_mul_ps(va, vb);
        _mm256_storeu_ps(out.as_mut_ptr().add(i), result);
    }
}
```

---

## 2. Loop Optimizations

### A. Loop Unrolling
```rust
// BEFORE
for i in 0..len {
    sum += data[i];
}

// AFTER - Manually unrolled
let chunks = len / 4;
for i in 0..chunks {
    let base = i * 4;
    sum += data[base];
    sum += data[base + 1];
    sum += data[base + 2];
    sum += data[base + 3];
}
// Handle remainder
for i in (chunks * 4)..len {
    sum += data[i];
}
```

**Why it works**: Reduces loop overhead, enables instruction-level parallelism, helps SIMD.

### B. Loop Fusion
```rust
// BEFORE - Two passes over data
for x in data.iter_mut() {
    *x *= 2.0;
}
for x in data.iter_mut() {
    *x += 1.0;
}

// AFTER - Single pass
for x in data.iter_mut() {
    *x = *x * 2.0 + 1.0;
}
```

### C. Loop Interchange
```rust
// BEFORE - Cache-unfriendly (column-major access)
for x in 0..width {
    for y in 0..height {
        image[y][x] = process(x, y);
    }
}

// AFTER - Cache-friendly (row-major access)
for y in 0..height {
    for x in 0..width {
        image[y][x] = process(x, y);
    }
}
```

---

## 3. Bounds Check Elimination

Rust checks array bounds on every access. Eliminate in hot loops:

```rust
// BEFORE - Bounds checked every iteration
for i in 0..len {
    data[i] = i as f32;
}

// AFTER - Single bounds check
let data_slice = &mut data[0..len]; // Single check here
for i in 0..len {
    unsafe {
        *data_slice.get_unchecked_mut(i) = i as f32;
    }
}

// OR use iterators (compiler can often elide checks)
for (i, val) in data.iter_mut().enumerate() {
    *val = i as f32;
}
```

**When to use unsafe**:
- ✅ Hot loops (profiled bottlenecks)
- ✅ When you've proven bounds are valid
- ✅ Add `debug_assert!` for safety:
  ```rust
  debug_assert!(i < data.len());
  unsafe { *data.get_unchecked_mut(i) = value; }
  ```
- ❌ Don't use for marginal gains

---

## 4. Memory Optimization

### A. Stack Allocation
```rust
// BEFORE - Heap allocation
let mut buffer = vec![0.0f32; 1024];

// AFTER - Stack allocation (if size known at compile time)
let mut buffer = [0.0f32; 1024];
```

### B. Memory Pooling / Reuse
```rust
// BEFORE - Allocate every time
fn process_frame(input: &[u8]) -> Vec<f32> {
    let mut output = vec![0.0; input.len()];
    // ... process ...
    output
}

// AFTER - Reuse buffer
struct Processor {
    buffer: Vec<f32>,
}

impl Processor {
    fn process_frame(&mut self, input: &[u8], output: &mut [f32]) {
        self.buffer.resize(input.len(), 0.0);
        // ... process using self.buffer ...
    }
}
```

### C. Alignment
```rust
#[repr(align(64))] // Cache line aligned
struct AlignedBuffer {
    data: [f32; 1024],
}
```

### D. Avoid Small Allocations
```rust
// BEFORE
let values: Vec<String> = items.iter().map(|x| x.to_string()).collect();

// AFTER - Reuse capacity
let mut values = Vec::with_capacity(items.len());
for item in items {
    values.push(item.to_string());
}
```

---

## 5. Branch Prediction & Branchless Code

### A. Branchless Operations
```rust
// BEFORE - Branch misprediction possible
let result = if value > threshold {
    expensive_op(value)
} else {
    cheap_op(value)
};

// AFTER - Branchless (when both ops are cheap)
let mask = (value > threshold) as usize;
let results = [cheap_op(value), expensive_op(value)];
let result = results[mask];
```

### B. Unlikely/Likely Hints
```rust
#[cold]
#[inline(never)]
fn handle_error() {
    // Error path
}

fn process(value: i32) {
    if unlikely!(value < 0) {
        handle_error();
    }
    // Hot path
}

// Define unlikely macro
macro_rules! unlikely {
    ($e:expr) => {
        std::intrinsics::unlikely($e)
    };
}
```

### C. Lookup Tables
```rust
// BEFORE
fn classify(x: u8) -> u8 {
    match x {
        0..=50 => 0,
        51..=100 => 1,
        101..=150 => 2,
        _ => 3,
    }
}

// AFTER
static LOOKUP: [u8; 256] = /* precomputed array */;
fn classify(x: u8) -> u8 {
    LOOKUP[x as usize]
}
```

---

## 6. Function Inlining

```rust
// Force inline hot functions
#[inline(always)]
fn hot_function(x: f32) -> f32 {
    x * x + 2.0
}

// Prevent inlining cold functions
#[inline(never)]
fn cold_error_handler() {
    // ...
}
```

---

## 7. Copy vs. Reference

### Use Copy Types
```rust
// Define copyable types for small data
#[derive(Copy, Clone)]
struct Point {
    x: f32,
    y: f32,
}

fn process(p: Point) -> Point {  // Passed by value, cheap copy
    Point { x: p.x * 2.0, y: p.y * 2.0 }
}
```

### Avoid Unnecessary Clones
```rust
// BEFORE
fn process(data: Vec<f32>) -> Vec<f32> {
    let copy = data.clone();  // Unnecessary
    copy.iter().map(|x| x * 2.0).collect()
}

// AFTER
fn process(data: &[f32]) -> Vec<f32> {
    data.iter().map(|x| x * 2.0).collect()
}
```

---

## 8. Const/Static Precomputation

```rust
// BEFORE - Computed at runtime
fn kernel() -> [[f32; 5]; 5] {
    let mut k = [[0.0; 5]; 5];
    for i in 0..5 {
        for j in 0..5 {
            k[i][j] = compute_weight(i, j);
        }
    }
    k
}

// AFTER - Computed at compile time
const KERNEL: [[f32; 5]; 5] = {
    let mut k = [[0.0; 5]; 5];
    // Use const fn or const_eval
    k
};
```

---

## 9. Parallel Processing

### A. Rayon (Data Parallelism)
```rust
use rayon::prelude::*;

// BEFORE
for row in rows.iter_mut() {
    process_row(row);
}

// AFTER - Parallel
rows.par_iter_mut().for_each(|row| {
    process_row(row);
});
```

### B. Thread Pool
```rust
use threadpool::ThreadPool;

let pool = ThreadPool::new(num_cpus::get());
for chunk in data.chunks_mut(chunk_size) {
    pool.execute(move || {
        process_chunk(chunk);
    });
}
pool.join();
```

---

## 10. Compiler Optimizations

### Build Flags
```bash
# Enable LTO (Link Time Optimization)
cargo build --release

# In Cargo.toml
[profile.release]
lto = "fat"              # Full LTO
codegen-units = 1        # Better optimization
opt-level = 3            # Maximum optimization
panic = "abort"          # Smaller binary, faster
strip = true             # Strip symbols

# CPU-specific optimizations
RUSTFLAGS="-C target-cpu=native" cargo build --release

# Profile-Guided Optimization (PGO)
RUSTFLAGS="-C profile-generate=/tmp/pgo-data" cargo build --release
# Run binary with typical workload
./target/release/my_app
RUSTFLAGS="-C profile-use=/tmp/pgo-data/merged.profdata" cargo build --release
```

---

## 11. Avoiding Allocator Overhead

```rust
// Use bump allocators for temporary allocations
use bumpalo::Bump;

let arena = Bump::new();
let temp_buffer = arena.alloc_slice_fill_copy(1024, 0.0f32);
// Use temp_buffer
// arena.reset(); // Reuse arena
```

---

## 12. Assembly Inspection

### Check what the compiler generates
```bash
# View assembly
cargo rustc --release -- --emit asm

# Use cargo-asm
cargo install cargo-asm
cargo asm my_crate::my_function --rust

# Use godbolt.org online
```

---

## 13. Micro-Benchmarking

### Use Criterion
```rust
use criterion::{black_box, criterion_group, criterion_main, Criterion};

fn benchmark_upsample(c: &mut Criterion) {
    let input = vec![1.0f32; 1000];
    let mut output = vec![0.0f32; 2000];

    c.bench_function("upsample", |b| {
        b.iter(|| {
            upsample(black_box(&input), black_box(&mut output));
        });
    });
}

criterion_group!(benches, benchmark_upsample);
criterion_main!(benches);
```

---

## 14. Specific Patterns for Image Processing

### A. Separable Filters
```rust
// BEFORE - 2D convolution: O(width * height * kernel² )
for y in 0..height {
    for x in 0..width {
        for ky in 0..kernel_size {
            for kx in 0..kernel_size {
                sum += input[y+ky][x+kx] * kernel_2d[ky][kx];
            }
        }
    }
}

// AFTER - Separable: O(width * height * kernel * 2)
// Horizontal pass
for y in 0..height {
    for x in 0..width {
        for k in 0..kernel_size {
            sum += input[y][x+k] * kernel_h[k];
        }
        temp[y][x] = sum;
    }
}
// Vertical pass
for y in 0..height {
    for x in 0..width {
        for k in 0..kernel_size {
            sum += temp[y+k][x] * kernel_v[k];
        }
        output[y][x] = sum;
    }
}
```

### B. Cache Blocking (Tiling)
```rust
const TILE_SIZE: usize = 64;

for ty in (0..height).step_by(TILE_SIZE) {
    for tx in (0..width).step_by(TILE_SIZE) {
        let y_end = (ty + TILE_SIZE).min(height);
        let x_end = (tx + TILE_SIZE).min(width);

        // Process tile
        for y in ty..y_end {
            for x in tx..x_end {
                process_pixel(x, y);
            }
        }
    }
}
```

---

## 15. Profiling Tools

```bash
# perf (Linux)
perf record -F 999 --call-graph dwarf ./my_binary
perf report

# Flamegraph
cargo install flamegraph
cargo flamegraph --bin my_binary

# Valgrind cachegrind
valgrind --tool=cachegrind ./my_binary
cg_annotate cachegrind.out.*

# Criterion benchmarks
cargo bench

# cargo-llvm-lines (code bloat)
cargo install cargo-llvm-lines
cargo llvm-lines
```

---

## Priority Checklist for Optimization

1. ✅ **Profile first** - Find actual bottlenecks
2. ✅ **Algorithm first** - O(n) → O(log n) beats any micro-optimization
3. ✅ **Memory layout** - Cache-friendly access patterns
4. ✅ **Loop unrolling** - Help compiler vectorize
5. ✅ **SIMD** - Explicit or auto-vectorization
6. ✅ **Bounds check elimination** - In proven-safe hot loops
7. ✅ **Inline hot functions** - `#[inline(always)]`
8. ✅ **Precompute constants** - Move to compile time
9. ✅ **Parallelize** - Use rayon for data parallelism
10. ✅ **Compiler flags** - LTO, codegen-units=1, target-cpu=native

---

## Example: Putting It All Together

```rust
#[inline(always)]
pub fn optimized_upsample(
    input: &[&[f32]],           // Input rows
    output: &mut [&mut [f32]],  // Output rows
    kernel: &[[[f32; 5]; 5]],   // Precomputed kernel
    width: usize,
) {
    const TILE: usize = 16; // Cache-friendly tile size

    for x_tile in (0..width).step_by(TILE) {
        let x_end = (x_tile + TILE).min(width);

        for x in x_tile..x_end {
            // Bounds checked once per tile
            let in_slice = &input[0][x..x+5];

            // Unrolled inner loop for auto-vectorization
            for di in 0..2 {
                for dj in 0..2 {
                    let k = &kernel[di][dj];

                    // This pattern is easy for LLVM to vectorize
                    let mut sum = 0.0f32;
                    for i in 0..5 {
                        sum += in_slice[0] * k[i][0];
                        sum += in_slice[1] * k[i][1];
                        sum += in_slice[2] * k[i][2];
                        sum += in_slice[3] * k[i][3];
                        sum += in_slice[4] * k[i][4];
                    }

                    unsafe {
                        *output[di].get_unchecked_mut(dj + 2 * x) = sum;
                    }
                }
            }
        }
    }
}
```

---

## Summary

**Most impactful optimizations** (in order):
1. Better algorithm (complexity reduction)
2. SIMD (2-8x speedup on numerical code)
3. Cache-friendly memory access
4. Loop unrolling
5. Removing bounds checks in hot loops
6. Parallel processing (near-linear with cores)
7. Compiler flags (LTO, target-cpu=native)

**Always**:
- Profile before optimizing
- Benchmark after optimizing
- Ensure correctness isn't broken
- Document why unsafe is safe
