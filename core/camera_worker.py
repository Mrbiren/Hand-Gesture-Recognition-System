"""
CryNet Camera Worker Thread

Runs the camera capture loop and calls the GestureEngine in a dedicated
QThread.
"""

from __future__ import annotations

import logging
import time
from typing import List, Optional

import cv2
import numpy as np
from PySide6.QtCore import QObject, QThread, Signal

from core.gesture_engine import GestureEngine
from gestures.gesture_state import TrackingData

logger = logging.getLogger("CryNet.CameraWorker")


class CameraWorker(QThread):
    """Dedicated background thread capturing frames and running gesture inference."""

    frame_ready = Signal(np.ndarray, TrackingData)
    status_changed = Signal(str)
    camera_error = Signal(str)

    def __init__(
        self,
        gesture_engine: GestureEngine,
        parent: Optional[QObject] = None,
    ):
        super().__init__(parent)

        self.gesture_engine = gesture_engine
        self._is_running: bool = False

        # Camera settings
        self.camera_index: int = 0
        self.camera_width: int = 640
        self.camera_height: int = 480
        self.camera_fps: int = 30
        self.mirror: bool = True
        self.preview_enabled: bool = True
        self.debug_visualization: bool = True

        self.cap: Optional[cv2.VideoCapture] = None

    def configure(
        self,
        camera_index: int = 0,
        width: int = 640,
        height: int = 480,
        fps: int = 30,
        mirror: bool = True,
        preview_enabled: bool = True,
        debug_visualization: bool = True,
    ) -> None:
        self.camera_index = camera_index
        self.camera_width = width
        self.camera_height = height
        self.camera_fps = fps
        self.mirror = mirror
        self.preview_enabled = preview_enabled
        self.debug_visualization = debug_visualization

    @staticmethod
    def detect_available_cameras(max_tested: int = 4) -> List[int]:
        """Probes video capture indexes 0..max_tested to find connected cameras."""

        available = []

        for idx in range(max_tested):
            try:
                cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)

                if cap.isOpened():
                    ret, _ = cap.read()

                    if ret:
                        available.append(idx)

                    cap.release()

            except Exception:
                pass

        if not available:
            available.append(0)

        return available

    def run(self) -> None:
        """Main camera worker processing loop."""

        self._is_running = True

        logger.info("Camera worker thread started.")

        # ---------------------------------------------------------
        # Camera initialization
        # ---------------------------------------------------------

        logger.info(
            f"Opening camera index {self.camera_index} (MSMF/DirectShow)..."
        )

        # Prioritize native backend (MSMF) for 30 FPS performance, with DSHOW fallback
        self.cap = cv2.VideoCapture(self.camera_index)

        if not self.cap or not self.cap.isOpened():
            logger.info("Default backend failed, trying DirectShow...")
            self.cap = cv2.VideoCapture(
                self.camera_index,
                cv2.CAP_DSHOW,
            )

        if not self.cap or not self.cap.isOpened():
            err_msg = (
                f"Unable to access camera index "
                f"{self.camera_index}."
            )

            logger.error(err_msg)
            self.camera_error.emit(err_msg)

            self._is_running = False
            return

        # Camera configuration
        self.cap.set(
            cv2.CAP_PROP_FRAME_WIDTH,
            self.camera_width,
        )

        self.cap.set(
            cv2.CAP_PROP_FRAME_HEIGHT,
            self.camera_height,
        )

        self.cap.set(
            cv2.CAP_PROP_FPS,
            self.camera_fps,
        )

        # Set buffer size to 1 to eliminate frame lag
        self.cap.set(
            cv2.CAP_PROP_BUFFERSIZE,
            1,
        )

        actual_width = int(
            self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        )

        actual_height = int(
            self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        )

        actual_fps = self.cap.get(
            cv2.CAP_PROP_FPS
        )

        logger.info(
            f"Camera started: "
            f"{actual_width}x{actual_height} "
            f"@ {actual_fps:.1f} FPS"
        )

        # ---------------------------------------------------------
        # Main processing loop
        # ---------------------------------------------------------

        while self._is_running:

            ret, frame = self.cap.read()

            if not ret or frame is None:
                logger.warning(
                    "Camera frame read failed."
                )

                time.sleep(0.01)
                continue

            # Mirror camera for intuitive left/right movement.
            if self.mirror:
                frame = cv2.flip(
                    frame,
                    1,
                )

            try:
                # Process frame through local gesture engine.
                tracking_data, annotated_frame = (
                    self.gesture_engine.process_frame(
                        frame
                    )
                )

            except Exception as e:
                logger.exception(
                    "Gesture processing error: %s",
                    e,
                )

                continue

            # Frame to display in UI.
            if self.debug_visualization:
                display_frame = annotated_frame

            else:
                display_frame = frame

            if display_frame is None:
                display_frame = frame

            # Send processed frame + TrackingData to UI.
            if self.preview_enabled:

                self.frame_ready.emit(
                    display_frame,
                    tracking_data,
                )

            else:

                # Preview disabled.
                # Still send TrackingData so gesture control remains active.
                self.frame_ready.emit(
                    np.empty(
                        (0, 0, 3),
                        dtype=np.uint8,
                    ),
                    tracking_data,
                )

        # ---------------------------------------------------------
        # Cleanup
        # ---------------------------------------------------------

        if self.cap:

            self.cap.release()
            self.cap = None

        logger.info(
            "Camera capture loop stopped."
        )

    def stop(self) -> None:
        """Requests graceful thread exit."""

        logger.info(
            "Stopping camera worker..."
        )

        self._is_running = False

        self.wait(1500)

        logger.info(
            "Camera worker stopped."
        )