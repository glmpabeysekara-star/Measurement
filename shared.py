# ─────────────────────────────────────────────────────────────
#  shared.py  –  Thread-safe state shared between the
#  detection/camera thread and the Tkinter GUI thread.
#
#  Two classes:
#    Settings  – runtime-adjustable thresholds (GUI writes, detector reads)
#    AppState  – detection results + snapshot image (detector writes, GUI reads)
#
#  Both use a single Lock per object; reads/writes are short, so
#  contention is never a practical issue at these frame rates.
# ─────────────────────────────────────────────────────────────

import threading
import time

import config


class Settings:
    """
    Holds all values the touchscreen can change while the app runs.
    The detector thread reads these every frame; the GUI thread
    writes to them when a button is pressed. Thread-safe via lock.
    """

    def __init__(self):
        self._lock = threading.Lock()

        self._eyes_closed_sec = config.EYES_CLOSED_SEC_DEFAULT
        self._yawn_window_sec = config.YAWN_WINDOW_SEC_DEFAULT
        self._sensitivity_name = config.SENSITIVITY_DEFAULT

        preset = config.SENSITIVITY_PRESETS[self._sensitivity_name]
        self._ear_threshold = preset["ear"]
        self._mar_threshold = preset["mar"]

        self._running = False   # detection loop active?

    # ── eyes_closed_sec ───────────────────────────────────────
    @property
    def eyes_closed_sec(self) -> float:
        with self._lock:
            return self._eyes_closed_sec

    def adjust_eyes_closed_sec(self, delta: float) -> float:
        with self._lock:
            new_val = round(self._eyes_closed_sec + delta, 1)
            new_val = max(config.EYES_CLOSED_SEC_MIN,
                         min(config.EYES_CLOSED_SEC_MAX, new_val))
            self._eyes_closed_sec = new_val
            return new_val

    # ── yawn_window_sec ───────────────────────────────────────
    @property
    def yawn_window_sec(self) -> float:
        with self._lock:
            return self._yawn_window_sec

    def adjust_yawn_window_sec(self, delta: float) -> float:
        with self._lock:
            new_val = round(self._yawn_window_sec + delta, 0)
            new_val = max(config.YAWN_WINDOW_SEC_MIN,
                         min(config.YAWN_WINDOW_SEC_MAX, new_val))
            self._yawn_window_sec = new_val
            return new_val

    # ── sensitivity (cycles EAR + MAR threshold presets together) ─
    @property
    def sensitivity_name(self) -> str:
        with self._lock:
            return self._sensitivity_name

    @property
    def ear_threshold(self) -> float:
        with self._lock:
            return self._ear_threshold

    @property
    def mar_threshold(self) -> float:
        with self._lock:
            return self._mar_threshold

    def cycle_sensitivity(self) -> str:
        """Advance to the next sensitivity preset; returns its name."""
        names = list(config.SENSITIVITY_PRESETS.keys())
        with self._lock:
            idx = names.index(self._sensitivity_name)
            new_name = names[(idx + 1) % len(names)]
            preset = config.SENSITIVITY_PRESETS[new_name]
            self._sensitivity_name = new_name
            self._ear_threshold = preset["ear"]
            self._mar_threshold = preset["mar"]
            return new_name

    # ── running flag ──────────────────────────────────────────
    @property
    def running(self) -> bool:
        with self._lock:
            return self._running

    def set_running(self, value: bool):
        with self._lock:
            self._running = value


class AppState:
    """
    Holds the latest detection results and camera snapshot.
    The detector/camera thread writes; the GUI thread reads.
    Thread-safe via lock. Snapshot is stored as raw RGB bytes
    + dimensions (not a Tk object — Tk objects must be created
    on the GUI thread only).
    """

    def __init__(self):
        self._lock = threading.Lock()

        self.warnings = dict(eyes_closed=False, yawn=False, no_face=True)
        self.metrics  = dict(ear=0.0, mar=0.0, eyes_closed_duration=0.0,
                             yawn_count=0, window_elapsed_sec=0.0)
        self.face_detected = False

        self.totals = dict(eyes_closed_events=0, yawn_alerts=0, no_face_events=0)

        # Snapshot: raw RGB bytes (for Tk PhotoImage construction on GUI thread)
        self.snapshot_rgb_bytes: bytes | None = None
        self.snapshot_w = 0
        self.snapshot_h = 0
        self.snapshot_updated_at = 0.0

        self.camera_error: str | None = None
        self.fps = 0.0

    def update_detection(self, warnings: dict, metrics: dict,
                        face_detected: bool, totals: dict):
        with self._lock:
            self.warnings = warnings
            self.metrics  = metrics
            self.face_detected = face_detected
            self.totals = totals

    def update_snapshot(self, rgb_bytes: bytes, w: int, h: int):
        with self._lock:
            self.snapshot_rgb_bytes = rgb_bytes
            self.snapshot_w = w
            self.snapshot_h = h
            self.snapshot_updated_at = time.time()

    def set_camera_error(self, msg: str | None):
        with self._lock:
            self.camera_error = msg

    def set_fps(self, fps: float):
        with self._lock:
            self.fps = fps

    def snapshot(self) -> dict:
        """Atomic read of everything the GUI needs in one call."""
        with self._lock:
            return dict(
                warnings=dict(self.warnings),
                metrics=dict(self.metrics),
                face_detected=self.face_detected,
                totals=dict(self.totals),
                snapshot_rgb_bytes=self.snapshot_rgb_bytes,
                snapshot_w=self.snapshot_w,
                snapshot_h=self.snapshot_h,
                snapshot_updated_at=self.snapshot_updated_at,
                camera_error=self.camera_error,
                fps=self.fps,
            )
