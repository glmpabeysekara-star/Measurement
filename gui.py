# ─────────────────────────────────────────────────────────────
#  gui.py  –  Tkinter touchscreen interface
#
#  Layout (matches the approved mockup):
#    ┌─────────────┬───────────────────────┐
#    │  Snapshot   │  Start  |  Stop        │
#    │  (1 fps)    │  Eyes-closed sec  -/+  │
#    │             │  Yawn window sec  -/+  │
#    │  Face: OK   │  Sensitivity | Reset   │
#    │  EAR / Yawn │  Shutdown              │
#    └─────────────┴───────────────────────┘
#
#  Runs entirely on the main thread (Tkinter requirement). Polls
#  the shared AppState every config.GUI_POLL_MS to refresh text,
#  colors, and the snapshot image. All camera/detection work
#  happens on the DetectionWorker's background thread.
# ─────────────────────────────────────────────────────────────

import subprocess
import sys
import tkinter as tk
from tkinter import font as tkfont

from PIL import Image, ImageTk

import config
from shared import Settings, AppState
from worker import DetectionWorker


# ── Color palette (dark, kiosk-style — readable in a car) ─────
BG_DARK      = "#1b1b1a"
PANEL_DARK   = "#242422"
CARD_DARK    = "#2a2a28"
BTN_DARK     = "#3a3a37"
TEXT_PRIMARY = "#f0f0ec"
TEXT_MUTED   = "#9a9a92"
GREEN        = "#2d6e3e"
GREEN_BRIGHT = "#3fae5a"
RED          = "#7a2d2d"
RED_BRIGHT   = "#d8453f"
AMBER        = "#a3791a"


class DrowsinessGUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.settings  = Settings()
        self.app_state = AppState()
        self.worker = DetectionWorker(self.settings, self.app_state)

        self._snapshot_photo = None   # keep a reference (Tk requirement)
        self._last_snapshot_ts = 0.0

        self._setup_window()
        self._build_layout()
        self._poll()   # begin the refresh loop

    # ── Window setup ──────────────────────────────────────────

    def _setup_window(self):
        self.root.title(config.WINDOW_TITLE)
        self.root.configure(bg=BG_DARK)

        if config.FULLSCREEN:
            self.root.attributes("-fullscreen", True)
        else:
            self.root.geometry(f"{config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}")

        self.root.bind("<Escape>", lambda e: self._on_close())
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Fonts scaled for a small screen
        self.font_label  = tkfont.Font(family="DejaVu Sans", size=9)
        self.font_value  = tkfont.Font(family="DejaVu Sans", size=12, weight="bold")
        self.font_button = tkfont.Font(family="DejaVu Sans", size=11, weight="bold")
        self.font_small  = tkfont.Font(family="DejaVu Sans", size=8)
        self.font_status = tkfont.Font(family="DejaVu Sans", size=11, weight="bold")

    # ── Layout ────────────────────────────────────────────────

    def _build_layout(self):
        outer = tk.Frame(self.root, bg=BG_DARK)
        outer.pack(fill="both", expand=True, padx=6, pady=6)

        # Left: camera/status panel  |  Right: controls
        left  = tk.Frame(outer, bg=BG_DARK, width=int(config.SCREEN_WIDTH * 0.42))
        right = tk.Frame(outer, bg=BG_DARK)
        left.pack(side="left", fill="y", padx=(0, 6))
        right.pack(side="left", fill="both", expand=True)

        self._build_left_panel(left)
        self._build_right_panel(right)

    def _build_left_panel(self, parent):
        cam_w = int(config.SCREEN_WIDTH * 0.40)
        cam_h = int(cam_w * 0.75)

        self.canvas = tk.Canvas(parent, width=cam_w, height=cam_h,
                                bg="black", highlightthickness=0)
        self.canvas.pack(pady=(0, 6))
        self._canvas_image_id = self.canvas.create_image(0, 0, anchor="nw")
        self._cam_w, self._cam_h = cam_w, cam_h

        self.live_badge = self.canvas.create_text(
            6, 8, anchor="nw", fill=GREEN_BRIGHT,
            font=self.font_small, text="● LIVE"
        )

        self.face_status_lbl = tk.Label(
            parent, text="Face: --", font=self.font_status,
            bg=CARD_DARK, fg=TEXT_PRIMARY, pady=6
        )
        self.face_status_lbl.pack(fill="x", pady=(0, 6))

        stats = tk.Frame(parent, bg=BG_DARK)
        stats.pack(fill="x")

        self.ear_card = self._make_stat_card(stats, "EAR", "0.00")
        self.ear_card["frame"].pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.yawn_card = self._make_stat_card(stats, "Yawns", "0/3")
        self.yawn_card["frame"].pack(side="left", expand=True, fill="x", padx=(3, 0))

    def _make_stat_card(self, parent, label_text, initial_value):
        frame = tk.Frame(parent, bg=CARD_DARK)
        lbl = tk.Label(frame, text=label_text, font=self.font_small,
                       bg=CARD_DARK, fg=TEXT_MUTED)
        lbl.pack(pady=(4, 0))
        val = tk.Label(frame, text=initial_value, font=self.font_value,
                       bg=CARD_DARK, fg=TEXT_PRIMARY)
        val.pack(pady=(0, 4))
        return {"frame": frame, "value_label": val}

    def _build_right_panel(self, parent):
        # Row 1: Start / Stop
        row1 = tk.Frame(parent, bg=BG_DARK)
        row1.pack(fill="x", pady=(0, 5))
        self.start_btn = self._make_button(
            row1, "▶ Start", GREEN, GREEN_BRIGHT, self._on_start
        )
        self.start_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        self.stop_btn = self._make_button(
            row1, "■ Stop", RED, RED_BRIGHT, self._on_stop
        )
        self.stop_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))

        # Row 2: Eyes-closed seconds adjuster
        self.eyes_closed_row, self.eyes_closed_val_lbl = self._make_adjuster_row(
            parent, "Eyes-closed time (s)",
            on_minus=lambda: self._adjust_eyes_closed(-config.EYES_CLOSED_SEC_STEP),
            on_plus=lambda: self._adjust_eyes_closed(config.EYES_CLOSED_SEC_STEP),
            initial_value=f"{self.settings.eyes_closed_sec:.1f}",
        )

        # Row 3: Yawn window adjuster
        self.yawn_window_row, self.yawn_window_val_lbl = self._make_adjuster_row(
            parent, "Yawn window (s)",
            on_minus=lambda: self._adjust_yawn_window(-config.YAWN_WINDOW_SEC_STEP),
            on_plus=lambda: self._adjust_yawn_window(config.YAWN_WINDOW_SEC_STEP),
            initial_value=f"{self.settings.yawn_window_sec:.0f}",
        )

        # Row 4: Sensitivity / Reset
        row4 = tk.Frame(parent, bg=BG_DARK)
        row4.pack(fill="x", pady=(0, 5))
        self.sensitivity_btn = self._make_button(
            row4, f"Sens: {self.settings.sensitivity_name}", BTN_DARK, "#4a4a47",
            self._on_cycle_sensitivity, font=self.font_label
        )
        self.sensitivity_btn.pack(side="left", expand=True, fill="x", padx=(0, 3))
        reset_btn = self._make_button(
            row4, "Reset", BTN_DARK, "#4a4a47", self._on_reset, font=self.font_label
        )
        reset_btn.pack(side="left", expand=True, fill="x", padx=(3, 0))

        # Row 5: Shutdown (separated, less prominent)
        shutdown_btn = self._make_button(
            parent, "⏻ Shutdown", BTN_DARK, "#5a3a3a", self._on_shutdown,
            font=self.font_label
        )
        shutdown_btn.pack(fill="x", pady=(8, 0))

    def _make_button(self, parent, text, bg, active_bg, command, font=None):
        btn = tk.Button(
            parent, text=text, command=command,
            bg=bg, fg=TEXT_PRIMARY, activebackground=active_bg,
            activeforeground=TEXT_PRIMARY, font=font or self.font_button,
            relief="flat", bd=0, padx=4, pady=10, cursor="hand2",
        )
        return btn

    def _make_adjuster_row(self, parent, label_text, on_minus, on_plus, initial_value):
        card = tk.Frame(parent, bg=CARD_DARK)
        card.pack(fill="x", pady=(0, 5))

        lbl = tk.Label(card, text=label_text, font=self.font_small,
                       bg=CARD_DARK, fg=TEXT_MUTED, anchor="w")
        lbl.pack(fill="x", padx=8, pady=(4, 0))

        ctrl = tk.Frame(card, bg=CARD_DARK)
        ctrl.pack(fill="x", padx=8, pady=(0, 6))

        minus_btn = tk.Button(
            ctrl, text="–", command=on_minus, bg=BTN_DARK, fg=TEXT_PRIMARY,
            activebackground="#4a4a47", font=self.font_button,
            relief="flat", bd=0, width=3, cursor="hand2",
        )
        minus_btn.pack(side="left")

        val_lbl = tk.Label(ctrl, text=initial_value, font=self.font_value,
                           bg=CARD_DARK, fg=TEXT_PRIMARY)
        val_lbl.pack(side="left", expand=True, fill="x")

        plus_btn = tk.Button(
            ctrl, text="+", command=on_plus, bg=BTN_DARK, fg=TEXT_PRIMARY,
            activebackground="#4a4a47", font=self.font_button,
            relief="flat", bd=0, width=3, cursor="hand2",
        )
        plus_btn.pack(side="right")

        return card, val_lbl

    # ── Button callbacks ──────────────────────────────────────

    def _on_start(self):
        self.worker.start()

    def _on_stop(self):
        self.worker.stop()

    def _on_reset(self):
        self.worker.reset_counters()

    def _adjust_eyes_closed(self, delta):
        new_val = self.settings.adjust_eyes_closed_sec(delta)
        self.eyes_closed_val_lbl.config(text=f"{new_val:.1f}")

    def _adjust_yawn_window(self, delta):
        new_val = self.settings.adjust_yawn_window_sec(delta)
        self.yawn_window_val_lbl.config(text=f"{new_val:.0f}")

    def _on_cycle_sensitivity(self):
        new_name = self.settings.cycle_sensitivity()
        self.sensitivity_btn.config(text=f"Sens: {new_name}")

    def _on_shutdown(self):
        self._confirm_shutdown()

    def _confirm_shutdown(self):
        # Simple inline confirmation overlay (touch-friendly, no popup dialogs)
        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.configure(bg=PANEL_DARK)
        w, h = 280, 140
        sw, sh = config.SCREEN_WIDTH, config.SCREEN_HEIGHT
        overlay.geometry(f"{w}x{h}+{(sw-w)//2}+{(sh-h)//2}")

        tk.Label(overlay, text="Shut down the Pi?", font=self.font_status,
                bg=PANEL_DARK, fg=TEXT_PRIMARY).pack(pady=(16, 12))

        btn_row = tk.Frame(overlay, bg=PANEL_DARK)
        btn_row.pack()

        def confirm():
            overlay.destroy()
            self._do_shutdown()

        def cancel():
            overlay.destroy()

        tk.Button(btn_row, text="Cancel", command=cancel, bg=BTN_DARK,
                  fg=TEXT_PRIMARY, relief="flat", bd=0, font=self.font_button,
                  padx=16, pady=8).pack(side="left", padx=8)
        tk.Button(btn_row, text="Shut down", command=confirm, bg=RED,
                  fg=TEXT_PRIMARY, relief="flat", bd=0, font=self.font_button,
                  padx=16, pady=8).pack(side="left", padx=8)

    def _do_shutdown(self):
        self._on_close()
        try:
            subprocess.run(["sudo", "shutdown", "-h", "now"])
        except Exception as e:
            print(f"[GUI] Shutdown command failed: {e}")
            sys.exit(0)

    def _on_close(self):
        self.worker.shutdown()
        self.root.destroy()

    # ── Polling loop (GUI thread reads shared state) ──────────

    def _poll(self):
        state = self.app_state.snapshot()
        self._update_camera_panel(state)
        self._update_status(state)
        self.root.after(config.GUI_POLL_MS, self._poll)

    def _update_camera_panel(self, state):
        if state["camera_error"]:
            self.canvas.delete("error_text")
            self.canvas.create_text(
                self._cam_w // 2, self._cam_h // 2, anchor="center",
                fill=RED_BRIGHT, font=self.font_small,
                text=state["camera_error"], tags="error_text",
                width=self._cam_w - 16,
            )
            return

        rgb_bytes = state["snapshot_rgb_bytes"]
        if rgb_bytes is None:
            return
        if state["snapshot_updated_at"] == self._last_snapshot_ts:
            return  # no new frame since last poll
        self._last_snapshot_ts = state["snapshot_updated_at"]

        w, h = state["snapshot_w"], state["snapshot_h"]
        photo = _rgb_bytes_to_photoimage(rgb_bytes, w, h, self._cam_w, self._cam_h)
        self._snapshot_photo = photo   # keep reference alive
        self.canvas.itemconfig(self._canvas_image_id, image=photo)
        self.canvas.delete("error_text")

    def _update_status(self, state):
        warnings = state["warnings"]
        metrics  = state["metrics"]

        # Face status label + color
        if warnings["no_face"]:
            self.face_status_lbl.config(text="NO FACE", bg=RED, fg=TEXT_PRIMARY)
        elif warnings["eyes_closed"]:
            self.face_status_lbl.config(text="EYES CLOSED", bg=RED, fg=TEXT_PRIMARY)
        elif warnings["yawn"]:
            self.face_status_lbl.config(text="YAWNING", bg=GREEN, fg=TEXT_PRIMARY)
        elif state["face_detected"]:
            self.face_status_lbl.config(text="Face OK", bg=CARD_DARK, fg=GREEN_BRIGHT)
        else:
            self.face_status_lbl.config(text="--", bg=CARD_DARK, fg=TEXT_MUTED)

        ear = metrics.get("ear", 0.0)
        self.ear_card["value_label"].config(text=f"{ear:.2f}")

        yawn_cnt = metrics.get("yawn_count", 0)
        self.yawn_card["value_label"].config(text=f"{yawn_cnt}/{config.YAWN_COUNT_TRIGGER}")

        # Live badge color reflects whether detection is actually running
        if self.settings.running and not state["camera_error"]:
            self.canvas.itemconfig(self.live_badge, fill=GREEN_BRIGHT,
                                   text=f"● LIVE {state['fps']:.0f}fps")
        else:
            self.canvas.itemconfig(self.live_badge, fill=TEXT_MUTED, text="● PAUSED")


def _rgb_bytes_to_photoimage(rgb_bytes: bytes, src_w: int, src_h: int,
                            dst_w: int, dst_h: int):
    """
    Convert raw RGB bytes to a Tkinter-compatible PhotoImage, resized
    to (dst_w, dst_h) via Pillow (fast — C-level resize, unlike a pure
    Python pixel loop which is far too slow for real-time use on a Pi 4).
    """
    img = Image.frombytes("RGB", (src_w, src_h), rgb_bytes)
    img = img.resize((dst_w, dst_h), Image.NEAREST)
    return ImageTk.PhotoImage(img)
