"""Config profiles (Work / Streaming / Travel) and favorites."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from copy import deepcopy
from typing import Any

from nordctl.config import load_config, save_config

EXAMPLE_FAVORITES: dict[str, list[str]] = {
    "countries": ["United_States", "United_Kingdom", "Germany", "France"],
    "servers": ["Spain Madrid", "Netherlands Amsterdam"],
}


def ensure_example_favorites(cfg: dict[str, Any] | None = None) -> bool:
    """Seed a few starter favorites when the list is empty (once per install)."""
    cfg = deepcopy(cfg or load_config())
    fav = cfg.get("favorites") if isinstance(cfg.get("favorites"), dict) else {}
    if fav.get("examples_seeded") or fav.get("countries") or fav.get("servers"):
        return False
    cfg["favorites"] = {
        "countries": list(EXAMPLE_FAVORITES["countries"]),
        "servers": list(EXAMPLE_FAVORITES["servers"]),
        "examples_seeded": True,
    }
    save_config(cfg)
    return True


def favorite_key(kind: str, value: str) -> str:
    val = str(value or "").strip()
    k = str(kind or "country").strip().lower()
    if k == "country" and " " in val:
        k = "city"
    elif k not in ("country", "city"):
        k = "city" if " " in val else "country"
    return f"{k}:{val}"


def _favorite_display(kind: str, value: str, overrides: dict[str, Any]) -> str:
    key = favorite_key(kind, value)
    ov = overrides.get(key) or {}
    label = str(ov.get("label") or "").strip()
    if label:
        return label
    if kind == "country":
        return str(value).replace("_", " ")
    return str(value)


def _favorite_rows(fav: dict[str, Any]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for c in fav.get("countries") or []:
        rows.append({"kind": "country", "value": str(c)})
    for s in fav.get("servers") or []:
        rows.append({"kind": "city", "value": str(s)})
    return rows


def list_profiles(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    if ensure_example_favorites(cfg):
        cfg = load_config()
    profiles = cfg.get("config_profiles") or {}
    active = str(cfg.get("active_profile") or "default")
    fav = cfg.get("favorites") or {}
    ui = cfg.get("ui") or {}
    hidden_keys = set(str(x) for x in (ui.get("hidden_favorites") or []))
    overrides = ui.get("favorite_overrides") or {}
    hidden_favorites: list[dict[str, str]] = []
    for row in _favorite_rows(fav):
        key = favorite_key(row["kind"], row["value"])
        if key in hidden_keys:
            hidden_favorites.append({
                **row,
                "display": _favorite_display(row["kind"], row["value"], overrides),
            })
    return {
        "active": active,
        "names": list(profiles.keys()) or ["default"],
        "profiles": profiles,
        "favorites": {
            "countries": list(fav.get("countries") or []),
            "servers": list(fav.get("servers") or []),
        },
        "hidden_favorites": hidden_favorites,
        "favorite_overrides": overrides,
        "hidden_favorite_keys": sorted(hidden_keys),
    }


def switch_profile(name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    profiles = cfg.get("config_profiles") or {}
    if name not in profiles and name != "default":
        return {"ok": False, "error": f"Unknown profile: {name}"}

    cfg["active_profile"] = name
    overlay = profiles.get(name) or {}
    for key, val in overlay.items():
        if isinstance(val, dict) and isinstance(cfg.get(key), dict):
            cfg[key] = {**cfg.get(key, {}), **val}
        else:
            cfg[key] = val
    save_config(cfg)
    return {"ok": True, "active": name}


def save_profile(name: str, overlay: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    profiles = cfg.setdefault("config_profiles", {})
    profiles[name] = overlay
    save_config(cfg)
    return {"ok": True, "name": name}


def add_favorite(kind: str, value: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    fav = cfg.setdefault("favorites", {"countries": [], "servers": []})
    val = value.strip()
    if not val:
        return {"ok": False, "error": "Pick a country or city first."}
    kind = str(kind or "country").strip().lower()
    if kind == "country" and " " in val:
        kind = "city"
    key = "countries" if kind == "country" else "servers"
    items = list(fav.get(key) or [])
    if val and val not in items:
        items.append(val)
    fav[key] = items
    save_config(cfg)
    return {"ok": True, "favorites": fav}


def remove_favorite(kind: str, value: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    fav = cfg.setdefault("favorites", {"countries": [], "servers": []})
    val = value.strip()
    kind_norm = str(kind or "country").strip().lower()
    if kind_norm == "country" and " " in val:
        kind_norm = "city"
    key = "countries" if kind_norm == "country" else "servers"
    items = [x for x in (fav.get(key) or []) if x != val]
    fav[key] = items
    ui = cfg.setdefault("ui", {})
    fav_key = favorite_key(kind, value)
    ui["hidden_favorites"] = [x for x in (ui.get("hidden_favorites") or []) if str(x) != fav_key]
    overrides = dict(ui.get("favorite_overrides") or {})
    overrides.pop(fav_key, None)
    ui["favorite_overrides"] = overrides
    save_config(cfg)
    return {"ok": True, "favorites": fav}


def hide_favorite(kind: str, value: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    fav_key = favorite_key(kind, value)
    ui = cfg.setdefault("ui", {})
    hidden = list(ui.get("hidden_favorites") or [])
    if fav_key not in hidden:
        hidden.append(fav_key)
    ui["hidden_favorites"] = hidden
    save_config(cfg)
    return {"ok": True, "note": "Favorite hidden"}


def unhide_favorite(kind: str, value: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    fav_key = favorite_key(kind, value)
    ui = cfg.setdefault("ui", {})
    ui["hidden_favorites"] = [x for x in (ui.get("hidden_favorites") or []) if str(x) != fav_key]
    save_config(cfg)
    return {"ok": True, "note": "Favorite restored"}


def update_favorite_display(kind: str, value: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = deepcopy(cfg or load_config())
    fav_key = favorite_key(kind, value)
    ui = cfg.setdefault("ui", {})
    overrides = dict(ui.get("favorite_overrides") or {})
    label = str(body.get("label") or "").strip()
    if label:
        overrides[fav_key] = {**(overrides.get(fav_key) or {}), "label": label}
    elif fav_key in overrides:
        row = dict(overrides[fav_key])
        row.pop("label", None)
        if row:
            overrides[fav_key] = row
        else:
            overrides.pop(fav_key, None)
    ui["favorite_overrides"] = overrides
    save_config(cfg)
    return {"ok": True, "note": "Favorite updated"}
