"""Thread-safe event bridge forwarding EventBus occurrences to PySide6 Qt signals."""

from typing import Any

from PySide6.QtCore import QObject, Signal

from eagle.core.events import (
    AudioLevelEvent,
    ErrorOccurredEvent,
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionRequestedEvent,
)


class EventBusQtBridge(QObject):
    """Bridges decoupled thread-safe EventBus subscriptions to Qt UI signals."""

    sig_audio_level = Signal(float)
    sig_state_changed = Signal(str, str, str)  # old_state, new_state, reason
    sig_speech_transcribed = Signal(str, float)  # text, confidence
    sig_speech_output_requested = Signal(str)  # text
    sig_tool_requested = Signal(str, dict)  # tool_name, arguments
    sig_tool_completed = Signal(str, bool, str, float)  # tool_name, success, result, duration
    sig_error_occurred = Signal(str, str)  # message, subsystem

    def __init__(self, event_bus: EventBus, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.event_bus = event_bus
        self._handlers: dict[type, Any] = {}
        self._attach()

    def _attach(self) -> None:
        def on_audio_level(event: AudioLevelEvent) -> None:
            self.sig_audio_level.emit(event.amplitude)

        def on_state_changed(event: ListeningStateChangedEvent) -> None:
            self.sig_state_changed.emit(event.old_state, event.new_state, event.reason)

        def on_speech_transcribed(event: SpeechTranscribedEvent) -> None:
            self.sig_speech_transcribed.emit(event.text, event.confidence)

        def on_speech_output(event: SpeechOutputRequestedEvent) -> None:
            self.sig_speech_output_requested.emit(event.text)

        def on_tool_requested(event: ToolExecutionRequestedEvent) -> None:
            self.sig_tool_requested.emit(event.tool_name, event.arguments)

        def on_tool_completed(event: ToolExecutionCompletedEvent) -> None:
            res_str = str(event.result if event.success else event.error or "Tool failed")
            self.sig_tool_completed.emit(event.tool_name, event.success, res_str, 0.0)

        def on_error(event: ErrorOccurredEvent) -> None:
            self.sig_error_occurred.emit(event.message, event.error_type)

        self._handlers = {
            AudioLevelEvent: on_audio_level,
            ListeningStateChangedEvent: on_state_changed,
            SpeechTranscribedEvent: on_speech_transcribed,
            SpeechOutputRequestedEvent: on_speech_output,
            ToolExecutionRequestedEvent: on_tool_requested,
            ToolExecutionCompletedEvent: on_tool_completed,
            ErrorOccurredEvent: on_error,
        }

        for event_cls, handler in self._handlers.items():
            self.event_bus.subscribe(event_cls, handler)

    def detach(self) -> None:
        """Unsubscribe handlers from EventBus to allow clean garbage collection."""
        for event_cls, handler in self._handlers.items():
            self.event_bus.unsubscribe(event_cls, handler)
        self._handlers.clear()
