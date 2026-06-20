# ─────────────────────────────────────────────────────────────
#  worker.py  –  Background thread: camera capture, detection,
#  alarm control, and throttled snapshot publishing.
#
#  Runs independently of the GUI's frame rate. The touchscreen
#  only needs ~1 snapshot/sec (config.SNAPSHOT_FPS), but the
#  detector itself processes every camera frame for accurate
#  timing (eyes-closed duration, yawn debounce).
# ─────────────────────────────────────────────────────────────

import threading
import time

import cv2

import config
from detector import DrowsinessDetector
from alarm import AlarmSystem


class DetectionWorker:
    """
    Owns the camera, the DrowsinessDetector, and the AlarmSystem.
    Runs its own loop on a background thread (start()/stop()).
    Publishes results into the shared AppState every frame, and
    a downsampled RGB snapshot into AppState at config.SNAPSHOT_FPS.
    """

    def __init__(self, settings, app_state):
        self.settings  = settings
        self.app_state = app_state

        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

        self._detector: DrowsinessDetector | None = None
        self._alarm = AlarmSystem(config.ALARM_SOUND_PATH, config.BEEP_INTERVAL_SEC)

        self._cap: cv2.VideoCapture | None = None

    # ── Public control ───────────────────────────────────────

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self.settings.set_running(True)
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self.settings.set_running(False)
        self._stop_event.set()
        self._alarm.stop()

    def shutdown(self):
        """Full teardown — call once when the app is closing."""
        self.stop()
        if self._thread:
            self._thread.join(timeout=2.0)
        if self._cap is not None:
            self._cap.release()
        if self._detector is not None:
            self._detector.close()

    def reset_counters(self):
        if self._detector is not None:
            self._detector.reset()

    # ── Worker loop ───────────────────────────────────────────

    def _run(self):
        try:
            self._cap = cv2.VideoCapture(config.CAMERA_INDEX)
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH,  config.FRAME_WIDTH)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.FRAME_HEIGHT)

            if not self._cap.isOpened():
                self.app_state.set_camera_error(
                    f"Cannot open camera index {config.CAMERA_INDEX}"
                )
                return

            self._detector = DrowsinessDetector(self.settings)
            self.app_state.set_camera_error(None)

        except Exception as e:
            self.app_state.set_camera_error(f"Init failed: {e}")
            return

        snapshot_interval = 1.0 / max(config.SNAPSHOT_FPS, 0.1)
        last_snapshot_t = 0.0

        fps_counter = 0
        fps_timer = time.time()

        while not self._stop_event.is_set():
            if not self.settings.running:
                # Paused (Stop pressed) — idle without burning camera/CPU
                time.sleep(0.1)
                continue

            ret, frame = self._cap.read()
            if not ret:
                self.app_state.set_camera_error("Frame read failed")
                time.sleep(0.1)
                continue

            self.app_state.set_camera_error(None)
            frame = cv2.flip(frame, 1)

            warnings, metrics = self._detector.process_frame(frame)

            # ── Alarm: beep continuously while any warning is active ──
            if warnings["eyes_closed"] or warnings["yawn"] or warnings["no_face"]:
                self._alarm.start()
            else:
                self._alarm.stop()

            totals = dict(
                eyes_closed_events = self._detector.total_eyes_closed_events,
                yawn_alerts        = self._detector.total_yawn_alerts,
                no_face_events     = self._detector.total_no_face_events,
            )
            self.app_state.update_detection(
                warnings, metrics, self._detector.face_detected, totals
            )

            # ── Throttled snapshot for the GUI ────────────────
            now = time.time()
            if now - last_snapshot_t >= snapshot_interval:
                last_snapshot_t = now
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                h, w = rgb.shape[:2]
                self.app_state.update_snapshot(rgb.tobytes(), w, h)

            # ── FPS bookkeeping ────────────────────────────────
            fps_counter += 1
            if now - fps_timer >= 1.0:
                self.app_state.set_fps(fps_counter / (now - fps_timer))
                fps_counter = 0
                fps_timer = now

        # Loop exited (stop_event set) — leave camera open in case
        # of restart via start(); shutdown() releases it for good.
        self._alarm.stop()
