"""zig-cc-python: zig cc wrapper for Python/Cython extension builds.

Resolves the zig binary from the ziglang PyPI package in the active venv
and applies the minimal set of flag filters and rewrites needed to make
real Python build systems (setuptools, Cython) work correctly
on macOS and Linux.

Known issues fixed vs raw `zig cc` / archived `zigcc`:

macOS:
  - `-bundle` silently ignored by zig ld → rewrite to `-shared`
  - `-LModules/_hacl` (CPython sysconfig artifact) → crashes zig → drop
  - `-Wl,-headerpad,N` → crashes zig 0.15.x → drop
  - `-Wl,-w` (marimo-cython suppresses linker warnings) → unsupported → drop

Linux:
  - zigcc wildcard `-x` blacklist drops any arg containing `-x` as substring,
    which includes every output path on x86_64 (`linux-x86_64`). Fixed here
    by only matching `-x` as an exact token or a proper flag prefix.

Usage:
    uv add ziglang zig-cc-python
    CC="zig-cc" uv run python setup.py build_ext --inplace
    CC="zig-cc" uv run python -m build
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Flag filter tables
# ---------------------------------------------------------------------------

# Drop these flags entirely.
# Matched as exact token OR prefix (e.g. "-LModules/" matches "-LModules/_hacl").
# IMPORTANT: entries must be specific enough not to match unrelated args.
# Do NOT add short flags like "-x" here — use _EXACT_DROPS for those.
_PREFIX_DROPS: tuple[str, ...] = (
    # CPython sysconfig artifact: relative -L path baked into uv-managed Python builds.
    "-LModules/",
    # macOS: crashes zig 0.15.x linker.
    "-Wl,-headerpad",
    # macOS: unsupported linker args.
    "-Wl,-dylib",
    "-Wl,-no_pie",
    "-Wl,-pie",
    # marimo-cython adds this to suppress linker warnings; zig cc rejects it.
    "-Wl,-w",
    # Linux: tells the linker not to re-export symbols from static libs.
    # zig cc linker does not support this flag.
    "-Wl,--exclude-libs",
    # Linux: makes function calls within the DSO go directly to the local
    # definition, bypassing the PLT. zig ld does not support this.
    "-Wl,-Bsymbolic-functions",
    "-Wl,-Bsymbolic",
)

# Drop these as exact token matches only (no substring/prefix matching).
# Use this for short flags that would cause false positives as prefixes (e.g. "-x").
_EXACT_DROPS: frozenset[str] = frozenset()

# Two-token drops: drop this flag AND the token immediately following it.
_PAIR_DROPS: frozenset[str] = frozenset(
    {
        # GNU-style --target; zig uses -target instead.
        "--target",
        # Apple linker flag: restricts exported symbols to a list file.
        # zig ld has no equivalent; the filename argument must also be dropped.
        "-exported_symbols_list",
    }
)

# Exact token rewrites: replace flag with zig cc equivalent.
_REWRITES: dict[str, str] = {
    # macOS: zig ld silently ignores -bundle and defaults to executable linking.
    # -shared produces a dylib which Python can dlopen just as well.
    "-bundle": "-shared",
}


# ---------------------------------------------------------------------------
# Zig binary resolution
# ---------------------------------------------------------------------------


def _find_zig() -> Path:
    """Find the zig binary from the ziglang package in the active venv.

    Prefers venv-local ziglang so the compiler version is pinned by uv.lock.
    Falls back to PATH so the tool still works if zig is installed system-wide.

    Raises RuntimeError if zig cannot be found anywhere.
    """
    # Prefer ziglang from the active venv — fully self-contained, version-pinned.
    try:
        import ziglang

        pkg_file: str | None = ziglang.__file__
        if pkg_file is not None:
            candidate = Path(pkg_file).parent / "zig"
            if candidate.exists():
                return candidate
    except ImportError:
        pass

    # Fall back to PATH (system zig or manually installed).
    zig_on_path = shutil.which("zig")
    if zig_on_path:
        return Path(zig_on_path)

    raise RuntimeError(
        "zig not found. Install ziglang into your project:\n\n    uv add ziglang\n"
    )


# ---------------------------------------------------------------------------
# Argument filtering
# ---------------------------------------------------------------------------


def _filter(args: list[str]) -> list[str]:
    """Apply drops and rewrites to the argument list."""
    result: list[str] = []
    skip_next = False

    for arg in args:
        if skip_next:
            skip_next = False
            continue

        # Two-token drop
        if arg in _PAIR_DROPS:
            skip_next = True
            continue

        # Exact drop
        if arg in _EXACT_DROPS:
            continue

        # Prefix drop
        if any(arg == p or arg.startswith(p) for p in _PREFIX_DROPS):
            continue

        # Rewrite
        result.append(_REWRITES.get(arg, arg))

    return result


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------


def _run(subcommand: str) -> None:
    zig = _find_zig()
    filtered = _filter(sys.argv[1:])
    # argv[0] must be the program name by POSIX convention — zig itself uses it.
    cmd = [str(zig), subcommand, *filtered]

    if os.name == "posix":
        os.execv(str(zig), cmd)
    else:
        import subprocess

        sys.exit(subprocess.call(cmd))


def main_cc() -> None:
    """Entry point for `zig-backend` and `zig-backend-cc`."""
    _run("cc")


def main_cxx() -> None:
    """Entry point for `zig-backend-c++` and `zig-backend-cxx`."""
    _run("c++")
