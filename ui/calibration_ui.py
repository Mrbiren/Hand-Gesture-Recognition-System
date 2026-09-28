"""
CryNet Calibration Wizard UI
Interactive 4-step wizard modal guiding the user to calibrate camera-to-screen
interaction zone boundaries with live target display visualization.
"""

from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
)
from core.calibration import CalibrationManager


class CalibrationDialog(QDialog):
    """Futuristic 4-step calibration dialog."""

    calibration_finished = Signal()

    def __init__(self, calibration_manager: CalibrationManager, target_display_name: str, parent=None):
        super().__init__(parent)
        self.calib_mgr = calibration_manager
        self.target_display_name = target_display_name
        self.current_hand_pos = (0.5, 0.5)

        self.setWindowTitle("CryNet — Calibration Wizard")
        self.setFixedSize(520, 380)
        self.setStyleSheet("""
            QDialog {
                background-color: #0a111a;
                border: 1px solid #00e5ff;
            }
            QLabel {
                color: #e0f2fe;
            }
        """)

        self._init_ui()
        self.start_wizard()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header
        title = QLabel("CRYNET CALIBRATION WIZARD")
        title.setStyleSheet("color: #00e5ff; font-size: 16px; font-weight: bold; letter-spacing: 2px;")
        layout.addWidget(title)

        disp_label = QLabel(f"Target Display: <b style='color:#38bdf8;'>{self.target_display_name}</b>")
        disp_label.setStyleSheet("font-size: 12px; color: #94a3b8;")
        layout.addWidget(disp_label)

        # Step box
        self.step_frame = QFrame()
        self.step_frame.setStyleSheet("""
            QFrame {
                background-color: #0f172a;
                border: 1px solid #1e293b;
                border-radius: 8px;
                padding: 16px;
            }
        """)
        s_layout = QVBoxLayout(self.step_frame)
        s_layout.setSpacing(8)

        self.step_counter = QLabel("Step 1/4")
        self.step_counter.setStyleSheet("color: #38bdf8; font-size: 13px; font-weight: bold;")

        self.step_instruction = QLabel("Move your hand to the TOP LEFT corner of your comfortable reach.")
        self.step_instruction.setStyleSheet("color: #f1f5f9; font-size: 14px; font-weight: 500;")
        self.step_instruction.setWordWrap(True)

        self.coord_preview = QLabel("Live Sensor Coord: X=0.00, Y=0.00")
        self.coord_preview.setStyleSheet("color: #64748b; font-size: 11px; font-family: Consolas;")

        s_layout.addWidget(self.step_counter)
        s_layout.addWidget(self.step_instruction)
        s_layout.addWidget(self.coord_preview)

        layout.addWidget(self.step_frame)

        # Progress bar
        self.progress = QProgressBar()
        self.progress.setRange(0, 4)
        self.progress.setValue(1)
        self.progress.setTextVisible(False)
        self.progress.setStyleSheet("""
            QProgressBar {
                background-color: #1e293b;
                border-radius: 4px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #00e5ff;
                border-radius: 4px;
            }
        """)
        layout.addWidget(self.progress)

        layout.addStretch()

        # Action Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("CANCEL")
        self.btn_cancel.setStyleSheet("""
            QPushButton {
                background-color: #1e293b;
                color: #94a3b8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 8px 16px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #334155;
                color: #ffffff;
            }
        """)
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_confirm = QPushButton("CONFIRM [SPACE]")
        self.btn_confirm.setStyleSheet("""
            QPushButton {
                background-color: #0284c7;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 8px 24px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #00e5ff;
                color: #0a111a;
            }
        """)
        self.btn_confirm.clicked.connect(self.on_confirm_step)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_confirm)
        layout.addLayout(btn_layout)

    def start_wizard(self) -> None:
        step_id, instruction = self.calib_mgr.start_wizard(self.target_display_name)
        self.update_step_display(0, instruction)

    def update_hand_position(self, norm_x: float, norm_y: float) -> None:
        self.current_hand_pos = (norm_x, norm_y)
        self.coord_preview.setText(f"Live Sensor Coord: X={norm_x:.3f}, Y={norm_y:.3f}")

    def update_step_display(self, step_idx: int, instruction: str) -> None:
        self.progress.setValue(step_idx + 1)
        self.step_counter.setText(f"Step {step_idx + 1}/4")
        self.step_instruction.setText(instruction)

    def on_confirm_step(self) -> None:
        hx, hy = self.current_hand_pos
        is_done, next_step, next_instr = self.calib_mgr.record_step(hx, hy)
        if is_done:
            self.step_counter.setText("COMPLETED")
            self.step_instruction.setText("CALIBRATION COMPLETE!\nInteraction zone mapped and saved.")
            self.btn_confirm.setText("CLOSE")
            self.btn_confirm.clicked.disconnect()
            self.btn_confirm.clicked.connect(self.accept)
            self.calibration_finished.emit()
        else:
            self.update_step_display(self.calib_mgr.current_step_idx, next_instr)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space or event.key() == Qt.Key.Key_Return:
            self.on_confirm_step()
            event.accept()
        elif event.key() == Qt.Key.Key_Escape:
            self.reject()
            event.accept()
        else:
            super().keyPressEvent(event)
