# ─────────────────────────────────────────────────────────────
#  detector.py  –  MediaPipe Tasks API drowsiness detector
#
#  THREE WARNING CONDITIONS:
#    1. EAR  → eyes-closed continuous timer   (≥2.0s → RED warning)
#    2. MAR  → yawn counter, SLIDING window    (3 yawns/60s → GREEN warning)
#    3. No face detected                       → RED warning (instant)
#
#  Yawn window behaviour (sliding / self-resetting):
#    • A window is config.YAWN_WINDOW_SEC seconds long.
#    • Yawns are counted as they occur within the current window.
#    • The INSTANT the count reaches config.YAWN_COUNT_TRIGGER, the
#      GREEN warning fires AND the count resets to 0 immediately,
#      with a brand-new window starting right at that moment.
#    • If the window's full duration elapses with the trigger count
#      never reached, the count also resets to 0 and a fresh window
#      begins (so stale old yawns don't linger forever).
# ─────────────────────────────────────────────────────────────

import time

import cv2
import numpy as np
from scipy.spatial import distance as dist

import mediapipe as mp
from mediapipe.tasks.python        import vision as mp_vision
from mediapipe.tasks.python.core   import base_options as mp_base
from mediapipe.tasks.python.vision import FaceLandmarker, FaceLandmarkerOptions
from mediapipe.tasks.python.vision.core.vision_task_running_mode import VisionTaskRunningMode

import config
from download_model import download_model


# ─────────────────────────────────────────────────────────────
#  Pure maths helpers
# ─────────────────────────────────────────────────────────────

