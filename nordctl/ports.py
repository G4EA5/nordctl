"""Find a free TCP port for the local web UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import socket
import subprocess
from typing import Iterable

DEFAULT_UI_PORT = 8765
PORT_SCAN_LIMIT = 50


def listeners_on_port(port: int) -> list[str]:
    """Process names listening on a TCP port (best effort via ss)."""
    try:
        r = subprocess.run(
            ["ss", "-tlnp", f"sport = :{port}"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    names: list[str] = []
    for line in (r.stdout or "").splitlines():
        names.extend(re.findall(r'"([^"]+)"', line))
    return names


def is_port_held_by_nordctl(port: int) -> bool:
    return any("nordctl" in name for name in listeners_on_port(port))


def is_port_available_for_nordctl(host: str, port: int) -> bool:
    """True if nordctl may use this port (free or already our UI)."""
    if is_port_free(host, port):
        return True
    return is_port_held_by_nordctl(port)


def detect_nordctl_listen() -> tuple[str, int] | None:
    """Return (bind, port) for a running nordctl serve process, if any."""
    try:
        r = subprocess.run(
            ["ss", "-tlnp", "-H"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return None
    for line in (r.stdout or "").splitlines():
        if "nordctl" not in line.lower():
            continue
        m = re.search(r"\s([\d.*]+):(\d+)\s", line)
        if m:
            return m.group(1), int(m.group(2))
    return None


def is_port_free(host: str, port: int) -> bool:
    if port < 1 or port > 65535:
        return False
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.bind((host, port))
        return True
    except OSError:
        return False


def find_free_port(
    host: str,
    start: int = DEFAULT_UI_PORT,
    *,
    limit: int = PORT_SCAN_LIMIT,
) -> int:
    for offset in range(limit):
        port = start + offset
        if is_port_free(host, port):
            return port
    raise OSError(f"no free port found on {host} in range {start}-{start + limit - 1}")


def port_status(host: str, port: int) -> dict[str, object]:
    """Summarize whether a TCP port can be used and what holds it (best effort)."""
    holders = listeners_on_port(port)
    nordctl = is_port_held_by_nordctl(port)
    free = is_port_free(host, port)
    return {
        "port": int(port),
        "host": host,
        "free": free,
        "holders": holders,
        "nordctl": nordctl,
        "available_for_nordctl": is_port_available_for_nordctl(host, port),
    }


def resolve_listen_port(
    host: str,
    preferred: int,
    *,
    explicit: bool = False,
    scan_limit: int = PORT_SCAN_LIMIT,
) -> tuple[int, int | None]:
    """Return (port, replaced_port_or_none). replaced is set when we picked a fallback."""
    preferred = int(preferred or DEFAULT_UI_PORT)
    if explicit:
        if not is_port_free(host, preferred):
            raise OSError(f"port {preferred} on {host} is already in use")
        return preferred, None
    if is_port_free(host, preferred):
        return preferred, None
    free = find_free_port(host, preferred + 1, limit=scan_limit)
    return free, preferred
