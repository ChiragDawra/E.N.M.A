from pathlib import Path

import pytest


@pytest.fixture()
def store(tmp_path):
    pytest.importorskip("cryptography")
    from jarvis.memory.store import MemoryStore
    return MemoryStore(db_path=tmp_path / "mem.db")


def test_roundtrip(store):
    store.add_message("user", "hello")
    store.add_message("assistant", "hi there")
    rows = store.recent(limit=10)
    assert [r[1] for r in rows] == ["user", "assistant"]
    assert [r[2] for r in rows] == ["hello", "hi there"]


def test_kv(store):
    store.set("name", "Chirag")
    assert store.get("name") == "Chirag"


def test_pii_redacted_before_encrypt(store):
    store.add_message("user", "email me at secret@example.com")
    rows = store.recent(1)
    assert "secret@example.com" not in rows[0][2]
    assert "[REDACTED-EMAIL]" in rows[0][2]


def test_ciphertext_on_disk_is_unreadable(store, tmp_path):
    store.add_message("user", "the password is hunter2")
    blob = Path(store.db_path).read_bytes()
    assert b"hunter2" not in blob
