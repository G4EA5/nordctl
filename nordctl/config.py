"""Load and merge user configuration."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
from copy import deepcopy
from pathlib import Path
from typing import Any

import yaml

from nordctl.ports import DEFAULT_UI_PORT, find_free_port, is_port_free

DEFAULTS: dict[str, Any] = {
    "nordvpn_bin": "nordvpn",
    "connect_country": None,
    "travel_country": None,
    "gaming_country": None,
    "work_country": None,
    "connect_server": None,
    "connect_city": None,
    "mesh_peer": None,
    "custom_dns": [],
    "allowlist_subnets": [],
    "smart_dns": {
        "primary": "103.86.96.103",
        "secondary": "103.86.99.103",
    },
    "wifi": {
        "device": None,
        "profiles": [],
        "auto_sync_active": True,
        "heal_smart_dns": True,
    },
    "lan_allowlist_cidr": "192.168.0.0/16",
    "voip_ports": [80, 443, 4244, 5242, 5243, 7985],
    "public_ip_check_url": "https://ifconfig.me/ip",
    "server": {
        "bind": "127.0.0.1",
        "access_mode": "local",
        "port": 8765,
        "ui_password_hash": None,
        "ui_password_salt": None,
        "ui_password_exempt_local": True,
        "demo_mode": False,
        "headless": False,
    },
    "presets_dir": None,
    "active_profile": "default",
    "config_profiles": {
        "default": {},
        "streaming": {"connect_country": None},
        "travel": {"travel_country": None},
    },
    "favorites": {"countries": [], "servers": []},
    "custom_places": [],
    "ui": {
        "page_guides_visible_default": True,
        "page_intro_visible": True,
        "clock_format": "24h",
        "nord_doctor_hidden": [],
        "hidden_places": [],
        "place_overrides": {},
        "hidden_presets": [],
        "preset_overrides": {},
    },
    "wifi_zones": {
        "auto_apply": False,
        "watch_enabled": False,
        "watch_interval": 30,
        "trusted": [],
        "untrusted_preset": "public-wifi",
        "home_ip_learn": True,
        "home_ip_when_trusted": True,
    },
    "schedules": [],
    "auto_snapshot_before_preset": True,
    "tray": {
        "enabled": False,
        "autostart": False,
    },
    "service": {
        "autostart": False,
    },
    "optional_tools": {
        "custom": [],
        "package_categories": [
            {"id": "miscellaneous", "label": "Miscellaneous"},
        ],
    },
    "security": {
        "disconnect_alerts": True,
        "watch_interval": 30,
        "status_page": {
            "enabled": False,
            "token": None,
        },
        "location_profiles": {},
        "preset_scenarios": {},
        "hidden_preset_scenarios": [],
        "custom_scenarios": [],
        "hidden_scenarios": [],
    },
    "features": {
        "onboarding_complete": False,
        "legal_accepted": False,
        "modules": {},
    },
    "usage_mode": "auto",
    # nord | network | full — set at onboarding; drives help and optional UI panels
    "install_profile": "auto",
    "alerts": {
        "browser_enabled": True,
        "watch_enabled": True,
        "watch_interval": 60,
        "rate_limit_minutes": 15,
        "health_threshold": 50,
        "email": {
            "enabled": False,
            "to": None,
            "from": None,
            "smtp_host": None,
            "smtp_port": 587,
            "smtp_user": None,
            "smtp_password": None,
            "use_tls": True,
        },
        "webhook": {
            "enabled": False,
            "url": None,
        },
        "rules": {
            "vpn_disconnect": True,
            "smart_dns_drift": True,
            "health_score_low": True,
            "wifi_untrusted": False,
            "test": True,
        },
        "scan_email": {
            "enabled": True,
            "email_on_findings": True,
            "email_on_failure": True,
            "email_always": False,
            "lynis_min_score_alert": 65,
        },
    },
    "home_ip_fallback": {
        "enabled": False,
        "ip": "",
    },
    "speedtest": {
        "default_provider": "auto",
        "default_profile": "standard",
        "default_method": "single",
        "warmup": False,
        "save_results": True,
        "custom_mirrors": [],
    },
    "terminal": {
        "quick_commands": {
            "network": None,
            "security": None,
            "nord": None,
            "custom_categories": [],
        },
    },
}


def config_dir() -> Path:
    env = os.environ.get("NORDCTL_CONFIG_DIR")
    if env:
        return Path(env).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "nordctl"


def config_path() -> Path:
    env = os.environ.get("NORDCTL_CONFIG")
    if env:
        return Path(env).expanduser()
    return config_dir() / "config.yaml"


def bundled_presets_dir() -> Path:
    for candidate in (
        Path("/usr/share/nordctl/presets"),
        Path(__file__).resolve().parent.parent / "presets",
    ):
        if candidate.is_dir():
            return candidate
    return Path(__file__).resolve().parent.parent / "presets"


def load_config() -> dict[str, Any]:
    cfg = deepcopy(DEFAULTS)
    path = config_path()
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            user = yaml.safe_load(fh) or {}
        _deep_merge(cfg, user)
        from nordctl.ui_auth import migrate_legacy_password_keys

        if migrate_legacy_password_keys(cfg):
            save_config(cfg)
    return cfg


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, val in override.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def presets_directory(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    custom = cfg.get("presets_dir")
    if custom:
        return Path(str(custom)).expanduser()
    return bundled_presets_dir()


def save_config(cfg: dict[str, Any]) -> None:
    dest = config_path()
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(cfg, sort_keys=False), encoding="utf-8")


def effective_usage_mode(cfg: dict[str, Any] | None = None) -> str:
    """auto → tools_only when Nord CLI missing; explicit vpn | tools_only respected."""
    cfg = cfg or load_config()
    mode = str(cfg.get("usage_mode") or "auto").strip().lower()
    if mode in ("tools_only", "vpn"):
        return mode
    from nordctl import nordvpn as nv

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return "tools_only"
    return "vpn"


def usage_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl import nordvpn as nv
    from nordctl.doctor import nordvpn_login_status

    mode = str(cfg.get("usage_mode") or "auto").strip().lower()
    effective = effective_usage_mode(cfg)
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    installed = nv.available(bin_path)
    logged_in = False
    if installed:
        logged_in, _ = nordvpn_login_status(bin_path)
    vpn_ready = installed and logged_in
    mode_stale = mode == "tools_only" and vpn_ready
    profile = effective_install_profile(cfg)
    return {
        "ok": True,
        "mode": mode,
        "effective": effective,
        "install_profile": profile,
        "tools_only": effective == "tools_only",
        "vpn_expected": effective == "vpn",
        "nord_installed": installed,
        "logged_in": logged_in,
        "vpn_ready": vpn_ready,
        "mode_stale": mode_stale,
        "label": (
            "Network & Security only"
            if profile == "network"
            else ("Nord VPN focus" if profile == "nord" else "Full VPN mode")
        ),
        "hint": (
            "NordVPN is installed and logged in — switch to VPN mode in Setup to use presets and Connect fully."
            if mode_stale
            else (
                "No NordVPN account needed — Network & Security and Tools tabs are your main areas. Install optional apt packages from Package tools."
                if profile == "network"
                else (
                    "Nord Dashboard is your home — enable Network & Security later from Optional extras if you want WiFi, UFW, and scans."
                    if profile == "nord"
                    else "VPN features need NordVPN installed and logged in."
                )
            )
        ),
    }


def effective_install_profile(cfg: dict[str, Any] | None = None) -> str:
    """nord | network | full — from explicit config or inferred from modules + usage mode."""
    cfg = cfg or load_config()
    explicit = str(cfg.get("install_profile") or "auto").strip().lower()
    if explicit in ("nord", "network", "full"):
        return explicit
    if effective_usage_mode(cfg) == "tools_only":
        return "network"
    from nordctl.features import get_enabled_modules

    mods = get_enabled_modules(cfg)
    if not mods.get("wifi") and not mods.get("security") and not mods.get("traffic"):
        return "nord"
    return "full"


def is_headless(cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    return bool((cfg.get("server") or {}).get("headless"))


def apply_minimal_install_profile(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Default GitHub-friendly install: Nord VPN focus, network hub hidden until enabled."""
    from nordctl.features import apply_nord_focus_modules

    cfg = cfg or load_config()
    cfg["install_profile"] = "nord"
    cfg["usage_mode"] = "vpn"
    cfg.setdefault("tray", {})["enabled"] = False
    save_config(cfg)
    return apply_nord_focus_modules(cfg, complete=False)


