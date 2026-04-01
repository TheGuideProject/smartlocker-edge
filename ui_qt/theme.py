"""
SmartLocker Design System — PyQt6 Theme

Maritime Tech dark theme with PPG brand accent colors.
QSS (Qt Style Sheets) for consistent styling across all widgets.
"""

# ══════════════════════════════════════════════════════════
# COLOR PALETTE
# ══════════════════════════════════════════════════════════

class C:
    """Color constants as hex strings."""
    # Backgrounds
    BG_DARK      = "#0F1119"
    BG_CARD      = "#181C28"
    BG_CARD_ALT  = "#1E2233"
    BG_HOVER     = "#232840"
    BG_INPUT     = "#12141E"
    BG_STATUS    = "#0C0E15"

    # Brand / Accent
    PRIMARY      = "#00D1BA"   # Teal/cyan (PPG marine)
    PRIMARY_DIM  = "#008C7D"
    PRIMARY_BG   = "#002B26"   # Teal tinted bg
    SECONDARY    = "#5494DA"   # Ocean blue
    SECONDARY_BG = "#0F1F33"
    ACCENT       = "#FA9F28"   # Warm amber
    ACCENT_BG    = "#2B1F0A"

    # Semantic
    SUCCESS      = "#33D17A"
    SUCCESS_BG   = "#0A2B14"
    WARNING      = "#FAC222"
    WARNING_BG   = "#2B250A"
    DANGER       = "#ED4452"
    DANGER_BG    = "#2B0A0F"

    # Text
    TEXT         = "#F5F7FA"
    TEXT_SEC     = "#99A3B8"
    TEXT_MUTED   = "#616878"

    # Borders
    BORDER       = "#2D3348"
    BORDER_HOVER = "#3D4560"


# ══════════════════════════════════════════════════════════
# FONT SIZES
# ══════════════════════════════════════════════════════════

class F:
    """Font size constants (px) — optimized for 4.3" 800x480 touch."""
    HERO   = 36
    H1     = 28
    H2     = 22
    H3     = 18
    BODY   = 16
    SMALL  = 14
    TINY   = 12


# ══════════════════════════════════════════════════════════
# SPACING
# ══════════════════════════════════════════════════════════

class S:
    """Spacing constants (px) — optimized for 4.3" touch with gloves."""
    PAD       = 10
    PAD_CARD  = 8
    GAP       = 6
    RADIUS    = 8
    BTN_H     = 44
    BTN_H_LG  = 52
    STATUS_H  = 44


# ══════════════════════════════════════════════════════════
# QSS STYLESHEET
# ══════════════════════════════════════════════════════════

