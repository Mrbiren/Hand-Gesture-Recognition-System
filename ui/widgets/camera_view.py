"""
CryNet Camera View Widget
High-performance PySide6 video viewport rendering OpenCV frames with
subtle sci-fi HUD gridlines, targeting reticle, and aspect ratio retention.
"""

from __future__ import annotations
import cv2
import numpy as np
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class CameraViewWidget(QWidget):
    """Renders video stream with a futuristic JARVIS HUD aesthetic."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 320)
        self._pixmap: QPixmap = QPixmap()
        self.hud_grid: bool = True
        self.status_text: str = "CAMERA STANDBY"
        self.fps: float = 0.0

    def update_frame(self, frame_bgr: np.ndarray, fps: float = 0.0, status: str = "") -> None:
        """Converts BGR OpenCV frame to QPixmap and triggers repaint."""
        if frame_bgr is None:
            return

        self.fps = fps
        if status:
            self.status_text = status

        h, w, c = frame_bgr.shape
        bytes_per_line = c * w
        # OpenCV BGR to RGB
        rgb_frame = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        q_img = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
        self._pixmap = QPixmap.fromImage(q_img)
        self.update()

    def clear_view(self, status: str = "OFFLINE") -> None:
        self._pixmap = QPixmap()
        self.status_text = status
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        # Background: Deep tech dark
        painter.fillRect(self.rect(), QColor(10, 14, 20))

        if not self._pixmap.isNull():
            # Scale maintaining aspect ratio
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.FastTransformation,
            )
            x = (self.width() - scaled.width()) // 2
            y = (self.height() - scaled.height()) // 2
            painter.drawPixmap(x, y, scaled)

            # Draw HUD corner brackets on video rect
            pen_cyan = QPen(QColor(0, 229, 255, 180), 1.5)
            painter.setPen(pen_cyan)
            blen = 16
            # Top-left
            painter.drawLine(x, y, x + blen, y)
            painter.drawLine(x, y, x, y + blen)
            # Top-right
            painter.drawLine(x + scaled.width(), y, x + scaled.width() - blen, y)
            painter.drawLine(x + scaled.width(), y, x + scaled.width(), y + blen)
            # Bottom-left
            painter.drawLine(x, y + scaled.height(), x + blen, y + scaled.height())
            painter.drawLine(x, y + scaled.height(), x, y + scaled.height() - blen)
            # Bottom-right
            painter.drawLine(x + scaled.width(), y + scaled.height(), x + scaled.width() - blen, y + scaled.height())
            painter.drawLine(x + scaled.width(), y + scaled.height(), x + scaled.width(), y + scaled.height() - blen)
        else:
            # Standby graphic
            pen = QPen(QColor(0, 180, 216, 80), 1, Qt.DashLine)
            painter.setPen(pen)
            cx, cy = self.width() // 2, self.height() // 2
            painter.drawEllipse(QPoint(cx, cy), 60, 60)
            painter.drawEllipse(QPoint(cx, cy), 80, 80)
            painter.drawLine(cx - 95, cy, cx + 95, cy)
            painter.drawLine(cx, cy - 95, cx, cy + 95)

            font = QFont("Segoe UI", 11, QFont.Bold)
            painter.setFont(font)
            painter.setPen(QColor(0, 229, 255, 200))
            painter.drawText(
                self.rect(),
                Qt.AlignmentFlag.AlignCenter,
                f"CRYNET OPTICAL SENSOR\n[{self.status_text}]",
            )

        # Subtle outer viewport border
        border_pen = QPen(QColor(0, 180, 216, 120), 1)
        painter.setPen(border_pen)
        painter.drawRect(0, 0, self.width() - 1, self.height() - 1)