def apply_headless_profile(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Server/VPS profile: API + CLI, no tray or browser alerts."""
    from nordctl.features import apply_nord_focus_modules

    cfg = cfg or load_config()
    cfg.setdefault("server", {})["headless"] = True
    cfg["install_profile"] = "nord"
    cfg["usage_mode"] = "vpn"
    cfg.setdefault("tray", {})["enabled"] = False
    cfg.setdefault("tray", {})["autostart"] = False
    cfg.setdefault("alerts", {})["browser_enabled"] = False
    save_config(cfg)
    return apply_nord_focus_modules(cfg, complete=True)


def ensure_server_port(cfg: dict[str, Any] | None = None, *, update_config: bool = False) -> tuple[int, int | None]:
    """Return a free UI port; optionally persist when the configured port is busy."""
    cfg = cfg or load_config()
    srv = cfg.setdefault("server", {})
    host = str(srv.get("bind") or "127.0.0.1")
    current = int(srv.get("port") or DEFAULT_UI_PORT)

    if is_port_free(host, current):
        return current, None

    free = find_free_port(host, DEFAULT_UI_PORT)
    replaced = current if free != current else None
    if update_config and replaced is not None:
        srv["port"] = free
        save_config(cfg)
    return free, replaced


def ensure_user_config(*, fix_port: bool = False, minimal: bool = True, headless: bool = False) -> Path:
    """Create config dir and copy example if missing; pick a free UI port."""
    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    dest = config_path()
    created = not dest.is_file()
    if created:
        example = Path(__file__).resolve().parent.parent / "config.example.yaml"
        if example.is_file():
            dest.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        else:
            dest.write_text(yaml.safe_dump(DEFAULTS, sort_keys=False), encoding="utf-8")

    cfg = load_config()
    port, replaced = ensure_server_port(cfg, update_config=created or fix_port)
    if created:
        print(f"Using UI port {port} (first free from {DEFAULT_UI_PORT})")
    elif replaced is not None:
        print(f"Port {replaced} was in use — updated config to {port}")

    from nordctl.baseline import ensure_baseline

    bl = ensure_baseline(cfg)
    if bl.get("created"):
        print(f"Install baseline saved: {bl.get('path')}")
        print("  Restore later: nordctl baseline restore")

    if created:
        if headless:
            apply_headless_profile(cfg)
            print("Headless profile applied — tray and browser alerts disabled.")
        elif minimal:
            apply_minimal_install_profile(cfg)
            print("Minimal VPN profile applied — enable Network & Security from Setup when ready.")
    return dest
