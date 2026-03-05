# zig-cc-python

`zig cc` as a drop-in `CC=` replacement for Python extension builds.

```bash
uv add --dev ziglang zig-cc-python
CC="zig-cc" uv run python setup.py build_ext --inplace
```

## What this is

This is not magic. It's a thin wrapper that drops or rewrites a handful of flags that `zig cc` doesn't support but Python's build system passes by default. The real work is in figuring out which flags those are — the code itself is trivial.

The whole point is building **Python C extensions** with `zig cc` instead of gcc or clang. That's the only use case it targets.

It uses the [`ziglang`](https://pypi.org/project/ziglang/) PyPI package as the compiler — not a system `zig` installation. The zig version is pinned in your `uv.lock`, the binary lives in your venv, nothing needs to be installed system-wide.

If you've decided to use this and hit a bug, open an issue or a PR.

## Not zigcc

There is a [`zigcc`](https://pypi.org/project/zigcc/) package on PyPI. It is archived and has bugs that break Python extension builds on Linux x86_64 and macOS. This is not that package.

## Usage

```bash
# C extension
CC="zig-cc" uv run python setup.py build_ext --inplace

# C++ extension
CC="zig-cc" CXX="zig-cc-cxx" uv run python setup.py build_ext --inplace

# python -m build
CC="zig-cc" uv run python -m build
```

## What it fixes

| Flag | Platform | Problem | Fix |
|---|---|---|---|
| `-bundle` | macOS | silently ignored by zig ld → broken output | rewrite to `-shared` |
| `-LModules/_hacl` | macOS/Linux | CPython sysconfig artifact → crashes zig | drop |
| `-Wl,-headerpad,N` | macOS | crashes zig 0.15.x | drop |
| `-Wl,-w` | macOS/Linux | unsupported linker arg | drop |
| `-Wl,--exclude-libs` | Linux | unsupported linker arg | drop |
| `-Wl,-Bsymbolic-functions` | Linux | unsupported linker arg (Ubuntu system Python) | drop |
| `-Wl,-Bsymbolic` | Linux | unsupported linker arg | drop |
| `-exported_symbols_list <file>` | macOS | unsupported Apple linker flag | drop (both tokens) |
| `-x` wildcard | Linux x86_64 | zigcc dropped output paths containing `-x` | exact matching only |

## Known limitations

**OpenMP (`-fopenmp`)** — partially supported. Linux works: install `libomp-dev` and pass `-I`/`-L`/`-lomp` flags manually. macOS does not work: zig cc 0.15.x / Clang 20 compiles Cython's outlined parallel regions without emitting the expected `___kmpc_fork_call` runtime calls, so `prange` loops silently return wrong results. Use a system compiler for OpenMP on macOS.

**Dropped flags have minor side effects.** zig-cc-python silently drops several flags that zig cc does not support. Verified consequences:

- `-Wl,-headerpad,0x40` — no effect in practice; zig cc and Apple ld produce identical header sizes.
- `-Wl,--exclude-libs,ALL` — static library symbols may leak into the extension's dynamic symbol table. This only causes conflicts if another extension is loaded with `RTLD_GLOBAL` and exports the same symbol. Python loads extensions with `RTLD_LOCAL` by default, so normal `import` is unaffected.
- `-exported_symbols_list` — same symbol visibility note as above. Not observed in any real build during testing.
