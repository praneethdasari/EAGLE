# EAGLE Architecture & System Design

## 1. Overview

**EAGLE** (Enhanced Autonomous General-purpose Local Executive) is designed as a modular, decoupled desktop voice assistant. It follows strict separation of concerns across audio input/output, AI reasoning, desktop automation, and user interface.

```mermaid
graph TD
    User([User]) <-->|Voice / Audio| AudioCapture[Audio Capture & STT]
    User <-->|Text & GUI| GUI[PySide6 Desktop Interface]
    
    AudioCapture -->|SpeechEvent| EventBus[Event Bus / Orchestrator]
    GUI -->|TextInputEvent| EventBus
    
    EventBus <-->|Query & Context| AIProvider[AI Reasoning Service]
    AIProvider <-->|ToolCallRequest| ToolRegistry[Tool Allowlist & Registry]
    
    ToolRegistry -->|Permission Check| PermManager[Permission & Safety Engine]
    PermManager -->|Execute if Approved| DesktopTools[Desktop & System Tools]
    DesktopTools -->|ToolResult| EventBus
    
    EventBus -->|SpeechResponse| TTSService[Text-to-Speech Engine]
    TTSService -->|Audio Output| User
    EventBus -->|UIUpdateEvent| GUI
```

---

## 2. Subsystem Directory Structure

```text
EAGLE/
├── AGENTS.md                  # Persistent instructions for AI agents
├── README.md                  # Project overview, installation, and usage
├── CHANGELOG.md               # Versioned change history
├── pyproject.toml             # Build, linting, formatting, and test settings
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development & testing dependencies
├── .env.example               # Template for optional API keys
├── .gitignore                 # Strict rules to prevent secret/artifact leakage
│
├── docs/                      # Comprehensive technical documentation
│   ├── ARCHITECTURE.md        # This document
│   ├── SETUP.md               # Setup and environment walkthrough
│   ├── DEVELOPMENT.md         # Developer guide, style guide, and test conventions
│   ├── SECURITY.md            # Threat model, safety rules, permission system
│   ├── FEATURE_STATUS.md      # Truthful matrix of features and statuses
│   ├── DECISIONS.md           # Architecture Decision Records (ADRs)
│   ├── TASK_LOG.md            # Development task logs with commit SHAs
│   └── IMPLEMENTATION_PLAN.md # Milestone tracker
│
├── eagle/                     # Main application package
│   ├── __init__.py
│   ├── main.py                # Entry point
│   │
│   ├── core/                  # Core infrastructure
│   │   ├── __init__.py
│   │   ├── config.py          # Pydantic configuration model and loader
│   │   ├── logging.py         # Structured logging with secret redaction
│   │   ├── exceptions.py      # Custom exception hierarchy
│   │   └── events.py          # Decoupled publish/subscribe event bus
│   │
│   ├── services/              # External interfaces and service clients
│   │   ├── __init__.py
│   │   ├── audio_capture.py   # Microphone listener and VAD
│   │   ├── stt.py             # Speech-to-Text abstraction
│   │   ├── tts.py             # Text-to-Speech abstraction
│   │   ├── wake_word.py       # Wake word engine
│   │   └── ai_provider.py     # Pluggable AI reasoning providers
│   │
│   ├── tools/                 # Safe system automation tools
│   │   ├── __init__.py
│   │   ├── base.py            # BaseTool abstraction and schemas
│   │   ├── registry.py        # Tool registry and allowlist enforcement
│   │   ├── apps.py            # Application launcher
│   │   ├── web.py             # Web browsing and search
│   │   ├── files.py           # Sandboxed file operations
│   │   └── system.py          # Safe system telemetry
│   │
│   └── ui/                    # PySide6 desktop user interface
│       ├── __init__.py
│       ├── main_window.py     # Main application window
│       ├── widgets/           # Visualizer, transcript, status cards
│       ├── styles/            # QSS / dark eagle styling
│       └── dialogs/           # Permission confirmations, settings
│
└── tests/                     # Automated test suite
    ├── __init__.py
    ├── conftest.py            # Pytest fixtures and mocks
    ├── unit/                  # Fast, offline unit tests
    └── integration/           # Real component interaction tests
```

