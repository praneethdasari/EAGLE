"""Conversation history feed with user/assistant message bubbles and tool execution cards."""

import html
import json
import time
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from eagle.ui.theme import PALETTE


class MessageBubble(QFrame):
    """Visual speech bubble for user or assistant conversational messages."""

    def __init__(
        self,
        text: str,
        is_user: bool = False,
        timestamp: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.is_user = is_user
        ts = timestamp or time.strftime("%H:%M")

        self.setObjectName("MessageBubble")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.setSpacing(6)

        # Header with role title and timestamp
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        sender_label = QLabel("You" if is_user else "🦅 EAGLE")
        sender_color = PALETTE.ACCENT_CYAN if is_user else PALETTE.ACCENT_GOLD
        sender_label.setStyleSheet(f"font-weight: bold; font-size: 11px; color: {sender_color};")
        header_layout.addWidget(sender_label)

        header_layout.addStretch()

        time_label = QLabel(ts)
        time_label.setStyleSheet(f"font-size: 10px; color: {PALETTE.TEXT_MUTED};")
        header_layout.addWidget(time_label)

        layout.addLayout(header_layout)

        # Content text
        escaped_text = html.escape(text).replace("\n", "<br/>")
        content_label = QLabel(escaped_text)
        content_label.setWordWrap(True)
        content_label.setTextFormat(Qt.TextFormat.RichText)
        content_label.setStyleSheet(
            f"color: {PALETTE.TEXT_PRIMARY}; font-size: 13px; line-height: 1.4;"
        )
        layout.addWidget(content_label)

        # Bubble frame styling
        if is_user:
            self.setStyleSheet(
                f"""
                QFrame#MessageBubble {{
                    background-color: {PALETTE.BG_PANEL};
                    border: 1px solid {PALETTE.BORDER_DEFAULT};
                    border-right: 3px solid {PALETTE.ACCENT_CYAN};
                    border-radius: 10px;
                }}
                """
            )
        else:
            self.setStyleSheet(
                f"""
                QFrame#MessageBubble {{
                    background-color: {PALETTE.BG_CARD};
                    border: 1px solid {PALETTE.BORDER_DEFAULT};
                    border-left: 3px solid {PALETTE.ACCENT_GOLD};
                    border-radius: 10px;
                }}
                """
            )


class ToolExecutionCard(QFrame):
    """Structured expandable card displaying tool execution name, arguments, status, and output."""

    TOOL_ICONS: dict[str, str] = {
        "launch_app": "🚀 [APP]",
        "open_website": "🌐 [WEB]",
        "web_search": "🔍 [SEARCH]",
        "list_files": "📁 [FILES]",
        "inspect_file": "📄 [INSPECT]",
        "system_info": "💻 [SYSTEM]",
    }

    def __init__(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: str = "",
        success: bool = True,
        duration: float = 0.0,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ToolCard")
        args_dict = arguments or {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(8)

        # Header row: Icon + Tool Name + Execution Pill + Duration
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)

        icon_prefix = self.TOOL_ICONS.get(tool_name, "⚙️ [TOOL]")
        name_label = QLabel(f"{icon_prefix} {tool_name}")
        name_label.setStyleSheet(
            f"font-weight: 700; font-size: 12px; color: {PALETTE.TEXT_PRIMARY};"
        )
        header_layout.addWidget(name_label)

        header_layout.addStretch()

        # Status badge
        status_text = "COMPLETED" if success else "FAILED"
        status_color = PALETTE.ACCENT_GREEN if success else PALETTE.ACCENT_RED
        status_bg = "rgba(0, 230, 118, 0.15)" if success else "rgba(255, 82, 82, 0.15)"
        status_badge = QLabel(status_text)
        status_badge.setStyleSheet(
            f"""
            background-color: {status_bg};
            color: {status_color};
            font-weight: bold;
            font-size: 10px;
            padding: 2px 8px;
            border-radius: 4px;
            border: 1px solid {status_color};
            """
        )
        header_layout.addWidget(status_badge)

        if duration > 0.0:
            dur_label = QLabel(f"{duration * 1000.0:.0f}ms")
            dur_label.setStyleSheet(f"font-size: 10px; color: {PALETTE.TEXT_MUTED};")
            header_layout.addWidget(dur_label)

        layout.addLayout(header_layout)

        # Arguments preview (if any arguments were passed)
        if args_dict:
            args_str = json.dumps(args_dict, indent=2)
            args_label = QLabel(f"Arguments:\n{html.escape(args_str)}")
            args_label.setStyleSheet(
                f"""
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                color: {PALETTE.TEXT_SECONDARY};
                background-color: {PALETTE.BG_BASE};
                padding: 6px 10px;
                border-radius: 6px;
                border: 1px solid {PALETTE.BORDER_DEFAULT};
                """
            )
            layout.addWidget(args_label)

        # Output / Result preview
        if result:
            clean_res = result.strip()
            # Truncate visually if extremely long
            if len(clean_res) > 500:
                clean_res = clean_res[:500] + "\n... (truncated)"
            res_label = QLabel(f"Result:\n{html.escape(clean_res)}")
            res_label.setStyleSheet(
                f"""
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 11px;
                color: {PALETTE.ACCENT_CYAN if success else PALETTE.ACCENT_RED};
                background-color: {PALETTE.BG_BASE};
                padding: 6px 10px;
                border-radius: 6px;
                border: 1px solid {PALETTE.BORDER_DEFAULT};
                """
            )
            layout.addWidget(res_label)

        # Card container style
        border_accent = PALETTE.ACCENT_GREEN if success else PALETTE.ACCENT_RED
        self.setStyleSheet(
            f"""
            QFrame#ToolCard {{
                background-color: {PALETTE.BG_CARD};
                border: 1px solid {PALETTE.BORDER_DEFAULT};
                border-left: 3px solid {border_accent};
                border-radius: 8px;
            }}
            """
        )


class ConversationFeedWidget(QScrollArea):
    """Scrollable feed container maintaining conversation history and tool cards."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ConversationFeed")
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

        # Container widget inside scroll area
        self._container = QWidget()
        self._container.setStyleSheet("background-color: transparent;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(12)
        self._layout.addStretch()

        self.setWidget(self._container)

    def add_user_message(self, text: str) -> None:
        """Append user message bubble aligned right."""
        bubble = MessageBubble(text=text, is_user=True)
        self._append_widget(bubble, align_right=True)

    def add_assistant_message(self, text: str) -> None:
        """Append assistant message bubble aligned left."""
        bubble = MessageBubble(text=text, is_user=False)
        self._append_widget(bubble, align_right=False)

    def add_tool_card(
        self,
        tool_name: str,
        arguments: dict[str, Any] | None = None,
        result: str = "",
        success: bool = True,
        duration: float = 0.0,
    ) -> None:
        """Append tool execution card into the feed."""
        card = ToolExecutionCard(
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            success=success,
            duration=duration,
        )
        self._append_widget(card, align_right=False)

    def clear_feed(self) -> None:
        """Clear all messages from the feed."""
        while self._layout.count() > 1:
            item = self._layout.takeAt(0)
            if item is not None:
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()

    def _append_widget(self, widget: QWidget, align_right: bool = False) -> None:
        # Insert before the trailing stretch
        row_widget = QWidget()
        row_widget.setStyleSheet("background-color: transparent;")
        row_layout = QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)

        if align_right:
            row_layout.addStretch()
            widget.setMaximumWidth(int(self.width() * 0.85) if self.width() > 400 else 350)
            row_layout.addWidget(widget)
        else:
            widget.setMaximumWidth(int(self.width() * 0.90) if self.width() > 400 else 380)
            row_layout.addWidget(widget)
            row_layout.addStretch()

        insert_idx = max(0, self._layout.count() - 1)
        self._layout.insertWidget(insert_idx, row_widget)

        # Scroll to bottom smoothly
        self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())
