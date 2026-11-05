"""Unit tests for EAGLE PySide6 desktop interface components, widgets, and EventBus bridge."""

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QLabel

from eagle.core.config import EagleConfig
from eagle.core.events import (
    AudioLevelEvent,
    ErrorOccurredEvent,
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    ToolExecutionCompletedEvent,
)
from eagle.services.ai_provider import AIOrchestrator, MockAIProvider
from eagle.services.command_router import CommandRouter
from eagle.services.continuous_listener import AssistantState, ContinuousListener
from eagle.services.stt import MockSTTEngine
from eagle.services.tts import MockTTSEngine
from eagle.services.wake_word import MockWakeWordEngine
from eagle.tools.registry import ToolRegistry
from eagle.ui.bridge import EventBusQtBridge
from eagle.ui.conversation import ConversationFeedWidget, MessageBubble, ToolExecutionCard
from eagle.ui.input_bar import InputBarWidget
from eagle.ui.main_window import MainWindow
from eagle.ui.settings_dialog import SettingsDialog
from eagle.ui.status_panel import StatusPanelWidget
from eagle.ui.theme import PALETTE, get_eagle_stylesheet
from eagle.ui.visualizer import AudioVisualizerWidget, MicrophoneIndicatorWidget


def test_theme_palette_and_stylesheet() -> None:
    """Verify EAGLE theme palette colors and generated stylesheet rules."""
    assert PALETTE.BG_BASE == "#0B0E14"
    assert PALETTE.ACCENT_CYAN == "#00E5FF"
    assert PALETTE.ACCENT_GOLD == "#FFB300"
    assert PALETTE.ACCENT_GREEN == "#00E676"
    assert PALETTE.ACCENT_RED == "#FF5252"

    stylesheet = get_eagle_stylesheet()
    assert "QMainWindow" in stylesheet
    assert PALETTE.BG_BASE in stylesheet
    assert PALETTE.ACCENT_CYAN in stylesheet
    assert "#HeaderBar" in stylesheet
    assert "#MicButton" in stylesheet


def test_microphone_indicator_widget(qapp: Any) -> None:
    """Verify MicrophoneIndicatorWidget state transitions and click signals."""
    indicator = MicrophoneIndicatorWidget()
    assert indicator.current_state == AssistantState.IDLE.value
    assert "Idle" in indicator._label.text()

    # Transition to LISTENING_FOR_WAKE_WORD
    indicator.set_state(AssistantState.LISTENING_FOR_WAKE_WORD.value)
    assert indicator.current_state == AssistantState.LISTENING_FOR_WAKE_WORD.value
    assert "Hey EAGLE" in indicator._label.text()

    # Transition to CAPTURING_COMMAND
    indicator.set_state(AssistantState.CAPTURING_COMMAND.value)
    assert indicator.current_state == AssistantState.CAPTURING_COMMAND.value
    assert "Listening to Command" in indicator._label.text()

    # Transition to PROCESSING_COMMAND
    indicator.set_state(AssistantState.PROCESSING_COMMAND.value)
    assert "Thinking" in indicator._label.text()

    # Click signal emission
    clicks: list[bool] = []
    indicator.clicked.connect(lambda: clicks.append(True))
    indicator.mousePressEvent(None)  # type: ignore[arg-type]
    assert len(clicks) == 1


def test_audio_visualizer_widget(qapp: Any) -> None:
    """Verify AudioVisualizerWidget amplitude updates and decay calculation."""
    visualizer = AudioVisualizerWidget(bar_count=20)
    assert visualizer.bar_count == 20
    assert len(visualizer._current_levels) == 20

    # Set high amplitude (1.0)
    visualizer.set_amplitude(1.0)
    assert visualizer._current_amplitude == 1.0
    assert any(level > 0.05 for level in visualizer._target_levels)

    # Frame tick interpolates and decays smoothly
    visualizer._on_animation_frame()
    assert any(level > 0.05 for level in visualizer._current_levels)

    # Low amplitude clamps cleanly
    visualizer.set_amplitude(-0.5)
    assert visualizer._current_amplitude == 0.0


def test_message_bubble(qapp: Any) -> None:
    """Verify user and assistant MessageBubble construction and styling."""
    user_bubble = MessageBubble(text="Open calculator", is_user=True, timestamp="12:00")
    assert user_bubble.is_user is True
    assert "You" in user_bubble.findChild(QLabel).text()  # type: ignore[union-attr]

    assistant_bubble = MessageBubble(
        text="Launching calculator now.", is_user=False, timestamp="12:01"
    )
    assert assistant_bubble.is_user is False
    assert "EAGLE" in assistant_bubble.findChild(QLabel).text()  # type: ignore[union-attr]


