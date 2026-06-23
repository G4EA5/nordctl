"""Safe read/write for nordctl configuration files (web editor)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from nordctl.config import config_dir, config_path, load_config, presets_directory, save_config

MAX_BYTES = 128 * 1024
PRESET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}\.yaml$", re.I)


def user_presets_dir() -> Path:
    d = config_dir() / "presets"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _bundled_presets_dir() -> Path:
    return presets_directory(load_config())


def _file_entry(
    fid: str,
    path: Path,
    *,
    label: str,
    group: str,
    editable: bool,
    description: str = "",
) -> dict[str, Any]:
    exists = path.is_file()
    size = path.stat().st_size if exists else 0
    too_large = size > MAX_BYTES
    return {
        "id": fid,
        "label": label,
        "path": str(path),
        "group": group,
        "editable": editable and exists and not too_large,
        "readonly": not editable or too_large,
        "exists": exists,
        "size": size,
        "too_large": too_large,
        "description": description,
    }


def list_editable_files() -> dict[str, Any]:
    cfg_path = config_path()
    user_dir = user_presets_dir()
    bundled = _bundled_presets_dir()

    files: list[dict[str, Any]] = [
        _file_entry(
            "config",
            cfg_path,
            label="config.yaml",
            group="Configuration",
            editable=True,
            description="Main settings: WiFi profiles, countries, Smart DNS, UI port",
        ),
    ]

    if not cfg_path.is_file():
        files[0]["editable"] = True
        files[0]["readonly"] = False
        files[0]["exists"] = False

    for p in sorted(user_dir.glob("*.yaml")):
        fid = f"user/{p.name}"
        files.append(
            _file_entry(
                fid,
                p,
                label=p.name,
                group="Your presets",
                editable=True,
                description="Custom preset — add under ~/.config/nordctl/presets/",
            )
        )

    if bundled.is_dir():
        for p in sorted(bundled.glob("*.yaml")):
            if p.name.lower() == "readme.md":
                continue
            fid = f"bundled/{p.name}"
            files.append(
                _file_entry(
                    fid,
                    p,
                    label=p.name,
                    group="Bundled presets (read-only)",
                    editable=False,
                    description="Copy ideas into your own preset in “Your presets”",
                )
            )

    groups: dict[str, list[dict[str, Any]]] = {}
    for f in files:
        groups.setdefault(f["group"], []).append(f)

    return {
        "ok": True,
        "config_dir": str(config_dir()),
        "config_path": str(cfg_path),
        "user_presets_dir": str(user_dir),
        "max_bytes": MAX_BYTES,
        "files": files,
        "groups": [{"name": k, "files": v} for k, v in groups.items()],
    }


def _resolve_file_id(fid: str) -> tuple[Path, bool]:
    fid = (fid or "").strip()
    if fid == "config":
        return config_path(), True

    if fid.startswith("user/"):
        name = fid[5:]
        if not PRESET_NAME_RE.match(name):
            raise ValueError("invalid preset filename")
        return user_presets_dir() / name, True

    if fid.startswith("bundled/"):
        name = fid[len("bundled/") :]
        if not PRESET_NAME_RE.match(name):
            raise ValueError("invalid preset filename")
        return _bundled_presets_dir() / name, False

    raise ValueError("unknown file id")


def read_file(fid: str) -> dict[str, Any]:
    try:
        path, editable = _resolve_file_id(fid)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not path.is_file():
        if fid == "config":
            from nordctl.config import ensure_user_config

            ensure_user_config()
            path = config_path()
        else:
            return {"ok": False, "error": "file not found", "path": str(path)}

    size = path.stat().st_size
    if size > MAX_BYTES:
        return {
            "ok": False,
            "error": f"File too large for editor ({size} bytes; max {MAX_BYTES})",
            "path": str(path),
            "too_large": True,
        }

    text = path.read_text(encoding="utf-8")
    valid, yaml_err, yaml_line = _validate_yaml(text, fid == "config")

    return {
        "ok": True,
        "id": fid,
        "path": str(path),
        "content": text,
        "size": size,
        "editable": editable,
        "readonly": not editable,
        "modified": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "yaml_valid": valid,
        "yaml_error": yaml_err,
        "yaml_line": yaml_line,
    }


def _validate_yaml(text: str, is_main_config: bool) -> tuple[bool, str | None, int | None]:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        line = None
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        return False, str(exc), line
    if is_main_config and data is not None and not isinstance(data, dict):
        return False, "config.yaml must be a YAML mapping (key: value)", None
    return True, None, None


def validate_content(fid: str, content: str) -> dict[str, Any]:
    if len(content.encode("utf-8")) > MAX_BYTES:
        return {"ok": False, "error": f"Content exceeds {MAX_BYTES} byte limit"}
    valid, yaml_err, yaml_line = _validate_yaml(content, fid == "config")
    if not valid:
        return {
            "ok": False,
            "error": f"Invalid YAML: {yaml_err}",
            "yaml_error": yaml_err,
            "yaml_line": yaml_line,
        }
    return {"ok": True, "yaml_valid": True, "yaml_line": None}


def write_file(fid: str, content: str) -> dict[str, Any]:
    try:
        path, editable = _resolve_file_id(fid)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not editable:
        return {"ok": False, "error": "This file is read-only"}

    if len(content.encode("utf-8")) > MAX_BYTES:
        return {"ok": False, "error": f"Content exceeds {MAX_BYTES} byte limit"}

    valid, yaml_err, yaml_line = _validate_yaml(content, fid == "config")
    if not valid:
        return {"ok": False, "error": f"Invalid YAML: {yaml_err}", "yaml_error": yaml_err, "yaml_line": yaml_line}

    path.parent.mkdir(parents=True, exist_ok=True)

    if path.is_file():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    path.write_text(content, encoding="utf-8")

    result: dict[str, Any] = {
        "ok": True,
        "id": fid,
        "path": str(path),
        "backup": str(path.with_suffix(path.suffix + ".bak")) if path.with_suffix(path.suffix + ".bak").is_file() else None,
    }

    if fid == "config":
        try:
            cfg = load_config()
            result["config_reloaded"] = True
            result["wifi_profiles"] = list((cfg.get("wifi") or {}).get("profiles") or [])
        except Exception as exc:
            result["warning"] = f"Saved but reload check failed: {exc}"

    return result


def restore_file_from_baseline(fid: str) -> dict[str, Any]:
    """Copy one editable file from the install baseline snapshot back to its live path."""
    from nordctl.baseline import baseline_dir, baseline_exists

    if not baseline_exists():
        return {"ok": False, "error": "No install baseline — run nordctl init or Tools → Automate → Create baseline first"}

    try:
        path, editable = _resolve_file_id(fid)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not editable:
        return {"ok": False, "error": "This file cannot be restored from baseline"}

    root = baseline_dir()
    if fid == "config":
        src = root / "config.yaml"
    elif fid.startswith("user/"):
        name = fid[5:]
        src = root / "presets" / name
        if not src.is_file():
            if path.is_file():
                backup = path.with_suffix(path.suffix + ".bak")
                shutil.copy2(path, backup)
                path.unlink()
            return {
                "ok": True,
                "removed": True,
                "id": fid,
                "note": "This preset did not exist at install — removed the file.",
            }
    else:
        return {"ok": False, "error": "Only config.yaml and your presets can be restored here"}

    if fid == "config" and not src.is_file():
        return {"ok": False, "error": "Install baseline has no config.yaml snapshot"}

    if path.is_file():
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)

    path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, path)
    return {
        "ok": True,
        "id": fid,
        "path": str(path),
        "note": "Restored from install baseline.",
    }


def delete_user_preset(fid: str) -> dict[str, Any]:
    try:
        path, editable = _resolve_file_id(fid)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not fid.startswith("user/") or not editable:
        return {"ok": False, "error": "Only your custom preset files can be deleted"}

    if not path.is_file():
        return {"ok": False, "error": "Preset file not found"}

    if path.is_file():
        backup = path.with_suffix(path.suffix + ".deleted")
        shutil.copy2(path, backup)
        path.unlink()
    return {"ok": True, "id": fid, "note": "Preset deleted"}


def update_user_preset_meta(fid: str, body: dict[str, Any]) -> dict[str, Any]:
    try:
        path, editable = _resolve_file_id(fid)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not fid.startswith("user/") or not editable:
        return {"ok": False, "error": "Only your custom preset files can be edited here"}

    if not path.is_file():
        return {"ok": False, "error": "Preset file not found"}

    try:
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    if not isinstance(doc, dict):
        return {"ok": False, "error": "Preset file must be a YAML mapping"}

    changed = False
    for key in ("label", "summary", "category"):
        if key in body and body[key] is not None:
            text = str(body[key]).strip()
            if text:
                doc[key] = text
                changed = True

    if not changed:
        return {"ok": False, "error": "Nothing to update"}

    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.write_text(yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    return {"ok": True, "id": fid, "note": "Preset updated"}


def create_user_preset(name: str, *, template: str = "blank") -> dict[str, Any]:
    raw = (name or "").strip()
    if not raw.endswith(".yaml"):
        raw = f"{raw}.yaml"
    if not PRESET_NAME_RE.match(raw):
        return {
            "ok": False,
            "error": "Name must be lowercase letters, numbers, hyphens (e.g. my-stream.yaml)",
        }

    dest = user_presets_dir() / raw
    if dest.is_file():
        return {"ok": False, "error": "Preset already exists", "id": f"user/{raw}"}

    if template == "copy-example":
        example = _bundled_presets_dir() / "streaming-smartdns.yaml"
        if example.is_file():
            content = example.read_text(encoding="utf-8")
        else:
            content = _blank_preset(raw)
    else:
        content = _blank_preset(raw)

    dest.write_text(content, encoding="utf-8")
    return {"ok": True, "id": f"user/{raw}", "path": str(dest)}


def _blank_preset(filename: str) -> str:
    slug = filename.replace(".yaml", "").replace("-", "_")
    return f"""# Custom preset: {filename}
id: {slug}
label: My custom preset
summary: Describe what this preset does
category: Custom
steps:
  - nordvpn: disconnect
"""


def list_wifi_profiles() -> dict[str, Any]:
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": str(exc), "profiles": []}

    profiles: list[dict[str, str]] = []
    for line in (r.stdout or "").splitlines():
        parts = line.split(":")
        if len(parts) < 2:
            continue
        name, ctype = parts[0], parts[1]
        if ctype in ("802-11-wireless", "wifi") or "wireless" in ctype.lower():
            profiles.append({"name": name, "type": ctype})

    return {"ok": r.returncode == 0, "profiles": profiles}


def insert_wifi_profiles_into_config(profile_names: list[str]) -> dict[str, Any]:
    cfg = load_config()
    wifi = cfg.setdefault("wifi", {})
    existing = list(wifi.get("profiles") or [])
    merged = existing[:]
    for name in profile_names:
        n = str(name).strip()
        if n and n not in merged:
            merged.append(n)
    wifi["profiles"] = merged
    save_config(cfg)
    return {"ok": True, "profiles": merged, "path": str(config_path())}
