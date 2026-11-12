"""Unit tests for eagle.services.command_router."""

from eagle.core.events import (
    EventBus,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    StateChangedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.core.paths import get_desktop_dir, get_documents_dir, get_downloads_dir
from eagle.services.command_router import (
    CommandIntent,
    CommandRouter,
    normalize_command_text,
)


def test_normalize_command_text() -> None:
    """Verify conversational fillers and punctuation are stripped during normalization."""
    assert normalize_command_text("Hey eagle, can you please open notepad?") == "open notepad"
    assert normalize_command_text("Could you please launch calculator!") == "launch calculator"
    assert normalize_command_text("Eagle please search for python.") == "search for python"
    assert normalize_command_text("   Please   stop   ") == "stop"
    assert normalize_command_text("what is quantum computing???") == "what is quantum computing"


def test_system_control_routing() -> None:
    """Verify system control keywords are classified with SYSTEM_CONTROL intent."""
    router = CommandRouter()

    for cmd in ["exit", "quit", "stop", "shut down", "goodbye", "close eagle"]:
        route = router.route(cmd)
        assert route.intent == CommandIntent.SYSTEM_CONTROL
        assert route.confidence == 1.0


def test_app_launch_routing_allowed_apps() -> None:
    """Verify registered applications are identified and routed with APP_LAUNCH intent."""
    router = CommandRouter()

    # Notepad
    r_notepad = router.route("open notepad")
    assert r_notepad.intent == CommandIntent.APP_LAUNCH
    assert r_notepad.action_name == "launch_app"
    assert r_notepad.parameters["app_name"] == "notepad"
    assert r_notepad.parameters.get("is_allowed", True) is True

    # Calculator
    r_calc = router.route("can you please launch calculator")
    assert r_calc.intent == CommandIntent.APP_LAUNCH
    assert r_calc.parameters["app_name"] == "calculator"

    # Browser
    r_browser = router.route("start browser")
    assert r_browser.intent == CommandIntent.APP_LAUNCH
    assert r_browser.parameters["app_name"] == "browser"


def test_app_launch_routing_unregistered_app() -> None:
    """Verify unregistered application requests are flagged as not allowed."""
    router = CommandRouter()
    route = router.route("open dangerous_game")

    assert route.intent == CommandIntent.APP_LAUNCH
    assert route.parameters["is_allowed"] is False
    assert route.parameters["app_name"] == "dangerous_game"


def test_web_open_routing() -> None:
    """Verify direct domain/URL open commands are classified with WEB_OPEN intent."""
    router = CommandRouter()

    r1 = router.route("go to github.com")
    assert r1.intent == CommandIntent.WEB_OPEN
    assert r1.parameters["url"] == "https://github.com"

    r2 = router.route("open https://python.org/docs")
    assert r2.intent == CommandIntent.WEB_OPEN
    assert r2.parameters["url"] == "https://python.org/docs"


def test_web_search_routing() -> None:
    """Verify search queries are extracted and classified with WEB_SEARCH intent."""
    router = CommandRouter()

    r1 = router.route("search the web for machine learning")
    assert r1.intent == CommandIntent.WEB_SEARCH
    assert r1.parameters["query"] == "machine learning"

    r2 = router.route("google quantum computing algorithms")
    assert r2.intent == CommandIntent.WEB_SEARCH
    assert r2.parameters["query"] == "quantum computing algorithms"

    r3 = router.route("look up best pasta recipes")
    assert r3.intent == CommandIntent.WEB_SEARCH
    assert r3.parameters["query"] == "best pasta recipes"


def test_system_info_routing() -> None:
    """Verify battery and system queries are routed to SYSTEM_INFO intent."""
    router = CommandRouter()

    r1 = router.route("what is my battery level")
    assert r1.intent == CommandIntent.SYSTEM_INFO

    r2 = router.route("check cpu usage")
    assert r2.intent == CommandIntent.SYSTEM_INFO

    r3 = router.route("system status")
    assert r3.intent == CommandIntent.SYSTEM_INFO


def test_file_operations_routing() -> None:
    """Verify file listing queries are routed to FILE_OPERATION intent."""
    router = CommandRouter()

    r1 = router.route("list files")
    assert r1.intent == CommandIntent.FILE_OPERATION

    r2 = router.route("show files in documents")
    assert r2.intent == CommandIntent.FILE_OPERATION
    assert r2.parameters["directory"] == "documents"


def test_conversational_queries() -> None:
    """Verify general questions route to CONVERSATION intent."""
    router = CommandRouter()

    r1 = router.route("who was Albert Einstein?")
    assert r1.intent == CommandIntent.CONVERSATION

    r2 = router.route("why is the sky blue?")
    assert r2.intent == CommandIntent.CONVERSATION

    r3 = router.route("tell me a joke about computers")
    assert r3.intent == CommandIntent.CONVERSATION


def test_empty_input_routing() -> None:
    """Verify blank input returns UNKNOWN intent with zero confidence."""
    router = CommandRouter()
    route = router.route("   ")
    assert route.intent == CommandIntent.UNKNOWN
    assert route.confidence == 0.0


def test_event_bus_voice_command_dispatch() -> None:
    """Verify that firing SpeechTranscribedEvent on EventBus dispatches tool & speech events."""
    bus = EventBus()
    spoken_events: list[SpeechOutputRequestedEvent] = []
    tool_events: list[ToolExecutionRequestedEvent] = []

    bus.subscribe(SpeechOutputRequestedEvent, lambda e: spoken_events.append(e))
    bus.subscribe(ToolExecutionRequestedEvent, lambda e: tool_events.append(e))

    # Initialize router connected to the EventBus
    CommandRouter(event_bus=bus)

    # Publish voice transcription event
    bus.publish(SpeechTranscribedEvent(text="open notepad", is_final=True))

    assert len(spoken_events) == 1
    assert "Opening notepad" in spoken_events[0].text

    assert len(tool_events) == 1
    assert tool_events[0].tool_name == "launch_app"
    assert tool_events[0].arguments["app_name"] == "notepad"


def test_event_bus_system_control_dispatch() -> None:
    """Verify system control voice command publishes state change and speech events."""
    bus = EventBus()
    state_changes: list[StateChangedEvent] = []

    bus.subscribe(StateChangedEvent, lambda e: state_changes.append(e))
    CommandRouter(event_bus=bus)

    bus.publish(SpeechTranscribedEvent(text="exit", is_final=True))

    assert len(state_changes) == 1
    assert state_changes[0].new_state == "IDLE"


def test_known_folder_navigation_routing() -> None:
    """Verify dynamic Known Folder navigation routes to FILE_OPERATION open_folder."""
    router = CommandRouter()

    # Downloads
    r_dl = router.route("open downloads")
    assert r_dl.intent == CommandIntent.FILE_OPERATION
    assert r_dl.action_name == "open_folder"
    assert r_dl.parameters["folder_name"] == "Downloads"
    assert r_dl.parameters["folder_path"] == str(get_downloads_dir())

    # Desktop
    r_desk = router.route("show my desktop folder")
    assert r_desk.intent == CommandIntent.FILE_OPERATION
    assert r_desk.action_name == "open_folder"
    assert r_desk.parameters["folder_name"] == "Desktop"
    assert r_desk.parameters["folder_path"] == str(get_desktop_dir())

    # Documents
    r_docs = router.route("explore documents")
    assert r_docs.intent == CommandIntent.FILE_OPERATION
    assert r_docs.action_name == "open_folder"
    assert r_docs.parameters["folder_name"] == "Documents"
    assert r_docs.parameters["folder_path"] == str(get_documents_dir())


def test_known_folder_dispatch_popen(monkeypatch) -> None:
    """Verify dispatching open_folder launches explorer.exe and announces vocal confirmation."""
    import subprocess

    bus = EventBus()
    spoken_events: list[SpeechOutputRequestedEvent] = []
    bus.subscribe(SpeechOutputRequestedEvent, lambda e: spoken_events.append(e))

    router = CommandRouter(event_bus=bus)
    popen_args = []

    def mock_popen(args, **kwargs):
        popen_args.append(args)

    monkeypatch.setattr(subprocess, "Popen", mock_popen)

    route = router.route("open downloads")
    router.dispatch(route)

    assert len(popen_args) == 1
    assert popen_args[0][0] == "explorer.exe"
    assert popen_args[0][1] == str(get_downloads_dir())
    assert len(spoken_events) == 1
    assert "Opening Downloads in File Explorer." in spoken_events[0].text


def test_volume_control_routing() -> None:
    """Verify volume adjustment phrases route to VOLUME_CONTROL intent."""
    router = CommandRouter()

    # Set volume
    r_set = router.route("set volume to 50 percent")
    assert r_set.intent == CommandIntent.VOLUME_CONTROL
    assert r_set.parameters["action"] == "set"
    assert r_set.parameters["level"] == 50.0

    r_set2 = router.route("volume 80%")
    assert r_set2.intent == CommandIntent.VOLUME_CONTROL
    assert r_set2.parameters["action"] == "set"
    assert r_set2.parameters["level"] == 80.0

    # Increase volume
    r_inc = router.route("increase volume")
    assert r_inc.intent == CommandIntent.VOLUME_CONTROL
    assert r_inc.parameters["action"] == "increase"

    # Decrease volume
    r_dec = router.route("turn down the volume")
    assert r_dec.intent == CommandIntent.VOLUME_CONTROL
    assert r_dec.parameters["action"] == "decrease"

    # Mute / unmute
    r_mute = router.route("mute the audio")
    assert r_mute.intent == CommandIntent.VOLUME_CONTROL
    assert r_mute.parameters["action"] == "mute"

    r_unmute = router.route("unmute")
    assert r_unmute.intent == CommandIntent.VOLUME_CONTROL
    assert r_unmute.parameters["action"] == "unmute"

    # Get volume
    r_get = router.route("what is the current volume")
    assert r_get.intent == CommandIntent.VOLUME_CONTROL
    assert r_get.parameters["action"] == "get"


def test_volume_control_dispatch() -> None:
    """Verify volume commands dispatch ToolExecutionRequestedEvent."""
    bus = EventBus()
    tool_events: list[ToolExecutionRequestedEvent] = []
    bus.subscribe(ToolExecutionRequestedEvent, lambda e: tool_events.append(e))

    router = CommandRouter(event_bus=bus)
    route = router.route("set volume to 60%")
    router.dispatch(route)

    assert len(tool_events) == 1
    assert tool_events[0].tool_name == "volume_control"
    assert tool_events[0].arguments["action"] == "set"
    assert tool_events[0].arguments["level"] == 60.0


def test_brightness_control_routing() -> None:
    """Verify brightness adjustment phrases route to BRIGHTNESS_CONTROL intent."""
    router = CommandRouter()

    # Set brightness
    r_set = router.route("set brightness to 70 percent")
    assert r_set.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_set.parameters["action"] == "set"
    assert r_set.parameters["level"] == 70.0

    # Increase / decrease
    r_inc = router.route("increase brightness")
    assert r_inc.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_inc.parameters["action"] == "increase"

    r_dec = router.route("dim screen")
    assert r_dec.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_dec.parameters["action"] == "decrease"

    # Max / min
    r_max = router.route("set brightness to max")
    assert r_max.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_max.parameters["action"] == "max"

    r_min = router.route("minimum brightness")
    assert r_min.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_min.parameters["action"] == "min"

    # Get brightness
    r_get = router.route("what is the brightness")
    assert r_get.intent == CommandIntent.BRIGHTNESS_CONTROL
    assert r_get.parameters["action"] == "get"


def test_brightness_control_dispatch() -> None:
    """Verify brightness commands dispatch ToolExecutionRequestedEvent."""
    bus = EventBus()
    tool_events: list[ToolExecutionRequestedEvent] = []
    bus.subscribe(ToolExecutionRequestedEvent, lambda e: tool_events.append(e))

    router = CommandRouter(event_bus=bus)
    route = router.route("increase brightness")
    router.dispatch(route)

    assert len(tool_events) == 1
    assert tool_events[0].tool_name == "brightness_control"
    assert tool_events[0].arguments["action"] == "increase"


def test_uninstalled_ollama_conversational_fallback() -> None:
    """Verify conversational queries announce offline AI status without crashing or mock fallback."""
    bus = EventBus()
    spoken_events: list[SpeechOutputRequestedEvent] = []
    bus.subscribe(SpeechOutputRequestedEvent, lambda e: spoken_events.append(e))

    # Router without available AI orchestrator
    router = CommandRouter(event_bus=bus, ai_orchestrator=None)
    route = router.route("explain artificial intelligence")
    router.dispatch(route)

    assert len(spoken_events) == 1
    assert "EAGLE AI reasoning is currently unavailable" in spoken_events[0].text
    assert "volume, brightness" in spoken_events[0].text

