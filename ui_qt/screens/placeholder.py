"""Placeholder screen for not-yet-implemented PySide6 screens."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton
from PySide6.QtCore import Qt
from ui_qt.theme import C, F


class PlaceholderScreen(QWidget):
    """Generic placeholder with back button."""

    def __init__(self, app, title="Coming Soon"):
        super().__init__()
        self.app = app
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)

        lbl = QLabel(title)
        lbl.setObjectName("title")
        lbl.setAlignment(Qt.AlignCenter)
        layout.addWidget(lbl)

        sub = QLabel("This screen is being built.")
        sub.setObjectName("subtitle")
        sub.setAlignment(Qt.AlignCenter)
        layout.addWidget(sub)

        btn = QPushButton("< BACK")
        btn.setObjectName("secondary")
        btn.clicked.connect(self.app.go_back)
        layout.addWidget(btn)

    def on_enter(self):
        pass

    def on_leave(self):
        pass
