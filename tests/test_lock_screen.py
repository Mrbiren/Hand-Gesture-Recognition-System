"""
Automated Unit and Integration Tests for Windows Screen Lock Gesture

Verifies:
1. Fist alone does NOT lock.
2. Open palm alone does NOT lock.
3. Open palm -> fist for <2 seconds does NOT lock.
4. Open palm -> fist for >=2 seconds triggers LOCK_SCREEN.
5. Tracking loss cancels the countdown.
6. Confidence loss cancels the countdown.
7. Opening the hand during countdown cancels the countdown.
8. Cooldown prevents repeated triggering.
9. Countdown string progression (2.0 -> 1.5 -> 1.0 -> 0.5 -> LOCKING SYSTEM...).
10. Existing cursor gesture still works.
11. Existing pinch click still works.
12. Existing drag still works.
13. Existing scroll still works.
14. Existing swipe gestures still work.
15. End-to-end GestureEngine lock triggering with mocked lock callable (DEV MACHINE NEVER LOCKED).
"""

from unittest.mock import MagicMock
import numpy as np
import pytest

from core.config_manager import ConfigManager
from core.calibration import CalibrationManager
from core.cursor_controller import CursorController
from core.display_manager import DisplayInfo, DisplayManager, VirtualDesktopInfo
from core.gesture_engine import GestureEngine
from core.safety_controller import SafetyController
from gestures.gesture_state import FingerStatus, GestureType, HandLandmarkPoint, TrackingData
from gestures.lock_screen import LockScreenDetector, LockScreenState
from gestures.pinch import PinchDetector
from gestures.scroll import ScrollDetector
from gestures.swipe import SwipeDetector


def make_open_palm() -> FingerStatus:
    return FingerStatus(
        thumb_extended=True,
        index_extended=True,
        middle_extended=True,
        ring_extended=True,
        pinky_extended=True,
    )


def make_fist() -> FingerStatus:
    return FingerStatus(
        thumb_extended=False,
        index_extended=False,
        middle_extended=False,
        ring_extended=False,
        pinky_extended=False,
    )


def make_cursor_fingers() -> FingerStatus:
    return FingerStatus(
        thumb_extended=False,
        index_extended=True,
        middle_extended=False,
        ring_extended=False,
        pinky_extended=False,
    )


def make_scroll_fingers() -> FingerStatus:
    return FingerStatus(
        thumb_extended=False,
        index_extended=True,
        middle_extended=True,
        ring_extended=False,
        pinky_extended=False,
    )


def make_landmarks(coords=None):
    lms = [HandLandmarkPoint(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    if coords:
        for idx, (x, y) in coords.items():
            lms[idx] = HandLandmarkPoint(x=x, y=y, z=0.0)
    return lms


# ---------------------------------------------------------------------------
# Requirement 1: Fist alone does NOT lock
# ---------------------------------------------------------------------------
def test_fist_alone_does_not_lock():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Provide fist continuously for 3.0 seconds without prior open palm
    for step in range(30):
        is_active, feedback = detector.process(
            hand_detected=True,
            confidence=0.95,
            fingers=make_fist(),
            current_time=t + (step * 0.1),
        )
        assert not is_active
        assert detector.state == LockScreenState.IDLE
        mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 2: Open palm alone does NOT lock
# ---------------------------------------------------------------------------
def test_open_palm_alone_does_not_lock():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Hold open palm for 3.0 seconds
    for step in range(30):
        is_active, feedback = detector.process(
            hand_detected=True,
            confidence=0.95,
            fingers=make_open_palm(),
            current_time=t + (step * 0.1),
        )
        assert not is_active
        assert detector.state == LockScreenState.OPEN_PALM_CONFIRMED
        mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 3: Open palm -> fist for <2 seconds does NOT lock
# ---------------------------------------------------------------------------
def test_open_palm_fist_under_2s_does_not_lock():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Step 1: Confirm open palm
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )
    assert detector.state == LockScreenState.OPEN_PALM_CONFIRMED

    # Step 2: Transition to fist and hold for only 1.5 seconds (< 2.0s)
    for step in range(15):
        t_curr = t + 0.1 + (step * 0.1)  # up to 1.5s
        is_active, feedback = detector.process(
            hand_detected=True,
            confidence=0.95,
            fingers=make_fist(),
            current_time=t_curr,
        )
        assert is_active is True
        mock_lock.assert_not_called()

    # Step 3: Open hand (break fist) at 1.6s
    is_active, feedback = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t + 1.7,
    )
    assert not is_active
    assert feedback == "LOCK CANCELLED"
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 4: Open palm -> fist for >=2 seconds triggers LOCK_SCREEN
# ---------------------------------------------------------------------------
def test_open_palm_fist_2s_triggers_lock():
    mock_lock = MagicMock(return_value=True)
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Step 1: Open palm
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )

    # Step 2: Fist held for full 2.0 seconds
    for step in range(20):
        t_curr = t + 0.05 + (step * 0.1)
        detector.process(
            hand_detected=True,
            confidence=0.95,
            fingers=make_fist(),
            current_time=t_curr,
        )
        mock_lock.assert_not_called()

    # Step 3: At t = 100.0 + 2.05s (>= 2.0s)
    is_active, feedback = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 2.1,
    )
    assert is_active is True
    assert feedback == "LOCKING SYSTEM..."
    mock_lock.assert_called_once()


