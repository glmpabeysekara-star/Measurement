# ─────────────────────────────────────────────────────────────
#  alarm.py  –  Continuous short-beep warning sound
#
#  Plays repeated short beeps (or a custom WAV/MP3 clip) in a
#  background thread for as long as start() has been called more
#  recently than stop(). Non-blocking — never freezes the video loop.
# ─────────────────────────────────────────────────────────────

import os
import sys
import threading
import time

import config


class AlarmSystem:
    def __init__(self, sound_path: str | None = None,
                 beep_interval: float = config.BEEP_INTERVAL_SEC):
        self._playing       = False
        self._thread        = None
        self._pygame_ok     = False
        self.beep_interval  = beep_interval

        if sound_path and os.path.exists(sound_path):
            try:
                import pygame
                pygame.mixer.init()
                self._sound = pygame.mixer.Sound(sound_path)
                self._pygame_ok = True
                print(f"[Alarm] Loaded custom sound: {sound_path}")
            except Exception as e:
                print(f"[Alarm] pygame failed ({e}) – using system beep fallback.")
        else:
            print("[Alarm] Using continuous system beep "
                  f"(every {beep_interval}s while a warning is active).")

    def start(self):
        """Begin beeping (no-op if already beeping)."""
        if not self._playing:
            self._playing = True
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        """Stop beeping."""
        self._playing = False

    @property
    def is_playing(self) -> bool:
        return self._playing

    def _loop(self):
        while self._playing:
            if self._pygame_ok:
                self._sound.play()
            else:
                self._beep()
            time.sleep(self.beep_interval)

    @staticmethod
    def _beep():
        if sys.platform == "win32":
            import winsound
            winsound.Beep(1200, 120)     # 1.2 kHz, 120 ms short beep
        else:
            sys.stdout.write("\a")
            sys.stdout.flush()
