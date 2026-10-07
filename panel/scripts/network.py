#!/usr/bin/env python3
import ipaddress
import json
import os
import subprocess
from pathlib import Path

PRIORITY = {"vpn": 0, "ethernet": 1, "wifi": 2, "cellular": 3, "bridge": 3, "virtual": 3, "tunnel": 3, "other": 3}

def read_ip(*args):
    try:
        return json.loads(subprocess.check_output(["ip", "-j", *args], stderr=subprocess.DEVNULL))
    except (OSError, subprocess.CalledProcessError, ValueError):
        return []

def classify(device):
    name = device.get("ifname", "").lower()
    kind = device.get("linkinfo", {}).get("info_kind", "").lower()
    if kind in {"wireguard", "tun", "tap", "vti", "vti6", "xfrm"} or name.startswith(("tun", "tap", "wg", "vpn", "tailscale", "zt", "utun")):
        return "vpn"
    if device.get("wireless") or Path("/sys/class/net", name, "wireless").exists() or name.startswith(("wl", "wlan")):
        return "wifi"
    if name.startswith(("wwan", "ppp", "rmnet", "usbmodem")) or kind == "ppp":
        return "cellular"
    if kind == "bridge" or name.startswith(("br-", "docker", "virbr")):
        return "bridge"
    if kind in {"veth", "dummy", "vxlan", "geneve", "vcan"} or name.startswith(("veth", "dummy")):
        return "virtual"
    if kind in {"gre", "gretap", "ip6gre", "ip6gretap", "ipip", "sit", "ip6tnl", "l2tp", "erspan"}:
        return "tunnel"
    if kind in {"bond", "team", "vlan", "macvlan", "ipvlan"} or device.get("link_type") == "ether" or name.startswith(("en", "eth")):
        return "ethernet"
    return "other"

def select_network(devices, routes4, routes6, preferred=""):
    candidates = []
    for device in devices:
        name = device.get("ifname", "")
        if preferred and name != preferred:
            continue
        if device.get("operstate") in {"DOWN", "LOWERLAYERDOWN", "NOTPRESENT"}:
            continue
        if "flags" in device and "UP" not in device["flags"]:
            continue
        category = classify(device)
        for item in device.get("addr_info", []):
            invalid = {"tentative", "deprecated", "dadfailed"}
            if any(flag in invalid for flag in item.get("flags", [])) or any(item.get(flag) for flag in invalid):
                continue
            try:
                address = ipaddress.ip_address(item["local"])
            except (ValueError, KeyError):
                continue
            if address.is_loopback or address.is_link_local or address.is_multicast or address.is_unspecified:
                continue
            if item.get("scope") not in {"global", "site"}:
                continue
            routes = routes4 if address.version == 4 else routes6
            matching = [route for route in routes if route.get("dev") == name]
            metric = min((int(route.get("metric", 0)) for route in matching), default=2147483647)
            rank = (PRIORITY[category], not bool(matching), address.version != 4, metric, bool(item.get("secondary")), name, str(address))
            candidates.append((rank, {"ip": str(address), "type": category, "interface": name}))
    return min(candidates, key=lambda item: item[0])[1] if candidates else None

