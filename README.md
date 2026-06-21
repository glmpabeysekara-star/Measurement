# Drowsiness Monitor — Raspberry Pi 4 Touchscreen Edition

Driver drowsiness monitor with a touchscreen GUI for a 3.5"
480×320 ILI9486/XPT2046 SPI touchscreen on a Raspberry Pi 4 Model B.

---

## Why the camera panel updates only ~1×/second

Your panel (ILI9486, 480×320, XPT2046 touch, SPI Fmax 32MHz) is a
classic SPI-bus display. A 480×320 16-bit-color frame is
480×320×16 = 2.46 million bits. At a 32MHz bus clock, with real-world
overhead, that caps out well under 10 full-screen refreshes per
second — and many of these ILI9486 panels only sustain
16-24MHz reliably in practice, pushing the real ceiling closer to
3-5fps for full motion video. Streaming a live annotated camera
feed onto a panel like this looks laggy and choppy — the bottleneck
is the hardware bus itself, not this code.

So this version **separates detection from display**:
- The camera + MediaPipe run continuously, in the background, at
  full speed — eyes-closed timing and yawn counting are accurate
  to the frame.
- The touchscreen shows a **1fps snapshot** (configurable) plus
  live numeric stats (EAR, yawn count) and big color-coded warning
  banners — all of which update smoothly because they're just text
  and color changes, not video.

If you add an HDMI monitor later, you get the full original
annotated-video experience for free — this code doesn't change.

