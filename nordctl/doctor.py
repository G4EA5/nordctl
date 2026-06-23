"""System health checks and actionable fix guidance."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
import threading
import time
from typing import Any

from nordctl import nordvpn as nv
from nordctl.config import config_path, load_config


def _run(argv: list[str], timeout: float = 8.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _check(name: str, ok: bool, summary: str, fix: list[str], *, severity: str = "error") -> dict[str, Any]:
    return {
        "id": name,
        "ok": ok,
        "severity": "ok" if ok else severity,
        "summary": summary,
        "fix": fix,
    }


def detect_distro() -> dict[str, str]:
    info = {"id": "unknown", "name": platform.system(), "version": ""}
    try:
        if Path := __import__("pathlib").Path:
            os_release = Path("/etc/os-release")
            if os_release.is_file():
                data: dict[str, str] = {}
                for line in os_release.read_text(encoding="utf-8").splitlines():
                    if "=" in line:
                        k, v = line.split("=", 1)
                        data[k.strip()] = v.strip().strip('"')
                info["id"] = (data.get("ID") or data.get("ID_LIKE") or "unknown").split()[0]
                info["name"] = data.get("PRETTY_NAME") or data.get("NAME") or info["name"]
                info["version"] = data.get("VERSION_ID") or ""
    except OSError:
        pass
    return info


def nordvpn_login_status(bin_path: str) -> tuple[bool, str]:
    if not nv.available(bin_path):
        return False, "NordVPN CLI not installed"
    r = nv.run_cached(bin_path, ["account"], timeout=10)
    out = r.get("output", "")
    if not r.get("ok"):
        return False, out or "Cannot read NordVPN account"
    low = out.lower()
    if "not logged in" in low or "you are not logged" in low:
        return False, "Not logged in to NordVPN"
    if "account" in low or "expires" in low or "subscription" in low:
        return True, out.splitlines()[0] if out else "Logged in"
    return True, "Logged in"


def run_doctor(cfg: dict[str, Any] | None = None, *, force: bool = False) -> dict[str, Any]:
    cfg = cfg or load_config()
    global _DOCTOR_CACHE
    now = time.monotonic()
    cfg_key = str(config_path())
    try:
        cfg_key = f"{cfg_key}:{config_path().stat().st_mtime_ns}"
    except OSError:
        pass
    if not force:
        with _DOCTOR_LOCK:
            hit = _DOCTOR_CACHE
            if hit and hit[0] == cfg_key and now - hit[1] < _DOCTOR_TTL:
                return hit[2]
    payload = _run_doctor_impl(cfg)
    with _DOCTOR_LOCK:
        _DOCTOR_CACHE = (cfg_key, now, payload)
    return payload


_DOCTOR_CACHE: tuple[str, float, dict[str, Any]] | None = None
_DOCTOR_LOCK = threading.Lock()
_DOCTOR_TTL = 45.0


def _run_doctor_impl(cfg: dict[str, Any]) -> dict[str, Any]:
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    from nordctl.config import effective_usage_mode

    tools_only = effective_usage_mode(cfg) == "tools_only"
    checks: list[dict[str, Any]] = []

    py_ok = sys.version_info >= (3, 10)
    checks.append(
        _check(
            "python",
            py_ok,
            f"Python {platform.python_version()}",
            ["Install Python 3.10 or newer from your package manager or python.org"],
            severity="error",
        )
    )

    nord_ok = nv.available(bin_path)
    nord_fix = [
        "Open Setup and click Install NordVPN (official Linux package).",
        "Or run in Terminal: nordctl install-nordvpn",
        "After install: nordvpn login — only needed if you want VPN features.",
    ]
    if tools_only:
        nord_fix = [
            "Optional — only if you want VPN, presets, and Meshnet.",
            "Open top bar Wizard → Install NordVPN, or switch to VPN mode on the welcome screen.",
            "Everything else (network tools, firewall, WiFi doctor) works without NordVPN.",
        ]
    checks.append(
        _check(
            "nordvpn_cli",
            nord_ok,
            "NordVPN CLI found" if nord_ok else ("NordVPN not installed (optional in tools-only mode)" if tools_only else "NordVPN CLI not installed"),
            nord_fix,
            severity="info" if tools_only else "error",
        )
    )

    svc_ok, svc_out = _run(["systemctl", "is-active", "nordvpnd"])
    svc_sev = "info" if tools_only else ("warning" if nord_ok else "error")
    checks.append(
        _check(
            "nordvpnd",
            svc_ok,
            "NordVPN service (nordvpnd) is running" if svc_ok else "NordVPN service not running",
            [
                "sudo systemctl enable --now nordvpnd",
                "If install just finished, reboot once then: sudo systemctl start nordvpnd",
                f"Details: {svc_out}" if svc_out else "",
            ],
            severity=svc_sev,
        )
    )

    logged_in, acct_msg = nordvpn_login_status(bin_path)
    login_sev = "info" if tools_only else ("warning" if nord_ok else "error")
    checks.append(
        _check(
            "nordvpn_login",
            logged_in,
            acct_msg if logged_in else "Not logged in to NordVPN",
            [
                "Open Nord Dashboard → Nord shell and run: nordvpn login",
                "Use your Nord Account email, or login with token from https://my.nordaccount.com/",
                "Verify with: nordvpn account",
            ],
            severity=login_sev,
        )
    )

    nm_ok = shutil.which("nmcli") is not None
    checks.append(
        _check(
            "networkmanager",
            nm_ok,
            "NetworkManager (nmcli) available" if nm_ok else "NetworkManager not found",
            [
                "Install NetworkManager: sudo apt install network-manager   (Debian/Ubuntu)",
                "Smart DNS presets need nmcli to set WiFi DNS",
                "VPN-only presets still work without it",
            ],
            severity="warning",
        )
    )

    resolve_ok = shutil.which("resolvectl") is not None
    checks.append(
        _check(
            "resolved",
            resolve_ok,
            "systemd-resolved (resolvectl) available" if resolve_ok else "resolvectl not found",
            [
                "Usually included with systemd. Install: sudo apt install systemd",
                "Used to verify Smart DNS is active on your WiFi interface",
            ],
            severity="warning",
        )
    )

    wifi = cfg.get("wifi") or {}
    profiles = [p for p in (wifi.get("profiles") or []) if p]
    cfg_ok = bool(profiles)
    checks.append(
        _check(
            "wifi_profiles",
            cfg_ok,
            f"WiFi profiles configured ({len(profiles)})" if cfg_ok else "No WiFi profiles in config",
            [
                "List names: nmcli -t -f NAME connection show",
                f"Edit {config_path()} and set wifi.profiles to your WiFi connection names",
                "Required for TV streaming (Smart DNS) presets",
            ],
            severity="warning",
        )
    )

    connect_ok = bool(cfg.get("connect_country"))
    checks.append(
        _check(
            "connect_country",
            connect_ok,
            f"connect_country: {cfg.get('connect_country')}" if connect_ok else "connect_country not set",
            [
                "Pick your home country below — used for reconnect, streaming, and travel presets.",
                "Advanced users can also edit config.yaml in the Editor tab.",
            ],
            severity="info",
        )
    )

    from nordctl.network_audit import run_network_audit

    audit = run_network_audit()
    for ac in audit.get("checks") or []:
        checks.append(
            _check(
                ac.get("id", "net"),
                ac.get("ok", False),
                ac.get("summary", "Network check"),
                ac.get("fix") or [],
                severity=ac.get("severity", "warning" if not ac.get("ok") else "ok"),
            )
        )

    blocking = [c for c in checks if not c["ok"] and c["severity"] == "error"]
    warnings = [c for c in checks if not c["ok"] and c["severity"] in ("warning", "info")]
    ready = len(blocking) == 0 and nord_ok and logged_in

    from nordctl.privileges import privilege_status

    priv = privilege_status()
    checks.append(
        _check(
            "privileges",
            True,
            "Privileges & sudo",
            priv["notes"] + (
                [priv["manual_sudo_hint"]]
                if priv["sudo_installed"] and not priv.get("ui_privileges_ok") and not priv.get("passwordless_sudo")
                else []
            ),
            severity="info",
        )
    )

    if tools_only:
        setup_required = False
        setup_optional = any(not c["ok"] for c in checks if c["id"] not in ("nordvpn_cli", "nordvpnd", "nordvpn_login"))
    else:
        setup_required = (
            not nord_ok
            or not logged_in
            or (nord_ok and not svc_ok)
            or len(blocking) > 0
        )
        setup_optional = any(
            c["id"] in {"wifi_profiles", "connect_country", "ipv6", "networkmanager", "resolved", "privileges", "resolv_conf", "dns_manager", "connectivity"}
            and not c["ok"]
            for c in checks
        )

    if setup_required:
        setup_level = "required"
    elif setup_optional:
        setup_level = "optional"
    else:
        setup_level = "none"

    return {
        "ok": len(blocking) == 0,
        "ready": ready,
        "setup_level": setup_level,
        "setup_required": setup_required,
        "setup_optional": setup_optional,
        "tools_only": tools_only,
        "nord_installed": nord_ok,
        "logged_in": logged_in,
        "privileges": priv,
        "distro": detect_distro(),
        "checks": checks,
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "help_url": "/help.html",
    }
