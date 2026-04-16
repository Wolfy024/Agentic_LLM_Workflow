import os

import pytest

from agent.watch.utils import should_ignore_path


@pytest.fixture
def ws(tmp_path):
    d = tmp_path / "proj"
    d.mkdir()
    return str(d)


def test_ignores_git_and_node_modules(ws):
    assert should_ignore_path(ws, os.path.join(ws, ".git", "HEAD"), None)
    assert should_ignore_path(ws, os.path.join(ws, "node_modules", "x.js"), None)


def test_ignores_pyc_and_venv_segment(ws):
    assert should_ignore_path(ws, os.path.join(ws, "lib", "x.pyc"), None)
    assert should_ignore_path(ws, os.path.join(ws, ".venv", "pyvenv.cfg"), None)


def test_keeps_src_file(ws):
    p = os.path.join(ws, "src", "main.py")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, "w").close()
    assert not should_ignore_path(ws, p, None)
