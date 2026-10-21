# EAGLE Setup & Installation Guide

This guide walks through configuring the development and runtime environment for **EAGLE** on Windows 11.

---

## 1. Prerequisites

- **Operating System**: Windows 10/11 (64-bit AMD64)
- **Python**: Version 3.13 (recommended for native prebuilt wheels) or 3.11/3.12
- **Git**: Git for Windows installed and accessible via command line
- **Hardware**: Working microphone and speaker / headphones

---

## 2. Step-by-Step Installation

### Step 2.1: Clone the Repository
```powershell
git clone https://github.com/praneethdasari/EAGLE.git
cd EAGLE
```

### Step 2.2: Create Virtual Environment
Use Python 3.13 to create an isolated environment:
```powershell
py -3.13 -m venv .venv
```

If PowerShell blocks script execution, run:
```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

Activate the environment:
```powershell
.\.venv\Scripts\Activate.ps1
```

### Step 2.3: Install Dependencies
Install production and development dependencies:
```powershell
pip install --upgrade pip
pip install -r requirements-dev.txt
```

### Step 2.4: Environment Configuration
Copy the sample environment file:
```powershell
Copy-Item .env.example .env
```
Edit `.env` if you wish to configure cloud AI providers (OpenAI, Gemini, Anthropic, or Groq). All cloud providers are optional; offline/local modes can also be used.

---

## 3. Verifying the Installation

### Run Unit Tests
```powershell
pytest
```
Expected output: All unit tests pass with zero failures.

---

## 4. Troubleshooting

### 1. PowerShell Script Execution Policy
**Symptom**: `File ... Activate.ps1 cannot be loaded because running scripts is disabled on this system.`  
**Solution**: Run `Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned` in PowerShell.

### 2. Audio Device Initialization
**Symptom**: `NoDefaultInputDeviceError` or `sounddevice.PortAudioError`.  
**Solution**: Verify in Windows Settings > System > Sound that a microphone is connected and set as default input. Ensure microphone access is allowed in Windows Privacy Settings.

### 3. Missing C++ Redistributable
**Symptom**: DLL load failures when importing `PySide6` or `sounddevice`.  
**Solution**: Install the Microsoft Visual C++ 2015-2022 Redistributable (x64) from official Microsoft downloads.
