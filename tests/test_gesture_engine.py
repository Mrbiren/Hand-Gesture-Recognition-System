"""
Unit tests for CryNet Gesture Engine algorithms & detectors
"""

import pytest
from gestures.gesture_state import FingerStatus, HandLandmarkPoint
from gestures.pinch import PinchDetector
from gestures.scroll import ScrollDetector
from gestures.swipe import SwipeDetector


def make_mock_landmarks(coords):
    """Helper to generate 21 landmarks with specified points."""
    lms = [HandLandmarkPoint(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    for idx, (x, y) in coords.items():
        lms[idx] = HandLandmarkPoint(x=x, y=y, z=0.0)
    return lms


def test_pinch_click_and_release():
    detector = PinchDetector(pinch_threshold=0.05, drag_distance_threshold=0.03)

    # 1. Open fingers: Thumb tip (4) and Index tip (8) far apart
    lms_open = make_mock_landmarks({4: (0.4, 0.4), 8: (0.6, 0.6)})
    is_p, click, is_d, dist = detector.process(lms_open)
    assert not is_p
    assert not click
    assert not is_d

    # 2. Pinch starts: Thumb tip (4) and Index tip (8) touching (dist < 0.05)
    lms_pinch = make_mock_landmarks({4: (0.50, 0.50), 8: (0.52, 0.50)})
    is_p, click, is_d, dist = detector.process(lms_pinch)
    assert is_p is True
    assert click is True  # First contact fires click!
    assert not is_d

    # 3. Pinch remains static: should NOT fire additional clicks
    is_p2, click2, is_d2, dist2 = detector.process(lms_pinch)
    assert is_p2 is True
    assert click2 is False  # No repeated click!
    assert not is_d2

    # 4. Pinch moves beyond drag threshold: triggers drag
    lms_moved = make_mock_landmarks({4: (0.60, 0.60), 8: (0.62, 0.60)})
    is_p3, click3, is_d3, dist3 = detector.process(lms_moved)
    assert is_p3 is True
    assert is_d3 is True  # Drag active!

    # 5. Fingers release
    is_p4, click4, is_d4, dist4 = detector.process(lms_open)
    assert not is_p4
    assert not is_d4


def test_two_finger_scroll():
    detector = ScrollDetector(dead_zone=0.005, scroll_sensitivity=1.0)

    # First frame to initialize position
    lms_1 = make_mock_landmarks({8: (0.5, 0.5), 12: (0.52, 0.5)})
    d1 = detector.process(lms_1, is_two_finger_extended=True)
    assert d1 == 0.0

    # Hand moves UP (Y decreases to 0.46) -> Scrolling UP (positive delta)
    lms_up = make_mock_landmarks({8: (0.5, 0.46), 12: (0.52, 0.46)})
    d_up = detector.process(lms_up, is_two_finger_extended=True)
    assert d_up > 0.0

    # Hand moves DOWN (Y increases) -> Scrolling DOWN (negative delta)
    lms_down = make_mock_landmarks({8: (0.5, 0.52), 12: (0.52, 0.52)})
    d_down = detector.process(lms_down, is_two_finger_extended=True)
    assert d_down < 0.0


def test_swipe_detector():
    detector = SwipeDetector(velocity_threshold=0.5, distance_threshold=0.15)

    # Frame 1: center
    lms_0 = make_mock_landmarks({0: (0.5, 0.5), 9: (0.5, 0.4)})
    assert detector.process(lms_0, is_palm_or_open=True) is None

    # Simulating time-based swipe steps
    import time
    time.sleep(0.06)
    lms_1 = make_mock_landmarks({0: (0.42, 0.5), 9: (0.42, 0.4)})
    detector.process(lms_1, is_palm_or_open=True)

    time.sleep(0.06)
    lms_2 = make_mock_landmarks({0: (0.35, 0.5), 9: (0.35, 0.4)})
    detector.process(lms_2, is_palm_or_open=True)

    time.sleep(0.06)
    lms_3 = make_mock_landmarks({0: (0.25, 0.5), 9: (0.25, 0.4)})
    res = detector.process(lms_3, is_palm_or_open=True)
    # Displacement from 0.5 to 0.25 is left
    assert res == "left"


def test_cursor_gesture_bounds():
    from gestures.cursor import CursorGesture
    cg = CursorGesture()
    cg.set_calibration_bounds(0.2, 0.2, 0.8, 0.8)

    # Center (0.5, 0.5)
    lms_center = make_mock_landmarks({8: (0.5, 0.5)})
    nx, ny = cg.extract_normalized_pos(lms_center)
    assert nx == pytest.approx(0.5, abs=0.01)
    assert ny == pytest.approx(0.5, abs=0.01)

    # Top-left bound (0.2, 0.2) maps to (0.0, 0.0)
    lms_tl = make_mock_landmarks({8: (0.2, 0.2)})
    nx0, ny0 = cg.extract_normalized_pos(lms_tl)
    assert nx0 == pytest.approx(0.0, abs=0.01)
    assert ny0 == pytest.approx(0.0, abs=0.01)

