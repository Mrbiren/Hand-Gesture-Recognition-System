"""
CryNet Swipe Gesture Detector
Tracks horizontal trajectory and velocity over a temporal window to trigger
directional swipes (Left / Right) without false positives during cursor movement.
"""

from __future__ import annotations
import collections
import time
from typing import Deque, List, Optional, Tuple
from gestures.gesture_state import HandLandmarkPoint


class SwipeDetector:
    """Detects quick horizontal flicks/swipes."""

    def __init__(
        self,
        velocity_threshold: float = 0.6,
        distance_threshold: float = 0.18,
        cooldown_seconds: float = 0.8,
        history_window_sec: float = 0.25,
    ):
        self.velocity_threshold = velocity_threshold
        self.distance_threshold = distance_threshold
        self.cooldown_seconds = cooldown_seconds
        self.history_window_sec = history_window_sec

        # Stores (timestamp, x, y)
        self.history: Deque[Tuple[float, float, float]] = collections.deque(maxlen=20)
        self.last_trigger_time: float = 0.0

    def update_config(self, velocity_threshold: float, distance_threshold: float) -> None:
        self.velocity_threshold = max(0.2, min(2.0, velocity_threshold))
        self.distance_threshold = max(0.08, min(0.6, distance_threshold))

    def reset(self) -> None:
        self.history.clear()

    def process(
        self, landmarks: List[HandLandmarkPoint], is_palm_or_open: bool
    ) -> Optional[str]:
        """
        Processes wrist/palm center position.
        Returns:
            'left', 'right', or None
        """
        now = time.time()

        # Check cooldown
        if now - self.last_trigger_time < self.cooldown_seconds:
            return None

        if len(landmarks) < 21:
            self.reset()
            return None

        # Track palm center (midpoint of wrist index 0 and middle MCP index 9)
        wrist = landmarks[0]
        middle_mcp = landmarks[9]
        cx = (wrist.x + middle_mcp.x) / 2.0
        cy = (wrist.y + middle_mcp.y) / 2.0

        # Append current point
        self.history.append((now, cx, cy))

        # Evict old history
        while self.history and (now - self.history[0][0]) > self.history_window_sec:
            self.history.popleft()

        if len(self.history) < 4:
            return None

        # Compare oldest in window with current
        start_t, start_x, start_y = self.history[0]
        dt = now - start_t
        if dt < 0.05:
            return None

        dx = cx - start_x
        dy = cy - start_y
        velocity_x = dx / dt

        # Swipe requires predominantly horizontal motion (horizontal > 1.8 * vertical)
        if abs(dy) > 0.001 and (abs(dx) / (abs(dy) + 1e-5)) < 1.6:
            return None

        # Check distance and velocity
        if abs(dx) >= self.distance_threshold and abs(velocity_x) >= self.velocity_threshold:
            # Camera view is mirrored by default, so moving hand to user's left
            # in mirror mode or normal mode. We ensure consistent intuitive direction:
            direction = "right" if dx > 0 else "left"
            self.last_trigger_time = now
            self.history.clear()
            return direction

        return None
