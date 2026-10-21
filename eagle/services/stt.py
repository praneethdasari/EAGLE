"""Speech-to-Text (STT) service and engine abstractions for EAGLE."""

import io
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from eagle.core.config import AudioConfig
from eagle.core.exceptions import TranscriptionError
from eagle.core.logging import get_logger

logger = get_logger("services.stt")


@dataclass
class TranscriptionResult:
    """Standardized result of a speech-to-text operation."""

    text: str
    language: str = "en"
    confidence: float = 1.0
    duration_seconds: float = 0.0

    @property
    def is_empty(self) -> bool:
        """Return True if transcription contains no words."""
        return not bool(self.text.strip())


class BaseSTTEngine(ABC):
    """Abstract interface for speech transcription engines."""

    @abstractmethod
    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        """Transcribe raw PCM/WAV audio bytes into text.

        Raises:
            TranscriptionError: If audio decoding or transcription fails.
        """
        raise NotImplementedError

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the engine and its dependencies/models are ready."""
        raise NotImplementedError


class MockSTTEngine(BaseSTTEngine):
    """Deterministic mock STT engine for unit testing and offline environments."""

    def __init__(self, default_response: str = "Hello EAGLE") -> None:
        self.default_response = default_response
        self._queued_responses: list[str] = []
        self._call_count = 0

    def queue_response(self, text: str) -> None:
        """Queue a specific text response for the next transcribe call."""
        self._queued_responses.append(text)

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        self._call_count += 1
        if self._queued_responses:
            text = self._queued_responses.pop(0)
        else:
            text = self.default_response

        logger.debug("MockSTT transcribed %d bytes to '%s'", len(audio_bytes), text)
        return TranscriptionResult(
            text=text,
            language="en",
            confidence=0.99,
            duration_seconds=1.0,
        )

    def is_available(self) -> bool:
        return True

    @property
    def call_count(self) -> int:
        return self._call_count


class FasterWhisperSTT(BaseSTTEngine):
    """Local Speech-to-Text engine using faster-whisper (CTranslate2)."""

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model: Any = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        try:
            from faster_whisper import WhisperModel

            logger.info("Loading faster-whisper model '%s' on %s...", self.model_size, self.device)
            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
            )
        except ImportError as exc:
            raise TranscriptionError(
                "faster-whisper is not installed. Run 'pip install faster-whisper'."
            ) from exc
        except Exception as exc:
            raise TranscriptionError(
                f"Failed to load faster-whisper model '{self.model_size}': {exc}"
            ) from exc

    def transcribe(self, audio_bytes: bytes) -> TranscriptionResult:
        self._ensure_loaded()
        if not audio_bytes:
            return TranscriptionResult(text="", confidence=0.0)

        try:
            # Wrap bytes in a BinaryIO stream for faster-whisper
            audio_stream = io.BytesIO(audio_bytes)
            segments, info = self._model.transcribe(
                audio_stream,
                beam_size=5,
                language="en",
                vad_filter=True,
            )

            text_chunks = [segment.text.strip() for segment in segments]
            full_text = " ".join(text_chunks).strip()
            confidence = float(info.avg_logprob) if hasattr(info, "avg_logprob") else 1.0

            return TranscriptionResult(
                text=full_text,
                language=info.language or "en",
                confidence=confidence,
                duration_seconds=float(info.duration) if hasattr(info, "duration") else 0.0,
            )
        except Exception as exc:
            logger.error("Transcription failed: %s", exc, exc_info=True)
            raise TranscriptionError(f"STT transcription failed: {exc}") from exc

    def is_available(self) -> bool:
        try:
            import faster_whisper  # noqa: F401

            return True
        except ImportError:
            return False


def create_stt_engine(config: AudioConfig) -> BaseSTTEngine:
    """Factory creating the appropriate STT engine based on configuration."""
    if config.stt_model_size.lower() == "mock":
        return MockSTTEngine()

    # If faster-whisper is available, use it; otherwise fallback gracefully to Mock with warning
    faster_whisper_engine = FasterWhisperSTT(model_size=config.stt_model_size)
    if faster_whisper_engine.is_available():
        return faster_whisper_engine

    logger.warning("Local faster-whisper not detected; defaulting to MockSTTEngine.")
    return MockSTTEngine(default_response="")
