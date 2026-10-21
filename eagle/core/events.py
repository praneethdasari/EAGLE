"""Thread-safe event bus and core event definitions for EAGLE."""

import datetime
import threading
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, TypeVar

from eagle.core.logging import get_logger

logger = get_logger("core.events")


@dataclass(kw_only=True)
class Event:
    """Base event payload class."""

    timestamp: datetime.datetime = field(
        default_factory=lambda: datetime.datetime.now(datetime.UTC)
    )

    @property
    def event_name(self) -> str:
        return self.__class__.__name__


# =====================================================================
# Concrete Event Types
# =====================================================================


@dataclass(kw_only=True)
class StateChangedEvent(Event):
    """Fired when assistant state changes (e.g. IDLE, LISTENING, PROCESSING, SPEAKING)."""

    old_state: str
    new_state: str


@dataclass(kw_only=True)
class AudioLevelEvent(Event):
    """Periodic audio amplitude level for UI visualizer."""

    amplitude: float  # Normalized 0.0 to 1.0


@dataclass(kw_only=True)
class SpeechTranscribedEvent(Event):
    """Fired when user audio is converted to text."""

    text: str
    is_final: bool = True
    confidence: float = 1.0


@dataclass(kw_only=True)
class TextCommandReceivedEvent(Event):
    """Fired when user enters a command via fallback text input."""

    text: str


@dataclass(kw_only=True)
class AIResponseGeneratedEvent(Event):
    """Fired when the AI model returns reasoning or conversational output."""

    text: str
    tool_calls: list[dict[str, Any]] = field(default_factory=list)


@dataclass(kw_only=True)
class ToolExecutionRequestedEvent(Event):
    """Fired before executing an allowlisted desktop tool."""

    tool_name: str
    arguments: dict[str, Any] = field(default_factory=dict)
    requires_confirmation: bool = False


@dataclass(kw_only=True)
class ToolExecutionCompletedEvent(Event):
    """Fired after tool execution completes."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None


@dataclass(kw_only=True)
class SpeechOutputRequestedEvent(Event):
    """Fired when text should be spoken aloud by TTS."""

    text: str


@dataclass(kw_only=True)
class SpeechOutputFinishedEvent(Event):
    """Fired when TTS speech generation finishes or is cancelled."""

    text: str
    interrupted: bool = False


@dataclass(kw_only=True)
class ErrorOccurredEvent(Event):
    """Fired when an unhandled error or subsystem warning occurs."""

    error_type: str
    message: str
    context: dict[str, Any] = field(default_factory=dict)


E = TypeVar("E", bound=Event)
EventHandler = Callable[[Any], None]


class EventBus:
    """Thread-safe publish-subscribe event broker for EAGLE components."""

    def __init__(self) -> None:
        self._subscribers: dict[type[Event], list[EventHandler]] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        """Register a handler callback for a specific event type."""
        with self._lock:
            if handler not in self._subscribers[event_type]:
                self._subscribers[event_type].append(handler)  # type: ignore[arg-type]

    def unsubscribe(self, event_type: type[E], handler: Callable[[E], None]) -> None:
        """Unregister a handler callback for an event type."""
        with self._lock:
            if handler in self._subscribers[event_type]:
                self._subscribers[event_type].remove(handler)  # type: ignore[arg-type]

    def publish(self, event: Event) -> None:
        """Publish an event to all registered subscribers."""
        event_class = type(event)
        with self._lock:
            # Copy subscriber list to avoid mutations during iteration
            handlers = list(self._subscribers.get(event_class, []))
            # Also notify any handlers subscribed to base Event class
            base_handlers = (
                list(self._subscribers.get(Event, [])) if event_class is not Event else []
            )

        all_handlers = handlers + base_handlers
        for handler in all_handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error(
                    "Error executing handler %s for event %s: %s",
                    getattr(handler, "__name__", str(handler)),
                    event.event_name,
                    exc,
                    exc_info=True,
                )

    def clear(self) -> None:
        """Clear all event subscriptions."""
        with self._lock:
            self._subscribers.clear()
