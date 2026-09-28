"""
CryNet Main Application Window
Iron Man / JARVIS-inspired futuristic command center for local hand-gesture control.
100% offline, sleek dark tech aesthetics, multi-tab modular architecture.
"""

from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional
import numpy as np

from PySide6.QtCore import QPoint, QSize, Qt, Signal, Slot
from PySide6.QtGui import QColor, QFont, QIcon, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPlainTextEdit,
    QPushButton,
    QSlider,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from core.calibration import CalibrationManager
from core.camera_worker import CameraWorker
from core.config_manager import ConfigManager
from core.cursor_controller import CursorController
from core.display_manager import DisplayManager
from core.gesture_engine import GestureEngine
from core.safety_controller import SafetyController
from gestures.gesture_state import GestureType, TrackingData
from ui.calibration_ui import CalibrationDialog
from ui.hud import JarvisHUD
from ui.widgets.camera_view import CameraViewWidget
from ui.widgets.gesture_test_ui import GestureTestPanel

logger = logging.getLogger("CryNet.MainWindow")


class CryNetMainWindow(QMainWindow):
    """Futuristic desktop command center for CryNet."""

    def __init__(
        self,
        config_manager: ConfigManager,
        display_manager: DisplayManager,
        calibration_manager: CalibrationManager,
        safety_controller: SafetyController,
        cursor_controller: CursorController,
        gesture_engine: GestureEngine,
    ):
        super().__init__()
        self.config_mgr = config_manager
        self.disp_mgr = display_manager
        self.calib_mgr = calibration_manager
        self.safety_ctrl = safety_controller
        self.cursor_ctrl = cursor_controller
        self.gesture_engine = gesture_engine

        self.setWindowTitle("CryNet — Gesture Control System")
        self.resize(1120, 760)
        self.setMinimumSize(960, 640)

        # Background HUD overlay
        self.hud = JarvisHUD()
        if self.config_mgr.get("hud_enabled", True):
            self.hud.show()
            self.hud.move(40, 40)
        else:
            self.hud.hide()

        # Camera Worker Thread
        self.camera_worker = CameraWorker(self.gesture_engine, self)
        self.camera_worker.frame_ready.connect(self.on_frame_ready)
        self.camera_worker.camera_error.connect(self.on_camera_error)

        # Wire Safety callbacks
        self.safety_ctrl.on_status_change = self.on_safety_status_change
        self.safety_ctrl.on_toggle_enabled = self.on_safety_toggle
        self.safety_ctrl.on_emergency_stop = self.on_emergency_stop

        self._init_theme()
        self._init_ui()
        self._init_shortcuts()
        self._load_initial_values()

        # Start camera stream
        self.start_camera()

    def _init_theme(self) -> None:
        """Sets modern futuristic dark cybersecurity stylesheet."""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #070d14;
            }
            QWidget {
                color: #e2e8f0;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QTabWidget::pane {
                border: 1px solid #1a2a3a;
                background-color: #0b131e;
                border-radius: 6px;
            }
            QTabBar::tab {
                background: #0e1724;
                color: #7b93a4;
                padding: 10px 18px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 11px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QTabBar::tab:selected {
                background: #142233;
                color: #00e5ff;
                border-bottom: 2px solid #00e5ff;
            }
            QTabBar::tab:hover {
                color: #38bdf8;
            }
            QGroupBox {
                color: #829ab1;
                font-size: 11px;
                font-weight: bold;
                border: 1px solid #192736;
                border-radius: 6px;
                margin-top: 10px;
                padding-top: 14px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
            }
            QLabel {
                font-size: 12px;
            }
            QComboBox {
                background-color: #0e1724;
                border: 1px solid #243b53;
                border-radius: 4px;
                padding: 6px 12px;
                color: #00e5ff;
                font-weight: 500;
            }
            QComboBox QAbstractItemView {
                background-color: #0e1724;
                border: 1px solid #00e5ff;
                selection-background-color: #142233;
                selection-color: #00e5ff;
            }
            QSlider::groove:horizontal {
                height: 4px;
                background: #1e293b;
                border-radius: 2px;
            }
            QSlider::sub-page:horizontal {
                background: #00e5ff;
                border-radius: 2px;
            }
            QSlider::handle:horizontal {
                background: #ffffff;
                border: 1px solid #00e5ff;
                width: 14px;
                margin-top: -5px;
                margin-bottom: -5px;
                border-radius: 7px;
            }
            QCheckBox {
                spacing: 8px;
                font-size: 12px;
                color: #cbd5e1;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                background: #0e1724;
                border: 1px solid #334e68;
                border-radius: 3px;
            }
            QCheckBox::indicator:checked {
                background: #00e5ff;
                border-color: #00e5ff;
            }
            QPlainTextEdit {
                background-color: #05090e;
                border: 1px solid #1a2a3a;
                color: #38bdf8;
                font-family: Consolas, monospace;
                font-size: 11px;
                border-radius: 4px;
            }
        """)

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setContentsMargins(16, 16, 16, 16)
        root_layout.setSpacing(12)

        # 1. Top Header Banner
        header = self._create_header_banner()
        root_layout.addWidget(header)

        # 2. Main Content Tabs
        self.tabs = QTabWidget()
        self.tabs.addTab(self._create_dashboard_tab(), "DASHBOARD & VISION")
        self.tabs.addTab(self._create_diagnostics_tab(), "GESTURE MATRIX")
        self.tabs.addTab(self._create_control_tab(), "CONTROL & TUNING")
        self.tabs.addTab(self._create_display_tab(), "DISPLAYS & CALIBRATION")
        self.tabs.addTab(self._create_camera_tab(), "OPTICAL SENSORS")
        self.tabs.addTab(self._create_logs_tab(), "SYSTEM LOGS")

        root_layout.addWidget(self.tabs, stretch=1)

        # 3. Bottom Status Bar
        bottom_bar = self._create_bottom_bar()
        root_layout.addWidget(bottom_bar)

    def _create_header_banner(self) -> QWidget:
        banner = QFrame()
        banner.setStyleSheet("""
            QFrame {
                background-color: #0a111a;
                border: 1px solid #162434;
                border-radius: 6px;
                padding: 10px 16px;
            }
        """)
        layout = QHBoxLayout(banner)
        layout.setContentsMargins(8, 4, 8, 4)

        # Title & Subtitle
        v_title = QVBoxLayout()
        v_title.setSpacing(2)

        title_lbl = QLabel("CRYNET")
        title_lbl.setStyleSheet("color: #00e5ff; font-size: 20px; font-weight: 900; letter-spacing: 4px;")
        sub_lbl = QLabel("AUTONOMOUS OFFLINE GESTURE CONTROL SYSTEM")
        sub_lbl.setStyleSheet("color: #627d98; font-size: 10px; font-weight: 600; letter-spacing: 1.5px;")

        v_title.addWidget(title_lbl)
        v_title.addWidget(sub_lbl)
        layout.addLayout(v_title)

        layout.addStretch()

        # Mode Badge
        self.mode_badge = QLabel("HOME MODE [1 DISPLAY]")
        self.mode_badge.setStyleSheet("""
            background-color: #0f2438;
            color: #38bdf8;
            border: 1px solid #0284c7;
            border-radius: 4px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
        """)
        layout.addWidget(self.mode_badge)

        # Status Badge
        self.status_badge = QLabel("STATUS: STANDBY")
        self.status_badge.setStyleSheet("""
            background-color: #1e293b;
            color: #94a3b8;
            border: 1px solid #334155;
            border-radius: 4px;
            padding: 6px 14px;
            font-size: 11px;
            font-weight: bold;
            letter-spacing: 1px;
        """)
        layout.addWidget(self.status_badge)

        # Quick Toggle Buttons
        self.btn_toggle = QPushButton("START [F8]")
        self.btn_toggle.setStyleSheet("""
            QPushButton {
                background-color: #00b4d8;
                color: #070d14;
                border: 1px solid #00e5ff;
                border-radius: 4px;
                padding: 7px 20px;
                font-size: 11px;
                font-weight: 900;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #00e5ff;
            }
        """)
        self.btn_toggle.clicked.connect(self.on_btn_toggle_clicked)
        layout.addWidget(self.btn_toggle)

        return banner

    def _create_dashboard_tab(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(14)

        # Left: Live Camera View
        v_left = QVBoxLayout()
        v_left.setSpacing(8)

        v_head = QHBoxLayout()
        v_head_lbl = QLabel("LIVE OPTICAL FEED")
        v_head_lbl.setStyleSheet("color: #00e5ff; font-size: 11px; font-weight: bold; letter-spacing: 1px;")
        v_head.addWidget(v_head_lbl)
        v_head.addStretch()

        self.lbl_fps_live = QLabel("0 FPS")
        self.lbl_fps_live.setStyleSheet("color: #38bdf8; font-size: 11px; font-family: Consolas;")
        v_head.addWidget(self.lbl_fps_live)

        v_left.addLayout(v_head)

        self.camera_view = CameraViewWidget()
        v_left.addWidget(self.camera_view, stretch=1)

        layout.addLayout(v_left, stretch=3)

        # Right: Quick Controls & Gesture Legend
        v_right = QVBoxLayout()
        v_right.setSpacing(12)

        # Telemetry Summary
        tele_box = QGroupBox("SYSTEM TELEMETRY")
        t_layout = QGridLayout(tele_box)
        t_layout.setSpacing(8)

        self.lbl_t_hand = QLabel("NONE")
        self.lbl_t_hand.setStyleSheet("color: #94a3b8; font-weight: bold; font-family: Consolas;")
        self.lbl_t_gesture = QLabel("NONE")
        self.lbl_t_gesture.setStyleSheet("color: #00e5ff; font-weight: bold; font-family: Consolas;")
        self.lbl_t_target = QLabel("Display 1")
        self.lbl_t_target.setStyleSheet("color: #38bdf8; font-weight: bold; font-family: Consolas;")

        t_layout.addWidget(QLabel("HAND:"), 0, 0)
        t_layout.addWidget(self.lbl_t_hand, 0, 1)
        t_layout.addWidget(QLabel("GESTURE:"), 1, 0)
        t_layout.addWidget(self.lbl_t_gesture, 1, 1)
        t_layout.addWidget(QLabel("TARGET:"), 2, 0)
        t_layout.addWidget(self.lbl_t_target, 2, 1)

        v_right.addWidget(tele_box)

        # Gesture Reference Legend
        legend_box = QGroupBox("GESTURE MAPPINGS")
        l_layout = QVBoxLayout(legend_box)
        l_layout.setSpacing(6)

        mappings = [
            ("Index Finger", "Virtual Cursor"),
            ("Pinch (Thumb+Index)", "Left Click"),
            ("Pinch + Movement", "Drag & Drop"),
            ("Two-Finger (Index+Mid)", "Vertical Scroll"),
            ("Open Palm", "Pause Control"),
            ("Fist", "Neutral Posture"),
            ("Swipe Left / Right", "Alt + Left / Right"),
        ]
        for g_input, g_action in mappings:
            row = QHBoxLayout()
            lbl_i = QLabel(g_input)
            lbl_i.setStyleSheet("color: #94a3b8; font-size: 11px;")
            lbl_a = QLabel(f"→  {g_action}")
            lbl_a.setStyleSheet("color: #38bdf8; font-size: 11px; font-weight: 600;")
            row.addWidget(lbl_i)
            row.addStretch()
            row.addWidget(lbl_a)
            l_layout.addLayout(row)

        v_right.addWidget(legend_box)

        # Action Buttons
        btn_calib = QPushButton("CALIBRATE WORKSPACE")
        btn_calib.setStyleSheet("""
            QPushButton {
                background-color: #0f2438;
                color: #00e5ff;
                border: 1px solid #00b4d8;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #00b4d8;
                color: #070d14;
            }
        """)
        btn_calib.clicked.connect(self.on_calibrate_clicked)
        v_right.addWidget(btn_calib)

        btn_hud = QPushButton("TOGGLE HUD [F7]")
        btn_hud.setStyleSheet("""
            QPushButton {
                background-color: #0f172a;
                color: #38bdf8;
                border: 1px solid #334155;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1e293b;
                color: #ffffff;
            }
        """)
        btn_hud.clicked.connect(self.toggle_hud)
        v_right.addWidget(btn_hud)

        v_right.addStretch()
        layout.addLayout(v_right, stretch=2)

        return widget

    def _create_diagnostics_tab(self) -> QWidget:
        self.diag_panel = GestureTestPanel()
        return self.diag_panel

    def _create_control_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("MOTION TRACKING & GESTURE TUNING")
        title.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)

        grid = QGridLayout()
        grid.setSpacing(14)

        # 1. Sensitivity
        self.slider_sens, self.lbl_sens = self._make_slider(
            "Cursor Sensitivity", 5, 30, int(self.config_mgr.get("sensitivity", 1.2) * 10), 10.0
        )
        self.slider_sens.valueChanged.connect(self._on_settings_slider_changed)

        # 2. Smoothing
        self.slider_smooth, self.lbl_smooth = self._make_slider(
            "Smoothing (Jitter Reduction)", 10, 95, int(self.config_mgr.get("smoothing", 0.65) * 100), 100.0
        )
        self.slider_smooth.valueChanged.connect(self._on_settings_slider_changed)

        # 3. Dead Zone
        self.slider_dead, self.lbl_dead = self._make_slider(
            "Dead Zone (Tremor Filter)", 1, 30, int(self.config_mgr.get("dead_zone", 0.005) * 1000), 1000.0
        )
        self.slider_dead.valueChanged.connect(self._on_settings_slider_changed)

        # 4. Acceleration
        self.slider_acc, self.lbl_acc = self._make_slider(
            "Cursor Acceleration", 10, 30, int(self.config_mgr.get("acceleration", 1.3) * 10), 10.0
        )
        self.slider_acc.valueChanged.connect(self._on_settings_slider_changed)

        # 5. Pinch Threshold
        self.slider_pinch, self.lbl_pinch = self._make_slider(
            "Pinch Threshold", 20, 90, int(self.config_mgr.get("pinch_threshold", 0.045) * 1000), 1000.0
        )
        self.slider_pinch.valueChanged.connect(self._on_settings_slider_changed)

        # 6. Scroll Sensitivity
        self.slider_scroll, self.lbl_scroll = self._make_slider(
            "Scroll Sensitivity", 5, 30, int(self.config_mgr.get("scroll_sensitivity", 1.0) * 10), 10.0
        )
        self.slider_scroll.valueChanged.connect(self._on_settings_slider_changed)

        # 7. Swipe Velocity
        self.slider_swipe, self.lbl_swipe = self._make_slider(
            "Swipe Velocity Threshold", 3, 15, int(self.config_mgr.get("swipe_velocity_threshold", 0.6) * 10), 10.0
        )
        self.slider_swipe.valueChanged.connect(self._on_settings_slider_changed)

        sliders = [
            ("Cursor Sensitivity", self.slider_sens, self.lbl_sens),
            ("Smoothing", self.slider_smooth, self.lbl_smooth),
            ("Dead Zone", self.slider_dead, self.lbl_dead),
            ("Acceleration", self.slider_acc, self.lbl_acc),
            ("Pinch Threshold", self.slider_pinch, self.lbl_pinch),
            ("Scroll Sensitivity", self.slider_scroll, self.lbl_scroll),
            ("Swipe Velocity", self.slider_swipe, self.lbl_swipe),
        ]

        for idx, (name, sld, lbl) in enumerate(sliders):
            grid.addWidget(QLabel(name), idx, 0)
            grid.addWidget(sld, idx, 1)
            grid.addWidget(lbl, idx, 2)

        layout.addLayout(grid)
        layout.addStretch()

        return widget

    def _make_slider(self, name: str, min_v: int, max_v: int, cur_v: int, divisor: float):
        slider = QSlider(Qt.Orientation.Horizontal)
        slider.setRange(min_v, max_v)
        slider.setValue(cur_v)
        lbl = QLabel(f"{cur_v / divisor:.2f}")
        lbl.setStyleSheet("color: #00e5ff; font-family: Consolas; font-weight: bold; min-width: 45px;")
        slider.valueChanged.connect(lambda v: lbl.setText(f"{v / divisor:.2f}"))
        return slider, lbl

    def _on_settings_slider_changed(self) -> None:
        self.config_mgr.set("sensitivity", self.slider_sens.value() / 10.0, save=False)
        self.config_mgr.set("smoothing", self.slider_smooth.value() / 100.0, save=False)
        self.config_mgr.set("dead_zone", self.slider_dead.value() / 1000.0, save=False)
        self.config_mgr.set("acceleration", self.slider_acc.value() / 10.0, save=False)
        self.config_mgr.set("pinch_threshold", self.slider_pinch.value() / 1000.0, save=False)
        self.config_mgr.set("scroll_sensitivity", self.slider_scroll.value() / 10.0, save=False)
        self.config_mgr.set("swipe_velocity_threshold", self.slider_swipe.value() / 10.0, save=True)

        self.gesture_engine.update_settings(self.config_mgr.settings)

    def _create_display_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("MULTI-MONITOR CONFIGURATION & TARGET ROUTING")
        title.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)

        box = QGroupBox("TARGET DISPLAY SELECTION")
        b_layout = QVBoxLayout(box)
        b_layout.setSpacing(12)

        row_sel = QHBoxLayout()
        row_sel.addWidget(QLabel("Target Display:"))
        self.combo_displays = QComboBox()
        self.combo_displays.currentIndexChanged.connect(self.on_target_display_changed)
        row_sel.addWidget(self.combo_displays, stretch=1)

        btn_refresh = QPushButton("REFRESH MONITORS")
        btn_refresh.setStyleSheet("background-color: #142233; color: #38bdf8; border: 1px solid #00b4d8; padding: 6px 12px; border-radius: 4px;")
        btn_refresh.clicked.connect(self.refresh_display_list)
        row_sel.addWidget(btn_refresh)

        b_layout.addLayout(row_sel)

        self.lbl_disp_details = QLabel()
        self.lbl_disp_details.setStyleSheet("color: #94a3b8; font-family: Consolas; font-size: 11px;")
        b_layout.addWidget(self.lbl_disp_details)

        layout.addWidget(box)

        # Calibration Box
        cal_box = QGroupBox("INTERACTION ZONE CALIBRATION")
        c_layout = QVBoxLayout(cal_box)
        c_layout.setSpacing(10)

        c_info = QLabel(
            "Calibrate your physical interaction space so you can effortlessly reach all screen corners "
            "without reaching to the physical limits of your camera lens."
        )
        c_info.setWordWrap(True)
        c_info.setStyleSheet("color: #cbd5e1; font-size: 11px;")
        c_layout.addWidget(c_info)

        btn_run_calib = QPushButton("LAUNCH 4-CORNER CALIBRATION WIZARD")
        btn_run_calib.setStyleSheet("""
            QPushButton {
                background-color: #0369a1;
                color: #ffffff;
                border: 1px solid #38bdf8;
                border-radius: 4px;
                padding: 10px;
                font-weight: bold;
                letter-spacing: 1px;
            }
            QPushButton:hover {
                background-color: #0284c7;
            }
        """)
        btn_run_calib.clicked.connect(self.on_calibrate_clicked)
        c_layout.addWidget(btn_run_calib)

        layout.addWidget(cal_box)
        layout.addStretch()

        return widget

    def _create_camera_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        title = QLabel("OPTICAL SENSOR CONFIGURATION")
        title.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 1.5px;")
        layout.addWidget(title)

        box = QGroupBox("WEBCAM HARDWARE SETTINGS")
        b_layout = QGridLayout(box)
        b_layout.setSpacing(12)

        # Camera selection
        b_layout.addWidget(QLabel("Active Camera:"), 0, 0)
        self.combo_cameras = QComboBox()
        self.combo_cameras.addItems(["Camera 0 (Integrated / Default)", "Camera 1", "Camera 2"])
        b_layout.addWidget(self.combo_cameras, 0, 1)

        # Resolution
        b_layout.addWidget(QLabel("Resolution:"), 1, 0)
        self.combo_res = QComboBox()
        self.combo_res.addItems(["640 x 480 (Recommended - Low Latency)", "1280 x 720 (HD)"])
        b_layout.addWidget(self.combo_res, 1, 1)

        # FPS
        b_layout.addWidget(QLabel("Target Frame Rate:"), 2, 0)
        self.combo_fps = QComboBox()
        self.combo_fps.addItems(["30 FPS", "60 FPS"])
        b_layout.addWidget(self.combo_fps, 2, 1)

        layout.addWidget(box)

        # Feature Toggles
        tog_box = QGroupBox("PREVIEW & VISUALIZATION")
        t_layout = QVBoxLayout(tog_box)
        t_layout.setSpacing(10)

        self.chk_mirror = QCheckBox("Mirror Camera Feed (Intuitive Left/Right Control)")
        self.chk_mirror.setChecked(self.config_mgr.get("camera_mirror", True))
        self.chk_mirror.toggled.connect(self.on_camera_toggles_changed)
        t_layout.addWidget(self.chk_mirror)

        self.chk_preview = QCheckBox("Enable Camera Live Preview (Disable to minimize CPU usage)")
        self.chk_preview.setChecked(self.config_mgr.get("camera_preview_enabled", True))
        self.chk_preview.toggled.connect(self.on_camera_toggles_changed)
        t_layout.addWidget(self.chk_preview)

        self.chk_debug = QCheckBox("Show HUD Hand Skeleton & Reticle Visualization")
        self.chk_debug.setChecked(self.config_mgr.get("debug_visualization", True))
        self.chk_debug.toggled.connect(self.on_camera_toggles_changed)
        t_layout.addWidget(self.chk_debug)

        layout.addWidget(tog_box)
        layout.addStretch()

        return widget

    def _create_logs_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        h_bar = QHBoxLayout()
        h_title = QLabel("SYSTEM & ENGINE EVENT LOG")
        h_title.setStyleSheet("color: #00e5ff; font-size: 13px; font-weight: bold; letter-spacing: 1.5px;")
        h_bar.addWidget(h_title)
        h_bar.addStretch()

        btn_clear = QPushButton("CLEAR LOGS")
        btn_clear.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; padding: 6px 14px; border-radius: 4px;")
        btn_clear.clicked.connect(self.clear_logs)
        h_bar.addWidget(btn_clear)

        layout.addLayout(h_bar)

        self.log_text = QPlainTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        return widget

    def _create_bottom_bar(self) -> QWidget:
        bar = QFrame()
        bar.setStyleSheet("background-color: #0a111a; border-top: 1px solid #162434; padding: 4px 8px;")
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(8, 4, 8, 4)

        hotkey_lbl = QLabel("HOTKEYS: [F8] Toggle Standby/Online  |  [ESC] Emergency Stop  |  [F7] Toggle HUD")
        hotkey_lbl.setStyleSheet("color: #64748b; font-size: 10px; font-weight: 600; font-family: Consolas;")
        layout.addWidget(hotkey_lbl)

        layout.addStretch()

        offline_lbl = QLabel("100% OFFLINE LOCAL RUNTIME")
        offline_lbl.setStyleSheet("color: #00e5ff; font-size: 10px; font-weight: bold; letter-spacing: 1px;")
        layout.addWidget(offline_lbl)

        return bar

    def _init_shortcuts(self) -> None:
        """PySide6 application shortcuts."""
        self.shortcut_f8 = QShortcut(QKeySequence("F8"), self)
        self.shortcut_f8.activated.connect(self.safety_ctrl.toggle_enabled)

        self.shortcut_esc = QShortcut(QKeySequence("Escape"), self)
        self.shortcut_esc.activated.connect(self.safety_ctrl.trigger_emergency_stop)

        self.shortcut_f7 = QShortcut(QKeySequence("F7"), self)
        self.shortcut_f7.activated.connect(self.toggle_hud)

    def _load_initial_values(self) -> None:
        self.refresh_display_list()

    def refresh_display_list(self) -> None:
        """Detects all physical displays via Windows APIs and updates UI."""
        displays = self.disp_mgr.refresh_displays()
        self.combo_displays.blockSignals(True)
        self.combo_displays.clear()

        for d in displays:
            self.combo_displays.addItem(d.label, d.index)

        self.combo_displays.setCurrentIndex(self.disp_mgr.target_display_index)
        self.combo_displays.blockSignals(False)

        # Update mode badge
        if len(displays) == 1:
            self.mode_badge.setText("HOME MODE [1 DISPLAY]")
            self.mode_badge.setStyleSheet("background-color: #0f2438; color: #38bdf8; border: 1px solid #0284c7; border-radius: 4px; padding: 6px 14px; font-weight: bold;")
        else:
            self.mode_badge.setText(f"OFFICE MODE [{len(displays)} DISPLAYS]")
            self.mode_badge.setStyleSheet("background-color: #042f2e; color: #2dd4bf; border: 1px solid #0d9488; border-radius: 4px; padding: 6px 14px; font-weight: bold;")

        target = self.disp_mgr.get_target_display()
        if target:
            self.lbl_t_target.setText(target.name)
            self.lbl_disp_details.setText(
                f"Bounds: Left={target.left}, Top={target.top}, Right={target.right}, Bottom={target.bottom} | Device: {target.device_name}"
            )

    def on_target_display_changed(self, index: int) -> None:
        if index >= 0:
            self.disp_mgr.set_target_display(index)
            self.config_mgr.set("target_display_index", index)
            target = self.disp_mgr.get_target_display()
            if target:
                self.lbl_t_target.setText(target.name)
                self.calib_mgr.load_active_calibration(target.name)

    def on_camera_toggles_changed(self) -> None:
        mirror = self.chk_mirror.isChecked()
        preview = self.chk_preview.isChecked()
        debug = self.chk_debug.isChecked()

        self.config_mgr.set("camera_mirror", mirror, save=False)
        self.config_mgr.set("camera_preview_enabled", preview, save=False)
        self.config_mgr.set("debug_visualization", debug, save=True)

        self.camera_worker.mirror = mirror
        self.camera_worker.preview_enabled = preview
        self.camera_worker.debug_visualization = debug

    def start_camera(self) -> None:
        cam_idx = self.config_mgr.get("camera_index", 0)
        w = self.config_mgr.get("camera_width", 640)
        h = self.config_mgr.get("camera_height", 480)
        fps = self.config_mgr.get("camera_fps", 30)
        mirror = self.config_mgr.get("camera_mirror", True)
        prev = self.config_mgr.get("camera_preview_enabled", True)
        debug = self.config_mgr.get("debug_visualization", True)

        self.camera_worker.configure(cam_idx, w, h, fps, mirror, prev, debug)
        self.camera_worker.start()

    def toggle_hud(self) -> None:
        if self.hud.isVisible():
            self.hud.hide()
            self.config_mgr.set("hud_enabled", False)
        else:
            self.hud.show()
            self.config_mgr.set("hud_enabled", True)

    def on_btn_toggle_clicked(self) -> None:
        self.safety_ctrl.toggle_enabled()

    def on_safety_toggle(self, is_enabled: bool) -> None:
        if is_enabled:
            self.btn_toggle.setText("STOP [F8]")
            self.btn_toggle.setStyleSheet("background-color: #ef4444; color: #ffffff; border: 1px solid #f87171; border-radius: 4px; padding: 7px 20px; font-weight: 900;")
            self.status_badge.setText("STATUS: ONLINE")
            self.status_badge.setStyleSheet("background-color: #064e3b; color: #34d399; border: 1px solid #059669; border-radius: 4px; padding: 6px 14px; font-weight: bold;")
        else:
            self.btn_toggle.setText("START [F8]")
            self.btn_toggle.setStyleSheet("background-color: #00b4d8; color: #070d14; border: 1px solid #00e5ff; border-radius: 4px; padding: 7px 20px; font-weight: 900;")
            self.status_badge.setText("STATUS: STANDBY")
            self.status_badge.setStyleSheet("background-color: #1e293b; color: #94a3b8; border: 1px solid #334155; border-radius: 4px; padding: 6px 14px; font-weight: bold;")

    def on_emergency_stop(self) -> None:
        self.cursor_ctrl.reset_state()
        self.on_safety_toggle(False)

    def on_safety_status_change(self, msg: str) -> None:
        self.status_badge.setText(msg)

    def on_calibrate_clicked(self) -> None:
        target = self.disp_mgr.get_target_display()
        name = target.name if target else "Display 1"
        dlg = CalibrationDialog(self.calib_mgr, name, self)
        dlg.exec()

    def on_frame_ready(self, frame: Optional[np.ndarray], data: TrackingData) -> None:
        """Called on every processed frame from the CameraWorker."""
        # 1. Update Camera Viewport
        if frame is not None:
            self.camera_view.update_frame(frame, data.fps, data.status_message)

        # 2. Update FPS counter
        self.lbl_fps_live.setText(f"{data.fps:.0f} FPS")

        # 3. Update Telemetry Summary
        self.lbl_t_hand.setText("DETECTED" if data.hand_detected else "NONE")
        self.lbl_t_hand.setStyleSheet(
            f"color: {'#00ffb4' if data.hand_detected else '#94a3b8'}; font-weight: bold; font-family: Consolas;"
        )
        self.lbl_t_gesture.setText(data.active_gesture.value if data.active_gesture else "NONE")

        # 4. Update HUD overlay
        if self.hud.isVisible():
            self.hud.update_tracking(data, self.safety_ctrl.is_enabled)

        # 5. Update Testing Matrix Tab
        self.diag_panel.update_diagnostics(data)

    def on_camera_error(self, err_msg: str) -> None:
        self.camera_view.clear_view("CAMERA ERROR")
        self.log_message(f"CAMERA ERROR: {err_msg}")

    def log_message(self, text: str) -> None:
        self.log_text.appendPlainText(text)

    def clear_logs(self) -> None:
        self.log_text.clear()
        # Also truncate crynet.log
        log_file = Path(__file__).resolve().parent.parent / "logs" / "crynet.log"
        if log_file.exists():
            try:
                with open(log_file, "w", encoding="utf-8") as f:
                    f.write("")
            except Exception:
                pass

    def closeEvent(self, event) -> None:
        """Clean shutdown."""
        self.camera_worker.stop()
        self.safety_ctrl.stop()
        if self.hud:
            self.hud.close()
        event.accept()
