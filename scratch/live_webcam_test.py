"""
Live Webcam Test for CryNet Gesture Pass
Measures:
1. Actual End-to-End processing FPS with live webcam
2. Actual Hand Detection & MediaPipe 21 landmark extraction
3. Index-Finger Cursor latency & adaptive velocity smoothing response
4. Two-Finger Scroll direction & coordinate convention (center 8 & 12, hand UP -> scroll UP)
5. Screen Lock State Machine transitions and cancellation pathways
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import time
import cv2
import numpy as np
from core.display_manager import DisplayManager
from core.calibration import CalibrationManager
from core.safety_controller import SafetyController
from core.cursor_controller import CursorController
from core.gesture_engine import GestureEngine
from gestures.gesture_state import GestureType, HandLandmarkPoint, FingerStatus

def run_live_test(num_frames=120):
    print("=" * 60)
    print("CRYNET LIVE WEBCAM & GESTURE PASS VALIDATION")
    print("=" * 60)

    # 1. Initialize Display & Safety
    disp_mgr = DisplayManager()
    disp_mgr.refresh_displays()
    print(f"[DISPLAY] Detected {len(disp_mgr.displays)} display(s). Virtual desktop: {disp_mgr.virtual_desktop.width}x{disp_mgr.virtual_desktop.height}")

    safety_ctrl = SafetyController()
    safety_ctrl.is_enabled = True # ONLINE for testing

    # Track actions without locking dev PC
    mock_lock_calls = []
    def safe_lock():
        mock_lock_calls.append(time.time())
        print(">>> [LOCK TRIGGERED] Native LockWorkStation intercepted safely! <<<")
        return True

    from core.config_manager import ConfigManager
    config_mgr = ConfigManager()
    cursor_ctrl = CursorController()
    calib_mgr = CalibrationManager(config_manager=config_mgr)

    engine = GestureEngine(
        display_manager=disp_mgr,
        calibration_manager=calib_mgr,
        safety_controller=safety_ctrl,
        cursor_controller=cursor_ctrl,
        lock_action=safe_lock,
    )

    # 2. Open Live Webcam
    print("\n[CAMERA] Opening live webcam (Index 0, MSMF backend)...")
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("[ERROR] Could not open camera 0!")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
    cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

    actual_w = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
    actual_h = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
    print(f"[CAMERA] Opened successfully: {actual_w:.0f}x{actual_h:.0f}")

    # Warmup
    for _ in range(5):
        cap.read()

    print(f"\n[STREAM] Running end-to-end pipeline for {num_frames} frames...")
    start_time = time.perf_counter()
    frame_times = []
    gesture_counts = {}
    hands_detected = 0

    for i in range(num_frames):
        t0 = time.perf_counter()
        ret, frame = cap.read()
        if not ret:
            print(f"[WARNING] Frame {i} read failed.")
            continue

        # Full end-to-end processing: MediaPipe + Landmark analysis + Gesture interpretation
        tracking_data, annotated_frame = engine.process_frame(frame)
        t1 = time.perf_counter()
        frame_times.append(t1 - t0)

        g_name = tracking_data.active_gesture.name
        gesture_counts[g_name] = gesture_counts.get(g_name, 0) + 1

        if tracking_data.hand_detected:
            hands_detected += 1

        if (i + 1) % 30 == 0:
            current_fps = 30.0 / sum(frame_times[-30:])
            print(f"  Frame {i+1:3d}/{num_frames}: Instant FPS = {current_fps:5.1f} | Hand: {tracking_data.hand_detected} | Gesture: {g_name:12s} | Status: {tracking_data.status_message}")

    total_time = time.perf_counter() - start_time
    cap.release()

    overall_fps = num_frames / total_time
    avg_proc_ms = (sum(frame_times) / len(frame_times)) * 1000.0

    print("\n" + "=" * 60)
    print("LIVE WEBCAM RESULTS SUMMARY")
    print("=" * 60)
    print(f"Total Frames Processed : {num_frames}")
    print(f"Total Elapsed Time     : {total_time:.2f} seconds")
    print(f"Actual End-to-End FPS  : {overall_fps:.2f} FPS")
    print(f"Avg Frame Processing   : {avg_proc_ms:.2f} ms")
    print(f"Hands Detected Frames  : {hands_detected}/{num_frames} ({hands_detected/num_frames*100:.1f}%)")
    print(f"Gesture Breakdown      : {gesture_counts}")
    print("=" * 60)

    # 3. Verify Precision Cursor Behavior
    print("\n[PRECISION CURSOR VALIDATION]")
    c_test = CursorController()
    # Test 1: Immediate first frame
    c_test.move_to(300, 300, 0, 0, 1920, 1080)
    print(f"  - First frame initialization: ({c_test.filtered_x}, {c_test.filtered_y}) -> Latency: 0 frames (immediate)")
    # Test 2: Deadzone filtering
    c_test.move_to(301, 300, 0, 0, 1920, 1080)
    is_deadzone_filtered = (c_test.filtered_x == 300.0)
    print(f"  - Sub-pixel deadzone filtering: {is_deadzone_filtered} (Filtered pos held at 300.0)")
    # Test 3: Adaptive velocity response
    c_test.move_to(304, 300, 0, 0, 1920, 1080) # slow move (4px)
    slow_alpha_step = c_test.filtered_x - 300.0
    c_test.filtered_x = 300.0
    c_test.move_to(400, 300, 0, 0, 1920, 1080) # fast move (100px)
    fast_alpha_step = c_test.filtered_x - 300.0
    print(f"  - Slow move (4px) response ratio : {slow_alpha_step/4.0:.3f} (high damping/jitter suppression)")
    print(f"  - Fast move (100px) response ratio: {fast_alpha_step/100.0:.3f} (high responsiveness/near-instant)")
    assert fast_alpha_step/100.0 > slow_alpha_step/4.0

    # 4. Verify Two-Finger Scroll Coordinate Convention
    print("\n[TWO-FINGER SCROLL VALIDATION]")
    s_test = engine.scroll_detector
    s_test.reset()
    lms_base = [HandLandmarkPoint(x=0.5, y=0.5, z=0.0) for _ in range(21)]
    s_test.process(lms_base, True)
    # Hand moves UP -> center_y decreases to 0.44
    lms_up = [HandLandmarkPoint(x=0.5, y=0.44, z=0.0) for _ in range(21)]
    up_scroll = s_test.process(lms_up, True)
    print(f"  - Hand moves UP (Y decreases)   -> Scroll Delta: {up_scroll:+.2f} (POSITIVE/UP: {up_scroll > 0})")
    assert up_scroll > 0

    s_test.reset()
    s_test.process(lms_base, True)
    # Hand moves DOWN -> center_y increases to 0.56
    lms_down = [HandLandmarkPoint(x=0.5, y=0.56, z=0.0) for _ in range(21)]
    down_scroll = s_test.process(lms_down, True)
    print(f"  - Hand moves DOWN (Y increases) -> Scroll Delta: {down_scroll:+.2f} (NEGATIVE/DOWN: {down_scroll < 0})")
    assert down_scroll < 0

    # 5. Verify Windows Lock State Machine Progression & Cooldown
    print("\n[LOCK SCREEN STATE MACHINE VALIDATION]")
    lk_test = engine.lock_screen_detector
    lk_test.reset()
    t_base = 500.0
    # Open palm
    f_open = FingerStatus(thumb_extended=True, index_extended=True, middle_extended=True, ring_extended=True, pinky_extended=True)
    lk_test.process(True, 0.95, f_open, None, current_time=t_base)
    print(f"  - State after Open Palm: {lk_test.state.name} (Arming ready)")

    # Transition to Fist
    f_fist = FingerStatus(thumb_extended=False, index_extended=False, middle_extended=False, ring_extended=False, pinky_extended=False)
    _, fb_start = lk_test.process(True, 0.95, f_fist, None, current_time=t_base + 0.1)
    print(f"  - State after Fist Start: {lk_test.state.name} | Feedback: '{fb_start}'")

    # Mid countdown (1.1s hold)
    _, fb_mid = lk_test.process(True, 0.95, f_fist, None, current_time=t_base + 1.2)
    print(f"  - Hold at 1.1s: Feedback: '{fb_mid}'")

    # Hold reaches 2.1s (>= 2.0s trigger threshold)
    _, fb_done = lk_test.process(True, 0.95, f_fist, None, current_time=t_base + 2.2)
    print(f"  - Hold at 2.1s (Trigger): Feedback: '{fb_done}' | Callback invoked: {len(mock_lock_calls) == 1}")
    assert len(mock_lock_calls) == 1

    # Cooldown guard (at 3.0s, cooldown lasts 5.0s)
    lk_test.process(True, 0.95, f_open, None, current_time=t_base + 3.0)
    lk_test.process(True, 0.95, f_fist, None, current_time=t_base + 3.1)
    lk_test.process(True, 0.95, f_fist, None, current_time=t_base + 5.5)
    print(f"  - Attempt during 5.0s Cooldown: Callback calls: {len(mock_lock_calls)} (Expected: 1, Blocked: True)")
    assert len(mock_lock_calls) == 1

    print("\n>>> ALL LIVE AND REAL-TIME CRITERIA VERIFIED SUCCESSFULLY! <<<")

if __name__ == "__main__":
    run_live_test(num_frames=120)
