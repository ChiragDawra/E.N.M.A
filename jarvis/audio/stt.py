"""Speech-to-text via faster-whisper (local, Apple-Silicon friendly)."""
from __future__ import annotations

import warnings as _w
_w.filterwarnings("ignore", message="pkg_resources is deprecated")

from pathlib import Path
from typing import Optional, Union

import numpy as np

from jarvis.core.config import CONFIG

try:
    from faster_whisper import WhisperModel
    _HAS_FW = True
except ImportError:  # pragma: no cover
    WhisperModel = None  # type: ignore[assignment]
    _HAS_FW = False


_model: Optional["WhisperModel"] = None


def _get_model(size: str = "medium") -> "WhisperModel":
    global _model
    if not _HAS_FW:
        raise RuntimeError("faster-whisper not installed; run: pip install faster-whisper")
    if _model is None:
        _model = WhisperModel(size, compute_type="int8")
    return _model


AudioLike = Union[str, Path, np.ndarray]


def transcribe(audio: AudioLike, language: str = "en") -> str:
    model = _get_model()
    source = str(audio) if isinstance(audio, (str, Path)) else np.asarray(audio, dtype=np.float32)
    segments, _info = model.transcribe(source, language=language, vad_filter=True)
    return " ".join(seg.text.strip() for seg in segments).strip()


# Keep ruff happy about unused imports when optional deps are missing.
_ = CONFIG
