#!/usr/bin/env python3
import fcntl
import os
import re
import subprocess
from pathlib import Path


def main():
    display = os.environ.get("DISPLAY")
    if not display:
        return
    runtime = Path(os.environ.get("XDG_RUNTIME_DIR", str(Path.home() / ".cache"))) / "svent-xfce"
    runtime.mkdir(parents=True, exist_ok=True)
    lock_path = runtime / ("super-key-" + re.sub(r"[^a-zA-Z0-9_-]", "_", display) + ".lock")
    with lock_path.open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        result = subprocess.run(
            ["xcape", "-d", "-t", "1000", "-e", "Super_L=Alt_L|F1;Super_R=Alt_L|F1"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        if result.returncode:
            raise SystemExit("Cannot activate the Svent menu key")


if __name__ == "__main__":
    main()
