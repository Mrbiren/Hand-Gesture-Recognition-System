import time
import cv2

from core.hand_tracker import HandTracker


print("=== CRYNET CAMERA PIPELINE TEST ===")

camera_index = 0
width = 640
height = 480
fps = 30
mirror = True

print("Opening camera with CAP_DSHOW...")

cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)

if not cap.isOpened():
    print("CAP_DSHOW failed. Trying default backend...")
    cap = cv2.VideoCapture(camera_index)

if not cap.isOpened():
    print("ERROR: Camera could not be opened.")
    raise SystemExit(1)

cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
cap.set(cv2.CAP_PROP_FPS, fps)

print("Camera opened:", cap.isOpened())
print(
    "Actual resolution:",
    int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
    "x",
    int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
)

tracker = HandTracker()

if tracker.hands is None:
    print("ERROR: MediaPipe Hands failed to initialize.")
    cap.release()
    raise SystemExit(1)

print("MediaPipe Hands initialized.")
print("Show your hand to the camera.")
print("Press Q to quit.")
print()

frames = 0
detected = 0
no_hand = 0
errors = 0

start = time.time()

while True:
    ret, frame = cap.read()

    if not ret or frame is None:
        print("WARNING: Camera frame read failed.")
        errors += 1
        time.sleep(0.01)
        continue

    # EXACTLY the same mirror operation as CameraWorker.
    if mirror:
        frame = cv2.flip(frame, 1)

    try:
        tracking, annotated = tracker.process_frame(frame)

        frames += 1

        if tracking.hand_detected:
            detected += 1

            print(
                f"HAND DETECTED | "
                f"count={tracking.hand_count} | "
                f"landmarks={len(tracking.landmarks)} | "
                f"confidence={tracking.confidence:.2f}"
            )

        else:
            no_hand += 1

        # Display the exact annotated frame returned by HandTracker.
        display = annotated if annotated is not None else frame

        cv2.imshow("CryNet Camera Pipeline Test", display)

    except Exception as e:
        errors += 1
        print("PROCESSING ERROR:", repr(e))

    key = cv2.waitKey(1) & 0xFF

    if key == ord("q") or key == ord("Q"):
        break

elapsed = time.time() - start

cap.release()
cv2.destroyAllWindows()

print()
print("=== TEST RESULT ===")
print("Frames processed:", frames)
print("Hands detected:", detected)
print("No-hand frames:", no_hand)
print("Processing errors:", errors)

if elapsed > 0:
    print("Average FPS:", round(frames / elapsed, 1))

if detected > 0:
    print()
    print("RESULT: EXACT CRYNET CAMERA PIPELINE DETECTS HANDS.")
else:
    print()
    print("RESULT: EXACT CRYNET CAMERA PIPELINE DOES NOT DETECT HANDS.")