---

## 3. Core Subsystems & Responsibilities

### 3.1 `eagle.core.config`
- Single source of truth for all runtime settings.
- Uses Pydantic v2 for data validation and schema coercion.
- Loads from `config.json` with fallback to safe defaults.
- Validates filesystem directory paths, allowed applications, and audio settings.

### 3.2 `eagle.core.logging`
- Formats logs into human-readable console output and structured disk logs.
- Includes a token/key sanitizer filter to prevent API keys or secrets from leaking to disk or standard output.

### 3.3 `eagle.core.exceptions`
- Hierarchy:
  - `EagleError` (Root)
    - `ConfigurationError`
    - `AudioError` (e.g. `MicrophoneNotFoundError`, `TranscriptionError`, `SpeechSynthesisError`)
    - `AIProviderError` (e.g. `ModelUnavailableError`, `RateLimitError`)
    - `ToolError` (e.g. `ToolNotFoundError`, `ToolExecutionError`, `PermissionDeniedError`, `SecurityViolationError`)

### 3.4 `eagle.core.events`
- Event-driven communication decouples UI, audio processing, and AI execution.
- Prevents tight coupling or circular imports between services.

### 3.5 `eagle.tools`
- Every tool inherits from `BaseTool` with typed Pydantic parameters schema and structured `ToolResult`.
- The `ToolRegistry` enforces an allowlist: only explicitly registered tools can ever be executed.
- Sensitive tools require an explicit confirmation token or approval callback before execution.
- **`LaunchAppTool` (`eagle/tools/apps.py`)**:
  - Validates requested application against `SecurityConfig.allowed_applications`.
  - Rejects path traversal sequences and untrusted executable path overrides.
  - Spawns subprocesses detached using argument arrays (`[executable]`), never raw shell strings (`shell=False`).
- **`OpenWebsiteTool` (`eagle/tools/web.py`)**:
  - Enforces HTTP/HTTPS protocol validation, blocking dangerous schemes (`file:`, `javascript:`, `data:`, `ftp:`).
  - Sanitizes hostnames, blocks embedded user/password credentials, and opens URLs in the operating system default browser.
- **`WebSearchTool` (`eagle/tools/web.py`)**:
  - Formats natural language web queries across configurable search providers (Google, DuckDuckGo, Bing).
  - Inspects queries to prevent accidental leakage of local file paths, API keys, bearer tokens, or secrets.
- **`ListFilesTool` (`eagle/tools/files.py`)**:
  - Sandboxed directory reader restricted strictly to `SecurityConfig.allowed_directories`.
  - Blocks `..` traversal and symlink escapes using canonical path resolution (`Path.resolve()`).
  - Returns structured, human-readable directory listings with file sizes, timestamps, and entry limits.
- **`InspectFileTool` (`eagle/tools/files.py`)**:
  - Inspects file metadata (size, created, modified, type, symlink status) within allowed boundaries.
  - Non-destructive and strictly read-only; does not modify files or read arbitrary file contents.
- **`SystemInfoTool` (`eagle/tools/system.py`)**:
  - Reads non-invasive telemetry metrics: operating system platform, CPU utilization and cores, RAM usage, and battery level via `psutil`.
  - Supports topic-based filtering (`battery`, `cpu`, `memory`, `platform`, `all`). Gracefully handles unavailable sensors.

### 3.6 `eagle.services`
- **Audio Capture (`audio_capture.py`)**: Safely enumerates microphones via `sounddevice`, captures mono 16-bit PCM streams, calculates RMS amplitude for UI audio visualizers, and packages data into WAV containers.
- **Speech-to-Text (`stt.py`)**: Abstract `BaseSTTEngine` with implementations for local `FasterWhisperSTT` and offline deterministic `MockSTTEngine`.
- **Text-to-Speech (`tts.py`)**: Abstract `BaseTTSEngine` providing Windows SAPI5 voice output via `Pyttsx3TTSEngine` with immediate `stop()` speech interruption support and offline `MockTTSEngine`.
- **Command Router (`command_router.py`)**: Normalizes input speech/text, extracts conversational fillers, classifies intents (`SYSTEM_CONTROL`, `APP_LAUNCH`, `WEB_SEARCH`, `WEB_OPEN`, `SYSTEM_INFO`, `FILE_OPERATION`, `CONVERSATION`), and dispatches events via the `EventBus`.

