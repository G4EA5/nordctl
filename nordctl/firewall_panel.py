"""UFW + NordVPN firewall/DNS status and guidance."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import shutil
import subprocess
from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv


def _run(argv: list[str], timeout: float = 8.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False, ""


def _enabled(value: str | None) -> bool:
    return "enabled" in str(value or "").lower()


def _dns_setting_on(value: str | None) -> bool:
    """True when NordVPN uses Nord DNS (automatic/disabled or Nord server IPs)."""
    return nv.nord_dns_active(value)


def ufw_state() -> dict[str, Any]:
    if not shutil.which("ufw"):
        return {
            "installed": False,
            "active": False,
            "status": "not installed",
            "default_incoming": None,
            "default_outgoing": None,
            "rules_count": 0,
            "summary": "UFW not installed",
        }
    ok, out = False, ""
    for argv in (["ufw", "status", "verbose"], ["sudo", "-n", "ufw", "status", "verbose"]):
        if argv[0] == "sudo" and not shutil.which("sudo"):
            continue
        ok, out = _run(argv, timeout=8)
        if ok and "Status:" in out:
            break
    active = "status: active" in out.lower()
    incoming = outgoing = None
    rules = 0
    for line in out.splitlines():
        s = line.strip()
        if s.startswith("Default:"):
            if "deny (incoming)" in s:
                incoming = "deny"
            elif "allow (incoming)" in s:
                incoming = "allow"
            if "allow (outgoing)" in s:
                outgoing = "allow"
            elif "deny (outgoing)" in s:
                outgoing = "deny"
        if s and s[0].isdigit() and "ALLOW" in s.upper():
            rules += 1
    status = "active" if active else ("inactive" if ok else "unknown")
    summary = f"UFW {status}"
    if active and rules:
        summary += f" · {rules} rule(s)"
    return {
        "installed": True,
        "active": active,
        "status": status,
        "default_incoming": incoming,
        "default_outgoing": outgoing,
        "rules_count": rules,
        "raw_head": out.splitlines()[:12],
        "summary": summary,
    }


def nord_security(settings: dict[str, Any]) -> dict[str, Any]:
    firewall = _enabled(settings.get("Firewall"))
    killswitch = _enabled(settings.get("Kill Switch"))
    nord_dns = _dns_setting_on(settings.get("DNS"))
    return {
        "firewall": firewall,
        "killswitch": killswitch,
        "nord_dns": nord_dns,
        "firewall_mark": settings.get("Firewall Mark") or settings.get("Firewall Mark:"),
        "summary": ", ".join(
            x
            for x in (
                f"Nord firewall {'on' if firewall else 'off'}",
                f"kill switch {'on' if killswitch else 'off'}",
                f"Nord DNS {'on' if nord_dns else 'off'}",
            )
        ),
    }


def compatibility_notes(nord: dict[str, Any], ufw: dict[str, Any], connected: bool) -> list[str]:
    notes: list[str] = []
    if not ufw.get("installed"):
        notes.append(
            "UFW is not installed — NordVPN firewall and kill switch manage traffic via their own iptables/nftables rules."
        )
        return notes

    if ufw.get("active") and nord.get("firewall"):
        notes.append(
            "Both UFW and NordVPN firewall are active. They both insert packet filter rules — "
            "local services, LAN discovery, or Meshnet may be blocked unless allowlisted in both places."
        )
    elif ufw.get("active") and nord.get("killswitch"):
        notes.append(
            "UFW is active with Nord kill switch. Unexpected blocks often mean overlapping DROP rules — "
            "check Nord allowlist (split tunnel) and UFW outbound policy."
        )
    elif ufw.get("active") and connected and not nord.get("firewall"):
        notes.append(
            "UFW is active but NordVPN firewall is off — UFW handles host filtering; "
            "traffic still routes through the VPN tunnel when connected."
        )
    elif ufw.get("active") and not connected:
        notes.append(
            "UFW is your system firewall. NordVPN firewall/kill switch only apply when the Nord daemon manages rules."
        )
    else:
        notes.append(
            "UFW is installed but inactive — NordVPN can manage its own firewall rules without conflicting with UFW."
        )

    notes.append(
        "Use Control → UFW editor to add or remove host firewall rules (needs one-time sudo setup). "
        "Nord presets (firewall-on, killswitch-on) change NordVPN rules only."
    )
    return notes


def dns_overview(
    cfg: dict[str, Any],
    settings: dict[str, Any],
    *,
    connected: bool,
    wifi_dns: list[str],
    smart_active: bool,
) -> dict[str, Any]:
    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    custom = list(cfg.get("custom_dns") or [])
    nord_dns = _dns_setting_on(settings.get("DNS"))

    if connected and nord_dns:
        mode = "vpn_nord_dns"
        mode_label = "Nord DNS on (via VPN tunnel)"
    elif smart_active:
        mode = "smart_dns_wifi"
        mode_label = "Smart DNS active on WiFi"
    elif connected:
        mode = "vpn_other"
        mode_label = "Nord DNS off (VPN tunnel still active)"
    else:
        mode = "auto"
        mode_label = "Automatic / ISP DNS"

    resolve_snippet = ""
    wifi = cfg.get("wifi") or {}
    device = net.detect_wifi_device(wifi.get("device"))
    if device:
        ok, out = _run(["resolvectl", "status", device], timeout=5)
        if ok:
            resolve_snippet = "\n".join(out.splitlines()[:14])

    return {
        "mode": mode,
        "mode_label": mode_label,
        "wifi_dns": wifi_dns,
        "primary": primary,
        "secondary": secondary,
        "custom_dns": custom,
        "nord_dns_enabled": nord_dns,
        "smart_active": smart_active,
        "resolve_snippet": resolve_snippet,
        "wifi_device": device,
        "profiles": list((cfg.get("wifi") or {}).get("profiles") or []),
    }


def firewall_overview(
    cfg: dict[str, Any],
    settings: dict[str, Any],
    *,
    connected: bool,
    wifi_dns: list[str],
    smart_active: bool,
) -> dict[str, Any]:
    ufw = ufw_state()
    nord = nord_security(settings)
    return {
        "ufw": ufw,
        "nord": nord,
        "connected": connected,
        "notes": compatibility_notes(nord, ufw, connected),
        "scopes": {
            "nord": {
                "label": "NordVPN daemon",
                "summary": nord.get("summary") or "",
                "controls": ["firewall", "killswitch", "nord_dns"],
            },
            "host": {
                "label": "System firewall (UFW)",
                "summary": ufw.get("summary") or "",
                "controls": ["ufw_rules", "ufw_defaults"],
            },
            "network": {
                "label": "WiFi / ISP DNS",
                "summary": "Smart DNS and resolver settings on NetworkManager profiles",
                "controls": ["smart_dns", "custom_dns", "resolvectl"],
            },
        },
        "dns": dns_overview(
            cfg,
            settings,
            connected=connected,
            wifi_dns=wifi_dns,
            smart_active=smart_active,
        ),
    }
