"""
CryNet Local Hand Tracker

Wraps MediaPipe Hands for 100% offline, low-latency landmark tracking.

Computes finger extension states, multiple-hand detection, and visualizes
landmarks with a sleek futuristic HUD aesthetic.
"""

from __future__ import annotations

import logging
import math
from typing import List, Optional, Tuple

import cv2
import numpy as np

from gestures.gesture_state import (
    FingerStatus,
    HandLandmarkPoint,
    TrackingData,
)

logger = logging.getLogger("CryNet.HandTracker")


class HandTracker:
    """Performs offline hand landmark detection using MediaPipe Hands."""

    def __init__(
        self,
        max_num_hands: int = 2,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
        model_complexity: int = 0,
    ):
        self.max_num_hands = max_num_hands
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence
        self.model_complexity = model_complexity

        self.mp_hands = None
        self.hands = None
        self.mp_draw = None

        self._init_mediapipe()

    def _init_mediapipe(self) -> None:
        """Initializes local MediaPipe Hands pipeline without network calls."""
        try:
            import mediapipe as mp

            # CryNet currently uses MediaPipe's legacy Hands Solution API.
            # MediaPipe 1.x no longer exposes mp.solutions.hands.
            solutions = getattr(mp, "solutions", None)

            if solutions is None or not hasattr(solutions, "hands"):
                version = getattr(mp, "__version__", "unknown")
                raise RuntimeError(
                    f"Unsupported MediaPipe {version}. CryNet requires "
                    "MediaPipe 0.10.21 because it uses mp.solutions.hands. "
                    "Reinstall from requirements.txt and rebuild CryNet."
                )

            self.mp_hands = solutions.hands
            self.mp_draw = solutions.drawing_utils

            self.hands = self.mp_hands.Hands(
                static_image_mode=False,
                max_num_hands=self.max_num_hands,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence,
                model_complexity=self.model_complexity,
            )

            logger.info("MediaPipe Hands initialized locally.")

        except Exception as e:
            logger.error(f"Failed to initialize MediaPipe Hands: {e}")
            self.hands = None

    def process_frame(
        self,
        frame_bgr: np.ndarray,
    ) -> Tuple[TrackingData, Optional[np.ndarray]]:
        """
        Processes a BGR webcam frame.

        Returns:
            (TrackingData, annotated_bgr_frame)
        """

        data = TrackingData()

        if self.hands is None or frame_bgr is None:
            return data, frame_bgr

        # Validate frame shape before processing.
        if frame_bgr.ndim != 3 or frame_bgr.shape[2] != 3:
            logger.warning("Invalid camera frame shape: %s", frame_bgr.shape)
            return data, frame_bgr

        h, w, c = frame_bgr.shape

        # Convert BGR to RGB for MediaPipe.
        frame_rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        frame_rgb.flags.writeable = False

        try:
            results = self.hands.process(frame_rgb)

        except Exception as e:
            logger.error(f"Error during MediaPipe process: {e}")
            return data, frame_bgr

        # No hand detected.
        if not results.multi_hand_landmarks:
            data.hand_detected = False
            data.hand_count = 0
            return data, frame_bgr

        data.hand_count = len(results.multi_hand_landmarks)
        data.hand_detected = True

        # Safety: Multiple hands detected.
        if data.hand_count > 1:
            data.is_paused = True
            data.status_message = "TWO HANDS DETECTED — PAUSED"

            annotated = self._draw_warning_overlay(
                frame_bgr,
                results.multi_hand_landmarks,
            )

            return data, annotated

        # Process primary hand.
        primary_hand = results.multi_hand_landmarks[0]

        # MediaPipe handedness confidence.
        confidence = 0.90

        if (
            results.multi_handedness
            and len(results.multi_handedness) > 0
            and results.multi_handedness[0].classification
        ):
            confidence = float(
                results.multi_handedness[0].classification[0].score
            )

        data.confidence = confidence

        # ---------------------------------------------------------
        # Extract exactly 21 landmarks.
        #
        # MediaPipe Hands normally returns 21 landmarks. However,
        # defensively reject malformed/incomplete landmark data so
        # downstream code can never crash on indexes such as [8],
        # [12], [16], or [20].
        # ---------------------------------------------------------

        raw_landmarks = getattr(primary_hand, "landmark", None)

        if raw_landmarks is None or len(raw_landmarks) < 21:
            count = 0 if raw_landmarks is None else len(raw_landmarks)

            logger.warning(
                "Incomplete hand landmarks received: %d/21",
                count,
            )

            data.hand_detected = False
            data.hand_count = 0
            data.landmarks = []
            data.status_message = "INCOMPLETE HAND LANDMARK DATA"

            return data, frame_bgr

        landmarks: List[HandLandmarkPoint] = []

        for lm in raw_landmarks[:21]:
            landmarks.append(
                HandLandmarkPoint(
                    x=float(lm.x),
                    y=float(lm.y),
                    z=float(lm.z),
                )
            )

        # Final defensive check.
        if len(landmarks) != 21:
            logger.warning(
                "Landmark conversion produced %d/21 points",
                len(landmarks),
            )

            data.hand_detected = False
            data.hand_count = 0
            data.landmarks = []
            data.status_message = "INVALID LANDMARK DATA"

            return data, frame_bgr

        data.landmarks = landmarks

        # Determine finger extension statuses.
        data.finger_status = self._calculate_finger_status(landmarks)

        # Draw futuristic HUD overlay on frame.
        annotated = self._draw_futuristic_hand(
            frame_bgr,
            landmarks,
            data.finger_status,
        )

        return data, annotated

    def _dist(
        self,
        p1: HandLandmarkPoint,
        p2: HandLandmarkPoint,
    ) -> float:
        """Returns 2D Euclidean distance between two landmarks."""
        return math.hypot(
            p1.x - p2.x,
            p1.y - p2.y,
        )

    def _calculate_finger_status(
        self,
        lms: List[HandLandmarkPoint],
    ) -> FingerStatus:
        """
        Determines whether each finger is extended or folded.

        Uses distance from wrist to fingertip versus the PIP joint.
        Requires the complete MediaPipe 21-landmark hand model.
        """

        status = FingerStatus()

        # Defensive guard against malformed landmark data.
        if len(lms) < 21:
            logger.warning(
                "Cannot calculate finger status: only %d/21 landmarks",
                len(lms),
            )
            return status

        wrist = lms[0]

        # Index: Tip (8) vs PIP (6)
        status.index_extended = (
            self._dist(wrist, lms[8])
            > self._dist(wrist, lms[6]) * 1.15
        )

        # Middle: Tip (12) vs PIP (10)
        status.middle_extended = (
            self._dist(wrist, lms[12])
            > self._dist(wrist, lms[10]) * 1.15
        )

        # Ring: Tip (16) vs PIP (14)
        status.ring_extended = (
            self._dist(wrist, lms[16])
            > self._dist(wrist, lms[14]) * 1.15
        )

        # Pinky: Tip (20) vs PIP (18)
        status.pinky_extended = (
            self._dist(wrist, lms[20])
            > self._dist(wrist, lms[18]) * 1.15
        )

        # Thumb: Tip (4) relative to Pinky MCP (17)
        # versus Thumb MCP (2) relative to Pinky MCP (17).
        status.thumb_extended = (
            self._dist(lms[4], lms[17])
            > self._dist(lms[2], lms[17]) * 1.2
        )

        return status

    def _draw_futuristic_hand(
        self,
        frame: np.ndarray,
        lms: List[HandLandmarkPoint],
        fingers: FingerStatus,
    ) -> np.ndarray:
        """Renders futuristic cyber HUD hand skeletal lines and glowing nodes."""

        # Defensive guard.
        if len(lms) < 21:
            logger.warning(
                "Cannot draw hand HUD: only %d/21 landmarks",
                len(lms),
            )
            return frame.copy()

        h, w, _ = frame.shape
        img = frame.copy()

        # Futuristic color scheme.
        # OpenCV uses BGR.
        CYAN = (255, 229, 0)       # #00E5FF
        TEAL = (216, 180, 0)       # #00B4D8
        GLOW = (255, 255, 255)
        ACCENT = (50, 200, 255)

        # Connection bones.
        connections = [
            # Thumb
            (0, 1),
            (1, 2),
            (2, 3),
            (3, 4),

            # Index
            (0, 5),
            (5, 6),
            (6, 7),
            (7, 8),

            # Middle
            (5, 9),
            (9, 10),
            (10, 11),
            (11, 12),

            # Ring
            (9, 13),
            (13, 14),
            (14, 15),
            (15, 16),

            # Pinky
            (13, 17),
            (17, 18),
            (18, 19),
            (19, 20),

            # Palm base
            (0, 17),
        ]

        coords = [
            (int(p.x * w), int(p.y * h))
            for p in lms
        ]

        # Draw technical bones.
        for p1_idx, p2_idx in connections:
            pt1 = coords[p1_idx]
            pt2 = coords[p2_idx]

            cv2.line(
                img,
                pt1,
                pt2,
                TEAL,
                1,
                cv2.LINE_AA,
            )

        # Draw joint nodes.
        for idx, (px, py) in enumerate(coords):

            # Fingertip nodes.
            if idx in (4, 8, 12, 16, 20):

                cv2.circle(
                    img,
                    (px, py),
                    5,
                    CYAN,
                    -1,
                    cv2.LINE_AA,
                )

                cv2.circle(
                    img,
                    (px, py),
                    7,
                    GLOW,
                    1,
                    cv2.LINE_AA,
                )

            else:

                cv2.circle(
                    img,
                    (px, py),
                    3,
                    TEAL,
                    -1,
                    cv2.LINE_AA,
                )

        # Highlight index fingertip for cursor control.
        ix, iy = coords[8]

        if fingers.index_extended:

            # Concentric futuristic HUD reticle.
            cv2.circle(
                img,
                (ix, iy),
                12,
                CYAN,
                1,
                cv2.LINE_AA,
            )

            cv2.circle(
                img,
                (ix, iy),
                18,
                CYAN,
                1,
                cv2.LINE_AA,
            )

            cv2.line(
                img,
                (ix - 22, iy),
                (ix - 14, iy),
                CYAN,
                1,
                cv2.LINE_AA,
            )

            cv2.line(
                img,
                (ix + 14, iy),
                (ix + 22, iy),
                CYAN,
                1,
                cv2.LINE_AA,
            )

            cv2.line(
                img,
                (ix, iy - 22),
                (ix, iy - 14),
                CYAN,
                1,
                cv2.LINE_AA,
            )

            cv2.line(
                img,
                (ix, iy + 14),
                (ix, iy + 22),
                CYAN,
                1,
                cv2.LINE_AA,
            )

        return img

    def _draw_warning_overlay(
        self,
        frame: np.ndarray,
        hands_lms: list,
    ) -> np.ndarray:
        """Draws warning markers when multiple hands are detected."""

        h, w, _ = frame.shape
        img = frame.copy()

        AMBER = (0, 165, 255)  # Orange/Amber BGR

        for hand_lms in hands_lms:

            raw_landmarks = getattr(hand_lms, "landmark", [])

            for lm in raw_landmarks:

                cx = int(lm.x * w)
                cy = int(lm.y * h)

                cv2.circle(
                    img,
                    (cx, cy),
                    3,
                    AMBER,
                    -1,
                )

        # Text banner.
        cv2.putText(
            img,
            "TWO HANDS DETECTED - PAUSED",
            (int(w * 0.15), 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            AMBER,
            2,
            cv2.LINE_AA,
        )

        return img