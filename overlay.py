# ─────────────────────────────────────────────────────────────
#  overlay.py  –  Three warning banners
#
#    RED   → eyes closed > config.EYES_CLOSED_SEC seconds
#    RED   → no face detected (instant)
#    GREEN → config.YAWN_COUNT_TRIGGER yawns within the current
#            sliding window; shown for config.YAWN_WARNING_DISPLAY_SEC
#            seconds, then auto-hides (window also resets at that instant)
#
#  Priority when multiple are active: no_face > eyes_closed > yawn
#  (no face means we can't even verify eye state, so it's most urgent)
# ─────────────────────────────────────────────────────────────

import cv2
import numpy as np

_FONT    = cv2.FONT_HERSHEY_DUPLEX
_FONT_SM = cv2.FONT_HERSHEY_SIMPLEX


def _draw_banner(frame: np.ndarray, color_bgr: tuple, headline: str, sub: str):
    h, w = frame.shape[:2]

    tint = frame.copy()
    cv2.rectangle(tint, (0, 0), (w, h), color_bgr, -1)
    cv2.addWeighted(tint, 0.35, frame, 0.65, 0, frame)

    cv2.rectangle(frame, (3, 3), (w - 3, h - 3), color_bgr, 5)

    sc, tk = 1.5, 3
    (tw, th), _ = cv2.getTextSize(headline, _FONT, sc, tk)
    cx = (w - tw) // 2
    cy = h // 2
    cv2.putText(frame, headline, (cx + 2, cy + 2), _FONT, sc, (0, 0, 0), tk + 2)
    cv2.putText(frame, headline, (cx, cy),         _FONT, sc, (255, 255, 255), tk)

    sc2 = 0.62
    (sw, _), _ = cv2.getTextSize(sub, _FONT_SM, sc2, 2)
    cv2.putText(frame, sub, ((w - sw) // 2, cy + 42), _FONT_SM, sc2, (255, 255, 255), 2)


def draw_warnings(frame: np.ndarray, eyes_closed: bool, yawn: bool, no_face: bool):
    """
    Draws the single highest-priority active warning banner.
    Priority: no_face > eyes_closed > yawn
    """
    if no_face:
        _draw_banner(
            frame,
            color_bgr=(0, 0, 200),                       # red
            headline="! NO FACE DETECTED !",
            sub="Make sure your face is visible to the camera",
        )
    elif eyes_closed:
        _draw_banner(
            frame,
            color_bgr=(0, 0, 200),                       # red
            headline="! EYES CLOSED !",
            sub="Wake up — pull over safely",
        )
    elif yawn:
        _draw_banner(
            frame,
            color_bgr=(0, 160, 0),                        # green
            headline="FREQUENT YAWNING DETECTED",
            sub="Signs of fatigue — consider taking a break",
        )


def draw_status_bar(frame: np.ndarray, fps: float, elapsed_sec: float):
    h, w = frame.shape[:2]
    bar_h = 28
    cv2.rectangle(frame, (0, h - bar_h), (w, h), (15, 15, 15), -1)

    m, s = divmod(int(elapsed_sec), 60)
    cv2.putText(frame, f"FPS {fps:4.1f}", (10, h - 8), _FONT_SM, 0.45, (150, 150, 150), 1)
    cv2.putText(frame, f"Session {m:02d}:{s:02d}", (w // 2 - 50, h - 8),
                _FONT_SM, 0.45, (150, 150, 150), 1)
    cv2.putText(frame, "Q quit  R reset", (w - 145, h - 8),
                _FONT_SM, 0.40, (100, 100, 100), 1)
