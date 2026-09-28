"""
CryNet Windows Screen Lock Gesture Detector

Temporal State Machine:
IDLE -> OPEN_PALM_CONFIRMED -> LOCK_ARMED -> FIST_HOLDING -> LOCK_TRIGGERED

Requirements:
1. Deliberate sequence: OPEN PALM -> CLOSE INTO FIST -> HOLD 2.0 seconds.
2. Fist alone does NOT trigger lock.
3. Open palm alone does NOT trigger lock.
4. Genuine landmark geometry verification:
   - For fist: verify fingertips are actually curled toward the palm.
   - For open palm: verify fingers are spatially extended and separated.
5. Fist must remain continuously detected for >= 2.0 seconds.
6. If hand opens during hold -> cancel ("LOCK CANCELLED").
7. If hand tracking is lost -> cancel ("LOCK CANCELLED").
8. If confidence drops below threshold -> cancel ("LOCK CANCELLED").
9. If finger configuration changes -> cancel ("LOCK CANCELLED").
10. Cooldown of at least 5.0 seconds after triggering.
11. Native Windows screen lock action (Win+L equivalent).
"""

from __future__ import annotations

from enum import Enum
import logging
import math
import time
from typing import Callable, List, Optional, Tuple

from gestures.gesture_state import FingerStatus, HandLandmarkPoint

logger = logging.getLogger("CryNet.LockScreen")


class LockScreenState(Enum):
    IDLE = "IDLE"
    OPEN_PALM_CONFIRMED = "OPEN_PALM_CONFIRMED"
    LOCK_ARMED = "LOCK_ARMED"
    FIST_HOLDING = "FIST_HOLDING"
    LOCK_TRIGGERED = "LOCK_TRIGGERED"


def dist_2d(p1: HandLandmarkPoint, p2: HandLandmarkPoint) -> float:
    """Computes 2D Euclidean distance between two landmarks."""
    return math.hypot(p1.x - p2.x, p1.y - p2.y)


def is_genuine_open_palm(
    landmarks: Optional[List[HandLandmarkPoint]],
    fingers: Optional[FingerStatus],
) -> bool:
    """
    Verifies that fingers are genuinely spatially extended and spread,
    rather than relying solely on extended_count.
    """
    if fingers is not None and fingers.extended_count < 4:
        return False

    # Exclude 2-finger scroll posture (Index+Middle extended, Ring+Pinky folded)
    if fingers is not None:
        if fingers.index_extended and fingers.middle_extended and not fingers.ring_extended:
            return False

    if landmarks is None or len(landmarks) < 21:
        # Fallback to finger status if landmarks not provided
        return fingers is not None and fingers.extended_count >= 4

    wrist = landmarks[0]
    middle_mcp = landmarks[9]
    palm_len = dist_2d(wrist, middle_mcp)
    if palm_len < 0.02:
        return fingers is not None and fingers.extended_count >= 4

    hand_scale = max(0.05, palm_len)

    # Palm center approximation
    palm_cx = (wrist.x + middle_mcp.x) / 2.0
    palm_cy = (wrist.y + middle_mcp.y) / 2.0
    palm_center = HandLandmarkPoint(x=palm_cx, y=palm_cy, z=0.0)

    # Check 4 non-thumb fingers: index(8 vs 5,6), middle(12 vs 9,10), ring(16 vs 13,14), pinky(20 vs 17,18)
    finger_joints = [
        (8, 6, 5),   # Index: tip, pip, mcp
        (12, 10, 9), # Middle: tip, pip, mcp
        (16, 14, 13),# Ring: tip, pip, mcp
        (20, 18, 17),# Pinky: tip, pip, mcp
    ]

    extended_fingers = 0
    for tip_idx, pip_idx, mcp_idx in finger_joints:
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]

        d_tip_wrist = dist_2d(tip, wrist)
        d_pip_wrist = dist_2d(pip, wrist)
        d_tip_mcp = dist_2d(tip, mcp)
        d_pip_mcp = max(0.01, dist_2d(pip, mcp))

        # Tip must be extended outward beyond PIP relative to wrist and MCP
        if d_tip_wrist > d_pip_wrist * 1.05 and (d_tip_mcp / d_pip_mcp) > 1.35:
            extended_fingers += 1

    # At least 3 of 4 non-thumb fingers must be spatially extended
    if extended_fingers < 3:
        return False

    # Spatial span: fingertips must be spread out across space
    span_index_pinky = dist_2d(landmarks[8], landmarks[20])
    if span_index_pinky < hand_scale * 0.45:
        # Fingers are clustered/bunched together, not an open palm
        return False

    return True


