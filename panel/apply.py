#!/usr/bin/env python3
import argparse
import datetime
import json
import os
import re
import shutil
import shlex
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET

HOME = Path.home()
CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", str(HOME / ".config")))
STATE = Path(os.environ.get("XDG_STATE_HOME", str(HOME / ".local/state"))) / "xfce-dark-panel"
SOURCE = Path(__file__).resolve().parent

def query(*args, check=True):
    return subprocess.run(["xfconf-query", "-c", "xfce4-panel", *args], check=check, capture_output=True, text=True)

def reset(path):
    query("-p", path, "-r", "-R", check=False)

def value_text(value):
    return str(value).lower() if isinstance(value, bool) else str(value)

def set_property(path, kind, value):
    exists = query("-p", path, check=False).returncode == 0
    command = ["-p", path]
    if not exists:
        command += ["-n"]
    values = value if isinstance(value, list) else [value]
    if isinstance(value, list):
        command += ["-a"]
    for item in values:
        command += ["-t", kind, "-s", value_text(item)]
    query(*command)

def installed_plugins():
    result = set()
    for folder in (Path("/usr/share/xfce4/panel/plugins"), Path("/usr/local/share/xfce4/panel/plugins")):
        for path in folder.glob("*.desktop"):
            result.add(path.stem)
            try:
                for line in path.read_text().splitlines():
                    if line.startswith("X-XFCE-Module="):
                        result.add(line.split("=", 1)[1].strip())
            except OSError:
                pass
    return result

def start_panel():
    log = STATE / "panel.log"
    STATE.mkdir(parents=True, exist_ok=True)
    with log.open("a") as stream:
        subprocess.Popen(["xfce4-panel"], stdout=stream, stderr=stream, start_new_session=True)

def desktop_directory():
    if shutil.which("xdg-user-dir"):
        result = subprocess.run(["xdg-user-dir", "DESKTOP"], capture_output=True, text=True)
        path = Path(result.stdout.strip())
        if result.returncode == 0 and result.stdout.strip() and path.is_absolute():
            return path
    return HOME / "Desktop"

def wallpaper_settings():
    result = subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-l"], capture_output=True, text=True)
    bases = set()
    for key in result.stdout.splitlines():
        match = re.match(r"(/backdrop/screen[^/]+/monitor[^/]+)/workspace[^/]+/", key)
        if match:
            bases.add(match.group(1))
    if not bases and shutil.which("xrandr"):
        outputs = subprocess.run(["xrandr", "--query"], capture_output=True, text=True)
        for line in outputs.stdout.splitlines():
            match = re.match(r"(\S+) connected", line)
            if match:
                bases.add("/backdrop/screen0/monitor" + match.group(1))
    if not bases:
        raise RuntimeError("No desktop monitor found. Start xfdesktop before installing this profile.")
    settings = []
    for base in sorted(bases):
        for number in range(7):
            prefix = base + "/workspace" + str(number)
            settings.extend([(prefix + "/last-image", "string"), (prefix + "/image-style", "int"), (prefix + "/backdrop-cycle-enable", "bool")])
    return settings

def snapshot():
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + str(os.getpid())
    backup = STATE / "backups" / stamp
    backup.mkdir(parents=True)
    xml = CONFIG / "xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
    if not xml.is_file():
        raise RuntimeError("No saved panel configuration found. Start the Xfce panel before applying this profile.")
    ET.parse(xml)
    shutil.copy2(xml, backup / "panel.xml")
    panel = CONFIG / "xfce4/panel"
    if panel.is_dir():
        shutil.copytree(panel, backup / "panel-files")
    css = CONFIG / "gtk-3.0/gtk.css"
    metadata = {"css_existed": css.exists()}
    metadata["settings"] = []
    for channel, key in [("xfwm4", "/general/workspace_count"), ("xfwm4", "/general/workspace_names"), ("xfce4-keyboard-shortcuts", "/commands/custom/Super_L"), ("xfce4-keyboard-shortcuts", "/commands/custom/override")]:
        old = subprocess.run(["xfconf-query", "-c", channel, "-p", key], capture_output=True, text=True)
        lines = old.stdout.strip().splitlines()
        values = lines[2:] if len(lines) > 1 and "Array" in lines[0] else lines
        metadata["settings"].append({"channel":channel, "key":key, "exists":old.returncode == 0, "values":values})
    for key, kind in wallpaper_settings():
        old = subprocess.run(["xfconf-query", "-c", "xfce4-desktop", "-p", key], capture_output=True, text=True)
        metadata["settings"].append({"channel": "xfce4-desktop", "key": key, "kind": kind, "exists": old.returncode == 0, "values": [old.stdout.strip()]})
    metadata["desktop_assets"] = []
    for asset in (SOURCE / "assets").glob("*.png"):
        destination = desktop_directory() / asset.name
        record = {"path": str(destination), "name": asset.name, "exists": destination.is_file()}
        if record["exists"]:
            (backup / "desktop-assets").mkdir(exist_ok=True)
            shutil.copy2(destination, backup / "desktop-assets" / asset.name)
        metadata["desktop_assets"].append(record)
    if css.exists():
        shutil.copy2(css, backup / "gtk.css")
    (backup / "metadata.json").write_text(json.dumps(metadata))
    (STATE / "latest-backup").write_text(str(backup))
    return backup

