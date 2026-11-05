"""EAGLE Dark Theme palette, styling constants, and QSS stylesheet generator."""

from dataclasses import dataclass


@dataclass(frozen=True)
class EaglePalette:
    """Branded color palette for the EAGLE desktop interface."""

    # Backgrounds
    BG_BASE: str = "#0B0E14"  # Dark obsidian base window
    BG_PANEL: str = "#151922"  # Deep slate sidebars / headers
    BG_CARD: str = "#1C2230"  # Elevated cards / bubbles
    BG_CARD_HOVER: str = "#242C3E"  # Interactive card hover
    BG_INPUT: str = "#121620"  # Input field background

    # Borders & Dividers
    BORDER_DEFAULT: str = "#2A3447"  # Muted container borders
    BORDER_FOCUSED: str = "#00E5FF"  # Focused cyan highlight
    DIVIDER: str = "#1E2638"  # Subtle horizontal rules

    # Brand & Accent Colors
    ACCENT_CYAN: str = "#00E5FF"  # Primary cyber cyan / active voice
    ACCENT_CYAN_DIM: str = "rgba(0, 229, 255, 0.15)"  # Translucent cyan glow
    ACCENT_GOLD: str = "#FFB300"  # Secondary eagle gold / highlights
    ACCENT_GOLD_DIM: str = "rgba(255, 179, 0, 0.15)"  # Translucent gold glow
    ACCENT_PURPLE: str = "#B388FF"  # Processing / reasoning state
    ACCENT_GREEN: str = "#00E676"  # Success / ready state
    ACCENT_RED: str = "#FF5252"  # Error / alert state

    # Typography
    TEXT_PRIMARY: str = "#F0F6FC"  # High-contrast readable white
    TEXT_SECONDARY: str = "#8B949E"  # Subdued gray captions
    TEXT_MUTED: str = "#545D68"  # Disabled / placeholder text
    TEXT_ACCENT: str = "#00E5FF"  # Highlighted cyan text

    # Scrollbars & Sliders
    SCROLLBAR_THUMB: str = "#2C364A"
    SCROLLBAR_HOVER: str = "#3D4B66"


PALETTE = EaglePalette()