### 3.7 `eagle.services.ai_provider`
- **AI Provider Abstraction (`BaseAIProvider`)**: Clean pluggable interface defining `generate_response(messages, tools)` and `is_available()`.
- **Mock Provider (`MockAIProvider`)**: Deterministic, offline reasoning engine for unit testing, test suites, and CI environments without network access or API fees.
- **OpenAI-Compatible Client (`OpenAICompatibleProvider`)**: Universal REST client supporting OpenAI, Groq, local Ollama, and OpenAI-compatible endpoints with configurable timeouts, retries, and comprehensive HTTP/network error mapping.
- **Conversation Context Management (`ConversationManager`)**: Sliding-window context manager enforcing configurable `max_conversation_turns` while permanently preserving the baseline system persona prompt.
- **AI Orchestrator (`AIOrchestrator`)**:
  - Dynamically extracts tool schemas from `ToolRegistry` and presents them as standard function definitions.
  - Coordinates multi-turn tool loops up to `max_tool_iterations` per turn.
  - Emits `ToolExecutionRequestedEvent`, executes actions safely via `ToolRegistry`, appends structured `role="tool"` results, and summarizes outcomes to the user.
  - Catches provider errors (`AuthenticationError`, `NetworkTimeoutError`, `RateLimitExceededError`, `ModelUnavailableError`) and emits clear, user-friendly spoken feedback.


### 3.8 `eagle.services.wake_word` & `eagle.services.continuous_listener`
- **Wake Word Engines (`eagle/services/wake_word.py`)**:
  - `BaseWakeWordEngine`: Core interface for streaming chunk evaluation (`process_audio(pcm_data)`), readiness check, and buffer reset.
  - `SlidingSTTWakeWordEngine`: Completely local, offline keyword detection combining vocal RMS energy gating with sliding-window speech-to-text recognition and cooldown debounce.
  - `OpenWakeWordEngine`: Optional integration with ONNX-based openWakeWord models; automatically falls back to sliding STT if optional dependencies are omitted.
  - `MockWakeWordEngine`: Deterministic test engine supporting programmatic, frame-count, and synthetic keyword triggers for automated test suites.
  - `get_wake_word_engine()`: Configuration-driven factory returning the appropriate engine based on `EagleConfig`.
- **Continuous Listening & State Machine (`eagle/services/continuous_listener.py`)**:
  - `AssistantState`: Explicit state enumeration (`IDLE`, `LISTENING_FOR_WAKE_WORD`, `CAPTURING_COMMAND`, `PROCESSING_COMMAND`, `SPEAKING`, `STOPPING`, `ERROR`).
  - `VALID_TRANSITIONS`: Strict transition table; illegal state shifts raise `InvalidStateTransitionError`.
  - `ContinuousListener`: Thread-safe coordinator running background command worker queue, detecting trailing silence and maximum command duration timeouts, suppressing self-speech, and interrupting TTS on user barge-in.
  - Broadcasts `WakeWordDetectedEvent`, `ListeningStateChangedEvent`, `AudioCaptureStartedEvent`, and `AudioCaptureStoppedEvent` across the `EventBus`.

