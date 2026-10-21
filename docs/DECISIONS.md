# Architectural Decision Records (ADRs)

This document tracks significant architectural decisions for **EAGLE**.

---

## ADR 001: Python 3.13 as Baseline Runtime Environment
- **Date**: 2026-10-21
- **Status**: Accepted
- **Context**: Host environment provides Python 3.13 and Python 3.14. Python 3.14 was recently released and many critical desktop/C-extension libraries (PySide6, sounddevice, torch, ctranslate2) lack stable prebuilt Windows wheels.
- **Decision**: Standardize on Python 3.13.1 within a project-isolated virtual environment (`.venv`).
- **Consequences**: Ensures robust wheel availability, smooth installation, and complete stability across audio and GUI modules without requiring compilation from source.

---

## ADR 002: PySide6 for Desktop Interface
- **Date**: 2026-10-21
- **Status**: Accepted
- **Context**: EAGLE requires a responsive, high-framerate desktop interface with custom dark theme aesthetics, custom audio visualizer widgets, low latency, and native Windows integration.
- **Decision**: Select PySide6 (official Qt for Python) as the primary GUI framework.
- **Consequences**: Superior performance, cross-platform UI primitives, robust threading via `QThread` / `QObject` signals, and separation of UI rendering from background tasks.

---

## ADR 003: Pydantic v2 for Configuration & Tool Schemas
- **Date**: 2026-10-21
- **Status**: Accepted
- **Context**: Robust desktop assistants must guard against malformed configuration files and invalid tool arguments produced by AI models.
- **Decision**: Use Pydantic v2 for all configuration models, environment parsing, and tool parameter validation schemas.
- **Consequences**: Strongly typed, fast C-core validation, clear error messages, and automatic generation of JSON schemas for LLM tool definitions.

---

## ADR 004: Event-Driven Subsystem Communication
- **Date**: 2026-10-21
- **Status**: Accepted
- **Context**: Direct synchronous calls between audio threads, AI network requests, tool execution, and the UI loop lead to UI freezing, thread safety hazards, and circular dependencies.
- **Decision**: Introduce a thread-safe publish-subscribe Event Bus (`eagle.core.events.EventBus`) with typed event payloads.
- **Consequences**: Clean separation of concerns; components can listen only to events they care about (e.g. `SpeechRecognizedEvent`, `ToolExecutionEvent`, `StateChangedEvent`).

---

## ADR 005: Allowlisted Tool Execution & Sandboxed File Operations
- **Date**: 2026-10-21
- **Status**: Accepted
- **Context**: Unrestricted shell or script execution poses an unacceptable security risk when driven by AI reasoning.
- **Decision**: Maintain a strict tool allowlist in `ToolRegistry`. Ban arbitrary shell execution. Restrict filesystem tools to explicitly configured user directories, blocking path traversal (`..`).
- **Consequences**: Prevents unauthorized modifications, protects system integrity, and satisfies strict security standards.
