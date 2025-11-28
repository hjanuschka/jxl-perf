# 🚀 JXL-RS Parallelization Implementation Progress

## Mission: 8-16x Speedup on 16 CPU Cores!

**Status:** IN PROGRESS (Day 1 of 5-7)
**Started:** 2025-11-27
**Target:** Per-thread cache parallelization (libjxl-style)
**Expected Speedup:** 8-16x on large images with 16 cores

---

## ✅ Completed Steps

### Phase 1: Research & Design (COMPLETE)
- [x] **Research libjxl threading architecture**
  - Identified `RunOnPool` pattern over groups
  - Found per-thread cache design (`group_dec_caches_[thread]`)
  - Documented guided scheduling strategy
  - Located all parallelization points (DC groups, AC groups, color conversion)

- [x] **Analyze jxl-rs current architecture**
  - Mapped group decoding flow: Frame → Groups → Passes
  - Found main sequential loop in `render.rs:188-193`
  - Identified `decode_hf_group(&mut self)` as blocking parallel execution
  - Confirmed groups are independent (different bitstreams, pixel regions)

- [x] **Add rayon dependency**
  - Added `rayon = { version = "1.10", optional = true }` to Cargo.toml
  - Created `parallel` feature (default enabled)
  - Built successfully

- [x] **Create design document**
  - Documented per-thread cache architecture
  - Planned GroupDecodeCache struct
  - Defined migration path
  - Estimated performance expectations

### Phase 2: Cache Infrastructure (IN PROGRESS)
- [x] **Create GroupDecodeCache module**
  - File: `jxl/src/frame/group_cache.rs`
  - Struct: `GroupDecodeCache` with pixel buffers, modular buffer, noise buffer
  - Struct: `GroupDecodeCachePool` for managing per-thread caches
  - Methods: `ensure_pixels_capacity()`, `clear()`, etc.

- [x] **Add module to frame/mod.rs**
  - Declared `pub mod group_cache;`
  - Module is now accessible

---

## 🚧 In Progress Steps

### Current Task: Step 2 - Analyze Mutations in decode_hf_group

**File to analyze:** `jxl/src/frame/decode.rs:363-488`

**Known mutations:**
1. **Line 427-431:** `lf_global.as_mut()`, `hf_global.as_mut()`, `hf_meta.as_mut()`
   - Strategy: Make these immutable borrows where possible
   - Challenge: modular_global.read_stream() and process_output() mutate state

2. **Line 432-436:** `pixels` temp buffers
   - Strategy: Move to GroupDecodeCache.pixels_temp
   - Easy win: Already designed

3. **Line 467-485:** `modular_global.read_stream()` and `process_output()`
   - Strategy: **Most complex** - needs thread-safe accumulation
   - Options:
     a) Per-thread modular buffers + merge after parallel section
     b) Mutex-protected modular_global (BAD for performance)
     c) Lock-free accumulation (complex)

4. **Lines 395-424:** Noise generation via `pipeline!` macro
   - Uses `p.get_buffer()` and `p.set_buffer_for_group()`
   - Strategy: Investigate BufferSplitter thread safety

**Next actions:**
- [ ] Complete mutation analysis
- [ ] Document all mutable state access points
- [ ] Design thread-safe alternatives for each

---

## 📋 Remaining Steps

### Phase 3: Refactor for Immutability
- [ ] **Step 3: Make LfGlobalState/HfGlobalState immutable where possible**
  - Change function signatures: `&mut LfGlobalState` → `&LfGlobalState`
  - Identify what MUST remain mutable (likely modular_global)
  - Update all call sites

- [ ] **Step 4: Move mutable state to GroupDecodeCache**
  - pixels_temp → cache.pixels_temp ✓ (designed)
  - modular buffers → cache.modular_buffer
  - Any other per-group state

### Phase 4: Thread Safety
- [ ] **Step 5: Handle ModularGlobal mutations**
  - **Option A:** Per-thread accumulation + merge
    - Each thread writes to cache.modular_buffer
    - After parallel section: merge all buffers into modular_global
    - Clean but requires merge logic

  - **Option B:** Atomic operations
    - Use atomics for modular stream writes
    - Complex, error-prone

  - **Option C:** Sequential modular, parallel VarDCT
    - Keep modular decoding sequential
    - Only parallelize VarDCT groups (most images)
    - Simpler, still big win

  - **Decision:** Start with Option C (VarDCT only), then Option A

