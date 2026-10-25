"""Comprehensive unit tests for EAGLE desktop automation tools and safety boundaries."""

import subprocess
from pathlib import Path

from pytest_mock import MockerFixture

from eagle.core.config import EagleConfig, SecurityConfig
from eagle.core.events import (
    EventBus,
    SpeechTranscribedEvent,
    ToolExecutionCompletedEvent,
    ToolExecutionRequestedEvent,
)
from eagle.main import register_default_tools
from eagle.services.command_router import CommandRouter
from eagle.tools.apps import LaunchAppTool
from eagle.tools.files import InspectFileTool, ListFilesTool
from eagle.tools.registry import ToolRegistry
from eagle.tools.system import SystemInfoTool
from eagle.tools.web import OpenWebsiteTool, WebSearchTool

# =====================================================================
# LaunchAppTool Tests
# =====================================================================


def test_launch_app_success(mocker: MockerFixture) -> None:
    """Verify approved application is launched via subprocess without shell injection."""
    mock_process = mocker.MagicMock(spec=subprocess.Popen)
    mock_process.pid = 4321
    mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

    config = SecurityConfig(allowed_applications={"notepad": "notepad.exe"})
    tool = LaunchAppTool(security_config=config)

    result = tool.execute({"app_name": "notepad"})
    assert result.success is True
    assert "launched successfully" in result.output
    assert result.metadata["pid"] == 4321

    # Verify Popen called with argument array, never shell=True
    mock_popen.assert_called_once()
    args, kwargs = mock_popen.call_args
    assert args[0] == ["notepad.exe"]
    assert kwargs.get("shell") is not True


def test_launch_app_unauthorized_rejection(mocker: MockerFixture) -> None:
    """Verify application outside allowlist is rejected immediately."""
    mock_popen = mocker.patch("subprocess.Popen")
    config = SecurityConfig(allowed_applications={"notepad": "notepad.exe"})
    tool = LaunchAppTool(security_config=config)

    result = tool.execute({"app_name": "malicious_script.bat"})
    assert result.success is False
    assert result.metadata["blocked"] is True
    assert "not in the approved applications allowlist" in (result.error or "")
    mock_popen.assert_not_called()


def test_launch_app_path_traversal_rejection(mocker: MockerFixture) -> None:
    """Verify application names containing path traversal sequences are blocked."""
    mock_popen = mocker.patch("subprocess.Popen")
    config = SecurityConfig(allowed_applications={"notepad": "notepad.exe"})
    tool = LaunchAppTool(security_config=config)

    for bad_name in ["../../cmd.exe", "C:\\evil.exe", "tools/script"]:
        result = tool.execute({"app_name": bad_name})
        assert result.success is False
        assert result.metadata.get("blocked") is True
        assert "Path traversal characters are forbidden" in (result.error or "")

    mock_popen.assert_not_called()


def test_launch_app_alias_resolution(mocker: MockerFixture) -> None:
    """Verify common alias (calc -> calculator) resolves and launches."""
    mock_process = mocker.MagicMock(spec=subprocess.Popen)
    mock_process.pid = 9999
    mocker.patch("subprocess.Popen", return_value=mock_process)

    config = SecurityConfig(allowed_applications={"calculator": "calc.exe"})
    tool = LaunchAppTool(security_config=config)

    result = tool.execute({"app_name": "calc"})
    assert result.success is True
    assert result.metadata["app_name"] == "calculator"


def test_launch_app_untrusted_executable_ignored(mocker: MockerFixture) -> None:
    """Verify executable argument passed in request is ignored in favor of allowlist."""
    mock_process = mocker.MagicMock(spec=subprocess.Popen)
    mock_process.pid = 1111
    mock_popen = mocker.patch("subprocess.Popen", return_value=mock_process)

    config = SecurityConfig(allowed_applications={"notepad": "notepad.exe"})
    tool = LaunchAppTool(security_config=config)

    # Attempt to pass an untrusted executable override
    result = tool.execute({"app_name": "notepad", "executable": "evil_payload.exe"})
    assert result.success is True
    args, _ = mock_popen.call_args
    assert args[0] == ["notepad.exe"]


