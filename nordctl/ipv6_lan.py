"""IPv6 LAN mode — keep local IPv6, reduce internet leak risk."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def _run(argv: list[str], timeout: float = 8.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def ipv6_lan_status() -> dict[str, Any]:
    sysctl_v6 = Path("/proc/sys/net/ipv6/conf/all/disable_ipv6")
    disabled = False
    if sysctl_v6.is_file():
        try:
            disabled = sysctl_v6.read_text(encoding="utf-8").strip() == "1"
        except OSError:
            pass

    ok, routes = _run(["ip", "-6", "route", "show"], timeout=5)
    has_default_v6 = "default" in routes if ok else False
    has_ula = "fd" in routes.lower() or "fe80" in routes.lower() if ok else False

    modes = [
        {
            "id": "full_off",
            "label": "IPv6 fully off",
            "active": disabled,
            "hint": "Strongest leak protection; breaks local IPv6 devices.",
        },
        {
            "id": "lan_only",
            "label": "LAN IPv6 only (recommended)",
            "active": not disabled and has_ula and not has_default_v6,
            "hint": "Keep link-local/ULA; block IPv6 internet default route when VPN on.",
        },
        {
            "id": "on",
            "label": "IPv6 enabled",
            "active": not disabled and has_default_v6,
            "hint": "May bypass VPN if Nord disables IPv6 incompletely.",
        },
    ]

    advice = []
    if disabled:
        advice.append("IPv6 is disabled system-wide — good for privacy, but printers/TVs on IPv6 LAN may break.")
    elif has_default_v6:
        advice.append("Default IPv6 route exists — run Lab leak tests with VPN connected.")
    else:
        advice.append("Local IPv6 without default route — good balance for many home networks.")

    return {
        "ok": True,
        "disabled": disabled,
        "has_default_v6": has_default_v6,
        "has_local_v6": has_ula,
        "modes": modes,
        "advice": advice,
        "manual_disable": "sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1  (nordctl can run if passwordless sudo works)",
    }
