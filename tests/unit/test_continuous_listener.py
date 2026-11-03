"""Unit tests for EAGLE continuous listener, state machine transitions, and speech lifecycle."""

import time

import pytest

from eagle.core.config import EagleConfig, VoiceConfig
from eagle.core.events import (
    AudioCaptureStartedEvent,
    AudioCaptureStoppedEvent,
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputFinishedEvent,
    SpeechTranscribedEvent,
    StateChangedEvent,
    WakeWordDetectedEvent,
)
from eagle.core.exceptions import InvalidStateTransitionError
from eagle.services.audio_capture import AudioCaptureManager
from eagle.services.continuous_listener import AssistantState, ContinuousListener
from eagle.services.stt import MockSTTEngine
from eagle.services.tts import MockTTSEngine
from eagle.services.wake_word import MockWakeWordEngine


def test_state_machine_valid_transitions() -> None:
    """Verify that all legal state machine transitions succeed."""
    listener = ContinuousListener()
    assert listener.state == AssistantState.IDLE

    # IDLE -> LISTENING_FOR_WAKE_WORD
    listener.transition_to(AssistantState.LISTENING_FOR_WAKE_WORD)
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # LISTENING_FOR_WAKE_WORD -> CAPTURING_COMMAND
    listener.transition_to(AssistantState.CAPTURING_COMMAND)
    assert listener.state == AssistantState.CAPTURING_COMMAND

    # CAPTURING_COMMAND -> PROCESSING_COMMAND
    listener.transition_to(AssistantState.PROCESSING_COMMAND)
    assert listener.state == AssistantState.PROCESSING_COMMAND

    # PROCESSING_COMMAND -> SPEAKING
    listener.transition_to(AssistantState.SPEAKING)
    assert listener.state == AssistantState.SPEAKING

    # SPEAKING -> LISTENING_FOR_WAKE_WORD
    listener.transition_to(AssistantState.LISTENING_FOR_WAKE_WORD)
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # LISTENING_FOR_WAKE_WORD -> STOPPING -> IDLE
    listener.transition_to(AssistantState.STOPPING)
    assert listener.state == AssistantState.STOPPING
    listener.transition_to(AssistantState.IDLE)
    assert listener.state == AssistantState.IDLE


def test_state_machine_invalid_transitions_raise() -> None:
    """Verify that illegal transitions raise InvalidStateTransitionError."""
    listener = ContinuousListener()
    assert listener.state == AssistantState.IDLE

    # IDLE cannot transition directly to SPEAKING
    with pytest.raises(InvalidStateTransitionError):
        listener.transition_to(AssistantState.SPEAKING)

    # Move to CAPTURING_COMMAND
    listener.transition_to(AssistantState.CAPTURING_COMMAND)

    # CAPTURING_COMMAND cannot transition directly to SPEAKING
    with pytest.raises(InvalidStateTransitionError):
        listener.transition_to(AssistantState.SPEAKING)


def test_state_change_events_published() -> None:
    """Verify StateChangedEvent and ListeningStateChangedEvent are published on transitions."""
    event_bus = EventBus()
    state_changes: list[StateChangedEvent] = []
    listening_changes: list[ListeningStateChangedEvent] = []

    event_bus.subscribe(StateChangedEvent, lambda e: state_changes.append(e))
    event_bus.subscribe(ListeningStateChangedEvent, lambda e: listening_changes.append(e))

    listener = ContinuousListener(event_bus=event_bus)
    listener.transition_to(AssistantState.LISTENING_FOR_WAKE_WORD, reason="unit test")

    assert len(state_changes) == 1
    assert state_changes[0].old_state == "IDLE"
    assert state_changes[0].new_state == "LISTENING_FOR_WAKE_WORD"

    assert len(listening_changes) == 1
    assert listening_changes[0].old_state == "IDLE"
    assert listening_changes[0].new_state == "LISTENING_FOR_WAKE_WORD"
    assert listening_changes[0].reason == "unit test"


def test_continuous_listener_lifecycle_start_and_stop() -> None:
    """Verify start and stop lifecycle for continuous listening with wake word enabled."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=True, wake_word_engine="mock"))
    event_bus = EventBus()
    audio_capture = AudioCaptureManager(config=config.audio, event_bus=event_bus)
    wake_word = MockWakeWordEngine()

    stopped_events: list[AudioCaptureStoppedEvent] = []
    event_bus.subscribe(AudioCaptureStoppedEvent, lambda e: stopped_events.append(e))

    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        audio_capture=audio_capture,
        wake_word_engine=wake_word,
    )

    listener.start()
    assert listener.is_active() is True
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # Repeated start is idempotent
    listener.start()
    assert listener.is_active() is True

    # Stop releases resources cleanly
    listener.stop()
    assert listener.is_active() is False
    assert listener.state == AssistantState.IDLE
    assert len(stopped_events) == 1


def test_continuous_listener_wake_word_disabled_start() -> None:
    """Verify that start() with wake_word_enabled=False stays in IDLE mode."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=False))
    listener = ContinuousListener(config=config)

    listener.start()
    assert listener.is_active() is True
    # Without wake word enabled, it remains in IDLE waiting for manual / CLI input
    assert listener.state == AssistantState.IDLE
    listener.stop()


