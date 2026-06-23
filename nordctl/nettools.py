"""Read-only network diagnostics for VPN routing and traffic visibility."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from pathlib import Path

MAX_OUTPUT = 12000
TARGET_RE = re.compile(r"^[a-zA-Z0-9._\-:/]+$")
VPN_IFACES = ("nordlynx", "nordtun", "tun0", "wg0")

def _tool_row(
    id: str,
    label: str,
    *,
    needs_target: bool = False,
    needs_root: bool = False,
    terminal_cmd: str = "",
    hint: str = "",
    detail: str = "",
    example: str = "",
    install_id: str | None = None,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "id": id,
        "label": label,
        "needs_target": needs_target,
        "needs_root": needs_root,
        "hint": hint or detail.split(".")[0],
        "detail": detail,
    }
    if terminal_cmd:
        row["terminal_cmd"] = terminal_cmd
    if example:
        row["example"] = example
    if install_id:
        row["install_id"] = install_id
    return row


TOOL_DEFS: list[dict[str, Any]] = [
    _tool_row(
        "overview",
        "Overview",
        hint="Default route and path to common targets",
        detail="Shows your default gateway, which interface traffic uses, and a quick route lookup to Cloudflare and Google DNS. Use this first when VPN is on to see whether packets leave via nordlynx/tun or your normal WiFi.",
        example="Combines ip route show and ip route get — no target field needed.",
        install_id="iputils-ping",
    ),
    _tool_row(
        "routes",
        "Routing table",
        hint="Full kernel routing table (ip route)",
        detail="Lists every route on this PC — default route, LAN subnets, and VPN tunnel routes. Lines mentioning nordlynx, nordtun, or tun0 mean traffic is steered through the VPN.",
        example="Same as running: ip route show",
    ),
    _tool_row(
        "route_get",
        "Route lookup",
        needs_target=True,
        hint="Which interface handles traffic to a host",
        detail="Asks the kernel which interface and gateway would carry a packet to the host or IP you enter. Helps answer “does traffic to this site go through the VPN or direct?”",
        example="Target: 8.8.8.8 or google.com — runs ip route get",
    ),
    _tool_row(
        "connections",
        "Connections",
        hint="Active sockets (ss / netstat)",
        detail="Lists open TCP/UDP connections and listening ports. Process names appear when your user may read them; otherwise you still see addresses and ports.",
        example="Runs ss -tun (or netstat). Read-only — no sudo.",
        install_id="net-tools",
    ),
    _tool_row(
        "traceroute",
        "Traceroute",
        needs_target=True,
        hint="Hop-by-hop path (tracepath / mtr / traceroute)",
        detail="Traces each router hop between this PC and the target host. Useful for latency issues and seeing where packets leave your ISP. Can take 10–45 seconds — wait for output below.",
        example="Target: google.com or 1.1.1.1 — uses mtr, traceroute, or tracepath (first installed).",
        install_id="mtr",
    ),
    _tool_row(
        "dns",
        "DNS lookup",
        needs_target=True,
        hint="Resolve a hostname (dig / host)",
        detail="Resolves a hostname to IP addresses using your current DNS setup (VPN DNS, Pi-hole, router, etc.). Shows both short and full dig answers when dig is installed.",
        example="Target: cloudflare.com — runs dig +short and dig +answer",
        install_id="dnsutils",
    ),
    _tool_row(
        "ping",
        "Ping",
        needs_target=True,
        hint="ICMP reachability test",
        detail="Sends four ICMP echo requests to check reachability and round-trip time. Fails if the host blocks ping or you have no route — that is normal for some sites.",
        example="Target: 1.1.1.1 — runs ping -c 4",
        install_id="iputils-ping",
    ),
    _tool_row(
        "interfaces",
        "Interfaces",
        hint="Addresses and VPN tunnel devices",
        detail="Shows network interface names, UP/DOWN state, and IPv4/IPv6 addresses. Look for nordlynx or tun devices when NordVPN is connected.",
        example="Runs ip -br addr and ip link",
    ),
    _tool_row(
        "public_ip",
        "Public IP",
        hint="Home ISP vs VPN exit (not default-route only)",
        detail="Shows your home ISP address for Smart DNS allowlisting and the default-route check (VPN exit when connected). Do not allowlist the VPN exit in Nord Account.",
        example="Runs nordctl public-ip — uses LAN probe, cache, or trusted zone when VPN is on.",
        install_id="curl",
    ),
    _tool_row(
        "listening",
        "Listening ports",
        hint="Local services accepting connections (ss -lntu)",
        detail="Lists programs listening for incoming connections on this machine (SSH, web UI, Samba, etc.). Helpful before opening UFW ports or checking exposure on LAN.",
        example="Runs ss -lntu — read-only, no sudo.",
        install_id="net-tools",
    ),
    _tool_row(
        "neighbors",
        "ARP / neighbors",
        hint="Layer-2 neighbor table (ip neigh)",
        detail="Shows devices your PC has talked to on the local network (ARP/neighbour cache) — routers, phones, printers on the same subnet.",
        example="Runs ip neigh show",
    ),
    _tool_row(
        "resolv",
        "DNS config",
        hint="resolv.conf and resolvectl status",
        detail="Displays /etc/resolv.conf and systemd-resolved status. Use when DNS leaks, Pi-hole conflicts, or Nord DNS changes are suspected.",
        example="Reads resolv.conf; optional resolvectl status",
    ),
    _tool_row(
        "networkmanager",
        "NetworkManager",
        hint="Active connections and WiFi profiles (nmcli)",
        detail="Summarises NetworkManager state — active WiFi/Ethernet profile, device status, and connection list. Pairs with the WiFi hub tabs for profile edits.",
        example="Runs nmcli general status and connection show --active",
    ),
    _tool_row(
        "ufw",
        "UFW status",
        needs_root=True,
        terminal_cmd="sudo ufw status verbose numbered",
        hint="Uncomplicated Firewall rules (read-only, sudo)",
        detail="Read-only snapshot of Linux UFW — active state and numbered allow/deny rules. Opens Network → Terminal with a sudo password box because ufw status requires root on most systems.",
        example="Runs sudo ufw status verbose numbered in Terminal",
        install_id="ufw",
    ),
    _tool_row(
        "nft",
        "nftables",
        needs_root=True,
        terminal_cmd="sudo nft list ruleset",
        hint="Kernel nft ruleset summary (read-only, sudo)",
        detail="Dumps kernel nftables rules (UFW uses nft on modern Ubuntu). Opens Network → Terminal with a sudo password box for the full ruleset.",
        example="Runs sudo nft list ruleset in Terminal",
        install_id="nftables",
    ),
    _tool_row(
        "nmap",
        "Port scan",
        needs_target=True,
        needs_root=True,
        terminal_cmd="sudo nmap -F -T4 --open {target}",
        hint="Quick TCP scan of top ports (sudo, Terminal)",
        detail="Runs a fast TCP scan of common ports on the target you enter. Opens Network → Terminal with a sudo password box. Only scan hosts you own or have permission to test.",
        example="Target: 192.168.1.1 — sudo nmap -F in Terminal",
        install_id="nmap",
    ),
    _tool_row(
        "whois",
        "WHOIS",
        needs_target=True,
        hint="Domain registration info",
        detail="Looks up domain registration and nameserver info for a domain name — useful for DNS troubleshooting, not for raw IPs.",
        example="Target: example.com — runs whois",
        install_id="whois",
    ),
    _tool_row(
        "nc_probe",
        "Port probe",
        needs_target=True,
        hint="TCP connect test to host:port (nc)",
        detail="Tries to open a TCP connection to host:port (e.g. 192.168.1.1:443) and reports success or timeout. Good for “is this port reachable?”",
        example="Target: google.com:443 or 10.0.0.1:22",
        install_id="netcat",
    ),
    _tool_row(
        "iperf3",
        "iperf3 client",
        needs_target=True,
        hint="3-second download test to an iperf3 server (host:5201)",
        detail="Runs a short iperf3 download test against an iperf3 server you specify. You need a reachable server (host or host:5201).",
        example="Target: iperf.example.net:5201 — 3 s download test",
        install_id="iperf3",
    ),
]

DEFAULT_TARGETS = ["1.1.1.1", "8.8.8.8", "cloudflare.com", "google.com"]


def _run(argv: list[str], timeout: float = 12.0) -> dict[str, Any]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        ok = r.returncode == 0
        if len(out) > MAX_OUTPUT:
            out = out[:MAX_OUTPUT] + "\n… (output truncated)"
        return {"ok": ok, "output": out, "command": " ".join(argv)}
    except subprocess.TimeoutExpired:
        return {"ok": False, "output": "Command timed out", "command": " ".join(argv)}
    except FileNotFoundError:
        return {"ok": False, "output": f"Not found: {argv[0]}", "command": " ".join(argv)}


def _which(name: str) -> str | None:
    return shutil.which(name)


def validate_target(target: str) -> str | None:
    t = (target or "").strip()
    if not t:
        return "target required"
    if len(t) > 253:
        return "target too long"
    if not TARGET_RE.match(t):
        return "invalid target characters"
    return None


def _looks_like_ip(target: str) -> bool:
    if ":" in target:
        return True
    parts = target.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return True
    return False


def _resolve_target(target: str) -> tuple[str, str | None]:
    """Return (lookup_target, resolved_note)."""
    t = target.strip()
    if _looks_like_ip(t):
        return t, None
    lookup = _run(["getent", "hosts", t], timeout=5)
    if lookup["ok"]:
        parts = lookup["output"].split()
        if parts:
            return parts[0], f"{t} → {parts[0]}"
    return t, None


def _via_vpn(text: str) -> bool:
    low = text.lower()
    return any(iface in low for iface in VPN_IFACES)


def _tool_ping(target: str) -> dict[str, Any]:
    return _run(["ping", "-c", "4", "-W", "2", target], timeout=15)


def _tool_dns(target: str) -> dict[str, Any]:
    if _which("dig"):
        short = _run(["dig", "+short", target], timeout=8)
        full = _run(["dig", "+noall", "+answer", target], timeout=8)
        out = f";; dig +short {target}\n{short['output']}\n\n;; dig answer\n{full['output']}"
        return {"ok": short["ok"] or full["ok"], "output": out, "command": f"dig {target}"}
    if _which("host"):
        return _run(["host", target], timeout=8)
    return {"ok": False, "output": "dig or host not installed", "command": "dig"}


def _tool_traceroute(target: str) -> dict[str, Any]:
    # Prefer non-interactive tools — mtr --report can hang without a TTY in the web UI.
    if _which("tracepath"):
        return _run(["tracepath", "-n", target], timeout=45)
    if _which("traceroute"):
        return _run(["traceroute", "-n", "-w", "2", "-q", "1", "-m", "20", target], timeout=40)
    if _which("mtr"):
        return _run(["mtr", "-r", "-c", "3", "-n", target], timeout=45)
    return {"ok": False, "output": "Install tracepath, traceroute, or mtr", "command": "tracepath"}


def _tool_connections() -> dict[str, Any]:
    if _which("ss"):
        result = _run(["ss", "-tun"], timeout=10)
        cmd = "ss -tun"
        if not result["ok"]:
            result = _run(["ss", "-tunap"], timeout=10)
            cmd = "ss -tunap"
    elif _which("netstat"):
        result = _run(["netstat", "-tun"], timeout=10)
        cmd = "netstat -tun"
        if not result["ok"]:
            result = _run(["netstat", "-tunap"], timeout=10)
            cmd = "netstat -tunap"
    else:
        return {"ok": False, "output": "ss or netstat not installed", "command": "ss"}
    lines = result["output"].splitlines()
    vpn_lines = [ln for ln in lines if any(v in ln.lower() for v in VPN_IFACES)]
    summary = f"{max(0, len(lines) - 1)} socket lines"
    if vpn_lines:
        summary += f" · {len(vpn_lines)} via VPN tunnel"
    result["summary"] = summary
    result["vpn_line_count"] = len(vpn_lines)
    result["command"] = cmd
    return result


def _tool_routes() -> dict[str, Any]:
    result = _run(["ip", "route", "show"], timeout=8)
    result["via_vpn"] = _via_vpn(result["output"])
    return result


def _tool_route_get(target: str) -> dict[str, Any]:
    lookup, note = _resolve_target(target)
    result = _run(["ip", "route", "get", lookup], timeout=8)
    result["via_vpn"] = _via_vpn(result["output"])
    result["target"] = target
    if note:
        result["resolved"] = note
        result["output"] = f"# {note}\n{result['output']}"
    return result


def _tool_interfaces() -> dict[str, Any]:
    addr = _run(["ip", "-br", "addr"], timeout=6)
    link = _run(["ip", "link", "show"], timeout=6)
    parts = ["# Addresses\n" + addr["output"]]
    for iface in VPN_IFACES:
        show = _run(["ip", "-4", "-o", "addr", "show", "dev", iface], timeout=4)
        if show["output"]:
            parts.append(f"\n# {iface}\n{show['output']}")
    parts.append("\n# Links (tail)\n" + "\n".join(link["output"].splitlines()[-24:]))
    out = "\n".join(parts).strip()
    return {
        "ok": addr["ok"],
        "output": out[:MAX_OUTPUT],
        "command": "ip -br addr; ip link",
        "via_vpn": any(iface in out.lower() for iface in VPN_IFACES),
    }


def _tool_public_ip() -> dict[str, Any]:
    from nordctl.config import load_config
    from nordctl.ip_info import public_ip_report

    rep = public_ip_report(load_config())
    return {
        "ok": bool(rep.get("ok")),
        "output": rep.get("text") or "Could not fetch public IP\n",
        "command": "nordctl public-ip",
        "home_ip": rep.get("home_ip"),
        "routed_ip": rep.get("routed_ip"),
    }


def _tool_listening() -> dict[str, Any]:
    if _which("ss"):
        result = _run(["ss", "-lntu"], timeout=10)
        if not result["ok"]:
            result = _run(["ss", "-lntup"], timeout=10)
            result["command"] = "ss -lntup"
        else:
            result["command"] = "ss -lntu"
        return result
    if _which("netstat"):
        result = _run(["netstat", "-lntu"], timeout=10)
        if not result["ok"]:
            result = _run(["netstat", "-lntup"], timeout=10)
            result["command"] = "netstat -lntup"
        else:
            result["command"] = "netstat -lntu"
        return result
    return {"ok": False, "output": "ss or netstat not installed", "command": "ss -lntu"}


def _tool_neighbors() -> dict[str, Any]:
    return _run(["ip", "neigh", "show"], timeout=8)


def _tool_resolv() -> dict[str, Any]:
    parts: list[str] = []
    resolv = Path("/etc/resolv.conf")
    if resolv.is_file():
        try:
            text = resolv.read_text(encoding="utf-8", errors="replace")
            parts.append("# /etc/resolv.conf\n" + text.strip())
        except OSError as exc:
            parts.append(f"# /etc/resolv.conf — read failed: {exc}")
    else:
        parts.append("# /etc/resolv.conf — not found")
    if _which("resolvectl"):
        st = _run(["resolvectl", "status"], timeout=8)
        parts.append("\n# resolvectl status\n" + (st["output"] or "none"))
    return {"ok": True, "output": "\n".join(parts).strip(), "command": "resolv.conf; resolvectl"}


def _tool_networkmanager() -> dict[str, Any]:
    if not _which("nmcli"):
        return {"ok": False, "output": "nmcli not installed — install network-manager", "command": "nmcli"}
    general = _run(["nmcli", "general", "status"], timeout=8)
    active = _run(["nmcli", "-f", "NAME,UUID,TYPE,DEVICE,STATE", "connection", "show", "--active"], timeout=8)
    wifi = _run(["nmcli", "-f", "IN-USE,SSID,BSSID,SIGNAL,SECURITY", "device", "wifi", "list"], timeout=12)
    parts = [
        "# nmcli general status\n" + (general["output"] or "none"),
        "\n# active connections\n" + (active["output"] or "none"),
        "\n# nearby WiFi (scan)\n" + (wifi["output"] or "none"),
    ]
    ok = general["ok"] or active["ok"]
    return {"ok": ok, "output": "\n".join(parts).strip(), "command": "nmcli general; nmcli connection show --active"}


def _tool_ufw() -> dict[str, Any]:
    if not _which("ufw"):
        return {"ok": False, "output": "ufw not installed", "command": "ufw status"}
    return _run(["ufw", "status", "verbose"], timeout=10)


def _tool_nmap(target: str) -> dict[str, Any]:
    if not _which("nmap"):
        return {"ok": False, "output": "nmap not installed — use Advanced → Networking tools → Install nmap", "command": "nmap"}
    host = target.split(":")[0].strip()
    return _run(["nmap", "-F", "-T4", "--open", host], timeout=90)


def _tool_whois(target: str) -> dict[str, Any]:
    if not _which("whois"):
        return {"ok": False, "output": "whois not installed — use Advanced → Networking tools → Install whois", "command": "whois"}
    return _run(["whois", target.strip()], timeout=20)


def _tool_nc_probe(target: str) -> dict[str, Any]:
    nc = _which("nc") or _which("nc.openbsd")
    if not nc:
        return {"ok": False, "output": "nc not installed — use Advanced → Networking tools → Install netcat", "command": "nc"}
    t = target.strip()
    if ":" in t:
        host, port_s = t.rsplit(":", 1)
        port = port_s.strip()
    else:
        host, port = t, "443"
    if not port.isdigit():
        return {"ok": False, "output": "Use host:port (e.g. 192.168.1.1:22)", "command": "nc -zv host port"}
    return _run([nc, "-zv", "-w", "3", host, port], timeout=8)


def _tool_iperf3(target: str) -> dict[str, Any]:
    if not _which("iperf3"):
        return {"ok": False, "output": "iperf3 not installed — use Advanced → Networking tools → Install iperf3", "command": "iperf3"}
    t = target.strip()
    if ":" in t:
        host, port_s = t.rsplit(":", 1)
        port = port_s.strip()
    else:
        host, port = t, "5201"
    if not port.isdigit():
        return {"ok": False, "output": "Use host or host:5201", "command": "iperf3 -c host"}
    return _run(["iperf3", "-c", host, "-p", port, "-t", "3", "-J"], timeout=25)


def _tool_nft() -> dict[str, Any]:
    if not _which("nft"):
        return {"ok": False, "output": "nft not installed", "command": "nft list ruleset"}
    result = _run(["nft", "list", "ruleset"], timeout=12)
    if not result["ok"] and "permission" in (result["output"] or "").lower():
        result["output"] = (
            (result["output"] or "")
            + "\n\n# Tip: run in terminal with sudo for full ruleset, or use Nord/UFW panels in Dashboard."
        )
    return result


def _tool_overview() -> dict[str, Any]:
    default = _run(["ip", "route", "show", "default"], timeout=6)
    sections = ["# Default route\n" + (default["output"] or "none")]
    for target in DEFAULT_TARGETS:
        lookup, note = _resolve_target(target)
        hop = _run(["ip", "route", "get", lookup], timeout=6)
        flag = "via VPN" if _via_vpn(hop["output"]) else "direct/ISP"
        prefix = f"# Route to {target} ({flag})"
        if note:
            prefix += f" — {note}"
        sections.append(f"\n{prefix}\n{hop['output'] or 'lookup failed'}")
    ping = _run(["ping", "-c", "1", "-W", "2", "1.1.1.1"], timeout=6)
    sections.append(f"\n# Ping 1.1.1.1\n{ping['output']}")
    out = "\n".join(sections)
    return {
        "ok": default["ok"],
        "output": out,
        "command": "ip route + ip route get",
        "via_vpn": _via_vpn(out),
    }


def run_tool(tool: str, target: str = "") -> dict[str, Any]:
    tool = (tool or "overview").strip().lower()
    known = {t["id"] for t in TOOL_DEFS}
    if tool not in known:
        return {"ok": False, "error": f"unknown tool: {tool}", "tools": [t["id"] for t in TOOL_DEFS]}

    meta = next(t for t in TOOL_DEFS if t["id"] == tool)
    if meta.get("needs_target"):
        err = validate_target(target)
        if err:
            return {"ok": False, "error": err, "tool": tool}

    runners = {
        "overview": lambda: _tool_overview(),
        "routes": _tool_routes,
        "route_get": lambda: _tool_route_get(target.strip()),
        "connections": _tool_connections,
        "traceroute": lambda: _tool_traceroute(target.strip()),
        "dns": lambda: _tool_dns(target.strip()),
        "ping": lambda: _tool_ping(target.strip()),
        "interfaces": _tool_interfaces,
        "public_ip": _tool_public_ip,
        "listening": _tool_listening,
        "neighbors": _tool_neighbors,
        "resolv": _tool_resolv,
        "networkmanager": _tool_networkmanager,
        "ufw": _tool_ufw,
        "nft": _tool_nft,
        "nmap": lambda: _tool_nmap(target.strip()),
        "whois": lambda: _tool_whois(target.strip()),
        "nc_probe": lambda: _tool_nc_probe(target.strip()),
        "iperf3": lambda: _tool_iperf3(target.strip()),
    }
    result = runners[tool]()
    result["tool"] = tool
    result["label"] = meta["label"]
    if target.strip():
        result["target"] = target.strip()
    return result


def _tool_install_status() -> dict[str, bool]:
    from nordctl.tool_install import TOOL_CATALOG, _is_installed

    return {item["id"]: _is_installed(item) for item in TOOL_CATALOG}


def nettools_payload() -> dict[str, Any]:
    from nordctl.tool_install import tool_installed

    overview = _tool_overview()
    install_status = _tool_install_status()
    tools_out = []
    for meta in TOOL_DEFS:
        row = dict(meta)
        iid = meta.get("install_id")
        if iid:
            row["install_id"] = iid
            row["package_installed"] = install_status.get(iid, tool_installed(iid))
        else:
            row["package_installed"] = True
        tools_out.append(row)
    return {
        "ok": True,
        "tools": tools_out,
        "default_targets": DEFAULT_TARGETS,
        "available": {
            "ss": bool(_which("ss")),
            "netstat": bool(_which("netstat")),
            "tracepath": bool(_which("tracepath")),
            "traceroute": bool(_which("traceroute")),
            "mtr": bool(_which("mtr")),
            "dig": bool(_which("dig")),
            "ping": bool(_which("ping")),
            "curl": bool(_which("curl")),
            "ufw": bool(_which("ufw")),
            "nft": bool(_which("nft")),
            "nmap": bool(_which("nmap")),
            "whois": bool(_which("whois")),
            "nc": bool(_which("nc") or _which("nc.openbsd")),
            "iperf3": bool(_which("iperf3")),
            "resolvectl": bool(_which("resolvectl")),
            "nmcli": bool(_which("nmcli")),
        },
        "install_status": install_status,
        "overview": overview,
    }
