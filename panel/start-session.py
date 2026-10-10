#!/usr/bin/env python3
import json
import importlib.util
import os
import subprocess
import sys
import time
from pathlib import Path


def main():
    started = time.monotonic()
    folder = Path(__file__).resolve().parent
    timings = {"started_at": started, "steps": []}
    for name in ("session-services.py", "prepare-desktop.py"):
        before = time.monotonic()
        try:
            spec = importlib.util.spec_from_file_location(name.replace("-", "_"), folder / name)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            if name == "session-services.py":
                runtime = os.environ.get("XDG_RUNTIME_DIR")
                if runtime and Path(runtime).is_dir():
                    module.switch("xfce", Path(runtime))
            else:
                arguments = sys.argv
                try:
                    sys.argv = [str(folder / name), "--offline"]
                    module.main()
                finally:
                    sys.argv = arguments
            status = 0
        except Exception as error:
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
    if runtime:
        subprocess.Popen([sys.executable, str(folder / "observe-startup.py")],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
    os.execv("/etc/xdg/xfce4/xinitrc", ["/etc/xdg/xfce4/xinitrc", *sys.argv[1:]])


if __name__ == "__main__":
    main()
