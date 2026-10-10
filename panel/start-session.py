#!/usr/bin/env python3
import json
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    started = time.monotonic()
    folder = Path(__file__).resolve().parent
    timings = {"started_at": started, "steps": []}
    for name, arguments, limit in (("session-services.py", ["xfce"], 2),
                                    ("prepare-desktop.py", ["--offline"], 2)):
        before = time.monotonic()
        try:
            result = subprocess.run([sys.executable, str(folder / name), *arguments], timeout=limit)
            status = result.returncode
        except (OSError, subprocess.TimeoutExpired) as error:
            print("SventOS startup: " + str(error), file=sys.stderr)
            status = -1
        timings["steps"].append({"name": name, "seconds": round(time.monotonic() - before, 4), "status": status})
    timings["native_handoff_at"] = time.monotonic()
    timings["seconds"] = round(timings["native_handoff_at"] - started, 4)
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        try:
            (Path(runtime) / "svent-xfce-startup.json").write_text(json.dumps(timings, indent=2), encoding="utf-8")
        except OSError:
            pass
    os.execv("/etc/xdg/xfce4/xinitrc", ["/etc/xdg/xfce4/xinitrc", *sys.argv[1:]])


if __name__ == "__main__":
    main()
