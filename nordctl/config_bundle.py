"""Export/import config bundles with secrets stripped."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import re
import shutil
import tarfile
import tempfile
import time
from pathlib import Path
from typing import Any

import yaml

from nordctl.config import config_dir, config_path, load_config, save_config

REDACT_PLACEHOLDER = "REDACTED"

REDACT_PATHS: tuple[tuple[str, ...], ...] = (
    ("server", "ui_password_hash"),
    ("server", "ui_password_salt"),
    ("alerts", "email", "smtp_password"),
    ("security", "status_page", "token"),
    ("alerts", "webhook", "url"),
)


def _get_nested(d: dict[str, Any], path: tuple[str, ...]) -> Any:
    cur: Any = d
    for key in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(key)
    return cur


def _set_nested(d: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    cur = d
    for key in path[:-1]:
        cur = cur.setdefault(key, {})
    cur[path[-1]] = value


def redact_config(cfg: dict[str, Any]) -> dict[str, Any]:
    out = yaml.safe_load(yaml.safe_dump(cfg)) or {}
    for path in REDACT_PATHS:
        if _get_nested(out, path):
            _set_nested(out, path, REDACT_PLACEHOLDER)
    return out


def export_config_bundle(*, include_activity: bool = True) -> dict[str, Any]:
    d = config_dir()
    out = d / "exports"
    out.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    archive = out / f"nordctl-export-{ts}.tar.gz"
    manifest: dict[str, Any] = {
        "format": "nordctl-config-bundle",
        "version": 1,
        "exported_at": ts,
        "redacted_keys": [".".join(p) for p in REDACT_PATHS],
    }

    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            cfg = load_config()
            redacted = redact_config(cfg)
            (tmp_path / "config.yaml").write_text(
                yaml.safe_dump(redacted, sort_keys=False),
                encoding="utf-8",
            )
            (tmp_path / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

            presets = d / "presets"
            if presets.is_dir():
                dest_presets = tmp_path / "presets"
                dest_presets.mkdir()
                for f in presets.glob("*.yaml"):
                    shutil.copy2(f, dest_presets / f.name)

            with tarfile.open(archive, "w:gz") as tar:
                for f in tmp_path.rglob("*"):
                    if f.is_file():
                        tar.add(f, arcname=str(f.relative_to(tmp_path)))

        return {
            "ok": True,
            "path": str(archive),
            "redacted": True,
            "note": "Secrets redacted (SMTP password, lab password hash, status token, webhook URL). Restore SMTP and tokens after import.",
        }
    except OSError as exc:
        return {"ok": False, "error": str(exc)}


def import_config_bundle(archive_path: str, *, merge: bool = True) -> dict[str, Any]:
    path = Path(archive_path).expanduser()
    if not path.is_file():
        return {"ok": False, "error": f"Archive not found: {path}"}

    d = config_dir()
    d.mkdir(parents=True, exist_ok=True)
    imported: list[str] = []

    try:
        with tarfile.open(path, "r:gz") as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            names = {m.name for m in members}
            if "config.yaml" not in names:
                return {"ok": False, "error": "Invalid bundle — missing config.yaml"}

            with tempfile.TemporaryDirectory() as tmp:
                tmp_path = Path(tmp)
                tar.extractall(tmp_path, members=members)

                cfg_file = tmp_path / "config.yaml"
                incoming = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
                if not isinstance(incoming, dict):
                    return {"ok": False, "error": "Invalid config.yaml in bundle"}

                for path_keys in REDACT_PATHS:
                    val = _get_nested(incoming, path_keys)
                    if val in (REDACT_PLACEHOLDER, None, ""):
                        _set_nested(incoming, path_keys, None)

                if merge and config_path().is_file():
                    current = load_config()
                    _deep_merge_import(current, incoming)
                    save_config(current)
                else:
                    save_config(incoming)
                imported.append("config.yaml")

                presets_src = tmp_path / "presets"
                if presets_src.is_dir():
                    dest = d / "presets"
                    dest.mkdir(parents=True, exist_ok=True)
                    for f in presets_src.glob("*.yaml"):
                        target = dest / f.name
                        if target.exists() and merge:
                            stem = f.stem
                            target = dest / f"{stem}-imported.yaml"
                        shutil.copy2(f, target)
                        imported.append(f"presets/{target.name}")

        return {
            "ok": True,
            "imported": imported,
            "merge": merge,
            "note": "Re-enter SMTP password and lab password in Settings if you use them.",
        }
    except (OSError, tarfile.TarError, yaml.YAMLError) as exc:
        return {"ok": False, "error": str(exc)}


def _deep_merge_import(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, val in override.items():
        if val is None:
            continue
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _deep_merge_import(base[key], val)
        else:
            base[key] = val
