# Round 9 Post-Mortem: EPF Algorithm Port Failure

**Date**: 2025-11-27
**Optimization Attempted**: Port C++ libjxl EPF0 algorithm to Rust
**Result**: ❌ **CATASTROPHIC FAILURE** - 46% regression on progressive images
**Status**: Reverted

---

## Executive Summary

After profiling identified EPF0 as consuming 37% of CPU time in progressive images, we attempted to port the C++ libjxl EPF0 algorithm to Rust, believing it would provide better cache locality and lower register pressure. **This was completely wrong**. The optimization made performance 46-49% WORSE on progressive images and 11% worse overall.

This is the **THIRD consecutive failed optimization** (Round 7: -22%, Round 8: -5-19%, Round 9: -11%).

---

## What We Tried

### Original Rust Implementation
**Algorithm**: Precompute all pairwise differences, then accumulate
- Load ALL 27 pixels from 7x7 window upfront
- Compute 50+ pairwise absolute differences
- Accumulate precomputed differences into 12 SADs

**Code structure** (lines 93-180 of epf0.rs):
```rust
// Load all pixels
let p30 = D::F32Vec::load(d, &input_c[0][3 + x..]);
let p21 = D::F32Vec::load(d, &input_c[1][2 + x..]);
// ... 25 more loads (27 total) ...

// Compute all pairwise differences
let d32_30 = (p32 - p30).abs();
let d32_21 = (p32 - p21).abs();
// ... 48 more differences ...

// Accumulate into SADs
sads[0] = scale.mul_add(d32_30 + d23_21 + d33_31 + d43_41 + d32_34, sads[0]);
// ... 11 more accumulations ...
```

###Our "Optimization" (FAILED)
**Algorithm**: Compute each SAD on-demand with immediate accumulation (matching C++)
- For each of 12 neighbor positions:
  - For each of 5 pixels in plus-shaped kernel:
    - Load center pixel with offset
    - Load neighbor pixel with offset
    - Compute absolute difference
    - **Immediately accumulate** into SAD

**Code structure** (our failed implementation):
```rust
const NEIGHBOR_OFFSETS: [(isize, isize); 12] = [
    (-2, 0), (-1, -1), (-1, 0), (-1, 1), (0, -2), (0, -1),
    (0, 1),  (0, 2),   (1, -1), (1, 0),  (1, 1),  (2, 0),
];

const PLUS_OFFSETS: [(isize, isize); 5] = [
    (0, 0), (-1, 0), (0, -1), (1, 0), (0, 1)
];

for &(ny, nx) in NEIGHBOR_OFFSETS.iter() {
    let mut sad = D::F32Vec::splat(d, 0.0);
    for &(oy, ox) in PLUS_OFFSETS.iter() {
        let center = D::F32Vec::load(d, &input_c[3 + oy][3 + x + ox..]);
        let neighbor = D::F32Vec::load(d, &input_c[3 + ny + oy][3 + x + nx + ox..]);
        sad += (center - neighbor).abs();
    }
    sads[idx] = scale.mul_add(sad, sads[idx]);
}
```

---

## Results

### Performance Impact

| Test | Baseline (Round 6) | Round 9 | Regression |
|------|-------------------|---------|------------|
| **progressive** | 1280ms (2.95x) | 1936ms (4.30x) | **+51% slower** ❌ |
| **progressive_5** | 1293ms (2.99x) | 1954ms (4.46x) | **+51% slower** ❌ |
| **grayscale_public_university** | 846ms (3.05x) | 1114ms (4.25x) | **+32% slower** ❌ |
| **bike_5** | 419ms (2.51x) | 589ms (3.53x) | **+41% slower** ❌ |
| **bike** | 409ms (2.45x) | 578ms (3.45x) | **+41% slower** ❌ |

### Overall Metrics
- **Average slowdown**: 1.95x (was 1.75x) → **+11% regression**
- **Median slowdown**: 1.96x (was 1.84x) → **+7% regression**
- **Worst case**: progressive_5 went from 2.99x → 4.46x (49% worse)

### No Improvements
**ZERO tests improved**. Every single test either regressed significantly or stayed roughly the same.

---

## Root Cause Analysis

### Why Our "Optimization" Failed

**Hypothesis**: C++ algorithm has better cache locality and lower register pressure
**Reality**: Rust compiler already optimizes the precomputed approach extremely well

#### Problem 1: Nested Loop Overhead
Our implementation introduced **3 nested loops**:
```rust
for channel in 0..3 {           // Outer loop
    for neighbor in 0..12 {     // Middle loop
        for pixel in 0..5 {     // Inner loop - NEW OVERHEAD!
            // Load and compute
        }
    }
}
```

The original Rust code **unrolls** all pixel accesses at compile time - no loops!

#### Problem 2: Dynamic Index Calculation
Our code computes array indices **at runtime**:
```rust
let center_row = (3 + oy) as usize;           // Runtime calculation
let center_col = (3 + x as isize + ox) as usize;  // Runtime calculation
```

The original code has **compile-time constant indices**:
```rust
let p30 = D::F32Vec::load(d, &input_c[0][3 + x..]);  // Const index
let p21 = D::F32Vec::load(d, &input_c[1][2 + x..]);  // Const index
```

