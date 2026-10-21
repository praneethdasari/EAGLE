"""Reliable voice and text command recognition, intent parsing, and routing for EAGLE."""

import re
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from eagle.core.config import EagleConfig, SecurityConfig
from eagle.core.events import (
    EventBus,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    StateChangedEvent,
    TextCommandReceivedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.core.logging import get_logger
from eagle.tools.registry import ToolRegistry

logger = get_logger("services.command_router")


class CommandIntent(StrEnum):
    """High-level classified intent of a user voice/text command."""

    SYSTEM_CONTROL = "system_control"  # Stop, quit, exit, cancel
    APP_LAUNCH = "app_launch"  # Open notepad, launch calculator
    WEB_SEARCH = "web_search"  # Search web for X, google Y
    WEB_OPEN = "web_open"  # Go to github.com, open python.org
    SYSTEM_INFO = "system_info"  # Battery level, system status
    FILE_OPERATION = "file_operation"  # List files in Documents
    CONVERSATION = "conversation"  # Question answering, AI chat
    UNKNOWN = "unknown"  # Unrecognized command


@dataclass
class CommandRoute:
    """Structured result of parsing and classifying a voice command."""

    intent: CommandIntent
    raw_text: str
    normalized_text: str
    action_name: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    matched_rule: str = "default"

    @property
    def is_actionable(self) -> bool:
        """Return True if the route can be executed as a local action."""
        return self.intent not in (CommandIntent.UNKNOWN, CommandIntent.CONVERSATION)


# Common conversational prefixes and filler phrases to strip during normalization
FILLER_PREFIXES = [
    r"^(?:hey\s+|hi\s+|ok\s+)?eagle[,\s]+(?:can\s+you\s+(?:please\s+)?)?",
    r"^(?:can\s+you\s+(?:please\s+)?|could\s+you\s+(?:please\s+)?|please\s+|would\s+you\s+(?:kindly\s+)?)",
    r"^(?:i\s+want\s+you\s+to\s+|i\s+need\s+you\s+to\s+|go\s+ahead\s+and\s+)",
]


def normalize_command_text(text: str) -> str:
    """Normalize input command text by stripping noise, fillers, and extra whitespace."""
    cleaned = text.strip().lower()

    # Strip conversational filler prefixes
    for prefix_pat in FILLER_PREFIXES:
        cleaned = re.sub(prefix_pat, "", cleaned, flags=re.IGNORECASE).strip()

    # Strip trailing punctuation
    cleaned = re.sub(r"[?!.,;]+$", "", cleaned).strip()
    # Normalize multiple whitespaces
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


class CommandRouter:
    """Parses natural language recognized speech and routes commands to appropriate tools or AI."""

    def __init__(
        self,
        config: EagleConfig | None = None,
        tool_registry: ToolRegistry | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config or EagleConfig()
        self.security_config: SecurityConfig = self.config.security
        self.tool_registry = tool_registry
        self.event_bus = event_bus

        # Wire event bus listeners if provided
        if self.event_bus:
            self.event_bus.subscribe(SpeechTranscribedEvent, self._handle_speech_transcribed)
            self.event_bus.subscribe(TextCommandReceivedEvent, self._handle_text_command)

    def route(self, raw_text: str) -> CommandRoute:
        """Analyze, classify, and route a user command text."""
        normalized = normalize_command_text(raw_text)

        if not normalized:
            return CommandRoute(
                intent=CommandIntent.UNKNOWN,
                raw_text=raw_text,
                normalized_text="",
                confidence=0.0,
                matched_rule="empty_input",
            )

        # 1. System Control (Highest priority)
        system_control_route = self._check_system_control(normalized, raw_text)
        if system_control_route:
            return system_control_route

        # 2. Application Launch
        app_route = self._check_app_launch(normalized, raw_text)
        if app_route:
            return app_route

        # 3. Direct Website Opening
        web_open_route = self._check_web_open(normalized, raw_text)
        if web_open_route:
            return web_open_route

        # 4. Web Search
        web_search_route = self._check_web_search(normalized, raw_text)
        if web_search_route:
            return web_search_route

        # 5. System Information
        system_info_route = self._check_system_info(normalized, raw_text)
        if system_info_route:
            return system_info_route

        # 6. File Operations
        file_route = self._check_file_operations(normalized, raw_text)
        if file_route:
            return file_route

        # 7. Conversational / Informational Query
        if self._is_conversational_query(normalized):
            return CommandRoute(
                intent=CommandIntent.CONVERSATION,
                raw_text=raw_text,
                normalized_text=normalized,
                confidence=0.9,
                matched_rule="conversational_query",
            )

        # Fallback to general conversation
        return CommandRoute(
            intent=CommandIntent.CONVERSATION,
            raw_text=raw_text,
            normalized_text=normalized,
            confidence=0.6,
            matched_rule="fallback_to_ai",
        )

    # ------------------------------------------------------------------
    # Pattern Matchers
    # ------------------------------------------------------------------

    def _check_system_control(self, text: str, raw: str) -> CommandRoute | None:
        match = re.match(r"^(exit|quit|stop|cancel|terminate|shut down|close eagle|goodbye)$", text)
        if match:
            action = match.group(1).replace(" ", "_")
            return CommandRoute(
                intent=CommandIntent.SYSTEM_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name=action,
                parameters={"action": action},
                confidence=1.0,
                matched_rule="system_control",
            )
        return None

    def _check_app_launch(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "open notepad", "launch calculator", "start paint", "run browser"
        match = re.match(r"^(?:open|launch|start|run)(?:\s+up)?\s+([a-zA-Z0-9_\-\.\s]+)$", text)
        if not match:
            return None

        target = match.group(1).strip()
        allowed_apps = self.security_config.allowed_applications

        # Exact match or normalized key lookup
        for app_alias, app_exec in allowed_apps.items():
            if (
                target == app_alias.lower()
                or target in app_alias.lower()
                or app_alias.lower() in target
            ):
                return CommandRoute(
                    intent=CommandIntent.APP_LAUNCH,
                    raw_text=raw,
                    normalized_text=text,
                    action_name="launch_app",
                    parameters={"app_name": app_alias, "executable": app_exec},
                    confidence=0.95,
                    matched_rule="app_launch",
                )

        # If user asked to open an app not in allowlist
        return CommandRoute(
            intent=CommandIntent.APP_LAUNCH,
            raw_text=raw,
            normalized_text=text,
            action_name="launch_app",
            parameters={"app_name": target, "is_allowed": False},
            confidence=0.8,
            matched_rule="unregistered_app_launch",
        )

    def _check_web_open(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "go to github.com", "open https://python.org", "navigate to wikipedia.org"
        match = re.match(
            r"^(?:go\s+to|open|navigate\s+to)\s+((?:https?:\/\/)?(?:[a-zA-Z0-9\-]+\.)+[a-zA-Z]{2,}(?:\/[^\s]*)?)$",
            text,
        )
        if match:
            url = match.group(1).strip()
            if not url.startswith("http://") and not url.startswith("https://"):
                url = f"https://{url}"
            return CommandRoute(
                intent=CommandIntent.WEB_OPEN,
                raw_text=raw,
                normalized_text=text,
                action_name="open_website",
                parameters={"url": url},
                confidence=0.95,
                matched_rule="direct_web_open",
            )
        return None

    def _check_web_search(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "search the web for python", "search for quantum computing", "google machine learning", "look up recipes"
        match = re.match(
            r"^(?:search(?:\s+(?:the\s+web|google))?(?:\s+for)?|look\s+up|google)\s+(.+)$",
            text,
        )
        if match:
            query = match.group(1).strip()
            return CommandRoute(
                intent=CommandIntent.WEB_SEARCH,
                raw_text=raw,
                normalized_text=text,
                action_name="web_search",
                parameters={"query": query},
                confidence=0.95,
                matched_rule="web_search",
            )
        return None

    def _check_system_info(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "system status", "battery level", "cpu usage", "system info", "how much battery"
        if re.search(r"\b(battery|cpu|ram|memory|system status|system info)\b", text):
            return CommandRoute(
                intent=CommandIntent.SYSTEM_INFO,
                raw_text=raw,
                normalized_text=text,
                action_name="system_info",
                parameters={"topic": "system"},
                confidence=0.9,
                matched_rule="system_info",
            )
        return None

    def _check_file_operations(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "list files", "show files in documents", "view files"
        match = re.match(r"^(?:list|show|view)\s+(?:the\s+)?files(?:\s+in\s+(.+))?$", text)
        if match:
            target_dir = match.group(1).strip() if match.group(1) else ""
            return CommandRoute(
                intent=CommandIntent.FILE_OPERATION,
                raw_text=raw,
                normalized_text=text,
                action_name="list_files",
                parameters={"directory": target_dir},
                confidence=0.9,
                matched_rule="file_listing",
            )
        return None

    def _is_conversational_query(self, text: str) -> bool:
        question_words = ("what", "who", "why", "when", "where", "how", "tell", "explain", "help")
        return any(text.startswith(word) for word in question_words)

    # ------------------------------------------------------------------
    # Dispatch & Event Handlers
    # ------------------------------------------------------------------

    def dispatch(self, route: CommandRoute) -> None:
        """Dispatch a resolved command route to tools, vocal confirmation, or event bus."""
        logger.info(
            "Dispatching route [%s] - Action: %s - Params: %s",
            route.intent.value,
            route.action_name,
            route.parameters,
        )

        if not self.event_bus:
            return

        if route.intent == CommandIntent.SYSTEM_CONTROL:
            self.event_bus.publish(SpeechOutputRequestedEvent(text="Stopping EAGLE."))
            self.event_bus.publish(StateChangedEvent(old_state="ACTIVE", new_state="IDLE"))
            return

        if route.intent == CommandIntent.APP_LAUNCH:
            app_name = route.parameters.get("app_name", "")
            if route.parameters.get("is_allowed") is False:
                msg = f"Application '{app_name}' is not in the approved applications list."
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            else:
                self.event_bus.publish(SpeechOutputRequestedEvent(text=f"Opening {app_name}."))
                self.event_bus.publish(
                    ToolExecutionRequestedEvent(
                        tool_name="launch_app",
                        arguments=route.parameters,
                    )
                )
            return

        if route.intent == CommandIntent.WEB_SEARCH:
            query = route.parameters.get("query", "")
            self.event_bus.publish(SpeechOutputRequestedEvent(text=f"Searching for {query}."))
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="web_search",
                    arguments={"query": query},
                )
            )
            return

        if route.intent == CommandIntent.WEB_OPEN:
            url = route.parameters.get("url", "")
            self.event_bus.publish(SpeechOutputRequestedEvent(text=f"Navigating to {url}."))
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="open_website",
                    arguments={"url": url},
                )
            )
            return

        if route.intent == CommandIntent.SYSTEM_INFO:
            self.event_bus.publish(SpeechOutputRequestedEvent(text="Checking system status."))
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="system_info",
                    arguments=route.parameters,
                )
            )
            return

        if route.intent == CommandIntent.CONVERSATION:
            # Emitted for AI reasoning orchestrator to handle
            logger.debug("Forwarding conversational command to AI reasoning: '%s'", route.raw_text)

    def process_and_dispatch(self, text: str) -> CommandRoute:
        """Convenience method to route and immediately dispatch a command."""
        route = self.route(text)
        self.dispatch(route)
        return route

    def _handle_speech_transcribed(self, event: SpeechTranscribedEvent) -> None:
        """EventBus callback for transcribed voice speech."""
        if event.is_final and event.text.strip():
            logger.info("CommandRouter received voice transcription: '%s'", event.text)
            self.process_and_dispatch(event.text)

    def _handle_text_command(self, event: TextCommandReceivedEvent) -> None:
        """EventBus callback for fallback text input."""
        if event.text.strip():
            logger.info("CommandRouter received text command: '%s'", event.text)
            self.process_and_dispatch(event.text)
