#!/usr/bin/env python3
import argparse
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

PROFILE = "0.5.4"
CHANNEL = "xfce4-keyboard-shortcuts"

def query(*args, check=True):
    return subprocess.run(["xfconf-query", "-c", CHANNEL, *args], check=check, capture_output=True, text=True, timeout=5)

def set_property(key, kind, value):
    exists = query("-p", key, check=False).returncode == 0
    args = ["-p", key]
    if not exists:
        args.append("-n")
    args += ["-t", kind, "-s", value]
    query(*args)

def bindings(root):
    result = []
    for provider in ("commands", "xfwm4"):
        custom = root.find(f"property[@name='{provider}']/property[@name='custom']")
        if custom is None:
            raise ValueError("Missing shortcut provider: " + provider)
        for item in custom.findall("property"):
            if item.get("type") in ("string", "bool"):
                result.append((f"/{provider}/custom/" + item.attrib["name"], item.attrib["type"], item.attrib["value"]))
    return result

def main():
    if not os.environ.get("DISPLAY"):
        raise RuntimeError("An XFCE X11 session is required")
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    options = parser.parse_args()
    if options.diagnose:
        for command in (["xmodmap", "-pm"], ["pgrep", "-a", "xfwm4"], ["pgrep", "-a", "xfsettingsd"]):
            subprocess.run(command, check=False)
        print(query("-l", "-v").stdout)
        return
    source = Path("/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml")
    wanted = bindings(ET.parse(source).getroot())
    root_key = "/svent/shortcuts-profile"
    snapshot = query("-l", "-v").stdout
    existing = {}
    for line in snapshot.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].startswith("/"):
            existing[parts[0]] = parts[1].strip()
    matches = all(existing.get(key, "").lower() == value.lower() if kind == "bool" else existing.get(key) == value for key, kind, value in wanted)
    changed = options.force or existing.get(root_key) != PROFILE or not matches or "/commands/custom/Super_L" in existing
    if changed:
        state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "svent-xfce"
        state.mkdir(parents=True, exist_ok=True)
        backup = state / ("shortcuts-before-" + PROFILE + ".txt")
        if not backup.exists():
            backup.write_text(snapshot, encoding="utf-8")
        for provider in ("commands", "xfwm4"):
            query("-p", f"/{provider}/custom", "-r", "-R", check=False)
        for key, kind, value in wanted:
            set_property(key, kind, value)
        set_property(root_key, "string", PROFILE)
    daemon = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "xfsettingsd"], capture_output=True)
    if daemon.returncode == 1 or options.force:
        subprocess.run(["xfsettingsd", "--replace"], check=True, timeout=5)
    if changed:
        print("Svent shortcuts activated: " + PROFILE)

if __name__ == "__main__":
    main()
