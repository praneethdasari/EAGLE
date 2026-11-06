# EAGLE — Windows Build & Packaging Guide

This guide details the complete build process, configuration, and reproducible workflow for packaging **EAGLE** (Enhanced Autonomous General-purpose Local Executive) v0.1.0 into a standalone, relocatable Windows 11 executable distribution.

---

## 1. Overview & Packaging Philosophy

EAGLE is designed as a modular desktop voice assistant targeting Windows 11. To deliver a seamless user experience without requiring end-users to install Python, configure CFFI compilers, or set up virtual environments, EAGLE utilizes **PyInstaller** configured in **onedir** directory collection mode.

### Key Packaging Decisions:
1. **Onedir Collection Mode (`COLLECT`)**:
   - Rather than packing all binaries into a single monolithic `.exe` that must decompress 150+ MB of DLLs into `%TEMP%` on every startup, EAGLE produces an application directory (`dist/EAGLE/`).
   - This achieves instantaneous launch speeds (<1 second) and prevents anti-virus scanning delays caused by runtime self-extraction.
2. **Windowed / Subsystem Mode (`console=False`)**:
   - Spawns as a native Windows GUI application without an ugly trailing black console window.
3. **Data and Configuration Isolation**:
   - Code assets and Qt resources are loaded via `eagle.core.paths.get_app_root()`, which gracefully detects whether the app is running in frozen PyInstaller mode (`sys._MEIPASS`) or raw source mode.
   - User configuration is stored in `%APPDATA%\EAGLE\config.json`.
   - Logs are directed to `%APPDATA%\EAGLE\logs\eagle.log`.
   - Local AI models and temporary cache are stored in `%LOCALAPPDATA%\EAGLE\`.
   - Application updates and reinstalls never overwrite user configuration or personal assistant history.
4. **Zero AI Model Bundling**:
   - AI models (e.g. Whisper base/small weights) are not baked into the installer package. This keeps the binary distribution compact (<80 MB) and allows models to download on demand or use system-installed engines (Windows SAPI5 for TTS, local Vosk/Whisper cache, or cloud AI providers).

---

## 2. Prerequisites & Build Environment

To build the executable from source, ensure the following prerequisites are installed on Windows 11 (or Windows 10 x64):

- **Python**: Version 3.13.1 (64-bit)
- **Virtual Environment**: `.venv` activated
- **Dependencies**: All core and dev dependencies installed:
  ```powershell
  python -m venv .venv
  .\.venv\Scripts\Activate.ps1
  pip install -r requirements.txt
  pip install -r requirements-dev.txt
  ```
- **PyInstaller**: Version `>=6.0.0` (installed via dev requirements)

---

## 3. PyInstaller Specification (`eagle.spec`)

The packaging rules are codified in [`eagle.spec`](../eagle.spec).

### Specification Structure:
- **Datas**:
  - `README.md` -> Application root.
  - `.env.example` -> Application root template.
- **Hidden Imports**:
  - `PySide6.QtCore`, `PySide6.QtGui`, `PySide6.QtWidgets` (Qt GUI toolkit)
  - `sounddevice`, `_cffi_backend`, `cffi` (Audio hardware capture)
  - `pyttsx3`, `pyttsx3.drivers.sapi5`, `win32com`, `comtypes` (Windows SAPI5 TTS)
  - `pydantic`, `pydantic_core` (Data validation and configuration schemas)
  - `psutil` (System telemetry and hardware monitoring)
  - `eagle.*` (All core submodules, tools, and services)
- **Excludes**:
  - `pytest`, `pytest_mock`, `_pytest`, `mypy`, `ruff`, `tkinter` (Development utilities stripped from release distribution).

---

## 4. Automated Build Command

EAGLE includes an automated build orchestration script that enforces quality gates prior to packaging:

```powershell
.\.venv\Scripts\python.exe scripts/build_windows.py
```

### Script Execution Pipeline:
1. **Unit Test Verification**: Executes `pytest tests/unit` to ensure zero regression.
2. **Code Quality Linting**: Runs `ruff check eagle tests scripts`.
3. **Static Type Checking**: Runs `mypy eagle tests scripts`.
4. **Artifact Cleanup**: Safely removes old `build/` and `dist/` folders.
5. **PyInstaller Compilation**: Invokes `PyInstaller --clean --noconfirm eagle.spec`.
6. **Integrity Checksums**: Verifies that `dist/EAGLE/EAGLE.exe` exists, calculates its SHA-256 hash, and writes `dist/SHA256SUMS.txt`.

---

## 5. Manual Build Command

If building manually without the orchestration script:

```powershell
# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Clean previous builds
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

# Compile using spec file
pyinstaller --clean --noconfirm eagle.spec

# Calculate SHA-256 hash
Get-FileHash -Algorithm SHA256 dist/EAGLE/EAGLE.exe | Out-File -Encoding utf8 dist/SHA256SUMS.txt
```

---

## 6. Output Artifacts

Upon successful build completion:

| Path | Description | Typical Size |
|---|---|---|
| `dist/EAGLE/` | Complete standalone application directory | ~150–220 MB |
| `dist/EAGLE/EAGLE.exe` | Main application launch executable | ~10–15 MB |
| `dist/EAGLE/_internal/` | Bundled Python runtime, CFFI, PySide6 DLLs, and libraries | ~140–200 MB |
| `dist/SHA256SUMS.txt` | Cryptographic SHA-256 hash file for release integrity | <1 KB |

---

## 7. Verification & Smoke Testing

To test the built binary on the local machine:

1. Launch directly:
   ```powershell
   .\dist\EAGLE\EAGLE.exe
   ```
2. Verify startup behavior:
   - PySide6 window appears with the Eagle-themed dark UI.
   - Microphone indicator displays `IDLE` or `LISTENING`.
   - Voice visualizer responds to audio input.
   - Settings dialog opens without errors.
   - User configuration is created in `%APPDATA%\EAGLE\config.json`.
   - Log entries are written to `%APPDATA%\EAGLE\logs\eagle.log`.

---

## 8. Troubleshooting Build Issues

- **Missing DLLs / CFFI Errors**:
  - Ensure Windows Universal C Runtime is installed.
  - Reinstall sounddevice with `pip install --force-reinstall sounddevice`.
- **PySide6 Plugin Not Found (`qt.qpa.plugin: Could not find the Qt platform plugin "windows"`)**:
  - The `eagle.spec` includes `PySide6.QtCore`, `PySide6.QtGui`, and `PySide6.QtWidgets`, which causes PyInstaller's built-in Qt hook to automatically bundle `platforms/qwindows.dll` into `_internal/PySide6/plugins/platforms/`.
- **Permission Errors on Clean**:
  - If `build/` or `dist/` cannot be deleted, ensure no previous instance of `EAGLE.exe` is still running in the background via Task Manager (`Stop-Process -Name EAGLE -Force`).
