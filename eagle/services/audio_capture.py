"""Audio capture and microphone management subsystem for EAGLE."""

import io
import math
import struct
import threading
import time
import wave
from dataclasses import dataclass
from typing import Any

from eagle.core.config import AudioConfig
from eagle.core.events import AudioLevelEvent, EventBus
from eagle.core.exceptions import MicrophoneNotFoundError, MicrophonePermissionError
from eagle.core.logging import get_logger

logger = get_logger("services.audio_capture")


@dataclass
class AudioDeviceInfo:
    """Metadata describing an audio input device."""

    index: int
    name: str
    max_input_channels: int
    default_sample_rate: float


def list_audio_input_devices() -> list[AudioDeviceInfo]:
    """Enumerate all available physical or virtual audio input devices."""
    try:
        import sounddevice as sd

        devices = sd.query_devices()
        input_devices: list[AudioDeviceInfo] = []
        for idx, dev in enumerate(devices):
            if dev.get("max_input_channels", 0) > 0:
                input_devices.append(
                    AudioDeviceInfo(
                        index=idx,
                        name=dev.get("name", f"Device {idx}"),
                        max_input_channels=dev.get("max_input_channels", 1),
                        default_sample_rate=float(dev.get("default_samplerate", 16000.0)),
                    )
                )
        return input_devices
    except Exception as exc:
        logger.warning("Could not query sounddevice devices: %s", exc)
        return []


def calculate_rms_amplitude(audio_bytes: bytes) -> float:
    """Calculate normalized RMS amplitude (0.0 to 1.0) from 16-bit mono PCM bytes."""
    if not audio_bytes:
        return 0.0

    count = len(audio_bytes) // 2
    if count == 0:
        return 0.0

    try:
        shorts = struct.unpack(f"{count}h", audio_bytes[: count * 2])
        sum_squares = sum(s * s for s in shorts)
        rms = math.sqrt(sum_squares / count)
        # Normalize assuming 16-bit max amplitude is 32767
        return min(1.0, max(0.0, rms / 32768.0))
    except Exception:
        return 0.0


def pcm_to_wav_bytes(pcm_data: bytes, sample_rate: int = 16000, channels: int = 1) -> bytes:
    """Wrap raw 16-bit PCM bytes into standard WAV format container."""
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav_file:
        wav_file.setnchannels(channels)
        wav_file.setsampwidth(2)  # 16-bit PCM = 2 bytes
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm_data)
    return buffer.getvalue()


class AudioCaptureManager:
    """Manages microphone audio stream capture, VAD buffering, and level reporting."""

    def __init__(
        self,
        config: AudioConfig | None = None,
        event_bus: EventBus | None = None,
    ) -> None:
        self.config = config or AudioConfig()
        self.event_bus = event_bus
        self.sample_rate = self.config.sample_rate
        self.channels = self.config.channels
        self.device_index = self.config.device_index
        self.vad_threshold = self.config.vad_threshold

        self._is_recording = False
        self._audio_buffer = bytearray()
        self._lock = threading.Lock()
        self._stream: Any = None

    def start_recording(self) -> None:
        """Begin audio capture from configured microphone."""
        with self._lock:
            if self._is_recording:
                return
            self._audio_buffer.clear()
            self._is_recording = True

        try:
            import sounddevice as sd

            def audio_callback(indata: Any, frames: int, time_info: Any, status: Any) -> None:
                if status:
                    logger.debug("Sounddevice audio status: %s", status)
                if not self._is_recording:
                    return

                # Convert float32 or int16 numpy array to 16-bit PCM bytes
                if indata.dtype == "float32":
                    pcm_chunk = (indata * 32767.0).astype("int16").tobytes()
                else:
                    pcm_chunk = indata.tobytes()

                with self._lock:
                    self._audio_buffer.extend(pcm_chunk)

                # Report audio amplitude to EventBus for UI visualizer
                if self.event_bus:
                    amp = calculate_rms_amplitude(pcm_chunk)
                    self.event_bus.publish(AudioLevelEvent(amplitude=amp))

            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=self.channels,
                device=self.device_index,
                dtype="int16",
                callback=audio_callback,
            )
            self._stream.start()
            logger.info(
                "Microphone stream started on device %s at %d Hz",
                self.device_index,
                self.sample_rate,
            )
        except Exception as exc:
            with self._lock:
                self._is_recording = False
            logger.error("Failed to open microphone stream: %s", exc)
            if "permission" in str(exc).lower():
                raise MicrophonePermissionError(
                    f"Microphone access permission denied: {exc}"
                ) from exc
            raise MicrophoneNotFoundError(f"Microphone input device unavailable: {exc}") from exc

    def stop_recording(self) -> bytes:
        """Stop microphone capture and return recorded audio as WAV bytes."""
        with self._lock:
            self._is_recording = False

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as exc:
                logger.warning("Error stopping audio stream: %s", exc)
            finally:
                self._stream = None

        with self._lock:
            pcm_bytes = bytes(self._audio_buffer)
            self._audio_buffer.clear()

        return pcm_to_wav_bytes(pcm_bytes, self.sample_rate, self.channels)

    def is_recording(self) -> bool:
        """Return True if currently capturing audio."""
        with self._lock:
            return self._is_recording

    def record_seconds(self, duration: float) -> bytes:
        """Helper to record audio for a fixed duration."""
        self.start_recording()
        time.sleep(duration)
        return self.stop_recording()

    def feed_simulated_pcm(self, pcm_chunk: bytes) -> None:
        """Test helper to simulate audio input without physical microphone hardware."""
        with self._lock:
            if self._is_recording:
                self._audio_buffer.extend(pcm_chunk)

        if self.event_bus:
            amp = calculate_rms_amplitude(pcm_chunk)
            self.event_bus.publish(AudioLevelEvent(amplitude=amp))
