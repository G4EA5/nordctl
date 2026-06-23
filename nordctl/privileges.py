"""Detect sudo availability and which actions need elevated privileges."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from nordctl.paths import (
    PRIV_SUDOERS_SCRIPT,
    install_script_sudo_cmd,
    install_scripts_map,
    is_readable_file,
)

NORDCTL_PRIV_SUDOERS = Path("/etc/sudoers.d/nordctl-privileges")
NORDCTL_UFW_SUDOERS = Path("/etc/sudoers.d/nordctl-ufw")

# Commands nordctl may run with sudo (read-only checks use the same paths).
SUDO_COMMANDS = (
    "/usr/bin/chattr",
    "/sbin/chattr",
    "/usr/sbin/sysctl",
    "/sbin/sysctl",
    "/usr/bin/sysctl",
)


def _run(argv: list[str], timeout: float = 6.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _sudo_needs_password(out: str) -> bool:
    low = out.lower()
    return any(
        phrase in low
        for phrase in (
            "a password is required",
            "password for",
            "interactive authentication is required",
            "sorry, try again",
        )
    )


def _sudo_n(argv: list[str], timeout: float = 6.0) -> tuple[bool, str]:
    return _run(["sudo", "-n", *argv], timeout=timeout)


def passwordless_sudo() -> bool:
    """True if `sudo -n true` works (full passwordless sudo — rare)."""
    if not shutil.which("sudo"):
        return False
    ok, _ = _run(["sudo", "-n", "true"])
    return ok


def sudo_available() -> bool:
    return shutil.which("sudo") is not None


def in_nordvpn_group() -> bool:
    try:
        import grp

        g = grp.getgrnam("nordvpn")
        user = os.environ.get("USER") or os.environ.get("LOGNAME") or ""
        if user and user in g.gr_mem:
            return True
        for gid in os.getgroups():
            if grp.getgrgid(gid).gr_name == "nordvpn":
                return True
    except (KeyError, OSError):
        pass
    return False


def nordctl_ui_privileges() -> dict[str, Any]:
    """Detect passwordless sudo for nordctl-specific commands (not `sudo -n true`)."""
    text = ""
    if is_readable_file(NORDCTL_PRIV_SUDOERS):
        try:
            text = NORDCTL_PRIV_SUDOERS.read_text(encoding="utf-8", errors="replace")
        except OSError:
            text = ""

    ufw_bin = shutil.which("ufw") or "/usr/sbin/ufw"
    ufw_ok = False
    if shutil.which("ufw") or Path(ufw_bin).is_file():
        ok, err = _sudo_n([ufw_bin, "status", "numbered"])
        ufw_ok = ok or ("status:" in err.lower() and not _sudo_needs_password(err))

    sysctl_bin = shutil.which("sysctl") or "/usr/sbin/sysctl"
    ipv6_rules = (
        "net.ipv6.conf.all.disable_ipv6=1",
        "net.ipv6.conf.default.disable_ipv6=1",
        "net.ipv6.conf.lo.disable_ipv6=1",
    )
    ipv6_in_file = all(rule in text for rule in ipv6_rules) if text else False
    ipv6_ok = False
    if ipv6_in_file and (shutil.which("sysctl") or Path(sysctl_bin).is_file()):
        ok, err = _sudo_n([sysctl_bin, "-w", "net.ipv6.conf.lo.disable_ipv6=1"])
        ipv6_ok = ok or (not _sudo_needs_password(err) and "=" in err)

    chattr_in_file = "chattr" in text and "resolv.conf" in text
    chattr_bin = shutil.which("chattr") or "/usr/bin/chattr"
    chattr_ok = False
    if chattr_in_file and (shutil.which("chattr") or Path(chattr_bin).is_file()):
        ok, err = _sudo_n([chattr_bin, "-i", "/etc/resolv.conf"])
        chattr_ok = ok or not _sudo_needs_password(err)

    sudoers_installed = is_readable_file(NORDCTL_PRIV_SUDOERS) or is_readable_file(NORDCTL_UFW_SUDOERS)
    ui_ok = ufw_ok or ipv6_ok or chattr_ok

    return {
        "sudoers_installed": sudoers_installed,
        "privileges_sudoers": str(NORDCTL_PRIV_SUDOERS) if is_readable_file(NORDCTL_PRIV_SUDOERS) else None,
        "ufw_passwordless": ufw_ok,
        "ipv6_passwordless": ipv6_ok,
        "ipv6_rules_installed": ipv6_in_file,
        "resolv_passwordless": chattr_ok,
        "resolv_rules_installed": chattr_in_file,
        "ui_fixes_ok": ui_ok and sudoers_installed,
        "ui_fixes_full": ufw_ok and ipv6_ok and chattr_ok,
    }


def ui_privileges_ok() -> bool:
    return bool(nordctl_ui_privileges().get("ui_fixes_ok"))


def privilege_status() -> dict[str, Any]:
    pwless = passwordless_sudo()
    has_sudo = sudo_available()
    nord_grp = in_nordvpn_group()
    nord = nordctl_ui_privileges()
    ui_ok = bool(nord.get("ui_fixes_ok"))

    notes: list[str] = []
    if not has_sudo:
        notes.append(
            "sudo is not installed — some fixes (IPv6 disable, resolv.conf immutable) must be run manually in a terminal."
        )
    elif pwless:
        notes.append(
            "Full passwordless sudo works — nordctl and apt one-click installs can run without a password."
        )
    elif ui_ok:
        priv_cmd = install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT)
        notes.append(
            "Nordctl UI fixes work without a password — UFW status/manage, IPv6 disable, and resolv.conf chattr "
            f"(from {priv_cmd}). Full passwordless sudo is not required."
        )
        if not nord.get("ui_fixes_full"):
            missing = []
            if nord.get("ipv6_rules_installed") and not nord.get("ipv6_passwordless"):
                missing.append("IPv6 sysctl")
            if nord.get("resolv_rules_installed") and not nord.get("resolv_passwordless"):
                missing.append("resolv chattr")
            if not nord.get("ufw_passwordless"):
                missing.append("UFW")
            if missing:
                notes.append(
                    "Some rules still need a fresh login session: "
                    + ", ".join(missing)
                    + " — log out/in or run: newgrp sudo"
                )
    elif nord.get("sudoers_installed"):
        notes.append(
            "Sudoers file is installed but passwordless commands failed in this session. "
            "Log out and back in, or run: newgrp sudo — then click Refresh below."
        )
    else:
        priv_cmd = install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT)
        notes.append(
            f"Run {priv_cmd} once so the UI can manage UFW, IPv6, and resolv.conf without your password. "
            "The web UI cannot type your sudo password interactively."
        )

    if nord_grp:
        notes.append("You are in the nordvpn group — most nordvpn CLI commands work without sudo.")
    else:
        notes.append(
            "Add yourself to the nordvpn group for CLI access: sudo usermod -aG nordvpn $USER then log out/in."
        )

    return {
        "sudo_installed": has_sudo,
        "passwordless_sudo": pwless,
        "ui_privileges_ok": ui_ok,
        "nordctl_privileges": nord,
        "nordvpn_group": nord_grp,
        "notes": notes,
        "manual_sudo_hint": (
            "One-time setup (run as your user, not root shell): "
            + install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT)
        ),
        "install_scripts": install_scripts_map(),
        "actions": {
            "nordvpn_cli": {"needs_sudo": False, "note": "VPN connect/disconnect/settings — no sudo if in nordvpn group"},
            "smart_dns_nmcli": {
                "needs_sudo": "maybe",
                "note": "User-owned WiFi profiles: no sudo. System-wide NM connections may need sudo nmcli.",
            },
            "disable_ipv6": {
                "needs_sudo": True,
                "note": f"sysctl — works from the UI after {install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT)}",
            },
            "fix_resolv_immutable": {
                "needs_sudo": True,
                "note": f"chattr -i /etc/resolv.conf — works from the UI after {install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT)}",
            },
            "install_nordvpn": {"needs_sudo": True, "note": "Official apt install — run in terminal with password"},
        },
    }


def run_privileged(argv: list[str], timeout: float = 15.0) -> dict[str, Any]:
    """Run command via sudo -n; fail clearly if a password would be required."""
    if not sudo_available():
        return {
            "ok": False,
            "output": "sudo not available",
            "needs_password": True,
            "command": " ".join(argv),
        }
    cmd = ["sudo", "-n", *argv]
    ok, out = _run(cmd, timeout=timeout)
    needs_password = not ok and _sudo_needs_password(out)
    return {
        "ok": ok,
        "output": out,
        "needs_password": needs_password,
        "command": " ".join(cmd),
        "manual": f"Run in terminal: sudo {' '.join(argv)}",
    }
