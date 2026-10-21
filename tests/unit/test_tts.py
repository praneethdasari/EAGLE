"""Unit tests for eagle.services.tts."""

from pytest_mock import MockerFixture

from eagle.core.config import AudioConfig
from eagle.services.tts import (
    MockTTSEngine,
    Pyttsx3TTSEngine,
    create_tts_engine,
)


def test_mock_tts_engine_playback() -> None:
    """Verify MockTTSEngine tracks spoken phrases and interruption."""
    engine = MockTTSEngine()
    assert engine.spoken_phrases == []
    assert engine.last_spoken is None

    # Normal speech
    engine.speak("Hello, I am EAGLE.")
    assert len(engine.spoken_phrases) == 1
    assert engine.last_spoken == "Hello, I am EAGLE."

    # Blank speech ignored
    engine.speak("   ")
    assert len(engine.spoken_phrases) == 1

    # Second utterance
    engine.speak("Opening Notepad.")
    assert len(engine.spoken_phrases) == 2
    assert engine.last_spoken == "Opening Notepad."

    # Clear
    engine.clear()
    assert engine.spoken_phrases == []
    assert engine.last_spoken is None


def test_mock_tts_stop_interruption() -> None:
    """Verify stop() handles interruption cleanly."""
    engine = MockTTSEngine()
    engine._is_speaking = True
    engine.stop()
    assert engine.is_speaking() is False
    assert engine._interrupted is True


def test_create_tts_engine_factory() -> None:
    """Verify factory returns MockTTSEngine when configured."""
    config = AudioConfig(tts_voice="mock")
    engine = create_tts_engine(config)
    assert isinstance(engine, MockTTSEngine)


def test_pyttsx3_tts_engine_mocked(mocker: MockerFixture) -> None:
    """Verify Pyttsx3TTSEngine interaction with mock pyttsx3 runtime."""
    mock_engine_instance = mocker.MagicMock()
    mock_pyttsx3 = mocker.MagicMock()
    mock_pyttsx3.init.return_value = mock_engine_instance
    mocker.patch.dict("sys.modules", {"pyttsx3": mock_pyttsx3})

    tts = Pyttsx3TTSEngine(rate=180, volume=0.9)
    tts.speak("Testing speech synthesis")

    mock_engine_instance.say.assert_called_once_with("Testing speech synthesis")
    mock_engine_instance.runAndWait.assert_called_once()
