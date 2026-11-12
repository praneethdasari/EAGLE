"""Reliable voice and text command recognition, intent parsing, and routing for EAGLE."""

import re
import subprocess
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
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
from eagle.core.paths import get_desktop_dir, get_documents_dir, get_downloads_dir
from eagle.tools.registry import ToolRegistry

logger = get_logger("services.command_router")


class CommandIntent(StrEnum):
    """High-level classified intent of a user voice/text command."""

    SYSTEM_CONTROL = "system_control"  # Stop, quit, exit, cancel
    APP_LAUNCH = "app_launch"  # Open notepad, launch calculator
    WEB_SEARCH = "web_search"  # Search web for X, google Y
    WEB_OPEN = "web_open"  # Go to github.com, open python.org
    SYSTEM_INFO = "system_info"  # Battery level, system status
    VOLUME_CONTROL = "volume_control"  # Master volume, mute, unmute
    BRIGHTNESS_CONTROL = "brightness_control"  # Display brightness
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
        ai_orchestrator: Any | None = None,
    ) -> None:
        self.config = config or EagleConfig()
        self.security_config: SecurityConfig = self.config.security
        self.tool_registry = tool_registry
        self.event_bus = event_bus
        self.ai_orchestrator = ai_orchestrator

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

        # 2. Windows Known Folder Navigation (Desktop, Documents, Downloads)
        folder_route = self._check_known_folder_open(normalized, raw_text)
        if folder_route:
            return folder_route

        # 3. Application Launch
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

        # 6. Volume Control
        volume_route = self._check_volume_control(normalized, raw_text)
        if volume_route:
            return volume_route

        # 7. Brightness Control
        brightness_route = self._check_brightness_control(normalized, raw_text)
        if brightness_route:
            return brightness_route

        # 8. File Operations
        file_route = self._check_file_operations(normalized, raw_text)
        if file_route:
            return file_route

        # 9. Conversational / Informational Query
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

    def _check_known_folder_open(self, text: str, raw: str) -> CommandRoute | None:
        """Matches requests to open Windows Known Folders: downloads, documents, desktop."""
        match = re.match(
            r"^(?:open|show|view|explore|browse)(?:\s+my)?(?:\s+the)?\s+(downloads?|documents?|desktop)(?:\s+folder|\s+directory)?$",
            text,
            flags=re.IGNORECASE,
        )
        if match:
            target = match.group(1).lower().rstrip("s")
            folder_map = {
                "download": (get_downloads_dir(), "Downloads"),
                "document": (get_documents_dir(), "Documents"),
                "desktop": (get_desktop_dir(), "Desktop"),
            }
            folder_info = folder_map.get(target)
            if folder_info:
                folder_path, display_name = folder_info
                return CommandRoute(
                    intent=CommandIntent.FILE_OPERATION,
                    raw_text=raw,
                    normalized_text=text,
                    action_name="open_folder",
                    parameters={"folder_path": str(folder_path), "folder_name": display_name},
                    confidence=0.98,
                    matched_rule="known_folder_open",
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
            topic = "all"
            if "battery" in text:
                topic = "battery"
            elif "cpu" in text:
                topic = "cpu"
            elif "ram" in text or "memory" in text:
                topic = "memory"
            return CommandRoute(
                intent=CommandIntent.SYSTEM_INFO,
                raw_text=raw,
                normalized_text=text,
                action_name="system_info",
                parameters={"topic": topic},
                confidence=0.9,
                matched_rule="system_info",
            )
        return None

    def _check_volume_control(self, text: str, raw: str) -> CommandRoute | None:
        """Matches volume adjustment commands: set volume, volume up/down, mute, unmute, status."""
        # 1. Mute / Unmute
        if re.search(
            r"\b(?:unmute|un-mute)(?:\s+(?:the\s+)?(?:volume|sound|audio|speaker))?\b", text
        ):
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "unmute"},
                confidence=0.98,
                matched_rule="volume_unmute",
            )
        if re.search(r"\b(?:mute)(?:\s+(?:the\s+)?(?:volume|sound|audio|speaker))?\b", text):
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "mute"},
                confidence=0.98,
                matched_rule="volume_mute",
            )

        # 2. Set volume to specific level: "set volume to 50 percent", "set volume 50%", "volume 75", "turn volume to 40"
        m_set = re.search(
            r"(?:set|turn|change|put)?\s*(?:the\s+)?volume\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?",
            text,
        )
        if m_set:
            val = float(m_set.group(1))
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "set", "level": val},
                confidence=0.98,
                matched_rule="volume_set",
            )

        # 3. Increase volume: "increase volume", "volume up", "turn up the volume", "turn it up", "raise volume"
        m_inc = re.search(
            r"(?:increase|raise|turn\s+up|pump\s+up)\s*(?:the\s+)?(?:volume|sound|audio)?(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|"
            r"(?:volume|sound|audio)\s+up(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?",
            text,
        )
        if m_inc and any(kw in text for kw in ("volume", "sound", "audio", "turn up", "pump up")):
            step_str = m_inc.group(1) or m_inc.group(2)
            step = float(step_str) if step_str else 10.0
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "increase", "level": step},
                confidence=0.95,
                matched_rule="volume_increase",
            )

        # 4. Decrease volume: "decrease volume", "volume down", "turn down the volume", "turn it down", "lower volume"
        m_dec = re.search(
            r"(?:decrease|lower|reduce|turn\s+down)\s*(?:the\s+)?(?:volume|sound|audio)?(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|"
            r"(?:volume|sound|audio)\s+down(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?",
            text,
        )
        if m_dec and any(kw in text for kw in ("volume", "sound", "audio", "turn down", "lower")):
            step_str = m_dec.group(1) or m_dec.group(2)
            step = float(step_str) if step_str else 10.0
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "decrease", "level": step},
                confidence=0.95,
                matched_rule="volume_decrease",
            )

        # 5. Query volume: "what is the volume", "current volume", "get volume", "check volume"
        if (
            re.search(
                r"\b(?:what(?:\s+is)?|get|check|tell\s+me)\s+(?:the\s+)?(?:current\s+)?(?:volume|sound\s+level)\b",
                text,
            )
            or text == "volume"
        ):
            return CommandRoute(
                intent=CommandIntent.VOLUME_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="volume_control",
                parameters={"action": "get"},
                confidence=0.95,
                matched_rule="volume_get",
            )

        return None

    def _check_brightness_control(self, text: str, raw: str) -> CommandRoute | None:
        """Matches brightness adjustment commands: set brightness, up/down, max/min, status."""
        # 1. Max / Min brightness
        if re.search(
            r"\b(?:max|maximum|full)\s+(?:the\s+)?brightness\b|set\s+(?:the\s+)?brightness\s+to\s+(?:max|maximum|full)",
            text,
        ):
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "max"},
                confidence=0.98,
                matched_rule="brightness_max",
            )
        if re.search(
            r"\b(?:min|minimum|lowest)\s+(?:the\s+)?brightness\b|set\s+(?:the\s+)?brightness\s+to\s+(?:min|minimum|lowest)",
            text,
        ):
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "min"},
                confidence=0.98,
                matched_rule="brightness_min",
            )

        # 2. Set brightness to specific level: "set brightness to 50 percent", "set brightness 80%", "brightness 60"
        m_set = re.search(
            r"(?:set|turn|change|put)?\s*(?:the\s+)?brightness\s+(?:to\s+)?(\d{1,3})\s*(?:%|percent)?",
            text,
        )
        if m_set:
            val = float(m_set.group(1))
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "set", "level": val},
                confidence=0.98,
                matched_rule="brightness_set",
            )

        # 3. Increase brightness: "increase brightness", "brightness up", "brighter", "turn up brightness"
        m_inc = re.search(
            r"(?:increase|raise|turn\s+up|make\s+it\s+more)\s*(?:the\s+)?brightness(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|"
            r"brightness\s+up(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|\bbrighter\b",
            text,
        )
        if m_inc:
            step_str = m_inc.group(1) or m_inc.group(2)
            step = float(step_str) if step_str else 10.0
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "increase", "level": step},
                confidence=0.95,
                matched_rule="brightness_increase",
            )

        # 4. Decrease brightness: "decrease brightness", "brightness down", "dim screen", "dimmer", "turn down brightness"
        m_dec = re.search(
            r"(?:decrease|lower|reduce|turn\s+down)\s*(?:the\s+)?brightness(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|"
            r"brightness\s+down(?:\s+by\s+(\d{1,2})\s*(?:%|percent)?)?|\b(?:dim|dimmer)\s*(?:screen)?\b",
            text,
        )
        if m_dec:
            step_str = m_dec.group(1) or m_dec.group(2)
            step = float(step_str) if step_str else 10.0
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "decrease", "level": step},
                confidence=0.95,
                matched_rule="brightness_decrease",
            )

        # 5. Query brightness: "what is the brightness", "current brightness", "check brightness"
        if (
            re.search(
                r"\b(?:what(?:\s+is)?|get|check|tell\s+me)\s+(?:the\s+)?(?:current\s+)?brightness\b",
                text,
            )
            or text == "brightness"
        ):
            return CommandRoute(
                intent=CommandIntent.BRIGHTNESS_CONTROL,
                raw_text=raw,
                normalized_text=text,
                action_name="brightness_control",
                parameters={"action": "get"},
                confidence=0.95,
                matched_rule="brightness_get",
            )

        return None

    def _check_file_operations(self, text: str, raw: str) -> CommandRoute | None:
        # Matches: "inspect file report.txt", "check file notes.md", "view file readme.txt"
        inspect_match = re.match(r"^(?:inspect|check|view)\s+(?:the\s+)?file\s+(.+)$", text)
        if inspect_match:
            target_file = inspect_match.group(1).strip()
            return CommandRoute(
                intent=CommandIntent.FILE_OPERATION,
                raw_text=raw,
                normalized_text=text,
                action_name="inspect_file",
                parameters={"path": target_file},
                confidence=0.9,
                matched_rule="file_inspection",
            )

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
            topic = route.parameters.get("topic", "all")
            if topic == "battery":
                msg = "Checking battery level."
            elif topic == "cpu":
                msg = "Checking CPU usage."
            elif topic == "memory":
                msg = "Checking memory usage."
            else:
                msg = "Checking system status."
            self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="system_info",
                    arguments=route.parameters,
                )
            )
            return

        if route.intent == CommandIntent.VOLUME_CONTROL:
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="volume_control",
                    arguments=route.parameters,
                )
            )
            return

        if route.intent == CommandIntent.BRIGHTNESS_CONTROL:
            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name="brightness_control",
                    arguments=route.parameters,
                )
            )
            return

        if route.intent == CommandIntent.FILE_OPERATION:
            action = route.action_name or "list_files"
            if action == "open_folder":
                folder_path = route.parameters.get("folder_path", "")
                folder_name = route.parameters.get("folder_name", "Folder")
                if folder_path and Path(folder_path).exists():
                    try:
                        subprocess.Popen(["explorer.exe", str(folder_path)])
                        self.event_bus.publish(
                            SpeechOutputRequestedEvent(
                                text=f"Opening {folder_name} in File Explorer."
                            )
                        )
                    except Exception as exc:
                        logger.error("Failed to open folder %s: %s", folder_path, exc)
                        self.event_bus.publish(
                            SpeechOutputRequestedEvent(text=f"Could not open {folder_name}.")
                        )
                else:
                    self.event_bus.publish(
                        SpeechOutputRequestedEvent(text=f"{folder_name} directory not found.")
                    )
                return

            if action == "inspect_file":
                path = route.parameters.get("path", "")
                self.event_bus.publish(SpeechOutputRequestedEvent(text=f"Inspecting file {path}."))
            else:
                target_dir = route.parameters.get("directory", "")
                dir_desc = f" in {target_dir}" if target_dir else ""
                self.event_bus.publish(SpeechOutputRequestedEvent(text=f"Listing files{dir_desc}."))

            self.event_bus.publish(
                ToolExecutionRequestedEvent(
                    tool_name=action,
                    arguments=route.parameters,
                )
            )
            return

        if route.intent == CommandIntent.CONVERSATION:
            if self.ai_orchestrator and self.ai_orchestrator.is_available():
                logger.debug(
                    "Forwarding conversational command to AI reasoning: '%s'", route.raw_text
                )
                self.ai_orchestrator.process_query(route.raw_text)
            else:
                msg = (
                    "EAGLE AI reasoning is currently unavailable. "
                    "Supported direct commands (e.g. open notepad, list files, volume, brightness) remain active."
                )
                self.event_bus.publish(SpeechOutputRequestedEvent(text=msg))
            return

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
