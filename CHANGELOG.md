# Changelog

All notable changes to the **EAGLE** project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
