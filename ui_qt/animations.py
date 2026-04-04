"""
SmartLocker Animation Utilities

Provides animated screen transitions, visual feedback effects,
and reusable animated widgets for the Qt UI.
"""

import math
from PyQt6.QtWidgets import (
    QWidget, QStackedWidget, QGraphicsOpacityEffect, QLabel,
    QVBoxLayout, QHBoxLayout, QFrame,
)
from PyQt6.QtCore import (
    Qt, QPropertyAnimation, QEasingCurve, QParallelAnimationGroup,
    QSequentialAnimationGroup, QTimer, QRect, QPoint, pyqtProperty,
    QAbstractAnimation, QVariantAnimation,
)
from PyQt6.QtGui import QPainter, QColor, QLinearGradient, QFont

from ui_qt.theme import C, F


# ════════════════════════════════════════════════════════════════
# ANIMATED STACKED WIDGET — Smooth screen transitions
# ════════════════════════════════════════════════════════════════

class AnimatedStackedWidget(QStackedWidget):
    """QStackedWidget with animated transitions between screens.

    Supports: fade, slide_left, slide_right, slide_up, slide_down.
    """

    DURATION_MS = 300  # Transition duration

    def __init__(self, parent=None):
        super().__init__(parent)
        self._animation_group: QParallelAnimationGroup = None
        self._is_animating = False

    def slide_to(self, index: int, direction: str = "slide_left"):
        """Animate transition to widget at index."""
        if index == self.currentIndex() or self._is_animating:
            return
        if index < 0 or index >= self.count():
            return

        current_widget = self.currentWidget()
        next_widget = self.widget(index)

        if not current_widget or not next_widget:
            self.setCurrentIndex(index)
            return

        self._is_animating = True
        w = self.width()
        h = self.height()

        # Determine start/end positions based on direction
        if direction == "slide_left":
            next_start = QPoint(w, 0)
            current_end = QPoint(-w, 0)
        elif direction == "slide_right":
            next_start = QPoint(-w, 0)
            current_end = QPoint(w, 0)
        elif direction == "slide_up":
            next_start = QPoint(0, h)
            current_end = QPoint(0, -h)
        elif direction == "slide_down":
            next_start = QPoint(0, -h)
            current_end = QPoint(0, h)
        elif direction == "fade":
            self._fade_to(index, current_widget, next_widget)
            return
        else:
            self.setCurrentIndex(index)
            self._is_animating = False
            return

        # Position next widget at start
        next_widget.move(next_start)
        next_widget.show()
        next_widget.raise_()

        # Animate current widget out
        anim_current = QPropertyAnimation(current_widget, b"pos")
        anim_current.setDuration(self.DURATION_MS)
        anim_current.setStartValue(QPoint(0, 0))
        anim_current.setEndValue(current_end)
        anim_current.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Animate next widget in
        anim_next = QPropertyAnimation(next_widget, b"pos")
        anim_next.setDuration(self.DURATION_MS)
        anim_next.setStartValue(next_start)
        anim_next.setEndValue(QPoint(0, 0))
        anim_next.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Run both in parallel
        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_current)
        group.addAnimation(anim_next)

        target_index = index

        def on_finished():
            self.setCurrentIndex(target_index)
            current_widget.move(0, 0)  # Reset position
            self._is_animating = False

        group.finished.connect(on_finished)
        self._animation_group = group
        group.start()

    def _fade_to(self, index: int, current_widget: QWidget, next_widget: QWidget):
        """Cross-fade between two widgets."""
        # Add opacity effect to current
        current_effect = QGraphicsOpacityEffect(current_widget)
        current_widget.setGraphicsEffect(current_effect)

        next_effect = QGraphicsOpacityEffect(next_widget)
        next_widget.setGraphicsEffect(next_effect)
        next_effect.setOpacity(0.0)
        next_widget.show()
        next_widget.raise_()

        # Fade out current
        anim_out = QPropertyAnimation(current_effect, b"opacity")
        anim_out.setDuration(self.DURATION_MS)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)
        anim_out.setEasingCurve(QEasingCurve.Type.InQuad)

        # Fade in next
        anim_in = QPropertyAnimation(next_effect, b"opacity")
        anim_in.setDuration(self.DURATION_MS)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)
        anim_in.setEasingCurve(QEasingCurve.Type.OutQuad)

        group = QParallelAnimationGroup(self)
        group.addAnimation(anim_out)
        group.addAnimation(anim_in)

        target_index = index

        def on_finished():
            self.setCurrentIndex(target_index)
            current_widget.setGraphicsEffect(None)
            next_widget.setGraphicsEffect(None)
            self._is_animating = False

        group.finished.connect(on_finished)
        self._animation_group = group
        group.start()

    @property
    def is_animating(self) -> bool:
        return self._is_animating


