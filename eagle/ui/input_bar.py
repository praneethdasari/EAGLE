"""Text input fallback bar with send button, microphone toggle, and input controls."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QWidget,
)

from eagle.ui.theme import PALETTE


class InputBarWidget(QFrame):
    """Bottom docked input bar allowing typed commands, push-to-talk, and listening toggles."""

    text_submitted = Signal(str)
    mic_toggled = Signal()
    clear_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("BottomBar")
        self.setFixedHeight(64)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # Clear conversation history button
        self._clear_btn = QPushButton("🗑️")
        self._clear_btn.setToolTip("Clear conversation history (Ctrl+L)")
        self._clear_btn.setFixedSize(38, 38)
        self._clear_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {PALETTE.BG_CARD};
                border: 1px solid {PALETTE.BORDER_DEFAULT};
                border-radius: 8px;
                font-size: 14px;
            }}
            QPushButton:hover {{
                background-color: {PALETTE.BG_CARD_HOVER};
                border-color: {PALETTE.ACCENT_RED};
            }}
            """
        )
        self._clear_btn.clicked.connect(self.clear_requested.emit)
        layout.addWidget(self._clear_btn)

        # Text input field
        self._input_field = QLineEdit()
        self._input_field.setPlaceholderText(
            "Ask EAGLE anything, or type a command ('open notepad', 'system info', 'search python')..."
        )
        self._input_field.returnPressed.connect(self._on_submit)
        self._input_field.textChanged.connect(self._on_text_changed)
        layout.addWidget(self._input_field)

        # Send button
        self._send_btn = QPushButton("Send ➤")
        self._send_btn.setObjectName("PrimaryButton")
        self._send_btn.setFixedHeight(38)
        self._send_btn.setEnabled(False)
        self._send_btn.clicked.connect(self._on_submit)
        layout.addWidget(self._send_btn)

        # Microphone toggle button
        self._mic_btn = QPushButton("🎙️")
        self._mic_btn.setObjectName("MicButton")
        self._mic_btn.setToolTip("Toggle Voice Listening (Ctrl+M)")
        self._mic_btn.setFixedSize(40, 40)
        self._mic_btn.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {PALETTE.BG_CARD};
                border: 2px solid {PALETTE.BORDER_DEFAULT};
                border-radius: 20px;
                font-size: 16px;
            }}
            QPushButton:hover {{
                border-color: {PALETTE.ACCENT_CYAN};
            }}
            """
        )
        self._mic_btn.clicked.connect(self.mic_toggled.emit)
        layout.addWidget(self._mic_btn)

    def set_listening_active(self, active: bool) -> None:
        """Update microphone button appearance when continuous listening is active."""
        if active:
            self._mic_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {PALETTE.ACCENT_CYAN_DIM};
                    border: 2px solid {PALETTE.ACCENT_CYAN};
                    border-radius: 20px;
                    font-size: 16px;
                }}
                """
            )
            self._mic_btn.setToolTip("Stop Voice Listening (Ctrl+M)")
        else:
            self._mic_btn.setStyleSheet(
                f"""
                QPushButton {{
                    background-color: {PALETTE.BG_CARD};
                    border: 2px solid {PALETTE.BORDER_DEFAULT};
                    border-radius: 20px;
                    font-size: 16px;
                }}
                QPushButton:hover {{
                    border-color: {PALETTE.ACCENT_CYAN};
                }}
                """
            )
            self._mic_btn.setToolTip("Start Voice Listening (Ctrl+M)")

    def focus_input(self) -> None:
        """Set keyboard focus onto the text input field."""
        self._input_field.setFocus()

    def _on_text_changed(self, text: str) -> None:
        self._send_btn.setEnabled(bool(text.strip()))

    def _on_submit(self) -> None:
        text = self._input_field.text().strip()
        if not text:
            return
        self._input_field.clear()
        self.text_submitted.emit(text)
