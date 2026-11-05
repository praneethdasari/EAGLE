# Changelog

All notable changes to the **EAGLE** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [0.6.0] - 2026-11-05

### Added
- **PySide6 Desktop User Interface Subsystem (`eagle.ui`)**:
  - `eagle.ui.theme`: Custom Eagle Dark aesthetic (`#0B0E14` obsidian, `#151922` deep slate, `#00E5FF` cyber cyan, `#FFB300` eagle gold) and generated QSS stylesheet for all Qt controls.
  - `eagle.ui.visualizer`: Dynamic 32-bar audio reactive visualizer (`AudioVisualizerWidget`) with smooth decay interpolation, and pulsing state badge (`MicrophoneIndicatorWidget`).
  - `eagle.ui.conversation`: Scrollable history feed (`ConversationFeedWidget`) with differentiated user and assistant speech bubbles (`MessageBubble`), and structured `ToolExecutionCard` widgets with duration badges, JSON parameters, and formatted results.
  - `eagle.ui.status_panel`: Live sidebar (`StatusPanelWidget`) displaying assistant state, live CPU load, RAM utilization, active AI model, and security permissions.
  - `eagle.ui.input_bar`: Fallback typed command bar (`InputBarWidget`) with send button, microphone listening toggle button, and clear history controls.
  - `eagle.ui.settings_dialog`: 4-tab preferences modal dialog (`SettingsDialog`) enabling runtime customization of Voice/Audio, AI Providers, Security Allowlists, and UI layout with JSON persistence via `save_config()`.
  - `eagle.ui.bridge`: Thread-safe `EventBusQtBridge` forwarder routing decoupled `EventBus` events to Qt UI signals without blocking worker threads.
  - `eagle.ui.main_window`: Primary `MainWindow` orchestrating all widgets, keyboard shortcuts (`Ctrl+M`, `Ctrl+L`, `Ctrl+,`), background worker processing, and clean shutdown hooks.
- **Application Startup & Integration (`eagle.main`)**:
  - Integrated PySide6 GUI launch as the default mode when `--cli` is not specified.
  - Added session-scoped headless `qapp` test fixture (`QT_QPA_PLATFORM=offscreen`) enabling 100% offline automated UI testing.
- **Unit Test Suite Expansion**: Added 11 unit tests in `tests/unit/test_ui.py` covering all widgets, signal routing, settings persistence, and main window lifecycle, expanding test coverage to 128 tests passing (100% pass rate).

---

## [0.5.0] - 2026-11-03

### Added
- **Wake Word Detection Subsystem (`eagle.services.wake_word`)**:
  - `BaseWakeWordEngine`: Clean abstract interface for streaming audio chunk evaluation, availability detection, and state resets.
  - `SlidingSTTWakeWordEngine`: Completely local, offline keyword detection combining vocal RMS energy gating with sliding-window speech recognition and cooldown debounce.
  - `OpenWakeWordEngine`: Optional integration for openWakeWord ONNX acoustic models, with safe fallback to sliding STT when optional dependencies are omitted.
  - `MockWakeWordEngine`: Deterministic test engine supporting programmatic triggers, frame-count triggers, and simulated trigger bytes.
  - `get_wake_word_engine`: Configuration-driven factory selecting the appropriate engine based on `EagleConfig`.
- **Continuous Listening & State Machine Coordinator (`eagle.services.continuous_listener`)**:
  - `AssistantState` (`StrEnum`): Explicit state machine with 7 states: `IDLE`, `LISTENING_FOR_WAKE_WORD`, `CAPTURING_COMMAND`, `PROCESSING_COMMAND`, `SPEAKING`, `STOPPING`, and `ERROR`.
  - `VALID_TRANSITIONS`: Strict transition table enforcing legal lifecycle paths and raising `InvalidStateTransitionError` on illegal transitions.
  - `ContinuousListener`: Thread-safe coordinator running a dedicated background command worker thread (`EAGLE-CommandWorker`), trailing silence detection, maximum command duration timeout, self-speech echo suppression, and barge-in speech interruption.
  - Real-time event broadcasting: `WakeWordDetectedEvent`, `ListeningStateChangedEvent`, `AudioCaptureStartedEvent`, and `AudioCaptureStoppedEvent`.
