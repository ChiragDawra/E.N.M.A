import os

from jarvis.utils import secrets


def test_env_override(monkeypatch):
    monkeypatch.setenv("JARVIS_FOO", "from-env")
    assert secrets.get_secret("foo", prompt=False) == "from-env"


def test_keyring_roundtrip():
    secrets.set_secret("unit_test_key", "s3cret")
    assert secrets.get_secret("unit_test_key", prompt=False) == "s3cret"
    secrets.delete_secret("unit_test_key")
    assert secrets.get_secret("unit_test_key", prompt=False) is None
