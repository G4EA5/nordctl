"""Find a free TCP port for the local web UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import socket
from typing import Iterable

DEFAULT_UI_PORT = 8765
PORT_SCAN_LIMIT = 50


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