STYLESHEET = f"""
/* ── Global ────────────────────────────────────── */
QWidget {{
    background-color: {C.BG_DARK};
    color: {C.TEXT};
    font-family: "Segoe UI", "Noto Sans", "DejaVu Sans", sans-serif;
    font-size: {F.BODY}px;
}}

/* ── Cards ─────────────────────────────────────── */
QFrame#card, QFrame[card="true"] {{
    background-color: {C.BG_CARD};
    border: 1px solid {C.BORDER};
    border-radius: {S.RADIUS}px;
    padding: {S.PAD_CARD}px;
}}

QFrame#card:hover {{
    border-color: {C.BORDER_HOVER};
}}

/* ── Buttons ───────────────────────────────────── */
QPushButton {{
    background-color: {C.BG_CARD};
    color: {C.TEXT};
    border: 1px solid {C.BORDER};
    border-radius: 6px;
    padding: 6px 14px;
    font-size: {F.BODY}px;
    font-weight: bold;
    min-height: 32px;
}}

QPushButton:hover {{
    background-color: {C.BG_HOVER};
    border-color: {C.BORDER_HOVER};
}}

QPushButton:pressed {{
    background-color: {C.BG_CARD_ALT};
}}

QPushButton#primary {{
    background-color: {C.PRIMARY};
    color: {C.BG_DARK};
    border: none;
    font-size: {F.H3}px;
    min-height: {S.BTN_H_LG}px;
    border-radius: {S.RADIUS}px;
}}

QPushButton#primary:hover {{
    background-color: {C.PRIMARY_DIM};
}}

QPushButton#secondary {{
    background-color: {C.SECONDARY_BG};
    color: {C.SECONDARY};
    border: 1px solid {C.SECONDARY};
}}

QPushButton#accent {{
    background-color: {C.ACCENT_BG};
    color: {C.ACCENT};
    border: 1px solid {C.ACCENT};
}}

QPushButton#danger {{
    background-color: {C.DANGER_BG};
    color: {C.DANGER};
    border: 1px solid {C.DANGER};
}}

QPushButton#success {{
    background-color: {C.SUCCESS_BG};
    color: {C.SUCCESS};
    border: 1px solid {C.SUCCESS};
}}

QPushButton#ghost {{
    background-color: transparent;
    color: {C.TEXT_SEC};
    border: none;
}}

QPushButton#nav_tile {{
    background-color: {C.BG_CARD};
    border: 1px solid {C.BORDER};
    border-radius: {S.RADIUS}px;
    min-height: 70px;
    font-size: {F.BODY}px;
    padding: 6px;
}}

QPushButton#nav_tile:hover {{
    background-color: {C.BG_HOVER};
    border-color: {C.PRIMARY};
}}

/* ── Labels ────────────────────────────────────── */
QLabel {{
    background-color: transparent;
    border: none;
    padding: 0px;
}}

QLabel#title {{
    font-size: {F.H2}px;
    font-weight: bold;
    color: {C.TEXT};
}}

QLabel#subtitle {{
    font-size: {F.SMALL}px;
    color: {C.TEXT_SEC};
}}

QLabel#hero {{
    font-size: {F.HERO}px;
    font-weight: bold;
    color: {C.PRIMARY};
}}

QLabel#section {{
    font-size: {F.SMALL}px;
    font-weight: bold;
    color: {C.SECONDARY};
    padding-left: 4px;
}}

QLabel#badge_real {{
    background-color: {C.SUCCESS_BG};
    color: {C.SUCCESS};
    border: 1px solid {C.SUCCESS};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: {F.TINY}px;
    font-weight: bold;
}}

QLabel#badge_fake {{
    background-color: {C.BG_CARD_ALT};
    color: {C.TEXT_MUTED};
    border: 1px solid {C.TEXT_MUTED};
    border-radius: 4px;
    padding: 2px 8px;
    font-size: {F.TINY}px;
}}

/* ── Progress Bar ──────────────────────────────── */
QProgressBar {{
    background-color: {C.BG_INPUT};
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
    font-size: 0px;
}}

QProgressBar::chunk {{
    background-color: {C.PRIMARY};
    border-radius: 4px;
}}

/* ── ScrollArea ────────────────────────────────── */
QScrollArea {{
    border: none;
    background-color: transparent;
}}

QScrollBar:vertical {{
    background: {C.BG_DARK};
    width: 14px;
    border-radius: 7px;
}}

QScrollBar::handle:vertical {{
    background: {C.BORDER};
    border-radius: 7px;
    min-height: 40px;
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

/* ── Tab Bar ───────────────────────────────────── */
QTabWidget::pane {{
    border: none;
    background-color: {C.BG_DARK};
}}

QTabBar {{
    background-color: {C.BG_STATUS};
}}

QTabBar::tab {{
    background-color: {C.BG_CARD};
    color: {C.TEXT_SEC};
    border: 1px solid {C.BORDER};
    border-bottom: none;
    border-radius: 8px 8px 0 0;
    padding: 10px 20px;
    font-weight: bold;
    min-width: 80px;
}}

QTabBar::tab:selected {{
    background-color: {C.PRIMARY_BG};
    color: {C.PRIMARY};
    border-color: {C.PRIMARY};
}}

QTabBar::tab:hover:!selected {{
    background-color: {C.BG_HOVER};
}}

/* ── Input ─────────────────────────────────────── */
QLineEdit, QSpinBox {{
    background-color: {C.BG_INPUT};
    color: {C.TEXT};
    border: 1px solid {C.BORDER};
    border-radius: 8px;
    padding: 8px 12px;
    font-size: {F.BODY}px;
    min-height: 36px;
}}

QLineEdit:focus, QSpinBox:focus {{
    border-color: {C.PRIMARY};
}}

/* ── Status Bar ────────────────────────────────── */
QFrame#status_bar {{
    background-color: {C.BG_STATUS};
    border-bottom: 1px solid {C.PRIMARY};
    min-height: {S.STATUS_H}px;
    max-height: {S.STATUS_H}px;
}}
"""


def enable_touch_scroll(scroll_area):
    """Enable finger/touch kinetic scrolling on a QScrollArea.

    Call this after creating any QScrollArea to allow
    drag-to-scroll on touchscreens (RPi 5" display).
    """
    from PyQt6.QtWidgets import QScroller, QScrollerProperties
    from PyQt6.QtCore import QVariant

    scroller = QScroller.scroller(scroll_area.viewport())
    scroller.grabGesture(
        scroll_area.viewport(),
        QScroller.ScrollerGestureType.LeftMouseButtonGesture,
    )

    # Tune for small touchscreen: responsive, not too much overshoot
    props = scroller.scrollerProperties()
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.DragVelocitySmoothingFactor, 0.6
    )
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.OvershootDragResistanceFactor, 0.4
    )
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.SnapPositionRatio, 0.2
    )
    props.setScrollMetric(
        QScrollerProperties.ScrollMetric.DecelerationFactor, 0.3
    )
    scroller.setScrollerProperties(props)
