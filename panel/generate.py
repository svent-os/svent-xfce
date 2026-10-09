#!/usr/bin/env python3
import json
from pathlib import Path
import xml.etree.ElementTree as ET

def property(parent, name, kind, value):
    node = ET.SubElement(parent, "property", name=name, type="array" if isinstance(value, list) else kind)
    def text(item):
        return str(item).lower() if isinstance(item, bool) else str(item)
    if isinstance(value, list):
        for item in value:
            ET.SubElement(node, "value", type=kind, value=text(item))
    else:
        node.set("value", text(value))
    return node

def panel_xml(profile):
    root = ET.Element("channel", name="xfce4-panel", version="1.0")
    property(root, "configver", "int", 2)
    panels = property(root, "panels", "int", [1])
    property(panels, "dark-mode", "bool", True)
    panel = ET.SubElement(panels, "property", name="panel-1", type="empty")
    for key, (kind, value) in profile["panel"].items():
        property(panel, key, kind, value)
    property(panel, "plugin-ids", "int", [item["id"] for item in profile["plugins"]])
    plugins = ET.SubElement(root, "property", name="plugins", type="empty")
    for item in profile["plugins"]:
        node = property(plugins, "plugin-" + str(item["id"]), "string", item["name"])
        for key, (kind, value) in item["settings"].items():
            property(node, key, kind, value)
    ET.indent(root)
    return ET.tostring(root, encoding="unicode", xml_declaration=True) + "\n"

if __name__ == "__main__":
    source = Path(__file__).resolve().parent
    target = source.parent / "skel/.config/xfce4/xfconf/xfce-perchannel-xml/xfce4-panel.xml"
    target.write_text(panel_xml(json.loads((source / "profile.json").read_text())), encoding="utf-8")
