# ─────────────────────────────────────────────────────────────
#  config.py  –  All settings for the Raspberry Pi touchscreen
#  drowsiness detector.
#
#  Values marked "RUNTIME" are the STARTING values only — the
#  touchscreen Sensitivity/time-adjust buttons change them live,
#  in memory, while the app runs. They are not re-saved to this
#  file (restarting the app reloads these defaults).
# ─────────────────────────────────────────────────────────────

# ── Model ────────────────────────────────────────────────────
MODEL_PATH = "face_landmarker.task"
MODEL_URL  = (
    "https://storage.googleapis.com/mediapipe-models/"
    "face_landmarker/face_landmarker/float16/1/face_landmarker.task"
)

# ── Face Mesh settings ────────────────────────────────────────
NUM_FACES                     = 1
MIN_FACE_DETECTION_CONFIDENCE = 0.6
MIN_FACE_PRESENCE_CONFIDENCE  = 0.6
MIN_TRACKING_CONFIDENCE       = 0.6

# ── Feature 1: Eyes-closed timer ──────────────────────────────
EAR_THRESHOLD          = 0.22   # below this = eye considered closed
EYES_CLOSED_SEC_DEFAULT = 2.0   # RUNTIME: adjustable via +/- buttons on screen
EYES_CLOSED_SEC_MIN     = 0.5
EYES_CLOSED_SEC_MAX     = 5.0
EYES_CLOSED_SEC_STEP    = 0.5

# ── Feature 2: Yawn counter (sliding window) ──────────────────
MAR_THRESHOLD       = 0.65
MAR_CONSEC_FRAMES    = 12

YAWN_WINDOW_SEC_DEFAULT = 60    # RUNTIME: adjustable via +/- buttons on screen
YAWN_WINDOW_SEC_MIN     = 10
YAWN_WINDOW_SEC_MAX     = 180
YAWN_WINDOW_SEC_STEP    = 10

YAWN_COUNT_TRIGGER        = 3
YAWN_WARNING_DISPLAY_SEC  = 5

# ── Feature 3: No-face warning ─────────────────────────────────
NO_FACE_WARNING_ENABLED = True

# ── Sensitivity presets ────────────────────────────────────────
# The on-screen "Sensitivity" button cycles through these presets,
# each adjusting EAR_THRESHOLD and MAR_THRESHOLD together.
SENSITIVITY_PRESETS = {
    "Low":    {"ear": 0.18, "mar": 0.75},   # harder to trigger (fewer false alarms)
    "Medium": {"ear": 0.22, "mar": 0.65},   # default / balanced
    "High":   {"ear": 0.26, "mar": 0.55},   # easier to trigger (more sensitive)
}
SENSITIVITY_DEFAULT = "Medium"

# ── GPIO warning outputs ─────────────────────────────────────
# Two 3.3V logic-level outputs, HIGH while the corresponding
# warning is active, LOW otherwise. Pins chosen to avoid every
# pin used by the piscreen display + XPT2046 touch overlay, and
# to sit on the header's OUTER row (odd physical pins) for easy
# jumper-wire access despite the display board on top.
#
# RED:   GPIO22 (physical pin 15) — eyes_closed OR no_face
# GREEN: GPIO5  (physical pin 29) — yawn
GPIO_ENABLED    = True
GPIO_RED_PIN    = 20   # BCM numbering — physical pin 38
GPIO_GREEN_PIN  = 21   # BCM numbering — physical pin 40

# ── Warning sound ──────────────────────────────────────────────
BEEP_INTERVAL_SEC = 0.4
ALARM_SOUND_PATH  = None        # optional WAV/MP3 path; None → system beep

# ── Camera (capture resolution — kept low for Pi 4 CPU headroom) ─
CAMERA_INDEX = 0
FRAME_WIDTH  = 320
FRAME_HEIGHT = 240

# ── GUI / touchscreen ──────────────────────────────────────────
# Set to match your panel. Confirmed for the 3.5" ILI9486/XPT2046
# 480x320 SPI panel (Fmax 32MHz) — see README for the dtoverlay
# setup. Change these two values if you swap to a different panel.
SCREEN_WIDTH   = 480
SCREEN_HEIGHT  = 320
FULLSCREEN     = True           # fills the screen on launch; set False for windowed/desktop use
SNAPSHOT_FPS   = 1.0            # how often the camera panel image updates (frames/sec)
GUI_POLL_MS    = 150            # how often the GUI refreshes text/color state (milliseconds)

WINDOW_TITLE = "Drowsiness Monitor"

# ── MediaPipe 478-landmark indices ────────────────────────────
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_EYE  = [ 33, 160, 158, 133, 153, 144]

MOUTH_TOP     = 13
MOUTH_BOTTOM  = 14
MOUTH_LEFT    = 78
MOUTH_RIGHT   = 308
MOUTH_TOP2    = 312
MOUTH_BOTTOM2 = 317
