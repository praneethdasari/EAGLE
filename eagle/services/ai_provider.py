"""AI reasoning engine, provider integrations, conversation context, and structured tool calling."""

import json
import os
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

import requests

from eagle.core.config import AIConfig, EagleConfig
from eagle.core.events import (
    AIResponseGeneratedEvent,
    EventBus,
    SpeechOutputRequestedEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.core.exceptions import (
    AIProviderError,
    AuthenticationError,
    InvalidResponseError,
    ModelUnavailableError,
    NetworkTimeoutError,
    RateLimitExceededError,
)
from eagle.core.logging import get_logger
from eagle.tools.registry import ToolRegistry

logger = get_logger("services.ai")


@dataclass
class ToolCall:
    """Represents a structured tool execution request from the AI model."""

    id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass
class ChatMessage:
    """A single turn in the conversation history."""

    role: str  # "system", "user", "assistant", "tool"
    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_call_id: str | None = None
    name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to standard OpenAI-compatible message representation."""
        msg: dict[str, Any] = {"role": self.role}
        if self.content is not None:
            msg["content"] = self.content
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {
                        "name": tc.tool_name,
                        "arguments": json.dumps(tc.arguments),
                    },
                }
                for tc in self.tool_calls
            ]
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
        if self.name:
            msg["name"] = self.name
        return msg


@dataclass
class AIResponse:
    """Standardized response from an AI reasoning provider."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_response: dict[str, Any] = field(default_factory=dict)
    finish_reason: str = "stop"  # "stop", "tool_calls", "length"


class BaseAIProvider(ABC):
    """Abstract base class for all EAGLE AI reasoning providers."""

    @abstractmethod
    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AIResponse:
        """Generate a reasoning response given conversation messages and optional tool specs.

        Raises:
            AuthenticationError: If credentials are invalid or missing.
            NetworkTimeoutError: If the request times out.
            ModelUnavailableError: If the remote endpoint is unreachable.
            RateLimitExceededError: If rate limits or quotas are hit.
            InvalidResponseError: If the provider returns unparseable or malformed output.
            AIProviderError: For any other provider-side failure.
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Return True if the provider is configured and ready to handle requests."""
        pass


class MockAIProvider(BaseAIProvider):
    """Deterministic, offline AI provider for unit testing, CI, and local operation."""

    def __init__(
        self,
        config: AIConfig | None = None,
        simulate_error: str | None = None,
    ) -> None:
        self.config = config or AIConfig()
        self.simulate_error = simulate_error
        self.call_history: list[list[ChatMessage]] = []

    def is_available(self) -> bool:
        return True

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AIResponse:
        self.call_history.append(messages)

        # 1. Error simulation support for testing
        if self.simulate_error == "auth":
            raise AuthenticationError("Simulated invalid or missing API key.")
        if self.simulate_error == "timeout":
            raise NetworkTimeoutError("Simulated AI provider network timeout.")
        if self.simulate_error == "rate_limit":
            raise RateLimitExceededError("Simulated provider rate limit exceeded.")
        if self.simulate_error == "unavailable":
            raise ModelUnavailableError("Simulated remote AI endpoint unavailable.")
        if self.simulate_error == "invalid_json":
            raise InvalidResponseError("Simulated malformed response payload.")

        # 2. Check if the previous message was a tool result
        last_msg = messages[-1] if messages else None
        if last_msg and last_msg.role == "tool":
            tool_name = last_msg.name or "tool"
            tool_output = last_msg.content or "Done"
            return AIResponse(
                content=f"I have executed {tool_name}. Here is the result:\n{tool_output}",
                finish_reason="stop",
            )

        # 3. Analyze latest user message for tool calling triggers
        user_text = ""
        for m in reversed(messages):
            if m.role == "user" and m.content:
                user_text = m.content.strip().lower()
                break

        # Check for tool calling requests if tools are enabled
        if tools and user_text:
            # Check app launch: "open notepad", "launch calculator"
            app_match = re.search(r"\b(?:open|launch|start|run)\s+([a-zA-Z0-9_\-]+)\b", user_text)
            if app_match and not any(kw in user_text for kw in ("http", "website", "file")):
                app_target = app_match.group(1)
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_app_1",
                            tool_name="launch_app",
                            arguments={"app_name": app_target},
                        )
                    ],
                    finish_reason="tool_calls",
                )

            # Check web search: "search for X", "google Y"
            search_match = re.search(r"\b(?:search(?:\s+for)?|look\s+up|google)\s+(.+)$", user_text)
            if search_match and "website" not in user_text:
                query = search_match.group(1).strip()
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_search_1",
                            tool_name="web_search",
                            arguments={"query": query},
                        )
                    ],
                    finish_reason="tool_calls",
                )

            # Check web open: "go to github.com", "open python.org"
            web_match = re.search(
                r"\b(?:go\s+to|navigate\s+to|open\s+website)\s+([a-zA-Z0-9\.\-]+\.[a-zA-Z]{2,}[^\s]*)\b",
                user_text,
            )
            if web_match:
                url = web_match.group(1).strip()
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_web_1",
                            tool_name="open_website",
                            arguments={"url": url},
                        )
                    ],
                    finish_reason="tool_calls",
                )

            # Check system telemetry: "battery level", "system status", "cpu usage"
            if any(
                kw in user_text
                for kw in ("battery", "cpu", "memory", "ram", "system info", "system status")
            ):
                topic = "all"
                if "battery" in user_text:
                    topic = "battery"
                elif "cpu" in user_text:
                    topic = "cpu"
                elif "memory" in user_text or "ram" in user_text:
                    topic = "memory"
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_sys_1",
                            tool_name="system_info",
                            arguments={"topic": topic},
                        )
                    ],
                    finish_reason="tool_calls",
                )

            # Check file operations: "list files", "show files"
            if "list files" in user_text or "show files" in user_text:
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_files_1",
                            tool_name="list_files",
                            arguments={},
                        )
                    ],
                    finish_reason="tool_calls",
                )

            # Check inspect file: "inspect file X"
            inspect_match = re.search(r"\binspect\s+(?:file\s+)?([a-zA-Z0-9_\.\-]+)\b", user_text)
            if inspect_match:
                filename = inspect_match.group(1).strip()
                return AIResponse(
                    content=None,
                    tool_calls=[
                        ToolCall(
                            id="call_mock_inspect_1",
                            tool_name="inspect_file",
                            arguments={"path": filename},
                        )
                    ],
                    finish_reason="tool_calls",
                )

        # 4. Standard conversational responses
        if "who are you" in user_text or "what are you" in user_text:
            return AIResponse(
                content=(
                    "I am EAGLE (Enhanced Autonomous General-purpose Local Executive), "
                    "your personal desktop voice assistant. I can converse, answer questions, "
                    "and safely perform computer automation actions."
                ),
                finish_reason="stop",
            )

        if "hello" in user_text or "hi" in user_text:
            return AIResponse(
                content="Greetings! How can I assist you with your tasks or system today?",
                finish_reason="stop",
            )

        if "help" in user_text:
            return AIResponse(
                content=(
                    "You can ask me questions, or command me to launch approved apps (Notepad, Calculator), "
                    "search the web, open websites, inspect files in permitted directories, or check system status."
                ),
                finish_reason="stop",
            )

        # General helpful answer
        return AIResponse(
            content=f"I understand your query: '{user_text}'. As EAGLE, I am ready to help.",
            finish_reason="stop",
        )


