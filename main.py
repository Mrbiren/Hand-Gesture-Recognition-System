"""
CryNet — Main Entry Point
Autonomous, offline-first, local-only hand-gesture control system.
"""

from __future__ import annotations
import ctypes
import logging
import os
import sys
from pathlib import Path

# Setup DPI awareness before Qt or Windows API calls
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

# Ensure base directory is in sys.path
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

# Create log directory and setup logging
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "crynet.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s]: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("CryNet")


def main() -> int:
    logger.info("=========================================")
    logger.info("Initializing CryNet Gesture Control System")
    logger.info("100% Offline | Local-Only MediaPipe Engine")
    logger.info("=========================================")

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QApplication

    from core.calibration import CalibrationManager
    from core.config_manager import ConfigManager
    from core.cursor_controller import CursorController
    from core.display_manager import DisplayManager
    from core.gesture_engine import GestureEngine
    from core.safety_controller import SafetyController
    from ui.main_window import CryNetMainWindow

    app = QApplication(sys.argv)
    app.setApplicationName("CryNet")
    app.setOrganizationName("CryNet")

    # Set default UI font
    font = QFont("Segoe UI", 9)
    app.setFont(font)

    # Initialize Core Architecture
    config_mgr = ConfigManager(base_dir=BASE_DIR)
    disp_mgr = DisplayManager()
    calib_mgr = CalibrationManager(config_manager=config_mgr)
    cursor_ctrl = CursorController()
    safety_ctrl = SafetyController()

    gesture_engine = GestureEngine(
        display_manager=disp_mgr,
        calibration_manager=calib_mgr,
        safety_controller=safety_ctrl,
        cursor_controller=cursor_ctrl,
    )
    # Apply saved settings to engine & cursor controller
    gesture_engine.update_settings(config_mgr.settings)

    # Instantiate MainWindow
    window = CryNetMainWindow(
        config_manager=config_mgr,
        display_manager=disp_mgr,
        calibration_manager=calib_mgr,
        safety_controller=safety_ctrl,
        cursor_controller=cursor_ctrl,
        gesture_engine=gesture_engine,
    )
    window.show()

    logger.info("CryNet UI loaded and ready. Engine in STANDBY.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
