# EAGLE 🦅

> **EAGLE**: **E**nhanced **A**utonomous **G**eneral-purpose **L**ocal **E**xecutive  
> *A modular, secure, AI-powered desktop voice assistant built for Windows.*

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python: 3.13](https://img.shields.io/badge/Python-3.13-brightgreen.svg)](https://www.python.org/)
[![Code Style: Ruff](https://img.shields.io/badge/Code%20Style-Ruff-000000.svg)](https://github.com/astral-sh/ruff)
[![Tests: Pytest](https://img.shields.io/badge/Tests-Pytest-yellow.svg)](https://docs.pytest.org/)

---

## 📖 Overview

**EAGLE** is a desktop voice assistant designed for practical local productivity and computer interaction. It pairs responsive local voice processing with configurable AI reasoning and safe desktop automation.

### Key Highlights
- **Original Identity**: Bespoke dark eagle-themed desktop interface built with PySide6.
- **Local-First Voice**: Designed for low-latency offline speech recognition (Whisper) and responsive text-to-speech.
- **Safety by Design**: Sandboxed tool system with strict allowlists, path traversal protection, and mandatory confirmation for destructive operations.
- **Pluggable Intelligence**: Decoupled AI provider interface supporting both local models (Ollama) and cloud APIs (OpenAI, Anthropic, Gemini, Groq).
- **Text & Voice Dual Mode**: Seamless text-input fallback when audio hardware is unavailable or silent operation is preferred.

---

## 🛠️ System Requirements

- **Operating System**: Microsoft Windows 10/11 (64-bit AMD64)
- **Python**: Version 3.13 (recommended) or 3.11+
- **Audio**: Working microphone and audio output device

---

## 🚀 Quickstart & Installation

### 1. Clone the Repository
```powershell
git clone https://github.com/praneethdasari/EAGLE.git
cd EAGLE
```

### 2. Set Up Virtual Environment
```powershell
# Create isolated environment using Python 3.13
py -3.13 -m venv .venv

# Activate environment in PowerShell
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### 4. Configuration
Create your configuration file from the template:
```powershell
Copy-Item .env.example .env
```
*(Optional)* Add your preferred AI provider API key inside `.env`.

---

## 🧪 Running the Tests

EAGLE includes an automated test suite designed to run fast and completely offline:
```powershell
pytest
```
To run with detailed test execution output:
```powershell
pytest -v
```

---

## 🔒 Security Architecture

1. **Strict Tool Allowlist**: The AI model has no raw shell access. It can only trigger pre-registered and validated tools.
2. **Path Sandboxing**: File operations are restricted to explicitly configured directories. Path traversal outside safe boundaries is detected and blocked.
3. **Secret Redaction**: Structured logging automatically redacts API keys and bearer tokens from logs.
4. **Local Audio**: Microphone capture is processed locally and discarded immediately after transcription.

Read the full threat model in [docs/SECURITY.md](docs/SECURITY.md).

---

## 📚 Project Documentation

- [System Architecture](docs/ARCHITECTURE.md)
- [Setup & Installation Guide](docs/SETUP.md)
- [Developer Guide](docs/DEVELOPMENT.md)
- [Security & Permission Model](docs/SECURITY.md)
- [Feature Status Matrix](docs/FEATURE_STATUS.md)
- [Architectural Decisions (ADRs)](docs/DECISIONS.md)
- [Task Log](docs/TASK_LOG.md)
- [Milestone Implementation Plan](docs/IMPLEMENTATION_PLAN.md)
- [Persistent Agent Instructions (AGENTS.md)](AGENTS.md)

---

## 🗺️ Roadmap & Milestones

- **Milestone 0**: Environment Inspection & Blueprint (Completed)
- **Milestone 1**: Foundation & Testing Infrastructure (In Progress)
- **Milestone 2**: Voice Interaction Subsystem (STT & TTS)
- **Milestone 3**: Safe Desktop Actions & Sandboxing
- **Milestone 4**: AI Reasoning & Tool Calling Orchestrator
- **Milestone 5**: Wake Word Detection & Continuous Listening
- **Milestone 6**: PySide6 Desktop GUI
- **Milestone 7**: Release Hardening & Windows Executable Packaging