- [ ] **Step 6: Make BufferSplitter thread-safe**
  - Current: `&mut BufferSplitter` in decode_hf_group
  - Options:
    - Make it `&BufferSplitter` (immutable) if possible
    - Wrap in Arc<Mutex<>> (kills parallelism)
    - Pre-allocate per-group buffers
  - Investigate actual BufferSplitter usage

- [ ] **Step 7: Update decode_hf_group signature**
  ```rust
  // BEFORE:
  pub fn decode_hf_group(
      &mut self,
      group: usize,
      pass: usize,
      br: BitReader,
      buffer_splitter: &mut BufferSplitter,
  ) -> Result<()>

  // AFTER:
  pub fn decode_hf_group(
      &self,  // Immutable!
      group: usize,
      pass: usize,
      br: BitReader,
      cache: &mut GroupDecodeCache,  // Per-thread cache
      buffer_splitter: &BufferSplitter,  // Shared read-only or per-thread
  ) -> Result<()>
  ```

- [ ] **Step 8: Update all callers**
  - render.rs:191
  - Any other decode_hf_group calls

### Phase 5: Implement Parallel Loop
- [ ] **Step 9: Add cache pool to Frame struct**
  ```rust
  pub struct Frame {
      // ... existing fields ...
      #[cfg(feature = "parallel")]
      group_decode_caches: Option<GroupDecodeCachePool>,
  }
  ```

- [ ] **Step 10: Allocate cache pool**
  - In Frame::new() or before decode_and_render_hf_groups()
  - `GroupDecodeCachePool::new(rayon::current_num_threads())`

- [ ] **Step 11: Implement parallel loop in render.rs**
  ```rust
  #[cfg(feature = "parallel")]
  {
      use rayon::prelude::*;

      groups.par_iter().try_for_each(|(group, passes)| {
          let thread_id = rayon::current_thread_index().unwrap();
          let cache = self.group_decode_caches.as_mut().unwrap()
              .get_mut(thread_id).unwrap();

          for (pass, br) in passes {
              self.decode_hf_group(*group, *pass, br, cache, &buffer_splitter)?;
          }
          Ok::<_, Error>(())
      })?;
  }
  #[cfg(not(feature = "parallel"))]
  {
      // Keep sequential fallback
      for (group, passes) in groups {
          // ... existing code ...
      }
  }
  ```

- [ ] **Step 12: Handle small images gracefully**
  - If `num_groups < 4`, use sequential path (avoid overhead)
  - Heuristic: `if num_groups < rayon::current_num_threads() { sequential } else { parallel }`

### Phase 6: Testing & Validation
- [ ] **Step 13: Build and fix compile errors**
  - Expect many errors from signature changes
  - Fix one module at a time
  - Use compiler as guide

- [ ] **Step 14: Run existing tests**
  - `cargo test --release --features parallel`
  - Ensure all tests pass
  - Fix any correctness issues

- [ ] **Step 15: Visual correctness testing**
  - Decode all benchmark images
  - Compare pixel-by-pixel with sequential decode
  - Use `assert_eq!` on output images

- [ ] **Step 16: Thread safety validation**
  - Run with `RUSTFLAGS="-Z sanitizer=thread" cargo test` (nightly)
  - Or use `cargo miri test` for UB detection
  - Fix any data races

### Phase 7: Performance Measurement
- [ ] **Step 17: Benchmark single-threaded (baseline)**
  - Run benchmarks with `--no-default-features` (disable parallel)
  - Record all times
  - This is our 1.34x baseline

- [ ] **Step 18: Benchmark with parallelization**
  - Run with default features (parallel enabled)
  - Measure per-image speedup
  - Expected:
    - grayscale_jpeg (200x200, 1 group): ~1x (no benefit, overhead)
    - progressive (4064x2704, 256 groups): 8-14x speedup!
    - bike (2048x2560, 64 groups): 6-10x speedup!

