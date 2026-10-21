"""Text-to-Speech (TTS) synthesis service and engine abstractions for EAGLE."""

import queue
import threading
from abc import ABC, abstractmethod
from typing import Any

from eagle.core.config import AudioConfig
from eagle.core.exceptions import SynthesisError
from eagle.core.logging import get_logger

logger = get_logger("services.tts")


class BaseTTSEngine(ABC):
    """Abstract interface for voice synthesis engines."""

    @abstractmethod
    def speak(self, text: str, interruptible: bool = True) -> None:
        """Synthesize and vocalize the provided text."""
        raise NotImplementedError

    @abstractmethod
    def stop(self) -> None:
        """Immediately cancel/interrupt any ongoing speech playback."""
        raise NotImplementedError

    @abstractmethod
    def is_speaking(self) -> bool:
        """Return True if speech synthesis is currently actively vocalizing."""
        raise NotImplementedError


class MockTTSEngine(BaseTTSEngine):
    """Deterministic mock TTS engine for unit testing and offline environments."""

    def __init__(self) -> None:
        self.spoken_phrases: list[str] = []
        self._is_speaking: bool = False
        self._interrupted: bool = False

    def speak(self, text: str, interruptible: bool = True) -> None:
        if not text.strip():
            return
        self._is_speaking = True
        self._interrupted = False
        self.spoken_phrases.append(text)
        logger.debug("MockTTS spoken: '%s'", text)
        self._is_speaking = False

    def stop(self) -> None:
        if self._is_speaking:
            self._interrupted = True
            self._is_speaking = False
        logger.debug("MockTTS speech stopped/interrupted.")

    def is_speaking(self) -> bool:
        return self._is_speaking

    @property
    def last_spoken(self) -> str | None:
        return self.spoken_phrases[-1] if self.spoken_phrases else None

    def clear(self) -> None:
        self.spoken_phrases.clear()


class Pyttsx3TTSEngine(BaseTTSEngine):
    """Local Text-to-Speech engine using pyttsx3 (Windows SAPI5)."""

    def __init__(self, rate: int = 175, volume: float = 1.0) -> None:
        self.rate = rate
        self.volume = volume
        self._engine: Any = None
        self._speaking_lock = threading.Lock()
        self._is_speaking = False
        self._stop_requested = False
        self._speech_queue: queue.Queue[str] = queue.Queue()
        self._worker_thread: threading.Thread | None = None

    def _init_engine(self) -> None:
        if self._engine is not None:
            return
        try:
            import pyttsx3

            self._engine = pyttsx3.init()
            self._engine.setProperty("rate", self.rate)
            self._engine.setProperty("volume", self.volume)
            logger.info("pyttsx3 SAPI5 TTS engine initialized.")
        except Exception as exc:
            logger.error("Failed to initialize pyttsx3: %s", exc)
            raise SynthesisError(f"Failed to initialize pyttsx3 TTS engine: {exc}") from exc

    def speak(self, text: str, interruptible: bool = True) -> None:
        if not text.strip():
            return

        try:
            self._init_engine()
        except SynthesisError:
            logger.warning("TTS unavailable; skipping spoken audio for: %s", text)
            return

        with self._speaking_lock:
            self._is_speaking = True
            self._stop_requested = False

        try:
            if self._engine:
                self._engine.say(text)
                self._engine.runAndWait()
        except Exception as exc:
            logger.error("Speech synthesis error: %s", exc)
        finally:
            with self._speaking_lock:
                self._is_speaking = False

    def stop(self) -> None:
        with self._speaking_lock:
            self._stop_requested = True
        try:
            if self._engine and self._is_speaking:
                self._engine.stop()
        except Exception as exc:
            logger.warning("Error stopping pyttsx3 speech: %s", exc)

    def is_speaking(self) -> bool:
        with self._speaking_lock:
            return self._is_speaking


def create_tts_engine(config: AudioConfig) -> BaseTTSEngine:
    """Factory creating the appropriate TTS engine based on configuration."""
    if config.tts_voice.lower() == "mock":
        return MockTTSEngine()

    try:
        import pyttsx3  # noqa: F401

        return Pyttsx3TTSEngine(rate=config.tts_rate, volume=config.tts_volume)
    except Exception as exc:
        logger.warning("pyttsx3 engine could not be initialized (%s); falling back to MockTTS", exc)
        return MockTTSEngine()
