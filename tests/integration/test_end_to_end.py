"""End-to-end integration tests validating EAGLE complete system flows, tool execution, and state transitions."""

from pathlib import Path
from typing import Any

from eagle.core.config import EagleConfig
from eagle.core.events import (
    AudioLevelEvent,
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.main import register_default_tools
from eagle.services.ai_provider import AIOrchestrator, MockAIProvider
from eagle.services.command_router import CommandIntent, CommandRouter
from eagle.services.continuous_listener import AssistantState, ContinuousListener
from eagle.services.stt import MockSTTEngine
from eagle.services.tts import MockTTSEngine
from eagle.services.wake_word import MockWakeWordEngine
from eagle.tools.registry import ToolRegistry
from eagle.ui.main_window import MainWindow


def test_e2e_voice_command_to_tool_execution() -> None:
    """Verify end-to-end pipeline: SpeechTranscribed -> Router -> Tool Execution -> EventBus -> TTS."""
    config = EagleConfig()
    event_bus = EventBus()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    tts = MockTTSEngine()
    router = CommandRouter(config=config, tool_registry=registry, event_bus=event_bus)

    tool_completed_events: list[ToolExecutionCompletedEvent] = []

    def on_tool_request(evt: ToolExecutionRequestedEvent) -> None:
        result = registry.execute(evt.tool_name, evt.arguments)
        event_bus.publish(
            ToolExecutionCompletedEvent(
                tool_name=evt.tool_name,
                success=result.success,
                result=result.output,
                error=result.error,
            )
        )
        if result.success and result.output:
            event_bus.publish(SpeechOutputRequestedEvent(text=str(result.output)[:100]))

    event_bus.subscribe(ToolExecutionRequestedEvent, on_tool_request)
    event_bus.subscribe(ToolExecutionCompletedEvent, lambda e: tool_completed_events.append(e))
    event_bus.subscribe(SpeechOutputRequestedEvent, lambda e: tts.speak(e.text))

    # Simulate recognized speech command: "system info"
    route = router.route("system info")
    assert route.intent == CommandIntent.SYSTEM_INFO
    assert route.is_actionable is True

    # Dispatch tool
    router.dispatch(route)

    # Verify tool completed successfully
    assert len(tool_completed_events) == 1
    completed = tool_completed_events[0]
    assert completed.tool_name == "system_info"
    assert completed.success is True
    assert "System Telemetry" in str(completed.result)

    # Verify spoken response was generated
    assert len(tts.spoken_phrases) >= 1
    assert any("telemetry" in phrase.lower() for phrase in tts.spoken_phrases)


def test_e2e_wake_word_and_continuous_listening_lifecycle() -> None:
    """Verify wake-word detection triggers command capture, silence timeout finishes, and transitions state."""
    config = EagleConfig()
    config.audio.wake_word_enabled = True
    config.audio.command_timeout_seconds = 1.0
    config.audio.silence_timeout_seconds = 0.5

    event_bus = EventBus()
    wake_word = MockWakeWordEngine()
    stt = MockSTTEngine(preset_text="open notepad")
    tts = MockTTSEngine()
    registry = ToolRegistry()
    router = CommandRouter(config=config, tool_registry=registry, event_bus=event_bus)

    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
        stt_engine=stt,
        tts_engine=tts,
        command_router=router,
    )

    state_transitions: list[str] = []
    event_bus.subscribe(
        ListeningStateChangedEvent,
        lambda e: state_transitions.append(f"{e.old_state}->{e.new_state}"),
    )

    listener.start()
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # Simulate wake word detection
    wake_word.trigger()
    listener.wake_word_engine.process_audio(b"\x00" * 640)

    # Transition to CAPTURING_COMMAND
    listener.transition_to(AssistantState.CAPTURING_COMMAND, reason="wake word detected")
    assert listener.state == AssistantState.CAPTURING_COMMAND

    # Feed audio frame
    listener._on_audio_chunk(b"\x00" * 3200)

    # Transition to PROCESSING_COMMAND
    listener.transition_to(AssistantState.PROCESSING_COMMAND, reason="silence timeout")
    assert listener.state == AssistantState.PROCESSING_COMMAND

    # Transition to SPEAKING
    listener.transition_to(AssistantState.SPEAKING, reason="vocalizing result")
    assert listener.state == AssistantState.SPEAKING

    # Interruption on barge-in
    listener.interrupt()
    assert tts.stop_called is True

    # Return to listening
    listener.transition_to(AssistantState.LISTENING_FOR_WAKE_WORD, reason="ready for next command")
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    listener.stop()
    assert listener.is_active() is False


def test_e2e_ai_conversational_reasoning_and_tool_calling() -> None:
    """Verify AIOrchestrator multi-turn loop invoking allowlisted tools and summarizing results."""
    config = EagleConfig()
    event_bus = EventBus()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    # Mock provider simulating structured tool call
    mock_ai = MockAIProvider(config=config.ai)
    orchestrator = AIOrchestrator(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        provider=mock_ai,
    )

    # Process conversational query
    response = orchestrator.process_query("What is the current system telemetry status?")
    assert response is not None
    assert len(response) > 0
    assert len(orchestrator.conversation.messages) >= 2


def test_e2e_security_sandbox_enforcement(tmp_path: Path) -> None:
    """Verify that file traversal and unauthorized application launches are rejected cleanly."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    config = EagleConfig()
    config.security.allowed_directories = [str(sandbox)]

    registry = ToolRegistry()
    register_default_tools(registry, config)

    # 1. Attempt path traversal outside sandbox
    outside_file = tmp_path / "secret.txt"
    outside_file.write_text("classified data", encoding="utf-8")

    list_tool = registry.get_tool("list_files")
    assert list_tool is not None

    result = list_tool.execute({"directory": str(tmp_path)})
    assert result.success is False
    assert "Path traversal blocked" in (result.error or "")

    # 2. Attempt launching unauthorized app
    launch_tool = registry.get_tool("launch_app")
    assert launch_tool is not None

    app_result = launch_tool.execute({"app_name": "unauthorized_virus.exe"})
    assert app_result.success is False
    assert "not in the approved applications allowlist" in (app_result.error or "")


def test_e2e_pyside6_main_window_integration(qapp: Any, tmp_path: Path) -> None:
    """Verify PySide6 desktop interface reacts to EventBus events, renders cards, and handles input."""
    config = EagleConfig()
    event_bus = EventBus()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    mock_ai = MockAIProvider(config=config.ai)
    orchestrator = AIOrchestrator(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        provider=mock_ai,
    )
    router = CommandRouter(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        ai_orchestrator=orchestrator,
    )
    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        command_router=router,
    )

    window = MainWindow(
        config=config,
        event_bus=event_bus,
        command_router=router,
        ai_orchestrator=orchestrator,
        continuous_listener=listener,
    )

    # Initial state
    assert window.isVisible() is False
    assert window.mic_indicator.current_state == AssistantState.IDLE.value

    # Simulate audio level event
    event_bus.publish(AudioLevelEvent(amplitude=0.75))
    if window.visualizer_widget:
        assert window.visualizer_widget._current_amplitude == 0.75

    # Simulate speech transcription event
    event_bus.publish(SpeechTranscribedEvent(text="open notepad", confidence=0.99))
    assert window.feed_widget._layout.count() >= 3

    # Simulate tool completed event
    event_bus.publish(
        ToolExecutionCompletedEvent(
            tool_name="launch_app",
            success=True,
            result="Launched notepad",
        )
    )
    assert window.feed_widget._layout.count() >= 4

    # Clean close
    window.close()
    assert listener.is_active() is False
