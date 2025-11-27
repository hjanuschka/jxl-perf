# Next Steps: How to Actually Reach 1.0x Performance

**Current Status**: 1.75x average slowdown (Round 6)
**Goal**: 1.0x (performance parity with C++)
**Gap**: Need to eliminate 75% of the performance difference

---

## Why We're NOT Doomed

### The Evidence for Hope

**EPF is 3x slower in absolute time:**
```
C++ EPF:  258ms (60% of 430ms total)
Rust EPF: 768ms (60% of 1280ms total)
Ratio: 3.0x slower
```

This means:
1. ✅ **There IS a real performance gap** - not just measurement error
2. ✅ **The gap is measurable and specific** - EPF is the bottleneck
3. ✅ **If we fix EPF, we get massive gains** - potentially 2-3x speedup!

### Why Previous Attempts Failed

**Rounds 7, 8, 9 all failed because**:
- ❌ We guessed at the problem (speculation)
- ❌ We optimized the wrong thing (algorithm vs codegen)
- ❌ We trusted our intuition over data

**What we need instead**:
- ✅ Assembly-level analysis
- ✅ Instruction-level profiling
- ✅ Micro-benchmarks
- ✅ Systematic hypothesis testing

---

## The Real Bottleneck

### It's Not The Algorithm

Both C++ and Rust:
- Use similar EPF algorithms ✅
- Have SIMD implementations ✅
- Spend ~60% of time in EPF ✅

**So what's different?**

### Hypothesis: SIMD Code Generation

**Possible causes of 3x slowdown:**

1. **jxl_simd wrapper overhead**
   - Rust abstracts SIMD through jxl_simd crate
   - C++ uses Highway directly
   - Extra abstraction layer may add overhead

2. **Suboptimal SIMD instruction selection**
   - LLVM may not generate optimal AVX2/AVX-512 instructions
   - Rust SIMD intrinsics may map poorly to x86 instructions
   - Missing optimizations that Clang/GCC apply

3. **Memory access patterns**
   - Unaligned loads may be slower
   - Cache line splits
   - Prefetching differences

4. **Register allocation**
   - LLVM may spill registers to stack
   - C++ may keep more in registers
   - Different register allocation heuristics

---

## Path Forward: Data-Driven Optimization

### Phase 1: Understand the Problem (Required!)

**Before attempting ANY optimization, we MUST:**

#### 1.1: Compare Generated Assembly

**Tools needed**:
- `cargo asm` - view Rust assembly
- `objdump` - view C++ assembly
- `perf annotate` - see which instructions are slow

**What to look for**:
```bash
# Rust EPF0 assembly
cd /home/chrome/jxl-perf
cargo asm -p jxl --lib jxl::render::stages::epf::epf0 > rust_epf0.asm

# C++ EPF0 assembly
objdump -d /tmp/libjxl/build/lib/libjxl.so | grep -A 500 "EPF0" > cpp_epf0.asm

# Compare instruction counts
grep "vfmadd" rust_epf0.asm | wc -l  # Should see FMA instructions
grep "vmov" rust_epf0.asm | wc -l    # Check for excessive moves
```

**Key questions**:
- Are we using AVX2 instructions? (vmov, vfmadd, etc.)
- How many memory loads per SAD computation?
- Are there register spills? (look for stack operations)
- Are loads aligned? (vmovaps vs vmovups)

#### 1.2: Instruction-Level Profiling

**Use perf to see which instructions are slow**:
```bash
# Record with detailed samples
perf record -e cycles:pp --call-graph dwarf ./target/release/test_decode_rs progressive.jxl

# Annotate specific function
perf annotate --stdio epf0_process_row_chunk_simd

# Look for:
# - High cycle counts on specific instructions
# - Cache misses (perf stat -e cache-misses)
# - Branch mispredictions
```

#### 1.3: Micro-Benchmark SIMD Primitives

**Test individual SIMD operations**:
```rust
// Create micro-benchmark crate
// benches/simd_primitives.rs

use criterion::{black_box, criterion_group, criterion_main, Criterion};
use jxl_simd::*;

fn bench_f32_load(c: &mut Criterion) {
    let data = vec![1.0f32; 1024];
    c.bench_function("F32Vec::load", |b| {
        b.iter(|| {
            for i in (0..1000).step_by(8) {
                let v = F32Vec::load(&data[i..]);
                black_box(v);
            }
        });
    });
}

fn bench_f32_abs(c: &mut Criterion) {
    let data = vec![-1.0f32; 1024];
    c.bench_function("F32Vec::abs", |b| {
        b.iter(|| {
            for i in (0..1000).step_by(8) {
                let v = F32Vec::load(&data[i..]);
                let a = v.abs();
                black_box(a);
            }
        });
    });
}

criterion_group!(benches, bench_f32_load, bench_f32_abs);
criterion_main!(benches);
```

**Compare with C++ Highway**:
```cpp
// Same benchmarks in C++ using Highway
// Measure actual instruction throughput
```

---

### Phase 2: Targeted Fixes (Only After Phase 1!)

**Based on findings from Phase 1, try ONE of these**:

#### Option A: If SIMD Wrapper Has Overhead

**Symptom**: Extra function calls in assembly, wrapper functions
**Fix**: Use direct SIMD intrinsics

