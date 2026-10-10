#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path


def command(*arguments):
    result = subprocess.run(["systemctl", "--user", *arguments], capture_output=True, text=True, timeout=4)
    return result.returncode == 0


def switch(desktop, runtime):
    units = runtime / "systemd/user"
    record = runtime / "svent-session-services.json"
    try:
        previous = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        previous = []
    allowed = {"dunst.service", "dunst-z1rov-battery.timer", "dunst-z1rov-battery.service", "xfce4-notifyd.service"}
    if not isinstance(previous, list):
        previous = []
    for name in previous:
        if name in allowed:
            path = units / name
            if path.is_symlink() and os.readlink(path) == "/dev/null":
                path.unlink()
    blocked = ["dunst.service", "dunst-z1rov-battery.timer", "dunst-z1rov-battery.service"] if desktop == "xfce" else ["xfce4-notifyd.service"]
    units.mkdir(parents=True, exist_ok=True)
    owned = []
    for name in blocked:
        path = units / name
        if not path.exists() and not path.is_symlink():
            path.symlink_to("/dev/null")
            owned.append(name)
    temporary = record.with_suffix(".tmp")
    temporary.write_text(json.dumps(owned), encoding="utf-8")
    temporary.replace(record)
    command("daemon-reload")
    command("stop", *blocked)
    command("import-environment", "DISPLAY", "XAUTHORITY", "XDG_CURRENT_DESKTOP")
    if desktop == "xfce":
        command("start", "--no-block", "xfce4-notifyd.service")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("desktop", choices=("xfce", "bspwm"))
    args = parser.parse_args()
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if not runtime or not Path(runtime).is_dir():
        return
    try:
        switch(args.desktop, Path(runtime))
    except (OSError, subprocess.TimeoutExpired) as error:
        print("SventOS session service isolation: " + str(error))


if __name__ == "__main__":
    main()