def test_launch_app_file_not_found(mocker: MockerFixture) -> None:
    """Verify missing executable on system returns clean error."""
    mocker.patch("subprocess.Popen", side_effect=FileNotFoundError("Executable not found"))
    config = SecurityConfig(allowed_applications={"custom_app": "missing.exe"})
    tool = LaunchAppTool(security_config=config)

    result = tool.execute({"app_name": "custom_app"})
    assert result.success is False
    assert "could not be located" in (result.error or "")


def test_launch_app_permission_denied(mocker: MockerFixture) -> None:
    """Verify OS permission error when launching is captured."""
    mocker.patch("subprocess.Popen", side_effect=PermissionError("Access denied"))
    config = SecurityConfig(allowed_applications={"restricted": "restricted.exe"})
    tool = LaunchAppTool(security_config=config)

    result = tool.execute({"app_name": "restricted"})
    assert result.success is False
    assert "OS permission denied" in (result.error or "")


# =====================================================================
# OpenWebsiteTool & WebSearchTool Tests
# =====================================================================


def test_open_website_valid_urls(mocker: MockerFixture) -> None:
    """Verify valid HTTP and HTTPS URLs open in the default browser."""
    mock_browser = mocker.patch("webbrowser.open", return_value=True)
    tool = OpenWebsiteTool()

    # Full HTTPS URL
    r1 = tool.execute({"url": "https://github.com/praneethdasari/EAGLE"})
    assert r1.success is True
    mock_browser.assert_called_with("https://github.com/praneethdasari/EAGLE", new=2)

    # Missing scheme prepends https://
    r2 = tool.execute({"url": "python.org"})
    assert r2.success is True
    mock_browser.assert_called_with("https://python.org", new=2)


def test_open_website_rejects_unsafe_schemes(mocker: MockerFixture) -> None:
    """Verify non-HTTP schemes (file:, javascript:, data:) are rejected."""
    mock_browser = mocker.patch("webbrowser.open")
    tool = OpenWebsiteTool()

    for unsafe in [
        "file:///C:/Windows/System32/cmd.exe",
        "javascript:alert(1)",
        "data:text/html,<h1>test</h1>",
        "ftp://ftp.example.com",
    ]:
        res = tool.execute({"url": unsafe})
        assert res.success is False
        assert res.metadata.get("blocked") is True
        assert "Only HTTP and HTTPS are permitted" in (res.error or "")

    mock_browser.assert_not_called()


def test_open_website_rejects_embedded_credentials(mocker: MockerFixture) -> None:
    """Verify URLs with embedded credentials are blocked."""
    mock_browser = mocker.patch("webbrowser.open")
    tool = OpenWebsiteTool()

    res = tool.execute({"url": "http://admin:secret@malicious.com"})
    assert res.success is False
    assert "embedded username or password" in (res.error or "")
    mock_browser.assert_not_called()


def test_open_website_rejects_malformed_host(mocker: MockerFixture) -> None:
    """Verify malformed hostnames are rejected."""
    tool = OpenWebsiteTool()
    res = tool.execute({"url": "https://localhost"})
    assert res.success is False
    assert "Invalid domain hostname" in (res.error or "")


def test_open_website_browser_failure(mocker: MockerFixture) -> None:
    """Verify browser launch errors are gracefully caught."""
    mocker.patch("webbrowser.open", side_effect=OSError("Browser process failed"))
    tool = OpenWebsiteTool()

    res = tool.execute({"url": "https://python.org"})
    assert res.success is False
    assert "Failed to open browser" in (res.error or "")


def test_web_search_providers(mocker: MockerFixture) -> None:
    """Verify search queries format correctly for Google, DuckDuckGo, and Bing."""
    mock_browser = mocker.patch("webbrowser.open", return_value=True)
    tool = WebSearchTool()

    # Google (default)
    r_google = tool.execute({"query": "python decorators", "provider": "google"})
    assert r_google.success is True
    assert "https://www.google.com/search?q=python+decorators" in r_google.metadata["url"]

    # DuckDuckGo
    r_ddg = tool.execute({"query": "quantum computing", "provider": "duckduckgo"})
    assert r_ddg.success is True
    assert "https://duckduckgo.com/?q=quantum+computing" in r_ddg.metadata["url"]

    # Bing
    r_bing = tool.execute({"query": "machine learning", "provider": "bing"})
    assert r_bing.success is True
    assert "https://www.bing.com/search?q=machine+learning" in r_bing.metadata["url"]
    assert mock_browser.call_count == 3


