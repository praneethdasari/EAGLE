"""Wake-word detection subsystem supporting local, offline keyword detection and mock engines."""

import re
import threading
import time
from abc import ABC, abstractmethod
from typing import Any

from eagle.core.config import EagleConfig, VoiceConfig
from eagle.core.logging import get_logger
from eagle.services.audio_capture import calculate_rms_amplitude, pcm_to_wav_bytes
from eagle.services.stt import BaseSTTEngine, MockSTTEngine

logger = get_logger("services.wake_word")


class BaseWakeWordEngine(ABC):
    """Abstract interface for wake-word detection engines."""

    name: str = "base"

    def __init__(self, wake_phrase: str = "hey eagle", sensitivity: float = 0.5) -> None:
        self.wake_phrase = wake_phrase.strip().lower()
        self.sensitivity = max(0.0, min(1.0, sensitivity))

    @abstractmethod
    def process_audio(self, pcm_data: bytes) -> bool:
        """Process a chunk of 16-bit mono 16kHz PCM audio bytes.

        Returns:
            True if the wake phrase was detected, False otherwise.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine is ready and operational."""
        pass

    @abstractmethod
    def reset(self) -> None:
        """Clear internal audio buffers, debounce timers, and state."""
        pass


class MockWakeWordEngine(BaseWakeWordEngine):
    """Deterministic, controllable wake-word engine for unit tests and CI."""

    name = "mock"

    def __init__(
        self,
        wake_phrase: str = "hey eagle",
        sensitivity: float = 0.5,
        trigger_on_frames: int | None = None,
    ) -> None:
        super().__init__(wake_phrase=wake_phrase, sensitivity=sensitivity)
        self.trigger_on_frames = trigger_on_frames
        self._triggered = False
        self._frame_count = 0
        self.total_triggers = 0
        self._lock = threading.Lock()

    def is_available(self) -> bool:
        return True

    def trigger(self) -> None:
        """Programmatically trigger wake-word detection on next audio chunk."""
        with self._lock:
            self._triggered = True

    def process_audio(self, pcm_data: bytes) -> bool:
        with self._lock:
            self._frame_count += 1

            if self._triggered:
                self._triggered = False
                self.total_triggers += 1
                logger.debug("MockWakeWordEngine triggered programmatically.")
                return True

            if self.trigger_on_frames is not None and self._frame_count >= self.trigger_on_frames:
                self._frame_count = 0
                self.total_triggers += 1
                logger.debug("MockWakeWordEngine triggered on frame %d.", self.trigger_on_frames)
                return True

            # If simulated PCM data has amplitude indicating speech and contains a marker
            if pcm_data == b"WAKE_WORD_TRIGGER":
                self.total_triggers += 1
                return True

            return False

    def reset(self) -> None:
        with self._lock:
            self._triggered = False
            self._frame_count = 0


class SlidingSTTWakeWordEngine(BaseWakeWordEngine):
    """Local, offline wake-word detector using energy-gated sliding window STT.

    Maintains a rolling 1.5-2.0 second audio buffer, detects vocal energy via RMS,
    and runs fast local transcription to detect the configured wake phrase.
    """

    name = "local_stt"

    def __init__(
        self,
        stt_engine: BaseSTTEngine,
        wake_phrase: str = "hey eagle",
        sensitivity: float = 0.5,
        sample_rate: int = 16000,
        window_duration_seconds: float = 1.5,
        cooldown_seconds: float = 1.5,
    ) -> None:
        super().__init__(wake_phrase=wake_phrase, sensitivity=sensitivity)
        self.stt_engine = stt_engine
        self.sample_rate = sample_rate
        # 16-bit mono = 2 bytes per sample
        self.max_buffer_bytes = int(sample_rate * 2 * window_duration_seconds)
        self.cooldown_seconds = cooldown_seconds

        self._rolling_buffer = bytearray()
        self._last_trigger_time: float = 0.0
        self._lock = threading.Lock()

        # Build search patterns for the wake phrase
        self._tokens = set(re.findall(r"\b\w+\b", self.wake_phrase))
        if not self._tokens:
            self._tokens = {"eagle"}

    def is_available(self) -> bool:
        return self.stt_engine is not None

    def reset(self) -> None:
        with self._lock:
            self._rolling_buffer.clear()
            self._last_trigger_time = 0.0

    def process_audio(self, pcm_data: bytes) -> bool:
        if not pcm_data:
            return False

        now = time.time()
        with self._lock:
            # Respect cooldown to prevent duplicate triggers
            if now - self._last_trigger_time < self.cooldown_seconds:
                return False

            self._rolling_buffer.extend(pcm_data)
            # Maintain sliding window length
            if len(self._rolling_buffer) > self.max_buffer_bytes:
                excess = len(self._rolling_buffer) - self.max_buffer_bytes
                del self._rolling_buffer[:excess]

            # Need at least 0.8s of audio to detect a wake phrase
            min_bytes = int(self.sample_rate * 2 * 0.8)
            if len(self._rolling_buffer) < min_bytes:
                return False

            # Energy gating: evaluate RMS amplitude
            # Higher sensitivity lowers the required energy threshold
            threshold = 0.01 + (1.0 - self.sensitivity) * 0.04
            amp = calculate_rms_amplitude(bytes(self._rolling_buffer))
            if amp < threshold:
                return False

            # Convert rolling window to WAV and run local STT
            wav_bytes = pcm_to_wav_bytes(
                bytes(self._rolling_buffer), sample_rate=self.sample_rate, channels=1
            )

        try:
            result = self.stt_engine.transcribe(wav_bytes)
            text = result.text.lower().strip()
            if not text:
                return False

            # Check for wake phrase matches
            detected = self._matches_wake_phrase(text)
            if detected:
                with self._lock:
                    self._last_trigger_time = now
                    self._rolling_buffer.clear()
                logger.info(
                    "Wake word '%s' detected from transcription: '%s'", self.wake_phrase, text
                )
                return True

            return False
        except Exception as exc:
            logger.debug("Error during wake-word STT processing: %s", exc)
            return False

    def _matches_wake_phrase(self, transcribed_text: str) -> bool:
        """Check if transcribed text contains the wake phrase or its core keywords."""
        cleaned = re.sub(r"[^\w\s]", "", transcribed_text.lower())
        words = set(cleaned.split())

        # Exact phrase substring match
        if self.wake_phrase in cleaned:
            return True

        # Common variants (e.g. "hey eagle", "ok eagle", "eagle")
        if "eagle" in self._tokens and "eagle" in words:
            return True

        # If all tokens in the wake phrase are present
        if self._tokens.issubset(words):
            return True

        return False


