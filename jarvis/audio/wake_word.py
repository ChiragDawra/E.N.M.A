"""Wake-word detection via openWakeWord (Vulnerability #9 cure).

Streams audio from the microphone at 16 kHz and fires when the "hey jarvis"
model exceeds the configured threshold. The caller supplies an on_detect
callback that receives the active stream so it can record the command
audio that follows.
"""
from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

import numpy as np

from jarvis.core.config import CONFIG

try:
    import sounddevice as sd
    _HAS_SD = True
except ImportError:  # pragma: no cover
    sd = None  # type: ignore[assignment]
    _HAS_SD = False

try:
    from openwakeword.model import Model as _WWModel
    _HAS_WW = True
except ImportError:  # pragma: no cover
    _WWModel = None  # type: ignore[assignment]
    _HAS_WW = False


BLOCK_SIZE = 1280  # 80 ms at 16 kHz — openWakeWord's native block


class WakeWordDetector:
    def __init__(self, model_path: Optional[Path] = None,
                 threshold: float | None = None,
                 model_name: str = "hey_jarvis") -> None:
        self.model_path = model_path or CONFIG.wake_word_model
        self.threshold = CONFIG.wake_word_threshold if threshold is None else threshold
        self.model_name = model_name
        self._model: Optional["_WWModel"] = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        if not _HAS_WW:
            raise RuntimeError("openwakeword not installed; run: pip install openwakeword")
        kwargs = {"inference_framework": "onnx"}
        if self.model_path.exists():
            kwargs["wakeword_models"] = [str(self.model_path)]
        self._model = _WWModel(**kwargs)

    def listen_forever(self, on_detect: Callable[[], None]) -> None:
        """Block forever, calling `on_detect` each time the wake word fires."""
        if not _HAS_SD:
            raise RuntimeError("sounddevice not installed; run: pip install sounddevice")
        self._ensure_model()
        assert self._model is not None

        with sd.InputStream(samplerate=CONFIG.sample_rate, channels=1,
                            blocksize=BLOCK_SIZE, dtype="float32") as stream:
            while True:
                audio, _overflow = stream.read(BLOCK_SIZE)
                audio_int16 = (audio[:, 0] * 32767.0).astype(np.int16)
                preds = self._model.predict(audio_int16)
                if preds.get(self.model_name, 0.0) > self.threshold:
                    on_detect()