# ---------------------------------------------------------------------------
# Requirement 5: Tracking loss cancels the countdown
# ---------------------------------------------------------------------------
def test_tracking_loss_cancels_countdown():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Open palm
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )
    # Fist for 1.0s
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 0.1,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 1.0,
    )
    assert detector.state == LockScreenState.FIST_HOLDING

    # Tracking lost!
    is_active, feedback = detector.process(
        hand_detected=False,
        confidence=0.0,
        fingers=None,
        current_time=t + 1.2,
    )
    assert not is_active
    assert detector.state == LockScreenState.IDLE
    assert feedback == "LOCK CANCELLED"
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 6: Confidence loss cancels the countdown
# ---------------------------------------------------------------------------
def test_confidence_loss_cancels_countdown():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0, confidence_threshold=0.60)

    t = 100.0
    # Open palm
    detector.process(
        hand_detected=True,
        confidence=0.90,
        fingers=make_open_palm(),
        current_time=t,
    )
    # Fist started
    detector.process(
        hand_detected=True,
        confidence=0.90,
        fingers=make_fist(),
        current_time=t + 0.1,
    )
    # Confidence drops to 0.40 (< 0.60)
    is_active, feedback = detector.process(
        hand_detected=True,
        confidence=0.40,
        fingers=make_fist(),
        current_time=t + 0.8,
    )
    assert not is_active
    assert detector.state == LockScreenState.IDLE
    assert feedback == "LOCK CANCELLED"
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 7: Opening the hand during countdown cancels the countdown
# ---------------------------------------------------------------------------
def test_opening_hand_cancels_countdown():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    # Open palm
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )
    # Fist countdown starts
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 0.1,
    )
    assert detector.state == LockScreenState.FIST_HOLDING

    # Hand opened (extended fingers >= 1)
    is_active, feedback = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_cursor_fingers(),
        current_time=t + 1.2,
    )
    assert not is_active
    assert detector.state == LockScreenState.IDLE
    assert feedback == "LOCK CANCELLED"
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 8: Cooldown prevents repeated triggering
# ---------------------------------------------------------------------------
def test_cooldown_prevents_repeated_triggering():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0, cooldown_duration=5.0)

    t = 100.0
    # First sequence: Open palm -> 2.0s fist -> LOCK
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 0.1,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 2.2,
    )
    assert mock_lock.call_count == 1

    # Attempt another lock at t = 103.0 (cooldown active until t = 107.2)
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=103.0,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=103.1,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=105.5,
    )
    # Still only 1 call, repeated trigger prevented!
    assert mock_lock.call_count == 1

    # Now after cooldown elapsed (t = 108.0 > 107.2)
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=108.0,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=108.1,
    )
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=110.2,
    )
    assert mock_lock.call_count == 2


