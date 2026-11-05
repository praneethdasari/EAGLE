# EAGLE Project Recovery & Continuity Guide

> **Permanent Recovery Document**: This guide enables any developer, contributor, or AI assistant to independently restore, verify, run, and continue development of **EAGLE** (Enhanced Autonomous General-purpose Local Executive) from the GitHub repository without relying on prior conversation history or ephemeral chat sessions.

---

## 1. Project Overview & Repository

- **Repository URL**: `https://github.com/praneethdasari/EAGLE.git`
- **Default Branch**: `main`
- **Application Name**: EAGLE (Enhanced Autonomous General-purpose Local Executive)
- **Target OS**: Windows 11 (NT 10.0.26300.0 or compatible) with cross-platform awareness
- **Baseline Runtime**: Python 3.13.x

---

## 2. System Prerequisites

Before restoring the project, ensure the host system has:

1. **Git**: Version 2.30+ installed and accessible via PATH (`git --version`).
2. **Python 3.13**: Installed from [Python.org](https://www.python.org/) or Windows Store. Verify with `py -3.13 --version` or `python --version`.
3. **Audio Hardware**: Default microphone and speakers (for voice interaction; unit tests run completely offline with mock hardware).
4. **C++ Build Tools / Windows SDK**: Optional, only required if compiling wheels from C source. Standard wheels are pre-built.

---

## 3. Cloning & Environment Restoration

Follow these exact steps to clone and set up the isolated environment:

### Step 1: Clone Repository
```powershell
git clone https://github.com/praneethdasari/EAGLE.git
cd EAGLE
```

### Step 2: Create Python 3.13 Virtual Environment
```powershell
# Create isolated .venv
py -3.13 -m venv .venv
# Alternatively: python -m venv .venv
```

### Step 3: Activate Virtual Environment
```powershell
# In PowerShell:
.\.venv\Scripts\Activate.ps1

# If PowerShell execution policy restricts scripts:
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
.\.venv\Scripts\Activate.ps1

# In Command Prompt (cmd.exe):
.\.venv\Scripts\activate.bat
```

### Step 4: Upgrade Pip & Install Dependencies
```powershell
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\pip.exe install -r requirements.txt
.\.venv\Scripts\pip.exe install -r requirements-dev.txt
.\.venv\Scripts\pip.exe install -e .
```

---

## 4. Configuration & Credentials

### Configuration Files
- Primary configuration is saved to `config.json` in the project root if customized, or falls back to sensible defaults embedded in `eagle.core.config.EagleConfig`.
- Configuration schema is strictly validated via Pydantic v2.

### Environment Variables & Secrets
EAGLE enforces a **Zero Secrets in Git** policy.
- To use cloud AI reasoning providers (OpenAI, Groq, Anthropic), copy `.env.example` to `.env`:
  ```powershell
  cp .env.example .env
  ```
- Configure desired credentials in `.env`:
  ```env
  EAGLE_AI__PROVIDER=openai
  EAGLE_AI__API_KEY=your-api-key-here
  EAGLE_AI__MODEL_NAME=gpt-4o-mini
  ```
- **Local / Offline Fallback**: If no API key is provided, EAGLE operates seamlessly with local models via Ollama (`http://localhost:11434/v1`) or deterministic offline mock reasoning (`provider: "mock"`).
- **Never commit `.env` or credentials to Git.**

---

## 5. Source Code Organization

```text
EAGLE/
├── AGENTS.md                          # Persistent instructions for AI developers
├── README.md                          # Project overview, installation, usage
├── CHANGELOG.md                       # Version-by-version release history
├── pyproject.toml                     # Project metadata, linting, formatting, test config
├── requirements.txt                   # Production dependencies
├── requirements-dev.txt               # Development & test tooling
├── .env.example                       # Safe environment variable template
├── .gitignore                         # Secret, bytecode, and cache exclusion rules
│
├── docs/                              # Comprehensive documentation suite
│   ├── ARCHITECTURE.md                # System architecture, data flows, thread model
│   ├── SETUP.md                       # Step-by-step setup guide
│   ├── DEVELOPMENT.md                 # Developer workflow and conventions
│   ├── SECURITY.md                    # Threat model, sandboxing, safety controls
│   ├── FEATURE_STATUS.md              # Truthful capability checklist
│   ├── DECISIONS.md                   # Architectural Decision Records (ADRs)
│   ├── TASK_LOG.md                    # Chronological log of development tasks
│   ├── IMPLEMENTATION_PLAN.md         # Milestone roadmap and task tracking
│   └── PROJECT_RECOVERY.md            # This recovery and continuity document
│
├── eagle/                             # Main application source package
│   ├── __init__.py                    # Version & package metadata
│   ├── main.py                        # Application entry point & CLI loop
│   │
│   ├── core/                          # Foundational infrastructure
│   │   ├── __init__.py
│   │   ├── config.py                  # Pydantic v2 schemas and validation
│   │   ├── logging.py                 # Structured logger with secret masking
│   │   ├── exceptions.py              # Subsystem exception hierarchy
│   │   └── events.py                  # Publish-subscribe EventBus
│   │
│   ├── services/                      # Audio, voice, AI, and listening services
│   │   ├── __init__.py
│   │   ├── audio_capture.py           # Microphone capture & zero-numpy RawInputStream
│   │   ├── stt.py                     # Faster-Whisper & Mock STT engines
│   │   ├── tts.py                     # Pyttsx3 SAPI5 & Mock TTS engines with interruption
│   │   ├── wake_word.py               # Offline sliding STT, openWakeWord, & mock engines
│   │   ├── continuous_listener.py     # State machine coordinator & continuous listening
│   │   ├── ai_provider.py             # Pluggable AI reasoning & structured tool calling
│   │   └── command_router.py          # Intent classification & routing
│   │
│   ├── tools/                         # Secure desktop automation tools
│   │   ├── __init__.py
│   │   ├── base.py                    # BaseTool class & Pydantic argument schemas
│   │   ├── registry.py                # Allowlist registry & safety checks
│   │   ├── apps.py                    # Process launcher with path traversal protection
│   │   ├── web.py                     # Web browser opener & search query sanitizer
│   │   ├── files.py                   # Sandboxed directory reader & inspector
│   │   └── system.py                  # System telemetry (CPU, RAM, battery)
│   │
│   └── ui/                            # Desktop user interface (PySide6)
│       └── __init__.py
│
└── tests/                             # Comprehensive automated test suite
    ├── __init__.py
    ├── conftest.py                    # Pytest fixtures and mock configurations
    └── unit/                          # Isolated unit test suites
        ├── test_config.py             # Configuration validation tests
        ├── test_logging.py            # Logger & redaction tests
        ├── test_exceptions.py         # Exception hierarchy tests
        ├── test_events.py             # EventBus pub/sub tests
        ├── test_tool_registry.py      # Registry & allowlist tests
        ├── test_tools.py              # Desktop automation tool tests
        ├── test_stt.py                # Speech-to-text tests
        ├── test_tts.py                # Text-to-speech tests
        ├── test_audio_capture.py      # Audio capture tests
        ├── test_command_router.py     # Command routing tests
        ├── test_ai_provider.py        # AI reasoning & tool calling tests
        ├── test_wake_word.py          # Wake word engine tests
        └── test_continuous_listener.py# State machine & continuous listener tests
```

---

## 6. How to Run EAGLE

### Interactive CLI Mode (Recommended for Terminal Testing)
```powershell
.\.venv\Scripts\python.exe -m eagle.main --cli
```

In interactive CLI mode:
- Enter commands directly: `"open notepad"`, `"search for quantum computing"`, `"system info"`, `"list files"`.
- Use `:listen` to toggle continuous listening with wake word detection.
- Use `:state` or `:status` to inspect the assistant's state machine (`IDLE`, `LISTENING_FOR_WAKE_WORD`, `CAPTURING_COMMAND`, `PROCESSING_COMMAND`, `SPEAKING`).
- Use `exit`, `quit`, or press `Ctrl+C` to cleanly shut down.

---

## 7. How to Verify & Run Automated Tests

Automated testing is mandatory before committing or declaring work complete:

```powershell
# 1. Run full test suite (100% offline, no API keys or audio hardware required)
.\.venv\Scripts\pytest.exe

# 2. Run Ruff lint check
.\.venv\Scripts\ruff.exe check eagle tests

# 3. Run Ruff code formatting check
.\.venv\Scripts\ruff.exe format --check eagle tests

# 4. Run Mypy static type checker
.\.venv\Scripts\mypy.exe eagle tests
```

All four commands MUST exit with status 0 before pushing changes to GitHub.

---

## 8. Capability Matrix: Implemented vs Remaining

| Milestone | Subsystem / Feature | Status | Details |
| :--- | :--- | :--- | :--- |
| **Milestone 0** | Blueprint & Virtualenv | **Completed** | Python 3.13 `.venv`, project layout, git origin |
| **Milestone 1** | Foundation Infrastructure | **Completed** | Pydantic config, logging, exceptions, EventBus, ToolRegistry |
| **Milestone 2** | Voice Command Recognition | **Completed** | Audio capture, Faster-Whisper STT, Pyttsx3 TTS, intent router |
| **Milestone 3** | Desktop Automation Tools | **Completed** | Apps, web search/open, sandboxed files, system info |
| **Milestone 4** | AI Reasoning Engine | **Completed** | BaseAIProvider, OpenAI-compatible client, tool calling loop, memory manager |
| **Milestone 5** | Wake Word & Continuous Listening | **Completed** | Sliding STT / openWakeWord, AssistantState machine, interruption, ContinuousListener |
| **Milestone 6** | PySide6 Desktop GUI | **In Progress** | Dark eagle theme, audio visualizer, conversation history feed, status indicators |
| **Milestone 7** | Packaging & Distribution | **Planned** | PyInstaller build, Windows executable distribution |

---

## 9. Known Issues & Troubleshooting Procedures

1. **Audio Capture Dependency (`numpy` absent)**:
   - *Symptom*: Older `sounddevice.InputStream` threw `MicrophoneNotFoundError: No module named 'numpy'`.
   - *Resolution*: `AudioCaptureManager` utilizes `sounddevice.RawInputStream` which consumes raw 16-bit CFFI memory buffers directly without requiring numpy.
2. **Missing Audio Hardware in CI / Sandbox**:
   - *Symptom*: Sounddevice fails to open default device if no microphone is connected.
   - *Resolution*: Unit tests use `MockWakeWordEngine`, `MockSTTEngine`, `MockTTSEngine`, and `feed_simulated_pcm()`, running 100% offline without physical hardware.
3. **PowerShell Script Execution Policy**:
   - *Symptom*: `.\.venv\Scripts\Activate.ps1 cannot be loaded because running scripts is disabled`.
   - *Resolution*: Run `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process` in the current PowerShell terminal session.

---

## 10. Project Recovery After Total Data Loss

If the local project directory is deleted or corrupted:

1. Clone the GitHub repository:
   ```powershell
   git clone https://github.com/praneethdasari/EAGLE.git
   cd EAGLE
   ```
2. Read `AGENTS.md`, `README.md`, and this file (`docs/PROJECT_RECOVERY.md`).
3. Re-create the `.venv` and install dependencies (Section 3).
4. Run tests to confirm integrity:
   ```powershell
   .\.venv\Scripts\pytest.exe
   ```
5. Consult `docs/TASK_LOG.md` to identify the last completed task.
6. Check `docs/IMPLEMENTATION_PLAN.md` and resume from the next roadmap task (currently Milestone 6: PySide6 Desktop GUI).

---

## 11. Development Checkpoint

This checkpoint represents the verified state at the conclusion of the latest development session:

- **Session Date**: 2026-11-05
- **Last Completed Task**: Task 006 — Polished EAGLE Desktop Interface (PySide6) (Milestone 6)
- **Current Git Branch**: `main`
- **Configured Remote**: `origin` -> `https://github.com/praneethdasari/EAGLE.git`
- **Latest Verified Commit Hash**: `5a4a3ae`
- **Latest Synchronized GitHub Commit**: `5a4a3ae`
- **Features Completed in Session**:
  - Custom dark eagle-themed PySide6 desktop interface (`eagle/ui/theme.py`)
  - Dynamic 32-bar audio reactive visualizer widget (`eagle/ui/visualizer.py`)
  - Pulsing microphone state indicator badge (`eagle/ui/visualizer.py`)
  - Conversation history feed with user/assistant bubbles and structured `ToolExecutionCard` widgets (`eagle/ui/conversation.py`)
  - Real-time system telemetry sidebar panel (`eagle/ui/status_panel.py`)
  - Fallback typed input bar with send button and microphone toggle (`eagle/ui/input_bar.py`)
  - Multi-tab preferences modal dialog with JSON persistence (`eagle/ui/settings_dialog.py`)
  - Thread-safe `EventBusQtBridge` decoupling background workers from Qt widgets (`eagle/ui/bridge.py`)
  - Desktop `MainWindow` orchestrating application lifecycle and shutdown hooks (`eagle/ui/main_window.py`)
  - Automated headless offscreen UI test suite with session-scoped `qapp` (`tests/unit/test_ui.py`)
- **Features In Progress**:
  - Milestone 7: Packaging & Release Hardening (PyInstaller build configuration, end-to-end integration validation, v0.1.0 release notes)
- **Outstanding Errors & Blockers**:
  - None. 0 errors, 0 blockers.
- **Tests Executed & Results**:
  - `pytest`: 128/128 tests passing (100% pass rate in ~4.3s)
  - `ruff check eagle tests`: Clean (0 errors)
  - `ruff format --check eagle tests`: Clean (0 formatting issues across 48 files)
  - `mypy eagle tests`: Clean (Success: no issues found in 48 source files)
- **Next Recommended Task**:
  - Milestone 7: Implement PyInstaller packaging configuration, execute Windows 11 executable build, perform end-to-end integration review, and tag v0.1.0.
  - Milestone 6: PySide6 Desktop User Interface implementation (`eagle/ui/`).
