"""Product roadmap tiers 1–6 — feature discovery without bloat."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.features import get_enabled_modules, module_catalog


def roadmap_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    mods = get_enabled_modules(cfg)
    catalog = {m["id"]: m for m in module_catalog()}

    tiers: dict[int, dict[str, Any]] = {
        1: {
            "title": "Essentials",
            "tagline": "Connect, presets, leak lab, health score",
            "items": ["dashboard", "lab", "security", "logs", "help"],
        },
        2: {
            "title": "Network hub",
            "tagline": "WiFi, traffic, automate, Meshnet",
            "items": ["wifi", "control", "automate", "traffic", "services"],
        },
        3: {
            "title": "Power user",
            "tagline": "Capture, HA export, LAN status, bandwidth",
            "items": ["security"],
            "features": [
                "Packet capture lite",
                "Home Assistant REST",
                "LAN status page",
                "Live bandwidth",
            ],
        },
        4: {
            "title": "Stay informed",
            "tagline": "Browser & email alerts, privacy dashboard",
            "items": ["alerts"],
            "features": [
                "Browser notifications (local UI)",
                "Email via your SMTP only",
                "VPN disconnect & DNS drift rules",
                "Privacy manifest",
            ],
        },
        5: {
            "title": "Global & portable",
            "tagline": "Regional presets, health digest, privacy export",
            "items": [],
            "features": [
                "Regional preset pack (EU, US, UK, APAC, LATAM, …)",
                "Daily health digest in activity log",
                "Privacy report export (local JSON)",
                "Connection journal (local, no cloud)",
            ],
        },
        6: {
            "title": "Smart assistant",
            "tagline": "Recommendations & optional webhook",
            "items": [],
            "features": [
                "Smart preset suggestions from doctors",
                "Alert rule builder in UI",
                "Optional webhook to your home automation (user URL only)",
                "Module picker on first install",
            ],
        },
    }

    out_tiers: list[dict[str, Any]] = []
    for n in range(1, 7):
        t = tiers[n]
        module_items = []
        for mid in t.get("items") or []:
            c = catalog.get(mid, {})
            module_items.append({
                "id": mid,
                "label": c.get("label", mid),
                "enabled": mods.get(mid, True),
            })
        out_tiers.append({
            "tier": n,
            "title": t["title"],
            "tagline": t["tagline"],
            "modules": module_items,
            "features": t.get("features") or [],
            "active": all(mods.get(m["id"], True) for m in module_items) if module_items else True,
        })

    return {"ok": True, "tiers": out_tiers, "current_max_enabled": _max_tier(mods)}


def _max_tier(mods: dict[str, bool]) -> int:
    if not mods.get("alerts", True):
        return 3 if mods.get("wifi", True) else 2
    return 6