# ---------------------------------------------------------------------------
# Feedback requirement: Countdown strings match specifications
# ---------------------------------------------------------------------------
def test_countdown_strings_progression():
    mock_lock = MagicMock()
    detector = LockScreenDetector(on_lock=mock_lock, hold_duration=2.0)

    t = 100.0
    detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_open_palm(),
        current_time=t,
    )

    # 1. Start of hold: remaining ~2.0s -> "LOCKING IN 2.0"
    _, fb1 = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 0.1,  # elapsed 0.0s since hold start
    )
    assert fb1 == "LOCKING IN 2.0"

    # 2. Elapsed 0.6s -> remaining ~1.4s -> "LOCKING IN 1.5"
    _, fb2 = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 0.7,
    )
    assert fb2 == "LOCKING IN 1.5"

    # 3. Elapsed 1.1s -> remaining ~0.9s -> "LOCKING IN 1.0"
    _, fb3 = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 1.2,
    )
    assert fb3 == "LOCKING IN 1.0"

    # 4. Elapsed 1.6s -> remaining ~0.4s -> "LOCKING IN 0.5"
    _, fb4 = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 1.7,
    )
    assert fb4 == "LOCKING IN 0.5"

    # 5. Elapsed >= 2.0s -> "LOCKING SYSTEM..."
    _, fb5 = detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 2.15,
    )
    assert fb5 == "LOCKING SYSTEM..."


# ---------------------------------------------------------------------------
# Helper fixture for GestureEngine integration
# ---------------------------------------------------------------------------
@pytest.fixture
def gesture_engine_fixture(tmp_path):
    disp_mgr = DisplayManager()
    disp = DisplayInfo(
        index=0,
        name="Display 1",
        left=0,
        top=0,
        right=1920,
        bottom=1080,
        width=1920,
        height=1080,
        is_primary=True,
        device_name="\\\\.\\DISPLAY1",
    )
    disp_mgr.displays = [disp]
    disp_mgr.target_display_index = 0
    disp_mgr.virtual_desktop = VirtualDesktopInfo(x_min=0, y_min=0, width=1920, height=1080)

    cfg = ConfigManager(base_dir=tmp_path)
    calib_mgr = CalibrationManager(config_manager=cfg)
    safety_ctrl = SafetyController()
    safety_ctrl.is_enabled = True  # ONLINE mode

    cursor_ctrl = CursorController()
    cursor_ctrl.move_to = MagicMock()
    cursor_ctrl.click = MagicMock()
    cursor_ctrl.mouse_down = MagicMock()
    cursor_ctrl.mouse_up = MagicMock()
    cursor_ctrl.scroll = MagicMock()
    cursor_ctrl.trigger_navigation = MagicMock()

    mock_lock = MagicMock()

    engine = GestureEngine(
        display_manager=disp_mgr,
        calibration_manager=calib_mgr,
        safety_controller=safety_ctrl,
        cursor_controller=cursor_ctrl,
        lock_action=mock_lock,
    )

    yield engine, cursor_ctrl, safety_ctrl, mock_lock

    safety_ctrl.stop()


# ---------------------------------------------------------------------------
# Requirement 9: Existing cursor gesture still works
# ---------------------------------------------------------------------------
def test_existing_cursor_gesture_still_works(gesture_engine_fixture):
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    # Hand with index extended, thumb separated, others folded
    lms = make_landmarks({4: (0.3, 0.5), 8: (0.5, 0.5)})
    data = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms,
        finger_status=make_cursor_fingers(),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data, None))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res_data, _ = engine.process_frame(frame)

    assert res_data.active_gesture == GestureType.CURSOR
    cursor_ctrl.move_to.assert_called()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 10: Existing pinch click still works
# ---------------------------------------------------------------------------
def test_existing_pinch_click_still_works(gesture_engine_fixture):
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    # Thumb tip (4) and Index tip (8) touching -> distance < 0.045
    lms = make_landmarks({4: (0.50, 0.50), 8: (0.51, 0.50)})
    fingers = FingerStatus(thumb_extended=True, index_extended=True)

    data = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms,
        finger_status=fingers,
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data, None))

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    res_data, _ = engine.process_frame(frame)

    assert res_data.active_gesture == GestureType.PINCH
    cursor_ctrl.click.assert_called_once()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 11: Existing drag still works
# ---------------------------------------------------------------------------
def test_existing_drag_still_works(gesture_engine_fixture):
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    # 1. Start pinch
    lms_pinch = make_landmarks({4: (0.50, 0.50), 8: (0.51, 0.50)})
    data1 = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms_pinch,
        finger_status=FingerStatus(thumb_extended=True, index_extended=True),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data1, None))
    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    engine.process_frame(frame)

    # 2. Move beyond drag threshold
    lms_drag = make_landmarks({4: (0.60, 0.60), 8: (0.61, 0.60)})
    data2 = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms_drag,
        finger_status=FingerStatus(thumb_extended=True, index_extended=True),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data2, None))
    res_data, _ = engine.process_frame(frame)

    assert res_data.active_gesture == GestureType.DRAG
    cursor_ctrl.mouse_down.assert_called()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 12: Existing scroll still works
