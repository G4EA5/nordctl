"""TCP listening ports on this machine — for Security → Listeners."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path
from typing import Any

# Well-known services (Linux desktop / server — generic, not site-specific).
PORT_LABELS: dict[int, str] = {
    21: "FTP",
    22: "SSH",
    23: "Telnet",
    25: "SMTP",
    53: "DNS",
    80: "HTTP",
    111: "RPC bind",
    139: "NetBIOS",
    443: "HTTPS",
    445: "SMB",
    631: "CUPS printing",
    1080: "SOCKS proxy",
    2049: "NFS",
    3306: "MySQL",
    3389: "RDP",
    5353: "mDNS (Avahi)",
    5432: "PostgreSQL",
    5900: "VNC",
    5901: "VNC",
    6379: "Redis",
    8080: "HTTP alt",
    8443: "HTTPS alt",
    8765: "nordctl web UI (default)",
    9050: "Tor",
    27017: "MongoDB",
}


def _run(cmd: list[str], *, timeout: float = 12) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)


def _hex_ip_to_str(hex_ip: str, *, v6: bool = False) -> str:
    if not v6:
        raw = bytes.fromhex(hex_ip.zfill(8))
        return ".".join(str(b) for b in reversed(raw))
    if hex_ip == "00000000000000000000000000000000":
        return "::"
    return hex_ip


def _parse_ss_addr(addr: str) -> tuple[str, int]:
    addr = (addr or "").strip()
    if addr.startswith("[") and "]:" in addr:
        host, port_s = addr[1:].rsplit("]:", 1)
        return host, int(port_s)
    if addr == "*":
        return "*", 0
    if ":" in addr:
        host, port_s = addr.rsplit(":", 1)
        if port_s.isdigit():
            return host, int(port_s)
    return addr, 0


def _bind_scope(host: str) -> str:
    h = (host or "").strip().lower()
    if h in ("127.0.0.1", "::1", "localhost") or h.startswith("127."):
        return "localhost"
    if h in ("0.0.0.0", "::", "*"):
        return "lan"
    return "lan"


def _listening_socket_inodes() -> dict[tuple[str, int], str]:
    out: dict[tuple[str, int], str] = {}
    for path, v6 in (("/proc/net/tcp", False), ("/proc/net/tcp6", True)):
        try:
            lines = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) < 10 or parts[3] != "0A":
                continue
            local, inode = parts[1], parts[9]
            ip_hex, port_hex = local.split(":")
            port = int(port_hex, 16)
            host = _hex_ip_to_str(ip_hex, v6=v6)
            out[(host, port)] = inode
    return out


def _inode_process_map() -> dict[str, str]:
    found: dict[str, str] = {}
    try:
        entries = list(Path("/proc").iterdir())
    except OSError:
        return found
    for pid_dir in entries:
        if not pid_dir.name.isdigit():
            continue
        try:
            cmd = (pid_dir / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace").strip()
        except OSError:
            continue
        if not cmd:
            try:
                cmd = (pid_dir / "comm").read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
        try:
            fds = list((pid_dir / "fd").iterdir())
        except OSError:
            continue
        for fd in fds:
            try:
                link = os.readlink(fd)
            except OSError:
                continue
            if link.startswith("socket:["):
                found[link[8:-1]] = cmd[:120]
    return found


def _dynamic_port_labels() -> dict[int, str]:
    labels: dict[int, str] = {}
    try:
        r = _run(["ps", "-eo", "pid=,args="], timeout=8)
        if r.returncode != 0:
            return labels
        for line in (r.stdout or "").splitlines():
            cmd = line.strip()
            if not cmd:
                continue
            if "dropbear" in cmd:
                for m in re.finditer(r"-p\s+(\d+)", cmd):
                    labels[int(m.group(1))] = "SSH (dropbear)"
            low = cmd.lower()
            if "nordctl" in low and (" serve" in low or low.endswith(" serve") or " serve " in low):
                for m in re.finditer(r":(\d{2,5})\b", cmd):
                    labels[int(m.group(1))] = "nordctl web UI"
                for m in re.finditer(r"--port\s+(\d+)", cmd):
                    labels[int(m.group(1))] = "nordctl web UI"
    except (OSError, subprocess.TimeoutExpired):
        pass
    return labels


def _port_label(port: int, extra: dict[int, str]) -> str:
    if port <= 0:
        return ""
    if port in extra:
        return extra[port]
    return PORT_LABELS.get(port, "")


def _ss_commands() -> list[list[str]]:
    return [
        ["sudo", "-n", "/usr/bin/ss", "-tlnp"],
        ["/usr/bin/ss", "-tlnp"],
        ["ss", "-tlnp"],
    ]


def _resolve_process(
    addr: str,
    ss_proc: str,
    inodes: dict[tuple[str, int], str],
    proc_by_inode: dict[str, str],
    port_labels: dict[int, str],
) -> str:
    proc = (ss_proc or "").strip()
    if proc:
        return proc[:120]

    host, port = _parse_ss_addr(addr)
    candidates: list[str] = []
    for key in ((host, port), ("0.0.0.0", port), ("::", port), ("*", port)):
        inode = inodes.get(key)
        if inode:
            candidates.append(inode)
    if not candidates:
        candidates = [inode for (h, p), inode in inodes.items() if p == port]

    for inode in candidates:
        name = proc_by_inode.get(inode)
        if name:
            return name[:120]

    label = _port_label(port, port_labels)
    return label


def listening_ports_payload(*, limit: int = 80) -> dict[str, Any]:
    stdout = ""
    ss_cmd = ""
    for cmd in _ss_commands():
        try:
            r = _run(cmd, timeout=12)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if r.returncode == 0 and (r.stdout or "").strip():
            stdout = r.stdout or ""
            ss_cmd = " ".join(cmd)
            break

    if not stdout:
        return {
            "ok": False,
            "error": "Could not run ss — install iproute2 (ss) or net-tools.",
            "listeners": [],
        }

    inodes = _listening_socket_inodes()
    proc_by_inode = _inode_process_map()
    port_labels = dict(PORT_LABELS)
    port_labels.update(_dynamic_port_labels())

    rows: list[dict[str, str]] = []
    named = 0
    lan_count = 0
    for line in stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 4:
            continue
        addr = parts[3]
        ss_proc = ""
        if "users:" in line:
            ss_proc = line.split("users:")[-1].strip("() ")
        host, _port = _parse_ss_addr(addr)
        scope = _bind_scope(host if host != "*" else "0.0.0.0")
        if scope == "lan":
            lan_count += 1
        proc = _resolve_process(addr, ss_proc, inodes, proc_by_inode, port_labels)
        if proc:
            named += 1
        rows.append({
            "proto": parts[0].lower(),
            "addr": addr,
            "process": proc,
            "scope": scope,
        })
        if len(rows) >= limit:
            break

    process_hint = (
        "Process names come from ss and /proc when your user can read them. "
        "Some listeners stay blank until you run "
        "<code>sudo ss -tulpn</code> in Security shell."
    )

    return {
        "ok": True,
        "listeners": rows,
        "summary": {
            "total": len(rows),
            "named": named,
            "lan_exposed": lan_count,
            "localhost_only": len(rows) - lan_count,
        },
        "command": ss_cmd,
        "message": "TCP listening sockets on this computer.",
        "hint": process_hint,
    }
