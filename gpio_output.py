# ─────────────────────────────────────────────────────────────
#  gpio_output.py  –  Two 3.3V logic GPIO outputs
#
#    RED pin   (config.GPIO_RED_PIN)   HIGH while eyes_closed OR no_face
#    GREEN pin (config.GPIO_GREEN_PIN) HIGH while yawn warning is active
#
#  Uses RPi.GPIO for direct Raspberry Pi GPIO control.
#
#  On a non-Pi machine (e.g. for local testing), RPi.GPIO raises
#  on import — this module catches that and runs in a no-op
#  "simulated" mode instead of crashing the whole app.
# ─────────────────────────────────────────────────────────────

import config

try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except Exception as e:
    _GPIO_AVAILABLE = False
    _IMPORT_ERROR = e
    GPIO = None


class GPIOWarningOutputs:
    """
    Call update(eyes_closed, yawn, no_face) every frame (or whenever
    warning state changes) to drive the two output pins.

    RED pin logic:   ON if eyes_closed OR no_face
    GREEN pin logic: ON if yawn
    """

    def __init__(self):
        self.enabled = config.GPIO_ENABLED and _GPIO_AVAILABLE
        self._last_red_state = None
        self._last_green_state = None

        if not config.GPIO_ENABLED:
            print("[GPIO] Disabled via config.GPIO_ENABLED = False.")
            return

        if not _GPIO_AVAILABLE:
            print(f"[GPIO] RPi.GPIO unavailable ({_IMPORT_ERROR}) — "
                  "running in simulated mode (no real pins driven). "
                  "This is expected when testing off a Raspberry Pi.")
            return

        try:
            GPIO.setmode(GPIO.BCM)
            GPIO.setup(config.GPIO_RED_PIN, GPIO.OUT, initial=GPIO.LOW)
            GPIO.setup(config.GPIO_GREEN_PIN, GPIO.OUT, initial=GPIO.LOW)
            print(f"[GPIO] RED → BCM{config.GPIO_RED_PIN}, "
                  f"GREEN → BCM{config.GPIO_GREEN_PIN} ready.")
        except Exception as e:
            print(f"[GPIO] Failed to setup pins ({e}) — "
                  "falling back to simulated mode.")
            self.enabled = False

    def update(self, eyes_closed: bool, yawn: bool, no_face: bool):
        """
        Drive both pins based on current warning state. Cheap to call
        every frame — GPIO.output() only updates if value has changed,
        but we also track state ourselves to avoid redundant calls and
        to support simulated-mode logging.
        """
        red_state = bool(eyes_closed or no_face)
        green_state = bool(yawn)

        if red_state != self._last_red_state:
            self._last_red_state = red_state
            if self.enabled and GPIO is not None:
                GPIO.output(config.GPIO_RED_PIN, GPIO.HIGH if red_state else GPIO.LOW)

        if green_state != self._last_green_state:
            self._last_green_state = green_state
            if self.enabled and GPIO is not None:
                GPIO.output(config.GPIO_GREEN_PIN, GPIO.HIGH if green_state else GPIO.LOW)

    def close(self):
        if self.enabled and GPIO is not None:
            GPIO.cleanup()
