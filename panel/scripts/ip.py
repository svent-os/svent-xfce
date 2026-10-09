#!/usr/bin/env python3
import html
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
import xml.etree.ElementTree as ET
from network import read_ip, select_network

SVG = "http://www.w3.org/2000/svg"

def badge_svg(value, category):
    ET.register_namespace("", SVG)
    width = 30 + max(5, len(value)) * 8
    root = ET.Element("{" + SVG + "}svg", width=str(width), height="24", viewBox=f"0 0 {width} 24")
    path = Path(__file__).resolve().parent.parent / "icons" / (category + ".svg")
    if not path.is_file():
        path = path.with_name("other.svg")
    icon = ET.parse(path).getroot()
    icon.set("x", "1")
    icon.set("y", "2")
    icon.set("width", "20")
    icon.set("height", "20")
    root.append(icon)
    text = ET.SubElement(root, "{" + SVG + "}text", x="28", y="17", fill="#e6e7e8")
    text.set("font-family", "JetBrains Mono, monospace")
    text.set("font-size", "13")
    text.text = value
    return ET.tostring(root, encoding="unicode")

def main():
    addresses = read_ip("addr", "show")
    links = {item.get("ifname"): item for item in read_ip("-d", "link", "show")}
    devices = [dict(links.get(item.get("ifname"), {}), **item) for item in addresses]
    selected = select_network(devices, read_ip("-4", "route", "show", "default"), read_ip("-6", "route", "show", "default"), os.environ.get("SVENT_INTERFACE", os.environ.get("POLYBAR_INTERFACE", "")))
    value = selected["ip"] if selected else "No IP"
    if "--copy" in sys.argv:
        if not selected:
            return
        if shutil.which("xclip"):
            subprocess.run(["xclip", "-selection", "clipboard"], input=value.encode(), check=True, timeout=3)
        elif shutil.which("xsel"):
            subprocess.run(["xsel", "--clipboard", "--input"], input=value.encode(), check=True, timeout=3)
        return
    category = selected["type"] if selected else "other"
    tooltip = f"{category.title()} on {selected['interface']}. Click to copy {value}" if selected else "No usable IP address"
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))) / "svent-xfce"
    cache.mkdir(parents=True, exist_ok=True)
    badge = cache / "network.svg"
    content = badge_svg(value, category)
    if not badge.exists() or badge.read_text() != content:
        temp = badge.with_name(f"network-{os.getpid()}.tmp")
        temp.write_text(content, encoding="utf-8")
        temp.replace(badge)
    command = shlex.join(["python3", str(Path(__file__).resolve()), "--copy"])
    click = "<click>" + command + "</click>" if selected else ""
    print("<img>" + str(badge) + "</img>" + click + "<tool>" + html.escape(tooltip) + "</tool>")

if __name__ == "__main__":
    main()