def test_tool_execution_card(qapp: Any) -> None:
    """Verify ToolExecutionCard formatting, argument display, and status badge."""
    card = ToolExecutionCard(
        tool_name="launch_app",
        arguments={"application_name": "notepad"},
        result="Successfully launched Notepad.",
        success=True,
        duration=0.045,
    )
    labels = [lbl.text() for lbl in card.findChildren(QLabel)]
    assert any("launch_app" in t for t in labels)
    assert any("COMPLETED" in t for t in labels)
    assert any("notepad" in t for t in labels)
    assert any("Successfully launched Notepad" in t for t in labels)

    failed_card = ToolExecutionCard(
        tool_name="open_website",
        arguments={"url": "ftp://bad.com"},
        result="URL scheme 'ftp' not allowed.",
        success=False,
        duration=0.010,
    )
    failed_labels = [lbl.text() for lbl in failed_card.findChildren(QLabel)]
    assert any("FAILED" in t for t in failed_labels)


def test_conversation_feed_widget(qapp: Any) -> None:
    """Verify adding messages and cards to ConversationFeedWidget and clearing."""
    feed = ConversationFeedWidget()
    assert feed._layout.count() == 1  # Only trailing stretch item initially

    feed.add_user_message("Hello EAGLE")
    assert feed._layout.count() == 2

    feed.add_assistant_message("Greetings! How can I help?")
    assert feed._layout.count() == 3

    feed.add_tool_card("system_info", {}, "CPU: 12%", True, 0.02)
    assert feed._layout.count() == 4

    feed.clear_feed()
    assert feed._layout.count() == 1  # All items removed except trailing stretch


def test_status_panel_widget(qapp: Any) -> None:
    """Verify StatusPanelWidget state updates, telemetry refresh, and labels."""
    config = EagleConfig()
    panel = StatusPanelWidget(config=config)

    panel.update_state(AssistantState.LISTENING_FOR_WAKE_WORD.value)
    assert "LISTENING" in panel._state_val.text()

    panel.update_state(AssistantState.CAPTURING_COMMAND.value)
    assert "CAPTURING" in panel._state_val.text()

    panel.update_state(AssistantState.SPEAKING.value)
    assert "SPEAKING" in panel._state_val.text()

    # Telemetry refresh does not raise and sets non-negative values
    panel.refresh_telemetry()
    assert panel._cpu_bar.value() >= 0
    assert panel._ram_bar.value() >= 0


def test_input_bar_widget(qapp: Any) -> None:
    """Verify InputBarWidget text typing, send button state, and signal emission."""
    input_bar = InputBarWidget()
    assert input_bar._send_btn.isEnabled() is False

    # Typing enables send button
    input_bar._input_field.setText("What is the battery level?")
    assert input_bar._send_btn.isEnabled() is True

    # Submitting emits signal and clears input field
    submitted_texts: list[str] = []
    input_bar.text_submitted.connect(lambda t: submitted_texts.append(t))
    input_bar._on_submit()

    assert len(submitted_texts) == 1
    assert submitted_texts[0] == "What is the battery level?"
    assert input_bar._input_field.text() == ""
    assert input_bar._send_btn.isEnabled() is False

    # Mic toggle signal
    mic_events: list[bool] = []
    input_bar.mic_toggled.connect(lambda: mic_events.append(True))
    input_bar._mic_btn.click()
    assert len(mic_events) == 1

    # Clear requested signal
    clear_events: list[bool] = []
    input_bar.clear_requested.connect(lambda: clear_events.append(True))
    input_bar._clear_btn.click()
    assert len(clear_events) == 1


def test_settings_dialog_save(qapp: Any, tmp_path: Path) -> None:
    """Verify SettingsDialog modifies configuration and saves preferences to disk."""
    config = EagleConfig()
    dialog = SettingsDialog(config=config, config_path=tmp_path / "config.json")

    # Modify settings in UI widgets
    dialog._ww_enabled.setChecked(True)
    dialog._ww_phrase.setText("hey assistant")
    dialog._ww_sens.setValue(75)
    dialog._ai_provider.setCurrentText("ollama")
    dialog._ai_model.setText("llama3.2")
    dialog._confirm_actions.setChecked(False)

    saved_configs: list[EagleConfig] = []
    dialog.settings_saved.connect(lambda c: saved_configs.append(c))

    # Trigger save
    dialog._save_settings()

    assert len(saved_configs) == 1
    updated = saved_configs[0]
    assert updated.audio.wake_word_enabled is True
    assert updated.audio.wake_word_phrase == "hey assistant"
    assert updated.audio.wake_word_sensitivity == 0.75
    assert updated.ai.provider == "ollama"
    assert updated.ai.model_name == "llama3.2"
    assert updated.security.confirm_sensitive_actions is False


