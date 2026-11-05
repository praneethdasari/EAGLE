# EAGLE — Windows 11 Installation & Setup Guide

This guide explains how to install, configure, and run **EAGLE** (Enhanced Autonomous General-purpose Local Executive) on Windows 11 systems, either as a standalone packaged application or from source.

---

## 1. System Requirements

- **Operating System**: Windows 11 (64-bit) or Windows 10 (version 1809+ 64-bit).
- **Processor**: Intel Core i5 / AMD Ryzen 5 or better.
- **Memory (RAM)**: 8 GB minimum (16 GB recommended for local Whisper STT).
- **Storage**: 500 MB free disk space for application files; additional 1 GB if caching local speech models.
- **Audio Hardware**:
  - Working microphone (integrated or external USB headset).
  - Audio output device (speakers or headphones).
- **Permissions**: Standard user permissions (no Administrator elevation required for normal operation).

---

## 2. Option A: Standalone Packaged Release (Recommended for Users)

The standalone release bundles the Python runtime, PySide6 GUI framework, and audio capture dependencies. No Python installation is needed.

### Installation Steps:
1. Download the release package (`EAGLE-v0.1.0-windows-x64.zip` or folder) from the [Releases page](https://github.com/praneethdasari/EAGLE/releases).
2. Extract the archive to your preferred location, e.g.:
   ```text
   C:\Users\<YourUsername>\AppData\Local\Programs\EAGLE\
   ```
   *Or keep it in a portable directory on any drive.*
3. Verify release integrity using the checksum file:
   ```powershell
   Get-FileHash -Algorithm SHA256 .\EAGLE\EAGLE.exe
   ```
   Compare the output hash against `SHA256SUMS.txt`.
4. Double-click `EAGLE.exe` to launch the application.
5. *(Optional)* Right-click `EAGLE.exe` and select **Show more options -> Create shortcut** and move the shortcut to your Desktop or Start Menu.

---

## 3. Option B: Running from Source (Recommended for Developers)

If developing or running directly from Git:

1. **Clone the repository**:
   ```powershell
   git clone https://github.com/praneethdasari/EAGLE.git
   cd EAGLE
   ```
2. **Create Python virtual environment** (Python 3.13+ required):
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. **Install dependencies**:
   ```powershell
   pip install --upgrade pip
   pip install -r requirements.txt
   pip install -r requirements-dev.txt
   ```
4. **Launch the application**:
   ```powershell
   python -m eagle.main --gui
   ```

---

## 4. Configuration & User Data Architecture

EAGLE adheres strictly to Windows application data isolation standards:

| Directory | Windows Path | Contents |
|---|---|---|
| **User Configuration** | `%APPDATA%\EAGLE\config.json` | Settings, allowlists, audio thresholds, AI provider parameters |
| **Secrets & Keys** | `%APPDATA%\EAGLE\.env` | API keys (`GEMINI_API_KEY`, `OPENAI_API_KEY`, etc.) |
| **Application Logs** | `%APPDATA%\EAGLE\logs\eagle.log` | Structured JSON and standard rotating operational logs |
| **Model Cache** | `%LOCALAPPDATA%\EAGLE\models\` | Downloaded speech-to-text models (Whisper / Vosk) |

Updating or replacing `EAGLE.exe` will **never** delete or overwrite your settings or history.

---

## 5. First-Time Setup & Configuration

### A. Microphone & Privacy Permissions
1. Open Windows **Settings** (`Win + I`).
2. Navigate to **Privacy & security -> Microphone**.
3. Ensure **Microphone access** is turned **On**.
4. Ensure **Let desktop apps access your microphone** is turned **On**.

### B. Configuring AI Providers
EAGLE functions 100% offline out-of-the-box using built-in system tools (calculator, notepad, system info, file inspection, website navigation).

To enable generative AI conversational reasoning:
1. Open the EAGLE desktop interface.
2. Click the **Settings** button (gear icon in the top header).
3. Under the **AI Provider** tab:
   - Select your provider: `gemini` (Google Gemini), `openai` (OpenAI), or `anthropic` (Claude).
   - Enter your API Key or store it in `%APPDATA%\EAGLE\.env`:
     ```bash
     EAGLE_AI__API_KEY=your_gemini_api_key_here
     ```
   - Click **Save Settings**.

---

## 6. Voice Assistant Controls & Usage

### Wake-Word & Voice Control
- Say **"Eagle"** or click the **Microphone Indicator** in the header.
- The voice visualizer will glow cyan/blue indicating active command capture.
- Speak your command clearly, for example:
  - *"Eagle, what is the system telemetry?"*
  - *"Eagle, open notepad."*
  - *"Eagle, search the web for quantum computing."*
  - *"Eagle, list files in Documents."*
  - *"Eagle, what is 25 times 48?"*

### Barge-In & Interruption
- You can interrupt EAGLE at any point while it is speaking by clicking the microphone button or saying the wake-word again. Spoken TTS will stop immediately.

### Text Fallback
- Type any query or command in the bottom command input bar and press `Enter`.

---

## 7. Uninstallation & Clean Removal

To cleanly remove EAGLE from your system:

1. Close the application.
2. Delete the application installation directory (e.g., `dist\EAGLE` or `%LOCALAPPDATA%\Programs\EAGLE`).
3. *(Optional)* If you wish to remove all settings and cached logs:
   ```powershell
   Remove-Item -Recurse -Force "$env:APPDATA\EAGLE"
   Remove-Item -Recurse -Force "$env:LOCALAPPDATA\EAGLE"
   ```
