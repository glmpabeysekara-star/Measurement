#!/usr/bin/env python3
# ─────────────────────────────────────────────────────────────
#  download_model.py  –  Downloads face_landmarker.task
#  Called automatically by detector.py if the file is missing.
# ─────────────────────────────────────────────────────────────

import os
import sys
import urllib.request

import config


def download_model(dest: str = config.MODEL_PATH, url: str = config.MODEL_URL) -> bool:
    if os.path.exists(dest):
        size_mb = os.path.getsize(dest) / 1_048_576
        print(f"[Model] '{dest}' already present ({size_mb:.1f} MB) – skipping download.")
        return True

    print(f"[Model] Downloading face_landmarker.task (~30 MB)…")
    try:
        def _progress(block_count, block_size, total_size):
            if total_size <= 0:
                return
            pct = min(block_count * block_size / total_size * 100, 100)
            bar = "█" * int(pct // 5) + "░" * (20 - int(pct // 5))
            sys.stdout.write(f"\r        [{bar}] {pct:5.1f}%")
            sys.stdout.flush()

        urllib.request.urlretrieve(url, dest, reporthook=_progress)
        print()
        print(f"[Model] Download complete.")
        return True
    except Exception as e:
        print(f"\n[Model] Download failed: {e}")
        print(f"        Manually download from:\n        {url}")
        print(f"        and place it as '{dest}'.")
        return False


if __name__ == "__main__":
    sys.exit(0 if download_model() else 1)
