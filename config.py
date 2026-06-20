# ─────────────────────────────────────────────────────────────
#  config.py  –  All tunable thresholds & settings
#
#  THREE WARNING CONDITIONS:
#    1. Eyes closed > 2 seconds              → RED warning
#    2. 3 yawns within a 60-second window     → GREEN warning
#       (window restarts from 0 the INSTANT the warning fires —
#        i.e. it's a sliding/resetting window, not a fixed clock cycle)
#    3. No face detected                      → RED warning (instant)
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
EAR_THRESHOLD        = 0.22   # below this = eye considered closed
EYES_CLOSED_SEC       = 2.0    # eyes closed continuously ≥ this → RED warning

# ── Feature 2: Yawn counter ────────────────────────────────────
MAR_THRESHOLD        = 0.65   # above this = mouth considered open (yawn)
MAR_CONSEC_FRAMES     = 12     # frames mouth must stay open to count as ONE yawn

# Sliding window: yawns are counted for up to YAWN_WINDOW_SEC seconds.
# The moment the count reaches YAWN_COUNT_TRIGGER, the GREEN warning
# fires AND the count immediately resets to 0, with a brand-new
# YAWN_WINDOW_SEC window starting right then (not waiting for the old
# window to finish naturally).
YAWN_WINDOW_SEC       = 60     # ← ADJUSTABLE: window length (seconds)
YAWN_COUNT_TRIGGER    = 3      # this many yawns within the window → GREEN warning

# How long the GREEN warning banner stays visible once triggered
YAWN_WARNING_DISPLAY_SEC = 5   # ← ADJUSTABLE: warning auto-hides after this long

# ── Feature 3: Face-not-detected warning ───────────────────────
# Fires the instant a frame has no detected face (no debounce delay).
NO_FACE_WARNING_ENABLED = True

# ── Warning sound ──────────────────────────────────────────────
# Continuous short beeps play for as long as ANY warning is active.
BEEP_INTERVAL_SEC = 0.4        # gap between beeps while a warning is active
ALARM_SOUND_PATH  = None       # optional WAV/MP3 path; None → system beep fallback

# ── Camera ───────────────────────────────────────────────────
CAMERA_INDEX = 0
FRAME_WIDTH  = 640
FRAME_HEIGHT = 480

# ── Display ──────────────────────────────────────────────────
WINDOW_TITLE = "Drowsiness Detection  |  Eyes-Closed + Yawn Counter"

# ── MediaPipe 478-landmark indices ────────────────────────────
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
LEFT_EYE  = [ 33, 160, 158, 133, 153, 144]

RIGHT_EYE_CONTOUR = [362,382,381,380,374,373,390,249,263,466,388,387,386,385,384,398]
LEFT_EYE_CONTOUR  = [ 33, 7, 163,144,145,153,154,155,133,173,157,158,159,160,161,246]

MOUTH_TOP     = 13
MOUTH_BOTTOM  = 14
MOUTH_LEFT    = 78
MOUTH_RIGHT   = 308
MOUTH_TOP2    = 312
MOUTH_BOTTOM2 = 317
