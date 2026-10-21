# AGENTS.md — Persistent Instructions for EAGLE

This document is the persistent instruction file for all AI coding assistants (including Antigravity / Gemini) working on the **EAGLE** project.

> **CRITICAL RULE**: Every development session MUST begin by reading this file, inspecting the Git repository status, checking the active branch and configured remote, verifying test health, and reviewing recent task entries in `docs/TASK_LOG.md`.

---

## 1. Project Identity & Purpose

- **Official Name**: EAGLE
- **Full Form**: Enhanced Autonomous General-purpose Local Executive
- **Type**: Real, practical AI-powered desktop voice assistant.
- **Design Philosophy**:
  - Modular, testable, secure, documented, and recoverable.
  - Original eagle-inspired visual identity.
  - Consistent EAGLE branding across window titles, spoken greetings, logs, settings, and documentation.
  - No fake demos, no static mockups, no placeholder implementations passed off as finished code.
  - Never use "JARVIS" or copy proprietary Iron Man branding.

---

## 2. Core Architecture Rules

1. **Language & Environment**:
   - Python 3.13+ with type annotations on all public interfaces.
   - Isolated virtual environment in `.venv/`.
   - Windows 11 target OS with cross-platform awareness where possible.

2. **Layer Separation**:
   - `eagle.core`: Configuration, structured logging, exception hierarchy, event bus, credential storage.
   - `eagle.services`: Audio capture, speech-to-text (STT), text-to-speech (TTS), wake-word detection, and AI reasoning providers.
   - `eagle.tools`: Allowlisted system automation tools (file operations, app launching, web browsing, system info) with strict argument validation and safety boundaries.
   - `eagle.ui`: PySide6 dark-themed desktop interface with responsive visualizer, microphone indicator, conversation history, and controls.
   - `eagle.main`: Main application entry point orchestrating lifecycle and background workers.

3. **Concurrency & Responsiveness**:
   - Heavy tasks (audio recording, Whisper inference, network AI requests, subprocess launching) MUST run on background threads/workers.
   - The UI thread must never be blocked.

---

## 3. Security & Permission Model

Security is non-negotiable. Follow these strict rules:

1. **Tool Allowlist**: Only explicitly registered tools in `eagle.tools.registry` can be invoked.
2. **Input Validation**: Validate every tool argument strictly using Pydantic or schema validators.
3. **No Arbitrary Execution**: Never allow LLMs to execute arbitrary shell commands (`cmd.exe`, `powershell.exe`, `bash`), raw Python `eval`/`exec`, or unrestricted subprocesses.
4. **Filesystem Boundaries**: All file read/write operations must be constrained to configured allowed directories. Path traversal outside permitted boundaries (`..`) must be detected and rejected.
5. **Confirmation for Sensitive Actions**: File deletion, overwriting, bulk file moves, or system modifications require explicit user confirmation.
6. **Zero Secrets in Git**:
   - Never commit `.env` files, API keys, bearer tokens, or credentials.
   - All logs and exceptions must redact sensitive tokens before writing to console or disk.
   - Check `.gitignore` before every commit.

---

## 4. Coding & Quality Standards

- **Formatting & Linting**: Follow PEP 8 via `ruff`. Line length: 100 characters.
- **Typing**: Use static type hints (`typing` / built-in generics) checked by `mypy`.
- **Logging**: Use the structured logger from `eagle.core.logging`. Never use bare `print()` in production code.
- **Exceptions**: Use the custom hierarchy in `eagle.core.exceptions`. Catch specific exceptions; never use bare `except: pass`.
- **Configuration**: Use `pydantic-settings` / `pydantic` in `eagle.core.config` with default values and validation.

---

## 5. Testing Requirements

- Automated test framework: `pytest`.
- Run tests with: `.\.venv\Scripts\pytest.exe`
- Unit tests must mock external network calls, audio hardware, and OS-specific side-effects. Unit tests must run fast and completely offline.
- Do not require paid API keys to run unit or integration test suites.
- Never delete or weaken assertions to make tests pass.
- Every new feature or bug fix must include corresponding tests in `tests/`.

---

## 6. Git & GitHub Workflow

- **Configured Remote**: `origin` -> `https://github.com/praneethdasari/EAGLE.git`
- **Default Branch**: `main`
- **Workflow Steps for Every Task**:
  1. Inspect Git status: verify clean state or identify uncommitted changes.
  2. Implement changes with clean, focused code.
  3. Run automated tests and ensure 100% pass rate.
  4. Run linting / type checks where configured.
  5. Update `CHANGELOG.md`, `docs/FEATURE_STATUS.md`, `docs/TASK_LOG.md`, and relevant architecture docs.
  6. Review diff to ensure no secrets or unintended files are staged.
  7. Stage intended files: `git add <files>`
  8. Commit using Conventional Commits format (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`).
  9. Push to GitHub: `git push origin <branch>`.
  10. Verify push outcome and report commit SHA, branch, and status.

> **RULE**: A task is NOT complete until code is tested, documentation is updated, changes are committed, and the commit is pushed to GitHub. Never claim a push succeeded without verifying.

---

## 7. Documentation Maintenance

Maintain and keep synchronized:
- `README.md`: Overview, quickstart, setup, architecture, usage, troubleshooting.
- `CHANGELOG.md`: Chronological log of user-facing changes and fixes.
- `docs/ARCHITECTURE.md`: Technical design, components, and data flows.
- `docs/SETUP.md`: Step-by-step installation and environment instructions.
- `docs/DEVELOPMENT.md`: Developer guide, testing conventions, and contribution rules.
- `docs/SECURITY.md`: Threat model, permissions, data privacy, and safe practices.
- `docs/FEATURE_STATUS.md`: Truthful checklist of completed, in-progress, and planned features.
- `docs/DECISIONS.md`: Architectural Decision Records (ADRs).
- `docs/TASK_LOG.md`: Running log of completed development tasks with commit SHAs.
- `docs/IMPLEMENTATION_PLAN.md`: Milestone roadmap and progress tracking.

When conventions or architectures evolve, update this `AGENTS.md` file immediately.
