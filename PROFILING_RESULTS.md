# Profiling Results - ACTUAL Bottlenecks Found

**Date**: 2025-11-27
**Method**: perf + cargo-flamegraph
**Tests Profiled**: progressive, grayscale, noise

---

## 🔥 Progressive Test (2.95x slowdown) - 11MP Image

### Top Bottlenecks by CPU Time

| Function | % CPU | Samples | Category |
|----------|-------|---------|----------|
| **EPF0 (Edge-Preserving Filter 0)** | **37.10%** | 1.75B | **Rendering** |
| **EPF1 (Edge-Preserving Filter 1)** | **16.37%** | 772M | **Rendering** |
| **VarDCT group decode** | 15.75% | 743M | Decoding |
| **EPF2 (Edge-Preserving Filter 2)** | **6.70%** | 316M | **Rendering** |
| Dequant + Transform | 9.25% | 436M | Decoding |
| Transform to pixels | 6.30% | 297M | Decoding |

### Key Findings

1. **EPF (Edge-Preserving Filter) stages dominate**: **60.17% total CPU time**
   - EPF0: 37.10%
   - EPF1: 16.37%
   - EPF2: 6.70%
   - All three EPF stages ARE using SIMD (_dispatch functions visible)
   - **This is the ACTUAL bottleneck, NOT transfer functions!**

2. **Our failed optimizations targeted the WRONG functions**:
   - BT.709 ToLinear: NOT IN TOP 20 functions! (<1% CPU)
   - Grayscale XYB: Only 19.42% in grayscale test
   - We optimized functions that barely show up in profiles

3. **Rendering pipeline is 65.56% of total time**
   - \`run_stage_on\`: 65.56%
   - Dominated by EPF filtering stages

---

## 🔥 Grayscale Test (2.23x slowdown) - 200x200 Image

### Top Bottlenecks by CPU Time

| Function | % CPU | Samples | Category |
|----------|-------|---------|----------|
| **XYB to RGB conversion** | **19.42%** | 2.66M | **Rendering** |
| **Save stage (memcpy)** | 20.34% | 2.78M | I/O |
| HF global decode | 31.33% | 4.28M | Decoding |
| Render pipeline | 39.76% | 5.44M | Rendering |

### Key Findings

1. **XYB Stage IS a bottleneck (19.42%)**
   - BUT it's using \`jxl_simd::scalar::load\` - **SIMD NOT BEING USED!**
   - The SIMD version exists but scalar path is being taken
   - This is a **SIMD dispatch issue**, not a missing SIMD implementation

2. **Save stage memcpy: 20.34%**
   - This is just copying final output
   - Can't really optimize this - it's fundamental I/O

3. **Small image characteristics**:
   - Different bottlenecks than large progressive image
   - Less EPF filtering, more overhead

---

## 💡 Critical Discovery: Why Our Optimizations Failed

### What We Thought Was Slow (WRONG):
- ❌ BT.709 transfer function
- ❌ Grayscale XYB "redundant computation"
- ❌ AddNoiseStage

### What's ACTUALLY Slow (PROFILING DATA):
1. ✅ **EPF0/EPF1/EPF2 stages** (60% of progressive test)
2. ✅ **XYB stage using SCALAR instead of SIMD** (19% of grayscale)
3. ✅ **VarDCT group decode** (16% of progressive)

---

## 📊 Profile-Guided Optimization Targets

### Priority 1: EPF Stages (Progressive Test)

**Finding**: EPF0 (37%), EPF1 (16%), EPF2 (6.7%) = 60% total
**Files**:
- \`jxl-rs/jxl/src/render/stages/epf/epf0.rs\`
- \`jxl-rs/jxl/src/render/stages/epf/epf1.rs\`
- \`jxl-rs/jxl/src/render/stages/epf/epf2.rs\`

**Status**: SIMD implementations exist (\`_dispatch\` functions are being called)

**Investigation needed**:
- Why is EPF so slow despite having SIMD?
- Compare with C++ libjxl EPF implementation
- Check if SIMD is actually being dispatched correctly
- Profile EPF internals to find sub-bottlenecks

**Expected Impact**: If we can make EPF 2x faster → 30% overall speedup on progressive

---

### Priority 2: XYB Scalar Path (Grayscale Test)

**Finding**: XYB using \`jxl_simd::scalar::load\` (19.42% of grayscale)
**File**: \`jxl-rs/jxl/src/render/stages/xyb.rs\`

**Problem**: SIMD version exists but scalar path is being taken

**Investigation needed**:
- Check \`xyb_process_dispatch\` function
- Why is it choosing scalar over SIMD?
- Is this a grayscale-specific path?
- Check SIMD feature detection

**Expected Impact**: 2x faster XYB → 10% overall speedup on grayscale

---

### Priority 3: VarDCT Group Decode (Progressive Test)

**Finding**: 15.75% CPU time in \`decode_vardct_group\`
**File**: \`jxl-rs/jxl/src/frame/group.rs\`

**Investigation needed**:
- Profile inside this function
- Compare with C++ implementation
- Check if SIMD is being used for DCT

**Expected Impact**: Uncertain without deeper profiling

---

## 🚫 What NOT To Optimize (Low Impact)

Based on profiling data, these are NOT worth optimizing:

1. **BT.709 transfer function**: <1% CPU time
2. **AddNoiseStage**: Not in top 20 functions
3. **BlendingStage allocation**: Not in top 20 functions
4. **SpotColorStage**: Not in top 20 functions

**Our speculation was completely wrong. Trust the profiler!**

---

## 📁 Flamegraph Files

Generated flamegraphs (viewable in browser):
- \`progressive_flamegraph.svg\` - 11MP progressive image
- \`grayscale_flamegraph.svg\` - 200x200 grayscale image
- \`noise_flamegraph.svg\` - Noise synthesis test

**View with**: \`firefox *.svg\` or any SVG viewer
