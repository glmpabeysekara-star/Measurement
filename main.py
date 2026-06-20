#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
#  main.py  –  Raspberry Pi touchscreen drowsiness monitor
#
#  Camera/detection runs on a background thread (worker.py).
#  Tkinter GUI runs on the main thread (required by Tk) and
#  polls shared state every config.GUI_POLL_MS (gui.py).
#
#  Run:  python main.py
#  Kiosk autostart: see README.md for the systemd service setup.
# ─────────────────────────────────────────────────────────────

import tkinter as tk

import config
from gui import DrowsinessGUI


def main():
    root = tk.Tk()
    app = DrowsinessGUI(root)

    # Auto-start detection immediately on launch (kiosk behaviour) —
    # remove this line if you'd rather require a manual Start press.
    app.worker.start()

    print("\n" + "═" * 50)
    print("  Drowsiness Monitor — Touchscreen GUI")
    print("═" * 50)
    print(f"  Screen        : {config.SCREEN_WIDTH}x{config.SCREEN_HEIGHT}")
    print(f"  Fullscreen    : {config.FULLSCREEN}")
    print(f"  Snapshot rate : {config.SNAPSHOT_FPS} fps")
    print("  Press Esc (or the Shutdown button) to exit/shut down.")
    print("═" * 50 + "\n")

    root.mainloop()


if __name__ == "__main__":
    main()
