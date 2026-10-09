#!/usr/bin/env python3
import shutil
import subprocess
import sys
from pathlib import Path

app = sys.argv[1]
commands = {"files": [["exo-open", "--launch", "FileManager"]], "firefox": [["firefox"], ["firefox-esr"]], "tor": [["torbrowser-launcher"], ["tor-browser"], ["torbrowser"]], "terminal": [["exo-open", "--launch", "TerminalEmulator"]]}
for command in commands[app]:
    if shutil.which(command[0]):
        subprocess.Popen(command, start_new_session=True)
        raise SystemExit(0)
if app == "tor":
    for folder in [Path.home()/".local/share/applications", Path("/usr/share/applications")]:
        for desktop in sorted(folder.glob("*.desktop")):
            if "tor" not in desktop.name.lower():
                continue
            try:
                data = desktop.read_text()
            except OSError:
                continue
            if "Tor Browser" in data and shutil.which("gtk-launch"):
                subprocess.Popen(["gtk-launch", desktop.stem], start_new_session=True)
                raise SystemExit(0)
if shutil.which("notify-send"):
    subprocess.run(["notify-send", "Application unavailable", "Install " + ("Tor Browser" if app == "tor" else app) + " to use this launcher."])
