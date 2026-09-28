"""
CryNet Pinch Gesture Detector
Handles discrete single left-click on pinch contact, continuous drag when moved
while pinched, and clean release upon finger separation.
"""

from __future__ import annotations
import math
import time
from typing import List, Optional, Tuple
from gestures.gesture_state import HandLandmarkPoint


class PinchDetector:
    """Detects pinch contact, discrete single click, and drag movement."""

    def __init__(
        self,
        pinch_threshold: float = 0.045,
        drag_distance_threshold: float = 0.025,
    ):
        self.pinch_threshold = pinch_threshold
        self.drag_distance_threshold = drag_distance_threshold

        self.is_pinched: bool = False
        self.is_dragging: bool = False
        self.pinch_start_pos: Optional[Tuple[float, float]] = None
        self.pinch_start_time: float = 0.0
        self.last_pinch_distance: float = 1.0

    def update_config(self, pinch_threshold: float, drag_threshold: float) -> None:
        self.pinch_threshold = max(0.01, min(0.15, pinch_threshold))
        self.drag_distance_threshold = max(0.005, min(0.1, drag_threshold))

    def reset(self) -> None:
        self.is_pinched = False
        self.is_dragging = False
        self.pinch_start_pos = None
        self.pinch_start_time = 0.0
        self.last_pinch_distance = 1.0

    def process(
        self, landmarks: List[HandLandmarkPoint]
    ) -> Tuple[bool, bool, bool, float]:
        """
        Calculates pinch state from thumb tip (index 4) and index tip (index 8).

        Returns:
            (is_pinched, click_triggered, is_dragging, current_distance)
        """
        if len(landmarks) < 21:
            if self.is_pinched:
                self.reset()
            return False, False, False, 1.0

        thumb_tip = landmarks[4]
        index_tip = landmarks[8]

        # Normalized Euclidean distance
        dx = thumb_tip.x - index_tip.x
        dy = thumb_tip.y - index_tip.y
        dist = math.hypot(dx, dy)
        self.last_pinch_distance = dist

        click_triggered = False
        current_pinched = dist < self.pinch_threshold

        # Center point between thumb and index
        mid_x = (thumb_tip.x + index_tip.x) / 2.0
        mid_y = (thumb_tip.y + index_tip.y) / 2.0

        if current_pinched:
            if not self.is_pinched:
                # Pinch just started!
                self.is_pinched = True
                self.is_dragging = False
                self.pinch_start_pos = (mid_x, mid_y)
                self.pinch_start_time = time.time()
                click_triggered = True  # Single initial click or down
            else:
                # Already pinched; check if moved enough to qualify as Drag
                if not self.is_dragging and self.pinch_start_pos:
                    move_dist = math.hypot(
                        mid_x - self.pinch_start_pos[0],
                        mid_y - self.pinch_start_pos[1],
                    )
                    if move_dist > self.drag_distance_threshold:
                        self.is_dragging = True
        else:
            # Pinch released
            if self.is_pinched:
                self.is_pinched = False
                self.is_dragging = False
                self.pinch_start_pos = None

        return self.is_pinched, click_triggered, self.is_dragging, dist
