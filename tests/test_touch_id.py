from jarvis.auth import touch_id


def test_non_mac_returns_false(monkeypatch):
    monkeypatch.setattr(touch_id.platform, "system", lambda: "Linux")
    assert touch_id.is_available() is False
    assert touch_id.authenticate() is False