class OpenAICompatibleProvider(BaseAIProvider):
    """Generic OpenAI-compatible REST API client supporting OpenAI, Groq, Ollama, and local servers."""

    PROVIDER_DEFAULTS = {
        "openai": {
            "base_url": "https://api.openai.com/v1",
            "env_var": "OPENAI_API_KEY",
            "default_model": "gpt-4o-mini",
        },
        "groq": {
            "base_url": "https://api.groq.com/openai/v1",
            "env_var": "GROQ_API_KEY",
            "default_model": "llama-3.3-70b-versatile",
        },
        "ollama": {
            "base_url": "http://localhost:11434/v1",
            "env_var": "OLLAMA_API_KEY",
            "default_model": "llama3.2",
        },
    }

    def __init__(self, config: AIConfig | None = None) -> None:
        self.config = config or AIConfig()
        provider_key = self.config.provider.lower()

        defaults = self.PROVIDER_DEFAULTS.get(
            provider_key,
            {
                "base_url": "https://api.openai.com/v1",
                "env_var": "OPENAI_API_KEY",
                "default_model": "gpt-4o-mini",
            },
        )

        self.base_url = (self.config.base_url or defaults["base_url"]).rstrip("/")
        self.env_var = defaults["env_var"]
        self.model_name = self.config.model_name or defaults["default_model"]
        self.timeout = self.config.timeout_seconds
        self.api_key = self._resolve_api_key()

    def _resolve_api_key(self) -> str | None:
        """Resolve API key from explicit config or environment variables."""
        if self.config.api_key and self.config.api_key.strip():
            return self.config.api_key.strip()

        key = os.environ.get(self.env_var)
        if key and key.strip():
            return key.strip()

        # Check generic AI_API_KEY as fallback
        generic_key = os.environ.get("AI_API_KEY")
        if generic_key and generic_key.strip():
            return generic_key.strip()

        return None

    def is_available(self) -> bool:
        """Check whether the provider has credentials (or doesn't require credentials like Ollama)."""
        # Local Ollama does not strictly require an API key
        if self.config.provider.lower() == "ollama":
            return True
        return bool(self.api_key)

    def generate_response(
        self,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
    ) -> AIResponse:
        """Send chat completion request to the OpenAI-compatible REST endpoint."""
        # Ollama can run without an API key; cloud providers require an API key
        if not self.is_available():
            raise AuthenticationError(
                f"Missing API key for AI provider '{self.config.provider}'. "
                f"Please set the {self.env_var} environment variable or configure 'ai.api_key' in config.json.",
                details={"provider": self.config.provider, "expected_env_var": self.env_var},
            )

        headers: dict[str, str] = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        payload: dict[str, Any] = {
            "model": self.model_name,
            "messages": [m.to_dict() for m in messages],
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        endpoint = f"{self.base_url}/chat/completions"
        logger.debug(
            "Dispatching request to AI endpoint: %s (model: %s)", endpoint, self.model_name
        )

        try:
            response = requests.post(
                endpoint,
                json=payload,
                headers=headers,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout as exc:
            logger.error("AI provider timeout after %ss: %s", self.timeout, exc)
            raise NetworkTimeoutError(
                f"AI provider request timed out after {self.timeout} seconds.",
                details={"endpoint": endpoint, "timeout": self.timeout},
            ) from exc
        except requests.exceptions.ConnectionError as exc:
            logger.error("AI provider connection error: %s", exc)
            raise ModelUnavailableError(
                f"Cannot connect to AI provider endpoint '{self.base_url}'. Verify your network or local server.",
                details={"endpoint": endpoint},
            ) from exc
        except Exception as exc:
            logger.error("Unexpected error contacting AI provider: %s", exc)
            raise AIProviderError(f"Failed to communicate with AI provider: {exc}") from exc

        # Handle HTTP error statuses
        if response.status_code == 401:
            raise AuthenticationError(
                f"Authentication failed (HTTP 401) for provider '{self.config.provider}'. Check {self.env_var}.",
                details={"status_code": 401, "response": response.text},
            )
        if response.status_code == 429:
            raise RateLimitExceededError(
                f"Rate limit or quota exceeded (HTTP 429) for provider '{self.config.provider}'.",
                details={"status_code": 429, "response": response.text},
            )
        if response.status_code != 200:
            raise AIProviderError(
                f"AI provider returned HTTP error {response.status_code}: {response.text}",
                details={"status_code": response.status_code, "response": response.text},
            )

        # Parse JSON response
        try:
            data = response.json()
        except Exception as exc:
            raise InvalidResponseError(
                f"AI provider returned malformed non-JSON payload: {exc}",
                details={"raw_text": response.text},
            ) from exc

        choices = data.get("choices")
        if not choices or not isinstance(choices, list):
            raise InvalidResponseError(
                "AI provider response missing 'choices' list.",
                details={"data": data},
            )

        choice = choices[0]
        message = choice.get("message", {})
        content = message.get("content")
        finish_reason = choice.get("finish_reason", "stop")

        # Parse tool calls if present
        raw_tool_calls = message.get("tool_calls", [])
        parsed_tool_calls: list[ToolCall] = []

        for tc in raw_tool_calls:
            tc_id = tc.get("id", f"call_{len(parsed_tool_calls)}")
            func_data = tc.get("function", {})
            func_name = func_data.get("name", "")
            raw_args = func_data.get("arguments", "{}")

            if isinstance(raw_args, str):
                try:
                    args_dict = json.loads(raw_args)
                except Exception:
                    args_dict = {"raw_arguments": raw_args}
            elif isinstance(raw_args, dict):
                args_dict = raw_args
            else:
                args_dict = {}

            parsed_tool_calls.append(
                ToolCall(
                    id=tc_id,
                    tool_name=func_name,
                    arguments=args_dict,
                )
            )

        return AIResponse(
            content=content,
            tool_calls=parsed_tool_calls,
            raw_response=data,
            finish_reason=finish_reason,
        )


class ConversationManager:
    """Maintains conversational context, enforces turn budgets, and manages message formatting."""

    def __init__(self, system_prompt: str, max_turns: int = 20) -> None:
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.messages: list[ChatMessage] = [ChatMessage(role="system", content=self.system_prompt)]

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))
        self._prune_history()

    def add_assistant_message(
        self,
        content: str | None,
        tool_calls: list[ToolCall] | None = None,
    ) -> None:
        self.messages.append(
            ChatMessage(role="assistant", content=content, tool_calls=tool_calls or [])
        )
        self._prune_history()

    def add_tool_result(self, tool_call_id: str, tool_name: str, result: str) -> None:
        self.messages.append(
            ChatMessage(
                role="tool",
                content=result,
                tool_call_id=tool_call_id,
                name=tool_name,
            )
        )

    def get_messages(self) -> list[ChatMessage]:
        return list(self.messages)

    def clear(self) -> None:
        """Reset conversation context back to initial system prompt."""
        self.messages = [ChatMessage(role="system", content=self.system_prompt)]

    def _prune_history(self) -> None:
        """Keep context within budget, preserving system prompt at index 0."""
        # Each conversational turn has roughly a user message + assistant message.
        # Max message count = 1 (system) + max_turns * 2.
        max_messages = 1 + (self.max_turns * 2)
        if len(self.messages) > max_messages:
            # Retain system prompt at [0], slice the excess from the oldest turns
            excess = len(self.messages) - max_messages
            self.messages = [self.messages[0]] + self.messages[1 + excess :]


