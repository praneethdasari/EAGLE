"""Continuous listening state machine, audio lifecycle coordinator, and wake-word manager."""

import queue
import threading
import time
from enum import StrEnum
from typing import Any

from eagle.core.config import EagleConfig
from eagle.core.events import (
    AudioCaptureStartedEvent,
    AudioCaptureStoppedEvent,
    EventBus,
    ListeningStateChangedEvent,
    SpeechOutputFinishedEvent,
    SpeechOutputRequestedEvent,
    SpeechTranscribedEvent,
    StateChangedEvent,
    WakeWordDetectedEvent,
)
from eagle.core.exceptions import InvalidStateTransitionError
from eagle.core.logging import get_logger
from eagle.services.audio_capture import (
    AudioCaptureManager,
    calculate_rms_amplitude,
    pcm_to_wav_bytes,
)
from eagle.services.command_router import CommandIntent, CommandRouter
from eagle.services.stt import BaseSTTEngine
from eagle.services.tts import BaseTTSEngine
from eagle.services.wake_word import BaseWakeWordEngine, get_wake_word_engine

logger = get_logger("services.listener")


class AssistantState(StrEnum):
    """Explicit states of the EAGLE continuous listening assistant."""

    IDLE = "IDLE"
    LISTENING_FOR_WAKE_WORD = "LISTENING_FOR_WAKE_WORD"
    CAPTURING_COMMAND = "CAPTURING_COMMAND"
    PROCESSING_COMMAND = "PROCESSING_COMMAND"
    SPEAKING = "SPEAKING"
    STOPPING = "STOPPING"
    ERROR = "ERROR"


VALID_TRANSITIONS: dict[AssistantState, set[AssistantState]] = {
    AssistantState.IDLE: {
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.CAPTURING_COMMAND,
        AssistantState.STOPPING,
        AssistantState.ERROR,
    },
    AssistantState.LISTENING_FOR_WAKE_WORD: {
        AssistantState.CAPTURING_COMMAND,
        AssistantState.IDLE,
        AssistantState.STOPPING,
        AssistantState.ERROR,
    },
    AssistantState.CAPTURING_COMMAND: {
        AssistantState.PROCESSING_COMMAND,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.IDLE,
        AssistantState.STOPPING,
        AssistantState.ERROR,
    },
    AssistantState.PROCESSING_COMMAND: {
        AssistantState.SPEAKING,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.IDLE,
        AssistantState.STOPPING,
        AssistantState.ERROR,
    },
    AssistantState.SPEAKING: {
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.IDLE,
        AssistantState.CAPTURING_COMMAND,  # User interruption / barge-in
        AssistantState.STOPPING,
        AssistantState.ERROR,
    },
    AssistantState.STOPPING: {
        AssistantState.IDLE,
    },
    AssistantState.ERROR: {
        AssistantState.IDLE,
        AssistantState.LISTENING_FOR_WAKE_WORD,
        AssistantState.STOPPING,
    },
}