---

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  DetectionWorker      │  AppState │  DrowsinessGUI         │
│  (background thread)  │ ───────▶ │  (Tkinter, main thread)│
│                       │  shared  │                        │
│  - camera capture      │  state   │  - snapshot panel       │
│  - MediaPipe detector  │ ◀─────── │  - status indicators    │
│  - alarm beeping       │ Settings │  - touch buttons        │
│  - GPIO RED/GREEN out  │          │                        │
└─────────────────────┘         └──────────────────────┘
```

- `shared.py` — `Settings` (GUI → detector) and `AppState`
  (detector → GUI), both thread-safe via locks.
- `worker.py` — owns the camera, detector, alarm, and GPIO outputs;
  runs its own loop on a background `threading.Thread`.
- `detector.py` — same EAR/MAR/no-face logic as before, but headless
  (no OpenCV drawing — the GUI does all rendering).
- `gpio_output.py` — drives the RED/GREEN GPIO pins based on
  warning state; falls back to a safe no-op mode off-Pi.
- `gui.py` — Tkinter interface; polls `AppState` every
  `config.GUI_POLL_MS` and redraws.
- `main.py` — wires it together and starts `root.mainloop()`.

---

## Files

```
pi_gui_drowsiness/
├── main.py            ← Entry point — run this
├── gui.py              ← Tkinter touchscreen interface
├── worker.py            ← Background camera/detection thread
├── detector.py          ← EAR/MAR/no-face detection logic (headless)
├── shared.py            ← Thread-safe Settings + AppState
├── alarm.py             ← Continuous short-beep sound
├── gpio_output.py       ← RED/GREEN GPIO warning pin outputs
├── config.py            ← All settings (screen size, thresholds, GPIO pins, etc.)
└── download_model.py    ← Auto-downloads face_landmarker.task
```

---

## Hardware Setup — Your Display (ILI9486 + XPT2046, 480×320, SPI 32MHz max)

This is a common "3.5 inch SPI TFT" panel sold under many brand
names (Waveshare, Kuman, Elegoo, generic). On modern Raspberry Pi
OS (Bookworm), you do **not** need to compile any third-party
driver — the kernel already includes a `piscreen` device tree
overlay that handles both the ILI9486 display and the XPT2046
touch controller together.

> **Important — do not use fbcp-ili9341 with this panel.** That
> driver (suggested in earlier guides for *other* SPI displays) is
> explicitly incompatible with XPT2046/ADS7846 touch controllers —
> using it would disable your touchscreen entirely. The `piscreen`
> overlay below is the correct approach for this exact hardware.

### 1. Connect the display
Plug it directly onto the Pi's 40-pin GPIO header (it's designed to
sit flush on top — no jumper wires needed for a standard HAT-style
3.5" panel).

### 2. Enable SPI
```bash
sudo raspi-config
# Interface Options → SPI → Enable
```

### 3. Add the display overlay
Edit the boot config (Bookworm path shown; use `/boot/config.txt`
on older Pi OS releases):
```bash
sudo nano /boot/firmware/config.txt
```
Add this line at the end:
```
dtoverlay=piscreen,drm,speed=24000000,rotate=90
```
- `drm` — uses the modern DRM/KMS driver (recommended on Bookworm;
  lets the display work alongside HDMI rather than only one or the
  other).
- `speed=24000000` — 24MHz, comfortably under your panel's 32MHz
  max while leaving margin for reliable communication. You can try
  raising it toward `32000000` afterward if the picture stays clean.
- `rotate=90` — landscape orientation (480 wide × 320 tall). Use
  `0` or `270` instead if the image appears sideways or upside down
  for your specific mounting.

If the touch axes are inverted or swapped once running, add
`,invx` and/or `,invy` and/or `,swapxy` to the same line, e.g.:
```
dtoverlay=piscreen,drm,speed=24000000,rotate=90,swapxy=1
```

### 4. Reboot
```bash
sudo reboot
```
The display should now show the Pi's desktop (or console) directly
— no extra background process required, unlike fbcp-style drivers.

### 5. Calibrate touch (only if taps land in the wrong place)
```bash
sudo apt install -y xinput-calibrator
xinput_calibrator
```
Follow the on-screen crosshair prompts; it prints a config snippet
to save under `/etc/X11/xorg.conf.d/`.

---

## GPIO Warning Outputs (RED / GREEN)

Two 3.3V logic-level GPIO outputs go HIGH while their warning is
active and LOW otherwise — for driving an LED, a transistor-driven
relay/buzzer module, or an opto-isolator input.

| Warning | BCM GPIO | Physical pin | Logic |
|---|---|---|---|
| **RED** | GPIO22 | **Pin 15** | HIGH while `eyes_closed` OR `no_face` |
| **GREEN** | GPIO5 | **Pin 29** | HIGH while `yawn` |

Both pins were chosen specifically to avoid every pin the
`piscreen` display/touch overlay uses (SPI bus, chip-selects,
reset, backlight, touch IRQ — 9 pins total), and both sit on the
header's **outer row** (odd-numbered physical pins) so they're
reachable with jumper wires even with the display board mounted
on top.

```
Pin 15 (GPIO22) ──► RED warning   (eyes closed / no face)
Pin 29 (GPIO5)  ──► GREEN warning (yawning)
Pin 6, 9, 14, 20, 25, 30, 34, or 39 ──► any GND pin for your circuit's return path
```

> **3.3V logic only.** These pins are not 5V tolerant and cannot
> drive a load directly — wire each one into an LED (with a
> current-limiting resistor, e.g. 330Ω), the trigger input of a
> transistor/relay driver module, or an opto-isolator, exactly as
> you'd wire any other Pi GPIO output.

### Software setup
```bash
sudo apt install -y python3-gpiozero
# gpiozero is also installed by default on the Raspberry Pi OS
# desktop image — the apt install above is just to be sure.
```
`gpiozero` (backed by `lgpio`) is the Pi-recommended GPIO library
on current Raspberry Pi OS and is what `gpio_output.py` uses.

### Toggle on/off
Set `GPIO_ENABLED = False` in `config.py` to disable both outputs
entirely (e.g. while testing off a Pi) without touching any other
code — `gpio_output.py` automatically falls back to a no-op
simulated mode if `gpiozero` or real GPIO hardware isn't available,
so the rest of the app keeps working normally either way.

### Changing pins
If you need different pins later, edit `GPIO_RED_PIN` and
`GPIO_GREEN_PIN` in `config.py` (BCM numbering) — just make sure
whatever you pick still avoids the display's 9 reserved pins
(BCM 7, 8, 9, 10, 11, 17, 22, 24, 25).

---

## Software Setup

```bash
# System packages (Pillow + Tk are usually preinstalled on Pi OS,
# but make sure):
sudo apt install -y python3-tk python3-pil python3-pil.imagetk python3-gpiozero

