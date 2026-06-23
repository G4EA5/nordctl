"""Simple, friendly view of active network connections (Wireshark-lite)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import socket
from functools import lru_cache
from ipaddress import ip_address, ip_network
from typing import Any

from nordctl.nettools import VPN_IFACES, _run, _which

# Parsed manually — ss column spacing varies.

_PRIVATE_NETS = (
    ip_network("10.0.0.0/8"),
    ip_network("172.16.0.0/12"),
    ip_network("192.168.0.0/16"),
    ip_network("127.0.0.0/8"),
    ip_network("169.254.0.0/16"),
    ip_network("::1/128"),
    ip_network("fc00::/7"),
    ip_network("fe80::/10"),
)

_APP_EMOJI: dict[str, str] = {
    "firefox": "🦊",
    "chrome": "🌐",
    "chromium": "🌐",
    "brave": "🦁",
    "discord": "💬",
    "spotify": "🎵",
    "steam": "🎮",
    "nordvpn": "🛡️",
    "nordvpnd": "🛡️",
    "nordlynx": "🛡️",
    "curl": "📡",
    "wget": "📡",
    "python": "🐍",
    "code": "📝",
    "cursor": "📝",
    "ssh": "🔐",
    "systemd": "⚙️",
    "NetworkManager": "📶",
}


def _split_host_port(addr: str) -> tuple[str, str]:
    if addr.startswith("["):
        m = re.match(r"\[([^\]]+)\]:(\S+)", addr)
        if m:
            return m.group(1), m.group(2)
    if ":" in addr:
        host, _, port = addr.rpartition(":")
        return host, port
    return addr, ""


def _is_private(host: str) -> bool:
    if not host or host in ("*", "0.0.0.0", "::"):
        return True
    try:
        ip = ip_address(host.split("%")[0])
    except ValueError:
        return False
    return any(ip in net for net in _PRIVATE_NETS)


def _vpn_local_ips() -> set[str]:
    ips: set[str] = set()
    for iface in VPN_IFACES:
        show = _run(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=4)
        for line in (show.get("output") or "").splitlines():
            parts = line.split()
            if len(parts) >= 4:
                ips.add(parts[3].split("/")[0])
    return ips


@lru_cache(maxsize=256)
def _reverse_name(ip: str) -> str:
    if _is_private(ip):
        return ip
    try:
        name, _, _ = socket.gethostbyaddr(ip)
        if name and name != ip:
            short = name.rstrip(".").split(".")
            if len(short) >= 2:
                return ".".join(short[-2:])
            return name
    except (socket.herror, socket.gaierror, OSError):
        pass
    return ip


_NORD_HOST_HINTS = ("nordvpn", "nordsec", "datapacket", "nord", "meshnet", "nordcdn")


def _ui_listen_ports() -> set[str]:
    from nordctl.config import load_config
    from nordctl.ports import DEFAULT_UI_PORT

    cfg = load_config()
    port = int((cfg.get("server") or {}).get("port") or DEFAULT_UI_PORT)
    return {str(DEFAULT_UI_PORT), str(port)}


def _infer_process(proc: str, peer_host: str, peer_port: str, local_host: str) -> str:
    if proc:
        return proc
    host = (peer_host or "").lower()
    if any(h in host for h in _NORD_HOST_HINTS):
        return "nordvpnd"
    ui_ports = _ui_listen_ports()
    if peer_port in ui_ports and _is_private(peer_host):
        return "nordctl"
    if peer_port in ui_ports and _is_private(local_host):
        return "nordctl"
    return ""


def _friendly_app(proc: str, peer_host: str = "", peer_port: str = "", local_host: str = "") -> tuple[str, str]:
    proc = _infer_process(proc, peer_host, peer_port, local_host)
    base = (proc or "unknown").split("/")[-1].lower()
    for key, emoji in _APP_EMOJI.items():
        if key in base:
            label = key.capitalize() if key != "NetworkManager" else "WiFi"
            return label, emoji
    if proc == "nordctl":
        return "nordctl UI", "◈"
    if not proc:
        return "Unidentified", "📱"
    label = proc.replace('"', "").strip()
    if len(label) > 24:
        label = label[:22] + "…"
    return label.title() if label.islower() else label, "📱"


def _path_info(local_host: str, peer_host: str, vpn_ips: set[str], proc: str) -> dict[str, str]:
    proc_low = (proc or "").lower()
    if any(v in proc_low for v in ("nordvpn", "nordlynx", "nordtun")):
        return {
            "via": "vpn",
            "path_label": "Through VPN",
            "path_hint": "This connection uses Nord’s tunnel.",
            "icon": "🛡️",
        }
    if local_host in vpn_ips:
        return {
            "via": "vpn",
            "path_label": "Through VPN",
            "path_hint": "Traffic left via the VPN tunnel.",
            "icon": "🛡️",
        }
    if _is_private(peer_host):
        return {
            "via": "local",
            "path_label": "On your network",
            "path_hint": "Talking to a device on your home or local network.",
            "icon": "🏠",
        }
    if _is_private(local_host) and not _is_private(peer_host):
        return {
            "via": "direct",
            "path_label": "Direct to internet",
            "path_hint": "Not using the VPN tunnel — check VPN is connected if this surprises you.",
            "icon": "⚠️",
        }
    return {
        "via": "other",
        "path_label": "Other",
        "path_hint": "System or internal connection.",
        "icon": "•",
    }


_PROC_RE = re.compile(r'users:\(\("([^"]+)"(?:,pid=(\d+))?')
_ADDR_RE = re.compile(r"(\S+:\S+|\[.+?\]:\S+)")


def _parse_ss_line(line: str) -> dict[str, str] | None:
    parts = line.split()
    if len(parts) < 5:
        return None
    net, state = parts[0], parts[1]
    if state in ("UNCONN", "LISTEN"):
        return None
    if state not in ("ESTAB", "ESTABLISHED", "SYN-SENT", "SYN-RECV", "TIME-WAIT"):
        return None
    addrs = _ADDR_RE.findall(line)
    if len(addrs) < 2:
        return None
    proc_m = _PROC_RE.search(line)
    return {
        "net": net,
        "state": state,
        "local": addrs[0],
        "peer": addrs[1],
        "proc": proc_m.group(1) if proc_m else "",
        "pid": proc_m.group(2) if proc_m and proc_m.group(2) else "",
    }


def _parse_ss() -> list[dict[str, Any]]:
    if not _which("ss"):
        return []
    raw = _run(["ss", "-H", "-tunap"], timeout=10)
    if not raw.get("ok") or not raw.get("output"):
        raw = _run(["ss", "-tunap"], timeout=10)
    vpn_ips = _vpn_local_ips()
    rows: list[dict[str, Any]] = []
    for line in (raw.get("output") or "").splitlines():
        line = line.strip()
        if not line or line.startswith("State") or line.startswith("Netid"):
            continue
        parsed = _parse_ss_line(line)
        if not parsed:
            continue
        local_host, peer_port_dummy = _split_host_port(parsed["local"])
        peer_host, peer_port = _split_host_port(parsed["peer"])
        if peer_host in ("0.0.0.0", "*", "[::]", "::"):
            continue
        proc = parsed["proc"]
        pid = parsed["pid"]
        app_label, emoji = _friendly_app(proc, peer_host, peer_port, local_host)
        effective_proc = proc or _infer_process(proc, peer_host, peer_port, local_host)
        path = _path_info(local_host, peer_host, vpn_ips, effective_proc)
        if not proc and app_label == "Unidentified":
            path = dict(path)
            path["path_hint"] = (
                "Linux did not report which app owns this socket (common without root). "
                "If the host is a Nord server (e.g. datapacket.com), it is usually NordVPN or your browser."
            )
        peer_name = _reverse_name(peer_host) if not _is_private(peer_host) else peer_host
        port_note = f" port {peer_port}" if peer_port and peer_port not in ("0", "*") else ""
        simple = f"{app_label} → {peer_name}{port_note} · {path['path_label']}"
        rows.append({
            "app": app_label,
            "emoji": emoji,
            "process": proc or "Unknown",
            "pid": pid,
            "protocol": parsed["net"].lower(),
            "state": parsed["state"],
            "local": parsed["local"],
            "peer": parsed["peer"],
            "peer_host": peer_host,
            "peer_name": peer_name,
            "peer_port": peer_port,
            "via": path["via"],
            "path_label": path["path_label"],
            "path_hint": path["path_hint"],
            "path_icon": path["icon"],
            "simple_line": simple,
            "is_internet": not _is_private(peer_host),
        })
    return rows


def _group_by_app(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = row["app"]
        g = groups.setdefault(key, {
            "app": row["app"],
            "emoji": row["emoji"],
            "count": 0,
            "via_vpn": 0,
            "via_direct": 0,
            "via_local": 0,
            "samples": [],
        })
        g["count"] += 1
        via = row["via"]
        if via == "vpn":
            g["via_vpn"] += 1
        elif via == "direct":
            g["via_direct"] += 1
        elif via == "local":
            g["via_local"] += 1
        if len(g["samples"]) < 4:
            g["samples"].append(row["simple_line"])
    out = sorted(groups.values(), key=lambda x: (-x["count"], x["app"]))
    return out


def run_traffic_watch(filter_name: str = "all", *, limit: int = 100) -> dict[str, Any]:
    """Return kid-friendly connection list and summary."""
    filt = (filter_name or "all").strip().lower()
    rows = _parse_ss()
    if not rows and not _which("ss"):
        return {
            "ok": False,
            "error": "Install iproute2 (ss command) to see connections",
            "connections": [],
            "groups": [],
            "summary": {},
        }

    filtered = rows
    if filt == "internet":
        filtered = [r for r in rows if r["is_internet"]]
    elif filt == "vpn":
        filtered = [r for r in rows if r["via"] == "vpn"]
    elif filt == "direct":
        filtered = [r for r in rows if r["via"] == "direct"]
    elif filt == "local":
        filtered = [r for r in rows if r["via"] == "local"]

    filtered = filtered[:limit]
    groups = _group_by_app(filtered)

    vpn_count = sum(1 for r in rows if r["via"] == "vpn" and r["is_internet"])
    direct_count = sum(1 for r in rows if r["via"] == "direct")
    internet_count = sum(1 for r in rows if r["is_internet"])

    summary = {
        "total_connections": len(rows),
        "shown": len(filtered),
        "apps_talking": len({r["app"] for r in filtered}),
        "internet_connections": internet_count,
        "through_vpn": vpn_count,
        "direct_internet": direct_count,
        "plain_english": _plain_summary(vpn_count, direct_count, internet_count, len(rows)),
    }

    return {
        "ok": True,
        "filter": filt,
        "filters": [
            {"id": "all", "label": "Everything", "hint": "All active connections"},
            {"id": "internet", "label": "Internet", "hint": "Apps talking to the wider internet"},
            {"id": "vpn", "label": "Through VPN", "hint": "Protected by Nord tunnel"},
            {"id": "direct", "label": "Direct ⚠️", "hint": "Bypassing VPN — worth a look if VPN is on"},
            {"id": "local", "label": "Home network", "hint": "Printers, phones, router, etc."},
        ],
        "connections": filtered,
        "groups": groups,
        "summary": summary,
    }


def _plain_summary(vpn: int, direct: int, internet: int, total: int) -> str:
    if total == 0:
        return "No active connections right now — open a website or app and refresh."
    parts = [f"{total} active connection{'s' if total != 1 else ''} right now."]
    if internet:
        parts.append(f"{internet} to the internet.")
    if vpn:
        parts.append(f"{vpn} through VPN 🛡️.")
    if direct:
        parts.append(f"{direct} going direct (not through VPN) — normal when VPN is off; check Lab if VPN is on.")
    return " ".join(parts)


def traffic_payload() -> dict[str, Any]:
    return run_traffic_watch("all")
