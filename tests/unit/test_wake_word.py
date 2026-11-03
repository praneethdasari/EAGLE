"""Unit tests for EAGLE wake-word detection engines and factory."""

from eagle.core.config import EagleConfig, VoiceConfig
from eagle.services.stt import MockSTTEngine
from eagle.services.wake_word import (
    MockWakeWordEngine,
    OpenWakeWordEngine,
    SlidingSTTWakeWordEngine,
    get_wake_word_engine,
)


def test_mock_wake_word_engine_programmatic_trigger() -> None:
    """Verify MockWakeWordEngine triggers when explicitly instructed."""
    engine = MockWakeWordEngine(wake_phrase="hey eagle")
    assert engine.is_available() is True
    assert engine.total_triggers == 0

    # Normal frame should return False
    assert engine.process_audio(b"\x00" * 640) is False
    assert engine.total_triggers == 0

    # Trigger programmatically
    engine.trigger()
    assert engine.process_audio(b"\x00" * 640) is True
    assert engine.total_triggers == 1

    # Next call without trigger should be False
    assert engine.process_audio(b"\x00" * 640) is False
    assert engine.total_triggers == 1


def test_mock_wake_word_engine_frame_trigger() -> None:
    """Verify MockWakeWordEngine triggers after configured frame count."""
    engine = MockWakeWordEngine(trigger_on_frames=3)
    assert engine.process_audio(b"\x00" * 640) is False
    assert engine.process_audio(b"\x00" * 640) is False
    assert engine.process_audio(b"\x00" * 640) is True
    assert engine.total_triggers == 1


def test_mock_wake_word_engine_keyword_trigger() -> None:
    """Verify MockWakeWordEngine triggers on simulated trigger bytes."""
    engine = MockWakeWordEngine()
    assert engine.process_audio(b"WAKE_WORD_TRIGGER") is True
    assert engine.total_triggers == 1


def test_mock_wake_word_engine_reset() -> None:
    """Verify MockWakeWordEngine reset clears trigger state."""
    engine = MockWakeWordEngine()
    engine.trigger()
    engine.reset()
    assert engine.process_audio(b"\x00" * 640) is False


def test_sliding_stt_wake_word_silence_gating() -> None:
    """Verify SlidingSTTWakeWordEngine ignores silence without invoking STT."""
    mock_stt = MockSTTEngine(preset_text="hey eagle")
    engine = SlidingSTTWakeWordEngine(stt_engine=mock_stt, wake_phrase="hey eagle")
    assert engine.is_available() is True

    # Feed silence PCM bytes (RMS = 0)
    for _ in range(10):
        result = engine.process_audio(b"\x00" * 3200)
        assert result is False

    # STT transcribe should never have been called for pure silence
    assert mock_stt.call_count == 0


def test_sliding_stt_wake_word_detection() -> None:
    """Verify SlidingSTTWakeWordEngine detects wake phrase when vocal energy is present."""
    mock_stt = MockSTTEngine(preset_text="Hey EAGLE!")
    engine = SlidingSTTWakeWordEngine(
        stt_engine=mock_stt,
        wake_phrase="hey eagle",
        sensitivity=0.8,
        cooldown_seconds=0.5,
    )

    # Generate synthetic audio chunk with alternating 16-bit values to simulate vocal energy
    loud_pcm = b"\x7f\x10\x80\xef" * 8000  # 32000 bytes = 1.0s at 16kHz mono

    detected = engine.process_audio(loud_pcm)
    assert detected is True
    assert mock_stt.call_count == 1

    # Immediate second call should be ignored by cooldown
    second = engine.process_audio(loud_pcm)
    assert second is False


def test_sliding_stt_wake_word_no_match() -> None:
    """Verify SlidingSTTWakeWordEngine returns False when speech does not contain wake phrase."""
    mock_stt = MockSTTEngine(preset_text="what time is it?")
    engine = SlidingSTTWakeWordEngine(
        stt_engine=mock_stt,
        wake_phrase="hey eagle",
        sensitivity=0.8,
        cooldown_seconds=0.1,
    )

    loud_pcm = b"\x7f\x10\x80\xef" * 8000
    detected = engine.process_audio(loud_pcm)
    assert detected is False
    assert mock_stt.call_count == 1


def test_openwakeword_engine_graceful_missing_handling() -> None:
    """Verify OpenWakeWordEngine handles missing library gracefully."""
    engine = OpenWakeWordEngine(wake_phrase="hey eagle")
    # If openwakeword is not installed, it safely reports unavailable and returns False
    assert engine.is_available() is False
    assert engine.process_audio(b"\x00" * 640) is False
    engine.reset()  # Should not raise


def test_get_wake_word_engine_factory() -> None:
    """Verify get_wake_word_engine factory returns expected engine based on config."""
    cfg_mock = EagleConfig(voice=VoiceConfig(wake_word_engine="mock"))
    e_mock = get_wake_word_engine(cfg_mock)
    assert isinstance(e_mock, MockWakeWordEngine)

    cfg_stt = EagleConfig(voice=VoiceConfig(wake_word_engine="local_stt"))
    e_stt = get_wake_word_engine(cfg_stt)
    assert isinstance(e_stt, SlidingSTTWakeWordEngine)

    # When openwakeword is missing, it falls back to SlidingSTTWakeWordEngine
    cfg_oww = EagleConfig(voice=VoiceConfig(wake_word_engine="openwakeword"))
    e_oww = get_wake_word_engine(cfg_oww)
    assert isinstance(e_oww, (OpenWakeWordEngine, SlidingSTTWakeWordEngine))
