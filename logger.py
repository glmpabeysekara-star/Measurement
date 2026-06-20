# ─────────────────────────────────────────────────────────────
#  logger.py  –  Optional per-frame CSV session logger
# ─────────────────────────────────────────────────────────────

import csv
import os
import time


class SessionLogger:
    COLUMNS = [
        "timestamp", "elapsed_s",
        "ear", "mar", "perclos_pct", "pitch_deg",
        "alert_ear", "alert_mar", "alert_perclos", "alert_head",
    ]

    def __init__(self, output_dir: str = "."):
        os.makedirs(output_dir, exist_ok=True)
        ts = time.strftime("%Y%m%d_%H%M%S")
        self.path = os.path.join(output_dir, f"session_{ts}.csv")
        self._start  = time.time()
        self._fh     = open(self.path, "w", newline="")
        self._writer = csv.DictWriter(self._fh, fieldnames=self.COLUMNS)
        self._writer.writeheader()
        self._rows   = 0
        print(f"[Logger] Writing to {self.path}")

    def log(self, metrics: dict, alerts: dict):
        now = time.time()
        self._writer.writerow({
            "timestamp":     time.strftime("%H:%M:%S"),
            "elapsed_s":     round(now - self._start, 2),
            "ear":           round(metrics.get("ear",     0.0), 4),
            "mar":           round(metrics.get("mar",     0.0), 4),
            "perclos_pct":   round(metrics.get("perclos", 0.0) * 100, 2),
            "pitch_deg":     round(metrics.get("pitch",   0.0), 2),
            "alert_ear":     int(alerts.get("ear",     False)),
            "alert_mar":     int(alerts.get("mar",     False)),
            "alert_perclos": int(alerts.get("perclos", False)),
            "alert_head":    int(alerts.get("head",    False)),
        })
        self._rows += 1
        if self._rows % 300 == 0:
            self._fh.flush()

    def close(self):
        self._fh.flush()
        self._fh.close()
        print(f"[Logger] Saved {self._rows} frames → {self.path}")
