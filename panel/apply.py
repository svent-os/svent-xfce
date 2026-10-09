#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from generate import panel_xml

SOURCE = Path(__file__).resolve().parent

def run(*args, check=True):
    return subprocess.run(args, check=check, capture_output=True, text=True)

def apply_xml(root):
    def visit(parent, prefix=""):
        for node in parent.findall("property"):
            key = prefix + "/" + node.attrib["name"]
            kind = node.attrib["type"]
            if kind != "empty":
                command = ["xfconf-query", "-c", "xfce4-panel", "-p", key, "-n"]
                if kind == "array":
                    command += ["-a"]
                    for item in node.findall("value"):
                        command += ["-t", item.attrib["type"], "-s", item.attrib["value"]]
                else:
                    command += ["-t", kind, "-s", node.attrib["value"]]
                run(*command)
            visit(node, key)
    for key in ("/panels", "/plugins", "/configver"):
        run("xfconf-query", "-c", "xfce4-panel", "-p", key, "-r", "-R", check=False)
    visit(root)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("DISPLAY"):
        parser.error("Run inside the XFCE X11 session")
    for command in ("xfce4-panel", "xfconf-query"):
        if not shutil.which(command):
            parser.error("Missing dependency: " + command)
    config = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    state = Path(os.environ.get("XDG_STATE_HOME", str(Path.home() / ".local/state"))) / "svent-xfce-panel"
    xml = config / "xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
    backup = state / "previous-panel.xml"
    profile = json.loads((SOURCE / "profile.json").read_text())
    target = ET.parse(backup).getroot() if args.restore else ET.fromstring(panel_xml(profile))
    run("xfce4-panel", "--quit")
    try:
        if not args.restore:
            state.mkdir(parents=True, exist_ok=True)
            if not xml.is_file():
                raise RuntimeError("No saved panel configuration available")
            ET.parse(xml)
            shutil.copy2(xml, backup)
        try:
            apply_xml(target)
        except Exception:
            if not args.restore and backup.exists():
                apply_xml(ET.parse(backup).getroot())
            raise
    finally:
        subprocess.Popen(["xfce4-panel"], start_new_session=True,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    print("Panel restored" if args.restore else "Panel reloaded; wallpaper unchanged")

if __name__ == "__main__":
    main()