### 3.9 `eagle.ui` — PySide6 Desktop Interface
- **Theme & Palette (`eagle/ui/theme.py`)**: Custom Eagle Dark aesthetic featuring deep obsidian (`#0B0E14`), deep slate (`#151922`), cyber cyan (`#00E5FF`), and eagle gold (`#FFB300`) with dynamic QSS stylesheet generation for all Qt widgets.
- **Audio Visualizer & Microphone Indicator (`eagle/ui/visualizer.py`)**:
  - `AudioVisualizerWidget`: Real-time 32-bar animated equalizer reacting to live microphone RMS amplitude with smooth decay interpolation.
  - `MicrophoneIndicatorWidget`: Clickable pill badge with pulsating status glow for all assistant states (`LISTENING_FOR_WAKE_WORD`, `CAPTURING_COMMAND`, `PROCESSING_COMMAND`, `SPEAKING`, `IDLE`).
- **Conversation History Feed (`eagle/ui/conversation.py`)**:
  - `ConversationFeedWidget`: Scrollable container displaying formatted conversation bubbles and tool execution cards.
  - `MessageBubble`: Differentiated user and assistant speech bubbles with timestamps and rich text formatting.
  - `ToolExecutionCard`: Structured expandable card displaying tool names, execution duration, status badges, parameter previews, and structured output formatting.
- **Status Panel (`eagle/ui/status_panel.py`)**: Live sidebar displaying current assistant state, system telemetry (CPU load and RAM utilization via `psutil`), active AI provider/model, and tool security permissions.
- **Input Bar (`eagle/ui/input_bar.py`)**: Bottom docked fallback text entry bar with send button, microphone listening toggle button, and clear history controls.
- **Settings Dialog (`eagle/ui/settings_dialog.py`)**: 4-tab preferences modal enabling runtime customization of Voice/Audio, AI Providers, Security Allowlists, and UI layout with JSON persistence via `save_config()`.
- **EventBus Qt Bridge (`eagle/ui/bridge.py`)**: `EventBusQtBridge(QObject)` translating decoupled `EventBus` events into Qt signals, ensuring all UI updates occur safely on the main Qt GUI thread.
- **Main Window (`eagle/ui/main_window.py`)**: Central window orchestrating all components, keyboard shortcuts (`Ctrl+M`, `Ctrl+L`, `Ctrl+,`), background worker processing, and clean application shutdown.

---

### 3.10 Packaging & Path Architecture (eagle.core.paths & eagle.spec)
- **Runtime Detection (eagle/core/paths.py)**: is_frozen() inspects sys.frozen and sys._MEIPASS to discern between running from raw source vs. bundled PyInstaller package.
- **Resource Resolution**: get_app_root() locates assets in the PyInstaller extraction folder or repository root.
- **Data Isolation**: User configurations are persistently stored in %APPDATA%\EAGLE\config.json, logs in %APPDATA%\EAGLE\logs\eagle.log, and model caches in %LOCALAPPDATA%\EAGLE\models\, ensuring application updates never overwrite user settings.
- **PyInstaller Specification (eagle.spec)**: Configured in onedir mode (COLLECT) with console=False for zero-terminal launch, bundling hidden imports (sounddevice, pyttsx3, pydantic, psutil, PySide6) and stripping development utilities (pytest, mypy, 
uff, 	kinter).
- **Automated Packaging (scripts/build_windows.py)**: Automated build runner enforcing unit test pass, ruff lint clean, and mypy type checks before compiling the Windows binary and generating cryptographic SHA-256 checksums (dist/SHA256SUMS.txt).

---

## 4. Concurrency & Threading Model

- **Main Thread**: Runs the PySide6 Qt event loop or interactive CLI input loop, handling user gestures and keyboard commands.
- **Microphone Stream Thread**: Background audio callback managed by `sounddevice.RawInputStream`, streaming raw 16-bit PCM chunks into `AudioCaptureManager` without memory copying or numpy requirements.
- **Command Worker Thread (`EAGLE-CommandWorker`)**: Background worker thread managed by `ContinuousListener`, consuming audio command bytes from a thread-safe queue to perform STT transcription, command routing, and AI reasoning without blocking audio capture.
- **TTS Playback Worker Thread**: Dedicated speech synthesis thread allowing immediate `stop()` interruption when a barge-in event occurs.
- **Event Bus Decoupling**: All inter-thread state and data communication flows asynchronously through the thread-safe `EventBus`.
