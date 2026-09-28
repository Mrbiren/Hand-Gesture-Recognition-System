"""
CryNet Cursor Gesture Module
Calculates normalized screen cursor coordinates from index fingertip landmark
relative to the active calibrated interaction zone.
"""

from __future__ import annotations
from typing import List, Optional, Tuple
from gestures.gesture_state import HandLandmarkPoint


class CursorGesture:
    """Extracts index fingertip position and maps to calibrated bounds [0.0, 1.0]."""

    def __init__(self):
        # Default interaction zone inside normalized camera frame
        self.min_x: float = 0.15
        self.min_y: float = 0.15
        self.max_x: float = 0.85
        self.max_y: float = 0.85

    def set_calibration_bounds(
        self, min_x: float, min_y: float, max_x: float, max_y: float
    ) -> None:
        """Sets calibrated bounding box for the interaction area."""
        self.min_x = max(0.0, min(0.45, min_x))
        self.min_y = max(0.0, min(0.45, min_y))
        self.max_x = max(0.55, min(1.0, max_x))
        self.max_y = max(0.55, min(1.0, max_y))

    def extract_normalized_pos(
        self, landmarks: List[HandLandmarkPoint]
    ) -> Optional[Tuple[float, float]]:
        """
        Extracts index fingertip (landmark 8) and projects into [0.0, 1.0] range
        based on calibrated bounding box.
        """
        if len(landmarks) < 21:
            return None

        index_tip = landmarks[8]
        raw_x = index_tip.x
        raw_y = index_tip.y

        width = max(0.1, self.max_x - self.min_x)
        height = max(0.1, self.max_y - self.min_y)

        norm_x = (raw_x - self.min_x) / width
        norm_y = (raw_y - self.min_y) / height

        # Clamp to [0.0, 1.0]
        norm_x = max(0.0, min(1.0, norm_x))
        norm_y = max(0.0, min(1.0, norm_y))

        return norm_x, norm_y
