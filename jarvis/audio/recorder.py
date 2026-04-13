"""Microphone recording with voice-activity-style silence trimming."""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import numpy as np

from jarvis.core.config import CONFIG

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:  # pragma: no cover
    sd = None  # type: ignore[assignment]
    _HAS_SD = False


def record(seconds: float = 5.0, sr: Optional[int] = None) -> np.ndarray:
    if not _HAS_SD:
        raise RuntimeError("sounddevice not installed")
    sr = sr or CONFIG.sample_rate
    frames = int(seconds * sr)
    audio = sd.rec(frames, samplerate=sr, channels=1, dtype="float32")
    sd.wait()
    return audio[:, 0]


def save_wav(samples: np.ndarray, sr: Optional[int] = None) -> Path:
    """Write samples to a temp WAV and return the path."""
    import wave
    sr = sr or CONFIG.sample_rate
    tmp = Path(tempfile.mkstemp(suffix=".wav", prefix="jarvis_")[1])
    pcm = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16).tobytes()
    with wave.open(str(tmp), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)
    return tmp
