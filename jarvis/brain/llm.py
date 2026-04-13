"""LLM routing with automatic failover.

Order of preference:
  1. Claude (Anthropic Pro) — primary brain with tool-calling.
  2. Gemini — fallback if Claude fails or circuit breaker is open.
  3. Ollama + Llama 3 — offline fallback.

Every call runs through the RateLimiter; consecutive failures trip the
circuit breaker and force offline mode for 60 s.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from jarvis.core.config import CONFIG
from jarvis.security.rate_limiter import LIMITER
from jarvis.tools import sandbox as _sb
from jarvis.utils.logging import log_error
from jarvis.utils.secrets import get_secret

try:
    import anthropic  # type: ignore
    _HAS_ANTHROPIC = True
except ImportError:  # pragma: no cover
    anthropic = None  # type: ignore[assignment]
    _HAS_ANTHROPIC = False

try:
    import google.generativeai as genai  # type: ignore
    _HAS_GEMINI = True
except ImportError:  # pragma: no cover
    genai = None  # type: ignore[assignment]
    _HAS_GEMINI = False

try:
    import requests  # used for Ollama
    _HAS_REQUESTS = True
except ImportError:  # pragma: no cover
    requests = None  # type: ignore[assignment]
    _HAS_REQUESTS = False


SYSTEM_PROMPT = (
    "You are JARVIS, a helpful, concise macOS voice assistant. "
    "When the user asks you to perform an action, respond ONLY with a single "
    "JSON object on its own line of the form "
    '{"tool": "<tool_name>", "params": {...}, "say": "<short spoken reply>"} '
    "choosing a tool from: " + ", ".join(_sb.all_tools()) + ". "
    "If no tool is appropriate, respond with "
    '{"tool": null, "say": "<your spoken reply>"}.'
)


@dataclass
class Decision:
    tool: Optional[str]
    params: dict
    say: str

    @classmethod
    def from_text(cls, text: str) -> "Decision":
        text = text.strip()
        # tolerate code-fenced JSON
        if text.startswith("```"):
            text = text.strip("`")
            if text.startswith("json"):
                text = text[4:]
        try:
            obj = json.loads(text)
        except json.JSONDecodeError:
            return cls(tool=None, params={}, say=text[:200])
        return cls(
            tool=obj.get("tool"),
            params=obj.get("params") or {},
            say=(obj.get("say") or "").strip(),
        )


def _call_claude(prompt: str, history: list[dict]) -> str:
    if not _HAS_ANTHROPIC:
        raise RuntimeError("anthropic package missing")
    api_key = get_secret("anthropic_api_key")
    if not api_key:
        raise RuntimeError("no anthropic api key")
    client = anthropic.Anthropic(api_key=api_key)
    msgs = history + [{"role": "user", "content": prompt}]
    resp = client.messages.create(
        model="claude-opus-4-6",
        max_tokens=400,
        system=SYSTEM_PROMPT,
        messages=msgs,
    )
    return resp.content[0].text  # type: ignore[no-any-return, index]


def _call_gemini(prompt: str, history: list[dict]) -> str:
    if not _HAS_GEMINI:
        raise RuntimeError("google-generativeai package missing")
    api_key = get_secret("gemini_api_key")
    if not api_key:
        raise RuntimeError("no gemini api key")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-pro", system_instruction=SYSTEM_PROMPT)
    chat = model.start_chat(history=[
        {"role": m["role"], "parts": [m["content"]]} for m in history
    ])
    r = chat.send_message(prompt)
    return r.text  # type: ignore[no-any-return]


def _call_ollama(prompt: str, history: list[dict]) -> str:
    if not _HAS_REQUESTS:
        raise RuntimeError("requests package missing")
    msgs = ([{"role": "system", "content": SYSTEM_PROMPT}]
            + history + [{"role": "user", "content": prompt}])
    r = requests.post(
        "http://127.0.0.1:11434/api/chat",
        json={"model": "llama3", "messages": msgs, "stream": False},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["message"]["content"]  # type: ignore[no-any-return]


def decide(prompt: str, history: Optional[list[dict]] = None) -> Decision:
    history = history or []
    if CONFIG.offline_mode or LIMITER.circuit_open():
        try:
            return Decision.from_text(_call_ollama(prompt, history))
        except Exception as e:
            log_error(e, "ollama")
            return Decision(None, {}, "I'm offline and unable to reach any brain.")

    # Primary: Claude
    if LIMITER.allow("claude_api"):
        try:
            out = _call_claude(prompt, history)
            LIMITER.record_success()
            return Decision.from_text(out)
        except Exception as e:
            LIMITER.record_failure()
            log_error(e, "claude")

    # Fallback: Gemini
    if LIMITER.allow("gemini_api"):
        try:
            out = _call_gemini(prompt, history)
            LIMITER.record_success()
            return Decision.from_text(out)
        except Exception as e:
            LIMITER.record_failure()
            log_error(e, "gemini")

    # Offline last-resort
    try:
        return Decision.from_text(_call_ollama(prompt, history))
    except Exception as e:
        log_error(e, "ollama")
        return Decision(None, {}, "All brains unavailable. Please try again later.")


_ = Any  # keep mypy happy when optional deps absent
