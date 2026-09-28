import cv2
import time

from core.hand_tracker import HandTracker


def main():
    print("=== CryNet MediaPipe Camera Test ===")

    cap = cv2.VideoCapture(0, cv2.CAP_DSHOW)

    if not cap.isOpened():
        print("ERROR: Could not open webcam.")
        return

    print("Camera opened: True")

    tracker = HandTracker()

    print("Hands initialized:", tracker.hands is not None)

    if tracker.hands is None:
        print("ERROR: MediaPipe Hands failed to initialize.")
        cap.release()
        return

    print("\nShow ONE hand clearly to the camera.")
    print("Press Q to quit.\n")

    frames = 0
    detected = 0
    incomplete = 0
    start = time.time()

    while True:
        ret, frame = cap.read()

        if not ret:
            print("ERROR: Camera frame could not be read.")
            break

        frames += 1

        tracking, annotated = tracker.process_frame(frame)

        landmark_count = len(tracking.landmarks)

        if tracking.hand_detected and landmark_count >= 21:
            detected += 1

            index = tracking.landmarks[8]

            print(
                "HAND DETECTED | "
                f"hands={tracking.hand_count} | "
                f"landmarks={landmark_count} | "
                f"confidence={tracking.confidence:.2f} | "
                f"index=({index.x:.3f}, {index.y:.3f})"
            )

        elif tracking.hand_detected:
            incomplete += 1

            print(
                "INCOMPLETE HAND | "
                f"landmarks={landmark_count} | "
                f"confidence={tracking.confidence:.2f}"
            )

        display_frame = annotated if annotated is not None else frame

        cv2.imshow("CryNet - MediaPipe Hand Test", display_frame)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        if time.time() - start >= 15:
            break

    cap.release()
    cv2.destroyAllWindows()

    print("\n=== TEST RESULT ===")
    print(f"Frames processed: {frames}")
    print(f"Complete hand frames: {detected}")
    print(f"Incomplete hand frames: {incomplete}")

    if detected > 0:
        print("RESULT: MediaPipe hand detection is WORKING.")
    else:
        print("RESULT: No complete hand landmarks detected.")


if __name__ == "__main__":
    main()