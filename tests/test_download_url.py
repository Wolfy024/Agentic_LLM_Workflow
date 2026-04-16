"""Tests for download_url (validation and workspace sandbox)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.registry import set_workspace, _resolve
from tools.web import fetch as fetch_mod


def test_validate_http_url_rejects_non_http():
    with pytest.raises(ValueError, match="http"):
        fetch_mod._validate_http_url("file:///etc/passwd")
    with pytest.raises(ValueError, match="http"):
        fetch_mod._validate_http_url("ftp://example.com/x")


def test_download_url_writes_streamed_bytes(tmp_path):
    set_workspace(str(tmp_path))
    dest = "dl/hello.bin"
    resolved = _resolve(dest)

    mock_resp = MagicMock()
    mock_resp.raise_for_status.return_value = None
    mock_resp.iter_bytes.side_effect = lambda chunk_size=65536: iter([b"ab", b"cd"])

    ctx = MagicMock()
    ctx.__enter__.return_value = mock_resp
    ctx.__exit__.return_value = None

    with patch.object(fetch_mod.httpx, "stream", return_value=ctx):
        out = fetch_mod.download_url("https://example.com/f.txt", dest)

    assert "4 bytes" in out
    assert Path(resolved).read_bytes() == b"abcd"


def test_download_url_removes_partial_file_on_error(tmp_path):
    set_workspace(str(tmp_path))
    dest = "dl/bad.bin"
    resolved = _resolve(dest)

    class BadResp:
        def raise_for_status(self):
            return None

        def iter_bytes(self, chunk_size=65536):
            yield b"x"
            raise OSError("disk full")

    ctx = MagicMock()
    ctx.__enter__.return_value = BadResp()
    ctx.__exit__.return_value = None

    with patch.object(fetch_mod.httpx, "stream", return_value=ctx):
        with pytest.raises(OSError, match="disk full"):
            fetch_mod.download_url("https://example.com/x", dest)

    assert not Path(resolved).exists()
