"""Guide and optional install of official NordVPN Linux client."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from nordctl.doctor import detect_distro
from nordctl.privileges import run_privileged, sudo_available


OFFICIAL_URL = "https://nordvpn.com/download/linux/"
DOCS_LOGIN = "https://support.nordvpn.com/hc/en-us/articles/20159875297425-How-to-install-NordVPN-on-Linux-distros"
RELEASE_DEB_URL = (
    "https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn-release/"
    "nordvpn-release_1.0.0_all.deb"
)


def _release_deb_path() -> Path:
    d = Path.home() / ".cache" / "nordctl"
    d.mkdir(parents=True, exist_ok=True)
    return d / "nordvpn-release.deb"


def _run_shell(cmd: str, *, timeout: float = 300) -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["bash", "-lc", cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return {"cmd": cmd, "ok": r.returncode == 0, "output": out}
    except subprocess.TimeoutExpired:
        return {"cmd": cmd, "ok": False, "output": f"Timed out after {timeout:.0f}s"}


def install_shell_script(plan: dict[str, Any] | None = None) -> str:
    """Bash script for the embedded Nord shell (interactive sudo)."""
    plan = plan or install_plan()
    cmds = list(plan.get("commands") or [])
    if not cmds:
        return ""
    lines = [
        "set -e",
        "# NordVPN official apt install — run from nordctl Nord shell",
        "export DEBIAN_FRONTEND=noninteractive",
    ]
    lines.extend(cmds)
    lines.extend(
        [
            'echo ""',
            'echo "✓ NordVPN install finished."',
            'echo "  Next: nordvpn login"',
            'command -v nordvpn >/dev/null && nordvpn --version 2>/dev/null | head -1 || true',
        ]
    )
    return "\n".join(lines) + "\n"


def _sudo_precheck() -> dict[str, Any] | None:
    if not sudo_available():
        return {
            "ok": False,
            "needs_password": True,
            "error": "sudo is not available on this system",
            "fix": [
                "Install sudo or run the apt commands as root",
                "Official guide: " + OFFICIAL_URL,
            ],
        }
    probe = run_privileged(["true"], timeout=5)
    if probe.get("ok"):
        return None
    if probe.get("needs_password"):
        return {
            "ok": False,
            "needs_password": True,
            "use_terminal": True,
            "error": "sudo password required — use the Nord shell below",
            "fix": [
                "Click Install NordVPN again — nordctl opens the Nord shell",
                "Enter your sudo password in the box when prompted",
                "Then run: nordvpn login",
                "Official guide: " + OFFICIAL_URL,
            ],
            "manual": probe.get("manual"),
        }
    return {
        "ok": False,
        "error": probe.get("output") or "sudo check failed",
        "fix": ["Try in Terminal: nordctl install-nordvpn"],
    }


def install_plan(distro_id: str | None = None) -> dict[str, Any]:
    distro = detect_distro()
    did = (distro_id or distro.get("id") or "unknown").lower()
    deb_path = _release_deb_path()

    if did in {"ubuntu", "debian", "linuxmint", "pop"} or "debian" in did:
        apt_plan: dict[str, Any] = {
            "method": "apt",
            "distro": distro.get("name") or did,
            "steps": [
                "Install Nord’s official apt repository (one-time):",
                f"  curl -fsSL {RELEASE_DEB_URL} -o {deb_path}",
                f"  sudo dpkg -i {deb_path}",
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
                f"curl -fsSL {RELEASE_DEB_URL} -o {deb_path}",
                f"sudo dpkg -i {deb_path}",
                "sudo apt update",
                "sudo apt install -y nordvpn",
                "sudo systemctl enable --now nordvpnd",
            ],
            "note": "nordctl does not bundle NordVPN — this uses Nord Security’s official package.",
            "official_url": OFFICIAL_URL,
        }
        apt_plan["shell_script"] = install_shell_script(apt_plan)
        return apt_plan

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


def _run_interactive(cmd: str) -> int:
    return subprocess.call(["bash", "-lc", cmd])


def _attach_terminal_response(payload: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    script = str(plan.get("shell_script") or install_shell_script(plan))
    if script:
        payload["shell_script"] = script
    blocked = _sudo_precheck()
    if blocked and blocked.get("needs_password"):
        payload["use_terminal"] = True
        payload["can_api_install"] = False
    else:
        payload["can_api_install"] = True
    return payload


def run_official_install(*, dry_run: bool = False) -> dict[str, Any]:
    plan = install_plan()
    if shutil.which("nordvpn"):
        return _attach_terminal_response(
            {
                "ok": True,
                "already_installed": True,
                "plan": plan,
                "next_steps": [
                    "Run: nordvpn login",
                    "Then: nordctl doctor",
                ],
            },
            plan,
        )

    if plan.get("method") != "apt" or not plan.get("commands"):
        return {
            "ok": False,
            "dry_run": dry_run,
            "plan": plan,
            "error": "Automatic install is only available for Debian/Ubuntu. Follow the manual steps in the plan.",
        }

    if dry_run:
        return _attach_terminal_response(
            {
                "ok": True,
                "dry_run": True,
                "plan": plan,
                "would_run": plan["commands"],
            },
            plan,
        )

    if not shutil.which("curl"):
        return {"ok": False, "plan": plan, "error": "curl is required. Install: sudo apt install curl"}

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    blocked = None if interactive else _sudo_precheck()
    if blocked:
        blocked["plan"] = plan
        return _attach_terminal_response(blocked, plan)

    logs: list[dict[str, Any]] = []
    for cmd in plan["commands"]:
        if interactive:
            code = _run_interactive(cmd)
            entry = {"cmd": cmd, "ok": code == 0, "output": ""}
            logs.append(entry)
            if code != 0:
                return _attach_terminal_response(
                    {
                        "ok": False,
                        "plan": plan,
                        "logs": logs,
                        "error": f"Command failed: {cmd}",
                        "fix": [
                            "Read the terminal output above for apt/dpkg errors",
                            "Official guide: " + OFFICIAL_URL,
                        ],
                    },
                    plan,
                )
            continue

        if cmd.startswith("sudo "):
            argv = cmd.split()[1:]
            r = run_privileged(argv, timeout=300)
            entry = {
                "cmd": cmd,
                "ok": r.get("ok"),
                "output": r.get("output") or "",
            }
            logs.append(entry)
            if not r.get("ok"):
                err: dict[str, Any] = {
                    "ok": False,
                    "plan": plan,
                    "logs": logs,
                    "needs_password": r.get("needs_password"),
                    "error": f"Command failed: {cmd}",
                    "fix": [
                        "Read the output above for apt/dpkg errors",
                        "Official guide: " + OFFICIAL_URL,
                        "After fixing, run: sudo systemctl enable --now nordvpnd && nordvpn login",
                    ],
                }
                if r.get("needs_password"):
                    err["error"] = "sudo password required — use the Nord shell in the dashboard"
                    err["fix"] = [
                        "Wizard → Install NordVPN opens the Nord shell",
                        "Enter your sudo password when prompted",
                    ]
                if entry["output"]:
                    err["fix"].insert(0, entry["output"].splitlines()[-1][:200])
                return _attach_terminal_response(err, plan)
        else:
            entry = _run_shell(cmd)
            logs.append(entry)
            if not entry["ok"]:
                return _attach_terminal_response(
                    {
                        "ok": False,
                        "plan": plan,
                        "logs": logs,
                        "error": f"Command failed: {cmd}",
                        "fix": [
                            entry.get("output") or "Download or shell command failed",
                            "Official guide: " + OFFICIAL_URL,
                        ],
                    },
                    plan,
                )

    return _attach_terminal_response(
        {
            "ok": True,
            "plan": plan,
            "logs": logs,
            "next_steps": [
                "Run: nordvpn login",
                "Then: nordctl doctor",
                "Configure WiFi names in ~/.config/nordctl/config.yaml",
            ],
        },
        plan,
    )
