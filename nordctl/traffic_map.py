"""Local network traffic map — LAN and internet connection tables."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import pwd
import re
import socket
import threading
import time
from ipaddress import ip_address, ip_network
from pathlib import Path
from typing import Any

from nordctl.bandwidth import _read_counters
from nordctl.config import load_config
from nordctl.nettools import VPN_IFACES, _run, _which
from nordctl.traffic_watch import _infer_process, _reverse_name, _split_host_port

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

PORT_HINTS: dict[int, str] = {
    22: "SSH",
    80: "HTTP",
    443: "HTTPS",
    554: "RTSP",
    8080: "HTTP alt",
    8443: "HTTPS alt",
    8883: "MQTT",
}

KNOWN_SERVICE_PORTS = frozenset(PORT_HINTS.keys())

_NET_PREV: dict[str, tuple[float, int, int]] = {}
_NET_LOCK = threading.Lock()
_DNS_CACHE: dict[str, tuple[float, str]] = {}
_DNS_TTL = 3600.0

_PROC_RE = re.compile(r'users:\(\("([^"]+)"(?:,pid=(\d+))?')
_ADDR_RE = re.compile(r"(\S+:\S+|\[.+?\]:\S+)")


def _normalize_ip(ip: str) -> str:
    ip = (ip or "").strip()
    if ip.startswith("::ffff:"):
        ip = ip[7:]
    return ip.split("%")[0]


def _is_loopback(ip: str) -> bool:
    try:
        return ip_address(_normalize_ip(ip)).is_loopback
    except ValueError:
        return False


def _is_lan_ip(ip: str) -> bool:
    try:
        addr = ip_address(_normalize_ip(ip))
        return addr.is_private and not addr.is_loopback
    except ValueError:
        return False


def _is_public_ip(ip: str) -> bool:
    try:
        return not ip_address(_normalize_ip(ip)).is_private
    except ValueError:
        return False


def _hostname_for_ip(ip: str) -> str:
    if not ip:
        return ""
    now = time.time()
    cached = _DNS_CACHE.get(ip)
    if cached and now - cached[0] < _DNS_TTL:
        return cached[1]
    host = _reverse_name(ip) if _is_public_ip(ip) else ""
    if host == ip:
        host = ""
    _DNS_CACHE[ip] = (now, host)
    return host


def _process_info(pid: str | int | None) -> dict[str, Any]:
    if not pid:
        return {}
    try:
        pid_i = int(pid)
        proc_dir = Path(f"/proc/{pid_i}")
        if not proc_dir.is_dir():
            return {"pid": pid_i}
        name = (proc_dir / "comm").read_text(encoding="utf-8", errors="replace").strip()
        user = ""
        for line in (proc_dir / "status").read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("Uid:"):
                uid = int(line.split()[1])
                try:
                    user = pwd.getpwuid(uid).pw_name
                except KeyError:
                    user = str(uid)
                break
        raw_cmd = (proc_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace").strip()
        parts = raw_cmd.split()
        cmdline = " ".join(parts[:6]) + ("…" if len(parts) > 6 else "")
        return {"pid": pid_i, "name": name, "user": user, "cmdline": cmdline}
    except (OSError, ValueError, PermissionError):
        return {"pid": pid}


def _service_label(port: int, device: str = "") -> str:
    if device:
        return device
    return PORT_HINTS.get(port, "")


def _guess_direction(local_port: int, remote_port: int, remote_public: bool) -> str:
    if not remote_public:
        if local_port in KNOWN_SERVICE_PORTS:
            return "inbound"
        if remote_port in KNOWN_SERVICE_PORTS:
            return "outbound"
        return "local"
    if local_port in KNOWN_SERVICE_PORTS:
        return "inbound"
    if remote_port in KNOWN_SERVICE_PORTS:
        return "outbound"
    if local_port >= 32768 or local_port > remote_port:
        return "outbound"
    return "inbound"


def _parse_ss_row(line: str) -> dict[str, str] | None:
    parts = line.split()
    if len(parts) < 5:
        return None
    net, state = parts[0], parts[1]
    if state not in ("ESTAB", "ESTABLISHED", "SYN-SENT", "SYN-RECV", "TIME-WAIT", "LISTEN"):
        return None
    addrs = _ADDR_RE.findall(line)
    if not addrs:
        return None
    proc_m = _PROC_RE.search(line)
    return {
        "net": net,
        "state": state,
        "local": addrs[0],
        "peer": addrs[1] if len(addrs) > 1 else "",
        "proc": proc_m.group(1) if proc_m else "",
        "pid": proc_m.group(2) if proc_m and proc_m.group(2) else "",
    }


def _port_int(text: str) -> int:
    try:
        return int(text)
    except (TypeError, ValueError):
        return 0


def _connection_record(row: dict[str, str]) -> dict[str, Any] | None:
    state = row["state"]
    is_listen = state == "LISTEN"
    local_host, local_port_s = _split_host_port(row["local"])
    local_host = _normalize_ip(local_host)
    local_port = _port_int(local_port_s)
    peer_host, peer_port_s = _split_host_port(row.get("peer") or "")
    peer_host = _normalize_ip(peer_host)
    peer_port = _port_int(peer_port_s)

    if is_listen:
        if not local_host or _is_loopback(local_host):
            return None
        rip, rport = "", 0
    elif not peer_host or peer_host in ("0.0.0.0", "*", "::"):
        return None
    else:
        rip, rport = peer_host, peer_port

    remote_public = bool(rip) and _is_public_ip(rip)
    remote_lan = bool(rip) and _is_lan_ip(rip)

    if is_listen:
        scope = "internet" if local_host in ("0.0.0.0", "::") else "local"
        direction = "listening"
    elif remote_public:
        scope = "internet"
        direction = _guess_direction(local_port, rport, True)
    elif remote_lan or _is_loopback(rip):
        scope = "local"
        direction = _guess_direction(local_port, rport, False)
    else:
        return None

    proc_name = row.get("proc") or ""
    pid = row.get("pid") or ""
    if not proc_name and pid:
        proc_name = _process_info(pid).get("name", "")
    proc_name = _infer_process(proc_name, rip or local_host, str(rport or local_port), local_host) or proc_name
    pinfo = _process_info(pid) if pid else {}
    if not proc_name:
        proc_name = pinfo.get("name", "")

    lip = local_host if local_host != "0.0.0.0" else "0.0.0.0"
    svc_port = local_port if direction in ("inbound", "listening") else rport
    return {
        "status": state,
        "scope": scope,
        "direction": direction,
        "local_ip": lip,
        "local_port": local_port,
        "local_host": _hostname_for_ip(lip) if lip and lip != "0.0.0.0" and not _is_loopback(lip) else "",
        "local_device": _service_label(local_port) if scope == "local" else "",
        "remote_ip": rip,
        "remote_port": rport,
        "remote_host": _hostname_for_ip(rip) if rip else "",
        "remote_device": "",
        "service": _service_label(svc_port),
        "process": proc_name or pinfo.get("name", ""),
        "pid": pinfo.get("pid") or (int(pid) if pid else None),
        "user": pinfo.get("user", ""),
        "cmdline": pinfo.get("cmdline", ""),
        "proto": row["net"].lower().replace("v6", "").upper() or "TCP",
    }


def _list_connections() -> list[dict[str, Any]]:
    if not _which("ss"):
        return []
    raw = _run(["ss", "-H", "-tunap"], timeout=10)
    if not raw.get("ok") or not raw.get("output"):
        raw = _run(["ss", "-tunap"], timeout=10)
    seen: set[tuple] = set()
    out: list[dict[str, Any]] = []
    for line in (raw.get("output") or "").splitlines():
        line = line.strip()
        if not line or line.startswith(("State", "Netid")):
            continue
        parsed = _parse_ss_row(line)
        if not parsed:
            continue
        rec = _connection_record(parsed)
        if not rec:
            continue
        key = (
            rec["status"],
            rec["local_ip"],
            rec["local_port"],
            rec["remote_ip"],
            rec["remote_port"],
            rec.get("pid"),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(rec)
    return sorted(
        out,
        key=lambda r: (
            r["scope"],
            r["direction"],
            r.get("remote_ip") or "",
            r.get("remote_port") or 0,
            r.get("local_port") or 0,
        ),
    )


def _iface_rates() -> dict[str, dict[str, Any]]:
    now = time.time()
    counters = _read_counters()
    out: dict[str, dict[str, Any]] = {}
    with _NET_LOCK:
        for name, (rx, tx) in counters.items():
            if name == "lo" or name.startswith(("docker", "veth", "br-", "virbr")):
                continue
            prev = _NET_PREV.get(name)
            _NET_PREV[name] = (now, rx, tx)
            if prev and now > prev[0]:
                dt = now - prev[0]
                up_mbps = round(max(0, tx - prev[2]) * 8 / dt / 1e6, 2)
                down_mbps = round(max(0, rx - prev[1]) * 8 / dt / 1e6, 2)
            else:
                up_mbps = down_mbps = 0.0
            out[name] = {"present": True, "up_mbps": up_mbps, "down_mbps": down_mbps}
    return out


def _pick_iface(ifaces: dict[str, dict], *candidates: str) -> dict[str, Any]:
    for c in candidates:
        for name, data in ifaces.items():
            if name == c or name.startswith(c):
                return data
    return {}


def _local_ip() -> str:
    from nordctl.ip_info import primary_lan_iface

    iface = primary_lan_iface()
    if not iface:
        return ""
    r = _run(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=4)
    for line in (r.get("output") or "").splitlines():
        parts = line.split()
        if len(parts) >= 4:
            return parts[3].split("/")[0]
    return ""


def _gateway_reachable() -> bool:
    r = _run(["ip", "route", "show", "default"], timeout=4)
    if not r.get("ok"):
        return False
    m = re.search(r"\bvia (\d+\.\d+\.\d+\.\d+)", r.get("output") or "")
    if not m:
        return False
    gw = m.group(1)
    ping = _run(["ping", "-c", "1", "-W", "1", gw], timeout=3)
    return bool(ping.get("ok"))


def _mesh_info() -> dict[str, Any]:
    try:
        from nordctl.meshnet_ui import meshnet_state

        mesh = meshnet_state()
        host = mesh.get("mesh_ip") or ""
        up = bool(host) and mesh.get("meshnet_enabled")
        routing = False
        r = _run(["nordvpn", "settings"], timeout=4)
        if r.get("ok"):
            routing = "Routing: enabled" in (r.get("output") or "")
        peers = []
        for p in mesh.get("peers") or []:
            hostname = p.get("hostname") or p.get("name") or ""
            status = p.get("status") or p.get("connection status") or ""
            peers.append({
                "hostname": hostname,
                "ip": p.get("ip") or p.get("nordlynx ip") or "",
                "status": status,
                "online": str(status).lower() in ("connected", "online"),
            })
        return {"up": up, "host": host, "routing": routing, "peers": peers}
    except Exception:
        return {"up": False, "host": "", "routing": False, "peers": []}


def _connect_path(ifaces: dict, lan_ip: str, hostname: str) -> list[dict[str, Any]]:
    wan = _pick_iface(ifaces, "wlo1", "wlan0", "wlp", "eth0", "enp") or {}
    wan_name = next((n for n in ifaces if n.startswith(("wlp", "wlan", "eth", "enp"))), "LAN")
    gw_ok = _gateway_reachable()
    return [
        {
            "name": "Internet",
            "via": f"{wan_name} WAN",
            "speed": f"↓{wan.get('down_mbps', 0)} ↑{wan.get('up_mbps', 0)} Mbps",
            "up": True,
        },
        {"name": "Router", "ip": "gateway", "via": "default route", "up": gw_ok},
        {
            "name": socket.gethostname() or "This PC",
            "ip": lan_ip or "—",
            "via": wan_name,
            "detail": hostname,
            "up": True,
        },
    ]


def _network_links(mesh: dict[str, Any]) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = [{
        "name": "Nord Meshnet",
        "via": "nordlynx",
        "ip": mesh.get("host") or "—",
        "detail": "routing " + ("on" if mesh.get("routing") else "off"),
        "up": bool(mesh.get("up")),
    }]
    for peer in mesh.get("peers") or []:
        links.append({
            "name": peer.get("hostname") or "Mesh peer",
            "via": "Meshnet peer",
            "ip": peer.get("ip") or "",
            "detail": peer.get("status") or "",
            "up": bool(peer.get("online")),
        })
    return links


def _outbound_feeds(conns: list[dict[str, Any]]) -> list[dict[str, Any]]:
    feeds: list[dict[str, Any]] = []
    nord_hits = [c for c in conns if c.get("process", "").lower().find("nord") >= 0 or c.get("remote_port") in (443, 1194)]
    feeds.append({
        "id": "nordvpn",
        "name": "NordVPN",
        "dest": "VPN tunnel",
        "via": "nordlynx",
        "active": bool(nord_hits),
        "service_up": bool(_run(["systemctl", "is-active", "nordvpnd"], timeout=3).get("ok")),
        "detail": ", ".join(f"{c['remote_ip']}:{c['remote_port']}" for c in nord_hits[:2]) if nord_hits else "no active tunnel sockets",
    })
    return feeds


def _service_counts() -> tuple[int, int]:
    total = 0
    up = 0
    for unit in ("nordvpnd", "nordctl"):
        total += 1
        r = _run(["systemctl", "is-active", unit], timeout=3)
        if r.get("ok") and "active" in (r.get("output") or "").strip():
            up += 1
    return up, total


def _summary_block(cfg: dict[str, Any], ifaces: dict) -> dict[str, Any]:
    from nordctl import nordvpn as nv
    from nordctl.ip_info import build_ip_info, display_public_ip

    lan = _pick_iface(ifaces, "br0", "wlan0", "wlp", "eth0", "enp") or {}
    wan = _pick_iface(ifaces, "wlan0", "wlp", "eth0", "enp") or lan
    mesh_if = _pick_iface(ifaces, "nordlynx", "nordtun") or {}
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))
    settings = nv.parse_settings(nv.run_cached(bin_path, ["settings"], timeout=8).get("output", ""))
    ip_info = build_ip_info(cfg, status, settings=settings, fast=False)
    vpn_connected = bool(status.get("connected"))
    ext_ip = display_public_ip(ip_info)
    ext_country = str(status.get("Country") or "")
    svc_up, svc_total = _service_counts()
    mesh = _mesh_info()
    return {
        "lan_down_mbps": lan.get("down_mbps", 0),
        "lan_up_mbps": lan.get("up_mbps", 0),
        "wan_down_mbps": wan.get("down_mbps", 0),
        "wan_up_mbps": wan.get("up_mbps", 0),
        "mesh_down_mbps": mesh_if.get("down_mbps", 0),
        "mesh_up_mbps": mesh_if.get("up_mbps", 0),
        "lan_ip": _local_ip(),
        "external_ip": ext_ip,
        "external_country": ext_country,
        "vpn_connected": vpn_connected,
        "mesh_ip": mesh.get("host") or "",
        "services_up": svc_up,
        "services_total": svc_total,
    }


def build_traffic_map(*, force: bool = False) -> dict[str, Any]:
    """Full traffic map payload for Internet + Local dashboard pages."""
    del force  # reserved for future cache
    cfg = load_config()
    ifaces = _iface_rates()
    conns = _list_connections()
    mesh = _mesh_info()
    summary = _summary_block(cfg, ifaces)
    hostname = socket.gethostname()

    local = [c for c in conns if c["scope"] == "local" and c["status"] in ("ESTAB", "ESTABLISHED")]
    local_listening = [c for c in conns if c["scope"] == "local" and c["direction"] == "listening"]
    internet = [c for c in conns if c["scope"] == "internet"]
    outbound = [c for c in internet if c["direction"] == "outbound" and c["status"] in ("ESTAB", "ESTABLISHED")]
    inbound = [c for c in internet if c["direction"] == "inbound" and c["status"] in ("ESTAB", "ESTABLISHED")]
    listening = [c for c in internet if c["direction"] == "listening"]

    ext_for_feeds = [
        {"remote_ip": c["remote_ip"], "remote_port": c["remote_port"], "process": c.get("process", "")}
        for c in outbound
    ]

    return {
        "ok": True,
        "ts": time.time(),
        "summary": summary,
        "interfaces": ifaces,
        "meshnet": mesh,
        "connect_path": _connect_path(ifaces, summary.get("lan_ip") or "", hostname),
        "network_links": _network_links(mesh),
        "local_connections": local,
        "local_listening": local_listening,
        "internet_outbound": outbound,
        "internet_inbound": inbound,
        "internet_listening": listening,
        "outbound_feeds": _outbound_feeds(ext_for_feeds),
        "counts": {
            "local_sessions": len(local),
            "internet_outbound": len(outbound),
            "internet_inbound": len(inbound),
            "internet_listening": len(listening),
        },
    }
