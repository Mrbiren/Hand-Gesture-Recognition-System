"""
CryNet Two-Finger Scroll Detector

Tracks the center of index fingertip (landmark 8) and middle fingertip (landmark 12).
Calculates vertical scrolling delta with:
- Temporal smoothing
- Direction hysteresis & tiny reversal suppression
- Minimum movement threshold
- Velocity-based scroll amount
- Explicit camera coordinate handling (hand UP -> center_y decreases -> scroll UP / positive;
  hand DOWN -> center_y increases -> scroll DOWN / negative)
- Stable scroll start/stop behavior
"""

from __future__ import annotations

from collections import deque
import math
from typing import Deque, List, Optional

from gestures.gesture_state import HandLandmarkPoint


class ScrollDetector:
    """Calculates robust, hysteresis-gated vertical scroll deltas."""

    def __init__(self, dead_zone: float = 0.0035, scroll_sensitivity: float = 1.0):
        self.dead_zone = dead_zone
        self.scroll_sensitivity = scroll_sensitivity

        self.last_raw_y: Optional[float] = None
        self.smoothed_y: Optional[float] = None
        self.smoothing_alpha: float = 0.65

        # Direction tracking: +1 = UP, -1 = DOWN, 0 = NEUTRAL
        self.active_direction: int = 0
        self.opposite_count: int = 0
        self.reversal_threshold: float = 0.006

        # History buffer for velocity calculation
        self.history_deltas: Deque[float] = deque(maxlen=4)

    def update_config(self, scroll_sensitivity: float, dead_zone: float = 0.0035) -> None:
        self.scroll_sensitivity = max(0.1, min(5.0, scroll_sensitivity))
        self.dead_zone = max(0.001, min(0.05, dead_zone))

    def reset(self) -> None:
        """Resets all tracking states upon gesture stop or tracking loss."""
        self.last_raw_y = None
        self.smoothed_y = None
        self.active_direction = 0
        self.opposite_count = 0
        self.history_deltas.clear()

    def process(
        self,
        landmarks: List[HandLandmarkPoint],
        is_two_finger_extended: bool,
    ) -> float:
        """
        Processes current landmark positions.

        Camera coordinate convention:
            Hand moves UP -> center_y decreases -> scroll UP (positive).
            Hand moves DOWN -> center_y increases -> scroll DOWN (negative).

        Returns:
            scroll_delta: Positive = scroll up, Negative = scroll down, 0.0 = no scroll.
        """
        if not is_two_finger_extended or len(landmarks) < 21:
            self.reset()
            return 0.0

        index_tip = landmarks[8]
        middle_tip = landmarks[12]

        center_x = (index_tip.x + middle_tip.x) / 2.0
        center_y = (index_tip.y + middle_tip.y) / 2.0

        # Initial anchor frame - establishes reference without sudden jump
        if self.smoothed_y is None or self.last_raw_y is None:
            self.smoothed_y = center_y
            self.last_raw_y = center_y
            return 0.0

        # Temporal exponential smoothing
        self.smoothed_y = (
            self.smoothed_y * (1.0 - self.smoothing_alpha)
            + center_y * self.smoothing_alpha
        )

        # Coordinate convention:
        # Hand moves UP -> center_y decreases -> (last_raw_y - smoothed_y) is POSITIVE.
        # Hand moves DOWN -> center_y increases -> (last_raw_y - smoothed_y) is NEGATIVE.
        dy = self.last_raw_y - self.smoothed_y  # UP = positive, DOWN = negative

        # Minimum movement threshold: ignore microscopic noise
        if abs(dy) < self.dead_zone:
            # Gently nudge last_raw_y towards smoothed_y to prevent accumulator creep
            self.last_raw_y = self.last_raw_y * 0.9 + self.smoothed_y * 0.1
            return 0.0

        frame_dir = 1 if dy > 0 else -1

        # Direction hysteresis & suppression of tiny reversals
        if self.active_direction == 0:
            # First deliberate movement sets direction
            self.active_direction = frame_dir
            self.opposite_count = 0
        elif frame_dir != self.active_direction:
            # Movement in opposite direction: check for genuine reversal vs momentary flutter
            if abs(dy) < self.reversal_threshold:
                # Tiny flutter in opposite direction -> suppress!
                return 0.0
            elif abs(dy) >= self.reversal_threshold * 2.0:
                # Large deliberate opposite motion -> immediate reversal!
                self.active_direction = frame_dir
                self.opposite_count = 0
            else:
                self.opposite_count += 1
                if self.opposite_count >= 2:
                    # Sustained movement in opposite direction -> reverse direction!
                    self.active_direction = frame_dir
                    self.opposite_count = 0
                else:
                    # Require another frame of sustained opposite movement
                    return 0.0
        else:
            # Consistent with active direction
            self.opposite_count = 0

        # Commit position update
        self.last_raw_y = self.smoothed_y
        self.history_deltas.append(abs(dy))

        # Velocity-based scroll amount calculation
        avg_speed = sum(self.history_deltas) / len(self.history_deltas)
        speed_factor = (
            18.0 * (avg_speed / 0.02)
            if avg_speed > 0.02
            else (avg_speed * 900.0)
        )
        scroll_amount = (
            self.active_direction
            * max(0.5, speed_factor)
            * self.scroll_sensitivity
        )

        return scroll_amount
