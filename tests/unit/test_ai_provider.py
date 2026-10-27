"""Comprehensive unit tests for EAGLE AI reasoning engine, providers, and tool calling."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests
from pydantic import BaseModel
from pytest_mock import MockerFixture

from eagle.core.config import AIConfig, EagleConfig, SecurityConfig
from eagle.core.events import (
    AIResponseGeneratedEvent,
    EventBus,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    ToolExecutionCompletedEvent,
)
from eagle.core.exceptions import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    NetworkTimeoutError,
    RateLimitExceededError,
)
from eagle.main import register_default_tools
from eagle.services.ai_provider import (
    AIOrchestrator,
    ChatMessage,
    ConversationManager,
    MockAIProvider,
    OpenAICompatibleProvider,
    ToolCall,
    get_ai_provider,
)
from eagle.services.command_router import CommandRouter
from eagle.tools.base import BaseTool, EmptyParameters, ToolResult
from eagle.tools.registry import ToolRegistry

# =====================================================================
# ChatMessage & ConversationManager Tests
# =====================================================================


def test_chat_message_to_dict_formatting() -> None:
    """Verify ChatMessage serializes to OpenAI-compatible message schema."""
    user_msg = ChatMessage(role="user", content="Hello EAGLE")
    assert user_msg.to_dict() == {"role": "user", "content": "Hello EAGLE"}

    tool_call = ToolCall(id="call_abc", tool_name="launch_app", arguments={"app_name": "notepad"})
    assistant_msg = ChatMessage(role="assistant", content="Launching app", tool_calls=[tool_call])
    d_asst = assistant_msg.to_dict()
    assert d_asst["role"] == "assistant"
    assert d_asst["content"] == "Launching app"
    assert len(d_asst["tool_calls"]) == 1
    assert d_asst["tool_calls"][0]["id"] == "call_abc"
    assert d_asst["tool_calls"][0]["function"]["name"] == "launch_app"
    assert '{"app_name": "notepad"}' in d_asst["tool_calls"][0]["function"]["arguments"]

    tool_result_msg = ChatMessage(
        role="tool", content="Success", tool_call_id="call_abc", name="launch_app"
    )
    d_tool = tool_result_msg.to_dict()
    assert d_tool["role"] == "tool"
    assert d_tool["content"] == "Success"
    assert d_tool["tool_call_id"] == "call_abc"
    assert d_tool["name"] == "launch_app"


def test_conversation_manager_pruning() -> None:
    """Verify ConversationManager limits history size while preserving the system prompt."""
    cm = ConversationManager(system_prompt="You are EAGLE.", max_turns=2)
    assert len(cm.get_messages()) == 1
    assert cm.get_messages()[0].role == "system"

    # Add 5 conversational turns (10 messages + 1 system = 11 total)
    for i in range(5):
        cm.add_user_message(f"User message {i}")
        cm.add_assistant_message(f"Assistant message {i}")

    msgs = cm.get_messages()
    # max_messages = 1 + (max_turns * 2) = 1 + (2 * 2) = 5 messages
    assert len(msgs) == 5
    assert msgs[0].role == "system"
    assert msgs[0].content == "You are EAGLE."
    # The oldest turns were pruned; newest turns remain
    assert msgs[-2].content == "User message 4"
    assert msgs[-1].content == "Assistant message 4"


def test_conversation_manager_clear() -> None:
    """Verify ConversationManager reset clears history back to system prompt."""
    cm = ConversationManager(system_prompt="Base prompt", max_turns=5)
    cm.add_user_message("Query 1")
    cm.add_assistant_message("Answer 1")
    assert len(cm.get_messages()) == 3

    cm.clear()
    assert len(cm.get_messages()) == 1
    assert cm.get_messages()[0].role == "system"
    assert cm.get_messages()[0].content == "Base prompt"


# =====================================================================
# MockAIProvider Tests
# =====================================================================


def test_mock_ai_provider_conversational_responses() -> None:
    """Verify MockAIProvider generates conversational replies offline."""
    provider = MockAIProvider()
    assert provider.is_available() is True

    # Identity query
    r_id = provider.generate_response([ChatMessage(role="user", content="Who are you?")])
    assert "EAGLE" in (r_id.content or "")
    assert r_id.finish_reason == "stop"
    assert len(r_id.tool_calls) == 0

    # Greeting
    r_hi = provider.generate_response([ChatMessage(role="user", content="Hello EAGLE")])
    assert "Greetings" in (r_hi.content or "")

    # Help
    r_help = provider.generate_response([ChatMessage(role="user", content="help")])
    assert "approved apps" in (r_help.content or "")


def test_mock_ai_provider_tool_call_generation() -> None:
    """Verify MockAIProvider detects command triggers and emits structured tool calls."""
    provider = MockAIProvider()
    tools_spec = [{"type": "function", "function": {"name": "launch_app"}}]

    # App launch
    r_app = provider.generate_response(
        [ChatMessage(role="user", content="Open notepad")], tools=tools_spec
    )
    assert len(r_app.tool_calls) == 1
    assert r_app.tool_calls[0].tool_name == "launch_app"
    assert r_app.tool_calls[0].arguments["app_name"] == "notepad"
    assert r_app.finish_reason == "tool_calls"

    # Web search
    r_search = provider.generate_response(
        [ChatMessage(role="user", content="search for quantum computing")], tools=tools_spec
    )
    assert len(r_search.tool_calls) == 1
    assert r_search.tool_calls[0].tool_name == "web_search"
    assert r_search.tool_calls[0].arguments["query"] == "quantum computing"

    # System telemetry
    r_sys = provider.generate_response(
        [ChatMessage(role="user", content="check battery level")], tools=tools_spec
    )
    assert len(r_sys.tool_calls) == 1
    assert r_sys.tool_calls[0].tool_name == "system_info"
    assert r_sys.tool_calls[0].arguments["topic"] == "battery"


def test_mock_ai_provider_tool_result_synthesis() -> None:
    """Verify MockAIProvider summarizes tool results passed with role='tool'."""
    provider = MockAIProvider()
    messages = [
        ChatMessage(role="user", content="check battery"),
        ChatMessage(
            role="assistant",
            tool_calls=[
                ToolCall(id="tc_1", tool_name="system_info", arguments={"topic": "battery"})
            ],
        ),
        ChatMessage(
            role="tool",
            content="Battery: 85% (Plugged in, 2h remaining)",
            tool_call_id="tc_1",
            name="system_info",
        ),
    ]
    response = provider.generate_response(messages)
    assert response.finish_reason == "stop"
    assert "Battery: 85%" in (response.content or "")


def test_mock_ai_provider_simulated_errors() -> None:
    """Verify MockAIProvider can simulate various failure modes for testing."""
    for error_type, expected_exc in [
        ("auth", AuthenticationError),
        ("timeout", NetworkTimeoutError),
        ("rate_limit", RateLimitExceededError),
        ("unavailable", ModelUnavailableError),
        ("invalid_json", InvalidResponseError),
    ]:
        p = MockAIProvider(simulate_error=error_type)
        with pytest.raises(expected_exc):
            p.generate_response([ChatMessage(role="user", content="test")])


# =====================================================================
# OpenAICompatibleProvider Tests
# =====================================================================


def test_openai_provider_credential_resolution(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify API key is resolved from provider-specific env var, generic env var, or config."""
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("AI_API_KEY", raising=False)

    # 1. Missing credentials
    cfg = AIConfig(provider="openai")
    p1 = OpenAICompatibleProvider(cfg)
    assert p1.is_available() is False
    with pytest.raises(AuthenticationError) as exc_info:
        p1.generate_response([ChatMessage(role="user", content="test")])
    assert "OPENAI_API_KEY" in str(exc_info.value)

    # 2. Config override
    cfg_with_key = AIConfig(provider="openai", api_key="sk-config-override")
    p2 = OpenAICompatibleProvider(cfg_with_key)
    assert p2.is_available() is True
    assert p2.api_key == "sk-config-override"

    # 3. Environment variable
    monkeypatch.setenv("OPENAI_API_KEY", "sk-env-key-12345")
    p3 = OpenAICompatibleProvider(cfg)
    assert p3.is_available() is True
    assert p3.api_key == "sk-env-key-12345"

    # 4. Ollama requires no key
    cfg_ollama = AIConfig(provider="ollama")
    p_ollama = OpenAICompatibleProvider(cfg_ollama)
    assert p_ollama.is_available() is True


