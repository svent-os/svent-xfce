#!/usr/bin/env python3
import argparse
import os
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

WALLPAPERS = Path("/usr/share/backgrounds/svent")

def set_value(parent, name, kind, value):
    node = parent.find("property[@name='" + name + "']")
    if node is None:
        node = ET.SubElement(parent, "property", name=name)
    node.set("type", kind)
    if value is not None:
        node.set("value", str(value))
    return node

def prepare(config, monitors, wallpaper_dir=WALLPAPERS):
    path = config / "xfce4/xfconf/xfce-perchannel-xml/xfce4-desktop.xml"
    if path.exists():
        tree = ET.parse(path)
    else:
        tree = ET.ElementTree(ET.Element("channel", name="xfce4-desktop", version="1.0"))
    root = tree.getroot()
    icons = set_value(root, "desktop-icons", "empty", None)
    set_value(icons, "style", "int", "2")
    set_value(icons, "icon-size", "uint", "40")
    set_value(icons, "single-click", "bool", "false")
    set_value(icons, "single-click-underline-hover", "bool", "false")
    set_value(icons, "use-custom-label-background-color", "bool", "false")
    files = set_value(icons, "file-icons", "empty", None)
    for name in ("show-home", "show-filesystem", "show-trash", "show-removable"):
        set_value(files, name, "bool", "true")
    backdrop = set_value(root, "backdrop", "empty", None)
    set_value(backdrop, "single-workspace-mode", "bool", "true")
    set_value(backdrop, "single-workspace-number", "int", "0")
    screen = set_value(backdrop, "screen0", "empty", None)
    state = config / "svent"
    choice = (state / "wallpaper.choice").read_text().strip() if (state / "wallpaper.choice").exists() else "orca-dark"
    override = (state / "wallpaper.override").read_text().strip() if (state / "wallpaper.override").exists() else ""
    saved = [node.get("value", "") for node in screen.findall(".//property[@name='last-image']")]
    def usable(image):
        return bool(image) and Path(image).is_file() and not image.startswith(("/usr/share/backgrounds/xfce/", "/usr/share/xfce4/backdrops/"))
    for name, portrait in monitors:
        monitor = set_value(screen, "monitor" + name, "empty", None)
        workspace = set_value(monitor, "workspace0", "empty", None)
        old = workspace.find("property[@name='last-image']")
        current = old.get("value", "") if old is not None else ""
        if not usable(current):
            candidates = [override] + saved + [str(wallpaper_dir / ("portrait" if portrait else "landscape") / ("svent-" + choice + ".png")), str(wallpaper_dir / "landscape/svent-orca-dark.png")]
            current = next((image for image in candidates if usable(image)), "")
        if current:
            set_value(workspace, "last-image", "string", current)
        set_value(workspace, "image-style", "int", "5")
        set_value(workspace, "backdrop-cycle-enable", "bool", "false")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    temp = path.with_suffix(".svent-tmp")
    tree.write(temp, encoding="utf-8", xml_declaration=True)
    temp.replace(path)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    config = args.config or Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    monitors = [("0", False)]
    if os.environ.get("DISPLAY"):
        import re
        try:
            result = subprocess.run(["xrandr", "--query"], capture_output=True, text=True, timeout=3)
            connected = []
            for line in result.stdout.splitlines():
                match = re.match(r"(\S+) connected(?: primary)? (\d+)x(\d+)[+-]", line)
                if match:
                    connected.append((match[1], int(match[3]) > int(match[2])))
            if connected:
                monitors = connected
        except (OSError, subprocess.TimeoutExpired):
            pass
    prepare(config, monitors)

if __name__ == "__main__":
    main()
