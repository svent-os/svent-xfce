#!/usr/bin/env python3
import html
import os
import shutil
import shlex
import subprocess
import sys
from pathlib import Path
from network import read_ip, select_network

addresses = read_ip("addr", "show")
links = {item.get("ifname"): item for item in read_ip("-d", "link", "show")}
devices = [dict(links.get(item.get("ifname"), {}), **item) for item in addresses]
selected = select_network(devices, read_ip("-4", "route", "show", "default"), read_ip("-6", "route", "show", "default"), os.environ.get("POLYBAR_INTERFACE", ""))
value = selected["ip"] if selected else "No IP"
if "--copy" in sys.argv:
    if not selected:
        raise SystemExit(0)
    if shutil.which("xclip"):
        subprocess.run(["xclip", "-selection", "clipboard"], input=value.encode(), check=True)
    elif shutil.which("xsel"):
        subprocess.run(["xsel", "--clipboard", "--input"], input=value.encode(), check=True)
else:
    command = "python3 " + shlex.quote(str(Path(__file__).resolve())) + " --copy"
    category = selected["type"] if selected else "other"
    tooltip = (category.title() + " on " + selected["interface"] + ". Click to copy IP address") if selected else "No usable IP address"
    print("<txt>" + html.escape(value) + "</txt><txtclick>" + html.escape(command) + "</txtclick><tool>" + html.escape(tooltip) + "</tool>")
