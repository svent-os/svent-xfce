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
    def default(parent, name, kind, value):
        node = parent.find("property[@name='" + name + "']")
        return node if node is not None else set_value(parent, name, kind, value)
    default(backdrop, "single-workspace-mode", "bool", "true")
    default(backdrop, "single-workspace-number", "int", "0")
    screen = set_value(backdrop, "screen0", "empty", None)
    state = config / "svent"
    choice = (state / "wallpaper.choice").read_text().strip() if (state / "wallpaper.choice").exists() else "currents-dark"
    override = (state / "wallpaper.override").read_text().strip() if (state / "wallpaper.override").exists() else ""
    def usable(image):
        return bool(image) and Path(image).is_file()
    saved = [node.get("value", "") for node in screen.findall(".//property[@name='last-image']")]
    for name, portrait in monitors:
        monitor = set_value(screen, "monitor" + name, "empty", None)
        local = [node.get("value", "") for node in monitor.findall(".//property[@name='last-image']")]
        candidates = local + saved + [override, str(wallpaper_dir / ("portrait" if portrait else "landscape") / ("svent-" + choice + ".png")), str(wallpaper_dir / "landscape/svent-currents-dark.png")]
        fallback = next((image for image in candidates if usable(image)), "")
        for number in range(5):
            workspace = set_value(monitor, "workspace" + str(number), "empty", None)
            image = workspace.find("property[@name='last-image']")
            style = workspace.find("property[@name='image-style']")
            disabled = style is not None and style.get("value") == "0"
            if not disabled and (image is None or not usable(image.get("value", ""))) and fallback:
                set_value(workspace, "last-image", "string", fallback)
            default(workspace, "image-style", "int", "5")
            default(workspace, "backdrop-cycle-enable", "bool", "false")
    path.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)
    if not path.exists() or path.read_bytes() != data:
        temp = path.with_suffix(".svent-tmp")
        temp.write_bytes(data)
        temp.replace(path)
    return root

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path)
    parser.add_argument("--offline", action="store_true")
    args = parser.parse_args()
    config = args.config or Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    monitors = [("0", False)]
    if os.environ.get("DISPLAY"):
        import re
        try:
            result = subprocess.run(["xrandr", "--current"], capture_output=True, text=True, timeout=1)
            connected = []
            for line in result.stdout.splitlines():
                match = re.match(r"(\S+) connected(?: primary)? (\d+)x(\d+)[+-]", line)
                if match:
                    connected.append((match[1], int(match[3]) > int(match[2])))
            if connected:
                monitors = connected
        except (OSError, subprocess.TimeoutExpired):
            pass
    root = prepare(config, monitors)
    if os.environ.get("DISPLAY") and not args.offline:
        import gi
        gi.require_version("Xfconf", "0")
        from gi.repository import Xfconf
        if Xfconf.init():
            channel = Xfconf.Channel.get("xfce4-desktop")
            def apply(parent, prefix=""):
                for node in parent.findall("property"):
                    key = prefix + "/" + node.attrib["name"]
                    kind = node.get("type")
                    value = node.get("value")
                    if kind in ("string", "bool", "int", "uint"):
                        desired = value if kind == "string" else value == "true" if kind == "bool" else int(value)
                        reader = getattr(channel, "get_" + kind)
                        writer = getattr(channel, "set_" + kind)
                        if not channel.has_property(key) or reader(key, desired) != desired:
                            writer(key, desired)
                    apply(node, key)
            apply(root)
            Xfconf.shutdown()

if __name__ == "__main__":
    main()