def is_genuine_closed_fist(
    landmarks: Optional[List[HandLandmarkPoint]],
    fingers: Optional[FingerStatus],
) -> bool:
    """
    Verifies that fingertips are genuinely curled in toward the palm,
    rather than relying solely on extended_count == 0.
    """
    if fingers is not None:
        # If any pointing/gesture finger is extended, it cannot be a closed fist
        if (
            fingers.index_extended
            or fingers.middle_extended
            or fingers.ring_extended
            or fingers.pinky_extended
        ):
            return False
        if fingers.extended_count > 1:
            return False

    if landmarks is None or len(landmarks) < 21:
        # Fallback to finger status if landmarks not provided
        return fingers is not None and fingers.extended_count == 0

    wrist = landmarks[0]
    middle_mcp = landmarks[9]
    palm_len = dist_2d(wrist, middle_mcp)
    if palm_len < 0.02:
        return fingers is not None and fingers.extended_count == 0

    hand_scale = max(0.05, palm_len)

    palm_cx = (wrist.x + middle_mcp.x) / 2.0
    palm_cy = (wrist.y + middle_mcp.y) / 2.0
    palm_center = HandLandmarkPoint(x=palm_cx, y=palm_cy, z=0.0)

    finger_joints = [
        (8, 6, 5),   # Index
        (12, 10, 9), # Middle
        (16, 14, 13),# Ring
        (20, 18, 17),# Pinky
    ]

    curled_fingers = 0
    for tip_idx, pip_idx, mcp_idx in finger_joints:
        tip = landmarks[tip_idx]
        pip = landmarks[pip_idx]
        mcp = landmarks[mcp_idx]

        d_tip_palm = dist_2d(tip, palm_center)
        d_pip_palm = dist_2d(pip, palm_center)
        d_tip_mcp = dist_2d(tip, mcp)
        d_pip_mcp = max(0.01, dist_2d(pip, mcp))
        d_tip_wrist = dist_2d(tip, wrist)
        d_pip_wrist = dist_2d(pip, wrist)

        # In a curled fist: tip is pulled in close to MCP / palm
        is_curled = (
            (d_tip_mcp / d_pip_mcp) < 1.45
            or d_tip_palm < d_pip_palm * 1.15
            or d_tip_wrist < d_pip_wrist * 1.10
        )
        if is_curled:
            curled_fingers += 1

    # In a genuine fist, all 4 non-thumb fingers must be curled
    if curled_fingers < 4:
        return False

    # Fingers should not be spread far apart
    span_index_pinky = dist_2d(landmarks[8], landmarks[20])
    if span_index_pinky > hand_scale * 1.3:
        return False

    return True