def test_openai_provider_successful_conversational_response(mocker: MockerFixture) -> None:
    """Verify HTTP 200 conversational response is parsed cleanly."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"role": "assistant", "content": "The weather is sunny."},
                "finish_reason": "stop",
            }
        ]
    }
    mocker.patch("requests.post", return_value=mock_response)

    cfg = AIConfig(provider="openai", api_key="test-key")
    provider = OpenAICompatibleProvider(cfg)

    response = provider.generate_response([ChatMessage(role="user", content="How is the weather?")])
    assert response.content == "The weather is sunny."
    assert response.finish_reason == "stop"
    assert len(response.tool_calls) == 0


def test_openai_provider_structured_tool_calls(mocker: MockerFixture) -> None:
    """Verify HTTP 200 response with function tool calls is parsed into ToolCall objects."""
    mock_response = MagicMock(spec=requests.Response)
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_123",
                            "type": "function",
                            "function": {
                                "name": "launch_app",
                                "arguments": '{"app_name": "calculator"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }
    mocker.patch("requests.post", return_value=mock_response)

    cfg = AIConfig(provider="openai", api_key="test-key")
    provider = OpenAICompatibleProvider(cfg)

    response = provider.generate_response([ChatMessage(role="user", content="Launch calc")])
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].id == "call_123"
    assert response.tool_calls[0].tool_name == "launch_app"
    assert response.tool_calls[0].arguments == {"app_name": "calculator"}
    assert response.finish_reason == "tool_calls"


def test_openai_provider_network_and_http_errors(mocker: MockerFixture) -> None:
    """Verify proper exception mapping for timeouts, connection drops, and HTTP errors."""
    cfg = AIConfig(provider="openai", api_key="test-key")
    provider = OpenAICompatibleProvider(cfg)

    # 1. Timeout
    mocker.patch("requests.post", side_effect=requests.exceptions.Timeout("Connection timed out"))
    with pytest.raises(NetworkTimeoutError):
        provider.generate_response([ChatMessage(role="user", content="test")])

    # 2. Connection failure
    mocker.patch("requests.post", side_effect=requests.exceptions.ConnectionError("DNS failure"))
    with pytest.raises(ModelUnavailableError):
        provider.generate_response([ChatMessage(role="user", content="test")])

    # 3. HTTP 401 Unauthorized
    resp_401 = MagicMock(status_code=401, text="Invalid API key")
    mocker.patch("requests.post", return_value=resp_401)
    with pytest.raises(AuthenticationError):
        provider.generate_response([ChatMessage(role="user", content="test")])

    # 4. HTTP 429 Rate Limit
    resp_429 = MagicMock(status_code=429, text="Rate limit reached")
    mocker.patch("requests.post", return_value=resp_429)
    with pytest.raises(RateLimitExceededError):
        provider.generate_response([ChatMessage(role="user", content="test")])

    # 5. HTTP 500 Server Error
    resp_500 = MagicMock(status_code=500, text="Internal server error")
    mocker.patch("requests.post", return_value=resp_500)
    with pytest.raises(AIProviderError):
        provider.generate_response([ChatMessage(role="user", content="test")])

    # 6. Malformed JSON
    resp_bad_json = MagicMock(status_code=200, text="not json")
    resp_bad_json.json.side_effect = ValueError("Invalid JSON")
    mocker.patch("requests.post", return_value=resp_bad_json)
    with pytest.raises(InvalidResponseError):
        provider.generate_response([ChatMessage(role="user", content="test")])


# =====================================================================
# AIOrchestrator Tests
# =====================================================================


def test_ai_orchestrator_conversational_turn() -> None:
    """Verify AIOrchestrator processes a general question and fires events."""
    event_bus = EventBus()
    received_speech: list[str] = []
    received_ai_resp: list[str] = []

    event_bus.subscribe(SpeechOutputRequestedEvent, lambda e: received_speech.append(e.text))
    event_bus.subscribe(AIResponseGeneratedEvent, lambda e: received_ai_resp.append(e.text))

    provider = MockAIProvider()
    orchestrator = AIOrchestrator(
        event_bus=event_bus,
        provider=provider,
    )

    answer = orchestrator.process_query("Who are you?")
    assert "EAGLE" in answer
    assert len(received_speech) == 1
    assert "EAGLE" in received_speech[0]
    assert len(received_ai_resp) == 1


def test_ai_orchestrator_tool_calling_loop(mocker: MockerFixture) -> None:
    """Verify full loop: user query -> AI tool call -> ToolRegistry execution -> AI final summary."""
    mock_process = mocker.MagicMock(spec=subprocess.Popen)
    mock_process.pid = 9876
    mocker.patch("subprocess.Popen", return_value=mock_process)

    config = EagleConfig(security=SecurityConfig(allowed_applications={"notepad": "notepad.exe"}))
    event_bus = EventBus()
    tool_registry = ToolRegistry()
    register_default_tools(tool_registry, config)

    completed_events: list[ToolExecutionCompletedEvent] = []
    event_bus.subscribe(ToolExecutionCompletedEvent, lambda e: completed_events.append(e))

    provider = MockAIProvider()
    orchestrator = AIOrchestrator(
        config=config,
        tool_registry=tool_registry,
        event_bus=event_bus,
        provider=provider,
    )

    # Process query that triggers MockAIProvider to call 'launch_app'
    response = orchestrator.process_query("Open notepad")

    # Verify tool was actually executed
    assert len(completed_events) == 1
    assert completed_events[0].tool_name == "launch_app"
    assert completed_events[0].success is True

    # Verify final response reflects tool execution outcome
    assert "executed launch_app" in response
    assert "launched successfully" in response


def test_ai_orchestrator_blocks_unregistered_tools() -> None:
    """Verify AI tool call to an unregistered or disallowed tool is securely blocked."""
    tool_registry = ToolRegistry()
    # ToolRegistry is empty - no tools registered!

    # Create a custom provider that returns an unknown tool call
    mock_provider = MagicMock(spec=MockAIProvider)
    mock_provider.is_available.return_value = True
    mock_provider.generate_response.side_effect = [
        # 1st turn: AI requests unauthorized tool
        MagicMock(
            content=None,
            tool_calls=[ToolCall(id="call_x", tool_name="format_c_drive", arguments={})],
        ),
        # 2nd turn: AI receives error and acknowledges
        MagicMock(
            content="I am unable to format the drive because it is not an approved tool.",
            tool_calls=[],
        ),
    ]

    orchestrator = AIOrchestrator(
        tool_registry=tool_registry,
        provider=mock_provider,
    )

    final_resp = orchestrator.process_query("Format my drive")
    assert "unable" in final_resp

    # Verify tool result recorded in conversation contained security block notice
    messages = orchestrator.conversation.get_messages()
    tool_results = [m for m in messages if m.role == "tool"]
    assert len(tool_results) == 1
    assert "Security Error: Tool 'format_c_drive' is not in the approved EAGLE allowlist" in (
        tool_results[0].content or ""
    )


def test_ai_orchestrator_sensitive_action_confirmation(tmp_path: Path) -> None:
    """Verify sensitive tools requiring confirmation are blocked if unconfirmed."""

    class DummySensitiveTool(BaseTool):
        name = "dangerous_action"
        description = "Dangerous operation"
        parameters_schema = EmptyParameters
        is_sensitive = True

        def run(self, validated_args: BaseModel) -> ToolResult:
            return ToolResult(success=True, output="Executed danger")

    tool_registry = ToolRegistry(confirm_sensitive_actions=True)
    tool_registry.register(DummySensitiveTool())

    mock_provider = MagicMock(spec=MockAIProvider)
    mock_provider.is_available.return_value = True
    mock_provider.generate_response.side_effect = [
        MagicMock(
            content=None,
            tool_calls=[ToolCall(id="c_sens", tool_name="dangerous_action", arguments={})],
        ),
        MagicMock(
            content="The action requires user confirmation.",
            tool_calls=[],
        ),
    ]

    orchestrator = AIOrchestrator(
        tool_registry=tool_registry,
        provider=mock_provider,
    )

    orchestrator.process_query("Do dangerous action")
    messages = orchestrator.conversation.get_messages()
    tool_results = [m for m in messages if m.role == "tool"]
    assert "requires explicit user confirmation" in (tool_results[0].content or "")


def test_ai_orchestrator_graceful_error_handling() -> None:
    """Verify orchestrator returns helpful setup message when provider raises AuthenticationError."""
    failing_provider = MockAIProvider(simulate_error="auth")
    orchestrator = AIOrchestrator(provider=failing_provider)

    result = orchestrator.process_query("What is AI?")
    assert "Authentication Error" in result
    assert "Please configure a valid API key" in result


# =====================================================================
# Factory & CommandRouter End-to-End Tests
# =====================================================================


def test_get_ai_provider_factory() -> None:
    """Verify factory returns appropriate provider implementation."""
    p_mock = get_ai_provider(EagleConfig(ai=AIConfig(provider="mock")))
    assert isinstance(p_mock, MockAIProvider)

    p_openai = get_ai_provider(EagleConfig(ai=AIConfig(provider="openai")))
    assert isinstance(p_openai, OpenAICompatibleProvider)

    p_groq = get_ai_provider(EagleConfig(ai=AIConfig(provider="groq")))
    assert isinstance(p_groq, OpenAICompatibleProvider)

    p_ollama = get_ai_provider(EagleConfig(ai=AIConfig(provider="ollama")))
    assert isinstance(p_ollama, OpenAICompatibleProvider)


def test_command_router_ai_fallback_and_conversation() -> None:
    """Verify CommandRouter routes conversational speech to AIOrchestrator when available."""
    event_bus = EventBus()
    spoken_messages: list[str] = []
    event_bus.subscribe(SpeechOutputRequestedEvent, lambda e: spoken_messages.append(e.text))

    config = EagleConfig(ai=AIConfig(provider="mock"))
    orchestrator = AIOrchestrator(config=config, event_bus=event_bus)
    _router = CommandRouter(config=config, event_bus=event_bus, ai_orchestrator=orchestrator)

    # 1. Conversational voice transcription
    event_bus.publish(SpeechTranscribedEvent(text="who are you?"))
    assert len(spoken_messages) >= 1
    assert any("EAGLE" in msg for msg in spoken_messages)

    # 2. When AI is unavailable, conversation query emits diagnostic message
    bus_offline = EventBus()
    offline_messages: list[str] = []
    bus_offline.subscribe(SpeechOutputRequestedEvent, lambda e: offline_messages.append(e.text))

    unavail_orchestrator = MagicMock(spec=AIOrchestrator)
    unavail_orchestrator.is_available.return_value = False
    _router_offline = CommandRouter(
        config=config, event_bus=bus_offline, ai_orchestrator=unavail_orchestrator
    )

    bus_offline.publish(SpeechTranscribedEvent(text="explain black holes"))
    assert len(offline_messages) == 1
    assert "EAGLE AI reasoning is currently unavailable" in offline_messages[0]
