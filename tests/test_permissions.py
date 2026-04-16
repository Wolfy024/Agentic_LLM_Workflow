import pytest

from core import permissions_checks as permissions


@pytest.fixture(autouse=True)
def reset_profile():
    prev = permissions.get_profile()
    yield
    permissions.set_profile(prev)


def test_ci_denies_mutating_tools():
    permissions.set_profile("ci")
    assert permissions.is_tool_denied_in_profile("write_file", {})
    assert permissions.is_tool_denied_in_profile("run_command", {})
    assert permissions.is_tool_denied_in_profile(
        "github_api", {"method": "POST", "path": "/x"}
    )


def test_ci_allows_read_like_tools():
    permissions.set_profile("ci")
    assert not permissions.is_tool_denied_in_profile("read_file", {"path": "a.py"})
    assert not permissions.is_tool_denied_in_profile("github_api", {"method": "GET"})


def test_strict_dev_never_denied_by_profile():
    for p in ("strict", "dev"):
        permissions.set_profile(p)
        assert not permissions.is_tool_denied_in_profile("write_file", {})
