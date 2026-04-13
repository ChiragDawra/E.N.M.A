"""Spectral liveness detection (Vulnerability #2 cure, Layer 1).

Live speech has a broader and less-compressed spectral signature than audio
re-radiated through a speaker. We combine four features into a liveness
score; the threshold is tuned conservatively to favour security.
"""
from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np

from jarvis.core.config import CONFIG
from jarvis.utils.logging import log_auth

try:
    import librosa
    _HAS_LIBROSA = True
except ImportError:  # pragma: no cover
    librosa = None  # type: ignore[assignment]
    _HAS_LIBROSA = False


AudioLike = Union[str, Path, np.ndarray]


def _load(audio: AudioLike, sr: int) -> np.ndarray:
    if not _HAS_LIBROSA:
        raise RuntimeError("librosa not installed; run: pip install librosa")
    if isinstance(audio, (str, Path)):
        y, _ = librosa.load(str(audio), sr=sr)
        return y
    return np.asarray(audio, dtype=np.float32)


def liveness_score(audio: AudioLike, sr: int | None = None) -> float:
    sr = sr or CONFIG.sample_rate
    y = _load(audio, sr)
    if y.size < sr // 4:  # <0.25s of audio — unreliable
        return 0.0
    centroid = float(np.mean(librosa.feature.spectral_centroid(y=y, sr=sr)))
    rolloff = float(np.mean(librosa.feature.spectral_rolloff(y=y, sr=sr)))
    zcr = float(np.mean(librosa.feature.zero_crossing_rate(y)))
    bandwidth = float(np.mean(librosa.feature.spectral_bandwidth(y=y, sr=sr)))
    score = (bandwidth / 2000.0) * (rolloff / 4000.0) * (1.0 + zcr)
    return score


def is_live(audio: AudioLike, sr: int | None = None,
            threshold: float | None = None) -> tuple[bool, float]:
    threshold = CONFIG.liveness_threshold if threshold is None else threshold
    score = liveness_score(audio, sr)
    ok = score > threshold
    log_auth(ok, similarity=score, note="liveness")
    return ok, score