def get_ai_provider(config: EagleConfig | None = None) -> BaseAIProvider:
    """Factory function creating the configured AI reasoning provider."""
    cfg = config or EagleConfig()
    provider_name = cfg.ai.provider.lower().strip()

    if provider_name == "mock":
        return MockAIProvider(config=cfg.ai)

    if provider_name in ("openai", "groq", "ollama", "openai_compatible"):
        return OpenAICompatibleProvider(config=cfg.ai)

    logger.warning("Unrecognized AI provider '%s', defaulting to MockAIProvider.", provider_name)
    return MockAIProvider(config=cfg.ai)


class AIOrchestrator:
    """High-level orchestrator connecting AI Provider, Conversation Context, and ToolRegistry."""

    def __init__(
        self,
        config: EagleConfig | None = None,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
        provider: BaseAIProvider | None = None,
    ) -> None:
        self.config = config or EagleConfig()
        self.tool_registry = tool_registry or ToolRegistry()
        self.event_bus = event_bus
        self.provider = provider or get_ai_provider(self.config)
        self.conversation = ConversationManager(
            system_prompt=self.config.ai.system_prompt,
            max_turns=self.config.ai.max_conversation_turns,
        )

    def is_available(self) -> bool:
        """Return True if the underlying AI provider is configured and available."""
        return self.provider.is_available()

    def process_query(self, user_query: str) -> str:
        """Process a natural language user query through reasoning and structured tool calling.

        Returns:
            The final text response from the assistant.
        """
        trimmed = user_query.strip()
        if not trimmed:
            return ""

        logger.info("AIOrchestrator processing query: '%s'", trimmed)
        self.conversation.add_user_message(trimmed)

        # Retrieve registered tool specs from ToolRegistry
        tool_specs = self.tool_registry.get_tool_specs() if self.tool_registry else []

        max_iterations = self.config.ai.max_tool_iterations
        iteration = 0

        try:
            while iteration < max_iterations:
                iteration += 1

                response = self.provider.generate_response(
                    messages=self.conversation.get_messages(),
                    tools=tool_specs if tool_specs else None,
                )

                # Case 1: Final conversational response (no tool calls)
                if not response.tool_calls:
                    final_text = response.content or ""
                    self.conversation.add_assistant_message(final_text)

                    if self.event_bus:
                        self.event_bus.publish(
                            AIResponseGeneratedEvent(text=final_text, tool_calls=[])
                        )
                        self.event_bus.publish(SpeechOutputRequestedEvent(text=final_text))

                    return final_text

                # Case 2: AI returned one or more structured tool calls
                logger.info(
                    "AI requested %d tool calls: %s",
                    len(response.tool_calls),
                    [tc.tool_name for tc in response.tool_calls],
                )
                self.conversation.add_assistant_message(
                    response.content, tool_calls=response.tool_calls
                )

                for tool_call in response.tool_calls:
                    tc_id = tool_call.id
                    name = tool_call.tool_name
                    args = tool_call.arguments

                    # Notify event bus before execution
                    if self.event_bus:
                        self.event_bus.publish(
                            ToolExecutionRequestedEvent(tool_name=name, arguments=args)
                        )

                    # 1. Enforce ToolRegistry allowlist
                    if not self.tool_registry.has_tool(name):
                        error_msg = (
                            f"Security Error: Tool '{name}' is not in the approved EAGLE allowlist."
                        )
                        logger.warning(error_msg)
                        self.conversation.add_tool_result(tc_id, name, error_msg)
                        if self.event_bus:
                            self.event_bus.publish(
                                ToolExecutionCompletedEvent(
                                    tool_name=name, success=False, error=error_msg
                                )
                            )
                        continue

                    # 2. Execute tool through ToolRegistry
                    try:
                        result = self.tool_registry.execute(name, args)
                        output_str = (
                            result.output if result.success else f"Tool Error: {result.error}"
                        )

                        if self.event_bus:
                            self.event_bus.publish(
                                ToolExecutionCompletedEvent(
                                    tool_name=name,
                                    success=result.success,
                                    result=result.output,
                                    error=result.error,
                                )
                            )

                        self.conversation.add_tool_result(tc_id, name, str(output_str))
                    except Exception as exc:
                        logger.error("Tool execution failed for '%s': %s", name, exc)
                        err_str = f"Execution exception: {exc}"
                        self.conversation.add_tool_result(tc_id, name, err_str)
                        if self.event_bus:
                            self.event_bus.publish(
                                ToolExecutionCompletedEvent(
                                    tool_name=name, success=False, error=err_str
                                )
                            )

            # Max iterations reached without a final conversational answer
            fallback_text = (
                "I completed the requested actions, but the conversation limit was reached."
            )
            if self.event_bus:
                self.event_bus.publish(AIResponseGeneratedEvent(text=fallback_text))
                self.event_bus.publish(SpeechOutputRequestedEvent(text=fallback_text))
            return fallback_text

        except AuthenticationError as auth_err:
            msg = (
                f"EAGLE AI Authentication Error: {auth_err.message} "
                "Please configure a valid API key in your environment or config.json."
            )
            logger.warning(msg)
            if self.event_bus:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return msg

        except (NetworkTimeoutError, ModelUnavailableError) as net_err:
            msg = (
                f"EAGLE AI is currently unavailable: {net_err.message} "
                "Supported direct commands (e.g. open notepad, list files, system info) remain available."
            )
            logger.warning(msg)
            if self.event_bus:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return msg

        except RateLimitExceededError:
            msg = "EAGLE AI rate limit reached. Please wait a moment before trying again."
            logger.warning(msg)
            if self.event_bus:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return msg

        except InvalidResponseError as inv_err:
            msg = f"EAGLE received an invalid response from the AI provider: {inv_err.message}"
            logger.error(msg)
            if self.event_bus:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return msg

        except Exception as exc:
            msg = f"An unexpected error occurred during AI processing: {exc}"
            logger.error(msg, exc_info=True)
            if self.event_bus:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return msg
