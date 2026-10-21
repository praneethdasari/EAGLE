"""Unit tests for eagle.services.audio_capture."""

import io
import struct
import wave

from pytest_mock import MockerFixture

from eagle.core.config import AudioConfig
from eagle.core.events import AudioLevelEvent, EventBus
from eagle.services.audio_capture import (
    AudioCaptureManager,
    calculate_rms_amplitude,
    list_audio_input_devices,
    pcm_to_wav_bytes,
)


def test_calculate_rms_amplitude() -> None:
    """Verify RMS calculation on empty, silent, and active audio chunks."""
    # Empty audio
    assert calculate_rms_amplitude(b"") == 0.0

    # Silent PCM (100 samples of 0)
    silent_pcm = struct.pack("100h", *([0] * 100))
    assert calculate_rms_amplitude(silent_pcm) == 0.0

    # Active PCM (100 samples of amplitude 16384 -> roughly 0.5 normalized)
    active_pcm = struct.pack("100h", *([16384] * 100))
    amp = calculate_rms_amplitude(active_pcm)
    assert 0.49 <= amp <= 0.51


def test_pcm_to_wav_bytes() -> None:
    """Verify raw PCM bytes are converted into a readable WAV container."""
    raw_pcm = struct.pack("500h", *([1000] * 500))
    wav_bytes = pcm_to_wav_bytes(raw_pcm, sample_rate=16000, channels=1)

    assert wav_bytes.startswith(b"RIFF")
    assert b"WAVE" in wav_bytes

    # Verify it can be parsed by wave standard library
    with wave.open(io.BytesIO(wav_bytes), "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 16000
        assert wf.getnframes() == 500


def test_list_audio_input_devices(mocker: MockerFixture) -> None:
    """Verify input device query filters out output-only devices."""
    mock_devices = [
        {
            "name": "Speakers (Realtek)",
            "max_input_channels": 0,
            "max_output_channels": 2,
            "default_samplerate": 48000.0,
        },
        {
            "name": "Microphone (Realtek)",
            "max_input_channels": 2,
            "max_output_channels": 0,
            "default_samplerate": 44100.0,
        },
        {
            "name": "USB Headset Mic",
            "max_input_channels": 1,
            "max_output_channels": 0,
            "default_samplerate": 16000.0,
        },
    ]
    mock_sd = mocker.MagicMock()
    mock_sd.query_devices.return_value = mock_devices
    mocker.patch.dict("sys.modules", {"sounddevice": mock_sd})

    devices = list_audio_input_devices()
    assert len(devices) == 2
    assert devices[0].name == "Microphone (Realtek)"
    assert devices[0].index == 1
    assert devices[1].name == "USB Headset Mic"
    assert devices[1].index == 2


def test_audio_capture_manager_simulated_pcm() -> None:
    """Verify AudioCaptureManager buffer collection and EventBus level reporting."""
    bus = EventBus()
    received_levels: list[float] = []

    def on_level(evt: AudioLevelEvent) -> None:
        received_levels.append(evt.amplitude)

    bus.subscribe(AudioLevelEvent, on_level)

    manager = AudioCaptureManager(config=AudioConfig(sample_rate=16000), event_bus=bus)
    assert manager.is_recording() is False

    # Simulate recording loop manually
    manager._is_recording = True
    test_pcm = struct.pack("200h", *([8000] * 200))
    manager.feed_simulated_pcm(test_pcm)

    assert len(received_levels) == 1
    assert received_levels[0] > 0.0

    wav_output = manager.stop_recording()
    assert manager.is_recording() is False
    assert len(wav_output) > 44  # WAV header + payload