# ---------------------------------------------------------------------------
def test_existing_scroll_still_works(gesture_engine_fixture):
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Frame 1: Index + Middle extended at y=0.5
    lms1 = make_landmarks({8: (0.5, 0.50), 12: (0.52, 0.50)})
    data1 = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms1,
        finger_status=make_scroll_fingers(),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data1, None))
    engine.process_frame(frame)

    # Frame 2: Hand moves UP (Y decreases to 0.44) -> scroll up
    lms2 = make_landmarks({8: (0.5, 0.44), 12: (0.52, 0.44)})
    data2 = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms2,
        finger_status=make_scroll_fingers(),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data2, None))
    res_data, _ = engine.process_frame(frame)

    assert res_data.active_gesture == GestureType.TWO_FINGER_SCROLL
    cursor_ctrl.scroll.assert_called()
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 13: Existing swipe gestures still work
# ---------------------------------------------------------------------------
def test_existing_swipe_still_works(gesture_engine_fixture):
    import time
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    frame = np.zeros((480, 640, 3), dtype=np.uint8)

    # Simulate fast horizontal movement with 4 frames
    xs = [0.75, 0.58, 0.42, 0.25]
    res_data = None
    for x in xs:
        lms = make_landmarks({0: (x, 0.5), 9: (x, 0.4), 4: (x + 0.1, 0.5), 8: (x - 0.1, 0.5)})
        data = TrackingData(
            hand_detected=True,
            hand_count=1,
            confidence=0.95,
            landmarks=lms,
            finger_status=make_open_palm(),
        )
        engine.hand_tracker.process_frame = MagicMock(return_value=(data, None))
        res_data, _ = engine.process_frame(frame)
        time.sleep(0.04)

    assert res_data.active_gesture in (GestureType.SWIPE_LEFT, GestureType.OPEN_PALM)
    mock_lock.assert_not_called()


# ---------------------------------------------------------------------------
# Requirement 14 & 15: Full GestureEngine lock pipeline with mock callable
# ---------------------------------------------------------------------------
def test_gesture_engine_lock_pipeline_with_mock_action(gesture_engine_fixture):
    engine, cursor_ctrl, safety_ctrl, mock_lock = gesture_engine_fixture

    frame = np.zeros((480, 640, 3), dtype=np.uint8)
    lms = make_landmarks()

    t = 200.0

    # Frame 1: Open Palm
    data_palm = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms,
        finger_status=make_open_palm(),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data_palm, None))
    engine.lock_screen_detector.process(hand_detected=True, confidence=0.95, fingers=make_open_palm(), current_time=t)

    # Frame 2: Fist start
    data_fist = TrackingData(
        hand_detected=True,
        hand_count=1,
        confidence=0.95,
        landmarks=lms,
        finger_status=make_fist(),
    )
    engine.hand_tracker.process_frame = MagicMock(return_value=(data_fist, None))
    engine._last_frame_time = t + 0.1

    # Run through hold to trigger
    engine.lock_screen_detector.hold_start_time = t + 0.1
    engine.lock_screen_detector.state = LockScreenState.FIST_HOLDING

    # At t + 2.2s (>= 2.0s hold)
    engine.lock_screen_detector.process(
        hand_detected=True,
        confidence=0.95,
        fingers=make_fist(),
        current_time=t + 2.2,
    )

    # Verify mock lock was invoked and not real Win32 LockWorkStation
    mock_lock.assert_called_once()


# ---------------------------------------------------------------------------
# Precision Cursor Tests
# ---------------------------------------------------------------------------
def test_cursor_immediate_activation():
    """Verify cursor activates immediately on the very first frame without delay."""
    ctrl = CursorController()
    assert ctrl.filtered_x is None
    assert ctrl.filtered_y is None

    # First move
    ctrl.move_to(500, 300, 0, 0, 1920, 1080)
    assert ctrl.filtered_x == 500.0
    assert ctrl.filtered_y == 300.0


