# zig-backend

`zig cc` backend for Python/Cython extension builds. Drop-in `CC=` replacement that actually works.

```bash
uv add --dev ziglang zig-backend
CC="zig-backend" uv run python setup.py build_ext --inplace
```

Works with setuptools, Cython, and marimo-cython. No system compiler required.

## Known limitations

**OpenMP is not supported.** `zig cc` does not bundle `omp.h` and does not link against `libomp`. Packages that require `-fopenmp` (scipy, scikit-learn internals) will fail at the compile step with `omp.h: file not found`. Use a system compiler for those.

## Why not zigcc?

[zigcc](https://pypi.org/project/zigcc/) is archived and has two bugs that break Python extension builds:

- **macOS**: `-bundle` is silently ignored by `zig ld`, producing a broken output. Rewritten to `-shared`.
- **Linux x86_64**: wildcard `-x` blacklist drops any argument containing `-x` as a substring — which includes every output path on x86_64 (`linux-x86_64`). Fixed with exact/prefix matching only.

`zig-backend` also resolves the `zig` binary directly from the `ziglang` PyPI package in your venv — no PATH setup, no symlinks, version-pinned by `uv.lock`.

## Usage

```bash
# Cython project
CC="zig-backend" uv run python setup.py build_ext --inplace

# marimo-cython
CC="zig-backend" uv run python your_notebook.py

# C++ extensions
CC="zig-backend" CXX="zig-backend-cxx" uv run python setup.py build_ext --inplace
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
| `-x` wildcard | Linux x86_64 | drops output paths containing `-x` | exact matching only |
