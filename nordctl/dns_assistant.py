"""Pi-hole, Unbound, and Nord DNS conflict assistant."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
from typing import Any


def _run(argv: list[str], timeout: float = 8.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        return r.returncode == 0, ((r.stdout or "") + (r.stderr or "")).strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def dns_assistant_report() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    tips: list[str] = []

    pihole = shutil.which("pihole") is not None
    if pihole:
        ok, out = _run(["pihole", "status"], timeout=6)
        active = ok and "blocking is enabled" in out.lower()
        findings.append({"name": "Pi-hole", "detected": True, "active": active, "detail": out.splitlines()[0] if out else "installed"})
        if active:
            tips.append("Pi-hole + Nord VPN: allowlist LAN DNS (port 53) in Nord split tunnel if local DNS breaks.")
    else:
        findings.append({"name": "Pi-hole", "detected": False, "active": False, "detail": "Not detected"})

    unbound = False
    ok, out = _run(["systemctl", "is-active", "unbound"], timeout=4)
    if ok and out == "active":
        unbound = True
    elif shutil.which("unbound"):
        unbound = True
    findings.append({
        "name": "Unbound",
        "detected": unbound or shutil.which("unbound") is not None,
        "active": unbound,
        "detail": "Recursive DNS resolver — may conflict with Nord firewall on port 53" if unbound else "Not running",
    })
    if unbound:
        tips.append("Unbound through VPN: Nord may block recursive queries — try forwarding mode or allowlist port 53.")

    resolved = False
    ok, out = _run(["systemctl", "is-active", "systemd-resolved"], timeout=4)
    if ok and out == "active":
        resolved = True
    findings.append({
        "name": "systemd-resolved",
        "detected": resolved,
        "active": resolved,
        "detail": "Manages /etc/resolv.conf on many distros",
    })

    ok, listen = _run(["ss", "-lunp"], timeout=5)
    local_dns_port = ":53 " in listen if ok else False
    if local_dns_port:
        tips.append("Something is listening on port 53 locally — Smart DNS and Nord DNS may override it while VPN is on.")

    return {
        "ok": True,
        "findings": findings,
        "tips": tips or ["No local DNS conflicts detected — Nord and Smart DNS should work normally."],
        "actions": [
            {"id": "allowlist_dns", "label": "Allowlist port 53 in Nord", "hint": "nordvpn allowlist add port 53"},
            {"id": "open_lab", "label": "Run leak lab", "hint": "Verify DNS is not leaking"},
        ],
    }
