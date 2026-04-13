"""End-to-end integration test in text mode (no audio stack).

Stubs the LLM decision so we exercise sanitizer → memory write → sandbox
execution → memory read on a real tool (`get_time`).
"""
from __future__ import annotations

from unittest.mock import patch


def test_run_once_text_low_tier_tool(tmp_path, monkeypatch):
    # Swap MemoryStore construction so the real store file lives in tmp_path.
    from jarvis.core import orchestrator as _orch
    from jarvis.memory import store as _store
    real_store = _store.MemoryStore(db_path=tmp_path / "mem.db")
    monkeypatch.setattr(_orch, "MemoryStore", lambda: real_store)

    from jarvis.brain import llm
    from jarvis.core.orchestrator import Jarvis

    fake = llm.Decision(tool="get_time", params={}, say="It is morning.")
    with patch.object(llm, "decide", return_value=fake):
        j = Jarvis()
        reply = j.run_once_text("what time is it")

    assert "morning" in reply.lower()
    assert "tool=get_time ok=True" in reply
    # Memory recorded both sides of the exchange
    rows = real_store.recent(limit=5)
    roles = [r[1] for r in rows]
    assert "user" in roles and "assistant" in roles


def test_run_once_text_rejects_injection():
    from jarvis.core.orchestrator import Jarvis
    j = Jarvis()
    reply = j.run_once_text("'; DROP TABLE users; --")
    assert reply.startswith("rejected:")
