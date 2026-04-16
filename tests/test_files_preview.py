import pytest

from tools.registry import set_workspace
from tools.fs.edit import preview_patch_file, preview_replace_in_file


def test_preview_replace_ok(tmp_path):
    set_workspace(str(tmp_path))
    p = tmp_path / "a.txt"
    p.write_text("hello world", encoding="utf-8")
    ok, before, after = preview_replace_in_file("a.txt", "world", "there")
    assert ok
    assert before == "hello world"
    assert after == "hello there"


def test_preview_replace_not_found(tmp_path):
    set_workspace(str(tmp_path))
    (tmp_path / "a.txt").write_text("x", encoding="utf-8")
    ok, err, _ = preview_replace_in_file("a.txt", "nope", "y")
    assert not ok
    assert "not found" in err


def test_preview_patch_ok(tmp_path):
    set_workspace(str(tmp_path))
    p = tmp_path / "b.txt"
    p.write_text("a\nb\nc\n", encoding="utf-8")
    ok, before, after = preview_patch_file("b.txt", [{"start_line": 2, "end_line": 2, "new_text": "B"}])
    assert ok
    assert "a\n" in before
    assert "B\n" in after
