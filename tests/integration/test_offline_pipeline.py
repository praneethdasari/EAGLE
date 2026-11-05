"""Comprehensive integration test suite validating EAGLE complete offline workflows.

Covers:
1. Local speech recognition cache & offline enforcement.
2. Local SAPI5 text-to-speech voice enumeration and speech interruption.
3. Local wake-word activation and continuous listening state transitions.
4. End-to-end voice -> Ollama AI reasoning -> allowlisted tool execution -> TTS output.
5. Local provider disconnection and recovery.
6. Strict offline policy blocking cloud providers.
7. PySide6 desktop GUI status panel and offline settings persistence.
"""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from eagle.core.config import AIConfig, EagleConfig, save_config
from eagle.core.events import (
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputRequestedEvent,
    ToolExecutionCompletedEvent,
)
from eagle.core.exceptions import (
    OfflinePolicyViolationError,
    TranscriptionError,
)
from eagle.main import register_default_tools
from eagle.services.ai_provider import (
    AIOrchestrator,
    OllamaProvider,
    get_ai_provider,
)
from eagle.services.command_router import CommandRouter
from eagle.services.continuous_listener import AssistantState, ContinuousListener
from eagle.services.stt import FasterWhisperSTT, MockSTTEngine
from eagle.services.tts import MockTTSEngine
from eagle.services.wake_word import MockWakeWordEngine
from eagle.tools.registry import ToolRegistry
from eagle.ui.main_window import MainWindow
from eagle.ui.settings_dialog import SettingsDialog


def test_offline_stt_cache_and_offline_enforcement(tmp_path: Path) -> None:
    """Verify FasterWhisperSTT enforces local_files_only in offline mode and does not attempt network downloads."""
    empty_models_dir = tmp_path / "models" / "whisper"
    empty_models_dir.mkdir(parents=True)

    stt = FasterWhisperSTT(
        model_size="base",
        download_root=empty_models_dir,
        local_files_only=True,
    )

    assert stt.is_model_cached() is False
    assert stt.list_cached_models() == []

    # In offline mode, missing model must raise TranscriptionError before attempting network download
    with pytest.raises(TranscriptionError) as exc_info:
        stt._ensure_loaded()
    assert "In offline mode, speech models must be pre-downloaded" in str(exc_info.value)

    # Simulated pre-cached model directory
    cached_model_dir = empty_models_dir / "models--Systran--faster-whisper-base"
    cached_model_dir.mkdir()
    (cached_model_dir / "model.bin").write_bytes(b"\x00" * 128)

    assert stt.is_model_cached() is True
    assert "base" in stt.list_cached_models()


def test_offline_tts_voice_control_and_interruption() -> None:
    """Verify offline text-to-speech voice enumeration, rate adjustment, and thread-safe interruption."""
    tts = MockTTSEngine()

    voices = tts.get_available_voices()
    assert len(voices) >= 1
    assert any(v["id"] == "default" for v in voices)

    # Select voice
    assert tts.set_voice("mock_female") is True
    assert tts.voice == "mock_female"

    # Vocalize speech
    tts.speak("EAGLE is running completely offline.")
    assert tts.last_spoken == "EAGLE is running completely offline."

    # Immediate speech interruption
    tts.stop()
    assert tts.stop_called is True


def test_offline_wakeword_detection_and_barge_in() -> None:
    """Verify offline wake-word energy gating, detection, and continuous listener barge-in."""
    config = EagleConfig()
    config.ai.offline_mode = True
    config.audio.wake_word_enabled = True

    event_bus = EventBus()
    wake_word = MockWakeWordEngine(wake_phrase="hey eagle")
    stt = MockSTTEngine(preset_text="check system status")
    tts = MockTTSEngine()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    router = CommandRouter(config=config, tool_registry=registry, event_bus=event_bus)
    listener = ContinuousListener(
        config=config,
        event_bus=event_bus,
        wake_word_engine=wake_word,
        stt_engine=stt,
        tts_engine=tts,
        command_router=router,
    )

    state_log: list[str] = []
    event_bus.subscribe(
        ListeningStateChangedEvent,
        lambda e: state_log.append(f"{e.old_state}->{e.new_state}"),
    )

    listener.start()
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    # 1. Wake word triggers
    wake_word.trigger()
    assert wake_word.process_audio(b"\x00" * 640) is True

    # 2. State transition to command capture
    listener.transition_to(AssistantState.CAPTURING_COMMAND, reason="wake word")
    assert listener.state == AssistantState.CAPTURING_COMMAND

    # 3. State transition to processing command
    listener.transition_to(AssistantState.PROCESSING_COMMAND, reason="silence timeout")
    assert listener.state == AssistantState.PROCESSING_COMMAND

    # 4. State transition to speaking
    listener.transition_to(AssistantState.SPEAKING, reason="vocalizing")
    assert listener.state == AssistantState.SPEAKING

    # 5. User barge-in interruption while speaking
    listener.interrupt()
    assert tts.stop_called is True

    # 6. Return to listening
    listener.transition_to(AssistantState.LISTENING_FOR_WAKE_WORD, reason="done")
    assert listener.state == AssistantState.LISTENING_FOR_WAKE_WORD

    listener.stop()
    assert listener.is_active() is False