class LockScreenDetector:
    """
    Evaluates temporal transitions and hold duration for the Windows Screen Lock gesture.
    State Machine:
    IDLE -> OPEN_PALM_CONFIRMED -> LOCK_ARMED -> FIST_HOLDING -> LOCK_TRIGGERED
    """

    def __init__(
        self,
        hold_duration: float = 2.0,
        cooldown_duration: float = 5.0,
        confidence_threshold: float = 0.60,
        transition_timeout: float = 1.5,
        on_lock: Optional[Callable[[], bool]] = None,
    ):
        self.hold_duration = hold_duration
        self.cooldown_duration = cooldown_duration
        self.confidence_threshold = confidence_threshold
        self.transition_timeout = transition_timeout
        self.on_lock = on_lock

        self.state: LockScreenState = LockScreenState.IDLE
        self.open_palm_time: float = 0.0
        self.armed_time: float = 0.0
        self.hold_start_time: float = 0.0
        self.last_trigger_time: float = 0.0

        # Feedback state
        self.feedback_message: str = ""
        self._cancel_message_until: float = 0.0

    def update_config(
        self,
        hold_duration: Optional[float] = None,
        cooldown_duration: Optional[float] = None,
        confidence_threshold: Optional[float] = None,
        transition_timeout: Optional[float] = None,
    ) -> None:
        """Updates detector configuration parameters."""
        if hold_duration is not None:
            self.hold_duration = max(0.5, float(hold_duration))
        if cooldown_duration is not None:
            self.cooldown_duration = max(1.0, float(cooldown_duration))
        if confidence_threshold is not None:
            self.confidence_threshold = max(0.1, min(1.0, float(confidence_threshold)))
        if transition_timeout is not None:
            self.transition_timeout = max(0.2, float(transition_timeout))

    def reset(self) -> None:
        """Resets the state machine to IDLE without cancel feedback."""
        self.state = LockScreenState.IDLE
        self.open_palm_time = 0.0
        self.armed_time = 0.0
        self.hold_start_time = 0.0
        self.feedback_message = ""
        self._cancel_message_until = 0.0

    def _cancel_gesture(self, now: float) -> None:
        """Handles cancellation of an in-progress hold."""
        self.state = LockScreenState.IDLE
        self.open_palm_time = 0.0
        self.armed_time = 0.0
        self.hold_start_time = 0.0
        self.feedback_message = "LOCK CANCELLED"
        self._cancel_message_until = now + 1.2
        logger.info("Screen lock gesture cancelled.")

    def process(
        self,
        hand_detected: bool,
        confidence: float,
        fingers: Optional[FingerStatus],
        landmarks: Optional[List[HandLandmarkPoint]] = None,
        current_time: Optional[float] = None,
    ) -> Tuple[bool, str]:
        """
        Evaluates current hand state and drives the screen lock temporal state machine:
        IDLE -> OPEN_PALM_CONFIRMED -> LOCK_ARMED -> FIST_HOLDING -> LOCK_TRIGGERED

        Returns:
            (is_lock_active, feedback_text)
            - is_lock_active: True if currently holding fist for lock or lock triggered.
            - feedback_text: Current status/HUD string (e.g. "LOCKING IN 2.0", "LOCK CANCELLED", etc.)
        """
        now = current_time if current_time is not None else time.time()

        # Cooldown guard: cannot initiate lock sequence during cooldown
        in_cooldown = (now - self.last_trigger_time) < self.cooldown_duration

        # 1. Cancellation Path: TRACKING_LOST
        if not hand_detected or fingers is None:
            if self.state in (LockScreenState.LOCK_ARMED, LockScreenState.FIST_HOLDING):
                self._cancel_gesture(now)
            elif self.state == LockScreenState.OPEN_PALM_CONFIRMED:
                if (now - self.open_palm_time) > self.transition_timeout:
                    self.state = LockScreenState.IDLE
            return False, self._get_feedback(now)

        # 2. Cancellation Path: CONFIDENCE_TOO_LOW
        if confidence < self.confidence_threshold:
            if self.state in (LockScreenState.LOCK_ARMED, LockScreenState.FIST_HOLDING):
                self._cancel_gesture(now)
            elif self.state == LockScreenState.OPEN_PALM_CONFIRMED:
                if (now - self.open_palm_time) > self.transition_timeout:
                    self.state = LockScreenState.IDLE
            return False, self._get_feedback(now)

        # In cooldown: prevent starting a new sequence
        if in_cooldown:
            if self.state != LockScreenState.IDLE:
                self.state = LockScreenState.IDLE
            return False, self._get_feedback(now)

        # Robust geometric verification
        open_palm = is_genuine_open_palm(landmarks, fingers)
        closed_fist = is_genuine_closed_fist(landmarks, fingers)

        # -------------------------------------------------------------
        # STATE MACHINE TRANSITIONS
        # -------------------------------------------------------------

        # State 1: IDLE
        if self.state == LockScreenState.IDLE:
            if open_palm:
                self.state = LockScreenState.OPEN_PALM_CONFIRMED
                self.open_palm_time = now
                self.feedback_message = ""
            # A fist in IDLE state is just a normal fist, do NOT lock!
            return False, self._get_feedback(now)

        # State 2: OPEN_PALM_CONFIRMED
        elif self.state == LockScreenState.OPEN_PALM_CONFIRMED:
            if open_palm:
                # Renew timestamp while palm stays genuinely open
                self.open_palm_time = now
                return False, self._get_feedback(now)

            # Hand is no longer open palm. Did it transition to a fist directly?
            if closed_fist:
                if (now - self.open_palm_time) <= self.transition_timeout:
                    # Direct transition from confirmed palm to fist
                    self.state = LockScreenState.FIST_HOLDING
                    self.hold_start_time = now
                    feedback = self._calculate_countdown(now)
                    return True, feedback
                else:
                    self.state = LockScreenState.IDLE
                    return False, self._get_feedback(now)

            # Hand began folding / closing (transitioning)
            if (now - self.open_palm_time) <= self.transition_timeout:
                # Check if user switched to an intentional non-lock gesture
                is_cursor = (fingers.index_extended and not fingers.middle_extended and not fingers.ring_extended)
                is_scroll = (fingers.index_extended and fingers.middle_extended and not fingers.ring_extended and not fingers.pinky_extended)
                if is_cursor or is_scroll:
                    self.state = LockScreenState.IDLE
                else:
                    self.state = LockScreenState.LOCK_ARMED
                    self.armed_time = now
            else:
                self.state = LockScreenState.IDLE

            return False, self._get_feedback(now)

        # State 3: LOCK_ARMED
        elif self.state == LockScreenState.LOCK_ARMED:
            if closed_fist:
                if (now - self.open_palm_time) <= self.transition_timeout:
                    self.state = LockScreenState.FIST_HOLDING
                    self.hold_start_time = now
                    feedback = self._calculate_countdown(now)
                    return True, feedback
                else:
                    self.state = LockScreenState.IDLE
                    return False, self._get_feedback(now)

            if open_palm:
                # Hand re-opened
                self.state = LockScreenState.OPEN_PALM_CONFIRMED
                self.open_palm_time = now
                return False, self._get_feedback(now)

            # Check timeout in armed state
            is_cursor = (fingers.index_extended and not fingers.middle_extended and not fingers.ring_extended)
            is_scroll = (fingers.index_extended and fingers.middle_extended and not fingers.ring_extended and not fingers.pinky_extended)
            if is_cursor or is_scroll or (now - self.open_palm_time) > self.transition_timeout:
                self.state = LockScreenState.IDLE

            return False, self._get_feedback(now)

        # State 4: FIST_HOLDING
        elif self.state == LockScreenState.FIST_HOLDING:
            # Must remain a genuine closed fist
            if not closed_fist:
                self._cancel_gesture(now)
                return False, self._get_feedback(now)

            # Continuous fist hold maintained
            elapsed = now - self.hold_start_time
            if elapsed >= self.hold_duration:
                # State 5: LOCK_TRIGGERED (Hold >= 2.0s reached)
                self.state = LockScreenState.LOCK_TRIGGERED
                self.last_trigger_time = now
                self.feedback_message = "LOCKING SYSTEM..."
                logger.info("Screen lock hold threshold met (>= 2.0s). Triggering Windows lock.")

                if self.on_lock:
                    try:
                        self.on_lock()
                    except Exception as e:
                        logger.error(f"Error triggering lock action: {e}")

                # Transition back to IDLE after triggering
                self.state = LockScreenState.IDLE
                self.open_palm_time = 0.0
                self.armed_time = 0.0
                self.hold_start_time = 0.0
                return True, "LOCKING SYSTEM..."
            else:
                feedback = self._calculate_countdown(now)
                return True, feedback

        return False, self._get_feedback(now)

    def _calculate_countdown(self, now: float) -> str:
        """Returns the discrete countdown string requested."""
        elapsed = now - self.hold_start_time
        remaining = max(0.0, self.hold_duration - elapsed)

        if remaining > 1.5:
            msg = "LOCKING IN 2.0"
        elif remaining > 1.0:
            msg = "LOCKING IN 1.5"
        elif remaining > 0.5:
            msg = "LOCKING IN 1.0"
        elif remaining > 0.0:
            msg = "LOCKING IN 0.5"
        else:
            msg = "LOCKING SYSTEM..."

        self.feedback_message = msg
        return msg

    def _get_feedback(self, now: float) -> str:
        """Returns active feedback, expiring temporary messages after display duration."""
        if self.feedback_message == "LOCK CANCELLED":
            if now > self._cancel_message_until:
                self.feedback_message = ""
        return self.feedback_message
