"""Unit tests for eagle.core.events."""

from eagle.core.events import (
    Event,
    EventBus,
    SpeechTranscribedEvent,
    StateChangedEvent,
)


def test_event_bus_publish_and_subscribe() -> None:
    """Verify events are received by registered subscriber callbacks."""
    bus = EventBus()
    received: list[str] = []

    def on_transcribed(evt: SpeechTranscribedEvent) -> None:
        received.append(evt.text)

    bus.subscribe(SpeechTranscribedEvent, on_transcribed)
    bus.publish(SpeechTranscribedEvent(text="Open notepad"))

    assert len(received) == 1
    assert received[0] == "Open notepad"


def test_event_bus_unsubscribe() -> None:
    """Verify unsubscribed handlers are no longer invoked."""
    bus = EventBus()
    received: list[str] = []

    def on_state(evt: StateChangedEvent) -> None:
        received.append(evt.new_state)

    bus.subscribe(StateChangedEvent, on_state)
    bus.publish(StateChangedEvent(old_state="IDLE", new_state="LISTENING"))
    assert received == ["LISTENING"]

    bus.unsubscribe(StateChangedEvent, on_state)
    bus.publish(StateChangedEvent(old_state="LISTENING", new_state="PROCESSING"))
    assert received == ["LISTENING"]


def test_base_event_subscription_receives_all() -> None:
    """Verify subscribing to Event base class receives all published events."""
    bus = EventBus()
    names: list[str] = []

    def on_any_event(evt: Event) -> None:
        names.append(evt.event_name)

    bus.subscribe(Event, on_any_event)
    bus.publish(SpeechTranscribedEvent(text="Hello"))
    bus.publish(StateChangedEvent(old_state="A", new_state="B"))

    assert names == ["SpeechTranscribedEvent", "StateChangedEvent"]


def test_failing_handler_does_not_break_other_handlers() -> None:
    """Verify an unhandled exception in one subscriber does not disrupt others."""
    bus = EventBus()
    executed: list[str] = []

    def bad_handler(evt: SpeechTranscribedEvent) -> None:
        raise RuntimeError("Handler failure")

    def good_handler(evt: SpeechTranscribedEvent) -> None:
        executed.append(evt.text)

    bus.subscribe(SpeechTranscribedEvent, bad_handler)
    bus.subscribe(SpeechTranscribedEvent, good_handler)

    # Should not raise exception
    bus.publish(SpeechTranscribedEvent(text="Resilient event"))
    assert executed == ["Resilient event"]
