#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
#  main.py  –  Drowsiness Detection (3 warnings)
#
#    1. Eyes closed > 2 seconds                  → RED warning
#    2. 3 yawns within a sliding N-second window   → GREEN warning
#       (window resets to 0 the INSTANT it triggers, starting fresh
#        from that moment — adjustable in config.py)
#    3. No face detected                           → RED warning (instant)
#
#  All warnings play continuous short beeps while active.
#
#  Run:  python main.py
# ─────────────────────────────────────────────────────────────

import time
import cv2

import config
from detector import DrowsinessDetector
from alarm    import AlarmSystem
from overlay  import draw_warnings, draw_status_bar


def main():
    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    if not cap.isOpened():
        raise RuntimeError(f"Cannot open camera {config.CAMERA_INDEX}.")
    cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

    detector = DrowsinessDetector()           # downloads model on first run
    alarm    = AlarmSystem(config.ALARM_SOUND_PATH, config.BEEP_INTERVAL_SEC)

    t0        = time.time()
    fps_cnt   = 0
    fps_disp  = 0.0
    fps_timer = time.time()

    print("\n" + "═" * 56)
    print("  Drowsiness Detection — 3 Warnings")
    print("═" * 56)
    print(f"  RED warning   : eyes closed ≥ {config.EYES_CLOSED_SEC}s")
    print(f"  RED warning   : no face detected (instant)")
    print(f"  GREEN warning : {config.YAWN_COUNT_TRIGGER} yawns within a "
          f"{config.YAWN_WINDOW_SEC}s sliding window")
    print(f"                  shown for {config.YAWN_WARNING_DISPLAY_SEC}s, "
          "then window resets to 0 immediately (starts fresh from that instant)")
    print(f"  Sound         : continuous beeps every {config.BEEP_INTERVAL_SEC}s "
          "while any warning is active")
    print("  Q → quit   R → reset")
    print("═" * 56 + "\n")

    while True:
        ret, frame = cap.read()
        if not ret:
            print("[WARN] Frame read failed – retrying…")
            continue

        frame = cv2.flip(frame, 1)

        annotated, warnings, metrics = detector.process_frame(frame)

        # ── Sound: beep continuously while ANY warning is active ──
        if warnings["eyes_closed"] or warnings["yawn"] or warnings["no_face"]:
            alarm.start()
        else:
            alarm.stop()

        draw_warnings(annotated, warnings["eyes_closed"], warnings["yawn"], warnings["no_face"])

        fps_cnt += 1
        now = time.time()
        if now - fps_timer >= 1.0:
            fps_disp  = fps_cnt / (now - fps_timer)
            fps_cnt   = 0
            fps_timer = now

        draw_status_bar(annotated, fps_disp, now - t0)

        cv2.imshow(config.WINDOW_TITLE, annotated)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q"):
            print("\n[System] Quit by user.")
            break
        elif key == ord("r"):
            detector.reset()
            alarm.stop()
            print("[System] Counters reset.")

    alarm.stop()
    detector.close()
    cap.release()
    cv2.destroyAllWindows()

    elapsed = time.time() - t0
    m, s = divmod(int(elapsed), 60)
    print("\n" + "─" * 38)
    print(f"  Session             : {m:02d}:{s:02d}")
    print(f"  Eyes-closed events  : {detector.total_eyes_closed_events}")
    print(f"  Yawn-burst alerts   : {detector.total_yawn_alerts}")
    print(f"  No-face events      : {detector.total_no_face_events}")
    print("─" * 38 + "\n")


if __name__ == "__main__":
    main()
