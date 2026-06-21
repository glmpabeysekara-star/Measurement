# ─────────────────────────────────────────────────────────────
#  gpio_output.py  –  Two 3.3V logic GPIO outputs
#
#    RED pin   (config.GPIO_RED_PIN)   HIGH while eyes_closed OR no_face
#    GREEN pin (config.GPIO_GREEN_PIN) HIGH while yawn warning is active
#
#  Uses gpiozero (the Raspberry Pi-recommended GPIO library on
#  Bookworm, backed by lgpio) so this works correctly on Pi 4
#  under current Raspberry Pi OS without extra drivers.
#
#  On a non-Pi machine (e.g. for local testing), gpiozero raises
#  on import/use — this module catches that and runs in a no-op
#  "simulated" mode instead of crashing the whole app, so the GUI
#  and detection logic can still be developed/tested off-Pi.
# ─────────────────────────────────────────────────────────────

import config

try:
    from gpiozero import OutputDevice
    _GPIOZERO_AVAILABLE = True
except Exception as e:
    _GPIOZERO_AVAILABLE = False
    _IMPORT_ERROR = e


class GPIOWarningOutputs:
    """
    Call update(eyes_closed, yawn, no_face) every frame (or whenever
    warning state changes) to drive the two output pins.

    RED pin logic:   ON if eyes_closed OR no_face
    GREEN pin logic: ON if yawn
    """

    def __init__(self):
        self.enabled = config.GPIO_ENABLED and _GPIOZERO_AVAILABLE
        self._red = None
        self._green = None
        self._last_red_state = None
        self._last_green_state = None

        if not config.GPIO_ENABLED:
            print("[GPIO] Disabled via config.GPIO_ENABLED = False.")
            return

        if not _GPIOZERO_AVAILABLE:
            print(f"[GPIO] gpiozero unavailable ({_IMPORT_ERROR}) — "
                  "running in simulated mode (no real pins driven). "
                  "This is expected when testing off a Raspberry Pi.")
            return

        try:
            self._red = OutputDevice(config.GPIO_RED_PIN, initial_value=False)
            self._green = OutputDevice(config.GPIO_GREEN_PIN, initial_value=False)
            print(f"[GPIO] RED → BCM{config.GPIO_RED_PIN} "
                  f"(physical pin), GREEN → BCM{config.GPIO_GREEN_PIN} ready.")
        except Exception as e:
            print(f"[GPIO] Failed to claim pins ({e}) — "
                  "falling back to simulated mode.")
            self.enabled = False
            self._red = None
            self._green = None

    def update(self, eyes_closed: bool, yawn: bool, no_face: bool):
        """
        Drive both pins based on current warning state. Cheap to call
        every frame — gpiozero/lgpio no-ops if the value hasn't changed,
        but we also track state ourselves to avoid redundant calls and
        to support simulated-mode logging.
        """
        red_state = bool(eyes_closed or no_face)
        green_state = bool(yawn)

        if red_state != self._last_red_state:
            self._last_red_state = red_state
            if self.enabled and self._red is not None:
                self._red.value = red_state

        if green_state != self._last_green_state:
            self._last_green_state = green_state
            if self.enabled and self._green is not None:
                self._green.value = green_state

    def close(self):
        if self._red is not None:
            self._red.close()
        if self._green is not None:
            self._green.close()
