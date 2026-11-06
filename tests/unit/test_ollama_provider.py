"""Unit tests for OllamaProvider, health diagnostics, and offline policy enforcement."""

from unittest.mock import MagicMock, patch

import pytest
import requests

from eagle.core.config import AIConfig, EagleConfig
from eagle.core.exceptions import (
    ModelUnavailableError,
    NetworkTimeoutError,
    OfflinePolicyViolationError,
)
from eagle.services.ai_provider import (
    AIOrchestrator,
    ChatMessage,
    OllamaProvider,
    OpenAICompatibleProvider,
    get_ai_provider,
)


def test_ollama_provider_initialization() -> None:
    """Verify OllamaProvider initializes with sensible local defaults and URL normalization."""
    cfg = AIConfig(provider="ollama")
    provider = OllamaProvider(config=cfg)
    assert provider.base_url == "http://localhost:11434"
    assert provider.model_name == "qwen2.5:3b"
    assert provider.timeout >= 60.0
    assert provider.offline_mode is False

    # Verify /v1 suffix is normalized out of base_url
    cfg_v1 = AIConfig(
        provider="ollama", base_url="http://localhost:11434/v1/", model_name="llama3.2"
    )
    provider_v1 = OllamaProvider(config=cfg_v1)
    assert provider_v1.base_url == "http://localhost:11434"
    assert provider_v1.model_name == "llama3.2"


def test_ollama_is_installed_detection() -> None:
    """Verify is_installed checks PATH and filesystem without raising exceptions."""
    result = OllamaProvider.is_installed()
    assert isinstance(result, bool)

    with patch("shutil.which", return_value="/usr/local/bin/ollama"):
        assert OllamaProvider.is_installed() is True

    with (
        patch("shutil.which", return_value=None),
        patch("pathlib.Path.is_file", return_value=False),
    ):
        assert OllamaProvider.is_installed() is False


def test_ollama_server_health_check() -> None:
    """Verify check_health returns correct diagnostics for various server and model states."""
    provider = OllamaProvider()

    # 1. Server offline (Connection refused)
    with (
        patch.object(provider, "is_installed", return_value=True),
        patch.object(provider, "is_server_running", return_value=False),
    ):
        healthy, msg = provider.check_health()
        assert healthy is False
        assert "not running" in msg

    # 2. Server running, no models pulled
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch.object(provider, "get_available_models", return_value=[]),
    ):
        healthy, msg = provider.check_health()
        assert healthy is False
        assert "no models are installed" in msg

    # 3. Server running, requested model missing
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch.object(
            provider, "get_available_models", return_value=["llama3.2:latest", "mistral:latest"]
        ),
    ):
        healthy, msg = provider.check_health()
        assert healthy is False
        assert "is not in Ollama" in msg

    # 4. Server running and model available
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch.object(
            provider, "get_available_models", return_value=["qwen2.5:3b", "llama3.2:latest"]
        ),
    ):
        healthy, msg = provider.check_health()
        assert healthy is True
        assert "operational" in msg.lower()


def test_ollama_model_availability_matching() -> None:
    """Verify model name matching accommodates tags and variants."""
    provider = OllamaProvider(config=AIConfig(model_name="qwen2.5:3b"))

    with patch.object(
        provider, "get_available_models", return_value=["qwen2.5:3b-instruct", "llama3.2"]
    ):
        assert provider.is_model_available("qwen2.5:3b") is True
        assert provider.is_model_available("llama3.2") is True
        assert provider.is_model_available("nonexistent") is False


def test_ollama_generate_response_success() -> None:
    """Verify OllamaProvider correctly parses standard chat completion responses."""
    provider = OllamaProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "I am EAGLE running locally on Ollama.",
                },
                "finish_reason": "stop",
            }
        ]
    }

    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch("requests.post", return_value=mock_resp),
    ):
        resp = provider.generate_response([ChatMessage(role="user", content="Who are you?")])
        assert resp.content == "I am EAGLE running locally on Ollama."
        assert len(resp.tool_calls) == 0
        assert resp.finish_reason == "stop"


def test_ollama_generate_response_native_tool_calling() -> None:
    """Verify OllamaProvider parses OpenAI-compatible structured tool calls from Ollama."""
    provider = OllamaProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": "call_12345",
                            "type": "function",
                            "function": {
                                "name": "system_info",
                                "arguments": '{"topic": "cpu"}',
                            },
                        }
                    ],
                },
                "finish_reason": "tool_calls",
            }
        ]
    }

    tools = [{"type": "function", "function": {"name": "system_info", "parameters": {}}}]

    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch("requests.post", return_value=mock_resp),
    ):
        resp = provider.generate_response(
            [ChatMessage(role="user", content="Check CPU load")], tools=tools
        )
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc.tool_name == "system_info"
        assert tc.arguments == {"topic": "cpu"}
        assert resp.finish_reason == "tool_calls"


