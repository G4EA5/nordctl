"""Tested platform matrix for GitHub documentation and API."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl import nordvpn as nv
from nordctl.config import load_config
from nordctl.doctor import run_doctor


MATRIX: list[dict[str, Any]] = [
    {
        "distro": "Ubuntu",
        "versions": ["22.04 LTS", "24.04 LTS"],
        "status": "tested",
        "notes": "NetworkManager + official NordVPN .deb",
    },
    {
        "distro": "Debian",
        "versions": ["12", "13"],
        "status": "tested",
        "notes": "Same NordVPN package as Ubuntu",
    },
    {
        "distro": "Linux Mint",
        "versions": ["21.x", "22.x"],
        "status": "compatible",
        "notes": "Ubuntu-based; use Ubuntu NordVPN package",
    },
    {
        "distro": "Fedora",
        "versions": ["39", "40+"],
        "status": "compatible",
        "notes": "NordVPN RPM; nmcli required for Smart DNS presets",
    },
    {
        "distro": "Arch Linux",
        "versions": ["rolling"],
        "status": "community",
        "notes": "Install nordvpn-bin or official package from AUR; not CI-tested",
    },
]

NORDVPN_CLI_RANGE = {
    "minimum": "3.15.0",
    "recommended": "3.18.0+",
    "notes": "Use `nordvpn version` — preset steps map to current CLI subcommands.",
}


def compatibility_matrix(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    doctor = run_doctor(cfg)
    nord_version = None
    if nv.available(bin_path):
        r = nv.run(bin_path, ["version"], timeout=8)
        nord_version = (r.get("output") or "").strip().splitlines()[0] if r.get("output") else None

    return {
        "ok": True,
        "platforms": MATRIX,
        "requirements": {
            "python": ">=3.10",
            "network_manager": "nmcli + resolvectl for Smart DNS presets",
            "nordvpn_cli": NORDVPN_CLI_RANGE,
        },
        "this_system": {
            "distro": doctor.get("distro"),
            "ready": doctor.get("ready"),
            "nordvpn_version": nord_version,
            "nordvpn_installed": nv.available(bin_path),
        },
        "docs": "See docs/COMPATIBILITY.md in the repository.",
    }
