"""EAGLE Services subsystem package."""

from eagle.services.ai_provider import (
    AIOrchestrator,
    AIResponse,
    BaseAIProvider,
    ChatMessage,
    ConversationManager,
    MockAIProvider,
    OpenAICompatibleProvider,
    ToolCall,
    get_ai_provider,
)
from eagle.services.audio_capture import (
    AudioCaptureManager,
    AudioDeviceInfo,
    calculate_rms_amplitude,
    list_audio_input_devices,
    pcm_to_wav_bytes,
)
from eagle.services.command_router import (
    CommandIntent,
    CommandRoute,
    CommandRouter,
    normalize_command_text,
)
from eagle.services.stt import (
    BaseSTTEngine,
    FasterWhisperSTT,
    MockSTTEngine,
    TranscriptionResult,
    create_stt_engine,
)
from eagle.services.tts import (
    BaseTTSEngine,
    MockTTSEngine,
    Pyttsx3TTSEngine,
    create_tts_engine,
)

__all__ = [
    # AI Reasoning & Tool Calling
    "BaseAIProvider",
    "MockAIProvider",
    "OpenAICompatibleProvider",
    "ChatMessage",
    "ToolCall",
    "AIResponse",
    "ConversationManager",
    "AIOrchestrator",
    "get_ai_provider",
    # Audio capture
    "AudioCaptureManager",
    "AudioDeviceInfo",
    "list_audio_input_devices",
    "calculate_rms_amplitude",
    "pcm_to_wav_bytes",
    # STT
    "BaseSTTEngine",
    "MockSTTEngine",
    "FasterWhisperSTT",
    "TranscriptionResult",
    "create_stt_engine",
    # TTS
    "BaseTTSEngine",
    "MockTTSEngine",
    "Pyttsx3TTSEngine",
    "create_tts_engine",
    # Routing
    "CommandRouter",
    "CommandRoute",
    "CommandIntent",
    "normalize_command_text",
]