def test_web_search_empty_query() -> None:
    """Verify empty search query returns an error."""
    tool = WebSearchTool()
    res = tool.execute({"query": "   "})
    assert res.success is False
    assert "cannot be empty" in (res.error or "")


def test_web_search_unsupported_provider(mocker: MockerFixture) -> None:
    """Verify unsupported search provider returns clear error."""
    mock_browser = mocker.patch("webbrowser.open")
    tool = WebSearchTool()

    res = tool.execute({"query": "python", "provider": "unknown_engine"})
    assert res.success is False
    assert "Unsupported search provider" in (res.error or "")
    mock_browser.assert_not_called()


def test_web_search_blocks_credentials_and_local_paths(mocker: MockerFixture) -> None:
    """Verify web search blocks queries with API keys or local filesystem paths."""
    mock_browser = mocker.patch("webbrowser.open")
    tool = WebSearchTool()

    sensitive_queries = [
        "sk-abcdef1234567890abcdef1234567890",
        "ghp_abcdef1234567890abcdef1234567890",
        "bearer secret_token_xyz_12345678901234567890",
        "password = my_super_secret",
        "C:\\Users\\admin\\passwords.txt",
        "file:///C:/secrets.json",
    ]

    for q in sensitive_queries:
        res = tool.execute({"query": q})
        assert res.success is False
        assert res.metadata.get("blocked") is True
        assert "Search query blocked" in (res.error or "")

    mock_browser.assert_not_called()


# =====================================================================
# ListFilesTool & InspectFileTool Tests
# =====================================================================


def test_list_files_in_sandbox(tmp_path: Path) -> None:
    """Verify listing files within an allowed directory returns formatted entries."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "doc1.txt").write_text("Hello world", encoding="utf-8")
    (sandbox / "doc2.pdf").write_bytes(b"%PDF-1.4 dummy")
    (sandbox / "subfolder").mkdir()

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    result = tool.execute({"directory": str(sandbox)})
    assert result.success is True
    assert result.metadata["count"] == 3
    assert "doc1.txt" in result.output
    assert "doc2.pdf" in result.output
    assert "subfolder" in result.output


def test_list_files_default_directory(tmp_path: Path) -> None:
    """Verify listing files without directory parameter defaults to allowed directory."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "default_test.txt").write_text("content", encoding="utf-8")

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    result = tool.execute({})
    assert result.success is True
    assert "default_test.txt" in result.output


def test_list_files_blocks_path_traversal(tmp_path: Path) -> None:
    """Verify attempting to list outside allowed directory via '..' is blocked."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    outside = tmp_path / "secret"
    outside.mkdir()

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    # Traversal escape
    traversal_path = str(sandbox / ".." / "secret")
    result = tool.execute({"directory": traversal_path})
    assert result.success is False
    assert result.metadata.get("blocked") is True
    assert "Path traversal blocked" in (result.error or "")


def test_list_files_non_existent_directory(tmp_path: Path) -> None:
    """Verify querying non-existent directory inside sandbox returns clear error."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    result = tool.execute({"directory": str(sandbox / "missing_dir")})
    assert result.success is False
    assert "does not exist" in (result.error or "")


def test_list_files_target_is_file(tmp_path: Path) -> None:
    """Verify error when list_files target is a file instead of a directory."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    f = sandbox / "file.txt"
    f.write_text("content", encoding="utf-8")

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    result = tool.execute({"directory": str(f)})
    assert result.success is False
    assert "is a file, not a directory" in (result.error or "")


def test_list_files_max_entries(tmp_path: Path) -> None:
    """Verify max_entries limits the number of directory entries returned."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    for i in range(10):
        (sandbox / f"item_{i}.txt").write_text(f"content {i}", encoding="utf-8")

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = ListFilesTool(security_config=config)

    result = tool.execute({"directory": str(sandbox), "max_entries": 3})
    assert result.success is True
    assert result.metadata["count"] == 3


