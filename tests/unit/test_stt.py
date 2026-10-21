"""Unit tests for eagle.services.stt."""

import pytest
from pytest_mock import MockerFixture

from eagle.core.config import AudioConfig
from eagle.core.exceptions import TranscriptionError
from eagle.services.stt import (
    FasterWhisperSTT,
    MockSTTEngine,
    TranscriptionResult,
    create_stt_engine,
)


def test_transcription_result_properties() -> None:
    """Verify TranscriptionResult attributes and is_empty logic."""
    res_empty = TranscriptionResult(text="   ")
    assert res_empty.is_empty is True

    res_valid = TranscriptionResult(text="Open calculator", language="en", confidence=0.98)
    assert res_valid.is_empty is False
    assert res_valid.text == "Open calculator"
    assert res_valid.confidence == 0.98


def test_mock_stt_engine_responses() -> None:
    """Verify MockSTTEngine default and queued response behavior."""
    engine = MockSTTEngine(default_response="Default response")
    assert engine.is_available() is True
    assert engine.call_count == 0

    # Default response
    r1 = engine.transcribe(b"dummy_pcm_audio")
    assert r1.text == "Default response"
    assert engine.call_count == 1

    # Queued responses
    engine.queue_response("First queued command")
    engine.queue_response("Second queued command")

    r2 = engine.transcribe(b"audio")
    assert r2.text == "First queued command"

    r3 = engine.transcribe(b"audio")
    assert r3.text == "Second queued command"

    # Falls back to default after queue is consumed
    r4 = engine.transcribe(b"audio")
    assert r4.text == "Default response"
    assert engine.call_count == 4


def test_create_stt_engine_factory() -> None:
    """Verify create_stt_engine factory initializes Mock or Whisper."""
    cfg_mock = AudioConfig(stt_model_size="mock")
    engine = create_stt_engine(cfg_mock)
    assert isinstance(engine, MockSTTEngine)


def test_faster_whisper_empty_audio_handling() -> None:
    """Verify FasterWhisperSTT handles empty audio bytes gracefully."""
    engine = FasterWhisperSTT(model_size="tiny")
    # Mock _model directly to avoid downloading whisper model in offline unit test
    engine._model = object()

    result = engine.transcribe(b"")
    assert result.is_empty is True
    assert result.confidence == 0.0


def test_faster_whisper_import_failure(mocker: MockerFixture) -> None:
    """Verify TranscriptionError is raised when faster_whisper is not installed."""
    mocker.patch("builtins.__import__", side_effect=ImportError("No module named 'faster_whisper'"))
    engine = FasterWhisperSTT(model_size="tiny")
    with pytest.raises(TranscriptionError) as exc_info:
        engine._ensure_loaded()
    assert "faster-whisper is not installed" in str(exc_info.value)
