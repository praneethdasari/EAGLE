"""EAGLE Desktop User Interface package powered by PySide6."""

from eagle.ui.bridge import EventBusQtBridge
from eagle.ui.conversation import ConversationFeedWidget, MessageBubble, ToolExecutionCard
from eagle.ui.input_bar import InputBarWidget
from eagle.ui.main_window import MainWindow
from eagle.ui.settings_dialog import SettingsDialog
from eagle.ui.status_panel import StatusPanelWidget
from eagle.ui.theme import PALETTE, get_eagle_stylesheet
from eagle.ui.visualizer import AudioVisualizerWidget, MicrophoneIndicatorWidget

__all__ = [
    "MainWindow",
    "AudioVisualizerWidget",
    "MicrophoneIndicatorWidget",
    "ConversationFeedWidget",
    "MessageBubble",
    "ToolExecutionCard",
    "StatusPanelWidget",
    "InputBarWidget",
    "SettingsDialog",
    "EventBusQtBridge",
    "PALETTE",
    "get_eagle_stylesheet",
]
