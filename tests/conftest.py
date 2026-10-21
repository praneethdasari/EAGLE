"""Shared pytest fixtures for the EAGLE test suite."""

import json
from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def sample_config_dict(tmp_path: Path) -> dict[str, Any]:
    """Returns a valid configuration dictionary pointing to safe temp paths."""
    return {
        "version": "0.1.0",
        "app_name": "EAGLE",
        "log_level": "DEBUG",
        "audio": {
            "sample_rate": 16000,
            "channels": 1,
            "device_index": None,
            "vad_threshold": 0.5,
            "stt_model_size": "tiny",
            "tts_rate": 180,
            "tts_volume": 0.9,
            "wake_word_enabled": False,
            "wake_word_phrase": "hey eagle",
        },
        "ai": {
            "provider": "mock",
            "model_name": "mock-model",
            "temperature": 0.5,
            "max_tokens": 512,
            "system_prompt": "You are EAGLE.",
        },
        "security": {
            "allowed_directories": [str(tmp_path / "sandbox")],
            "allowed_applications": {
                "notepad": "notepad.exe",
                "calc": "calc.exe",
            },
            "allowed_domains": ["google.com", "github.com"],
            "confirm_sensitive_actions": True,
        },
        "ui": {
            "theme": "eagle_dark",
            "window_title": "EAGLE — Voice Assistant",
            "window_width": 900,
            "window_height": 650,
            "show_visualizer": True,
            "start_minimized": False,
        },
    }


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_config_dict: dict[str, Any]) -> Path:
    """Creates a temporary config.json file and returns its path."""
    config_file = tmp_path / "config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(sample_config_dict, f)
    return config_file