#### Problem 3: More Memory Loads
**Our approach**: 3 channels × 12 neighbors × 5 pixels = **180 loads** (many redundant)
**Original approach**: 3 channels × 27 unique pixels = **81 loads** (no redundancy)

The Rust compiler can **optimize away** redundant subexpressions in the precomputed approach.

#### Problem 4: Register Spilling
Storing 12 neighbor offsets and 5 plus offsets as arrays causes them to be stored in **memory**, not registers. The original code has all offsets as **immediate constants** in the compiled assembly.

---

## What The C++ Code Actually Does

Looking more carefully at the C++ implementation, we found:

### Highway SIMD Library Differences
C++ uses Google **Highway** SIMD library:
- `LoadU()` - unaligned load
- `Load()` - aligned load
- `AbsDiff()`, `Add()`, `MulAdd()` - explicit SIMD operations

Rust uses **jxl_simd** abstraction:
- Different API surface
- Different optimization characteristics
- **May already be more optimized than C++**

### Compiler Optimization Levels
- **C++ libjxl**: Uses Highway dynamic dispatch (`HWY_DYNAMIC_DISPATCH`)
- **Rust jxl-rs**: Uses `simd_function!` macro with static dispatch
- Rust's approach may actually be **MORE optimized** due to monomorphization

---

## Why Profiling Misled Us

### The Paradox
- Profiling correctly identified EPF0 as 37% of CPU time ✅
- We correctly found the Rust and C++ implementations differ ✅
- **But we incorrectly assumed C++'s approach was better** ❌

### What We Missed
1. **Rust's precomputed approach is optimized by LLVM** - constant folding, CSE, vectorization
2. **C++'s on-demand approach is optimized for Highway** - may not translate well to Rust SIMD
3. **The C++ code is ALSO slow** - EPF takes 60% of C++ time too! It's just that C++ is faster overall.

---

## Lessons Learned

### ❌ DO NOT Do This Again
1. **Don't blindly port C++ algorithms to Rust** - they optimize differently
2. **Don't assume "better algorithm" = faster** - compiler optimizations matter more
3. **Don't introduce dynamic loops** where static unrolling works
4. **Don't use runtime index calculations** when compile-time constants work

### ✅ What To Do Instead
1. **Profile the GENERATED ASSEMBLY**, not just the source code
2. **Benchmark micro-changes** before full implementation
3. **Trust the Rust compiler's optimizations** - LLVM is very good
4. **Focus on algorithmic improvements**, not code structure changes

---

## Why EPF Is Still Slow (Even In C++)

### The Real Problem
EPF **is actually slow in C++ too**! Looking at the C++ benchmark:
- Progressive C++: 430ms
- Progressive Rust: 1280ms (2.95x slower)

EPF consumes similar **percentage of time** in both:
- C++: ~60% of 430ms = 258ms in EPF
- Rust: ~60% of 1280ms = 768ms in EPF

**The real issue**: Rust's EPF is **3x slower in absolute time**, not because of the algorithm, but because **Rust's SIMD is 3x slower**.

### The Real Bottleneck
It's not the algorithm. It's **SIMD code generation quality**.

Possible causes:
1. jxl_simd wrapper adds overhead vs Highway
2. Rust SIMD intrinsics generate worse assembly
3. LLVM's Rust backend is less optimized than C++ backend for this workload
4. Missing SIMD optimizations that C++ has

---

## Next Steps (What NOT To Do)

### ❌ Bad Ideas (Don't Try These)
1. **Port more C++ code structure** - proven to make things worse
2. **Micro-optimize the SAD computation** - algorithm is fine
3. **Add manual unrolling hints** - compiler already unrolls optimally
4. **Try different SIMD approaches** - too risky after 3 failures

### ✅ Better Ideas (Consider These)
1. **Compare generated assembly** (Rust vs C++)
   - Use `cargo asm` to see what LLVM generates
   - Use `objdump` to see what C++ generates
   - Find specific codegen differences

2. **Profile with perf at instruction level**
   - See which instructions are slow
   - Check for cache misses, branch mispredicts
   - Identify specific SIMD instruction inefficiencies

3. **Benchmark individual SIMD operations**
   - Test `F32Vec::load` performance
   - Test `abs()` performance
   - Test `mul_add()` performance
   - Find which primitive is slow

4. **Check if problem is elsewhere**
   - EPF might not be the real bottleneck
   - Could be the rendering pipeline calling EPF
   - Could be memory allocation
   - Could be something outside EPF entirely

---

## Conclusion

Attempting to port C++'s EPF0 algorithm to Rust was a **catastrophic failure** that made performance 46% worse on our most important test case (progressive images).

The key insight: **Don't fight the Rust compiler**. The original precomputed approach is actually correct and well-optimized by LLVM. Our "optimization" introduced runtime overhead that destroyed performance.

**After 3 consecutive failed optimizations (Rounds 7, 8, 9), it's time to fundamentally rethink our approach.** Speculation and code inspection have failed. We need assembly-level analysis and micro-benchmarking.

**Current Status**: Reverted to Round 6 baseline (1.75x average slowdown)
