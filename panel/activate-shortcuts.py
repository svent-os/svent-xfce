#!/usr/bin/env python3
import argparse
import os
import hashlib
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

PROFILE = "0.5.8"
CHANNEL = "xfce4-keyboard-shortcuts"

def query(*args, check=True):
    return subprocess.run(["xfconf-query", "-c", CHANNEL, *args], check=check, capture_output=True, text=True, timeout=5)

def set_property(key, kind, value):
    channel = Xfconf.Channel.get(CHANNEL)
    success = channel.set_bool(key, value.lower() == "true") if kind == "bool" else channel.set_string(key, value)
    if not success:
        raise RuntimeError("Cannot set shortcut: " + key)

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
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "svent-xfce"
    marker = state / "shortcuts-applied"
    data = source.read_bytes()
    signature = hashlib.sha256(PROFILE.encode() + data).hexdigest()
    if not options.force and marker.is_file() and marker.read_text(encoding="utf-8").strip() == signature:
        return
    wanted = bindings(ET.fromstring(data))
    root_key = "/svent/shortcuts-profile"
    snapshot = query("-l", "-v").stdout
    existing = {}
    for line in snapshot.splitlines():
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0].startswith("/"):
            existing[parts[0]] = parts[1].strip()
    matches = all(existing.get(key, "").lower() == value.lower() if kind == "bool" else existing.get(key) == value for key, kind, value in wanted)
    changed = existing.get(root_key) != PROFILE or not matches or "/commands/custom/Super_L" in existing
    if changed:
        global Xfconf
        import gi
        gi.require_version("Xfconf", "0")
        from gi.repository import Xfconf
        if not Xfconf.init():
            raise RuntimeError("Cannot initialize keyboard shortcut settings")
        state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "svent-xfce"
        state.mkdir(parents=True, exist_ok=True)
        backup = state / ("shortcuts-before-" + PROFILE + ".txt")
        if not backup.exists():
            backup.write_text(snapshot, encoding="utf-8")
        for provider in ("commands", "xfwm4"):
            Xfconf.Channel.get(CHANNEL).reset_property(f"/{provider}/custom", True)
        for key, kind, value in wanted:
            set_property(key, kind, value)
        set_property(root_key, "string", PROFILE)
        Xfconf.shutdown()
    daemon = subprocess.run(["pgrep", "-u", str(os.getuid()), "-x", "xfsettingsd"], capture_output=True)
    if daemon.returncode == 1 or changed or options.force:
        subprocess.Popen(["xfsettingsd", "--replace"], stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    state.mkdir(parents=True, exist_ok=True)
    temporary = marker.with_suffix(".tmp")
    temporary.write_text(signature + "\n", encoding="utf-8")
    temporary.replace(marker)
    if changed:
        print("SventOS shortcuts activated: " + PROFILE)

if __name__ == "__main__":
    main()
