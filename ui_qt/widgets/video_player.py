"""
SmartLocker Video Player Widget

Provides an embedded video player for instructional videos,
safety warnings, and branded content on the touchscreen UI.

Uses Qt Multimedia (QMediaPlayer + QVideoWidget).
Fallback to static image if multimedia not available.
"""

import logging
from pathlib import Path

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
)
from PyQt6.QtCore import Qt, QUrl, QTimer

from ui_qt.theme import C, F, S

logger = logging.getLogger("smartlocker.ui.video")

# Try importing multimedia (may not be available on all systems)
_HAS_MULTIMEDIA = False
try:
    from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput
    from PyQt6.QtMultimediaWidgets import QVideoWidget
    _HAS_MULTIMEDIA = True
except ImportError:
    logger.warning("PyQt6.QtMultimedia not available — video playback disabled")


class VideoPlayer(QWidget):
    """Embedded video player with play/pause controls.

    Falls back to a placeholder label if Qt Multimedia is not installed.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self._video_path = ""
        self._loop = False
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        if _HAS_MULTIMEDIA:
            # Video output widget
            self._video_widget = QVideoWidget()
            self._video_widget.setStyleSheet(f"background-color: {C.BG_DARK};")
            layout.addWidget(self._video_widget, stretch=1)

            # Media player
            self._player = QMediaPlayer()
            self._audio = QAudioOutput()
            self._audio.setVolume(0.5)
            self._player.setAudioOutput(self._audio)
            self._player.setVideoOutput(self._video_widget)

            # Loop handler
            self._player.mediaStatusChanged.connect(self._on_status_changed)

            # Controls bar
            controls = QFrame()
            controls.setStyleSheet(
                f"background-color: {C.BG_STATUS}; "
                f"border-top: 1px solid {C.BORDER};"
            )
            ctrl_layout = QHBoxLayout(controls)
            ctrl_layout.setContentsMargins(S.PAD, 4, S.PAD, 4)
            ctrl_layout.setSpacing(S.GAP)

            self._btn_play = QPushButton("PLAY")
            self._btn_play.setObjectName("primary")
            self._btn_play.setFixedHeight(40)
            self._btn_play.clicked.connect(self.toggle_play)
            ctrl_layout.addWidget(self._btn_play)

            self._btn_stop = QPushButton("STOP")
            self._btn_stop.setFixedHeight(40)
            self._btn_stop.clicked.connect(self.stop)
            ctrl_layout.addWidget(self._btn_stop)

            ctrl_layout.addStretch(1)

            self._lbl_status = QLabel("Ready")
            self._lbl_status.setStyleSheet(
                f"font-size: {F.SMALL}px; color: {C.TEXT_SEC};"
            )
            ctrl_layout.addWidget(self._lbl_status)

            layout.addWidget(controls)
        else:
            # Fallback: static placeholder
            self._player = None
            placeholder = QLabel("Video playback not available\n(install PyQt6-Multimedia)")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setStyleSheet(
                f"font-size: {F.H3}px; color: {C.TEXT_MUTED}; "
                f"background-color: {C.BG_CARD}; border-radius: {S.RADIUS}px;"
            )
            layout.addWidget(placeholder)

    def load(self, path: str, loop: bool = False):
        """Load a video file."""
        if not self._player:
            return

        self._video_path = path
        self._loop = loop

        p = Path(path)
        if p.exists():
            self._player.setSource(QUrl.fromLocalFile(str(p.resolve())))
            self._lbl_status.setText(f"Loaded: {p.name}")
        else:
            self._lbl_status.setText(f"File not found: {p.name}")
            logger.warning(f"Video file not found: {path}")

    def play(self):
        if self._player:
            self._player.play()
            self._btn_play.setText("PAUSE")
            self._lbl_status.setText("Playing...")

    def pause(self):
        if self._player:
            self._player.pause()
            self._btn_play.setText("PLAY")
            self._lbl_status.setText("Paused")

    def stop(self):
        if self._player:
            self._player.stop()
            self._btn_play.setText("PLAY")
            self._lbl_status.setText("Stopped")

    def toggle_play(self):
        if not self._player:
            return
        if self._player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.pause()
        else:
            self.play()

    def set_volume(self, volume: float):
        """Set volume (0.0 to 1.0)."""
        if _HAS_MULTIMEDIA and hasattr(self, '_audio'):
            self._audio.setVolume(max(0.0, min(1.0, volume)))

    def _on_status_changed(self, status):
        if not _HAS_MULTIMEDIA:
            return
        if status == QMediaPlayer.MediaStatus.EndOfMedia and self._loop:
            self._player.setPosition(0)
            self._player.play()
        elif status == QMediaPlayer.MediaStatus.EndOfMedia:
            self._btn_play.setText("PLAY")
            self._lbl_status.setText("Finished")


class VideoSplash(QWidget):
    """Full-screen video splash with auto-dismiss.

    Plays a branding/safety video then calls on_finished callback.
    Tap anywhere to skip.
    """

    def __init__(self, video_path: str, duration_s: float = 5.0,
                 on_finished=None, parent=None):
        super().__init__(parent)
        self._on_finished = on_finished
        self._duration = duration_s

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._player = VideoPlayer()
        layout.addWidget(self._player)

        # Skip hint
        skip_label = QLabel("Tap anywhere to skip")
        skip_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        skip_label.setStyleSheet(
            f"font-size: {F.SMALL}px; color: {C.TEXT_MUTED}; "
            f"padding: 4px; background-color: {C.BG_STATUS};"
        )
        layout.addWidget(skip_label)

        # Load and auto-play
        self._player.load(video_path)
        QTimer.singleShot(200, self._player.play)

        # Auto-dismiss timer
        if duration_s > 0:
            QTimer.singleShot(int(duration_s * 1000), self._finish)

    def mousePressEvent(self, event):
        """Tap to skip."""
        self._finish()

    def _finish(self):
        self._player.stop()
        if self._on_finished:
            self._on_finished()