def test_event_bus_qt_bridge(qapp: Any) -> None:
    """Verify EventBusQtBridge receives EventBus events and forwards them to Qt signals."""
    event_bus = EventBus()
    bridge = EventBusQtBridge(event_bus)

    audio_levels: list[float] = []
    state_changes: list[tuple[str, str, str]] = []
    transcriptions: list[tuple[str, float]] = []
    speech_outputs: list[str] = []
    tool_events: list[tuple[str, bool, str, float]] = []
    errors: list[tuple[str, str]] = []

    bridge.sig_audio_level.connect(lambda a: audio_levels.append(a))
    bridge.sig_state_changed.connect(
        lambda old, new, reason: state_changes.append((old, new, reason))
    )
    bridge.sig_speech_transcribed.connect(lambda text, conf: transcriptions.append((text, conf)))
    bridge.sig_speech_output_requested.connect(lambda text: speech_outputs.append(text))
    bridge.sig_tool_completed.connect(
        lambda name, ok, res, dur: tool_events.append((name, ok, res, dur))
    )
    bridge.sig_error_occurred.connect(lambda msg, sub: errors.append((msg, sub)))

    # 1. Audio level
    event_bus.publish(AudioLevelEvent(amplitude=0.82))
    assert len(audio_levels) == 1
    assert audio_levels[0] == 0.82

    # 2. State change
    event_bus.publish(
        ListeningStateChangedEvent(
            old_state="IDLE", new_state="LISTENING_FOR_WAKE_WORD", reason="start"
        )
    )
    assert len(state_changes) == 1
    assert state_changes[0] == ("IDLE", "LISTENING_FOR_WAKE_WORD", "start")

    # 3. Speech transcribed
    event_bus.publish(SpeechTranscribedEvent(text="open edge", confidence=0.98))
    assert len(transcriptions) == 1
    assert transcriptions[0] == ("open edge", 0.98)

    # 4. Speech output requested
    event_bus.publish(SpeechOutputRequestedEvent(text="Opening Edge browser."))
    assert len(speech_outputs) == 1
    assert speech_outputs[0] == "Opening Edge browser."

    # 5. Tool completed
    event_bus.publish(
        ToolExecutionCompletedEvent(
            tool_name="launch_app",
            success=True,
            result="Launched app",
        )
    )
    assert len(tool_events) == 1
    assert tool_events[0][0] == "launch_app"
    assert tool_events[0][1] is True

    # 6. Error occurred
    event_bus.publish(ErrorOccurredEvent(error_type="NetworkError", message="Host unreachable"))
    assert len(errors) == 1
    assert errors[0] == ("Host unreachable", "NetworkError")

    # Detach bridge
    bridge.detach()
    event_bus.publish(AudioLevelEvent(amplitude=0.1))
    assert len(audio_levels) == 1  # No new event received after detach


def test_main_window_instantiation_and_lifecycle(qapp: Any) -> None:
    """Verify MainWindow integrates all UI sub-widgets and terminates cleanly."""
    config = EagleConfig()
    event_bus = EventBus()
    registry = ToolRegistry()
    mock_ai = MockAIProvider()
    orchestrator = AIOrchestrator(provider=mock_ai, tool_registry=registry, event_bus=event_bus)
    tts = MockTTSEngine()
    stt = MockSTTEngine()
    wake_word = MockWakeWordEngine()
    router = CommandRouter(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        ai_orchestrator=orchestrator,
    )
    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
        stt_engine=stt,
        tts_engine=tts,
        command_router=router,
    )

    window = MainWindow(
        config=config,
        event_bus=event_bus,
        command_router=router,
        ai_orchestrator=orchestrator,
        continuous_listener=listener,
    )

    assert window.windowTitle() == config.ui.window_title
    assert window.feed_widget is not None
    assert window.status_panel is not None
    assert window.input_bar is not None
    assert window.mic_indicator is not None
    assert window.visualizer_widget is not None

    # Initial greeting is populated
    assert window.feed_widget._layout.count() >= 2

    # Speech transcribed triggers user bubble
    window._on_speech_transcribed("open calculator", 0.95)
    assert window.feed_widget._layout.count() >= 3

    # Speech output triggers assistant bubble
    window._on_speech_output("Launching calculator.")
    assert window.feed_widget._layout.count() >= 4

    # Close window cleanly
    window.close()
    assert listener.is_active() is False
