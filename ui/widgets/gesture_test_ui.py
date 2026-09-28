"""
CryNet Gesture Testing Diagnostic Panel
Provides real-time feedback on finger flexion/extension states, gesture classification,
pinch detection, swipe events, and confidence levels for standalone home validation.
"""

from __future__ import annotations
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)
from gestures.gesture_state import GestureType, TrackingData


class DiagnosticCard(QFrame):
    """Futuristic telemetry metric card."""

    def __init__(self, label: str, default_val: str = "OFFLINE", parent=None):
        super().__init__(parent)
        self.setObjectName("diagCard")
        self.setStyleSheet("""
            QFrame#diagCard {
                background-color: #0c141f;
                border: 1px solid #1a2a3a;
                border-radius: 6px;
                padding: 6px 12px;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(4)

        self.title_label = QLabel(label.upper())
        self.title_label.setStyleSheet("color: #627d98; font-size: 11px; font-weight: 600; letter-spacing: 1px;")

        self.val_label = QLabel(default_val)
        self.val_label.setStyleSheet("color: #00e5ff; font-size: 16px; font-weight: bold; font-family: Consolas;")

        layout.addWidget(self.title_label)
        layout.addWidget(self.val_label)

    def set_value(self, val: str, is_active: bool = True, custom_color: str = "") -> None:
        self.val_label.setText(val)
        if custom_color:
            color = custom_color
        elif is_active:
            color = "#00e5ff" if val not in ("FOLDED", "NO", "NONE") else "#486581"
        else:
            color = "#486581"
        self.val_label.setStyleSheet(f"color: {color}; font-size: 16px; font-weight: bold; font-family: Consolas;")


class GestureTestPanel(QWidget):
    """Interactive visual testing monitor displaying all tracked hand dimensions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(12)

        header = QLabel("TACTICAL GESTURE DIAGNOSTIC MATRIX")
        header.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 1.5px;")
        main_layout.addWidget(header)

        # Overview Grid
        grid = QGridLayout()
        grid.setSpacing(10)

        self.card_hand = DiagnosticCard("Hand Detected", "NO")
        self.card_gesture = DiagnosticCard("Active Gesture", "NONE")
        self.card_pinch = DiagnosticCard("Pinch State", "NO")
        self.card_swipe = DiagnosticCard("Swipe Event", "NONE")

        grid.addWidget(self.card_hand, 0, 0)
        grid.addWidget(self.card_gesture, 0, 1)
        grid.addWidget(self.card_pinch, 1, 0)
        grid.addWidget(self.card_swipe, 1, 1)

        main_layout.addLayout(grid)

        # Finger Status Group
        finger_group = QGroupBox("ANATOMICAL FINGER STATUS")
        finger_group.setStyleSheet("""
            QGroupBox {
                color: #829ab1;
                font-size: 11px;
                font-weight: 600;
                border: 1px solid #1a2a3a;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
        """)
        f_layout = QGridLayout(finger_group)
        f_layout.setSpacing(8)

        self.card_thumb = DiagnosticCard("Thumb", "FOLDED")
        self.card_index = DiagnosticCard("Index", "FOLDED")
        self.card_middle = DiagnosticCard("Middle", "FOLDED")
        self.card_ring = DiagnosticCard("Ring", "FOLDED")
        self.card_pinky = DiagnosticCard("Pinky", "FOLDED")

        f_layout.addWidget(self.card_thumb, 0, 0)
        f_layout.addWidget(self.card_index, 0, 1)
        f_layout.addWidget(self.card_middle, 0, 2)
        f_layout.addWidget(self.card_ring, 1, 0)
        f_layout.addWidget(self.card_pinky, 1, 1)

        main_layout.addWidget(finger_group)

        # Confidence Bar
        conf_box = QFrame()
        conf_box.setStyleSheet("background-color: #0c141f; border: 1px solid #1a2a3a; border-radius: 6px; padding: 6px 12px;")
        conf_layout = QHBoxLayout(conf_box)
        conf_title = QLabel("TRACKING CONFIDENCE:")
        conf_title.setStyleSheet("color: #627d98; font-size: 11px; font-weight: 600;")
        self.conf_bar = QProgressBar()
        self.conf_bar.setRange(0, 100)
        self.conf_bar.setValue(0)
        self.conf_bar.setTextVisible(True)
        self.conf_bar.setStyleSheet("""
            QProgressBar {
                background-color: #101c2a;
                border: 1px solid #243b53;
                border-radius: 4px;
                height: 16px;
                text-align: center;
                color: #ffffff;
                font-size: 10px;
                font-weight: bold;
            }
            QProgressBar::chunk {
                background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #0088cc, stop:1 #00e5ff);
                border-radius: 3px;
            }
        """)
        conf_layout.addWidget(conf_title)
        conf_layout.addWidget(self.conf_bar)

        main_layout.addWidget(conf_box)
        main_layout.addStretch()

    def update_diagnostics(self, data: TrackingData) -> None:
        """Refreshes the matrix with latest TrackingData."""
        if not data.hand_detected:
            self.card_hand.set_value("NO", False)
            self.card_gesture.set_value("NONE", False)
            self.card_pinch.set_value("NO", False)
            self.card_swipe.set_value("NONE", False)
            self.card_thumb.set_value("FOLDED", False)
            self.card_index.set_value("FOLDED", False)
            self.card_middle.set_value("FOLDED", False)
            self.card_ring.set_value("FOLDED", False)
            self.card_pinky.set_value("FOLDED", False)
            self.conf_bar.setValue(0)
            return

        self.card_hand.set_value("YES", True, "#00ffb4")
        self.card_gesture.set_value(data.active_gesture.value if data.active_gesture else "NONE", True)

        # Pinch
        is_pinched = data.active_gesture in (GestureType.PINCH, GestureType.DRAG)
        pinch_str = "YES (DRAG)" if data.active_gesture == GestureType.DRAG else ("YES" if is_pinched else "NO")
        self.card_pinch.set_value(pinch_str, is_pinched, "#00e5ff" if is_pinched else "#486581")

        # Swipe
        self.card_swipe.set_value(data.swipe_event or "NONE", bool(data.swipe_event))

        # Fingers
        fs = data.finger_status
        self.card_thumb.set_value("EXTENDED" if fs.thumb_extended else "FOLDED", fs.thumb_extended)
        self.card_index.set_value("EXTENDED" if fs.index_extended else "FOLDED", fs.index_extended)
        self.card_middle.set_value("EXTENDED" if fs.middle_extended else "FOLDED", fs.middle_extended)
        self.card_ring.set_value("EXTENDED" if fs.ring_extended else "FOLDED", fs.ring_extended)
        self.card_pinky.set_value("EXTENDED" if fs.pinky_extended else "FOLDED", fs.pinky_extended)

        # Confidence
        self.conf_bar.setValue(int(data.confidence * 100))