def restore_xml(path):
    root = ET.parse(path).getroot()
    def visit(node, prefix=""):
        for prop in node.findall("property"):
            key = prefix + "/" + prop.attrib["name"]
            kind = prop.attrib.get("type", "empty")
            if kind == "array":
                items = prop.findall("value")
                if items:
                    types = {item.attrib["type"] for item in items}
                    if len(types) != 1:
                        raise RuntimeError("Mixed array types are not supported by this restore tool")
                    set_property(key, items[0].attrib["type"], [item.attrib["value"] for item in items])
            elif kind != "empty":
                set_property(key, kind, prop.attrib.get("value", ""))
            visit(prop, key)
    reset("/panels")
    reset("/plugins")
    visit(root)

def set_other(channel, key, kind, value):
    exists = subprocess.run(["xfconf-query", "-c", channel, "-p", key], capture_output=True).returncode == 0
    command = ["xfconf-query", "-c", channel, "-p", key]
    if not exists:
        command += ["-n"]
    values = value if isinstance(value, list) else [value]
    if isinstance(value, list):
        command += ["-a"]
    for item in values:
        command += ["-t", kind, "-s", value_text(item)]
    subprocess.run(command, check=True, capture_output=True)

def restore(backup):
    restore_xml(backup / "panel.xml")
    for item in json.loads((backup / "metadata.json").read_text()).get("settings", []):
        subprocess.run(["xfconf-query", "-c", item["channel"], "-p", item["key"], "-r"], capture_output=True)
        if item["exists"]:
            if item["key"].endswith("workspace_names"):
                set_other(item["channel"], item["key"], "string", item["values"])
            else:
                kind = "int" if item["key"].endswith("workspace_count") else "bool" if item["key"].endswith("override") else "string"
                set_other(item["channel"], item["key"], item.get("kind", kind), item["values"][0])
    for item in json.loads((backup / "metadata.json").read_text()).get("desktop_assets", []):
        if item["exists"]:
            shutil.copy2(backup / "desktop-assets" / item["name"], item["path"])
    if shutil.which("xfdesktop"):
        subprocess.run(["xfdesktop", "--reload"], check=False, capture_output=True)
    if (backup / "panel-files").is_dir():
        shutil.copytree(backup / "panel-files", CONFIG / "xfce4/panel", dirs_exist_ok=True)
    css = CONFIG / "gtk-3.0/gtk.css"
    if json.loads((backup / "metadata.json").read_text())["css_existed"]:
        css.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(backup / "gtk.css", css)
    elif css.exists():
        content = re.sub(r"/\* BEGIN Z1ROV DARK PANEL \*/.*?/\* END Z1ROV DARK PANEL \*/\n?", "", css.read_text(), flags=re.S)
        css.write_text(content, encoding="utf-8")

