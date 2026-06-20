# ─────────────────────────────────────────────────────────────
#  detector.py  –  MediaPipe Tasks API drowsiness detector
#  (headless: no OpenCV drawing — the GUI handles all display)
#
#  THREE WARNING CONDITIONS:
#    1. EAR  → eyes-closed continuous timer   (RED warning)
#    2. MAR  → yawn counter, sliding window    (GREEN warning)
#    3. No face detected                       → RED warning (instant)
#
#  All thresholds are read from a `Settings` object every frame,
#  so the touchscreen GUI can change them live while this runs.
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
    pts = np.array([(lms[i].x * w, lms[i].y * h) for i in indices])
    A = dist.euclidean(pts[1], pts[5])
    B = dist.euclidean(pts[2], pts[4])
    C = dist.euclidean(pts[0], pts[3])
    return (A + B) / (2.0 * C) if C > 0 else 0.0


def _mar(lms: list, w: int, h: int) -> float:
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
    Headless detector — does no drawing. Call process_frame(bgr_frame)
    every loop iteration; read results from the returned dicts or
    from the public attributes below.

    All thresholds are pulled from `settings` (a shared.Settings
    instance) on every call, so changes made by the GUI thread take
    effect on the very next frame.
    """

    def __init__(self, settings):
        self.settings = settings

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
        self._mar_open_counter  = 0
        self._yawn_in_progress  = False
        self._window_start: float | None = None
        self.yawn_count_this_window = 0
        self._yawn_warning_until: float | None = None
        self.yawn_warning = False

        # ── Feature 3: no-face warning ────────────────────────
        self.no_face_warning = False

        # Totals
        self.total_eyes_closed_events = 0
        self.total_yawn_alerts        = 0
        self.total_no_face_events     = 0
        self.face_detected            = False
        self._was_face_detected_prev  = True

        # Latest live metrics (read by GUI for EAR/MAR display)
        self.last_ear = 0.0
        self.last_mar = 0.0

        print("[Detector] Ready (headless) — eyes-closed timer + "
              "sliding yawn window + no-face check.")

    # ── Main API ──────────────────────────────────────────────

    def process_frame(self, bgr: np.ndarray):
        """
        Returns
        -------
        warnings : dict {"eyes_closed": bool, "yawn": bool, "no_face": bool}
        metrics  : dict {"ear", "mar", "eyes_closed_duration",
                          "yawn_count", "window_elapsed_sec"}
        """
        h, w = bgr.shape[:2]
        now  = time.time()

        # Pull current (possibly GUI-modified) thresholds
        ear_threshold  = self.settings.ear_threshold
        mar_threshold  = self.settings.mar_threshold
        eyes_closed_sec = self.settings.eyes_closed_sec
        yawn_window_sec = self.settings.yawn_window_sec

        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        self._frame_ts_ms += 33
        result = self._landmarker.detect_for_video(mp_img, self._frame_ts_ms)

        metrics = dict(ear=0.0, mar=0.0, eyes_closed_duration=0.0,
                       yawn_count=0, window_elapsed_sec=0.0)

        if self._window_start is None:
            self._window_start = now

        elapsed_in_window = now - self._window_start
        if elapsed_in_window >= yawn_window_sec:
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
            self.last_ear = ear

            eye_closed_now = ear < ear_threshold
            if eye_closed_now:
                if self._eye_close_start is None:
                    self._eye_close_start = now
                self.eyes_closed_duration = now - self._eye_close_start
                if self.eyes_closed_duration >= eyes_closed_sec:
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
            self.last_mar = mar

            mouth_open_now = mar > mar_threshold
            if mouth_open_now:
                self._mar_open_counter += 1
                if (self._mar_open_counter >= config.MAR_CONSEC_FRAMES
                        and not self._yawn_in_progress):
                    self._yawn_in_progress = True
                    self.yawn_count_this_window += 1

                    if self.yawn_count_this_window >= config.YAWN_COUNT_TRIGGER:
                        self.total_yawn_alerts += 1
                        self._yawn_warning_until = now + config.YAWN_WARNING_DISPLAY_SEC
                        # Sliding window: reset immediately, fresh window starts NOW
                        self.yawn_count_this_window = 0
                        self._window_start = now
                        elapsed_in_window = 0.0
            else:
                self._mar_open_counter = 0
                self._yawn_in_progress = False

        else:
            self.face_detected = False
            if config.NO_FACE_WARNING_ENABLED:
                if self._was_face_detected_prev:
                    self.total_no_face_events += 1
                self.no_face_warning = True
            self._eye_close_start = None
            self.eyes_closed_duration = 0.0
            self.eyes_closed_warning = False

        self._was_face_detected_prev = self.face_detected

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
        return warnings, metrics

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