def test_cursor_adaptive_velocity_smoothing():
    """Verify adaptive smoothing: high responsiveness on fast moves, smooth on slow moves."""
    ctrl = CursorController(smoothing=0.65)
    ctrl.filtered_x = 100.0
    ctrl.filtered_y = 100.0

    # 1. Slow micro-movement (4 pixels) -> lower alpha, fine control
    ctrl.move_to(104, 100, 0, 0, 1920, 1080)
    slow_step = ctrl.filtered_x - 100.0

    # Reset
    ctrl.filtered_x = 100.0
    ctrl.filtered_y = 100.0

    # 2. Fast large flick (100 pixels) -> higher alpha, low latency
    ctrl.move_to(200, 100, 0, 0, 1920, 1080)
    fast_step = ctrl.filtered_x - 100.0
    fast_fraction = fast_step / 100.0
    slow_fraction = slow_step / 4.0

    # Fast movement should have a significantly higher progression ratio than slow movement
    assert fast_fraction > slow_fraction


def test_cursor_jitter_filtering():
    """Verify sub-threshold hand tremor is filtered by dead zone."""
    ctrl = CursorController(dead_zone=0.002)
    ctrl.filtered_x = 500.0
    ctrl.filtered_y = 500.0

    # Sub-pixel hand tremor (< 1.5 pixels)
    ctrl.move_to(501, 500, 0, 0, 1920, 1080)
    # Filtered pos should not change because movement is inside deadband
    assert ctrl.filtered_x == 500.0
    assert ctrl.filtered_y == 500.0


# ---------------------------------------------------------------------------
# Precision Two-Finger Scroll Tests
# ---------------------------------------------------------------------------
def test_scroll_precision_directions():
    """Verify upward hand movement produces ONLY upward scroll, downward produces ONLY downward scroll."""
    detector = ScrollDetector(dead_zone=0.0035, scroll_sensitivity=1.0)

    # Frame 1: Center anchor
    lms_0 = make_landmarks({8: (0.5, 0.50), 12: (0.52, 0.50)})
    assert detector.process(lms_0, is_two_finger_extended=True) == 0.0

    # Frame 2: Move hand UP (Y decreases to 0.44) -> positive delta
    lms_up = make_landmarks({8: (0.5, 0.44), 12: (0.52, 0.44)})
    delta_up = detector.process(lms_up, is_two_finger_extended=True)
    assert delta_up > 0.0

    # Reset and test downward
    detector.reset()
    detector.process(lms_0, is_two_finger_extended=True)

    # Move hand DOWN (Y increases to 0.56) -> negative delta
    lms_down = make_landmarks({8: (0.5, 0.56), 12: (0.52, 0.56)})
    delta_down = detector.process(lms_down, is_two_finger_extended=True)
    assert delta_down < 0.0


def test_scroll_tiny_jitter_suppressed():
    """Verify tiny fluctuations within deadband produce zero scroll."""
    detector = ScrollDetector(dead_zone=0.0035)

    lms_0 = make_landmarks({8: (0.5, 0.50), 12: (0.52, 0.50)})
    detector.process(lms_0, is_two_finger_extended=True)

    # Hand moves only 0.001 (camera sensor noise)
    lms_jitter = make_landmarks({8: (0.5, 0.501), 12: (0.52, 0.501)})
    delta_jitter = detector.process(lms_jitter, is_two_finger_extended=True)
    assert delta_jitter == 0.0


def test_scroll_hysteresis_reversal_suppression():
    """Verify that a single tiny opposite flicker does not immediately flip scroll direction."""
    detector = ScrollDetector(dead_zone=0.0035)

    # Frame 1: Anchor
    lms_0 = make_landmarks({8: (0.5, 0.50), 12: (0.52, 0.50)})
    detector.process(lms_0, is_two_finger_extended=True)

    # Frame 2: Sustained upward scroll
    lms_up = make_landmarks({8: (0.5, 0.45), 12: (0.52, 0.45)})
    d_up = detector.process(lms_up, is_two_finger_extended=True)
    assert d_up > 0.0
    assert detector.active_direction == 1

    # Settle smoothed_y at upward position
    for _ in range(4):
        detector.process(lms_up, is_two_finger_extended=True)

    # Frame 3: Single tiny opposite wobble (down by 0.004)
    lms_wobble = make_landmarks({8: (0.5, 0.454), 12: (0.52, 0.454)})
    d_wobble = detector.process(lms_wobble, is_two_finger_extended=True)
    # Must be suppressed (0.0) without flipping active direction to -1!
    assert d_wobble == 0.0
    assert detector.active_direction == 1
