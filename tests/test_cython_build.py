"""Integration test: build a minimal Cython extension with zig-cc as CC
and verify the compiled function returns the correct result.

Requires ziglang and Cython to be installed in the test environment.
Skipped if either is missing.
"""

import importlib.util
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _has_package(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def built_extension(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Build a minimal Cython extension using zig-backend as CC.

    Returns the directory containing the built .so/.pyd file.
    """
    build_dir = tmp_path_factory.mktemp("cython_build")

    # Write the .pyx source
    (build_dir / "math_ext.pyx").write_text(
        textwrap.dedent("""\
        # cython: language_level=3

        def add(int a, int b) -> int:
            return a + b

        def triangle(int n) -> int:
            \"\"\"Sum 0..n-1 using a typed loop.\"\"\"
            cdef int i, total = 0
            for i in range(n):
                total += i
            return total
    """)
    )

    # Write setup.py
    (build_dir / "setup.py").write_text(
        textwrap.dedent("""\
        from setuptools import setup, Extension
        from Cython.Build import cythonize
        setup(ext_modules=cythonize([Extension("math_ext", ["math_ext.pyx"])]))
    """)
    )

    # Resolve zig-cc entry point from the installed package
    from zig_cc.cc import _find_zig  # noqa: PLC0415

    _find_zig()  # raises if zig is not available — will be caught by the skip below

    zig_cc_exe = Path(sys.executable).parent / "zig-cc"
    if not zig_cc_exe.exists():
        # In editable installs the script may have a different path
        import shutil

        found = shutil.which("zig-cc")
        if found is None:
            pytest.skip("zig-cc entry point not found on PATH")
        zig_cc_exe = Path(found)

    env = os.environ.copy()
    env["CC"] = str(zig_cc_exe)

    result = subprocess.run(
        [sys.executable, "setup.py", "build_ext", "--inplace"],
        cwd=build_dir,
        env=env,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        pytest.fail(f"Cython build failed:\n{result.stdout}\n{result.stderr}")

    return build_dir


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _has_package("ziglang"),
    reason="ziglang not installed",
)
@pytest.mark.skipif(
    not _has_package("Cython"),
    reason="Cython not installed",
)
class TestCythonBuild:
    def test_add(self, built_extension: Path) -> None:
        sys.path.insert(0, str(built_extension))
        try:
            import math_ext  # type: ignore[import-not-found]

            assert math_ext.add(2, 3) == 5
            assert math_ext.add(-1, 1) == 0
        finally:
            sys.path.pop(0)

    def test_triangle(self, built_extension: Path) -> None:
        sys.path.insert(0, str(built_extension))
        try:
            import math_ext  # type: ignore[import-not-found]

            # 0+1+2+...+9 = 45
            assert math_ext.triangle(10) == 45
            assert math_ext.triangle(0) == 0
            assert math_ext.triangle(1) == 0
        finally:
            sys.path.pop(0)