def apply(profile):
    available = installed_plugins()
    plugins = []
    for item in profile["plugins"]:
        item = dict(item)
        if item["name"] == "menu":
            item["name"] = "whiskermenu" if "whiskermenu" in available else "applicationsmenu"
        if item.get("optional") and item["name"] not in available:
            print("Optional plugin skipped:", item["name"])
            continue
        if available and item["name"] not in available:
            raise RuntimeError("Missing panel plugin: " + item["name"])
        plugins.append(item)
    reset("/panels")
    reset("/plugins")
    set_property("/configver", "int", 2)
    set_property("/panels", "int", [1])
    for key, (kind, value) in profile["panel"].items():
        set_property("/panels/panel-1/" + key, kind, value)
    set_property("/panels/panel-1/plugin-ids", "int", [item["id"] for item in plugins])
    for item in plugins:
        prefix = "/plugins/plugin-" + str(item["id"])
        set_property(prefix, "string", item["name"])
        for key, (kind, value) in item["settings"].items():
            set_property(prefix + "/" + key, kind, value)
    scripts = CONFIG / "xfce4/z1rov-panel"
    scripts.mkdir(parents=True, exist_ok=True)
    for script in (SOURCE / "scripts").glob("*.py"):
        shutil.copy2(script, scripts / script.name)
    ip_command = "python3 " + shlex.quote(str(scripts / "ip.py"))
    shutil.copytree(SOURCE / "icons", scripts / "icons", dirs_exist_ok=True)
    set_property("/plugins/plugin-915/command", "string", ip_command)
    legacy = CONFIG / "xfce4/panel/genmon-915.rc"
    legacy.parent.mkdir(parents=True, exist_ok=True)
    legacy.write_text("Command=" + ip_command + "\nUseLabel=0\nText=\nUpdatePeriod=15000\nFont=Sans 10\n", encoding="utf-8")
    artwork_logo = Path("/usr/share/svent/logo/logo.png")
    if artwork_logo.exists():
        shutil.copy2(artwork_logo, scripts / "logo.png")
        logo = str(scripts / "logo.png")
    else:
        shutil.copy2(SOURCE / "assets/logo-white.png", scripts / "logo-white.png")
        logo = str(scripts / "logo-white.png")
    set_property("/plugins/plugin-901/button-icon", "string", logo)
    set_property("/plugins/plugin-901/show-button-title", "bool", False)
    set_property("/plugins/plugin-901/show-button-icon", "bool", True)
    set_property("/plugins/plugin-901/button-title", "string", "Svent")
    (CONFIG / "xfce4/panel/whiskermenu-901.rc").write_text(
        "button-icon=" + logo + "\nbutton-title=Svent\nshow-button-title=false\nshow-button-icon=true\nbutton-single-row=true\n", encoding="utf-8")
    wallpaper = "/usr/share/backgrounds/svent/landscape/svent-orca-dark.png"
    for key, kind in wallpaper_settings():
        value = wallpaper if key.endswith("last-image") else 5 if key.endswith("image-style") else False
        set_other("xfce4-desktop", key, kind, value)
    subprocess.run(["xfdesktop", "--reload"], check=False, capture_output=True)
    menu = "xfce4-popup-whiskermenu" if "whiskermenu" in available else "xfce4-popup-applicationsmenu"
    set_other("xfwm4", "/general/workspace_count", "int", 7)
    set_other("xfwm4", "/general/workspace_names", "string", [str(i) for i in range(1, 8)])
    set_other("xfce4-keyboard-shortcuts", "/commands/custom/override", "bool", True)
    set_other("xfce4-keyboard-shortcuts", "/commands/custom/Super_L", "string", menu)
    def firefox_icon():
        for filename in ("firefox-esr.desktop", "firefox.desktop", "org.mozilla.firefox.desktop"):
            for folder in (Path("/usr/share/applications"), HOME / ".local/share/applications"):
                desktop = folder / filename
                if desktop.is_file():
                    for line in desktop.read_text().splitlines():
                        if line.startswith("Icon="):
                            return line.split("=", 1)[1].strip()
        return str(scripts / "icons/firefox.svg")
    for ident, app, name, icon in [(902, "firefox", "Firefox ESR", firefox_icon()), (903, "tor", "Tor Browser", str(scripts / "icons/tor.svg")), (904, "terminal", "Terminal", "utilities-terminal")]:
        folder = CONFIG / ("xfce4/panel/launcher-" + str(ident))
        folder.mkdir(parents=True, exist_ok=True)
        command = "python3 " + '"' + str(scripts / "launch-app.py").replace('"', '\\"') + '" ' + app
        (folder / (app + ".desktop")).write_text("[Desktop Entry]\nType=Application\nName=" + name + "\nIcon=" + icon + "\nExec=" + command + "\nTerminal=false\n", encoding="utf-8")
    css = CONFIG / "gtk-3.0/gtk.css"
    css.parent.mkdir(parents=True, exist_ok=True)
    original = css.read_text() if css.exists() else ""
    original = re.sub(r"/\* BEGIN Z1ROV DARK PANEL \*/.*?/\* END Z1ROV DARK PANEL \*/\n?", "", original, flags=re.S)
    css.write_text(original.rstrip()+"\n\n"+(SOURCE / "panel.css").read_text(), encoding="utf-8")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run this installer as your desktop user, without sudo")
    for command in ("xfce4-panel", "xfconf-query", "exo-open", "ip", "xfdesktop"):
        if not shutil.which(command):
            parser.error("Missing dependency: " + command)
    if not args.restore:
        if "genmon" not in installed_plugins():
            parser.error("Install xfce4-genmon-plugin before applying this profile")
        if not (shutil.which("xclip") or shutil.which("xsel")):
            parser.error("Install xclip for IP clipboard support")
    if not os.environ.get("DISPLAY"):
        parser.error("Run from a terminal inside your Xfce X11 desktop")
    if query("-l", check=False).returncode:
        parser.error("The Xfce settings service is unavailable")
    if args.restore:
        backup = Path((STATE / "latest-backup").read_text().strip())
        subprocess.run(["xfce4-panel", "--quit"], check=False)
        try:
            restore(backup)
        finally:
            start_panel()
        print("Previous panel restored")
    else:
        profile = json.loads((SOURCE / "profile.json").read_text())
        subprocess.run(["xfce4-panel", "--quit"], check=False)
        backup = None
        try:
            backup = snapshot()
            apply(profile)
        except Exception:
            if backup:
                restore(backup)
            raise
        finally:
            start_panel()
        print("Dark panel installed. Backup:", backup)
