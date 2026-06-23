"""Dashboard interface preferences stored in config.yaml under ``ui``."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import load_config, save_config


def ui_prefs_from_config(cfg: dict[str, Any] | None = None) -> dict[str, bool]:
    cfg = cfg or load_config()
    ui = cfg.get("ui") or {}
    return {
        "page_guides_visible_default": ui.get("page_guides_visible_default", True) is not False,
        "page_intro_visible": ui.get("page_intro_visible", True) is not False,
        "clock_format": "12h" if str(ui.get("clock_format", "24h")).lower() in ("12", "12h", "ampm") else "24h",
    }


def save_ui_prefs(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ui = cfg.setdefault("ui", {})
    if "page_guides_visible_default" in body:
        ui["page_guides_visible_default"] = bool(body["page_guides_visible_default"])
    if "page_intro_visible" in body:
        ui["page_intro_visible"] = bool(body["page_intro_visible"])
    if "clock_format" in body:
        raw = str(body.get("clock_format", "24h")).lower().strip()
        ui["clock_format"] = "12h" if raw in ("12", "12h", "ampm") else "24h"
    save_config(cfg)
    prefs = ui_prefs_from_config(cfg)
    return {
        "ok": True,
        "note": "Interface preferences saved to config.yaml — applies on every browser after refresh.",
        **prefs,
    }
