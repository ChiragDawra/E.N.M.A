from unittest.mock import patch

from jarvis.tools import sandbox as sb


def test_unknown_tool_rejected():
    ok, err = sb.execute_tool("delete_all_files", {})
    assert not ok and "not allowed" in err


def test_blocked_pattern_rejected():
    ok, err = sb.execute_tool("open_app", {"name": "rm -rf /"})
    assert not ok


def test_low_tier_runs():
    ok, res = sb.execute_tool("get_time", {})
    assert ok and isinstance(res, str) and len(res) > 0


def test_high_tier_requires_auth():
    # Without ctx and without Touch ID (stubbed False), this must refuse.
    with patch("jarvis.auth.touch_id.authenticate", return_value=False):
        ok, err = sb.execute_tool("touch_id_gate", {})
        assert not ok


def test_medium_tier_without_ctx_refuses():
    ok, err = sb.execute_tool("search_web", {"query": "weather"})
    assert not ok and "confirmation" in err