class ContinuousListener:
    """Thread-safe continuous listening coordinator and state machine for EAGLE."""

    def __init__(
        self,
        config: EagleConfig | None = None,
        event_bus: EventBus | None = None,
        audio_capture: AudioCaptureManager | None = None,
        wake_word_engine: BaseWakeWordEngine | None = None,
        stt_engine: BaseSTTEngine | None = None,
        tts_engine: BaseTTSEngine | None = None,
        command_router: CommandRouter | None = None,
        ai_orchestrator: Any | None = None,
    ) -> None:
        self.config = config or EagleConfig()
        self.event_bus = event_bus or EventBus()
        self.audio_capture = audio_capture or AudioCaptureManager(
            config=self.config.audio, event_bus=self.event_bus
        )
        self.stt_engine = stt_engine
        self.wake_word_engine = wake_word_engine or get_wake_word_engine(
            self.config, stt_engine=self.stt_engine
        )
        self.tts_engine = tts_engine
        self.command_router = command_router
        self.ai_orchestrator = ai_orchestrator

        self._state = AssistantState.IDLE
        self._state_lock = threading.RLock()
        self._command_audio = bytearray()
        self._command_start_time: float = 0.0
        self._last_voice_time: float = 0.0
        self._frames_captured: int = 0
        self._is_active = False

        # Asynchronous processing queue for audio commands
        self._process_queue: queue.Queue[bytes] = queue.Queue()
        self._worker_thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        # Wire event subscriptions
        self._wire_event_bus()

    @property
    def state(self) -> AssistantState:
        with self._state_lock:
            return self._state

    def is_active(self) -> bool:
        return self._is_active

    def transition_to(self, new_state: AssistantState, reason: str = "") -> None:
        """Enforce thread-safe state machine transitions and broadcast change events."""
        with self._state_lock:
            old_state = self._state
            if old_state == new_state:
                return

            allowed = VALID_TRANSITIONS.get(old_state, set())
            if new_state not in allowed:
                err_msg = (
                    f"Illegal state transition from {old_state.value} to {new_state.value}. "
                    f"Allowed: {[s.value for s in allowed]}"
                )
                logger.error(err_msg)
                raise InvalidStateTransitionError(err_msg)

            self._state = new_state
            logger.info(
                "Assistant state transition: %s -> %s (Reason: '%s')",
                old_state.value,
                new_state.value,
                reason or "normal",
            )

        # Broadcast events outside lock to prevent deadlocks
        self.event_bus.publish(
            StateChangedEvent(old_state=old_state.value, new_state=new_state.value)
        )
        self.event_bus.publish(
            ListeningStateChangedEvent(
                old_state=old_state.value,
                new_state=new_state.value,
                reason=reason,
            )
        )

    def start(self) -> None:
        """Start continuous listening coordinator and background worker."""
        with self._state_lock:
            if self._is_active:
                logger.debug("ContinuousListener is already active.")
                return

            self._is_active = True
            self._stop_event.clear()
            self._command_audio.clear()

            # Start background command processing worker
            self._worker_thread = threading.Thread(
                target=self._command_worker_loop,
                daemon=True,
                name="EAGLE-CommandWorker",
            )
            self._worker_thread.start()

            # Determine initial listening state
            if self.config.voice.wake_word_enabled and self.wake_word_engine.is_available():
                self.transition_to(
                    AssistantState.LISTENING_FOR_WAKE_WORD,
                    reason="continuous listening started with wake word",
                )
                self.audio_capture.start_recording(chunk_callback=self._on_audio_chunk)
                self.event_bus.publish(AudioCaptureStartedEvent(mode="wake_word"))
            else:
                self.transition_to(
                    AssistantState.IDLE,
                    reason="started without wake-word detection (manual/CLI mode)",
                )

    def stop(self) -> None:
        """Cleanly stop continuous listening, release microphone, and cancel pending tasks."""
        with self._state_lock:
            if not self._is_active:
                return
            self._is_active = False
            self.transition_to(AssistantState.STOPPING, reason="stop requested")

        self._stop_event.set()

        # Stop audio capture hardware stream
        try:
            self.audio_capture.stop_recording()
        except Exception as exc:
            logger.warning("Error stopping audio capture stream: %s", exc)

        # Interrupt active speech playback if speaking
        self.interrupt()

        # Reset wake word engine buffers
        if self.wake_word_engine:
            self.wake_word_engine.reset()

        # Emit stopped event
        self.event_bus.publish(AudioCaptureStoppedEvent(frames_captured=self._frames_captured))

        with self._state_lock:
            self._command_audio.clear()
            self.transition_to(AssistantState.IDLE, reason="shutdown complete")

    def interrupt(self) -> None:
        """Safely interrupt active speech playback."""
        if self.tts_engine:
            try:
                self.tts_engine.stop()
            except Exception as exc:
                logger.debug("Error interrupting TTS engine: %s", exc)

    def start_manual_recording(self) -> None:
        """Trigger manual command recording (push-to-talk / CLI shortcut)."""
        with self._state_lock:
            if self._state == AssistantState.SPEAKING:
                self.interrupt()

            if self._state in (AssistantState.IDLE, AssistantState.LISTENING_FOR_WAKE_WORD):
                self._command_audio.clear()
                self._command_start_time = time.time()
                self._last_voice_time = time.time()
                self.transition_to(
                    AssistantState.CAPTURING_COMMAND, reason="manual capture initiated"
                )
                self.audio_capture.start_recording(chunk_callback=self._on_audio_chunk)
                self.event_bus.publish(AudioCaptureStartedEvent(mode="command"))

    def stop_manual_recording(self) -> None:
        """Finish manual command recording and dispatch for transcription & execution."""
        with self._state_lock:
            if self._state != AssistantState.CAPTURING_COMMAND:
                return
            pcm_bytes = bytes(self._command_audio)
            self._command_audio.clear()
            self.transition_to(AssistantState.PROCESSING_COMMAND, reason="manual capture finished")

        if pcm_bytes:
            self._process_queue.put(pcm_bytes)
        else:
            self._resume_appropriate_state()

    def _on_audio_chunk(self, pcm_chunk: bytes) -> None:
        """Handle real-time incoming 16-bit PCM chunk from microphone."""
        if not self._is_active:
            return

        with self._state_lock:
            current_state = self._state

        # 1. State: LISTENING_FOR_WAKE_WORD
        if current_state == AssistantState.LISTENING_FOR_WAKE_WORD:
            detected = self.wake_word_engine.process_audio(pcm_chunk)
            if detected:
                logger.info("Wake word detected! Transitioning to CAPTURING_COMMAND.")
                self.event_bus.publish(
                    WakeWordDetectedEvent(wake_phrase=self.wake_word_engine.wake_phrase)
                )
                with self._state_lock:
                    self._command_audio.clear()
                    self._command_start_time = time.time()
                    self._last_voice_time = time.time()
                    self.transition_to(
                        AssistantState.CAPTURING_COMMAND, reason="wake word triggered"
                    )
                self.event_bus.publish(AudioCaptureStartedEvent(mode="command"))
            return

        # 2. State: CAPTURING_COMMAND
        if current_state == AssistantState.CAPTURING_COMMAND:
            now = time.time()
            amp = calculate_rms_amplitude(pcm_chunk)

            # Update voice activity timestamp if speech detected
            vad_threshold = self.config.audio.vad_threshold
            if amp >= (vad_threshold * 0.05):
                self._last_voice_time = now

            with self._state_lock:
                self._command_audio.extend(pcm_chunk)
                self._frames_captured += 1
                command_len = len(self._command_audio)
                duration = command_len / (self.config.audio.sample_rate * 2)

                # Silence detection: trailing silence exceeded and min command duration recorded
                silence_timeout = self.config.voice.silence_timeout_seconds
                silence_elapsed = now - self._last_voice_time

                should_finish = False
                if duration >= 0.5 and silence_elapsed >= silence_timeout:
                    logger.debug(
                        "Command capture finished: silence elapsed (%.2fs)", silence_elapsed
                    )
                    should_finish = True
                elif duration >= self.config.voice.command_timeout_seconds:
                    logger.debug("Command capture finished: max duration reached (%.2fs)", duration)
                    should_finish = True

                if should_finish:
                    pcm_to_process = bytes(self._command_audio)
                    self._command_audio.clear()
                    self.transition_to(
                        AssistantState.PROCESSING_COMMAND, reason="command capture complete"
                    )

            if should_finish:
                self._process_queue.put(pcm_to_process)
            return

        # 3. State: SPEAKING (Self-speech suppression)
        if current_state == AssistantState.SPEAKING:
            # During assistant speech playback, ignore microphone inputs to prevent self-triggering
            return

    def _command_worker_loop(self) -> None:
        """Background worker thread processing captured audio commands."""
        while not self._stop_event.is_set():
            try:
                pcm_bytes = self._process_queue.get(timeout=0.2)
            except queue.Empty:
                continue

            self._process_audio_command(pcm_bytes)
            self._process_queue.task_done()

    def _process_audio_command(self, pcm_bytes: bytes) -> None:
        """Transcribe and route captured voice command."""
        if not pcm_bytes or not self.stt_engine:
            self._resume_appropriate_state()
            return

        wav_bytes = pcm_to_wav_bytes(
            pcm_bytes,
            sample_rate=self.config.audio.sample_rate,
            channels=self.config.audio.channels,
        )

        try:
            result = self.stt_engine.transcribe(wav_bytes)
            text = result.text.strip()
            if not text:
                logger.debug("Captured speech was empty or unrecognized.")
                self._resume_appropriate_state()
                return

            logger.info(
                "Transcribed voice command: '%s' (Confidence: %.2f)", text, result.confidence
            )
            self.event_bus.publish(
                SpeechTranscribedEvent(
                    text=text,
                    is_final=True,
                    confidence=result.confidence,
                )
            )

            # Route command through CommandRouter & AIOrchestrator
            if self.command_router:
                route = self.command_router.route(text)
                logger.debug(
                    "Routed voice intent: %s (Action: %s)", route.intent.value, route.action_name
                )

                # Conversational or unrouted queries forwarded to AIOrchestrator
                if (
                    self.ai_orchestrator
                    and self.ai_orchestrator.is_available()
                    and (route.intent == CommandIntent.CONVERSATION or not route.is_actionable)
                ):
                    self.ai_orchestrator.process_query(text)
                else:
                    self.command_router.dispatch(route)

        except Exception as exc:
            logger.error("Error processing voice command: %s", exc, exc_info=True)
            self.transition_to(AssistantState.ERROR, reason=f"processing error: {exc}")

        # Check if we should return to listening (if no speech was requested)
        with self._state_lock:
            if self._state == AssistantState.PROCESSING_COMMAND:
                self._resume_appropriate_state()

    def _resume_appropriate_state(self) -> None:
        """Return to LISTENING_FOR_WAKE_WORD or IDLE according to configuration."""
        with self._state_lock:
            if not self._is_active:
                return

            if (
                self.config.voice.continuous_listening
                and self.config.voice.wake_word_enabled
                and self.wake_word_engine.is_available()
            ):
                self.transition_to(
                    AssistantState.LISTENING_FOR_WAKE_WORD,
                    reason="continuous listening resumed",
                )
            else:
                self.transition_to(AssistantState.IDLE, reason="listening cycle complete")

    def _wire_event_bus(self) -> None:
        """Subscribe to speech and system events for lifecycle coordination."""

        def on_speech_requested(event: SpeechOutputRequestedEvent) -> None:
            with self._state_lock:
                if self._is_active and self._state != AssistantState.SPEAKING:
                    self.transition_to(AssistantState.SPEAKING, reason="assistant speaking")

        def on_speech_finished(event: SpeechOutputFinishedEvent) -> None:
            with self._state_lock:
                if self._state == AssistantState.SPEAKING:
                    self._resume_appropriate_state()

        self.event_bus.subscribe(SpeechOutputRequestedEvent, on_speech_requested)
        self.event_bus.subscribe(SpeechOutputFinishedEvent, on_speech_finished)

    def feed_simulated_audio(self, pcm_chunk: bytes) -> None:
        """Test helper to simulate microphone audio input deterministically."""
        self._on_audio_chunk(pcm_chunk)
