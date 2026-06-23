"""Full connection path — interfaces, routes, ISP, VPN (any provider)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import re
from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.home_ip import resolve_home_ip
from nordctl.ip_info import build_ip_info, primary_lan_iface, public_ipv4_via_iface
from nordctl.vpn_detect import analyze_vpn, default_route
from nordctl.zones import zone_status


def _parse_mac(text: str) -> str | None:
    m = re.search(r"link/ether ([0-9a-f:]{11,17})", text, re.I)
    return m.group(1).lower() if m else None


def _list_interfaces() -> list[dict[str, Any]]:
    """All network interfaces with link + IPv4/IPv6 addresses."""
    link_r = net.run_cmd(["ip", "-j", "link", "show"], timeout=5)
    if link_r["ok"] and link_r["output"].strip().startswith("["):
        try:
            links = json.loads(link_r["output"])
        except json.JSONDecodeError:
            links = []
    else:
        links = []
        lr = net.run_cmd(["ip", "link", "show"], timeout=5)
        if lr["ok"]:
            cur = None
            for line in lr["output"].splitlines():
                m = re.match(r"^\d+:\s+(\S+?):", line)
                if m:
                    cur = m.group(1).rstrip("@")
                    links.append({"ifname": cur, "operstate": "UNKNOWN", "address": None})
                elif cur and "link/ether" in line:
                    links[-1]["address"] = _parse_mac(line)

    addr4: dict[str, list[str]] = {}
    addr6: dict[str, list[str]] = {}
    for fam, store in (("-4", addr4), ("-6", addr6)):
        ar = net.run_cmd(["ip", fam, "-o", "addr", "show"], timeout=5)
        if not ar["ok"]:
            continue
        for line in ar["output"].splitlines():
            parts = line.split()
            if len(parts) < 4:
                continue
            dev = parts[1]
            store.setdefault(dev, []).append(parts[3])

    out: list[dict[str, Any]] = []
    seen = set()
    for row in links:
        name = row.get("ifname") or row.get("name")
        if not name or name in seen:
            continue
        seen.add(name)
        mac = row.get("address")
        if isinstance(mac, str):
            mac = mac.lower()
        out.append({
            "name": name,
            "state": (row.get("operstate") or "unknown").lower(),
            "mac": mac,
            "ipv4": addr4.get(name, []),
            "ipv6": addr6.get(name, [])[:4],
        })
    out.sort(key=lambda x: (0 if x["state"] == "up" else 1, x["name"]))
    return out


def _wifi_details(cfg: dict[str, Any]) -> dict[str, Any]:
    dev = net.detect_wifi_device((cfg.get("wifi") or {}).get("device"))
    zs = zone_status(cfg)
    out: dict[str, Any] = {
        "ssid": zs.get("ssid"),
        "zone_trusted": bool(zs.get("is_trusted")),
        "device": dev,
    }
    if not dev:
        return out
    st = net.wifi_device_status(dev)
    out.update(st)
    wr = net.run_cmd(["nmcli", "-t", "-f", "GENERAL.CONNECTION,GENERAL.HWADDR,WIFI-SEC,IP4.ADDRESS", "dev", "show", dev], timeout=8)
    if wr["ok"]:
        for line in wr["output"].splitlines():
            if ":" not in line:
                continue
            k, v = line.split(":", 1)
            k, v = k.strip(), v.strip()
            if k == "GENERAL.HWADDR" and v:
                out["mac"] = v.lower()
            elif k == "WIFI-SEC" and v:
                out["security"] = v
            elif k == "IP4.ADDRESS" and v:
                out.setdefault("ipv4", []).append(v)
    br = net.run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID,BSSID,SIGNAL", "dev", "wifi"], timeout=8)
    if br["ok"]:
        for line in br["output"].splitlines():
            parts = line.split(":")
            if len(parts) >= 3 and parts[0] == "yes":
                out["bssid"] = parts[2] or None
                out["signal"] = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else None
                break
    if dev:
        out["dns"] = net.wifi_dns_servers(dev)
    return out


def _dns_global(device: str | None) -> dict[str, Any]:
    servers: list[str] = []
    if device:
        servers = net.wifi_dns_servers(device)
    rr = net.run_cmd(["resolvectl", "status"], timeout=5)
    return {
        "servers": servers,
        "resolvectl": (rr.get("output") or "")[:4000],
    }


def _route_table(limit: int = 40) -> list[str]:
    r = net.run_cmd(["ip", "route", "show"], timeout=5)
    if not r["ok"]:
        return []
    lines = r["output"].splitlines()
    return lines[:limit]


def build_connection_details(
    cfg: dict[str, Any],
    status: dict[str, Any] | None = None,
    *,
    settings: dict[str, Any] | None = None,
    mesh_ip: str | None = None,
) -> dict[str, Any]:
    """Rich connection snapshot for the Connection details dashboard tab."""
    settings = settings or {}
    status = status or {}
    url = str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip")
    probe_timeout = min(4.0, float(cfg.get("public_ip_timeout") or 4))

    def _fetch_public() -> str | None:
        r = net.run_cmd(
            ["curl", "-s", "--max-time", str(max(1, int(probe_timeout))), url],
            timeout=probe_timeout + 1,
        )
        if r["ok"]:
            from nordctl.ip_info import _parse_ipv4

            for line in r["output"].splitlines():
                ip = _parse_ipv4(line)
                if ip:
                    return ip
        return None

    lan = primary_lan_iface()
    routed_ip = _fetch_public()
    home_probe = public_ipv4_via_iface(url, lan, timeout=probe_timeout) if lan else None

    vpn = analyze_vpn(status, routed_public_ip=routed_ip)
    vpn_active = bool(vpn.get("active"))
    exit_ip = vpn.get("exit_ip") or (routed_ip if vpn_active else None)

    home_ctx = resolve_home_ip(
        cfg,
        connected=vpn_active,
        probe_ip=home_probe,
        live_public_ip=routed_ip if not vpn_active else None,
        vpn_ip=exit_ip,
    )

    ip_info = build_ip_info(
        cfg,
        status,
        settings=settings,
        mesh_ip=mesh_ip,
        fast=False,
    )

    wifi = _wifi_details(cfg)
    dr = default_route()
    ifaces = _list_interfaces()
    dns = _dns_global(wifi.get("device"))

    hops: list[dict[str, Any]] = []

    # Device / LAN
    lan_row = next((i for i in ifaces if i["name"] == lan), None)
    hops.append({
        "role": "device",
        "label": "This PC (LAN)",
        "interface": lan,
        "mac": (lan_row or {}).get("mac") or wifi.get("mac"),
        "ipv4": (lan_row or {}).get("ipv4") or wifi.get("ipv4"),
        "detail": wifi.get("active_profile") or wifi.get("device"),
    })

    if wifi.get("ssid"):
        hops.append({
            "role": "wifi",
            "label": "Wi‑Fi network",
            "ssid": wifi.get("ssid"),
            "bssid": wifi.get("bssid"),
            "signal": wifi.get("signal"),
            "security": wifi.get("security"),
            "trusted_zone": wifi.get("zone_trusted"),
        })

    if dr.get("gateway"):
        hops.append({
            "role": "gateway",
            "label": "Default gateway (router)",
            "ipv4": dr.get("gateway"),
            "interface": dr.get("device"),
        })

    if home_ctx.get("show") and home_ctx.get("ip"):
        hops.append({
            "role": "isp",
            "label": "ISP public (Home)" if home_ctx.get("is_trusted_network") else "ISP public",
            "ipv4": home_ctx.get("ip"),
            "source": home_ctx.get("source"),
            "note": home_ctx.get("note"),
        })
    elif not vpn_active and routed_ip:
        hops.append({
            "role": "isp",
            "label": "Public IP (live)",
            "ipv4": routed_ip,
            "source": "live",
        })

    if vpn_active:
        nord_block: dict[str, Any] = {
            "provider": vpn.get("provider_label"),
            "provider_id": vpn.get("provider"),
            "interface": vpn.get("interface"),
            "local_ip": vpn.get("local_ip"),
            "exit_ip": exit_ip,
            "detection": vpn.get("detection_via"),
            "default_route_device": dr.get("device"),
            "tunnels": vpn.get("tunnels") or [],
        }
        if vpn.get("nord_connected"):
            nord_block["nord_status"] = {
                k: status.get(k)
                for k in (
                    "Status", "Server", "Hostname", "Country", "City", "IP",
                    "Current technology", "Current protocol", "Transfer",
                    "Uptime", "Connected",
                )
                if status.get(k)
            }
            nord_block["nord_settings"] = {
                k: settings.get(k)
                for k in (
                    "Firewall", "Kill Switch", "Meshnet", "DNS", "Threat Protection Lite",
                    "Technology", "Protocol", "Auto-connect", "LAN Discovery",
                )
                if settings.get(k)
            }
        hops.append({
            "role": "vpn",
            "label": str(vpn.get("provider_label") or "VPN"),
            "ipv4": exit_ip,
            "detail": vpn.get("interface"),
            "vpn": nord_block,
        })

    if ip_info.get("mesh_ip"):
        hops.append({
            "role": "mesh",
            "label": "Nord Meshnet",
            "ipv4": ip_info.get("mesh_ip"),
        })

    return {
        "ok": True,
        "generated_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "path": hops,
        "ip_info": ip_info,
        "home": home_ctx,
        "vpn": vpn,
        "wifi": wifi,
        "default_route": dr,
        "routed_public_ip": routed_ip,
        "lan_interface": lan,
        "interfaces": ifaces,
        "routes": _route_table(),
        "dns": dns,
        "notes": [
            n
            for n in (
                home_ctx.get("note"),
                ip_info.get("note"),
                ip_info.get("routed_ip_note"),
                (
                    "Default-route public IP differs from Home — normal when any VPN carries traffic."
                    if vpn_active and routed_ip and home_ctx.get("ip") and routed_ip != home_ctx.get("ip")
                    else None
                ),
            )
            if n
        ],
    }
