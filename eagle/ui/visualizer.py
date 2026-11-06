"""Microphone status indicator badge and dynamic real-time audio visualizer widget."""

import math
from typing import Any

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QBrush, QColor, QLinearGradient, QPainter, QPaintEvent, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QWidget

from eagle.services.continuous_listener import AssistantState
from eagle.ui.theme import PALETTE


class MicrophoneIndicatorWidget(QWidget):
    """Pill badge showing current microphone/assistant state with glowing status indicator."""

    clicked = Signal()

    STATE_COLORS: dict[str, str] = {
        AssistantState.IDLE.value: PALETTE.TEXT_SECONDARY,
        AssistantState.SLEEPING.value: PALETTE.ACCENT_CYAN,
        AssistantState.LISTENING_FOR_WAKE_WORD.value: PALETTE.ACCENT_CYAN,
        AssistantState.ACTIVE.value: PALETTE.ACCENT_CYAN,
        AssistantState.CAPTURING_COMMAND.value: PALETTE.ACCENT_GOLD,
        AssistantState.PROCESSING_COMMAND.value: PALETTE.ACCENT_PURPLE,
        AssistantState.SPEAKING.value: PALETTE.ACCENT_CYAN,
        AssistantState.AWAITING_FOLLOWUP.value: PALETTE.ACCENT_GOLD,
        AssistantState.PRIVACY_MUTED.value: PALETTE.ACCENT_RED,
        AssistantState.STOPPING.value: PALETTE.TEXT_MUTED,
        AssistantState.ERROR.value: PALETTE.ACCENT_RED,
    }

    STATE_LABELS: dict[str, str] = {
        AssistantState.IDLE.value: "Idle",
        AssistantState.SLEEPING.value: "Sleeping (Waiting for 'Hey EAGLE')",
        AssistantState.LISTENING_FOR_WAKE_WORD.value: "Sleeping (Waiting for 'Hey EAGLE')",
        AssistantState.ACTIVE.value: "Active",
        AssistantState.CAPTURING_COMMAND.value: "Listening to Command...",
        AssistantState.PROCESSING_COMMAND.value: "Thinking...",
        AssistantState.SPEAKING.value: "Speaking...",
        AssistantState.AWAITING_FOLLOWUP.value: "Awaiting Follow-up...",
        AssistantState.PRIVACY_MUTED.value: "Mic Muted (Privacy)",
        AssistantState.STOPPING.value: "Stopping...",
        AssistantState.ERROR.value: "System Error",
    }

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._current_state: str = AssistantState.IDLE.value
        self._pulse_value: float = 0.0
        self._pulse_direction: float = 1.0

        self.setFixedHeight(36)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        # Pulse timer for animated glow
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._on_pulse_tick)
        self._pulse_timer.start(40)  # ~25 FPS

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 4, 16, 4)
        layout.setSpacing(10)

        # Spacer placeholder for dot drawn in paintEvent
        self._spacer = QWidget()
        self._spacer.setFixedSize(14, 14)
        layout.addWidget(self._spacer)

        self._label = QLabel(self.STATE_LABELS[self._current_state])
        self._label.setStyleSheet(
            f"color: {PALETTE.TEXT_PRIMARY}; font-weight: 600; font-size: 12px;"
        )
        layout.addWidget(self._label)

    def set_state(self, state: str, reason: str = "") -> None:
        """Update active assistant state and label."""
        self._current_state = state
        display_text = self.STATE_LABELS.get(state, state)
        self._label.setText(display_text)
        self.update()

    @property
    def current_state(self) -> str:
        return self._current_state

    def _on_pulse_tick(self) -> None:
        # Oscillate pulse between 0.0 and 1.0
        self._pulse_value += 0.06 * self._pulse_direction
        if self._pulse_value >= 1.0:
            self._pulse_value = 1.0
            self._pulse_direction = -1.0
        elif self._pulse_value <= 0.0:
            self._pulse_value = 0.0
            self._pulse_direction = 1.0

        if self._current_state in (
            AssistantState.LISTENING_FOR_WAKE_WORD.value,
            AssistantState.CAPTURING_COMMAND.value,
            AssistantState.PROCESSING_COMMAND.value,
            AssistantState.SPEAKING.value,
        ):
            self.update()

    def mousePressEvent(self, event: Any) -> None:
        self.clicked.emit()
        if event is not None:
            super().mousePressEvent(event)

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Draw outer pill background
        bg_color = QColor(PALETTE.BG_CARD)
        border_color = QColor(PALETTE.BORDER_DEFAULT)
        painter.setBrush(QBrush(bg_color))
        painter.setPen(QPen(border_color, 1))
        pill_rect = QRectF(0, 0, self.width(), self.height())
        painter.drawRoundedRect(pill_rect, 18, 18)

        # Draw glowing dot on left
        dot_color_hex = self.STATE_COLORS.get(self._current_state, PALETTE.TEXT_SECONDARY)
        dot_color = QColor(dot_color_hex)

        dot_center = QPointF(19, self.height() / 2)
        base_radius = 5.0

        # Draw halo if in active state
        if self._current_state != AssistantState.IDLE.value:
            halo_radius = base_radius + (3.0 * self._pulse_value)
            halo_color = QColor(dot_color)
            halo_color.setAlpha(int(60 * (1.0 - self._pulse_value * 0.5)))
            painter.setBrush(QBrush(halo_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(dot_center, halo_radius, halo_radius)

        # Center dot
        painter.setBrush(QBrush(dot_color))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(dot_center, base_radius, base_radius)


class AudioVisualizerWidget(QWidget):
    """Dynamic multi-bar audio reactive visualizer rendering live microphone amplitude."""

    def __init__(self, bar_count: int = 28, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.bar_count = max(8, bar_count)
        self._current_levels = [0.05] * self.bar_count
        self._target_levels = [0.05] * self.bar_count
        self._decay_rate = 0.85
        self._current_amplitude = 0.0

        self.setFixedHeight(50)
        self.setMinimumWidth(180)

        # Animation timer running at ~30 FPS
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._on_animation_frame)
        self._timer.start(33)

    def set_amplitude(self, amplitude: float) -> None:
        """Update live audio amplitude (0.0 to 1.0)."""
        clamped = max(0.0, min(1.0, amplitude))
        self._current_amplitude = clamped

        # Generate symmetrical wave heights based on amplitude
        center = (self.bar_count - 1) / 2.0
        for i in range(self.bar_count):
            dist_from_center = abs(i - center) / (center if center > 0 else 1)
            # High frequency variation across bars
            harmonic = math.sin(i * 0.8 + 0.3) * 0.2 + 0.8
            target = clamped * harmonic * (1.0 - dist_from_center * 0.4)
            # Ensure minimum baseline visibility
            self._target_levels[i] = max(0.05, min(1.0, target))

    def _on_animation_frame(self) -> None:
        needs_redraw = False
        for i in range(self.bar_count):
            # Smooth interpolation towards target
            diff = self._target_levels[i] - self._current_levels[i]
            if diff > 0:
                self._current_levels[i] += diff * 0.5
            else:
                self._current_levels[i] *= self._decay_rate

            # Smoothly lower target if audio is quiet
            self._target_levels[i] *= self._decay_rate
            if self._target_levels[i] < 0.05:
                self._target_levels[i] = 0.05

            if self._current_levels[i] > 0.055:
                needs_redraw = True

        if needs_redraw or self._current_amplitude > 0.01:
            self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = float(self.width())
        height = float(self.height())

        # Total bar spacing calculations
        spacing = 3.0
        total_spacing = spacing * (self.bar_count - 1)
        bar_width = max(2.0, (width - total_spacing) / self.bar_count)

        # Gradient from Cyan to Gold
        gradient = QLinearGradient(0, height, 0, 0)
        gradient.setColorAt(0.0, QColor(PALETTE.ACCENT_CYAN))
        gradient.setColorAt(0.7, QColor(PALETTE.ACCENT_CYAN))
        gradient.setColorAt(1.0, QColor(PALETTE.ACCENT_GOLD))

        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.PenStyle.NoPen)

        for i in range(self.bar_count):
            x = i * (bar_width + spacing)
            level = max(0.05, min(1.0, self._current_levels[i]))
            bar_height = max(4.0, height * level * 0.9)
            y = (height - bar_height) / 2.0  # Center vertically

            rect = QRectF(x, y, bar_width, bar_height)
            radius = min(bar_width / 2.0, 3.0)
            painter.drawRoundedRect(rect, radius, radius)