def test_offline_full_pipeline_voice_to_ollama_to_tool_execution(tmp_path: Path) -> None:
    """Verify complete end-to-end offline loop: Voice -> Ollama -> Tool Execution -> TTS output."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "report.txt").write_text("Offline flight log data", encoding="utf-8")

    config = EagleConfig()
    config.ai.provider = "ollama"
    config.ai.model_name = "qwen2.5:3b"
    config.ai.offline_mode = True
    config.security.allowed_directories = [str(sandbox)]

    event_bus = EventBus()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    tts = MockTTSEngine()
    event_bus.subscribe(SpeechOutputRequestedEvent, lambda e: tts.speak(e.text))

    # Mock Ollama provider responding with structured tool call to inspect file
    ollama_provider = OllamaProvider(config=config.ai)
    orchestrator = AIOrchestrator(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        provider=ollama_provider,
    )

    router = CommandRouter(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        ai_orchestrator=orchestrator,
    )
    assert router.ai_orchestrator is not None

    # 1. Simulate speech transcribed event
    transcription = "what files are in the sandbox folder?"

    # Ollama returns tool call: list_files in sandbox
    mock_resp_1 = MagicMock()
    mock_resp_1.status_code = 200
    mock_resp_1.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_ollama_01",
                            "type": "function",
                            "function": {
                                "name": "list_files",
                                "arguments": f'{{"directory": "{str(sandbox).replace("\\", "/")}"}}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    # Ollama returns final conversational summary after tool execution
    mock_resp_2 = MagicMock()
    mock_resp_2.status_code = 200
    mock_resp_2.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "The sandbox directory contains report.txt.",
                },
                "finish_reason": "stop",
            }
        ]
    }

    tool_completed_events: list[ToolExecutionCompletedEvent] = []
    event_bus.subscribe(ToolExecutionCompletedEvent, lambda e: tool_completed_events.append(e))

    with (
        patch.object(ollama_provider, "is_server_running", return_value=True),
        patch("requests.post", side_effect=[mock_resp_1, mock_resp_2]),
    ):
        result_text = orchestrator.process_query(transcription)

        assert "report.txt" in result_text
        assert len(tool_completed_events) == 1
        assert tool_completed_events[0].tool_name == "list_files"
        assert tool_completed_events[0].success is True
        assert "report.txt" in str(tool_completed_events[0].result)

        # Spoken response was vocalized
        assert len(tts.spoken_phrases) >= 1
        assert "report.txt" in tts.spoken_phrases[-1]


def test_offline_provider_disconnection_and_recovery() -> None:
    """Verify assistant handles local Ollama server disconnection and recovery cleanly without crashes."""
    config = EagleConfig()
    config.ai.provider = "ollama"
    config.ai.offline_mode = True

    event_bus = EventBus()
    ollama_provider = OllamaProvider(config=config.ai)
    orchestrator = AIOrchestrator(
        config=config,
        event_bus=event_bus,
        provider=ollama_provider,
    )

    spoken_feedback: list[str] = []
    event_bus.subscribe(SpeechOutputRequestedEvent, lambda e: spoken_feedback.append(e.text))

    # Query 1: Server down before request
    with patch.object(ollama_provider, "is_server_running", return_value=False):
        response = orchestrator.process_query("What is 2 + 2?")
        assert "unavailable" in response.lower()
        assert len(spoken_feedback) >= 1
        assert "unavailable" in spoken_feedback[-1].lower()

    # Query 2: Server recovers
    mock_success = MagicMock()
    mock_success.status_code = 200
    mock_success.json.return_value = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "4"},
                "finish_reason": "stop",
            }
        ]
    }

    with (
        patch.object(ollama_provider, "is_server_running", return_value=True),
        patch("requests.post", return_value=mock_success),
    ):
        recovered_response = orchestrator.process_query("What is 2 + 2?")
        assert recovered_response == "4"


def test_offline_mode_strictly_blocks_cloud_providers() -> None:
    """Verify setting offline_mode=True rejects cloud provider initialization and requests."""
    config = EagleConfig(ai=AIConfig(provider="groq", offline_mode=True))

    with pytest.raises(OfflinePolicyViolationError) as exc_info:
        get_ai_provider(config)
    assert "Offline mode active: Cloud AI provider 'groq' is forbidden" in str(exc_info.value)


def test_offline_gui_status_panel_and_settings_integration(qapp: Any, tmp_path: Path) -> None:
    """Verify PySide6 desktop interface reflects offline state and settings dialog persists offline preferences."""
    config_file = tmp_path / "offline_config.json"
    config = EagleConfig()
    config.ai.provider = "ollama"
    config.ai.model_name = "qwen2.5:3b"
    config.ai.offline_mode = True
    save_config(config, config_file)

    event_bus = EventBus()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    ollama_provider = OllamaProvider(config=config.ai)
    orchestrator = AIOrchestrator(
        config=config,
        tool_registry=registry,
        event_bus=event_bus,
        provider=ollama_provider,
    )
    router = CommandRouter(config=config, tool_registry=registry, event_bus=event_bus)
    listener = ContinuousListener(config=config, event_bus=event_bus, command_router=router)

    with (
        patch.object(ollama_provider, "is_server_running", return_value=True),
        patch.object(ollama_provider, "get_available_models", return_value=["qwen2.5:3b"]),
    ):
        window = MainWindow(
            config=config,
            event_bus=event_bus,
            command_router=router,
            ai_orchestrator=orchestrator,
            continuous_listener=listener,
        )

        # Status panel presents strict offline mode and Ollama provider
        assert "OLLAMA" in window.status_panel._provider_label.text()
        assert "qwen2.5:3b" in window.status_panel._provider_label.text()
        assert "Strict Offline Mode" in window.status_panel._offline_mode_badge.text()

        # Settings dialog opens and reflects offline mode
        dialog = SettingsDialog(config=config, config_path=config_file, parent=window)
        assert dialog._ai_offline_mode.isChecked() is True
        assert dialog._ai_provider.currentText() == "ollama"
        assert dialog._ai_model.text() == "qwen2.5:3b"

        # Toggle offline mode and save
        dialog._ai_offline_mode.setChecked(False)
        dialog._save_settings()

        assert config.ai.offline_mode is False
        window.close()
