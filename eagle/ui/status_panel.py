"""Status panel widget displaying assistant state, system telemetry, and active permissions."""

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from eagle.core.config import EagleConfig
from eagle.services.continuous_listener import AssistantState
from eagle.ui.theme import PALETTE


class StatusPanelWidget(QFrame):
    """Sidebar widget presenting live assistant metrics, system telemetry, and safety state."""

    def __init__(self, config: EagleConfig | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.config = config or EagleConfig()
        self.setObjectName("StatusPanel")
        self.setFixedWidth(260)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Title
        title_label = QLabel("SYSTEM STATUS")
        title_label.setStyleSheet(
            f"font-weight: 800; font-size: 11px; letter-spacing: 1px; color: {PALETTE.ACCENT_CYAN};"
        )
        layout.addWidget(title_label)

        # Assistant State Section
        state_section = self._create_card()
        state_layout = QVBoxLayout(state_section)
        state_layout.setContentsMargins(12, 10, 12, 10)
        state_layout.setSpacing(4)

        state_header = QLabel("ASSISTANT STATE")
        state_header.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {PALETTE.TEXT_MUTED};"
        )
        state_layout.addWidget(state_header)

        self._state_val = QLabel("IDLE")
        self._state_val.setStyleSheet(
            f"font-size: 13px; font-weight: bold; color: {PALETTE.TEXT_PRIMARY};"
        )
        state_layout.addWidget(self._state_val)

        self._task_val = QLabel("Ready for commands")
        self._task_val.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        state_layout.addWidget(self._task_val)
        layout.addWidget(state_section)

        # Telemetry Section (CPU & RAM)
        telemetry_section = self._create_card()
        telemetry_layout = QVBoxLayout(telemetry_section)
        telemetry_layout.setContentsMargins(12, 10, 12, 10)
        telemetry_layout.setSpacing(8)

        telem_header = QLabel("SYSTEM TELEMETRY")
        telem_header.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {PALETTE.TEXT_MUTED};"
        )
        telemetry_layout.addWidget(telem_header)

        # CPU Row
        cpu_row = QHBoxLayout()
        cpu_label = QLabel("CPU Load")
        cpu_label.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        self._cpu_val = QLabel("0%")
        self._cpu_val.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {PALETTE.TEXT_PRIMARY};"
        )
        cpu_row.addWidget(cpu_label)
        cpu_row.addStretch()
        cpu_row.addWidget(self._cpu_val)
        telemetry_layout.addLayout(cpu_row)

        self._cpu_bar = QProgressBar()
        self._cpu_bar.setFixedHeight(4)
        self._cpu_bar.setTextVisible(False)
        self._cpu_bar.setRange(0, 100)
        self._cpu_bar.setValue(0)
        self._cpu_bar.setStyleSheet(
            f"""
            QProgressBar {{ background-color: {PALETTE.BG_BASE}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {PALETTE.ACCENT_CYAN}; border-radius: 2px; }}
            """
        )
        telemetry_layout.addWidget(self._cpu_bar)

        # RAM Row
        ram_row = QHBoxLayout()
        ram_label = QLabel("Memory")
        ram_label.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        self._ram_val = QLabel("0%")
        self._ram_val.setStyleSheet(
            f"font-size: 11px; font-weight: bold; color: {PALETTE.TEXT_PRIMARY};"
        )
        ram_row.addWidget(ram_label)
        ram_row.addStretch()
        ram_row.addWidget(self._ram_val)
        telemetry_layout.addLayout(ram_row)

        self._ram_bar = QProgressBar()
        self._ram_bar.setFixedHeight(4)
        self._ram_bar.setTextVisible(False)
        self._ram_bar.setRange(0, 100)
        self._ram_bar.setValue(0)
        self._ram_bar.setStyleSheet(
            f"""
            QProgressBar {{ background-color: {PALETTE.BG_BASE}; border: none; border-radius: 2px; }}
            QProgressBar::chunk {{ background-color: {PALETTE.ACCENT_GOLD}; border-radius: 2px; }}
            """
        )
        telemetry_layout.addWidget(self._ram_bar)

        layout.addWidget(telemetry_section)

        # Intelligence & Configuration Section
        config_section = self._create_card()
        config_layout = QVBoxLayout(config_section)
        config_layout.setContentsMargins(12, 10, 12, 10)
        config_layout.setSpacing(6)

        config_header = QLabel("INTELLIGENCE & TOOLS")
        config_header.setStyleSheet(
            f"font-size: 10px; font-weight: bold; color: {PALETTE.TEXT_MUTED};"
        )
        config_layout.addWidget(config_header)

        provider_name = self.config.ai.provider.upper()
        model_name = self.config.ai.model_name
        self._provider_label = QLabel(f"AI: {provider_name} ({model_name})")
        self._provider_label.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        config_layout.addWidget(self._provider_label)

        app_count = len(self.config.security.allowed_applications)
        dir_count = len(self.config.security.allowed_directories)
        tools_summary = QLabel(f"Allowed: {app_count} Apps • {dir_count} Dirs")
        tools_summary.setStyleSheet(f"font-size: 11px; color: {PALETTE.TEXT_SECONDARY};")
        config_layout.addWidget(tools_summary)

        confirm_text = (
            "Confirm Sensitive: ON"
            if self.config.security.confirm_sensitive_actions
            else "Confirm: OFF"
        )
        confirm_label = QLabel(confirm_text)
        confirm_label.setStyleSheet(
            f"font-size: 10px; color: {PALETTE.ACCENT_GREEN if self.config.security.confirm_sensitive_actions else PALETTE.ACCENT_RED};"
        )
        config_layout.addWidget(confirm_label)

        layout.addWidget(config_section)

        layout.addStretch()

        # Telemetry refresh timer (every 2.5 seconds)
        self._telemetry_timer = QTimer(self)
        self._telemetry_timer.timeout.connect(self.refresh_telemetry)
        self._telemetry_timer.start(2500)
        self.refresh_telemetry()

    def update_state(self, state: str, reason: str = "") -> None:
        """Update active assistant state presentation."""
        self._state_val.setText(state.replace("_", " "))
        if state == AssistantState.IDLE.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.TEXT_SECONDARY};"
            )
            self._task_val.setText("Ready for commands")
        elif state == AssistantState.LISTENING_FOR_WAKE_WORD.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.ACCENT_CYAN};"
            )
            self._task_val.setText("Waiting for 'Hey EAGLE'...")
        elif state == AssistantState.CAPTURING_COMMAND.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.ACCENT_GOLD};"
            )
            self._task_val.setText("Capturing voice command...")
        elif state == AssistantState.PROCESSING_COMMAND.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.ACCENT_PURPLE};"
            )
            self._task_val.setText("Analyzing & executing...")
        elif state == AssistantState.SPEAKING.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.ACCENT_CYAN};"
            )
            self._task_val.setText("Speaking response...")
        elif state == AssistantState.ERROR.value:
            self._state_val.setStyleSheet(
                f"font-size: 13px; font-weight: bold; color: {PALETTE.ACCENT_RED};"
            )
            self._task_val.setText(reason or "Error occurred")

    def refresh_telemetry(self) -> None:
        """Query and display CPU and RAM metrics non-invasively."""
        try:
            cpu_pct = psutil.cpu_percent(interval=None)
            mem = psutil.virtual_memory()

            self._cpu_val.setText(f"{cpu_pct:.0f}%")
            self._cpu_bar.setValue(int(cpu_pct))

            self._ram_val.setText(f"{mem.percent:.0f}% ({mem.used / (1024**3):.1f}GB)")
            self._ram_bar.setValue(int(mem.percent))
        except Exception:
            pass

    def _create_card(self) -> QFrame:
        card = QFrame()
        card.setStyleSheet(
            f"""
            QFrame {{
                background-color: {PALETTE.BG_CARD};
                border: 1px solid {PALETTE.BORDER_DEFAULT};
                border-radius: 8px;
            }}
            """
        )
        return card