def test_inspect_file_metadata(tmp_path: Path) -> None:
    """Verify file metadata inspection returns size, timestamps, and extension."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    test_file = sandbox / "notes.md"
    test_file.write_text("# Markdown Notes", encoding="utf-8")

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = InspectFileTool(security_config=config)

    result = tool.execute({"path": str(test_file)})
    assert result.success is True
    assert result.metadata["name"] == "notes.md"
    assert result.metadata["extension"] == ".md"
    assert result.metadata["is_file"] is True
    assert result.metadata["size_bytes"] > 0
    assert "notes.md" in result.output


def test_inspect_file_blocks_path_traversal(tmp_path: Path) -> None:
    """Verify file inspection blocks path traversal attempts."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    secret_file = tmp_path / "secret_passwords.txt"
    secret_file.write_text("top secret", encoding="utf-8")

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = InspectFileTool(security_config=config)

    result = tool.execute({"path": str(sandbox / ".." / "secret_passwords.txt")})
    assert result.success is False
    assert result.metadata.get("blocked") is True
    assert "Path traversal blocked" in (result.error or "")


def test_inspect_file_blocks_symlink_escape(tmp_path: Path, mocker: MockerFixture) -> None:
    """Verify symlink pointing outside allowed directory is blocked."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    symlink_file = sandbox / "symlink_secret.txt"
    symlink_file.write_text("dummy", encoding="utf-8")

    # Mock resolve on symlink_file to simulate pointing to an outside secret file
    outside_secret = tmp_path / "secret" / "passwords.txt"
    orig_resolve = Path.resolve

    def fake_resolve(self: Path, strict: bool = False) -> Path:
        if self.name == "symlink_secret.txt":
            return outside_secret
        return orig_resolve(self, strict=strict)

    mocker.patch.object(Path, "resolve", side_effect=fake_resolve, autospec=True)

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = InspectFileTool(security_config=config)

    result = tool.execute({"path": str(symlink_file)})
    assert result.success is False
    assert result.metadata.get("blocked") is True
    assert "Path traversal blocked" in (result.error or "")


def test_inspect_file_missing_file(tmp_path: Path) -> None:
    """Verify inspecting a missing file returns clean error."""
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()

    config = SecurityConfig(allowed_directories=[str(sandbox)])
    tool = InspectFileTool(security_config=config)

    result = tool.execute({"path": str(sandbox / "non_existent.txt")})
    assert result.success is False
    assert "does not exist" in (result.error or "")


# =====================================================================
# SystemInfoTool Tests
# =====================================================================


def test_system_info_tool_output(mocker: MockerFixture) -> None:
    """Verify SystemInfoTool aggregates platform, CPU, RAM, and battery metrics."""
    tool = SystemInfoTool()
    result = tool.execute({"topic": "all"})

    assert result.success is True
    assert "=== EAGLE System Telemetry ===" in result.output
    assert "OS:" in result.output
    assert "CPU:" in result.output
    assert "Memory:" in result.output

    metadata = result.metadata
    assert "platform" in metadata
    assert "os" in metadata["platform"]
    assert "cpu" in metadata
    assert "memory" in metadata
    assert "battery" in metadata


def test_system_info_topics(mocker: MockerFixture) -> None:
    """Verify querying specific telemetry topics (battery, cpu, memory, platform)."""
    tool = SystemInfoTool()

    r_battery = tool.execute({"topic": "battery"})
    assert r_battery.success is True
    assert "Battery:" in r_battery.output

    r_cpu = tool.execute({"topic": "cpu"})
    assert r_cpu.success is True
    assert "CPU:" in r_cpu.output

    r_mem = tool.execute({"topic": "memory"})
    assert r_mem.success is True
    assert "Memory:" in r_mem.output

    r_plat = tool.execute({"topic": "platform"})
    assert r_plat.success is True
    assert "OS:" in r_plat.output


def test_system_info_without_battery(mocker: MockerFixture) -> None:
    """Verify graceful handling when machine has no battery (AC desktop)."""
    mocker.patch("psutil.sensors_battery", return_value=None)
    tool = SystemInfoTool()

    result = tool.execute({})
    assert result.success is True
    assert result.metadata["battery"]["has_battery"] is False
    assert "No battery" in result.output


def test_system_info_psutil_exceptions(mocker: MockerFixture) -> None:
    """Verify system info tool handles sensor exceptions gracefully."""
    mocker.patch("psutil.cpu_percent", side_effect=OSError("CPU sensor failed"))
    mocker.patch("psutil.virtual_memory", side_effect=OSError("Memory sensor failed"))
    mocker.patch("psutil.sensors_battery", side_effect=OSError("Battery sensor failed"))

    tool = SystemInfoTool()
    result = tool.execute({"topic": "all"})
    assert result.success is True
    assert "=== EAGLE System Telemetry ===" in result.output


# =====================================================================
# Tool Registry & End-to-End Main Integration Tests
# =====================================================================


def test_register_default_tools_and_registry() -> None:
    """Verify register_default_tools registers all 6 concrete tools."""
    config = EagleConfig()
    registry = ToolRegistry()
    register_default_tools(registry, config)

    registered = registry.list_tools()
    assert "launch_app" in registered
    assert "open_website" in registered
    assert "web_search" in registered
    assert "list_files" in registered
    assert "inspect_file" in registered
    assert "system_info" in registered


def test_end_to_end_voice_command_to_tool_execution(mocker: MockerFixture) -> None:
    """Verify voice command -> router -> event bus -> tool execution -> completion event."""
    mock_browser = mocker.patch("webbrowser.open", return_value=True)

    config = EagleConfig()
    event_bus = EventBus()
    tool_registry = ToolRegistry()
    register_default_tools(tool_registry, config)
    router = CommandRouter(config=config, tool_registry=tool_registry, event_bus=event_bus)
    assert router is not None

    completed_events: list[ToolExecutionCompletedEvent] = []

    def on_tool_request(evt: ToolExecutionCompletedEvent) -> None:
        completed_events.append(evt)

    event_bus.subscribe(ToolExecutionCompletedEvent, on_tool_request)

    def handle_tool_request(evt: ToolExecutionRequestedEvent) -> None:
        res = tool_registry.execute(evt.tool_name, evt.arguments)
        event_bus.publish(
            ToolExecutionCompletedEvent(
                tool_name=evt.tool_name,
                success=res.success,
                result=res.output,
                error=res.error,
            )
        )

    event_bus.subscribe(ToolExecutionRequestedEvent, handle_tool_request)

    # Simulate user saying "search the web for artificial intelligence"
    event_bus.publish(SpeechTranscribedEvent(text="search the web for artificial intelligence"))

    assert len(completed_events) == 1
    assert completed_events[0].tool_name == "web_search"
    assert completed_events[0].success is True
    mock_browser.assert_called_once()


def test_end_to_end_app_launch_and_file_operation(mocker: MockerFixture, tmp_path: Path) -> None:
    """Verify voice command for launching apps and listing files routes to tool execution."""
    mock_process = mocker.MagicMock(spec=subprocess.Popen)
    mock_process.pid = 7777
    mocker.patch("subprocess.Popen", return_value=mock_process)

    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    (sandbox / "todo.txt").write_text("buy milk", encoding="utf-8")

    config = EagleConfig(
        security=SecurityConfig(
            allowed_directories=[str(sandbox)],
            allowed_applications={"notepad": "notepad.exe"},
        )
    )
    event_bus = EventBus()
    tool_registry = ToolRegistry()
    register_default_tools(tool_registry, config)
    router = CommandRouter(config=config, tool_registry=tool_registry, event_bus=event_bus)
    assert router is not None

    completed_events: list[ToolExecutionCompletedEvent] = []

    def on_completed(evt: ToolExecutionCompletedEvent) -> None:
        completed_events.append(evt)

    def on_requested(evt: ToolExecutionRequestedEvent) -> None:
        res = tool_registry.execute(evt.tool_name, evt.arguments)
        event_bus.publish(
            ToolExecutionCompletedEvent(
                tool_name=evt.tool_name,
                success=res.success,
                result=res.output,
                error=res.error,
            )
        )

    event_bus.subscribe(ToolExecutionCompletedEvent, on_completed)
    event_bus.subscribe(ToolExecutionRequestedEvent, on_requested)

    # 1. Voice command: "open notepad"
    event_bus.publish(SpeechTranscribedEvent(text="open notepad"))
    assert len(completed_events) == 1
    assert completed_events[0].tool_name == "launch_app"
    assert completed_events[0].success is True

    # 2. Voice command: "list files"
    event_bus.publish(SpeechTranscribedEvent(text="list files"))
    assert len(completed_events) == 2
    assert completed_events[1].tool_name == "list_files"
    assert completed_events[1].success is True
    assert "todo.txt" in (completed_events[1].result or "")

    # 3. Voice command: "check battery level"
    event_bus.publish(SpeechTranscribedEvent(text="what is my battery level"))
    assert len(completed_events) == 3
    assert completed_events[2].tool_name == "system_info"
    assert completed_events[2].success is True
