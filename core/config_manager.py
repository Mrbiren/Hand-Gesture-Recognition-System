"""
CryNet Configuration Manager
Safely loads, validates, and persists user settings and calibration data.
Offline-only; falls back to defaults on corruption.
"""

from __future__ import annotations
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger("CryNet.Config")

DEFAULT_SETTINGS: Dict[str, Any] = {
    "camera_index": 0,
    "camera_width": 640,
    "camera_height": 480,
    "camera_fps": 30,
    "camera_mirror": True,
    "target_display_index": 0,
    "sensitivity": 1.2,
    "smoothing": 0.65,
    "dead_zone": 0.005,
    "acceleration": 1.3,
    "pinch_threshold": 0.045,
    "drag_distance_threshold": 0.02,
    "scroll_sensitivity": 1.0,
    "swipe_velocity_threshold": 0.6,
    "swipe_distance_threshold": 0.25,
    "hud_enabled": True,
    "debug_visualization": True,
    "camera_preview_enabled": True,
    "start_with_windows": False,
    "emergency_key_f8": True,
    "emergency_key_esc": True
}


class ConfigManager:
    """Manages application settings and calibration files with robust fallback."""

    def __init__(self, base_dir: Path | str | None = None):
        if base_dir is None:
            self.base_dir = Path(__file__).resolve().parent.parent
        else:
            self.base_dir = Path(base_dir)

        self.config_dir = self.base_dir / "config"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.settings_file = self.config_dir / "settings.json"
        self.calibration_file = self.config_dir / "calibration.json"

        self.settings: Dict[str, Any] = dict(DEFAULT_SETTINGS)
        self.settings = self.load_settings()

    def load_settings(self) -> Dict[str, Any]:
        """Loads and validates settings.json, returning safe defaults if invalid."""
        if not self.settings_file.exists():
            self.save_settings(dict(DEFAULT_SETTINGS))
            return dict(DEFAULT_SETTINGS)

        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                raise ValueError("Settings root is not a dictionary")

            validated = dict(DEFAULT_SETTINGS)
            for key, default_val in DEFAULT_SETTINGS.items():
                if key in data:
                    val = data[key]
                    if isinstance(default_val, bool):
                        validated[key] = bool(val)
                    elif isinstance(default_val, int) and not isinstance(default_val, bool):
                        validated[key] = int(val)
                    elif isinstance(default_val, float):
                        validated[key] = float(val)
                    else:
                        validated[key] = val
            return validated
        except Exception as e:
            logger.warning(f"Settings file corrupted or unreadable ({e}). Rebuilding defaults.")
            backup_path = self.settings_file.with_suffix(".corrupt.bak")
            try:
                shutil.copy2(self.settings_file, backup_path)
            except Exception:
                pass
            self.save_settings(DEFAULT_SETTINGS)
            return dict(DEFAULT_SETTINGS)

    def save_settings(self, new_settings: Dict[str, Any] | None = None) -> bool:
        """Persists current or specified settings to disk."""
        if new_settings is not None:
            self.settings.update(new_settings)
        try:
            temp_file = self.settings_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2)
            temp_file.replace(self.settings_file)
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def get(self, key: str, default: Any = None) -> Any:
        return self.settings.get(key, default)

    def set(self, key: str, value: Any, save: bool = True) -> None:
        self.settings[key] = value
        if save:
            self.save_settings()

    def load_calibration(self) -> Dict[str, Any]:
        """Loads calibration mapping or defaults."""
        default_calib = {
            "default": {
                "top_left": [0.15, 0.15],
                "top_right": [0.85, 0.15],
                "bottom_left": [0.15, 0.85],
                "bottom_right": [0.85, 0.85],
                "calibrated": False,
                "timestamp": None
            },
            "displays": {}
        }
        if not self.calibration_file.exists():
            self.save_calibration(default_calib)
            return default_calib

        try:
            with open(self.calibration_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, dict):
                return default_calib
            return data
        except Exception as e:
            logger.warning(f"Calibration file unreadable ({e}). Reverting to default bounds.")
            self.save_calibration(default_calib)
            return default_calib

    def save_calibration(self, data: Dict[str, Any]) -> bool:
        try:
            temp_file = self.calibration_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            temp_file.replace(self.calibration_file)
            return True
        except Exception as e:
            logger.error(f"Failed to save calibration: {e}")
            return False
