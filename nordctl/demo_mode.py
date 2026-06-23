"""Demo / mock mode — explore the UI without NordVPN or network changes."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
from typing import Any

from nordctl.actions import describe_step
from nordctl.config import load_config
from nordctl.ui_prefs import ui_prefs_from_config, save_config
from nordctl.presets import get_preset, load_presets, preset_region

# RFC 5737 documentation addresses only — never real client IPs
_DEMO_VPN_IP = "203.0.113.45"
_DEMO_PUBLIC_IP = "198.51.100.10"
_DEMO_MESH_IP = "100.64.0.7"
_DEMO_PEER_IP = "100.64.0.8"
_DEMO_COUNTRY = "United Kingdom"
_DEMO_CITY = "London"
_DEMO_WIFI = ["ExampleWiFi-5G", "ExampleWiFi"]


def is_demo_mode(cfg: dict[str, Any] | None = None) -> bool:
    if os.environ.get("NORDCTL_DEMO", "").strip().lower() in ("1", "true", "yes", "on"):
        return True
    cfg = cfg or load_config()
    return bool((cfg.get("server") or {}).get("demo_mode"))


def set_demo_mode(enabled: bool, *, persist: bool = False, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    srv = cfg.setdefault("server", {})
    srv["demo_mode"] = bool(enabled)
    if persist:
        save_config(cfg)
    return {"ok": True, "demo_mode": bool(enabled), "persisted": persist}


def _demo_presets(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    out = []
    for p in load_presets(cfg):
        out.append({
            "id": p.get("id"),
            "label": p.get("label"),
            "summary": p.get("summary"),
            "category": p.get("category") or "General",
            "region": preset_region(p),
            "requires": p.get("requires") or [],
            "user": bool(p.get("user")),
            "community": bool(p.get("community")),
        })
    return out


def build_demo_state_quick(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    return {
        "ok": True,
        "quick": True,
        "demo_mode": True,
        "available": True,
        "nordvpn_available": True,
        "nordvpn": {"installed": True, "logged_in": True, "connected": True},
        "status": {
            "connected": True,
            "Country": _DEMO_COUNTRY,
            "City": _DEMO_CITY,
            "IP": _DEMO_VPN_IP,
            "Server": f"{_DEMO_COUNTRY} #842",
            "Technology": "NORDLYNX",
        },
        "settings": {
            "Technology": "NORDLYNX",
            "Protocol": "UDP",
            "Kill Switch": "disabled",
            "Firewall": "disabled",
            "DNS": "103.86.96.103",
            "Meshnet": "enabled",
        },
        "presets": _demo_presets(cfg),
        "usage": {
            "ok": True,
            "mode": "vpn",
            "effective": "vpn",
            "install_profile": "nord",
            "tools_only": False,
            "vpn_expected": True,
            "nord_installed": True,
            "logged_in": True,
            "vpn_ready": True,
            "demo_mode": True,
            "label": "Demo mode",
            "hint": "Simulated data only — no VPN or DNS changes are applied.",
        },
        "countries": ["United Kingdom", "United States", "Germany", "Netherlands"],
        "ip_info": {
            "ok": True,
            "public_ipv4": _DEMO_VPN_IP,
            "vpn_ipv4": _DEMO_VPN_IP,
            "chain": [
                {"label": "Public IP", "value": _DEMO_PUBLIC_IP},
                {"label": "VPN", "value": f"{_DEMO_COUNTRY} · {_DEMO_CITY}"},
            ],
        },
        "smart_dns": {
            "active": False,
            "dns_servers": ["103.86.96.103", "103.86.99.103"],
            "system_dns": {"servers": ["192.168.1.1"], "device": "wlan0", "source": "wlan0"},
            "public_ip": _DEMO_PUBLIC_IP,
            "wifi_device": "wlan0",
            "profiles": list(_DEMO_WIFI),
        },
        "ui_prefs": ui_prefs_from_config(cfg),
    }


def build_demo_state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl.config import config_path
    from nordctl.features import features_payload
    from nordctl.ui_auth import ui_auth_status

    quick = build_demo_state_quick(cfg)
    return {
        **quick,
        "demo_mode": True,
        "config_path": str(config_path()),
        "connect_country": _DEMO_COUNTRY,
        "mesh_ip": _DEMO_MESH_IP,
        "mesh": {
            "enabled": True,
            "peers": [{"hostname": "demo-peer.example", "status": "connected", "ip": _DEMO_PEER_IP}],
        },
        "mesh_peers_raw": "demo-peer.example · connected",
        "firewall": {"nord": {"firewall": False, "killswitch": False}, "dns": {}, "notes": []},
        "doctor": {
            "ok": True,
            "ready": True,
            "demo_mode": True,
            "distro": {"name": "Demo Linux"},
            "checks": [{"ok": True, "summary": "Demo mode — no system checks run"}],
        },
        "profiles": [],
        "zones": {"ssid": "ExampleWiFi", "trusted": False, "preset": None},
        "schedules": [],
        "snapshots": [],
        "baseline": {"exists": True, "created": "demo", "message": "Demo baseline (not real)"},
        "locations": {"ok": True, "fields": []},
        "ui_auth": ui_auth_status(cfg),
        "features": features_payload(cfg),
        "hidden_presets": [],
        "services": {"ui_running": True, "demo_mode": True},
        "privileges": {"ui_privileges_ok": True, "demo_mode": True},
    }


def simulate_preset_apply(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"unknown preset: {preset_id}", "demo_mode": True}

    steps_out: list[dict[str, Any]] = []
    for step in preset.get("steps") or []:
        steps_out.append({
            "ok": True,
            "simulated": True,
            "output": describe_step(step, cfg),
            "args": [str(step.get("action") or "step")],
        })

    from nordctl.preset_verify import verify_after_preset

    return {
        "ok": True,
        "demo_mode": True,
        "simulated": True,
        "preset": preset_id,
        "label": preset.get("label"),
        "category": preset.get("category"),
        "steps": steps_out,
        "note": "Demo mode — preset was not applied. Run without demo to change real settings.",
        "verification": verify_after_preset(cfg, preset_id, demo=True),
        "state": build_demo_state(cfg),
    }
