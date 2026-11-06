# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller specification file for EAGLE v0.1.0 Windows release build."""

import sys
from pathlib import Path

block_cipher = None

# Base directory
ROOT_DIR = Path.cwd()

# Data files to bundle into the executable
datas = [
    (str(ROOT_DIR / "README.md"), "."),
    (str(ROOT_DIR / ".env.example"), "."),
]

# Essential hidden imports for dynamic and C-extension dependencies
hiddenimports = [
    # PySide6 Qt Modules
    "PySide6.QtCore",
    "PySide6.QtGui",
    "PySide6.QtWidgets",
    # Audio capture & CFFI
    "sounddevice",
    "_cffi_backend",
    "cffi",
    # Windows Text-to-Speech (SAPI5)
    "pyttsx3",
    "pyttsx3.drivers",
    "pyttsx3.drivers.sapi5",
    "comtypes",
    "comtypes.client",
    "win32com",
    "win32com.client",
    # Pydantic v2 core
    "pydantic",
    "pydantic.deprecated",
    "pydantic_core",
    # System telemetry
    "psutil",
    # Networking & HTTP
    "requests",
    "urllib3",
    # EAGLE packages
    "eagle",
    "eagle.main",
    "eagle.core",
    "eagle.core.config",
    "eagle.core.events",
    "eagle.core.exceptions",
    "eagle.core.logging",
    "eagle.core.paths",
    "eagle.services",
    "eagle.services.audio_capture",
    "eagle.services.stt",
    "eagle.services.tts",
    "eagle.services.wake_word",
    "eagle.services.continuous_listener",
    "eagle.services.ai_provider",
    "eagle.services.command_router",
    "eagle.services.startup",
    "eagle.tools",
    "eagle.tools.base",
    "eagle.tools.registry",
    "eagle.tools.apps",
    "eagle.tools.web",
    "eagle.tools.files",
    "eagle.tools.system",
    "eagle.ui",
    "eagle.ui.theme",
    "eagle.ui.visualizer",
    "eagle.ui.conversation",
    "eagle.ui.status_panel",
    "eagle.ui.input_bar",
    "eagle.ui.settings_dialog",
    "eagle.ui.bridge",
    "eagle.ui.main_window",
]

# Development/testing modules to exclude from release build to minimize size
excludes = [
    "pytest",
    "pytest_mock",
    "_pytest",
    "mypy",
    "ruff",
    "tkinter",
    "test",
    "tests",
]

a = Analysis(
    ["eagle/main.py"],
    pathex=[str(ROOT_DIR)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(
    a.pure,
    a.zipped_data,
    cipher=block_cipher,
)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="EAGLE",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,  # Windowed GUI application (no trailing console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="EAGLE",
)
