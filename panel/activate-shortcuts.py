#!/usr/bin/env python3
import os
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

PROFILE = "0.5.3"
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
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    source = Path("/etc/skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-keyboard-shortcuts.xml")
    wanted = bindings(ET.parse(source).getroot())
    root_key = "/svent/shortcuts-profile"
    current = query("-p", root_key, check=False)
    marker = current.returncode == 0 and current.stdout.strip() == PROFILE
    sentinel = query("-p", "/xfwm4/custom/<Super>Left", check=False)
    old_super = query("-p", "/commands/custom/Super_L", check=False)
    if not (marker and sentinel.stdout.strip() == "tile_left_key" and old_super.returncode != 0):
        state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "svent-xfce"
        state.mkdir(parents=True, exist_ok=True)
        backup = state / ("shortcuts-before-" + PROFILE + ".txt")
        if not backup.exists():
            backup.write_text(query("-l", "-v").stdout, encoding="utf-8")
        for provider in ("commands", "xfwm4"):
            query("-p", f"/{provider}/custom", "-r", "-R", check=False)
        for key, kind, value in wanted:
            set_property(key, kind, value)
        set_property(root_key, "string", PROFILE)
    daemon = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "xfsettingsd"], capture_output=True)
    if daemon.returncode == 1:
        subprocess.run(["xfsettingsd"], check=True, timeout=5)

if __name__ == "__main__":
    main()