def _ear(lms: list, indices: list[int], w: int, h: int) -> float:
    """Eye Aspect Ratio from 6 landmark points."""
    pts = np.array([(lms[i].x * w, lms[i].y * h) for i in indices])
    A = dist.euclidean(pts[1], pts[5])
    B = dist.euclidean(pts[2], pts[4])
    C = dist.euclidean(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def _mar(lms: list, w: int, h: int) -> float:
    """Mouth Aspect Ratio (yawn proxy)."""
    def pt(i): return np.array([lms[i].x * w, lms[i].y * h])
    A = dist.euclidean(pt(config.MOUTH_TOP),  pt(config.MOUTH_BOTTOM))
    B = dist.euclidean(pt(config.MOUTH_TOP2), pt(config.MOUTH_BOTTOM2))
    C = dist.euclidean(pt(config.MOUTH_LEFT), pt(config.MOUTH_RIGHT))
    return (A + B) / (2.0 * C) if C > 0 else 0.0


# ─────────────────────────────────────────────────────────────
#  DrowsinessDetector
# ─────────────────────────────────────────────────────────────

class DrowsinessDetector:
    """
    Tracks three warning conditions:

      1. eyes_closed_warning : True while eyes have been continuously
         closed for >= config.EYES_CLOSED_SEC seconds.

      2. yawn_warning : True for config.YAWN_WARNING_DISPLAY_SEC seconds
         after config.YAWN_COUNT_TRIGGER yawns occur inside the current
         sliding window (config.YAWN_WINDOW_SEC seconds long). The
         instant the trigger count is reached, the count resets to 0
         and a brand-new window starts immediately from that moment.

      3. no_face_warning : True on any frame where no face is detected
         (fires instantly, no debounce).

    Call process_frame(bgr_frame) every loop iteration.
    """

    def __init__(self):
        if not download_model():
            raise RuntimeError("FaceLandmarker model unavailable.")

        options = FaceLandmarkerOptions(
            base_options = mp_base.BaseOptions(model_asset_path=config.MODEL_PATH),
            running_mode = VisionTaskRunningMode.VIDEO,
            num_faces    = config.NUM_FACES,
            min_face_detection_confidence = config.MIN_FACE_DETECTION_CONFIDENCE,
            min_face_presence_confidence  = config.MIN_FACE_PRESENCE_CONFIDENCE,
            min_tracking_confidence       = config.MIN_TRACKING_CONFIDENCE,
        )
        self._landmarker = FaceLandmarker.create_from_options(options)
        self._frame_ts_ms = 0

        # ── Feature 1: eyes-closed continuous timer ──────────
        self._eye_close_start: float | None = None
        self.eyes_closed_warning  = False
        self.eyes_closed_duration = 0.0

        # ── Feature 2: yawn counter (sliding / self-resetting window) ─
        self._mar_open_counter  = 0      # consecutive frames mouth is open
        self._yawn_in_progress  = False  # guards against double-counting one yawn
        self._window_start: float | None = None   # when the current window began
        self.yawn_count_this_window = 0
        self._yawn_warning_until: float | None = None  # timestamp warning auto-hides
        self.yawn_warning = False

        # ── Feature 3: no-face warning ────────────────────────
        self.no_face_warning = False

        # Totals (for end-of-session summary)
        self.total_eyes_closed_events = 0
        self.total_yawn_alerts        = 0
        self.total_no_face_events     = 0
        self.face_detected            = False
        self._was_face_detected_prev  = True   # to count distinct no-face "events"

        print("[Detector] Ready — eyes-closed timer + sliding yawn window + no-face check.")

    # ── Main API ──────────────────────────────────────────────

    def process_frame(self, bgr: np.ndarray):
        """
        Returns
        -------
        annotated : np.ndarray
        warnings  : dict  {"eyes_closed": bool, "yawn": bool, "no_face": bool}
        metrics   : dict  {"ear", "mar", "eyes_closed_duration",
                            "yawn_count", "window_elapsed_sec"}
        """
        h, w = bgr.shape[:2]
        now  = time.time()

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._frame_ts_ms += 33
        result = self._landmarker.detect_for_video(mp_img, self._frame_ts_ms)

        metrics = dict(ear=0.0, mar=0.0, eyes_closed_duration=0.0,
                       yawn_count=0, window_elapsed_sec=0.0)

        # ── Start the very first window on first call ─────────
        if self._window_start is None:
            self._window_start = now

        # ── If the window's full duration elapsed with no trigger,
        #    reset it (so very old yawns eventually drop off) ───
        elapsed_in_window = now - self._window_start
        if elapsed_in_window >= config.YAWN_WINDOW_SEC:
            self._window_start = now
            self.yawn_count_this_window = 0
            elapsed_in_window = 0.0

        if result.face_landmarks:
            self.face_detected = True
            self.no_face_warning = False
            lms = result.face_landmarks[0]

            # ── Feature 1: EAR → eyes-closed timer ────────────
            ear_r = _ear(lms, config.RIGHT_EYE, w, h)
            ear_l = _ear(lms, config.LEFT_EYE,  w, h)
            ear   = (ear_r + ear_l) / 2.0
            metrics["ear"] = ear

            eye_closed_now = ear < config.EAR_THRESHOLD
            if eye_closed_now:
                if self._eye_close_start is None:
                    self._eye_close_start = now
                self.eyes_closed_duration = now - self._eye_close_start
                if self.eyes_closed_duration >= config.EYES_CLOSED_SEC:
                    if not self.eyes_closed_warning:
                        self.total_eyes_closed_events += 1
                    self.eyes_closed_warning = True
            else:
                self._eye_close_start = None
                self.eyes_closed_duration = 0.0
                self.eyes_closed_warning = False

            # ── Feature 2: MAR → yawn detection (debounced) ───
            mar = _mar(lms, w, h)
            metrics["mar"] = mar

            mouth_open_now = mar > config.MAR_THRESHOLD
            if mouth_open_now:
                self._mar_open_counter += 1
                if (self._mar_open_counter >= config.MAR_CONSEC_FRAMES
                        and not self._yawn_in_progress):
                    self._yawn_in_progress = True
                    self.yawn_count_this_window += 1

                    if self.yawn_count_this_window >= config.YAWN_COUNT_TRIGGER:
                        self.total_yawn_alerts += 1
                        self._yawn_warning_until = now + config.YAWN_WARNING_DISPLAY_SEC
                        # Sliding window: reset immediately, start fresh window NOW
                        self.yawn_count_this_window = 0
                        self._window_start = now
                        elapsed_in_window = 0.0
            else:
                self._mar_open_counter = 0
                self._yawn_in_progress = False

            self._draw_mesh(bgr, lms, w, h, ear, mar)

        else:
            # ── Feature 3: no face detected → instant RED warning ──
            self.face_detected = False
            if config.NO_FACE_WARNING_ENABLED:
                if self._was_face_detected_prev:
                    self.total_no_face_events += 1
                self.no_face_warning = True
            self._eye_close_start = None
            self.eyes_closed_duration = 0.0
            self.eyes_closed_warning = False

        self._was_face_detected_prev = self.face_detected

        # ── Yawn warning visibility: active until its display timer expires ─
        if self._yawn_warning_until is not None:
            self.yawn_warning = now < self._yawn_warning_until
            if not self.yawn_warning:
                self._yawn_warning_until = None
        else:
            self.yawn_warning = False

        metrics["eyes_closed_duration"] = self.eyes_closed_duration
        metrics["yawn_count"]           = self.yawn_count_this_window
        metrics["window_elapsed_sec"]   = elapsed_in_window

        warnings = dict(
            eyes_closed = self.eyes_closed_warning,
            yawn        = self.yawn_warning,
            no_face     = self.no_face_warning,
        )

        self._draw_hud(bgr, metrics)
        return bgr, warnings, metrics

    def reset(self):
        self._eye_close_start = None
        self.eyes_closed_duration = 0.0
        self.eyes_closed_warning = False
        self._mar_open_counter = 0
        self._yawn_in_progress = False
        self._window_start = None
        self.yawn_count_this_window = 0
        self._yawn_warning_until = None
        self.yawn_warning = False
        self.no_face_warning = False
        self._was_face_detected_prev = True
        self.total_eyes_closed_events = 0
        self.total_yawn_alerts = 0
        self.total_no_face_events = 0

    def close(self):
        self._landmarker.close()

    # ── Drawing ───────────────────────────────────────────────

    def _draw_mesh(self, frame, lms, w, h, ear, mar):
        eye_color = (0, 210, 0) if ear >= config.EAR_THRESHOLD else (20, 20, 220)
        for contour_ids in [config.LEFT_EYE_CONTOUR, config.RIGHT_EYE_CONTOUR]:
            pts = np.array(
                [(int(lms[i].x * w), int(lms[i].y * h)) for i in contour_ids],
                dtype=np.int32,
            )
            cv2.polylines(frame, [pts], isClosed=True, color=eye_color, thickness=2)

        if mar > config.MAR_THRESHOLD:
            mouth_ids = [61,185,40,39,37,0,267,269,270,409,291,
                         375,321,405,314,17,84,181,91,146]
            mpts = np.array(
                [(int(lms[i].x * w), int(lms[i].y * h)) for i in mouth_ids],
                dtype=np.int32,
            )
            cv2.polylines(frame, [mpts], isClosed=True, color=(0, 200, 0), thickness=2)

    def _draw_hud(self, frame, metrics):
        h, w = frame.shape[:2]
        font = cv2.FONT_HERSHEY_SIMPLEX

        if not self.face_detected:
            text = "NO FACE DETECTED"
            cv2.putText(frame, text, (12, 26), font, 0.55, (0, 0, 0), 3)
            cv2.putText(frame, text, (12, 26), font, 0.55, (20, 20, 220), 1)
            return

        ear        = metrics["ear"]
        mar        = metrics["mar"]
        closed_dur = metrics["eyes_closed_duration"]
        yawn_cnt   = metrics["yawn_count"]
        win_elapsed = metrics["window_elapsed_sec"]
        win_remaining = max(0.0, config.YAWN_WINDOW_SEC - win_elapsed)

        ear_col = (0, 210, 0) if ear >= config.EAR_THRESHOLD else (20, 20, 220)
        mar_col = (0, 210, 0) if mar <= config.MAR_THRESHOLD else (0, 200, 0)

        rows = [
            (f"EAR: {ear:.3f}", ear_col),
            (f"Eyes closed: {closed_dur:.1f}s / {config.EYES_CLOSED_SEC:.1f}s", ear_col),
            (f"MAR: {mar:.3f}", mar_col),
            (f"Yawns this window: {yawn_cnt} / {config.YAWN_COUNT_TRIGGER}"
             f"   (window auto-resets in {win_remaining:.0f}s if no trigger)", mar_col),
        ]
        for i, (text, color) in enumerate(rows):
            y = 26 + i * 24
            cv2.putText(frame, text, (12, y), font, 0.55, (0, 0, 0), 3)
            cv2.putText(frame, text, (12, y), font, 0.55, color, 1)

        face_str = "Face OK"
        face_col = (0, 210, 0)
        cv2.putText(frame, face_str, (w - 120, 25), font, 0.55, (0, 0, 0), 3)
        cv2.putText(frame, face_str, (w - 120, 25), font, 0.55, face_col, 1)
