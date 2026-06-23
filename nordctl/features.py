"""Feature modules — pick what to install, control nav and background services."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import load_config, save_config

# id -> nav data-view name (None = always on or not a tab)
MODULE_CATALOG: list[dict[str, Any]] = [
    {
        "id": "dashboard",
        "label": "Dashboard & presets",
        "emoji": "🏠",
        "hint": "VPN connect, Smart DNS, preset grid — core experience",
        "required": True,
        "view": "dashboard",
        "tier": 1,
    },
    {
        "id": "wifi",
        "label": "WiFi hub",
        "emoji": "📶",
        "hint": "Profiles, zones, doctors, self-healing",
        "view": "wifi",
        "tier": 2,
    },
    {
        "id": "lab",
        "label": "Leak lab",
        "emoji": "🧪",
        "hint": "DNS leak tests and network audit",
        "view": "lab",
        "tier": 1,
    },
    {
        "id": "security",
        "label": "Security hub",
        "emoji": "🛡️",
        "hint": "Health score, bandwidth, capture, status page",
        "view": "security",
        "tier": 1,
    },
    {
        "id": "control",
        "label": "Control & Meshnet",
        "emoji": "🎛️",
        "hint": "Favorites, split tunnel, Meshnet peers",
        "view": "control",
        "tier": 2,
    },
    {
        "id": "automate",
        "label": "Automate",
        "emoji": "⏰",
        "hint": "Schedules, zones, baseline rollback",
        "view": "automate",
        "tier": 2,
    },
    {
        "id": "traffic",
        "label": "Traffic watch",
        "emoji": "🔀",
        "hint": "Who is talking to who (Advanced tab)",
        "view": "advanced",
        "tier": 2,
    },
    {
        "id": "services",
        "label": "Services panel",
        "emoji": "⚙️",
        "hint": "nordctl UI, nordvpnd, tray — in Advanced",
        "view": "advanced",
        "tier": 2,
    },
    {
        "id": "alerts",
        "label": "Browser & email alerts",
        "emoji": "🔔",
        "hint": "Local notifications — your SMTP only, no cloud",
        "view": "security",
        "tier": 4,
    },
    {
        "id": "logs",
        "label": "Activity log",
        "emoji": "📋",
        "hint": "Plain-English local history",
        "view": "logs",
        "tier": 1,
    },
    {
        "id": "editor",
        "label": "Config editor",
        "emoji": "✏️",
        "hint": "Edit config.yaml and presets in the UI",
        "view": "editor",
        "tier": 1,
    },
    {
        "id": "terminal",
        "label": "Web terminal",
        "emoji": "💻",
        "hint": "Interactive bash — sudo, nordvpn login, apt installs",
        "view": "terminal",
        "tier": 1,
    },
    {
        "id": "help",
        "label": "Help guide",
        "emoji": "❓",
        "hint": "Full documentation",
        "view": "help",
        "required": True,
        "tier": 1,
    },
]

DEFAULT_MODULES: dict[str, bool] = {m["id"]: True for m in MODULE_CATALOG}


def _place_values_set(cfg: dict[str, Any]) -> bool:
    from nordctl.config_fields import FIELD_CATALOG

    for fid in FIELD_CATALOG:
        if cfg.get(fid):
            return True
    for row in cfg.get("custom_places") or []:
        pid = str(row.get("id") or "").strip()
        if pid and cfg.get(pid):
            return True
    return False


def _activity_in_use() -> bool:
    from nordctl.activity_log import LOG_FILE

    try:
        return LOG_FILE.is_file() and LOG_FILE.stat().st_size > 512
    except OSError:
        return False


def is_returning_user(cfg: dict[str, Any]) -> bool:
    """Install is clearly in use but onboarding was never marked complete."""
    feats = cfg.get("features") or {}
    if feats.get("onboarding_complete"):
        return False
    fav = cfg.get("favorites") or {}
    if fav.get("countries") or fav.get("servers"):
        return True
    if _place_values_set(cfg):
        return True
    if _activity_in_use():
        return True
    if (cfg.get("security") or {}).get("custom_scenarios"):
        return True
    if cfg.get("schedules"):
        return True
    if (cfg.get("wifi") or {}).get("profiles"):
        return True
    if str(cfg.get("install_profile") or "auto").strip().lower() not in ("", "auto"):
        return True
    if str(cfg.get("usage_mode") or "auto").strip().lower() not in ("", "auto"):
        return True
    return False


def ensure_onboarding_for_returning_user(cfg: dict[str, Any]) -> bool:
    """One-time: skip the welcome modal for installs that are already configured."""
    if not is_returning_user(cfg):
        return False
    apply_modules(
        get_enabled_modules(cfg),
        cfg,
        legal_accepted=True,
        complete=True,
    )
    return True


def module_catalog() -> list[dict[str, Any]]:
    return [dict(m) for m in MODULE_CATALOG]


def get_enabled_modules(cfg: dict[str, Any] | None = None) -> dict[str, bool]:
    cfg = cfg or load_config()
    feats = cfg.get("features") or {}
    stored = dict(feats.get("modules") or {})
    out = dict(DEFAULT_MODULES)
    for m in MODULE_CATALOG:
        if m.get("required"):
            out[m["id"]] = True
    out.update({k: bool(v) for k, v in stored.items()})
    return out


def is_module_enabled(module_id: str, cfg: dict[str, Any] | None = None) -> bool:
    mods = get_enabled_modules(cfg)
    return bool(mods.get(module_id, True))


def apply_nord_focus_modules(cfg: dict[str, Any] | None = None, *, complete: bool = True) -> dict[str, Any]:
    """VPN presets focus — hide network/security hubs until user opts in."""
    cfg = cfg or load_config()
    nord_mods = {
        m["id"]: m["id"] in ("dashboard", "help", "logs", "editor", "terminal", "automate", "lab")
        or bool(m.get("required"))
        for m in module_catalog()
    }
    return apply_modules(nord_mods, cfg, legal_accepted=True, complete=complete)


def enable_network_modules(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Turn on Network & Security hub modules without changing Nord usage mode."""
    cfg = cfg or load_config()
    mods = get_enabled_modules(cfg)
    for mid in ("wifi", "lab", "security", "control", "traffic", "services"):
        mods[mid] = True
    if str(cfg.get("install_profile") or "auto") in ("auto", "nord"):
        cfg["install_profile"] = "full"
        save_config(cfg)
    return apply_modules(mods, cfg)


