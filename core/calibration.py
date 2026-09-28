"""
CryNet Calibration Manager
Manages the 4-corner interaction area calibration wizard and coordinate mapping.
Stores results in config/calibration.json per display or default.
"""

from __future__ import annotations
import datetime
import logging
from typing import Any, Dict, List, Optional, Tuple
from core.config_manager import ConfigManager

logger = logging.getLogger("CryNet.Calibration")


class CalibrationManager:
    """Handles 4-point calibration step recording and bounding box calculation."""

    STEPS = [
        ("TOP_LEFT", "Move hand to TOP-LEFT corner of comfortable interaction area"),
        ("TOP_RIGHT", "Move hand to TOP-RIGHT corner of comfortable interaction area"),
        ("BOTTOM_LEFT", "Move hand to BOTTOM-LEFT corner of comfortable interaction area"),
        ("BOTTOM_RIGHT", "Move hand to BOTTOM-RIGHT corner of comfortable interaction area"),
    ]

    def __init__(self, config_manager: ConfigManager):
        self.config_manager = config_manager
        self.current_step_idx: int = 0
        self.is_calibrating: bool = False
        self.recorded_points: Dict[str, Tuple[float, float]] = {}
        self.target_display_name: str = "Display 1"

        # Active interaction bounds [min_x, min_y, max_x, max_y]
        self.min_x: float = 0.15
        self.min_y: float = 0.15
        self.max_x: float = 0.85
        self.max_y: float = 0.85

        self.load_active_calibration()

    def load_active_calibration(self, display_name: Optional[str] = None) -> None:
        """Loads calibration for specified display or default."""
        if display_name:
            self.target_display_name = display_name

        data = self.config_manager.load_calibration()
        calib_entry = data.get("displays", {}).get(self.target_display_name) or data.get("default", {})

        tl = calib_entry.get("top_left", [0.15, 0.15])
        tr = calib_entry.get("top_right", [0.85, 0.15])
        bl = calib_entry.get("bottom_left", [0.15, 0.85])
        br = calib_entry.get("bottom_right", [0.85, 0.85])

        xs = [tl[0], tr[0], bl[0], br[0]]
        ys = [tl[1], tr[1], bl[1], br[1]]

        self.min_x = max(0.0, min(xs))
        self.max_x = min(1.0, max(xs))
        self.min_y = max(0.0, min(ys))
        self.max_y = min(1.0, max(ys))

        # Enforce minimum area
        if (self.max_x - self.min_x) < 0.2:
            self.min_x, self.max_x = 0.15, 0.85
        if (self.max_y - self.min_y) < 0.2:
            self.min_y, self.max_y = 0.15, 0.85

        logger.info(
            f"Loaded calibration for {self.target_display_name}: "
            f"X=[{self.min_x:.2f}, {self.max_x:.2f}], Y=[{self.min_y:.2f}, {self.max_y:.2f}]"
        )

    def start_wizard(self, display_name: str) -> Tuple[str, str]:
        """Starts calibration wizard at Step 1."""
        self.target_display_name = display_name
        self.current_step_idx = 0
        self.is_calibrating = True
        self.recorded_points.clear()
        step_id, instruction = self.STEPS[0]
        return step_id, instruction

    def record_step(self, current_hand_x: float, current_hand_y: float) -> Tuple[bool, str, str]:
        """
        Records the current hand position for the active step.
        Returns:
            (is_finished, next_step_name, instruction_or_summary)
        """
        if not self.is_calibrating or self.current_step_idx >= len(self.STEPS):
            return True, "COMPLETE", "Calibration already completed"

        step_id, _ = self.STEPS[self.current_step_idx]
        self.recorded_points[step_id] = (
            max(0.0, min(1.0, current_hand_x)),
            max(0.0, min(1.0, current_hand_y)),
        )
        logger.info(f"Recorded calibration point for {step_id}: ({current_hand_x:.3f}, {current_hand_y:.3f})")

        self.current_step_idx += 1

        if self.current_step_idx >= len(self.STEPS):
            # All 4 points collected!
            self.finish_wizard()
            return True, "COMPLETE", "CALIBRATION COMPLETE"

        next_step_id, next_instruction = self.STEPS[self.current_step_idx]
        return False, next_step_id, next_instruction

    def cancel_wizard(self) -> None:
        self.is_calibrating = False
        self.current_step_idx = 0
        self.recorded_points.clear()

    def finish_wizard(self) -> None:
        """Computes bounding box and saves to config/calibration.json."""
        tl = self.recorded_points.get("TOP_LEFT", (0.15, 0.15))
        tr = self.recorded_points.get("TOP_RIGHT", (0.85, 0.15))
        bl = self.recorded_points.get("BOTTOM_LEFT", (0.15, 0.85))
        br = self.recorded_points.get("BOTTOM_RIGHT", (0.85, 0.85))

        xs = [tl[0], tr[0], bl[0], br[0]]
        ys = [tl[1], tr[1], bl[1], br[1]]

        self.min_x = max(0.0, min(xs))
        self.max_x = min(1.0, max(xs))
        self.min_y = max(0.0, min(ys))
        self.max_y = min(1.0, max(ys))

        # Enforce minimum boundaries
        if (self.max_x - self.min_x) < 0.15:
            self.min_x, self.max_x = 0.15, 0.85
        if (self.max_y - self.min_y) < 0.15:
            self.min_y, self.max_y = 0.15, 0.85

        data = self.config_manager.load_calibration()
        if "displays" not in data:
            data["displays"] = {}

        data["displays"][self.target_display_name] = {
            "top_left": list(tl),
            "top_right": list(tr),
            "bottom_left": list(bl),
            "bottom_right": list(br),
            "calibrated": True,
            "timestamp": datetime.datetime.now().isoformat(),
        }

        self.config_manager.save_calibration(data)
        self.is_calibrating = False
        logger.info(f"Calibration saved successfully for {self.target_display_name}")

    def map_to_normalized_interaction_space(
        self, raw_x: float, raw_y: float
    ) -> Tuple[float, float]:
        """Maps camera coordinate [0, 1] to calibrated active space [0, 1]."""
        w = max(0.1, self.max_x - self.min_x)
        h = max(0.1, self.max_y - self.min_y)

        norm_x = (raw_x - self.min_x) / w
        norm_y = (raw_y - self.min_y) / h

        return max(0.0, min(1.0, norm_x)), max(0.0, min(1.0, norm_y))
