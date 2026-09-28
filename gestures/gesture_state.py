"""
CryNet Gesture State Definitions
Contains enums, data structures, and state representations for all hand gestures.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional, Tuple


class GestureType(Enum):
    NONE = "NONE"
    CURSOR = "CURSOR"                # Index extended, others folded
    PINCH = "PINCH"                  # Thumb & Index touching (Click / Drag)
    DRAG = "DRAG"                    # Pinch held + hand movement
    TWO_FINGER_SCROLL = "SCROLL"     # Index + Middle extended, vertical movement
    OPEN_PALM = "OPEN_PALM"          # All fingers spread -> Safety Pause
    FIST = "FIST"                    # All fingers folded -> Neutral
    SWIPE_LEFT = "SWIPE_LEFT"        # Deliberate fast horizontal left -> Alt+Left
    SWIPE_RIGHT = "SWIPE_RIGHT"      # Deliberate fast horizontal right -> Alt+Right
    LOCK_SCREEN = "LOCK_SCREEN"      # Open Palm -> Fist held 2s -> Windows Lock


class SystemMode(Enum):
    STANDBY = "STANDBY"
    ONLINE = "ONLINE"
    PAUSED = "PAUSED"
    CALIBRATING = "CALIBRATING"
    ERROR = "ERROR"


@dataclass
class FingerStatus:
    thumb_extended: bool = False
    index_extended: bool = False
    middle_extended: bool = False
    ring_extended: bool = False
    pinky_extended: bool = False

    @property
    def extended_count(self) -> int:
        return sum([
            self.thumb_extended,
            self.index_extended,
            self.middle_extended,
            self.ring_extended,
            self.pinky_extended,
        ])


@dataclass
class HandLandmarkPoint:
    x: float  # Normalized [0.0, 1.0]
    y: float  # Normalized [0.0, 1.0]
    z: float  # Relative depth
    visibility: float = 1.0


@dataclass
class TrackingData:
    hand_detected: bool = False
    hand_count: int = 0
    landmarks: List[HandLandmarkPoint] = field(default_factory=list)
    confidence: float = 0.0
    finger_status: FingerStatus = field(default_factory=FingerStatus)
    active_gesture: GestureType = GestureType.NONE
    status_message: str = "STANDBY"
    cursor_point: Optional[Tuple[float, float]] = None  # Normalized (x, y)
    pinch_distance: float = 1.0
    scroll_delta: float = 0.0
    swipe_event: Optional[str] = None
    fps: float = 0.0
    target_display_name: str = "Display 1"
    is_paused: bool = False
