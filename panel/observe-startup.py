#!/usr/bin/env python3
import json
import os
import re
import subprocess
import time
from pathlib import Path


def main():
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime:
        return
    report = Path(runtime) / "svent-xfce-readiness.json"
    started = time.monotonic()
    events = {}
    samples = []
    for number in range(25):
        now = time.monotonic()
        try:
            result = subprocess.run(["xwininfo", "-root", "-tree"], capture_output=True, text=True, timeout=0.5)
            for name in ("xfce4-panel", "xfdesktop"):
                if name in events:
                    continue
                for line in result.stdout.splitlines():
                    if '"' + name + '"' in line.lower():
                        match = re.search(r"0x[0-9a-fA-F]+", line)
                        if match:
                            info = subprocess.run(["xwininfo", "-id", match[0]], capture_output=True, text=True, timeout=0.5)
                            if "Map State: IsViewable" in info.stdout:
                                events[name] = {"observed_at": time.monotonic(), "window": match[0]}
                                break
        except (OSError, subprocess.TimeoutExpired) as error:
            samples.append(str(error))
            if isinstance(error, FileNotFoundError):
                break
        report.write_text(json.dumps({"started_at": started, "mapped_windows": events, "errors": samples}, indent=2), encoding="utf-8")
        if len(events) == 2:
            break
        time.sleep(max(0, 1 - (time.monotonic() - now)))


if __name__ == "__main__":
    main()
