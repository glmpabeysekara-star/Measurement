# Drowsiness Detection — 3-Warning Edition

Driver drowsiness monitor using **MediaPipe FaceLandmarker**.
Tracks three warning conditions, each with a sound alert:

| # | Signal | Trigger | Warning |
|---|--------|---------|---------|
| 1 | Eyes closed continuously | ≥ **2.0 seconds** (adjustable) | 🔴 **RED**: "EYES CLOSED" + beeps |
| 2 | Yawns in a sliding window | **3 yawns** within **60 seconds** (both adjustable) | 🟢 **GREEN** for 5s (adjustable) + beeps |
| 3 | Face not detected | Instantly, on the very first missing-face frame | 🔴 **RED**: "NO FACE DETECTED" + beeps |

If more than one condition is active at once, only one banner shows,
in priority order: **no_face > eyes_closed > yawn**. Sound plays for
**any** active warning, regardless of which banner is shown.

---

## How the Yawn Window Works (sliding / self-resetting)

This is different from a fixed clock cycle — the window **resets the
instant it triggers**, not on a fixed schedule:

1. A window starts (e.g. at t = 0s) and can last up to `YAWN_WINDOW_SEC`
   (default 60s).
2. Yawns are counted as they happen inside that window.
3. The **instant** the count reaches `YAWN_COUNT_TRIGGER` (default 3) —
   even if that's after only 9 seconds — three things happen at once:
   - The GREEN warning appears.
   - The yawn count resets to **0** immediately.
   - A **brand-new window starts right then**, not at some fixed
     60-second mark.
4. The GREEN warning stays visible for `YAWN_WARNING_DISPLAY_SEC`
   (default 5s), then auto-hides on its own.
5. If 3 yawns are *not* reached within `YAWN_WINDOW_SEC`, the window
   also quietly resets to 0 at that point (so very old isolated yawns
   eventually drop off and don't carry over forever).

**Example** (exactly the case you described):
```
t=0s     window starts, count=0
t=3s     yawn #1 → count=1
t=6s     yawn #2 → count=2
t=9s     yawn #3 → count resets to 0 IMMEDIATELY, GREEN warning appears
t=14s    GREEN warning auto-hides (5s elapsed)
t=9s     ← a NEW 60-second window has already started here, at t=9s,
           not at t=60s. The next yawn-burst is counted fresh from t=9s.
```

---

## How the No-Face Warning Works

- The moment a video frame has no detected face, the RED "NO FACE
  DETECTED" warning appears — **no delay, no debounce**.
- It clears the instant a face is detected again.
- While no face is visible, eye/mouth tracking is paused (there's
  nothing to measure), so the eyes-closed timer also resets — it
  picks back up once the face returns.

---

## Files

```
simple_drowsiness/
├── main.py            ← Entry point — run this
├── detector.py        ← EAR timer + sliding yawn window + no-face check
├── overlay.py         ← Red / green warning banners (priority-ordered)
├── alarm.py           ← Continuous short-beep sound (non-blocking)
├── config.py          ← All thresholds — including the adjustable ones
└── download_model.py  ← Auto-downloads face_landmarker.task
```

---

## Quick Start

```bash
pip install mediapipe opencv-python scipy numpy
python main.py
```

The FaceLandmarker model (~30 MB) downloads automatically on first run.

---

## Controls

| Key | Action |
|-----|--------|
| `Q` | Quit, print summary |
| `R` | Reset all timers/counters and stop any active alarm |

---

## Adjustable Settings (`config.py`)

| Setting | Default | Description |
|---------|---------|-------------|
| `EAR_THRESHOLD` | 0.22 | EAR below this = eyes closed |
| `EYES_CLOSED_SEC` | 2.0 | Continuous closed-eye seconds → RED warning |
| `MAR_THRESHOLD` | 0.65 | MAR above this = mouth open (yawn) |
| `MAR_CONSEC_FRAMES` | 12 | Frames mouth must stay open to count as 1 yawn |
| **`YAWN_WINDOW_SEC`** | **60** | **Sliding window length (seconds) — adjustable** |
| `YAWN_COUNT_TRIGGER` | 3 | Yawns needed within the window → GREEN warning |
| **`YAWN_WARNING_DISPLAY_SEC`** | **5** | **How long the GREEN banner stays visible — adjustable** |
| `NO_FACE_WARNING_ENABLED` | True | Toggle the no-face RED warning on/off |
| **`BEEP_INTERVAL_SEC`** | **0.4** | **Gap between beeps while any warning is active — adjustable** |
| `ALARM_SOUND_PATH` | None | Optional WAV/MP3 file path; `None` → system beep |
| `CAMERA_INDEX` | 0 | 0 = built-in webcam |

To make the yawn window shorter for testing, try:
```python
YAWN_WINDOW_SEC = 20   # quick demo window
```

---

## Sound

All three warnings produce **continuous short beeps** for as long as
the warning condition is active — implemented in `alarm.py` on a
background thread so the video loop never freezes.

- **Default:** terminal bell (`\a`) on Linux/macOS, or `winsound.Beep()`
  on Windows, repeating every `BEEP_INTERVAL_SEC`.
- **Custom sound:** set `ALARM_SOUND_PATH = "alarm.wav"` in `config.py`
  and place the file in the project folder — it loops continuously via
  `pygame` instead of the system beep.

---

## Tuning Tips

| Problem | Fix |
|---------|-----|
| RED (eyes) fires too easily on normal blinks | Increase `EYES_CLOSED_SEC`, or lower `EAR_THRESHOLD` |
| RED (eyes) too slow to trigger | Decrease `EYES_CLOSED_SEC` (e.g. 1.5) |
| Yawns not being detected | Lower `MAR_THRESHOLD` to 0.55–0.60 |
| One yawn counted as multiple | Increase `MAR_CONSEC_FRAMES` to 15–18 |
| GREEN too strict | Lower `YAWN_COUNT_TRIGGER` to 2, or increase `YAWN_WINDOW_SEC` |
| GREEN banner disappears too fast/slow | Adjust `YAWN_WARNING_DISPLAY_SEC` |
| RED (no face) too sensitive to brief glitches | Set `NO_FACE_WARNING_ENABLED = False`, or ask for a debounced version |
| Beeping too rapid/slow | Adjust `BEEP_INTERVAL_SEC` |

---

## MediaPipe Landmark Indices Used

```
Right eye EAR : [362, 385, 387, 263, 373, 380]
Left eye EAR  : [ 33, 160, 158, 133, 153, 144]
Mouth MAR     : top=13, bottom=14, left=78, right=308, top2=312, bottom2=317
```
