"""
CryNet JARVIS HUD Overlay
A lightweight, semi-transparent, always-on-top heads-up display showing
real-time gesture state, FPS, confidence, and target monitor.
Toggleable with F7.
"""

from __future__ import annotations
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget
from gestures.gesture_state import GestureType, TrackingData


class JarvisHUD(QWidget):
    """Transparent futuristic HUD overlay widget."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self.resize(360, 240)
        self._drag_pos = QPoint()

        # HUD State
        self.status: str = "ONLINE"
        self.hand_detected: bool = False
        self.gesture_name: str = "NONE"
        self.target_display: str = "Display 1"
        self.fps: float = 0.0
        self.confidence: float = 0.0
        self.is_active: bool = False
        self.status_message: str = ""

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if event.buttons() == Qt.MouseButton.LeftButton and not self._drag_pos.isNull():
            self.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def update_tracking(self, data: TrackingData, is_system_enabled: bool) -> None:
        """Updates internal telemetry values and refreshes the overlay."""
        self.is_active = is_system_enabled
        self.hand_detected = data.hand_detected
        self.gesture_name = data.active_gesture.value if data.active_gesture else "NONE"
        self.target_display = data.target_display_name
        self.fps = data.fps
        self.confidence = data.confidence * 100.0
        self.status_message = data.status_message

        if not self.is_active:
            self.status = "STANDBY"
        elif "LOCKING" in data.status_message:
            self.status = data.status_message
        elif data.status_message == "LOCK CANCELLED":
            self.status = "LOCK CANCELLED"
        elif data.is_paused:
            self.status = "PAUSED"
        else:
            self.status = "ONLINE"

        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)

        # Background: Translucent obsidian cyan gradient
        bg_color = QColor(10, 16, 26, 220)
        painter.setBrush(bg_color)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 8, 8)

        # Glowing Border
        is_locking = "LOCKING" in self.status or self.gesture_name == "LOCK_SCREEN"
        is_cancelled = self.status == "LOCK CANCELLED"

        if is_locking:
            border_color = QColor(255, 60, 60, 220)
        elif is_cancelled:
            border_color = QColor(255, 170, 0, 200)
        elif self.is_active:
            border_color = QColor(0, 229, 255, 140)
        else:
            border_color = QColor(100, 120, 140, 100)

        painter.setPen(QPen(border_color, 1.4 if (is_locking or is_cancelled) else 1.2))
        painter.drawRoundedRect(rect, 8, 8)

        # Futuristic Corner Tech Accents
        acc_len = 14
        acc_color = QColor(255, 70, 70, 240) if is_locking else (QColor(255, 180, 0, 240) if is_cancelled else QColor(0, 240, 255, 230))
        acc_pen = QPen(acc_color, 2.0)
        painter.setPen(acc_pen)

        # Top-Left
        painter.drawLine(rect.left(), rect.top(), rect.left() + acc_len, rect.top())
        painter.drawLine(rect.left(), rect.top(), rect.left(), rect.top() + acc_len)
        # Top-Right
        painter.drawLine(rect.right(), rect.top(), rect.right() - acc_len, rect.top())
        painter.drawLine(rect.right(), rect.top(), rect.right(), rect.top() + acc_len)
        # Bottom-Left
        painter.drawLine(rect.left(), rect.bottom(), rect.left() + acc_len, rect.bottom())
        painter.drawLine(rect.left(), rect.bottom(), rect.left(), rect.bottom() - acc_len)
        # Bottom-Right
        painter.drawLine(rect.right(), rect.bottom(), rect.right() - acc_len, rect.bottom())
        painter.drawLine(rect.right(), rect.bottom(), rect.right(), rect.bottom() - acc_len)

        # Header Title: CRYNET
        title_font = QFont("Segoe UI", 12, QFont.Bold)
        title_font.setLetterSpacing(QFont.AbsoluteSpacing, 3)
        painter.setFont(title_font)
        painter.setPen(acc_color)
        painter.drawText(
            QRect(rect.left(), rect.top() + 8, rect.width(), 24),
            Qt.AlignmentFlag.AlignHCenter,
            "CRYNET TACTICAL HUD",
        )

        # Divider line
        painter.setPen(QPen(QColor(0, 180, 216, 70), 1))
        painter.drawLine(rect.left() + 20, rect.top() + 36, rect.right() - 20, rect.top() + 36)

        # Content Items
        body_font = QFont("Consolas", 10, QFont.DemiBold)
        painter.setFont(body_font)

        y_start = rect.top() + 48
        line_height = 24

        status_color = (
            QColor(255, 70, 70) if is_locking
            else (QColor(255, 180, 0) if is_cancelled
            else (QColor(0, 255, 180) if self.status == "ONLINE"
            else (QColor(255, 180, 0) if self.status == "PAUSED"
            else QColor(160, 180, 200))))
        )

        gesture_color = (
            QColor(255, 60, 60) if self.gesture_name == "LOCK_SCREEN"
            else (QColor(0, 240, 255) if self.gesture_name != "NONE"
            else QColor(180, 190, 200))
        )

        rows = [
            ("STATUS:", self.status, status_color),
            ("HAND:", "DETECTED" if self.hand_detected else "NONE", QColor(0, 229, 255) if self.hand_detected else QColor(140, 150, 160)),
            ("GESTURE:", self.gesture_name, gesture_color),
            ("TARGET:", self.target_display, QColor(180, 220, 255)),
            ("FPS / CONF:", f"{self.fps:.0f} FPS  |  {self.confidence:.0f}%", QColor(0, 229, 255, 200)),
        ]

        label_x = rect.left() + 24
        val_x = rect.left() + 130

        for idx, (label, val, color) in enumerate(rows):
            cy = y_start + (idx * line_height)
            painter.setPen(QColor(130, 160, 190, 200))
            painter.drawText(label_x, cy, label)

            painter.setPen(color)
            painter.drawText(val_x, cy, val)

        # Dedicated Lock Countdown / Cancellation Banner
        if is_locking or is_cancelled:
            banner_rect = QRect(rect.left() + 16, rect.bottom() - 36, rect.width() - 32, 28)
            banner_bg = QColor(255, 40, 40, 50) if is_locking else QColor(255, 160, 0, 45)
            banner_border = QColor(255, 70, 70, 200) if is_locking else QColor(255, 170, 0, 190)

            painter.setBrush(banner_bg)
            painter.setPen(QPen(banner_border, 1.2))
            painter.drawRoundedRect(banner_rect, 5, 5)

            banner_font = QFont("Consolas", 10, QFont.Bold)
            banner_font.setLetterSpacing(QFont.AbsoluteSpacing, 1)
            painter.setFont(banner_font)
            painter.setPen(QColor(255, 255, 255) if is_locking else QColor(255, 220, 120))
            banner_text = self.status if is_locking else "LOCK CANCELLED"
            painter.drawText(banner_rect, Qt.AlignmentFlag.AlignCenter, banner_text)
