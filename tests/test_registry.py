import pytest

from tools.registry import set_workspace, _resolve


def test_resolve_relative_inside_workspace(tmp_path):
    set_workspace(str(tmp_path))
    p = _resolve("sub/file.txt")
    assert p == str(tmp_path / "sub" / "file.txt")


def test_resolve_absolute_inside_workspace(tmp_path):
    set_workspace(str(tmp_path))
    inner = tmp_path / "inner"
    inner.mkdir()
    p = _resolve(str(inner / "x.py"))
    assert p == str(inner / "x.py")


def test_resolve_absolute_outside_workspace(tmp_path):
    """Absolute paths outside workspace should resolve without error (full access mode)."""
    set_workspace(str(tmp_path))
    outside = tmp_path.parent / "outside_dir"
    outside.mkdir(exist_ok=True)
    p = _resolve(str(outside / "file.txt"))
    assert p == str(outside / "file.txt")
