"""Main desktop window for EAGLE voice assistant uniting UI widgets, audio visualizer, and event routing."""

import threading

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from eagle import __version__
from eagle.core.config import EagleConfig
from eagle.core.events import EventBus
from eagle.core.logging import get_logger
from eagle.services.ai_provider import AIOrchestrator
from eagle.services.command_router import CommandIntent, CommandRouter
from eagle.services.continuous_listener import AssistantState, ContinuousListener
from eagle.ui.bridge import EventBusQtBridge
from eagle.ui.conversation import ConversationFeedWidget
from eagle.ui.input_bar import InputBarWidget
from eagle.ui.settings_dialog import SettingsDialog
from eagle.ui.status_panel import StatusPanelWidget
from eagle.ui.theme import PALETTE, get_eagle_stylesheet
from eagle.ui.visualizer import AudioVisualizerWidget, MicrophoneIndicatorWidget

logger = get_logger("ui.main_window")


class MainWindow(QMainWindow):
    """Primary PySide6 desktop interface for the EAGLE voice assistant."""

    def __init__(
        self,
        config: EagleConfig,
        event_bus: EventBus,
        command_router: CommandRouter,
        ai_orchestrator: AIOrchestrator,
        continuous_listener: ContinuousListener,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.config = config
        self.event_bus = event_bus
        self.command_router = command_router
        self.ai_orchestrator = ai_orchestrator
        self.continuous_listener = continuous_listener

        # Setup window properties
        self.setWindowTitle(self.config.ui.window_title)
        self.resize(self.config.ui.window_width, self.config.ui.window_height)
        self.setMinimumSize(800, 560)
        self.setStyleSheet(get_eagle_stylesheet())

        # Setup thread-safe EventBus bridge
        self.bridge = EventBusQtBridge(self.event_bus, parent=self)

        # Build UI layout
        self._init_ui()

        # Connect bridge signals to UI slots
        self._wire_bridge_signals()

        # Keyboard shortcuts
        self._init_shortcuts()

        # Greeting in conversation feed
        self._show_initial_greeting()

    def _init_ui(self) -> None:
        central_widget = QWidget(self)
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # 1. Header Bar
        header = self._create_header_bar()
        main_layout.addWidget(header)

        # 2. Main Content Splitter (Chat Feed + Status Sidebar)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setStyleSheet("QSplitter::handle { background-color: #1E2638; width: 1px; }")

        # Conversation History Feed (Main Area)
        self.feed_widget = ConversationFeedWidget(self)
        splitter.addWidget(self.feed_widget)

        # Status Sidebar (Collapsible Panel)
        self.status_panel = StatusPanelWidget(config=self.config, parent=self)
        splitter.addWidget(self.status_panel)

        # Splitter sizing ratio: 75% chat feed, 25% status panel
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 1)
        main_layout.addWidget(splitter, stretch=1)

        # 3. Dynamic Audio Visualizer
        if self.config.ui.show_visualizer:
            visualizer_container = QFrame()
            visualizer_container.setStyleSheet(
                f"background-color: {PALETTE.BG_BASE}; padding: 0 16px;"
            )
            vis_layout = QHBoxLayout(visualizer_container)
            vis_layout.setContentsMargins(16, 4, 16, 4)
            self.visualizer_widget = AudioVisualizerWidget(bar_count=32, parent=self)
            vis_layout.addWidget(self.visualizer_widget)
            main_layout.addWidget(visualizer_container)
        else:
            self.visualizer_widget = None  # type: ignore[assignment]

        # 4. Bottom Input Bar
        self.input_bar = InputBarWidget(self)
        self.input_bar.text_submitted.connect(self._on_user_input)
        self.input_bar.mic_toggled.connect(self._toggle_listening)
        self.input_bar.clear_requested.connect(self.feed_widget.clear_feed)
        main_layout.addWidget(self.input_bar)

    def _create_header_bar(self) -> QFrame:
        header = QFrame(self)
        header.setObjectName("HeaderBar")
        header.setFixedHeight(54)

        layout = QHBoxLayout(header)
        layout.setContentsMargins(18, 8, 18, 8)
        layout.setSpacing(12)

        # Brand Title
        brand_label = QLabel("🦅 EAGLE")
        brand_label.setStyleSheet(
            f"font-weight: 800; font-size: 15px; letter-spacing: 1px; color: {PALETTE.ACCENT_CYAN};"
        )
        layout.addWidget(brand_label)

        sub_label = QLabel("Enhanced Autonomous Local Executive")
        sub_label.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        layout.addWidget(sub_label)

        layout.addStretch()

        # Microphone State Indicator Pill
        self.mic_indicator = MicrophoneIndicatorWidget(header)
        self.mic_indicator.clicked.connect(self._toggle_listening)
        layout.addWidget(self.mic_indicator)

        # Settings Button
        self.settings_btn = QPushButton("⚙️ Settings")
        self.settings_btn.setFixedHeight(34)
        self.settings_btn.clicked.connect(self._open_settings_dialog)
        layout.addWidget(self.settings_btn)

        return header

    def _init_shortcuts(self) -> None:
        # Ctrl+M: Toggle Voice Listening
        mic_action = QAction(self)
        mic_action.setShortcut(QKeySequence("Ctrl+M"))
        mic_action.triggered.connect(self._toggle_listening)
        self.addAction(mic_action)

        # Ctrl+L: Clear conversation history
        clear_action = QAction(self)
        clear_action.setShortcut(QKeySequence("Ctrl+L"))
        clear_action.triggered.connect(self.feed_widget.clear_feed)
        self.addAction(clear_action)

        # Ctrl+,: Open Settings
        settings_action = QAction(self)
        settings_action.setShortcut(QKeySequence("Ctrl+,"))
        settings_action.triggered.connect(self._open_settings_dialog)
        self.addAction(settings_action)

    def _show_initial_greeting(self) -> None:
        welcome_text = (
            f"Welcome to EAGLE v{__version__}!\n"
            "I'm your autonomous desktop voice assistant. You can speak to me by saying 'Hey EAGLE' "
            "or type any command below.\n"
            "• Launch apps: 'open notepad', 'launch calculator'\n"
            "• Search the web: 'search for quantum computing'\n"
            "• System metrics: 'system info'\n"
            "• File management: 'list files'"
        )
        self.feed_widget.add_assistant_message(welcome_text)

    def _wire_bridge_signals(self) -> None:
        # Audio level -> Visualizer
        if self.visualizer_widget:
            self.bridge.sig_audio_level.connect(self.visualizer_widget.set_amplitude)

        # Assistant state changed
        self.bridge.sig_state_changed.connect(self._on_state_changed)

        # Speech transcribed (voice input recognized)
        self.bridge.sig_speech_transcribed.connect(self._on_speech_transcribed)

        # Speech output requested (assistant verbal response)
        self.bridge.sig_speech_output_requested.connect(self._on_speech_output)

        # Tool execution cards
        self.bridge.sig_tool_completed.connect(self._on_tool_completed)

    def _on_state_changed(self, old_state: str, new_state: str, reason: str) -> None:
        self.mic_indicator.set_state(new_state, reason)
        self.status_panel.update_state(new_state, reason)
        is_listening = new_state == AssistantState.LISTENING_FOR_WAKE_WORD.value
        self.input_bar.set_listening_active(is_listening)

    def _on_speech_transcribed(self, text: str, confidence: float) -> None:
        if text.strip():
            self.feed_widget.add_user_message(text)

    def _on_speech_output(self, text: str) -> None:
        if text.strip():
            self.feed_widget.add_assistant_message(text)

    def _on_tool_completed(
        self, tool_name: str, success: bool, result: str, duration: float
    ) -> None:
        self.feed_widget.add_tool_card(
            tool_name=tool_name,
            result=result,
            success=success,
            duration=duration,
        )

    def _on_user_input(self, text: str) -> None:
        """Handle user text submitted from the bottom input bar."""
        self.feed_widget.add_user_message(text)

        # Route input in a background thread to prevent UI freezing
        def process_in_background() -> None:
            route = self.command_router.route(text)
            logger.info("Routed text input: %s (Action: %s)", route.intent.value, route.action_name)

            if route.intent == CommandIntent.SYSTEM_CONTROL and route.action_name in (
                "exit",
                "quit",
                "goodbye",
            ):
                self.command_router.dispatch(route)
                return

            if self.ai_orchestrator.is_available() and (
                route.intent == CommandIntent.CONVERSATION or not route.is_actionable
            ):
                self.ai_orchestrator.process_query(text)
            else:
                self.command_router.dispatch(route)

        thread = threading.Thread(
            target=process_in_background,
            daemon=True,
            name="EAGLE-UICommandProcessor",
        )
        thread.start()

    def _toggle_listening(self) -> None:
        """Toggle continuous listening state."""
        if self.continuous_listener.is_active():
            self.continuous_listener.stop()
        else:
            self.continuous_listener.start()

    def _open_settings_dialog(self) -> None:
        dialog = SettingsDialog(config=self.config, parent=self)
        dialog.settings_saved.connect(self._on_settings_saved)
        dialog.exec()

    def _on_settings_saved(self, updated_config: EagleConfig) -> None:
        self.config = updated_config
        self.status_panel.config = updated_config
        self.status_panel.refresh_telemetry()
        self.feed_widget.add_assistant_message("⚙️ Settings updated and saved successfully.")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Cleanly stop background services and detach EventBus bridge upon window close."""
        logger.info("Closing EAGLE MainWindow...")
        if self.continuous_listener:
            self.continuous_listener.stop()
        if self.bridge:
            self.bridge.detach()
        super().closeEvent(event)