def features_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    feats = cfg.setdefault("features", {})
    mods = get_enabled_modules(cfg)
    views = set()
    for m in MODULE_CATALOG:
        if mods.get(m["id"], True) and m.get("view"):
            views.add(m["view"])
    return {
        "ok": True,
        "onboarding_complete": bool(feats.get("onboarding_complete")),
        "setup_wizard_complete": bool(feats.get("setup_wizard_complete")),
        "legal_accepted": bool(feats.get("legal_accepted")),
        "modules": mods,
        "catalog": module_catalog(),
        "enabled_views": sorted(views),
        "open_source": {
            "license": "MIT",
            "license_url": "https://opensource.org/licenses/MIT",
            "source_hint": "Full source in your nordctl install directory — no proprietary blobs.",
        },
    }


def apply_modules(
    selected: dict[str, bool],
    cfg: dict[str, Any] | None = None,
    *,
    legal_accepted: bool | None = None,
    complete: bool | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    feats = cfg.setdefault("features", {})
    mods: dict[str, bool] = {}
    for m in MODULE_CATALOG:
        mid = m["id"]
        if m.get("required"):
            mods[mid] = True
        else:
            mods[mid] = bool(selected.get(mid, DEFAULT_MODULES.get(mid, True)))
    feats["modules"] = mods
    if legal_accepted is not None:
        feats["legal_accepted"] = bool(legal_accepted)
    if complete is not None:
        feats["onboarding_complete"] = bool(complete)
    save_config(cfg)
    return features_payload(cfg)


def enable_all_modules(cfg: dict[str, Any] | None = None, *, complete: bool = True) -> dict[str, Any]:
    return apply_modules(
        {m["id"]: True for m in MODULE_CATALOG},
        cfg,
        legal_accepted=True,
        complete=complete,
    )
