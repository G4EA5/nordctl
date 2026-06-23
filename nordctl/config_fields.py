"""User-facing config fields — menus instead of editing config.yaml."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import load_config

# Keys presets may require — each has a menu type for the web UI.
FIELD_CATALOG: dict[str, dict[str, Any]] = {
    "connect_country": {
        "label": "Home country",
        "hint": "Used for reconnect, streaming, and regional presets.",
        "type": "country",
        "placeholder": "Pick your country…",
    },
    "connect_city": {
        "label": "Preferred city",
        "hint": 'Connect to a specific city — e.g. "United Kingdom London". Pick country first, then city.',
        "type": "city",
        "country_field": "connect_country",
        "placeholder": "Pick country, then city…",
    },
    "travel_country": {
        "label": "Travel country",
        "hint": "Country to use when traveling (APAC travel, travel presets).",
        "type": "country",
        "placeholder": "Where you travel most…",
    },
    "gaming_country": {
        "label": "Gaming country",
        "hint": "Low-latency VPN exit for gaming presets.",
        "type": "country",
        "placeholder": "Gaming server region…",
    },
    "work_country": {
        "label": "Work country",
        "hint": "VPN exit for work presets while keeping home LAN accessible.",
        "type": "country",
        "placeholder": "Work VPN country…",
    },
    "connect_server": {
        "label": "Dedicated server",
        "hint": "Specific Nord server name or ID from nordvpn servers.",
        "type": "text",
        "placeholder": "e.g. uk1234 or server hostname",
    },
    "mesh_peer": {
        "label": "Meshnet peer",
        "hint": "Peer hostname or nickname for Meshnet exit presets.",
        "type": "text",
        "placeholder": "e.g. my-phone.nord",
        "help_view": "dashboard",
        "help_anchor": "mesh",
    },
    "custom_dns": {
        "label": "Custom DNS servers",
        "hint": "Comma-separated DNS IPs for custom DNS presets.",
        "type": "text",
        "placeholder": "1.1.1.1, 8.8.8.8",
    },
    "lan_allowlist_cidr": {
        "label": "Home LAN range",
        "hint": "Local subnet reachable while LAN split tunnel is on (Switches) — printers, NAS, etc. Set on Split tunnel.",
        "type": "text",
        "placeholder": "192.168.0.0/16",
        "show_in_places": False,
    },
}


def field_meta(field_id: str) -> dict[str, Any] | None:
    meta = FIELD_CATALOG.get(field_id)
    if not meta:
        return None
    return {"id": field_id, **meta}


def missing_requirement(field_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Structured missing-config payload for API + UI wizard."""
    cfg = cfg or load_config()
    meta = field_meta(field_id) or {
        "id": field_id,
        "label": field_id.replace("_", " ").title(),
        "hint": "Set this value to continue.",
        "type": "text",
        "placeholder": "",
    }
    label = meta.get("label") or field_id
    return {
        "field": field_id,
        "message": f"Before running this, choose your {label.lower()}.",
        "field_meta": meta,
        "current": cfg.get(field_id),
        "preset_hint": f"Save your {label.lower()} below, then try the preset again.",
    }


