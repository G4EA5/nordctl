"""Community preset catalog and import from URL."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml

from nordctl.config import bundled_presets_dir, load_config
from nordctl.files import user_presets_dir
from nordctl.presets import get_preset, load_presets

MAX_DOWNLOAD_BYTES = 256_000
ALLOWED_URL_SCHEMES = ("https", "http", "file")


def community_presets_dir(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    custom = cfg.get("presets_dir")
    if custom:
        p = Path(str(custom)).expanduser() / "community"
        if p.is_dir():
            return p
    bundled = bundled_presets_dir() / "community"
    return bundled


def list_community_presets(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    root = community_presets_dir(cfg)
    items: list[dict[str, Any]] = []
    if root.is_dir():
        for path in sorted(root.glob("*.yaml")):
            try:
                doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            except (OSError, yaml.YAMLError):
                continue
            pid = str(doc.get("id") or path.stem).strip()
            preset_obj = get_preset(pid, cfg)
            items.append({
                "id": pid,
                "label": doc.get("label") or pid,
                "summary": doc.get("summary") or "",
                "category": doc.get("category") or "Community",
                "source": "bundled" if "share/nordctl" in str(path) or "presets/community" in str(path) else "local",
                "path": str(path),
                "installed": preset_obj is not None,
                "user_copy": bool(preset_obj and preset_obj.get("user")),
            })

    for p in load_presets(cfg):
        if p.get("community"):
            if not any(x["id"] == p.get("id") for x in items):
                items.append({
                    "id": p.get("id"),
                    "label": p.get("label"),
                    "summary": p.get("summary"),
                    "category": p.get("category") or "Community",
                    "source": "user",
                    "installed": True,
                    "user_copy": True,
                })

    return {"ok": True, "presets": items, "directory": str(root), "readme": str(root / "README.md")}


def _safe_preset_filename(preset_id: str) -> str:
    safe = re.sub(r"[^a-zA-Z0-9_-]+", "-", preset_id.strip()).strip("-").lower()
    return f"{safe or 'community-preset'}.yaml"


def _validate_preset_doc(doc: Any) -> str | None:
    if not isinstance(doc, dict):
        return "Preset must be a YAML mapping"
    if not doc.get("id"):
        return "Preset must include id:"
    if not doc.get("label"):
        return "Preset must include label:"
    steps = doc.get("steps")
    if not isinstance(steps, list) or not steps:
        return "Preset must include a non-empty steps: list"
    return None


def _write_imported_preset(doc: dict[str, Any]) -> dict[str, Any]:
    pid = str(doc["id"]).strip()
    doc["community"] = True
    if not doc.get("category"):
        doc["category"] = "Shared"

    dest = user_presets_dir() / _safe_preset_filename(pid)
    if dest.is_file():
        dest = user_presets_dir() / _safe_preset_filename(f"{pid}-imported")

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    return {
        "ok": True,
        "id": pid,
        "label": doc.get("label"),
        "path": str(dest),
        "file_id": f"user/{dest.name}",
        "note": f"Imported preset “{doc.get('label')}”. Find it under My presets.",
    }


def import_preset_from_content(content: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    text = str(content or "").strip()
    if not text:
        return {"ok": False, "error": "YAML content required"}

    try:
        doc = yaml.safe_load(text) or {}
    except yaml.YAMLError as exc:
        return {"ok": False, "error": f"Invalid YAML: {exc}"}

    err = _validate_preset_doc(doc)
    if err:
        return {"ok": False, "error": err}

    return _write_imported_preset(doc)


def save_preset_to_my_presets(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Copy a bundled or community preset into ~/.config/nordctl/presets/."""
    from nordctl.presets import export_preset_yaml, get_preset

    cfg = cfg or load_config()
    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"Unknown preset: {preset_id}"}

    if preset.get("user"):
        file_id = preset.get("_file_id") or f"user/{Path(str(preset.get('_path', ''))).name}"
        return {
            "ok": True,
            "already_saved": True,
            "id": preset.get("id"),
            "label": preset.get("label"),
            "file_id": file_id,
            "note": f"“{preset.get('label')}” is already in My presets.",
        }

    exp = export_preset_yaml(preset_id, cfg)
    if not exp.get("ok"):
        return exp

    try:
        doc = yaml.safe_load(exp["content"]) or {}
    except yaml.YAMLError as exc:
        return {"ok": False, "error": f"Invalid YAML: {exc}"}

    err = _validate_preset_doc(doc)
    if err:
        return {"ok": False, "error": err}

    pid = str(doc["id"]).strip()
    dest = user_presets_dir() / _safe_preset_filename(pid)
    if dest.is_file():
        base = _safe_preset_filename(f"{pid}-copy").replace(".yaml", "")
        dest = user_presets_dir() / f"{base}.yaml"
        n = 2
        while dest.is_file():
            dest = user_presets_dir() / f"{base}-{n}.yaml"
            n += 1

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")

    return {
        "ok": True,
        "id": pid,
        "label": doc.get("label"),
        "path": str(dest),
        "file_id": f"user/{dest.name}",
        "note": f"Saved “{doc.get('label')}” to My presets — edit, share, or run it from the cards below.",
    }
    cfg = cfg or load_config()
    url = str(url or "").strip()
    if not url:
        return {"ok": False, "error": "URL required"}

    parsed = urllib.request.urlsplit(url)
    if parsed.scheme not in ALLOWED_URL_SCHEMES:
        return {"ok": False, "error": f"URL scheme must be one of: {', '.join(ALLOWED_URL_SCHEMES)}"}

    try:
        if parsed.scheme == "file":
            raw = Path(parsed.path).read_bytes()
        else:
            req = urllib.request.Request(url, headers={"User-Agent": "nordctl/community-import"})
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read(MAX_DOWNLOAD_BYTES + 1)
                if len(raw) > MAX_DOWNLOAD_BYTES:
                    return {"ok": False, "error": "Preset file too large (max 256 KB)"}
    except (urllib.error.URLError, OSError) as exc:
        return {"ok": False, "error": f"Download failed: {exc}"}

    try:
        doc = yaml.safe_load(raw.decode("utf-8", errors="replace")) or {}
    except yaml.YAMLError as exc:
        return {"ok": False, "error": f"Invalid YAML: {exc}"}

    err = _validate_preset_doc(doc)
    if err:
        return {"ok": False, "error": err}

    return _write_imported_preset(doc)
