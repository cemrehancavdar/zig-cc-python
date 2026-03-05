"""Tests for zig_cc.cc._filter().

Covers every entry in _PREFIX_DROPS, _EXACT_DROPS, _PAIR_DROPS, and _REWRITES
plus passthrough behaviour for unrecognised flags.
"""

from zig_cc.cc import _filter


# ---------------------------------------------------------------------------
# Passthrough — unknown flags must never be dropped or rewritten
# ---------------------------------------------------------------------------


def test_passthrough_compile_flags() -> None:
    args = ["-O3", "-fPIC", "-Wall", "-c", "foo.c", "-o", "foo.o"]
    assert _filter(args) == args


def test_passthrough_include_and_lib() -> None:
    args = ["-I/usr/include", "-L/usr/lib", "-lpython3.12"]
    assert _filter(args) == args


def test_passthrough_output_path_containing_x86_64() -> None:
    # Regression: zigcc wildcard dropped paths containing "-x" as substring.
    # "linux-x86_64" contains "-x" — must not be dropped.
    args = [
        "-o",
        "build/temp.linux-x86_64-cpython-314/fast_math.o",
        "-c",
        "fast_math.c",
    ]
    assert _filter(args) == args


# ---------------------------------------------------------------------------
# Prefix drops
# ---------------------------------------------------------------------------


def test_drop_LModules() -> None:
    assert _filter(["-LModules/_hacl"]) == []


def test_drop_headerpad_exact() -> None:
    assert _filter(["-Wl,-headerpad,40"]) == []


def test_drop_headerpad_variant() -> None:
    assert _filter(["-Wl,-headerpad_max_install_names"]) == []


def test_drop_Wl_w() -> None:
    assert _filter(["-Wl,-w"]) == []


def test_drop_exclude_libs() -> None:
    assert _filter(["-Wl,--exclude-libs,ALL"]) == []


def test_drop_Bsymbolic_functions() -> None:
    assert _filter(["-Wl,-Bsymbolic-functions"]) == []


def test_drop_Bsymbolic() -> None:
    assert _filter(["-Wl,-Bsymbolic"]) == []


def test_drop_exported_symbols_list() -> None:
    # Pair drop: the flag and its filename argument are both dropped.
    assert _filter(["-exported_symbols_list", "/path/to/exports.txt"]) == []


def test_drop_Wl_dylib() -> None:
    assert _filter(["-Wl,-dylib"]) == []


def test_drop_Wl_no_pie() -> None:
    assert _filter(["-Wl,-no_pie"]) == []


def test_drop_Wl_pie() -> None:
    assert _filter(["-Wl,-pie"]) == []


# ---------------------------------------------------------------------------
# Pair drops
# ---------------------------------------------------------------------------


def test_pair_drop_target_drops_value() -> None:
    assert _filter(["--target", "x86_64-linux-gnu"]) == []


def test_pair_drop_target_preserves_surrounding() -> None:
    args = ["-O2", "--target", "x86_64-linux-gnu", "-fPIC"]
    assert _filter(args) == ["-O2", "-fPIC"]


# ---------------------------------------------------------------------------
# Rewrites
# ---------------------------------------------------------------------------


def test_rewrite_bundle_to_shared() -> None:
    assert _filter(["-bundle"]) == ["-shared"]


def test_rewrite_bundle_preserves_surrounding() -> None:
    args = ["-undefined", "dynamic_lookup", "-bundle", "-arch", "arm64"]
    assert _filter(args) == [
        "-undefined",
        "dynamic_lookup",
        "-shared",
        "-arch",
        "arm64",
    ]


# ---------------------------------------------------------------------------
# Mixed real-world invocations
# ---------------------------------------------------------------------------


def test_macos_link_invocation() -> None:
    """Simulate a typical macOS setuptools link command."""
    args = [
        "-bundle",
        "-undefined",
        "dynamic_lookup",
        "-arch",
        "arm64",
        "-mmacosx-version-min=11.0",
        "-LModules/_hacl",
        "-Wl,-headerpad,40",
        "build/temp.macosx-11.0-arm64-cpython-314/fast.o",
        "-L/some/python/lib",
        "-o",
        "fast.cpython-314-darwin.so",
    ]
    result = _filter(args)
    assert "-shared" in result
    assert "-bundle" not in result
    assert not any(a.startswith("-LModules/") for a in result)
    assert not any(a.startswith("-Wl,-headerpad") for a in result)
    assert "build/temp.macosx-11.0-arm64-cpython-314/fast.o" in result


def test_linux_link_invocation() -> None:
    """Simulate a typical Linux setuptools link command."""
    args = [
        "-shared",
        "-Wl,--exclude-libs,ALL",
        "-LModules/_hacl",
        "-Wl,-Bsymbolic-functions",
        "build/temp.linux-x86_64-cpython-314/fast.o",
        "-o",
        "build/lib.linux-x86_64-cpython-314/fast.cpython-314-x86_64-linux-gnu.so",
    ]
    result = _filter(args)
    assert "-shared" in result
    assert not any("exclude-libs" in a for a in result)
    assert not any("Bsymbolic" in a for a in result)
    assert not any(a.startswith("-LModules/") for a in result)
    assert "build/temp.linux-x86_64-cpython-314/fast.o" in result
