---
### [ ] OPENMP-MACOS-CYTHON | 2026-03-05
- **Status**: [X] DISCARDED (macOS), [OK] ADOPTED (Linux)
- **Objective**: Auto-inject OpenMP flags so `-fopenmp` just works with zig cc
- **Hypothesis**: Injecting `-I{libomp}/include -L{libomp}/lib -lomp -Wl,-rpath` + rewriting `-fopenmp` → `-Xclang -fopenmp` on macOS would fix Cython prange builds
- **Approach**: Detect platform, find LLVM libomp, inject flags in `_inject_openmp()`
- **Result**:
    - Linux: WORKS. `libomp-dev` provides `/usr/lib/llvm-18/lib/clang/18/include/omp.h` (Clang-native, no GCC `__malloc__` attribute issues). `parallel_sum(100) = 4950`. Confirmed.
    - macOS: BROKEN. Extension builds and links `libomp.dylib` correctly, but Cython `prange` produces wrong results (`omp_get_max_threads()` returns garbage, parallel loop returns 0).
    - [Root cause]: zig cc with `-fopenmp` or `-Xclang -fopenmp` compiles Cython's `#pragma omp parallel` + `#pragma omp for` outlined regions without emitting `___kmpc_fork_call` or `_omp_get_max_threads` as undefined external symbols. The outlined functions are local (`t` in `nm`). libomp runtime never initializes.
    - [Contrast]: plain C `#pragma omp parallel for` with the same flags correctly emits `___kmpc_fork_call` as undefined. The bug is specific to Cython's outlined parallel region pattern with zig cc 0.15.x / Clang 20 on Apple Silicon.
    - [Outcome]: Discarded for macOS. Linux injection was working but reverted for consistency — ship as future work.
- **The Delta**: Linux fully solved; macOS has a zig cc codegen bug with Cython outlined regions
- **Next Step**: Revisit when zig upgrades Clang past 20; or test hybrid (Apple Clang compile + zig link).
---

---
### [OK] DROPPED-FLAGS-AUDIT | 2026-03-05
- **Status**: [OK] ADOPTED (documented in README)
- **Objective**: Verify actual side effects of each dropped flag
- **Hypothesis**: Drops are safe or have negligible consequences worth documenting
- **Approach**: Direct measurement — otool, nm -D, install_name_tool stress test, RTLD_GLOBAL conflict test
- **Result**:
    - `-Wl,-headerpad,0x40`: zig cc and Apple ld produce identical sizeofcmds=1576. Both fail at rpath #4. No difference.
    - `-Wl,--exclude-libs,ALL`: confirmed leaks static lib symbols to dynamic table. Conflict only fires with `RTLD_GLOBAL` — Python uses `RTLD_LOCAL` by default. Safe for normal use.
    - `-exported_symbols_list`: same visibility risk. Never observed in any real build (not in sysconfig for any Python, not in setuptools, greenlet, psutil, numpy, lxml, cffi, marimo-cython). Defensive drop only.
    - [Outcome]: All drops are safe for normal extension builds. Documented in README.
- **The Delta**: Replaced speculation with measured results
- **Next Step**: Proceed to publish.
---

---
### [OK] ZIG-BACKEND-CORE | 2026-03-05
- **Status**: [OK] ADOPTED
- **Objective**: Drop-in `CC=` wrapper making `zig cc` work for Python/Cython builds
- **Hypothesis**: Filtering ~8 unsupported flags is enough for real-world packages
- **Approach**: `_filter()` with prefix-drop + exact-drop + pair-drop + rewrite tables
- **Result**:
    - macOS arm64: Cython C/C++, NumPy, pybind11, cffi, greenlet, msgpack, psutil, regex, lxml, marimo-cython — all pass
    - Linux x86_64: same package list — all pass
    - [Outcome]: Success
- **The Delta**: Fixed `zigcc` (archived) bugs: `-x` wildcard, `-bundle` rewrite, all dropped flags
- **Next Step**: Publish to PyPI.
---
