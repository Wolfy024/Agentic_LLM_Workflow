"""Tests for reading/importing files from outside the workspace."""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.registry import set_workspace, is_path_inside_workspace
from tools.fs import external as ext
from tools.fs.read import list_directory


def test_is_path_inside_workspace(tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    set_workspace(str(ws))
    assert is_path_inside_workspace(str(ws / "a" / "b.txt"))
    assert is_path_inside_workspace(str(ws))
    assert not is_path_inside_workspace(str(tmp_path / "other" / "x.txt"))


def test_read_external_file_rejects_workspace_path(tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    f = ws / "in.txt"
    f.write_text("hello", encoding="utf-8")
    set_workspace(str(ws))
    out = ext.read_external_file(str(f))
    assert "inside the workspace" in out.lower() or "use read_file" in out.lower()


def test_read_external_file_reads_outside_file(tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    outside = tmp_path / "outside" / "secret.txt"
    outside.parent.mkdir()
    outside.write_text("line1\nline2\n", encoding="utf-8")
    set_workspace(str(ws))
    out = ext.read_external_file(str(outside))
    assert "line1" in out and "line2" in out


def test_import_external_file_copies_into_workspace(tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    outside = tmp_path / "vendor" / "lib.py"
    outside.parent.mkdir()
    outside.write_text("# original", encoding="utf-8")
    set_workspace(str(ws))
    msg = ext.import_external_file(str(outside), ".minillm/imports/lib.py")
    assert "Copied" in msg or "copied" in msg
    copy_path = ws / ".minillm" / "imports" / "lib.py"
    assert copy_path.read_text(encoding="utf-8") == "# original"
    assert outside.read_text(encoding="utf-8") == "# original"


def test_list_directory_absolute_outside_workspace(tmp_path):
    outside = tmp_path / "desktop_sim"
    outside.mkdir()
    (outside / "note.txt").write_text("x", encoding="utf-8")
    ws = tmp_path / "proj"
    ws.mkdir()
    set_workspace(str(ws))
    out = list_directory(str(outside))
    assert "note.txt" in out


def test_import_external_file_rejects_source_already_in_workspace(tmp_path):
    ws = tmp_path / "proj"
    ws.mkdir()
    inner = ws / "x.py"
    inner.write_text("x", encoding="utf-8")
    set_workspace(str(ws))
    msg = ext.import_external_file(str(inner), "copy.py")
    assert "already" in msg.lower() or "workspace" in msg.lower()