- **Streaming Audio Capture Improvements (`eagle.services.audio_capture`)**:
  - Migrated stream creation to `sounddevice.RawInputStream` consuming raw 16-bit PCM CFFI buffers directly, eliminating hard dependencies on numpy.
  - Added real-time chunk callbacks, buffer draining (`drain_buffer_wav()`), and thread-safe buffer clearing.
- **CLI Commands & Diagnostics (`eagle.main`)**:
  - Added `:listen` command to toggle continuous listening with wake-word detection in CLI mode.
  - Added `:state` and `:status` commands to inspect live assistant state machine status.
- **Project Continuity & Recovery Guide (`docs/PROJECT_RECOVERY.md`)**:
  - Standardized recovery procedures for cloning, virtual environment creation, configuration, running, test execution, troubleshooting, and total data loss recovery.
  - Permanent development checkpoint recording verified commit state, features completed, and next tasks.
- **Unit Test Suite Expansion**: Added 19 unit tests across `tests/unit/test_wake_word.py` (8 tests) and `tests/unit/test_continuous_listener.py` (11 tests), bringing the total test suite to 117 passing tests (100% pass rate).

---

## [0.4.0] - 2026-10-27

### Added
- **AI Reasoning Subsystem (`eagle.services.ai_provider`)**:
  - `BaseAIProvider`: Abstract provider interface with credential availability check and typed response generation.
  - `OpenAICompatibleProvider`: Universal REST client compatible with OpenAI, Groq, Ollama, and local OpenAI-compatible endpoints with configurable timeouts, retries, and error handling.
  - `MockAIProvider`: Fully offline, deterministic AI provider for unit testing, test suites, and CI environments without external API keys.
  - `ConversationManager`: Sliding-window conversational turn manager enforcing `max_conversation_turns` while preserving the baseline system prompt.
  - `AIOrchestrator`: High-level orchestrator extracting tool schemas from `ToolRegistry`, dispatching structured tool calls up to `max_tool_iterations`, coordinating multi-turn tool loops, and synthesizing final answers.
- **AI Error Recovery & Resilience**:
  - Structured exception hierarchy for `AuthenticationError`, `NetworkTimeoutError`, `RateLimitExceededError`, `ModelUnavailableError`, and `InvalidResponseError`.
  - Spoken diagnostic feedback published over `EventBus` when AI provider fails or credentials are unconfigured.
- **Command Router & Main Integration**:
  - Connected `CommandRouter` conversational fallback to `AIOrchestrator.process_query()`.
  - Initialized `AIOrchestrator` in `eagle.main` with automatic event-driven feedback.
- **Unit Test Suite Expansion**: Added 18 unit tests in `tests/unit/test_ai_provider.py` covering providers, context pruning, tool call loops, allowlist enforcement, sensitive action gating, and network error handling (98 total tests passing).

---

## [0.3.0] - 2026-10-25


### Added
- **Desktop Application Launcher (`eagle.tools.apps.LaunchAppTool`)**: Secure process launching for approved applications registered in `SecurityConfig.allowed_applications` without shell injection (`shell=False`) or path traversal vulnerabilities.
- **Web Browsing & Search Tools (`eagle.tools.web`)**:
  - `OpenWebsiteTool`: Validates and navigates to HTTP and HTTPS URLs in the default browser, strictly blocking non-HTTP schemes, embedded credentials, and malformed hostnames.
  - `WebSearchTool`: Natural language web searches across Google, DuckDuckGo, and Bing with automatic detection and blocking of sensitive credentials (API tokens, passwords) or local file paths.
- **Sandboxed Filesystem Operations (`eagle.tools.files`)**:
  - `ListFilesTool`: Sandboxed directory listing strictly restricted to `SecurityConfig.allowed_directories`, featuring `..` traversal defense, symlink escape protection, formatted sizes/timestamps, and entry pagination.
  - `InspectFileTool`: Read-only, non-destructive file metadata inspection (size, created/modified dates, extension, symlink target).