# ════════════════════════════════════════════════════════════════
# PULSING DOT — Live/active indicator
# ════════════════════════════════════════════════════════════════

class PulsingDot(QWidget):
    """Small animated dot that pulses to indicate live status.
    Timer auto-pauses when widget is hidden (e.g. screen not visible)."""

    def __init__(self, color: str = C.SUCCESS, size: int = 12, parent=None):
        super().__init__(parent)
        self._color = QColor(color)
        self._size = size
        self._opacity = 1.0
        self._pulse_timer = QTimer(self)
        self._pulse_timer.timeout.connect(self._tick)
        self._phase = 0.0
        self._wants_running = False
        self.setFixedSize(size + 4, size + 4)

    def start(self):
        self._wants_running = True
        if self.isVisible():
            self._pulse_timer.start(50)

    def stop(self):
        self._wants_running = False
        self._pulse_timer.stop()
        self._opacity = 1.0
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._wants_running and not self._pulse_timer.isActive():
            self._pulse_timer.start(50)

    def hideEvent(self, event):
        super().hideEvent(event)
        self._pulse_timer.stop()

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def _tick(self):
        self._phase += 0.1
        self._opacity = 0.4 + 0.6 * (0.5 + 0.5 * math.sin(self._phase))
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QColor(self._color)
        c.setAlphaF(self._opacity)
        p.setBrush(c)
        p.setPen(Qt.PenStyle.NoPen)
        margin = 2
        p.drawEllipse(margin, margin, self._size, self._size)
        p.end()


# ════════════════════════════════════════════════════════════════
# ANIMATED PROGRESS RING — Circular progress indicator
# ════════════════════════════════════════════════════════════════

class ProgressRing(QWidget):
    """Animated circular progress indicator with percentage text."""

    def __init__(self, size: int = 80, thickness: int = 6, parent=None):
        super().__init__(parent)
        self._size = size
        self._thickness = thickness
        self._value = 0.0  # 0.0 → 1.0
        self._target = 0.0
        self._color = QColor(C.PRIMARY)
        self._bg_color = QColor(C.BG_INPUT)
        self._text_color = QColor(C.TEXT)
        self._show_text = True
        self._indeterminate = False
        self._spin_angle = 0

        self.setFixedSize(size, size)

        self._anim_timer = QTimer(self)
        self._anim_timer.timeout.connect(self._animate)

    def set_value(self, value: float):
        """Set progress (0.0 to 1.0) with smooth animation."""
        self._target = max(0.0, min(1.0, value))
        self._indeterminate = False
        if not self._anim_timer.isActive():
            self._anim_timer.start(16)

    def set_indeterminate(self, enabled: bool):
        """Spinning mode (no specific progress)."""
        self._indeterminate = enabled
        if enabled and not self._anim_timer.isActive():
            self._anim_timer.start(16)

    def set_color(self, color: str):
        self._color = QColor(color)
        self.update()

    def _animate(self):
        if self._indeterminate:
            self._spin_angle = (self._spin_angle + 4) % 360
            self.update()
        else:
            diff = self._target - self._value
            if abs(diff) < 0.005:
                self._value = self._target
                self._anim_timer.stop()
            else:
                self._value += diff * 0.15
            self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(
            self._thickness, self._thickness,
            -self._thickness, -self._thickness,
        )

        # Background circle
        pen = p.pen()
        from PyQt6.QtGui import QPen
        p.setPen(QPen(self._bg_color, self._thickness, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap))
        p.drawArc(rect, 0, 360 * 16)

        # Progress arc
        p.setPen(QPen(self._color, self._thickness, Qt.PenStyle.SolidLine,
                       Qt.PenCapStyle.RoundCap))

        if self._indeterminate:
            span = 90 * 16
            start = self._spin_angle * 16
            p.drawArc(rect, start, span)
        else:
            span = int(self._value * 360 * 16)
            p.drawArc(rect, 90 * 16, -span)

        # Center text
        if self._show_text and not self._indeterminate:
            p.setPen(self._text_color)
            font = QFont()
            font.setPixelSize(self._size // 4)
            font.setBold(True)
            p.setFont(font)
            text = f"{int(self._value * 100)}%"
            p.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, text)

        p.end()


# ════════════════════════════════════════════════════════════════
# ANIMATED STATUS BADGE — Fade-in/out badge
# ════════════════════════════════════════════════════════════════

