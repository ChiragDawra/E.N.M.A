"""Main JARVIS event loop.

wake word → voice auth + liveness → STT → LLM → sandboxed tool → TTS reply
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from jarvis.audio import recorder, stt, tts, wake_word
from jarvis.auth import liveness as _liveness
from jarvis.auth import voice as _voice
from jarvis.brain import llm
from jarvis.core.config import CONFIG
from jarvis.memory.store import MemoryStore
from jarvis.security.sanitizer import sanitize
from jarvis.tools import sandbox as _sb
from jarvis.utils.logging import configure, log_auth, log_error


class Jarvis:
    def __init__(self) -> None:
        configure()
        self.memory = MemoryStore()
        self._history: list[dict] = []

    # ---- listener helpers passed down to the sandbox for challenge/response
    def _listen(self, timeout_s: float) -> str:
        samples = recorder.record(seconds=min(timeout_s, 6.0))
        wav = recorder.save_wav(samples)
        try:
            return stt.transcribe(wav) or ""
        except Exception as e:
            log_error(e, "stt")
            return ""
        finally:
            try:
                Path(wav).unlink(missing_ok=True)
            except Exception:
                pass

    def _speak(self, text: str) -> None:
        tts.speak(text, use_fast=True)

    # ---- main pipeline -------------------------------------------------
    def handle_command_window(self, seconds: float = 5.0) -> None:
        samples = recorder.record(seconds=seconds)
        wav = recorder.save_wav(samples)
        try:
            live_ok, live_score = _liveness.is_live(str(wav))
            if not live_ok:
                log_auth(False, similarity=live_score, note="liveness-fail")
                return  # silent drop — don't tip off an attacker
            ok, sim = _voice.verify(str(wav))
            if not ok:
                log_auth(False, similarity=sim, note="voiceprint-fail")
                return
            text = stt.transcribe(str(wav))
        except FileNotFoundError as e:
            self._speak("I need to be enrolled first. Please run setup.")
            log_error(e, "no-profile")
            return
        except Exception as e:
            log_error(e, "pipeline")
            return
        finally:
            try:
                Path(wav).unlink(missing_ok=True)
            except Exception:
                pass

        clean, err = sanitize(text)
        if err or clean is None:
            self._speak("I couldn't understand that safely.")
            return

        self.memory.add_message("user", clean)
        decision = llm.decide(clean, history=self._history_for_llm())
        if decision.say:
            self.memory.add_message("assistant", decision.say)
            self._speak(decision.say)

        if decision.tool:
            ctx = _sb.ExecutionContext(speak=self._speak, listen=self._listen)
            ok, result = _sb.execute_tool(decision.tool, decision.params,
                                          ctx=ctx, speaker_verified=True)
            if not ok:
                self._speak(f"I couldn't do that: {result}")

    def _history_for_llm(self, n: int = 8) -> list[dict]:
        rows = self.memory.recent(limit=n)
        return [{"role": role, "content": text} for _, role, text in rows]

    # ---- runners -------------------------------------------------------
    def run_forever(self) -> None:
        detector = wake_word.WakeWordDetector()
        self._speak("JARVIS online.")
        detector.listen_forever(on_detect=lambda: self.handle_command_window())

    def run_once_text(self, text: str) -> Optional[str]:
        """Headless text-mode entry point — bypasses audio stack for tests."""
        clean, err = sanitize(text)
        if err or clean is None:
            return f"rejected: {err}"
        self.memory.add_message("user", clean)
        decision = llm.decide(clean, history=self._history_for_llm())
        if decision.say:
            self.memory.add_message("assistant", decision.say)
        if decision.tool:
            ctx = None  # interactive confirm not possible in text mode
            ok, res = _sb.execute_tool(decision.tool, decision.params, ctx=ctx)
            return f"{decision.say} [tool={decision.tool} ok={ok} result={res}]"
        return decision.say