```rust
// Instead of:
let v = D::F32Vec::load(d, &data[x..]);

// Try:
#[cfg(target_arch = "x86_64")]
use std::arch::x86_64::*;
let v = unsafe { _mm256_loadu_ps(data[x..].as_ptr()) };
```

**Risk**: Low - can easily A/B test
**Expected gain**: 5-15% if wrapper has overhead

#### Option B: If Memory Access Is Problem

**Symptom**: High cache miss rate, many memory stalls
**Fix**: Prefetch, alignment, blocking

```rust
// Add prefetching
use std::intrinsics::prefetch_read_data;
unsafe {
    prefetch_read_data(input_c[row][col..].as_ptr(), 3);
}

// Or ensure alignment
#[repr(align(32))]
struct AlignedBuffer {
    data: [f32; 1024],
}
```

**Risk**: Medium - can affect correctness
**Expected gain**: 10-30% if memory-bound

#### Option C: If Register Pressure Is Problem

**Symptom**: Stack spills visible in assembly (mov to [rsp+offset])
**Fix**: Reduce live values, add inline hints

```rust
// Break computation into smaller chunks
#[inline(never)]  // Force separate function
fn compute_sad_batch(/* ... */) {
    // Compute 4 SADs at a time instead of 12
}

// Or use explicit drops
{
    let temp = expensive_computation();
    use_temp(temp);
}  // temp dropped here, frees registers
```

**Risk**: Medium - may affect optimization
**Expected gain**: 5-20% if register-constrained

#### Option D: If LLVM Misoptimizes

**Symptom**: Suboptimal instruction selection in assembly
**Fix**: Use target-specific features, compiler flags

```toml
# Cargo.toml
[profile.release]
opt-level = 3
lto = "fat"
codegen-units = 1
[target.'cfg(target_arch = "x86_64")']
rustflags = ["-C", "target-cpu=native", "-C", "target-feature=+avx2,+fma"]
```

**Risk**: Low - just compiler flags
**Expected gain**: 10-40% if LLVM was conservative

---

### Phase 3: Validation

**After ANY change**:

1. **Run micro-benchmark** - verify primitive is faster
2. **Run single test** - check progressive.jxl time
3. **Run full suite** - ensure no regressions
4. **Check correctness** - pixel-perfect output

**Success criteria**:
- ✅ Average slowdown < 1.60x (15% improvement)
- ✅ Progressive < 2.50x (15% improvement)
- ✅ No test regresses by >5%
- ✅ All 30 tests still pass

---

## Realistic Timeline

### Conservative Estimate

**Phase 1** (Understanding): 4-8 hours
- Assembly comparison: 2h
- Instruction profiling: 2h
- Micro-benchmarks: 2-4h

**Phase 2** (Fix attempt): 2-6 hours per attempt
- Implement fix: 1-2h
- Test and measure: 1-2h
- Debug if broken: 0-2h

**Phase 3** (Validation): 1-2 hours
- Full benchmark suite: 30min
- Correctness checks: 30min
- Documentation: 30min

**Total: 7-16 hours** for one complete cycle

### Optimistic Path to 1.0x

If we're lucky and find a simple fix:
- **Best case**: One good optimization = 2.0x speedup → **0.85x** (beating C++!)
- **Likely case**: 2-3 optimizations = 1.5x speedup → **1.15x** (close!)
- **Worst case**: No silver bullet, need many small wins → stay at 1.75x

---

## Alternative Approaches

If assembly analysis doesn't reveal obvious issues:

### Approach 1: Profile-Guided Optimization (PGO)

Let the compiler optimize based on actual workload:
```bash
# Step 1: Build with instrumentation
RUSTFLAGS="-Cprofile-generate=/tmp/pgo-data" cargo build --release

# Step 2: Run representative workload
./target/release/test_decode_rs progressive.jxl

# Step 3: Rebuild with profile data
RUSTFLAGS="-Cprofile-use=/tmp/pgo-data" cargo build --release
```

**Expected gain**: 5-15%

### Approach 2: Try Different SIMD Library

jxl_simd might not be optimal. Try:
- `std::simd` (portable_simd)
- `packed_simd`
- Direct intrinsics

**Expected gain**: Unknown, could be 0-50%

### Approach 3: Rewrite EPF in C++

Nuclear option: Keep Rust for most code, call C++ for EPF:
```rust
extern "C" {
    fn epf0_cpp(/* ... */);
}
```

**Expected gain**: 3x speedup on EPF = 1.2x overall
**Risk**: HIGH - FFI overhead, maintenance burden

---

## Recommendation

**START WITH PHASE 1 - UNDERSTAND THE PROBLEM**

Do NOT attempt more optimizations until we have:
1. ✅ Assembly comparison showing actual differences
2. ✅ Instruction-level profiling showing hot instructions
3. ✅ Micro-benchmarks quantifying SIMD primitive performance

Only then can we make an informed decision about what to optimize.

**After 3 failures, speculation has proven to be completely ineffective. We MUST use data.**

---

## Success Metrics

**Minimum viable improvement**: 1.60x average (15% faster)
**Stretch goal**: 1.40x average (25% faster)
**Dream scenario**: 1.0x average (parity!)

Even small improvements compound:
- 15% improvement × 4 rounds = 2.0x speedup total
- That would bring us from 1.75x → **0.85x (faster than C++!)**

**We're not doomed. We just need to be systematic.**