def test_continuous_listener_wake_word_trigger_event() -> None:
    """Verify that wake-word detection transitions from LISTENING_FOR_WAKE_WORD to CAPTURING_COMMAND."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=True, wake_word_engine="mock"))
    event_bus = EventBus()
    wake_events: list[WakeWordDetectedEvent] = []
    capture_events: list[AudioCaptureStartedEvent] = []

    event_bus.subscribe(WakeWordDetectedEvent, lambda e: wake_events.append(e))
    event_bus.subscribe(AudioCaptureStartedEvent, lambda e: capture_events.append(e))

    wake_word = MockWakeWordEngine()
    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
    )

    listener.start()
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # Trigger wake word programmatically and feed simulated chunk
    wake_word.trigger()
    listener.feed_simulated_audio(b"\x00" * 640)

    # Verify transition and events
    assert listener.state == AssistantState.CAPTURING_COMMAND
    assert len(wake_events) == 1
    assert wake_events[0].wake_phrase == "hey eagle"
    assert any(e.mode == "command" for e in capture_events)

    listener.stop()


def test_continuous_listener_self_speech_suppression() -> None:
    """Verify that during SPEAKING, wake-word detection is suppressed to prevent self-triggering."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=True, wake_word_engine="mock"))
    event_bus = EventBus()
    wake_word = MockWakeWordEngine()
    tts_engine = MockTTSEngine()

    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
        tts_engine=tts_engine,
    )

    listener.start()
    listener.transition_to(AssistantState.CAPTURING_COMMAND)
    listener.transition_to(AssistantState.PROCESSING_COMMAND)
    listener.transition_to(AssistantState.SPEAKING)

    # Arm wake word trigger while SPEAKING
    wake_word.trigger()
    # Feed audio chunk while assistant is speaking
    listener.feed_simulated_audio(b"\x00" * 640)

    # State should remain SPEAKING; self-speech suppression ignored the chunk
    assert listener.state == AssistantState.SPEAKING

    # Now speech output finishes
    event_bus.publish(SpeechOutputFinishedEvent(text="Finished speaking"))

    # State transitions back to LISTENING_FOR_WAKE_WORD
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD
    listener.stop()


def test_continuous_listener_speech_interruption() -> None:
    """Verify interrupt() halts active TTS speech."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=True))
    tts_engine = MockTTSEngine()
    listener = ContinuousListener(config=config, tts_engine=tts_engine)

    listener.start()
    listener.transition_to(AssistantState.CAPTURING_COMMAND)
    listener.transition_to(AssistantState.PROCESSING_COMMAND)
    listener.transition_to(AssistantState.SPEAKING)

    listener.interrupt()
    assert tts_engine.stop_called is True
    listener.stop()


def test_continuous_listener_manual_capture() -> None:
    """Verify push-to-talk manual recording start and stop."""
    config = EagleConfig(voice=VoiceConfig(wake_word_enabled=False))
    event_bus = EventBus()
    transcriptions: list[str] = []
    event_bus.subscribe(SpeechTranscribedEvent, lambda e: transcriptions.append(e.text))

    mock_stt = MockSTTEngine(preset_text="open notepad")
    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        stt_engine=mock_stt,
    )

    listener.start()
    assert listener.state == AssistantState.IDLE

    # Trigger manual capture
    listener.start_manual_recording()
    assert listener.state == AssistantState.CAPTURING_COMMAND

    # Feed simulated command audio
    listener.feed_simulated_audio(b"\x7f\x10\x80\xef" * 4000)

    # Stop manual capture
    listener.stop_manual_recording()
    assert listener.state == AssistantState.PROCESSING_COMMAND

    # Allow worker thread a brief instant to transcribe
    time.sleep(0.3)
    assert len(transcriptions) >= 1
    assert "open notepad" in transcriptions[0]

    listener.stop()


def test_continuous_listener_command_timeout_processing() -> None:
    """Verify that command capture completes when timeout duration is reached."""
    config = EagleConfig(
        voice=VoiceConfig(
            wake_word_enabled=True,
            command_timeout_seconds=1.0,
            silence_timeout_seconds=0.5,
        )
    )
    event_bus = EventBus()
    mock_stt = MockSTTEngine(preset_text="system info")
    wake_word = MockWakeWordEngine()

    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
        stt_engine=mock_stt,
    )

    listener.start()
    wake_word.trigger()
    listener.feed_simulated_audio(b"\x00" * 640)
    assert listener.state == AssistantState.CAPTURING_COMMAND

    # Feed 1.5 seconds of simulated PCM to exceed command_timeout_seconds (1.0s)
    # 1.5s at 16kHz mono = 24000 samples = 48000 bytes
    listener.feed_simulated_audio(b"\x7f\x10\x80\xef" * 12000)

    # Should have transitioned to PROCESSING_COMMAND
    assert listener.state in (
        AssistantState.PROCESSING_COMMAND,
        AssistantState.LISTENING_FOR_WAKE_WORD,
    )
    listener.stop()