def _ui_section(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.setdefault("ui", {})


def _hidden_places(cfg: dict[str, Any]) -> set[str]:
    return {str(x) for x in (_ui_section(cfg).get("hidden_places") or [])}


def _place_overrides(cfg: dict[str, Any]) -> dict[str, Any]:
    return _ui_section(cfg).setdefault("place_overrides", {})


def _place_field_row(
    cfg: dict[str, Any],
    fid: str,
    *,
    meta: dict[str, Any] | None = None,
    custom_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    ov = _place_overrides(cfg).get(fid) or {}
    custom = custom_row is not None
    if custom:
        val = cfg.get(fid) if cfg.get(fid) is not None else custom_row.get("value")
        base_meta = custom_row or {}
        label = str(ov.get("label") or base_meta.get("label") or fid.replace("_", " ").title())
        hint = str(ov.get("hint") or base_meta.get("hint") or "Custom place — saved for presets and quick connect.")
        ftype = str(ov.get("type") or base_meta.get("type") or "text")
        country_field = base_meta.get("country_field") or "connect_country"
        placeholder = str(base_meta.get("placeholder") or "")
    else:
        meta = meta or FIELD_CATALOG[fid]
        val = cfg.get(fid)
        label = str(ov.get("label") or meta["label"])
        hint = str(ov.get("hint") or meta.get("hint", ""))
        ftype = meta.get("type", "text")
        country_field = meta.get("country_field")
        placeholder = meta.get("placeholder", "")
    display = val
    if isinstance(val, list):
        display = ", ".join(str(x) for x in val)
    return {
        "id": fid,
        "label": label,
        "hint": hint,
        "type": ftype,
        "value": display or "",
        "set": bool(val),
        "country_field": country_field,
        "placeholder": placeholder,
        "custom": custom,
        "builtin": not custom,
    }


def location_settings(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    hidden = _hidden_places(cfg)
    fields: list[dict[str, Any]] = []
    hidden_fields: list[dict[str, Any]] = []
    for fid, meta in FIELD_CATALOG.items():
        if meta.get("show_in_places") is False:
            row = _place_field_row(cfg, fid, meta=meta)
            row["show_in_places"] = False
            if fid in hidden:
                hidden_fields.append(row)
            else:
                fields.append(row)
            continue
        row = _place_field_row(cfg, fid, meta=meta)
        if fid in hidden:
            hidden_fields.append(row)
        else:
            fields.append(row)
    for row in cfg.get("custom_places") or []:
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        place_row = _place_field_row(cfg, pid, custom_row=row)
        if pid in hidden:
            hidden_fields.append(place_row)
        else:
            fields.append(place_row)
    return {"ok": True, "fields": fields, "hidden_fields": hidden_fields}


def hide_place(place_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(place_id or "").strip()
    if pid not in FIELD_CATALOG and not _custom_place_row(cfg, pid):
        return {"ok": False, "error": f"Unknown place: {pid}"}
    ui = _ui_section(cfg)
    hidden = list(ui.get("hidden_places") or [])
    if pid not in hidden:
        hidden.append(pid)
    ui["hidden_places"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Place hidden"}


def unhide_place(place_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(place_id or "").strip()
    ui = _ui_section(cfg)
    hidden = [x for x in (ui.get("hidden_places") or []) if str(x) != pid]
    ui["hidden_places"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Place restored"}


def update_place(place_id: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(place_id or "").strip()
    custom = _custom_place_row(cfg, pid)
    label = str(body.get("label") or "").strip()
    hint = str(body.get("hint") or "").strip()
    if custom:
        if label:
            custom["label"] = label
        if hint:
            custom["hint"] = hint
        kind = str(body.get("type") or "").strip().lower()
        if kind in ("country", "city", "text"):
            custom["type"] = kind
            if kind == "city":
                custom["country_field"] = body.get("country_field") or custom.get("country_field") or "connect_country"
        from nordctl.config import save_config

        save_config(cfg)
        return {"ok": True, "note": "Place updated"}
    if pid not in FIELD_CATALOG:
        return {"ok": False, "error": f"Unknown place: {pid}"}
    ov = _place_overrides(cfg).setdefault(pid, {})
    if label:
        ov["label"] = label
    if hint:
        ov["hint"] = hint
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Place updated"}


def hide_preset(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(preset_id or "").strip()
    if not pid:
        return {"ok": False, "error": "Preset id required"}
    ui = _ui_section(cfg)
    hidden = list(ui.get("hidden_presets") or [])
    if pid not in hidden:
        hidden.append(pid)
    ui["hidden_presets"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Preset hidden"}


def unhide_preset(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(preset_id or "").strip()
    ui = _ui_section(cfg)
    hidden = [x for x in (ui.get("hidden_presets") or []) if str(x) != pid]
    ui["hidden_presets"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Preset restored"}


def update_preset_display(preset_id: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(preset_id or "").strip()
    label = str(body.get("label") or "").strip()
    summary = str(body.get("summary") or "").strip()
    category = str(body.get("category") or "").strip()
    ov = _ui_section(cfg).setdefault("preset_overrides", {}).setdefault(pid, {})
    if label:
        ov["label"] = label
    if summary:
        ov["summary"] = summary
    if category:
        ov["category"] = category
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Preset updated"}


def _custom_place_row(cfg: dict[str, Any], field_id: str) -> dict[str, Any] | None:
    for row in cfg.get("custom_places") or []:
        if str(row.get("id") or "") == field_id:
            return row
    return None


def add_custom_place(
    label: str,
    type_: str = "country",
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    import re

    cfg = cfg or load_config()
    text = str(label or "").strip()
    if not text:
        return {"ok": False, "error": "Enter a name for this place."}
    kind = str(type_ or "country").strip().lower()
    if kind not in ("country", "city", "text"):
        kind = "country"
    pid = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_") or "custom_place"
    places = list(cfg.get("custom_places") or [])
    existing = {str(p.get("id") or "") for p in places}
    base = pid
    n = 2
    while pid in existing:
        pid = f"{base}_{n}"
        n += 1
    row = {
        "id": pid,
        "label": text,
        "type": kind,
        "hint": f"Custom {kind} — used like built-in My places fields.",
        "placeholder": "Pick country…" if kind == "country" else ("Pick city…" if kind == "city" else "Enter value…"),
    }
    if kind == "city":
        row["country_field"] = "connect_country"
    places.append(row)
    cfg["custom_places"] = places
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "place": row, "note": f"Added place: {text}"}


def remove_custom_place(place_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    pid = str(place_id or "").strip()
    places = [p for p in (cfg.get("custom_places") or []) if str(p.get("id") or "") != pid]
    if len(places) == len(cfg.get("custom_places") or []):
        return {"ok": False, "error": f"Unknown place: {pid}"}
    cfg["custom_places"] = places
    if pid in cfg:
        del cfg[pid]
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Place removed"}


def clear_config_field(field_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Remove a saved My places value (built-in or custom)."""
    cfg = cfg or load_config()
    fid = str(field_id or "").strip()
    custom = _custom_place_row(cfg, fid)
    if custom:
        if fid in cfg:
            del cfg[fid]
        custom.pop("value", None)
        from nordctl.config import save_config

        save_config(cfg)
        return {"ok": True, "field": fid, "note": f"Cleared {custom.get('label', fid)}"}

    if fid not in FIELD_CATALOG:
        return {"ok": False, "error": f"Unknown setting: {fid}"}

    if fid not in cfg:
        return {"ok": True, "field": fid, "note": "Already empty"}

    del cfg[fid]
    from nordctl.config import save_config

    save_config(cfg)
    meta = FIELD_CATALOG[fid]
    return {"ok": True, "field": fid, "note": f"Cleared {meta['label']}"}


def set_config_field(cfg: dict[str, Any], field_id: str, value: Any) -> dict[str, Any]:
    fid = str(field_id or "").strip()
    custom = _custom_place_row(cfg, fid)
    if custom:
        kind = str(custom.get("type") or "text")
        if kind == "country":
            text = str(value or "").strip()
            if not text:
                return {"ok": False, "error": f"Pick a country for {custom.get('label')}."}
            stored = text.replace(" ", "_")
        elif kind == "city":
            text = str(value or "").strip()
            if not text:
                return {"ok": False, "error": "Pick a city from the list."}
            stored = text
        else:
            text = str(value or "").strip()
            if not text:
                return {"ok": False, "error": f"Enter a value for {custom.get('label')}."}
            stored = text
        custom["value"] = stored
        cfg[fid] = stored
        from nordctl.config import save_config

        save_config(cfg)
        display = stored.replace("_", " ") if kind == "country" else stored
        return {"ok": True, "field": fid, "value": stored, "note": f"{custom.get('label')} saved: {display}"}

    if fid not in FIELD_CATALOG:
        return {"ok": False, "error": f"Unknown setting: {fid}"}

    meta = FIELD_CATALOG[fid]
    raw = value
    if meta.get("type") == "country":
        text = str(value or "").strip()
        if not text:
            return {"ok": False, "error": f"Pick a country for {meta['label']}."}
        cfg[fid] = text.replace(" ", "_")
    elif meta.get("type") == "city":
        text = str(value or "").strip()
        if not text:
            return {"ok": False, "error": "Pick a city from the list."}
        cfg[fid] = text
    elif fid == "custom_dns":
        if isinstance(value, list):
            cfg[fid] = [str(x).strip() for x in value if str(x).strip()]
        else:
            parts = [p.strip() for p in str(value or "").split(",") if p.strip()]
            if not parts:
                return {"ok": False, "error": "Enter at least one DNS IP address."}
            cfg[fid] = parts
    else:
        text = str(value or "").strip()
        if not text:
            return {"ok": False, "error": f"Enter a value for {meta['label']}."}
        cfg[fid] = text

    from nordctl.config import save_config

    save_config(cfg)
    label = meta["label"]
    display = cfg.get(fid)
    if isinstance(display, list):
        display = ", ".join(display)
    elif isinstance(display, str):
        display = display.replace("_", " ")
    return {
        "ok": True,
        "field": fid,
        "value": cfg.get(fid),
        "note": f"{label} saved: {display}",
    }


# Preset categories shown on each Nord Dashboard tab (workflows = general presets only).
PRESET_PANEL_CATEGORIES: dict[str, list[str]] = {
    "split-tunnel": ["Split tunnel"],
    "server-groups": ["Server groups"],
}


def categories_for_preset_panel(panel: str) -> list[str]:
    key = str(panel or "").strip()
    return list(PRESET_PANEL_CATEGORIES.get(key) or [])


def reset_presets_factory(
    categories: list[str] | None = None,
    *,
    panel: str | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Restore presets in the given categories to factory — unhide, clear UI overrides, restore user YAML from install baseline."""
    from nordctl.files import restore_file_from_baseline
    from nordctl.presets import load_presets

    cfg = cfg or load_config()
    cats = [c.strip() for c in (categories or []) if str(c).strip()]
    if panel and not cats:
        cats = categories_for_preset_panel(panel)
    cat_set = set(cats)
    if not cat_set:
        return {"ok": False, "error": "Unknown preset panel or empty category list"}

    ui = _ui_section(cfg)
    hidden = list(ui.get("hidden_presets") or [])
    overrides = dict(ui.get("preset_overrides") or {})

    affected: list[str] = []
    restored_files: list[str] = []
    removed_files: list[str] = []
    errors: list[str] = []

    for preset in load_presets(cfg):
        pid = str(preset.get("id") or "")
        if not pid:
            continue
        pcat = str(preset.get("category") or "General")
        if pcat not in cat_set:
            continue
        affected.append(pid)
        hidden = [x for x in hidden if str(x) != pid]
        overrides.pop(pid, None)
        if preset.get("user") and preset.get("_file_id"):
            fid = str(preset["_file_id"])
            result = restore_file_from_baseline(fid)
            if not result.get("ok"):
                errors.append(result.get("error") or f"Could not restore {fid}")
            elif result.get("removed"):
                removed_files.append(fid)
            else:
                restored_files.append(fid)

    ui["hidden_presets"] = hidden
    ui["preset_overrides"] = overrides
    from nordctl.config import save_config

    save_config(cfg)

    label = ", ".join(sorted(cat_set))
    parts = [f"Reset {len(affected)} preset(s) in {label}"]
    if restored_files:
        parts.append(f"restored {len(restored_files)} custom file(s) from install")
    if removed_files:
        parts.append(f"removed {len(removed_files)} custom file(s) added after install")
    note = " — ".join(parts) + "."

    return {
        "ok": not errors or bool(affected),
        "note": note,
        "panel": panel,
        "categories": sorted(cat_set),
        "affected": affected,
        "restored_files": restored_files,
        "removed_files": removed_files,
        "errors": errors or None,
        "error": errors[0] if errors and not affected else None,
    }