def get_eagle_stylesheet() -> str:
    """Generate comprehensive Qt Style Sheet (QSS) for EAGLE dark theme."""
    return f"""
    /* Global Application Defaults */
    QWidget {{
        background-color: {PALETTE.BG_BASE};
        color: {PALETTE.TEXT_PRIMARY};
        font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, "Roboto", sans-serif;
        font-size: 13px;
        selection-background-color: {PALETTE.ACCENT_CYAN};
        selection-color: {PALETTE.BG_BASE};
    }}

    QMainWindow {{
        background-color: {PALETTE.BG_BASE};
    }}

    /* Panels & Containers */
    QFrame#HeaderBar {{
        background-color: {PALETTE.BG_PANEL};
        border-bottom: 1px solid {PALETTE.BORDER_DEFAULT};
    }}

    QFrame#StatusPanel {{
        background-color: {PALETTE.BG_PANEL};
        border-left: 1px solid {PALETTE.BORDER_DEFAULT};
    }}

    QFrame#BottomBar {{
        background-color: {PALETTE.BG_PANEL};
        border-top: 1px solid {PALETTE.BORDER_DEFAULT};
    }}

    /* Scroll Areas */
    QScrollArea {{
        background-color: transparent;
        border: none;
    }}

    QScrollBar:vertical {{
        background-color: {PALETTE.BG_BASE};
        width: 8px;
        margin: 0px;
    }}

    QScrollBar::handle:vertical {{
        background-color: {PALETTE.SCROLLBAR_THUMB};
        min-height: 24px;
        border-radius: 4px;
    }}

    QScrollBar::handle:vertical:hover {{
        background-color: {PALETTE.SCROLLBAR_HOVER};
    }}

    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
        height: 0px;
    }}

    /* Text Inputs */
    QLineEdit {{
        background-color: {PALETTE.BG_INPUT};
        color: {PALETTE.TEXT_PRIMARY};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 8px;
        padding: 8px 12px;
        font-size: 13px;
    }}

    QLineEdit:focus {{
        border: 1px solid {PALETTE.ACCENT_CYAN};
        background-color: {PALETTE.BG_PANEL};
    }}

    QTextEdit, QPlainTextEdit {{
        background-color: {PALETTE.BG_INPUT};
        color: {PALETTE.TEXT_PRIMARY};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 8px;
        padding: 8px;
    }}

    /* Buttons */
    QPushButton {{
        background-color: {PALETTE.BG_CARD};
        color: {PALETTE.TEXT_PRIMARY};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 8px;
        padding: 8px 16px;
        font-weight: 600;
        min-height: 20px;
    }}

    QPushButton:hover {{
        background-color: {PALETTE.BG_CARD_HOVER};
        border-color: {PALETTE.ACCENT_CYAN};
        color: {PALETTE.ACCENT_CYAN};
    }}

    QPushButton:pressed {{
        background-color: {PALETTE.BORDER_DEFAULT};
    }}

    QPushButton:disabled {{
        background-color: {PALETTE.BG_PANEL};
        color: {PALETTE.TEXT_MUTED};
        border-color: {PALETTE.BORDER_DEFAULT};
    }}

    QPushButton#PrimaryButton {{
        background-color: {PALETTE.ACCENT_CYAN};
        color: {PALETTE.BG_BASE};
        border: 1px solid {PALETTE.ACCENT_CYAN};
    }}

    QPushButton#PrimaryButton:hover {{
        background-color: #33EBFF;
        border-color: #33EBFF;
        color: #000000;
    }}

    QPushButton#MicButton {{
        background-color: {PALETTE.BG_CARD};
        border: 2px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 20px;
        min-width: 40px;
        min-height: 40px;
        max-width: 40px;
        max-height: 40px;
    }}

    QPushButton#MicButton:hover {{
        border-color: {PALETTE.ACCENT_CYAN};
    }}

    QPushButton#MicButtonActive {{
        background-color: {PALETTE.ACCENT_CYAN_DIM};
        border: 2px solid {PALETTE.ACCENT_CYAN};
        border-radius: 20px;
        min-width: 40px;
        min-height: 40px;
        max-width: 40px;
        max-height: 40px;
    }}

    /* Tab Widget & Dialogs */
    QDialog {{
        background-color: {PALETTE.BG_BASE};
    }}

    QTabWidget::pane {{
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        background-color: {PALETTE.BG_PANEL};
        border-radius: 8px;
    }}

    QTabBar::tab {{
        background-color: {PALETTE.BG_BASE};
        color: {PALETTE.TEXT_SECONDARY};
        padding: 8px 16px;
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
        margin-right: 2px;
    }}

    QTabBar::tab:selected {{
        background-color: {PALETTE.BG_PANEL};
        color: {PALETTE.ACCENT_CYAN};
        border-bottom: 2px solid {PALETTE.ACCENT_CYAN};
        font-weight: bold;
    }}

    /* Labels & Tooltips */
    QToolTip {{
        background-color: {PALETTE.BG_CARD};
        color: {PALETTE.TEXT_PRIMARY};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 4px;
        padding: 4px 8px;
    }}

    QComboBox {{
        background-color: {PALETTE.BG_INPUT};
        color: {PALETTE.TEXT_PRIMARY};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 6px;
        padding: 6px 10px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {PALETTE.BG_CARD};
        color: {PALETTE.TEXT_PRIMARY};
        selection-background-color: {PALETTE.ACCENT_CYAN_DIM};
        selection-color: {PALETTE.ACCENT_CYAN};
        border: 1px solid {PALETTE.BORDER_DEFAULT};
    }}

    QSlider::groove:horizontal {{
        border: none;
        height: 6px;
        background: {PALETTE.BORDER_DEFAULT};
        border-radius: 3px;
    }}

    QSlider::sub-page:horizontal {{
        background: {PALETTE.ACCENT_CYAN};
        border-radius: 3px;
    }}

    QSlider::handle:horizontal {{
        background: {PALETTE.TEXT_PRIMARY};
        border: 2px solid {PALETTE.ACCENT_CYAN};
        width: 14px;
        margin-top: -4px;
        margin-bottom: -4px;
        border-radius: 7px;
    }}

    QCheckBox {{
        spacing: 8px;
        color: {PALETTE.TEXT_PRIMARY};
    }}

    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {PALETTE.BORDER_DEFAULT};
        border-radius: 4px;
        background-color: {PALETTE.BG_INPUT};
    }}

    QCheckBox::indicator:checked {{
        background-color: {PALETTE.ACCENT_CYAN};
        border-color: {PALETTE.ACCENT_CYAN};
    }}
    """
