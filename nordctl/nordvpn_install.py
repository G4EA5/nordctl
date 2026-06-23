"""Guide and optional install of official NordVPN Linux client."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
from typing import Any

from nordctl.doctor import detect_distro


OFFICIAL_URL = "https://nordvpn.com/download/linux/"
DOCS_LOGIN = "https://support.nordvpn.com/hc/en-us/articles/20159875297425-How-to-install-NordVPN-on-Linux-distros"


def install_plan(distro_id: str | None = None) -> dict[str, Any]:
    distro = detect_distro()
    did = (distro_id or distro.get("id") or "unknown").lower()

    if did in {"ubuntu", "debian", "linuxmint", "pop"} or "debian" in did:
        return {
            "method": "apt",
            "distro": distro.get("name") or did,
            "steps": [
                "Install Nord’s official apt repository (one-time):",
                "  curl -fsSL https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn-release/nordvpn-release_1.0.0_all.deb -o /tmp/nordvpn-release.deb",
                "  sudo dpkg -i /tmp/nordvpn-release.deb",
                "  sudo apt update",
                "  sudo apt install -y nordvpn",
                "Enable and start the service:",
                "  sudo systemctl enable --now nordvpnd",
                "Log in (required once):",
                "  nordvpn login",
                "Verify:",
                "  nordvpn account && nordvpn status",
            ],
            "commands": [
                "curl -fsSL https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn-release/nordvpn-release_1.0.0_all.deb -o /tmp/nordvpn-release.deb",
                "sudo dpkg -i /tmp/nordvpn-release.deb",
                "sudo apt update",
                "sudo apt install -y nordvpn",
                "sudo systemctl enable --now nordvpnd",
            ],
            "note": "nordctl does not bundle NordVPN — this uses Nord Security’s official package.",
            "official_url": OFFICIAL_URL,
        }

    if did in {"fedora", "rhel", "centos", "rocky", "almalinux"} or "rhel" in did or "fedora" in did:
        return {
            "method": "dnf",
            "distro": distro.get("name") or did,
            "steps": [
                "Install Nord’s official yum/dnf repository:",
                "  sudo mkdir -p /etc/yum.repos.d/",
                "  See current commands at: " + OFFICIAL_URL,
                "  sudo dnf install -y nordvpn",
                "  sudo systemctl enable --now nordvpnd",
                "  nordvpn login",
            ],
            "commands": [],
            "note": "Fedora/RHEL steps change occasionally — open the official page if commands fail.",
            "official_url": OFFICIAL_URL,
        }

    if did in {"arch", "manjaro"}:
        return {
            "method": "manual",
            "distro": distro.get("name") or did,
            "steps": [
                "Arch-based: use AUR package nordvpn-bin OR follow Nord’s generic Linux instructions:",
                "  " + OFFICIAL_URL,
                "After install: sudo systemctl enable --now nordvpnd && nordvpn login",
            ],
            "commands": [],
            "official_url": OFFICIAL_URL,
        }

    return {
        "method": "manual",
        "distro": distro.get("name") or did,
        "steps": [
            "Open NordVPN’s official Linux install page and follow steps for your distribution:",
            "  " + OFFICIAL_URL,
            "After installing, run in a terminal:",
            "  sudo systemctl enable --now nordvpnd",
            "  nordvpn login",
            "  nordvpn status",
        ],
        "commands": [],
        "official_url": OFFICIAL_URL,
    }


def run_official_install(*, dry_run: bool = False) -> dict[str, Any]:
    plan = install_plan()
    if plan.get("method") != "apt" or not plan.get("commands"):
        return {
            "ok": False,
            "dry_run": dry_run,
            "plan": plan,
            "error": "Automatic install is only available for Debian/Ubuntu. Follow the manual steps in the plan.",
        }

    if dry_run:
        return {"ok": True, "dry_run": True, "plan": plan, "would_run": plan["commands"]}

    if not shutil.which("curl"):
        return {"ok": False, "plan": plan, "error": "curl is required. Install: sudo apt install curl"}

    if not shutil.which("sudo"):
        return {"ok": False, "plan": plan, "error": "sudo is required to install NordVPN system packages"}

    logs: list[dict[str, Any]] = []
    for cmd in plan["commands"]:
        try:
            r = subprocess.run(
                ["bash", "-lc", cmd],
                capture_output=True,
                text=True,
                timeout=300,
            )
            logs.append({"cmd": cmd, "ok": r.returncode == 0, "output": (r.stdout or "") + (r.stderr or "")})
            if r.returncode != 0:
                return {
                    "ok": False,
                    "plan": plan,
                    "logs": logs,
                    "error": f"Command failed: {cmd}",
                    "fix": [
                        "Read the output above for apt/dpkg errors",
                        "Try running the commands manually from: nordctl install-nordvpn",
                        "Official guide: " + OFFICIAL_URL,
                        "After fixing, run: sudo systemctl enable --now nordvpnd && nordvpn login",
                    ],
                }
        except subprocess.TimeoutExpired:
            return {"ok": False, "plan": plan, "logs": logs, "error": f"Timed out: {cmd}"}

    return {
        "ok": True,
        "plan": plan,
        "logs": logs,
        "next_steps": [
            "Run: nordvpn login",
            "Then: nordctl doctor",
            "Configure WiFi names in ~/.config/nordctl/config.yaml",
        ],
    }
