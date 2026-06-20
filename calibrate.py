#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
#  calibrate.py  –  Find YOUR personal EAR & MAR thresholds
#  Run once before main.py:  python calibrate.py
# ─────────────────────────────────────────────────────────────

import statistics
import time
import sys

import cv2
import numpy as np
import mediapipe as mp
from mediapipe.tasks.python import vision as mp_vision
from mediapipe.tasks.python.core import base_options as mp_base
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode
from scipy.spatial import distance as dist

import config
from download_model import download_model
from detector import _ear, _mar   # reuse the same helpers

PHASES = [
    ("EYES OPEN",   10, "Look straight at the camera with eyes fully open."),
    ("EYES CLOSED",  8, "Close your eyes gently (simulate drowsiness)."),
    ("YAWNING",      8, "Open your mouth wide as if yawning."),
]


def collect_phase(cap, landmarker, label, duration, instruction):
    print(f"\n  ▶  Phase: {label}  ({duration}s)")
    print(f"     {instruction}")
    time.sleep(1.5)

    ears, mars = [], []
    deadline  = time.time() + duration
    ts_ms     = 0
    shown     = set()

    while time.time() < deadline:
        rem = int(deadline - time.time()) + 1
        if rem not in shown:
            print(f"     {rem}s …")
            shown.add(rem)

        ret, frame = cap.read()
        if not ret:
            continue

        frame = cv2.flip(frame, 1)
        h, w  = frame.shape[:2]
        rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        ts_ms += 33
        result = landmarker.detect_for_video(mp_img, ts_ms)

        if result.face_landmarks:
            lms = result.face_landmarks[0]
            ear_r = _ear(lms, config.RIGHT_EYE, w, h)
            ear_l = _ear(lms, config.LEFT_EYE,  w, h)
            ears.append((ear_r + ear_l) / 2.0)
            mars.append(_mar(lms, w, h))

        cv2.putText(frame, f"{label}  {rem}s", (20, 42),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 215, 255), 2)
        cv2.imshow("Calibration", frame)
        cv2.waitKey(1)

    return ears, mars


def main():
    print("\n" + "═" * 52)
    print("  Drowsiness Detector – Personal Calibration")
    print("═" * 52)
    print("  • Sit as you would while driving.")
    print("  • Good frontal lighting, face the camera.")
    print("  • Press Q to abort at any time.\n")

    if not download_model():
        print("Model unavailable – aborting calibration.")
        sys.exit(1)

    cap = cv2.VideoCapture(config.CAMERA_INDEX)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

    options = mp_vision.FaceLandmarkerOptions(
        base_options = mp_base.BaseOptions(model_asset_path=config.MODEL_PATH),
        running_mode = VisionTaskRunningMode.VIDEO,
        num_faces    = 1,
        min_face_detection_confidence = 0.6,
        min_face_presence_confidence  = 0.6,
        min_tracking_confidence       = 0.6,
    )
    landmarker = mp_vision.FaceLandmarker.create_from_options(options)

    data = {}
    for label, dur, instr in PHASES:
        ears, mars = collect_phase(cap, landmarker, label, dur, instr)
        data[label] = (ears, mars)
        print(f"     Collected {len(ears)} valid frames.")

    cap.release()
    landmarker.close()
    cv2.destroyAllWindows()

    # ── Compute thresholds ────────────────────────────────────
    open_ears,   _  = data["EYES OPEN"]
    closed_ears, _  = data["EYES CLOSED"]
    open_mars,   _  = data["EYES OPEN"]
    _,       yawn_m = data["YAWNING"]

    if len(open_ears) < 5 or len(closed_ears) < 5:
        print("\n[ERROR] Too few samples. Try again in better lighting.")
        sys.exit(1)

    mean_open   = statistics.mean(open_ears)
    mean_closed = statistics.mean(closed_ears)
    mean_yawn   = statistics.mean(yawn_m)  if yawn_m  else 0.65
    mean_rest_m = statistics.mean(open_mars) if open_mars else 0.30

    # EAR threshold: 45 % of the way from closed→open
    ear_thr = round(mean_closed + (mean_open - mean_closed) * 0.45, 3)
    # MAR threshold: 55 % of the way from rest→yawn
    mar_thr = round(mean_rest_m + (mean_yawn - mean_rest_m) * 0.55, 3)

    print("\n" + "═" * 52)
    print("  Results")
    print("─" * 52)
    print(f"  EAR open eyes  : {mean_open:.4f}")
    print(f"  EAR closed eyes: {mean_closed:.4f}")
    print(f"  MAR at rest    : {mean_rest_m:.4f}")
    print(f"  MAR yawning    : {mean_yawn:.4f}")
    print("─" * 52)
    print(f"  ✔  EAR_THRESHOLD = {ear_thr}")
    print(f"  ✔  MAR_THRESHOLD = {mar_thr}")
    print("═" * 52)
    print("\n  Paste these values into config.py, then run  python main.py\n")


if __name__ == "__main__":
    main()