class AnimatedBadge(QLabel):
    """Badge label that fades in/out when text changes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._effect = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(self._effect)
        self._effect.setOpacity(1.0)

    def set_text_animated(self, text: str, duration_ms: int = 200):
        """Change text with fade-out/in animation."""
        if self.text() == text:
            return

        # Fade out
        anim_out = QPropertyAnimation(self._effect, b"opacity")
        anim_out.setDuration(duration_ms // 2)
        anim_out.setStartValue(1.0)
        anim_out.setEndValue(0.0)

        # Fade in
        anim_in = QPropertyAnimation(self._effect, b"opacity")
        anim_in.setDuration(duration_ms // 2)
        anim_in.setStartValue(0.0)
        anim_in.setEndValue(1.0)

        new_text = text

        def on_half():
            self.setText(new_text)

        seq = QSequentialAnimationGroup(self)
        seq.addAnimation(anim_out)
        anim_out.finished.connect(on_half)
        seq.addAnimation(anim_in)
        seq.start()


# ════════════════════════════════════════════════════════════════
# GRADIENT BANNER — Animated background gradient
# ════════════════════════════════════════════════════════════════

class GradientBanner(QFrame):
    """Banner with animated gradient background (used for splash/hero)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._color1 = QColor(C.PRIMARY_BG)
        self._color2 = QColor(C.BG_DARK)
        self._accent = QColor(C.PRIMARY)

    def start_animation(self):
        self._timer.start(33)  # ~30 FPS

    def stop_animation(self):
        self._timer.stop()

    def _tick(self):
        self._phase += 0.02
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        w = self.width()
        h = self.height()

        # Animated gradient position
        offset = 0.5 + 0.5 * math.sin(self._phase)
        x_start = int(w * offset * 0.5)

        gradient = QLinearGradient(x_start, 0, w, h)
        gradient.setColorAt(0.0, self._color1)
        gradient.setColorAt(0.5, self._color2)

        # Subtle accent glow
        accent = QColor(self._accent)
        accent.setAlphaF(0.08 + 0.04 * math.sin(self._phase * 1.5))
        gradient.setColorAt(1.0, accent)

        p.fillRect(0, 0, w, h, gradient)
        p.end()


# ════════════════════════════════════════════════════════════════
# SPLASH SCREEN WIDGET
# ════════════════════════════════════════════════════════════════

class SplashWidget(QWidget):
    """Animated splash screen with PPG branding and loading progress."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()
        self._progress = ProgressRing(size=60, thickness=4)
        self._layout.addWidget(self._progress, alignment=Qt.AlignmentFlag.AlignCenter)
        self._progress.set_indeterminate(True)

    def _build_ui(self):
        self._layout = QVBoxLayout(self)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._layout.setSpacing(16)

        # Background gradient
        self._bg = GradientBanner(self)
        self._bg.lower()

        # Logo / Title
        title = QLabel("SMARTLOCKER")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet(
            f"font-size: {F.HERO}px; font-weight: bold; "
            f"color: {C.PRIMARY}; letter-spacing: 4px;"
        )
        self._layout.addWidget(title)

        subtitle = QLabel("Paint Inventory System")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet(
            f"font-size: {F.H3}px; color: {C.TEXT_SEC};"
        )
        self._layout.addWidget(subtitle)

        self._layout.addSpacing(20)

        # Status text
        self._status = QLabel("Initializing hardware...")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED};"
        )
        self._layout.addWidget(self._status)

    def set_status(self, text: str):
        self._status.setText(text)

    def set_progress(self, value: float):
        """Set loading progress (0.0 to 1.0)."""
        self._progress.set_indeterminate(False)
        self._progress.set_value(value)

    def start(self):
        self._bg.start_animation()

    def stop(self):
        self._bg.stop_animation()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._bg.setGeometry(self.rect())


# ════════════════════════════════════════════════════════════════
# HELPER: animate widget entry
# ════════════════════════════════════════════════════════════════

def fade_in(widget: QWidget, duration_ms: int = 300):
    """Fade a widget in from transparent."""
    effect = QGraphicsOpacityEffect(widget)
    widget.setGraphicsEffect(effect)
    effect.setOpacity(0.0)

    anim = QPropertyAnimation(effect, b"opacity")
    anim.setDuration(duration_ms)
    anim.setStartValue(0.0)
    anim.setEndValue(1.0)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)

    def cleanup():
        widget.setGraphicsEffect(None)

    anim.finished.connect(cleanup)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim


def slide_in(widget: QWidget, direction: str = "up", duration_ms: int = 300):
    """Slide a widget in from off-screen."""
    parent = widget.parentWidget()
    if not parent:
        return None

    if direction == "up":
        start = QPoint(widget.x(), parent.height())
    elif direction == "down":
        start = QPoint(widget.x(), -widget.height())
    elif direction == "left":
        start = QPoint(parent.width(), widget.y())
    elif direction == "right":
        start = QPoint(-widget.width(), widget.y())
    else:
        return None

    end = widget.pos()
    widget.move(start)
    widget.show()

    anim = QPropertyAnimation(widget, b"pos")
    anim.setDuration(duration_ms)
    anim.setStartValue(start)
    anim.setEndValue(end)
    anim.setEasingCurve(QEasingCurve.Type.OutCubic)
    anim.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)
    return anim
