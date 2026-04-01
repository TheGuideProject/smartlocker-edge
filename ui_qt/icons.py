"""
SmartLocker Icon System

Consistent icon labels for the entire UI. Uses styled QLabel widgets
with Unicode glyphs inside colored circles/badges. Works on all
platforms (Windows, RPi, Linux) without external icon fonts.

Usage:
    from ui_qt.icons import Icon, icon_label, status_dot, section_header

    label = icon_label(Icon.MIXING, size=32)
    dot = status_dot(connected=True)
    header = section_header(Icon.INVENTORY, "INVENTORY")
"""

from PyQt6.QtWidgets import QLabel, QHBoxLayout, QWidget, QFrame
from PyQt6.QtCore import Qt
from ui_qt.theme import C, F, S


class Icon:
    """Unicode glyphs for consistent icons across the UI."""
    # Navigation
    BACK        = "\u25C0"   # ◀
    FORWARD     = "\u25B6"   # ▶
    HOME        = "\u2302"   # ⌂
    CLOSE       = "\u2715"   # ✕
    MENU        = "\u2630"   # ☰

    # Actions
    PLAY        = "\u25B6"   # ▶
    STOP        = "\u25A0"   # ■
    REFRESH     = "\u21BB"   # ↻
    SAVE        = "\u2713"   # ✓
    DELETE      = "\u2716"   # ✖
    ADD         = "\u002B"   # +
    EDIT        = "\u270E"   # ✎

    # Status
    OK          = "\u2713"   # ✓
    WARN        = "\u26A0"   # ⚠
    ERROR       = "\u2716"   # ✖
    INFO        = "\u2139"   # ℹ
    DOT         = "\u2B24"   # ⬤

    # Sections
    MIXING      = "\u2697"   # ⚗ (alembic)
    INVENTORY   = "\u2610"   # ☐ (ballot box)
    SENSORS     = "\u2316"   # ⌖ (position indicator)
    SETTINGS    = "\u2699"   # ⚙
    CHART       = "\u2637"   # ☷ (trigram)
    CLOUD       = "\u2601"   # ☁
    LOCK        = "\u26BF"   # ⚿
    WEIGHT      = "\u2696"   # ⚖
    TAG         = "\u2605"   # ★
    ALARM       = "\u2622"   # ☢
    HEALTH      = "\u2665"   # ♥
    SHELF       = "\u2592"   # ▒

    # Slot states
    OCCUPIED    = "\u25CF"   # ●
    EMPTY       = "\u25CB"   # ○
    REMOVED     = "\u25D2"   # ◒


def icon_badge(glyph: str, bg_color: str = C.PRIMARY_BG,
               fg_color: str = C.PRIMARY, size: int = 32) -> QLabel:
    """Create a circular icon badge (colored circle with glyph inside)."""
    lbl = QLabel(glyph)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedSize(size, size)
    font_px = int(size * 0.55)
    lbl.setStyleSheet(
        f"background-color: {bg_color}; color: {fg_color};"
        f"border-radius: {size // 2}px;"
        f"font-size: {font_px}px; font-weight: bold;"
        f"border: 1px solid {fg_color};"
    )
    return lbl


def icon_label(glyph: str, color: str = C.PRIMARY, size: int = 18) -> QLabel:
    """Create an inline icon label (no background, just the glyph)."""
    lbl = QLabel(glyph)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setFixedSize(size + 4, size + 4)
    lbl.setStyleSheet(
        f"color: {color}; font-size: {size}px; font-weight: bold;"
        f"background: transparent; border: none;"
    )
    return lbl


def status_dot(active: bool = True, size: int = 10) -> QLabel:
    """Create a small solid status dot (green=active, red=inactive)."""
    color = C.SUCCESS if active else C.DANGER
    lbl = QLabel()
    lbl.setFixedSize(size, size)
    lbl.setStyleSheet(
        f"background-color: {color}; border-radius: {size // 2}px;"
        f"border: none;"
    )
    return lbl


def type_badge(text: str, variant: str = "primary") -> QLabel:
    """Create a small type badge (BASE_PAINT, HARDENER, etc.)."""
    colors = {
        "primary": (C.PRIMARY_BG, C.PRIMARY, C.PRIMARY),
        "secondary": (C.SECONDARY_BG, C.SECONDARY, C.SECONDARY),
        "accent": (C.ACCENT_BG, C.ACCENT, C.ACCENT),
        "success": (C.SUCCESS_BG, C.SUCCESS, C.SUCCESS),
        "warning": (C.WARNING_BG, C.WARNING, C.WARNING),
        "danger": (C.DANGER_BG, C.DANGER, C.DANGER),
        "muted": (C.BG_CARD_ALT, C.TEXT_MUTED, C.TEXT_MUTED),
    }
    bg, fg, border = colors.get(variant, colors["primary"])
    lbl = QLabel(text)
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet(
        f"background-color: {bg}; color: {fg};"
        f"border: 1px solid {border}; border-radius: 4px;"
        f"padding: 2px 8px; font-size: {F.TINY}px; font-weight: bold;"
    )
    return lbl


def section_header(glyph: str, text: str, color: str = C.SECONDARY) -> QWidget:
    """Create a section header with icon + text + horizontal line."""
    widget = QWidget()
    layout = QHBoxLayout(widget)
    layout.setContentsMargins(0, 4, 0, 4)
    layout.setSpacing(6)

    icn = icon_label(glyph, color=color, size=16)
    layout.addWidget(icn)

    lbl = QLabel(text)
    lbl.setStyleSheet(
        f"font-size: {F.SMALL}px; font-weight: bold;"
        f"color: {color}; letter-spacing: 1px;"
    )
    layout.addWidget(lbl)

    # Horizontal line
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet(f"color: {color}; background-color: {color}; max-height: 1px;")
    layout.addWidget(line, stretch=1)

    return widget


def screen_header(app, title: str, glyph: str = "",
                  accent: str = C.PRIMARY) -> QFrame:
    """Create a standard screen header bar with back button + icon + title.

    Returns the header frame. Consistent across ALL screens.
    """
    header = QFrame()
    header.setObjectName("screen_header")
    header.setStyleSheet(
        f"QFrame#screen_header {{"
        f"  background: qlineargradient(x1:0, y1:0, x2:1, y2:0,"
        f"    stop:0 {C.BG_STATUS}, stop:1 {C.BG_CARD});"
        f"  border-bottom: 2px solid {accent};"
        f"  min-height: 48px; max-height: 48px;"
        f"}}"
    )

    layout = QHBoxLayout(header)
    layout.setContentsMargins(S.PAD, 0, S.PAD, 0)
    layout.setSpacing(S.GAP)

    # Back button
    from PyQt6.QtWidgets import QPushButton
    btn_back = QPushButton(f"{Icon.BACK}  BACK")
    btn_back.setObjectName("ghost")
    btn_back.setCursor(Qt.CursorShape.PointingHandCursor)
    btn_back.setStyleSheet(
        f"color: {C.TEXT_SEC}; font-size: {F.SMALL}px;"
        f"border: none; background: transparent; padding: 4px 8px;"
    )
    btn_back.clicked.connect(lambda: app.go_back())
    layout.addWidget(btn_back)

    # Icon
    if glyph:
        icn = icon_label(glyph, color=accent, size=20)
        layout.addWidget(icn)

    # Title
    lbl = QLabel(title)
    lbl.setStyleSheet(
        f"font-size: {F.H3}px; font-weight: bold; color: {C.TEXT};"
        f"letter-spacing: 1px;"
    )
    layout.addWidget(lbl)

    layout.addStretch(1)

    return header, layout
