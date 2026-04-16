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


def test_resolve_escapes_workspace(tmp_path):
    set_workspace(str(tmp_path))
    outside = tmp_path.parent / "outside_secret"
    outside.mkdir(exist_ok=True)
    with pytest.raises(PermissionError, match="escapes workspace"):
        _resolve(str(outside / "evil.txt"))
