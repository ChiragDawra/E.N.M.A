"""Text-to-speech.

Primary: Chatterbox TTS (high quality).  Fallback: macOS `say` command for
instant response while Chatterbox is loading or unavailable.
"""
from __future__ import annotations

import platform
import shutil
import subprocess
from typing import Optional

try:
    import chatterbox_tts  # type: ignore
    _HAS_CHATTERBOX = True
except ImportError:  # pragma: no cover
    chatterbox_tts = None  # type: ignore[assignment]
    _HAS_CHATTERBOX = False


_engine = None


def _mac_say(text: str, voice: Optional[str] = None) -> None:
    if platform.system() != "Darwin":
        print(f"[TTS fallback] {text}")
        return
    args = ["say"]
    if voice:
        args += ["-v", voice]
    args.append(text)
    try:
        subprocess.run(args, check=False, timeout=60)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        print(f"[TTS fallback] {text}")


def speak(text: str, use_fast: bool = False) -> None:
    """Speak `text`.  If `use_fast` is True, skip Chatterbox and use `say`."""
    if not text:
        return
    if use_fast or not _HAS_CHATTERBOX:
        _mac_say(text)
        return
    try:
        global _engine
        if _engine is None:
            _engine = chatterbox_tts.TTS()  # type: ignore[attr-defined]
        _engine.speak(text)  # type: ignore[union-attr]
    except Exception:
        _mac_say(text)


_ = shutil  # reserved for future: lookup of 'say' path