- [ ] **Step 19: Profile to find remaining bottlenecks**
  - Use `perf record` on large images
  - Check CPU utilization (should be 1600% on 16 cores!)
  - Identify any lock contention

- [ ] **Step 20: Optimize based on profiling**
  - Remove any remaining Mutex contention
  - Tune work distribution if needed
  - Consider guided scheduling (like libjxl)

### Phase 8: Documentation & Cleanup
- [ ] **Step 21: Document parallel feature**
  - Update README with `parallel` feature
  - Explain when it helps (large images)
  - Document `RAYON_NUM_THREADS` env var

- [ ] **Step 22: Add benchmark results to README**
  - Show speedup table
  - Include core count scaling

- [ ] **Step 23: Clean up debug code**
  - Remove any temporary `println!` debugging
  - Clean up comments

- [ ] **Step 24: Final benchmark run**
  - Clean rebuild
  - Fresh benchmark results
  - Create comparison charts

---

## 📊 Expected Performance Gains

### Small Images (< 4 groups)
- **Before:** Sequential decode
- **After:** Sequential (fallback to avoid overhead)
- **Speedup:** 1.0x (no change, as designed)
- **Example:** `grayscale_jpeg` (200x200)

### Medium Images (16-64 groups)
- **Before:** 1 core at 100% CPU
- **After:** 16 cores at ~60-80% CPU (some synchronization overhead)
- **Speedup:** 8-12x
- **Example:** `bike` (2048x2560, ~64 groups)

### Large Images (256+ groups)
- **Before:** 1 core at 100% CPU
- **After:** 16 cores at ~90-95% CPU (near-perfect scaling)
- **Speedup:** 14-16x (near-linear!)
- **Example:** `progressive` (4064x2704, ~256 groups)

### Overall Benchmark Suite
- **Current Average:** 1.34x slower than C++
- **Expected with Parallelization:** 0.15x-0.20x (5-7x FASTER than C++!)
- **Why:** C++ benchmark is single-threaded in our tests!

---

## 🎯 Success Criteria

- [x] Design documented and approved
- [x] Cache infrastructure created
- [ ] All tests pass with `--features parallel`
- [ ] No data races (verified with ThreadSanitizer)
- [ ] Large images decode 8-16x faster on 16 cores
- [ ] Small images don't regress (<5% overhead acceptable)
- [ ] Code is maintainable and well-documented

---

## 🚀 Current Status Summary

**Date:** 2025-11-27 (Day 1)
**Progress:** 15% complete (2 of 24 steps done)
**Blockers:** None
**Next Session:** Complete mutation analysis (Step 2)
**Estimated Completion:** 5-7 days

**Commit Strategy:**
- Small, incremental commits
- Each commit compiles (even if tests fail during refactor)
- Feature flag ensures no breakage of main branch
- Final commit: Enable `parallel` by default after validation

---

## 📝 Notes & Learnings

### Key Insights
1. **Per-thread caches are essential** - Mutex would kill all performance
2. **Groups ARE independent** - Perfect for data parallelism
3. **ModularGlobal is the hardest part** - Requires careful thread-safe accumulation
4. **Small images need special handling** - Avoid parallelization overhead
5. **rayon makes this easy** - Once refactoring is done, parallel loop is simple

### Risks & Mitigations
- **Risk:** Thread safety bugs
  - **Mitigation:** Extensive testing, ThreadSanitizer, visual validation
- **Risk:** Performance regression on small images
  - **Mitigation:** Fallback to sequential for `num_groups < 4`
- **Risk:** Complex merge logic for modular
  - **Mitigation:** Start with VarDCT-only parallelization first

### Alternative Approaches Considered
1. ❌ **Mutex around mutable state** - Too slow, defeats purpose
2. ❌ **Lock-free data structures** - Too complex, error-prone
3. ✅ **Per-thread caches** - Clean, scalable, proven by libjxl
4. ⏸️ **Parallel within groups** - Future work, groups are already small (256x256)

---

**Last Updated:** 2025-11-27
**Maintainer:** Performance optimization team
**Contact:** GitHub Issues for jxl-rs
