"""Detect active VPN tunnels — NordVPN, WireGuard, OpenVPN, and generic TUN/TAP."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any

from nordctl import network_linux as net

# Physical-ish prefixes — default route via these usually means no VPN on path
_PHYS_PREFIXES = ("wl", "eth", "enp", "eno", "ens", "usb", "wwan")

_TUNNEL_PREFIXES = (
    ("nordlynx", "nord"),
    ("nordtun", "nord"),
    ("wg", "wireguard"),
    ("tun", "openvpn"),
    ("tap", "tap"),
    ("ppp", "ppp"),
)


def _iface_kind(name: str) -> str:
    low = name.lower()
    for prefix, kind in _TUNNEL_PREFIXES:
        if low == prefix or low.startswith(prefix):
            return kind
    if any(low.startswith(p) for p in _PHYS_PREFIXES):
        return "physical"
    return "other"


def default_route() -> dict[str, Any]:
    """Parse `ip route show default` — gateway and egress interface."""
    r = net.run_cmd(["ip", "route", "show", "default"], timeout=4)
    out = r.get("output") or ""
    gateway = None
    dev = None
    for line in out.splitlines():
        if "default" not in line:
            continue
        m_gw = re.search(r"\bvia (\d+\.\d+\.\d+\.\d+)\b", line)
        if m_gw:
            gateway = m_gw.group(1)
        m_dev = re.search(r"\bdev (\S+)\b", line)
        if m_dev:
            dev = m_dev.group(1)
        if gateway or dev:
            break
    return {"gateway": gateway, "device": dev, "raw": out.strip()}


def list_tunnel_interfaces() -> list[dict[str, Any]]:
    """UP tunnel-like interfaces with IPv4 addresses."""
    r = net.run_cmd(["ip", "-4", "-o", "addr", "show"], timeout=5)
    if not r["ok"]:
        return []
    tunnels: list[dict[str, Any]] = []
    for line in r["output"].splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        dev = parts[1]
        kind = _iface_kind(dev)
        if kind in ("physical", "other") and dev not in ("lo",):
            continue
        if kind == "other" and not dev.startswith(("tun", "tap", "wg", "nord", "ppp")):
            continue
        ip = parts[3].split("/")[0]
        link = net.run_cmd(["ip", "link", "show", dev], timeout=3)
        state = "UNKNOWN"
        mac = None
        if link["ok"]:
            m_state = re.search(r"state (\w+)", link["output"])
            if m_state:
                state = m_state.group(1)
            m_mac = re.search(r"link/ether ([0-9a-f:]+)", link["output"], re.I)
            if m_mac:
                mac = m_mac.group(1)
        if state.upper() != "UP":
            continue
        tunnels.append({
            "device": dev,
            "kind": kind,
            "ipv4": ip,
            "mac": mac,
            "state": state,
        })
    return tunnels


def analyze_vpn(
    nord_status: dict[str, Any] | None = None,
    *,
    routed_public_ip: str | None = None,
) -> dict[str, Any]:
    """Summarize VPN state for ip_info and connection details."""
    nord_status = nord_status or {}
    nord_connected = bool(nord_status.get("connected"))
    nord_ip = str(nord_status.get("IP") or "").strip() or None

    dr = default_route()
    dr_dev = dr.get("device")
    dr_kind = _iface_kind(str(dr_dev or ""))
    tunnels = list_tunnel_interfaces()

    provider = None
    active = nord_connected
    iface = None
    exit_ip = nord_ip if nord_connected else None
    local_ip = None
    via = "nord_cli"

    if nord_connected:
        iface = "nordlynx"
        for t in tunnels:
            if t["kind"] == "nord":
                iface = t["device"]
                local_ip = t.get("ipv4")
                break
        if not local_ip:
            from nordctl import nordvpn as nv

            local_ip = nv.tunnel_local_ip(str(iface or "nordlynx"))
        provider = "nordvpn"
    elif dr_dev and dr_kind not in ("physical", "other"):
        active = True
        iface = dr_dev
        via = "default_route"
        provider = dr_kind
        for t in tunnels:
            if t["device"] == dr_dev:
                local_ip = t.get("ipv4")
                break
        exit_ip = routed_public_ip
    elif tunnels:
        # VPN up but default route not through tunnel (split tunnel / policy routing)
        t0 = tunnels[0]
        active = True
        iface = t0["device"]
        provider = t0["kind"]
        local_ip = t0.get("ipv4")
        via = "tunnel_up"
        exit_ip = routed_public_ip

    return {
        "active": active,
        "provider": provider,
        "provider_label": {
            "nordvpn": "NordVPN",
            "nord": "NordVPN",
            "wireguard": "WireGuard",
            "openvpn": "OpenVPN / TUN",
            "tap": "TAP VPN",
            "ppp": "PPP VPN",
        }.get(str(provider or ""), provider or "VPN"),
        "interface": iface,
        "local_ip": local_ip,
        "exit_ip": exit_ip,
        "nord_connected": nord_connected,
        "default_route": dr,
        "tunnels": tunnels,
        "detection_via": via,
    }