# Python packages
pip install mediapipe opencv-python scipy numpy Pillow --break-system-packages
```

`config.py` is already set for your panel:
```python
SCREEN_WIDTH  = 480
SCREEN_HEIGHT = 320
FULLSCREEN    = True  # set False while developing on a regular desktop
```

Run it:
```bash
python main.py
```
The FaceLandmarker model (~30 MB) downloads automatically on first
run — make sure the Pi has internet access at least once.

Since the `piscreen,drm` overlay registers as a normal DRM display,
Tkinter/X11 draws on it the same way it would on HDMI — no special
framebuffer redirection needed, unlike older fbcp-style drivers.

---

## Touchscreen Controls

| Control | Effect |
|---|---|
| **Start** | Resumes camera + detection (also runs automatically on launch) |
| **Stop** | Pauses camera + detection; alarm silences; screen shows "PAUSED" |
| **Eyes-closed time –/+** | Adjusts the RED-warning threshold, 0.5–5.0s in 0.5s steps |
| **Yawn window –/+** | Adjusts the sliding yawn-counting window, 10–180s in 10s steps |
| **Sensitivity** | Cycles Low → Medium → High, adjusting EAR/MAR thresholds together |
| **Reset** | Zeroes all event counters and timers |
| **Shutdown** | Confirms, then runs `sudo shutdown -h now` |

All adjustments take effect immediately on the next camera frame —
no restart needed.

> **Shutdown button needs passwordless sudo.** Add this line via
> `sudo visudo` (replace `pi` with your username if different):
> ```
> pi ALL=(ALL) NOPASSWD: /sbin/shutdown
> ```

### Troubleshooting the display

- **Screen stays blank after reboot** — double check you edited
  `/boot/firmware/config.txt` (not the legacy `/boot/config.txt`
  path, which is ignored on current Bookworm releases) and that
  SPI is enabled via `raspi-config`.
- **Picture is garbled or flickering** — lower `speed=24000000` to
  `speed=16000000` in the overlay line; some panels of this type
  are less tolerant of higher SPI clocks than their datasheet
  suggests.
- **Touch registers but taps land in the wrong place** — add
  `,swapxy=1` to the overlay line, or run `xinput_calibrator`
  (see step 5 above).
- **Display works but HDMI no longer does (or vice versa)** — the
  `,drm` variant of the overlay is specifically meant to support
  *both* outputs simultaneously; if you're missing one, confirm you
  used `dtoverlay=piscreen,drm,...` and not the older non-DRM form.

---

## Running the App

This app is launched manually — there's no boot-time autostart.
Each time you want to use it:

```bash
cd /path/to/pi_gui_drowsiness
python main.py
```

It opens full-screen (`config.FULLSCREEN = True`) on whichever
display is active — the SPI panel if that's your primary display,
or HDMI if connected. Press `Esc` or use the on-screen Shutdown
button to exit.

If you'd like it to launch automatically when the Pi boots later,
that's a small addition (a desktop autostart entry) — let me know
and it can be added back in.

---

## Performance Notes (this panel, specifically)

- Your panel's SPI bus tops out at 32MHz; `dtoverlay=piscreen,drm,speed=24000000`
  runs it at 24MHz for reliability margin. Even at the full 32MHz, a
  480×320 panel cannot sustain smooth full-motion video — this is
  why the GUI uses a 1fps snapshot instead of live video (see top
  of this README).
- Camera capture resolution is kept at 320×240 (`config.FRAME_WIDTH/HEIGHT`)
  to leave CPU headroom for MediaPipe — raising this will slow detection.
  This is independent of the *display* resolution (480×320) — the
  snapshot is simply scaled up to fit the panel.
- The GUI polls shared state every 150ms (`config.GUI_POLL_MS`) — this is
  independent of camera FPS, so the touch interface stays responsive even
  if detection briefly lags.
- Pillow (not raw Tkinter `PhotoImage.put()`) is used for snapshot
  resizing — a pure-Python pixel loop was benchmarked at ~100× slower
  and would visibly stutter the GUI even at 1fps.
- If the touchscreen GUI itself feels sluggish, try lowering
  `SNAPSHOT_FPS` to 0.5 — the detection logic is unaffected either way.
- 4-wire resistive touch (XPT2046) needs a firmer, more deliberate
  press than capacitive touchscreens — if taps feel unresponsive,
  this is normal for the technology, not a software bug.

---

## Tuning (`config.py`)

| Setting | Default | Notes |
|---|---|---|
| `EYES_CLOSED_SEC_DEFAULT` | 2.0 | Starting value; adjustable live via touch |
| `YAWN_WINDOW_SEC_DEFAULT` | 60 | Starting value; adjustable live via touch |
| `YAWN_COUNT_TRIGGER` | 3 | Yawns needed in the window → GREEN warning |
| `YAWN_WARNING_DISPLAY_SEC` | 5 | How long the GREEN warning stays visible |
| `SENSITIVITY_PRESETS` | Low/Medium/High | EAR+MAR threshold pairs cycled by the Sensitivity button |
| `SNAPSHOT_FPS` | 1.0 | Camera panel update rate |
| `GUI_POLL_MS` | 150 | How often the GUI refreshes from shared state |
| `FRAME_WIDTH/HEIGHT` | 320×240 | Camera capture resolution |
| `SCREEN_WIDTH/HEIGHT` | 480×320 | Match to your actual panel |
| `FULLSCREEN` | True | Set False for desktop development/testing |

---

## MediaPipe Landmark Indices Used

```
Right eye EAR : [362, 385, 387, 263, 373, 380]
Left eye EAR  : [ 33, 160, 158, 133, 153, 144]
Mouth MAR     : top=13, bottom=14, left=78, right=308, top2=312, bottom2=317
```