class OpenWakeWordEngine(BaseWakeWordEngine):
    """Wake-word detector using local openWakeWord neural models (when installed)."""

    name = "openwakeword"

    def __init__(
        self,
        wake_phrase: str = "hey eagle",
        sensitivity: float = 0.5,
        model_path: str | None = None,
    ) -> None:
        super().__init__(wake_phrase=wake_phrase, sensitivity=sensitivity)
        self.model_path = model_path
        self._model: Any = None
        self._is_available = False
        self._init_model()

    def _init_model(self) -> None:
        try:
            from openwakeword.model import Model  # type: ignore[import-untyped,import-not-found]

            # openWakeWord expects 16-bit 16kHz PCM chunks
            if self.model_path:
                self._model = Model(wakeword_models=[self.model_path], inference_framework="onnx")
            else:
                self._model = Model(inference_framework="onnx")
            self._is_available = True
            logger.info("OpenWakeWord engine initialized successfully.")
        except ImportError:
            logger.debug("openwakeword package is not installed.")
            self._is_available = False
        except Exception as exc:
            logger.warning("Failed to initialize openWakeWord model: %s", exc)
            self._is_available = False

    def is_available(self) -> bool:
        return self._is_available

    def process_audio(self, pcm_data: bytes) -> bool:
        if not self._is_available or self._model is None:
            return False

        try:
            import numpy as np  # type: ignore[import-untyped,import-not-found]

            audio_int16 = np.frombuffer(pcm_data, dtype=np.int16)
            prediction = self._model.predict(audio_int16)

            threshold = 0.5 - (self.sensitivity - 0.5) * 0.4
            for model_name, score in prediction.items():
                if score >= threshold:
                    logger.info(
                        "OpenWakeWord detected wake word '%s' with score %.2f", model_name, score
                    )
                    self.reset()
                    return True
            return False
        except Exception as exc:
            logger.debug("Error in OpenWakeWord processing: %s", exc)
            return False

    def reset(self) -> None:
        if self._model:
            try:
                self._model.reset()
            except Exception:
                pass


def get_wake_word_engine(
    config: EagleConfig | None = None,
    stt_engine: BaseSTTEngine | None = None,
) -> BaseWakeWordEngine:
    """Factory creating the configured wake-word engine.

    Args:
        config: EAGLE configuration instance.
        stt_engine: Optional speech-to-text engine used for sliding STT wake-word detection.

    Returns:
        An instance of BaseWakeWordEngine.
    """
    cfg = config or EagleConfig()
    voice_cfg: VoiceConfig = cfg.voice
    engine_name = voice_cfg.wake_word_engine.lower().strip()

    if engine_name == "mock":
        return MockWakeWordEngine(
            wake_phrase=voice_cfg.wake_word_phrase,
            sensitivity=voice_cfg.wake_word_sensitivity,
        )

    if engine_name == "openwakeword":
        oww = OpenWakeWordEngine(
            wake_phrase=voice_cfg.wake_word_phrase,
            sensitivity=voice_cfg.wake_word_sensitivity,
        )
        if oww.is_available():
            return oww
        logger.warning(
            "OpenWakeWord is not available. Falling back to local sliding STT wake-word engine."
        )

    # Default: Sliding STT Wake Word Engine using local STT
    active_stt = stt_engine or MockSTTEngine()
    return SlidingSTTWakeWordEngine(
        stt_engine=active_stt,
        wake_phrase=voice_cfg.wake_word_phrase,
        sensitivity=voice_cfg.wake_word_sensitivity,
        sample_rate=cfg.audio.sample_rate,
    )