def test_ollama_generate_response_inline_tool_calling_fallback() -> None:
    """Verify OllamaProvider extracts JSON markdown tool calls when smaller models output text."""
    provider = OllamaProvider()

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    # Model outputted a markdown code block containing JSON tool call
    mock_resp.json.return_value = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": '```json\n{"name": "launch_app", "arguments": {"app_name": "notepad"}}\n```',
                    "tool_calls": [],
                },
                "finish_reason": "stop",
            }
        ]
    }

    tools = [{"type": "function", "function": {"name": "launch_app", "parameters": {}}}]

    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch("requests.post", return_value=mock_resp),
    ):
        resp = provider.generate_response(
            [ChatMessage(role="user", content="open notepad")], tools=tools
        )
        assert len(resp.tool_calls) == 1
        tc = resp.tool_calls[0]
        assert tc.tool_name == "launch_app"
        assert tc.arguments == {"app_name": "notepad"}
        assert resp.finish_reason == "tool_calls"


def test_ollama_generate_response_error_handling() -> None:
    """Verify OllamaProvider raises structured exceptions with useful diagnostics."""
    provider = OllamaProvider()

    # 1. Server down before request
    with patch.object(provider, "is_server_running", return_value=False):
        with pytest.raises(ModelUnavailableError) as exc_info:
            provider.generate_response([ChatMessage(role="user", content="hi")])
        assert "not reachable" in str(exc_info.value)

    # 2. Connection error during request
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch(
            "requests.post", side_effect=requests.exceptions.ConnectionError("Connection refused")
        ),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            provider.generate_response([ChatMessage(role="user", content="hi")])
        assert "Cannot connect to Ollama" in str(exc_info.value)

    # 3. Timeout during generation
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch("requests.post", side_effect=requests.exceptions.Timeout("Read timed out")),
    ):
        with pytest.raises(NetworkTimeoutError) as timeout_exc_info:
            provider.generate_response([ChatMessage(role="user", content="hi")])
        assert "timed out" in str(timeout_exc_info.value)

    # 4. Model not found (HTTP 404 from Ollama)
    mock_404 = MagicMock()
    mock_404.status_code = 404
    mock_404.text = "model not found"
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch("requests.post", return_value=mock_404),
    ):
        with pytest.raises(ModelUnavailableError) as exc_info:
            provider.generate_response([ChatMessage(role="user", content="hi")])
        assert "ollama pull" in str(exc_info.value)


def test_offline_policy_violation_prohibits_cloud_calls() -> None:
    """Verify strict offline mode blocks cloud AI API requests."""
    # 1. OpenAICompatibleProvider raises OfflinePolicyViolationError
    cloud_cfg = AIConfig(provider="openai", api_key="sk-test", offline_mode=True)
    provider = OpenAICompatibleProvider(config=cloud_cfg)

    with pytest.raises(OfflinePolicyViolationError) as exc_info:
        provider.generate_response([ChatMessage(role="user", content="Hello")])
    assert "Offline mode active" in str(exc_info.value)

    # 2. get_ai_provider factory raises OfflinePolicyViolationError for cloud providers
    eagle_cfg = EagleConfig(ai=cloud_cfg)
    with pytest.raises(OfflinePolicyViolationError):
        get_ai_provider(eagle_cfg)

    # 3. get_ai_provider allows ollama and mock in offline mode
    eagle_cfg_ollama = EagleConfig(ai=AIConfig(provider="ollama", offline_mode=True))
    ollama_p = get_ai_provider(eagle_cfg_ollama)
    assert isinstance(ollama_p, OllamaProvider)


def test_ai_orchestrator_get_provider_status() -> None:
    """Verify AIOrchestrator returns structured diagnostic status for Ollama and mock providers."""
    cfg = EagleConfig(ai=AIConfig(provider="ollama", offline_mode=True))
    orchestrator = AIOrchestrator(config=cfg)

    with (
        patch.object(orchestrator.provider, "is_server_running", return_value=True),
        patch.object(orchestrator.provider, "get_available_models", return_value=["qwen2.5:3b"]),
    ):
        status = orchestrator.get_provider_status()
        assert status["provider"] == "ollama"
        assert status["model"] == "qwen2.5:3b"
        assert status["is_available"] is True
        assert status["is_healthy"] is True
        assert status["offline_mode"] is True
        assert "qwen2.5:3b" in status["available_models"]


def test_ollama_discover_active_model() -> None:
    """Verify discover_active_model auto-detects installed models when preferred model is absent."""
    provider = OllamaProvider(config=AIConfig(provider="ollama", model_name="qwen2.5:3b"))

    # Server offline returns default
    with patch.object(provider, "is_server_running", return_value=False):
        assert provider.discover_active_model() == "qwen2.5:3b"

    # Server online, preferred model present
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch.object(provider, "get_available_models", return_value=["qwen2.5:3b", "llama3.2:3b"]),
    ):
        assert provider.discover_active_model() == "qwen2.5:3b"

    # Server online, preferred absent, auto-discovers llama
    with (
        patch.object(provider, "is_server_running", return_value=True),
        patch.object(provider, "get_available_models", return_value=["llama3.2:latest", "phi3:mini"]),
    ):
        model = provider.discover_active_model()
        assert "llama3.2" in model