- **System Telemetry Tool (`eagle.tools.system.SystemInfoTool`)**: System metrics reporting for OS platform, CPU utilization and cores, RAM usage, and battery status via `psutil`.
- **Command Routing & Tool Dispatch Integration**:
  - Registered all 6 concrete tools with `ToolRegistry` on startup in `eagle.main`.
  - Wired `CommandRouter` dispatch for `APP_LAUNCH`, `WEB_SEARCH`, `WEB_OPEN`, `SYSTEM_INFO`, and `FILE_OPERATION` (`list_files` and `inspect_file`).
  - Added interactive CLI execution loop and event-driven tool execution feedback via `ToolExecutionCompletedEvent`.
- **Unit & Integration Test Suite Expansion**: Added 33 comprehensive tests in `tests/unit/test_tools.py`, expanding the test suite to 80 passing tests (100% offline, 0 failures).

---

## [0.2.0] - 2026-10-21

### Added
- **Speech-to-Text Subsystem (`eagle.services.stt`)**: Created `BaseSTTEngine` interface, `TranscriptionResult` model, `FasterWhisperSTT` integration with CTranslate2 Whisper models, and deterministic `MockSTTEngine` for offline testing.
- **Text-to-Speech Subsystem (`eagle.services.tts`)**: Created `BaseTTSEngine` interface, `Pyttsx3TTSEngine` with Windows SAPI5 voice output, interruptibility support via `stop()`, and `MockTTSEngine`.
- **Audio Capture Subsystem (`eagle.services.audio_capture`)**: Created `AudioCaptureManager` for microphone stream recording via `sounddevice`, input device enumeration, RMS amplitude calculation for visualizers, and WAV packaging.
- **Voice Command Router (`eagle.services.command_router`)**: Built natural language command parsing with conversational filler stripping, regex pattern matching, and intent classification (`SYSTEM_CONTROL`, `APP_LAUNCH`, `WEB_SEARCH`, `WEB_OPEN`, `SYSTEM_INFO`, `FILE_OPERATION`, `CONVERSATION`).
- **EventBus Integration**: Connected voice transcription and text command events directly to the command router for automated action and speech dispatch.
- **Interactive CLI Routing**: Integrated `CommandRouter` into `eagle.main` with live intent classification and verbal speech output feedback.
- **Unit Test Suite Expansion**: Added 25 new unit tests across `test_stt.py`, `test_tts.py`, `test_audio_capture.py`, and `test_command_router.py` bringing test coverage to 47 passing tests.

---

## [0.1.0] - 2026-10-21

### Added
- **Project Blueprint & Architecture**: Established comprehensive technical specifications in `docs/ARCHITECTURE.md`, `docs/IMPLEMENTATION_PLAN.md`, `docs/SECURITY.md`, `docs/SETUP.md`, `docs/DEVELOPMENT.md`, `docs/DECISIONS.md`, and `docs/FEATURE_STATUS.md`.
- **Persistent AI Agent Instructions**: Created `AGENTS.md` defining mandatory conventions, security boundaries, and the commit/push workflow.
- **Environment & Build Tools**: Configured `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `.gitignore`, and `.env.example` targeting Python 3.13.
- **Core Configuration Engine (`eagle.core.config`)**: Implemented strongly-typed Pydantic v2 configuration manager supporting defaults, file loading, and path validation.
- **Structured Logging (`eagle.core.logging`)**: Implemented dual console and rotating disk logging with automatic regex-based credential redaction.
- **Custom Exceptions (`eagle.core.exceptions`)**: Created granular error hierarchy covering configuration, audio, AI, tool, and security violations.
- **Event Bus (`eagle.core.events`)**: Implemented thread-safe, decoupled publish-subscribe event dispatching system.
- **Tool Registry & Safety Foundation (`eagle.tools.base`, `eagle.tools.registry`)**: Implemented `BaseTool` abstraction and `ToolRegistry` with strict allowlisting and parameter validation.
- **Automated Test Suite**: Created offline unit tests in `tests/unit/` covering configuration, logging, event bus, exceptions, and tool registry.
