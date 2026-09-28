"""
CryNet Gesture Engine

Orchestrates hand tracking, gesture classification, multi-monitor coordinate
mapping, safety enforcement, and mouse/keyboard event dispatching.
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Optional, Tuple

import numpy as np

from core.calibration import CalibrationManager
from core.cursor_controller import CursorController
from core.display_manager import DisplayManager
from core.hand_tracker import HandTracker
from core.safety_controller import SafetyController
from gestures.cursor import CursorGesture
from gestures.gesture_state import GestureType, SystemMode, TrackingData
from gestures.lock_screen import (
    LockScreenDetector,
    LockScreenState,
    is_genuine_closed_fist,
    is_genuine_open_palm,
)
from gestures.pinch import PinchDetector
from gestures.scroll import ScrollDetector
from gestures.swipe import SwipeDetector

logger = logging.getLogger("CryNet.GestureEngine")


class GestureEngine:
    """Core engine evaluating camera frames and driving OS interactions."""

    def __init__(
        self,
        display_manager: DisplayManager,
        calibration_manager: CalibrationManager,
        safety_controller: SafetyController,
        cursor_controller: CursorController,
        on_tracking_update: Optional[Callable[[TrackingData], None]] = None,
        lock_action: Optional[Callable[[], bool]] = None,
    ):
        self.display_manager = display_manager
        self.calibration_manager = calibration_manager
        self.safety_controller = safety_controller
        self.cursor_controller = cursor_controller
        self.on_tracking_update = on_tracking_update

        # Abstracted Windows lock workstation action (defaults to Win32 LockWorkStation)
        self.lock_action = lock_action or self.cursor_controller.lock_workstation

        self.hand_tracker = HandTracker()

        if self.hand_tracker.hands is None:
            logger.error(
                "Hand tracking is unavailable. Check the MediaPipe version in "
                "requirements.txt before starting gesture control."
            )

        self.pinch_detector = PinchDetector()
        self.scroll_detector = ScrollDetector()
        self.swipe_detector = SwipeDetector()
        self.cursor_gesture = CursorGesture()
        self.lock_screen_detector = LockScreenDetector(
            hold_duration=2.0,
            cooldown_duration=5.0,
            confidence_threshold=0.60,
            transition_timeout=1.5,
            on_lock=self._execute_lock_action,
        )

        # FPS calculation
        self._last_frame_time = time.time()
        self._fps_history = []

        # Current state
        self.active_gesture: GestureType = GestureType.NONE
        self.last_status_message: str = "STANDBY"

    def _execute_lock_action(self) -> bool:
        """Executes native workstation lock if verified safe by SafetyController."""
        if not self.safety_controller.validate_action_safe("lock_workstation"):
            return False
        return self.lock_action()

    def update_settings(self, settings: dict) -> None:
        """Propagates updated settings to sub-controllers."""

        self.cursor_controller.update_config(
            sensitivity=settings.get("sensitivity", 1.2),
            smoothing=settings.get("smoothing", 0.65),
            dead_zone=settings.get("dead_zone", 0.005),
            acceleration=settings.get("acceleration", 1.3),
            scroll_sensitivity=settings.get("scroll_sensitivity", 1.0),
        )

        self.pinch_detector.update_config(
            pinch_threshold=settings.get("pinch_threshold", 0.045),
            drag_threshold=settings.get("drag_distance_threshold", 0.025),
        )

        self.scroll_detector.update_config(
            scroll_sensitivity=settings.get("scroll_sensitivity", 1.0),
            dead_zone=settings.get("dead_zone", 0.005),
        )

        self.swipe_detector.update_config(
            velocity_threshold=settings.get("swipe_velocity_threshold", 0.6),
            distance_threshold=settings.get("swipe_distance_threshold", 0.25),
        )

        self.lock_screen_detector.update_config(
            hold_duration=settings.get("lock_hold_duration", 2.0),
            cooldown_duration=settings.get("lock_cooldown_duration", 5.0),
            confidence_threshold=settings.get("lock_confidence_threshold", 0.60),
        )

    def process_frame(
        self,
        frame_bgr: np.ndarray,
    ) -> Tuple[TrackingData, Optional[np.ndarray]]:
        """
        Main pipeline step called per webcam frame:

        1. Track hand landmarks with local MediaPipe.
        2. Calculate FPS.
        3. Check safety & monitor availability.
        4. Classify gesture.
        5. Map coordinates & dispatch Win32 inputs.
        """

        now = time.time()
        dt = now - self._last_frame_time
        self._last_frame_time = now

        fps = 1.0 / dt if dt > 0 else 0.0

        self._fps_history.append(fps)

        if len(self._fps_history) > 15:
            self._fps_history.pop(0)

        smooth_fps = sum(self._fps_history) / len(self._fps_history)

        # 1. MediaPipe Local Tracking
        tracking_data, annotated_frame = self.hand_tracker.process_frame(
            frame_bgr
        )

        if tracking_data.hand_detected:
            logger.debug(
                "GESTURE ENGINE: HAND DETECTED | count=%d | landmarks=%d | confidence=%.2f",
                tracking_data.hand_count,
                len(tracking_data.landmarks),
                tracking_data.confidence,
            )

        tracking_data.fps = smooth_fps

        target_disp = self.display_manager.get_target_display()

        tracking_data.target_display_name = (
            target_disp.name if target_disp else "None"
        )

        # 2. Monitor connection check
        if not self.display_manager.check_target_valid():
            self.safety_controller.pause_control("TARGET DISPLAY LOST")

            tracking_data.status_message = "TARGET DISPLAY LOST — PAUSED"
            tracking_data.is_paused = True

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # 3. If no hand detected
        if not tracking_data.hand_detected:
            self.active_gesture = GestureType.NONE

            # Reset ongoing drag/scroll
            self.cursor_controller.reset_state()
            self.pinch_detector.reset()
            self.scroll_detector.reset()
            self.swipe_detector.reset()

            # Handle lock screen tracking loss cancellation
            _, lock_feedback = self.lock_screen_detector.process(
                hand_detected=False,
                confidence=0.0,
                fingers=None,
                current_time=now,
            )

            status = (
                "STANDBY"
                if not self.safety_controller.is_enabled
                else "ONLINE — NO HAND"
            )

            tracking_data.status_message = lock_feedback if lock_feedback else status

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # 4. Multi-hand safety rule
        if tracking_data.hand_count > 1:
            self.safety_controller.pause_control(
                "TWO HANDS DETECTED"
            )

            self.cursor_controller.reset_state()
            self.pinch_detector.reset()
            self.lock_screen_detector.reset()

            tracking_data.status_message = (
                "TWO HANDS DETECTED — PAUSED"
            )

            tracking_data.is_paused = True
            tracking_data.active_gesture = GestureType.NONE

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # If we previously paused for 2 hands, resume
        if self.safety_controller.pause_reason == "TWO HANDS DETECTED":
            self.safety_controller.resume_control()

        # 5. Calibration Wizard Interception
        if self.calibration_manager.is_calibrating:
            tracking_data.active_gesture = GestureType.NONE

            tracking_data.status_message = (
                f"CALIBRATING: STEP "
                f"{self.calibration_manager.current_step_idx + 1}/4"
            )

            if len(tracking_data.landmarks) >= 21:
                raw_tip = tracking_data.landmarks[8]

                tracking_data.cursor_point = (
                    raw_tip.x,
                    raw_tip.y,
                )

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # ---------------------------------------------------------
        # DEFENSIVE LANDMARK VALIDATION
        #
        # MediaPipe should provide 21 landmarks for a valid hand.
        # Do not allow the gesture pipeline to process incomplete data.
        # ---------------------------------------------------------

        if len(tracking_data.landmarks) < 21:
            tracking_data.hand_detected = False
            tracking_data.status_message = (
                "INCOMPLETE HAND LANDMARK DATA"
            )

            self.active_gesture = GestureType.NONE

            self.cursor_controller.reset_state()
            self.pinch_detector.reset()
            self.scroll_detector.reset()
            self.swipe_detector.reset()

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        lms = tracking_data.landmarks
        fingers = tracking_data.finger_status

        # 6. Gesture Classification

        # 6.0 Lock Screen State Machine Evaluation
        is_lock_active = False
        lock_feedback = ""

        if self.safety_controller.is_enabled:
            is_lock_active, lock_feedback = self.lock_screen_detector.process(
                hand_detected=True,
                confidence=tracking_data.confidence,
                fingers=fingers,
                landmarks=lms,
                current_time=now,
            )
        else:
            self.lock_screen_detector.reset()

        if is_lock_active:
            if self.safety_controller.pause_reason == "GESTURE CONTROL PAUSED":
                self.safety_controller.resume_control()

            self.active_gesture = GestureType.LOCK_SCREEN
            tracking_data.active_gesture = GestureType.LOCK_SCREEN
            tracking_data.status_message = lock_feedback

            self.cursor_controller.reset_state()
            self.pinch_detector.reset()
            self.scroll_detector.reset()
            self.swipe_detector.reset()

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # 6A. Open Palm check (Pause safety)
        if is_genuine_open_palm(lms, fingers):
            self.safety_controller.pause_control(
                "GESTURE CONTROL PAUSED"
            )

            self.active_gesture = GestureType.OPEN_PALM
            tracking_data.active_gesture = GestureType.OPEN_PALM
            tracking_data.status_message = "GESTURE CONTROL PAUSED"
            tracking_data.is_paused = True

            self.cursor_controller.reset_state()
            self.pinch_detector.reset()

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        elif self.safety_controller.pause_reason == "GESTURE CONTROL PAUSED":
            # Palm closed/changed, resume
            self.safety_controller.resume_control()

        # 6B. Fist (Neutral)
        if is_genuine_closed_fist(lms, fingers):
            self.active_gesture = GestureType.FIST
            tracking_data.active_gesture = GestureType.FIST
            tracking_data.status_message = "FIST (NEUTRAL)"

            self.cursor_controller.reset_state()
            self.pinch_detector.reset()
            self.scroll_detector.reset()

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # 6C. Swipe Check (Alt+Left / Alt+Right)
        swipe_dir = self.swipe_detector.process(
            lms,
            fingers.extended_count >= 3,
        )

        if swipe_dir and self.safety_controller.is_action_allowed():
            self.active_gesture = (
                GestureType.SWIPE_LEFT
                if swipe_dir == "left"
                else GestureType.SWIPE_RIGHT
            )

            tracking_data.active_gesture = self.active_gesture

            tracking_data.swipe_event = swipe_dir.upper()

            tracking_data.status_message = (
                f"SWIPE {swipe_dir.upper()} -> "
                f"ALT + {swipe_dir.upper()}"
            )

            self.cursor_controller.trigger_navigation(
                swipe_dir
            )

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        # 6D. Two-Finger Scroll
        # Index + Middle extended,
        # Ring + Pinky folded.
        is_two_finger = (
            fingers.index_extended
            and fingers.middle_extended
            and not fingers.ring_extended
            and not fingers.pinky_extended
        )

        if is_two_finger:
            self.active_gesture = GestureType.TWO_FINGER_SCROLL

            scroll_delta = self.scroll_detector.process(
                lms,
                True,
            )

            tracking_data.scroll_delta = scroll_delta

            tracking_data.active_gesture = (
                GestureType.TWO_FINGER_SCROLL
            )

            tracking_data.status_message = (
                f"SCROLLING (Δ={scroll_delta:+.1f})"
            )

            if (
                self.safety_controller.is_action_allowed()
                and abs(scroll_delta) > 0.01
            ):
                self.cursor_controller.scroll(
                    scroll_delta
                )

            if self.on_tracking_update:
                self.on_tracking_update(tracking_data)

            return tracking_data, annotated_frame

        else:
            self.scroll_detector.reset()

        # 6E. Pinch & Drag vs Cursor
        is_pinched, click_triggered, is_dragging, pinch_dist = (
            self.pinch_detector.process(lms)
        )

        tracking_data.pinch_distance = pinch_dist

        # Map index fingertip to calibrated workspace
        self.cursor_gesture.set_calibration_bounds(
            self.calibration_manager.min_x,
            self.calibration_manager.min_y,
            self.calibration_manager.max_x,
            self.calibration_manager.max_y,
        )

        norm_cursor = self.cursor_gesture.extract_normalized_pos(
            lms
        )

        tracking_data.cursor_point = norm_cursor

        v_desk = self.display_manager.virtual_desktop

        # Determine if Pinch or Cursor
        if is_pinched:

            if is_dragging:
                self.active_gesture = GestureType.DRAG
                tracking_data.active_gesture = GestureType.DRAG
                tracking_data.status_message = (
                    "DRAG (MOUSE DOWN + MOVE)"
                )

            else:
                self.active_gesture = GestureType.PINCH
                tracking_data.active_gesture = GestureType.PINCH
                tracking_data.status_message = (
                    "PINCH (LEFT CLICK)"
                )

            if self.safety_controller.is_action_allowed():

                if click_triggered and not is_dragging:
                    # Discrete click
                    self.cursor_controller.click()

                elif is_dragging and norm_cursor:
                    # Maintain mouse down and update position
                    self.cursor_controller.mouse_down()

                    screen_coords = (
                        self.display_manager.map_normalized_to_target_screen(
                            norm_cursor[0],
                            norm_cursor[1],
                        )
                    )

                    if screen_coords:
                        self.cursor_controller.move_to(
                            screen_coords[0],
                            screen_coords[1],
                            v_desk.x_min,
                            v_desk.y_min,
                            v_desk.width,
                            v_desk.height,
                        )

        elif (
            fingers.index_extended
            and not fingers.middle_extended
            and not fingers.ring_extended
        ):
            # Clean release of any dragging
            if self.cursor_controller.is_dragging:
                self.cursor_controller.mouse_up()

            self.active_gesture = GestureType.CURSOR

            tracking_data.active_gesture = GestureType.CURSOR

            tracking_data.status_message = (
                "CURSOR (INDEX EXTENDED)"
            )

            if (
                self.safety_controller.is_action_allowed()
                and norm_cursor
            ):
                screen_coords = (
                    self.display_manager.map_normalized_to_target_screen(
                        norm_cursor[0],
                        norm_cursor[1],
                    )
                )

                if screen_coords:
                    self.cursor_controller.move_to(
                        screen_coords[0],
                        screen_coords[1],
                        v_desk.x_min,
                        v_desk.y_min,
                        v_desk.width,
                        v_desk.height,
                    )

        else:
            # Other neutral posture
            if self.cursor_controller.is_dragging:
                self.cursor_controller.mouse_up()

            self.active_gesture = GestureType.NONE
            tracking_data.active_gesture = GestureType.NONE

            tracking_data.status_message = (
                lock_feedback if lock_feedback else (
                    "ONLINE"
                    if self.safety_controller.is_enabled
                    else "STANDBY"
                )
            )

        if not self.safety_controller.is_enabled:
            tracking_data.status_message = (
                "STANDBY (F8 TO ACTIVATE)"
            )

        if self.on_tracking_update:
            self.on_tracking_update(tracking_data)

        return tracking_data, annotated_frame