# Changelog

All notable changes to the **EAGLE** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
