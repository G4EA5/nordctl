"""User-editable terminal quick commands stored in config.yaml."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import hashlib
import re
from typing import Any

SCOPES = ("network", "security", "nord")
SCOPE_LABELS = {
    "network": "Networking",
    "security": "Security",
    "nord": "Nord VPN",
}
MAX_COMMANDS_PER_SCOPE = 120
MAX_CUSTOM_CATEGORIES = 20
MAX_COMMANDS_PER_CATEGORY = 80


def _norm_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", (cmd or "").strip())


def _cmd_is_sudo(cmd: str) -> bool:
    return bool(re.match(r"^\s*sudo\b", cmd or ""))


def _slug(text: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return slug[:48] or "category"


def _command_id(scope: str, cmd: str) -> str:
    digest = hashlib.sha256(f"{scope}:{_norm_cmd(cmd)}".encode()).hexdigest()[:12]
    return f"cmd-{digest}"


def _quick_commands_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    term = cfg.setdefault("terminal", {})
    qc = term.setdefault("quick_commands", {})
    if "custom_categories" not in qc or not isinstance(qc.get("custom_categories"), list):
        qc["custom_categories"] = []
    return qc


def _normalize_command_row(row: dict[str, Any], scope: str, *, builtin: bool = False) -> dict[str, Any] | None:
    label = str(row.get("label") or "").strip()[:80]
    cmd = str(row.get("cmd") or "").strip()
    if not label or not cmd:
        return None
    if not cmd.endswith("\n"):
        cmd += "\n"
    cid = str(row.get("id") or "").strip() or _command_id(scope, cmd)
    return {
        "id": cid[:64],
        "label": label,
        "cmd": cmd,
        "enabled": row.get("enabled", True) is not False,
        "builtin": bool(builtin or row.get("builtin")),
        "sudo": bool(row.get("sudo")) or _cmd_is_sudo(cmd),
    }


def _default_scope_commands(scope: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    from nordctl.paths import PRIV_SUDOERS_SCRIPT, install_script_path, resolve_nordctl_bin
    from nordctl.terminal import (
        _builtin_cmd_available,
        _catalog_quick_commands,
        _merge_quick_commands,
        _networking_quick_commands,
        _nord_quick_commands,
        _security_quick_commands,
    )

    bin_path = resolve_nordctl_bin()
    priv_script = install_script_path(PRIV_SUDOERS_SCRIPT)
    scope_key = scope.strip().lower()
    if scope_key == "nord":
        raw = _nord_quick_commands(bin_path)
    elif scope_key == "security":
        builtins = [
            c
            for c in _security_quick_commands(bin_path, priv_script)
            if _builtin_cmd_available(str(c.get("cmd") or ""))
        ]
        catalog = _catalog_quick_commands("security", cfg)
        raw = _merge_quick_commands(builtins, catalog, "security")
    else:
        builtins = [
            c
            for c in _networking_quick_commands(bin_path)
            if _builtin_cmd_available(str(c.get("cmd") or ""))
        ]
        catalog = _catalog_quick_commands("network", cfg)
        raw = _merge_quick_commands(builtins, catalog, "network")

    out: list[dict[str, Any]] = []
    for item in raw:
        row = _normalize_command_row(item, scope_key, builtin=True)
        if row:
            out.append(row)
    return out


def _terminal_command_rows(rows: list[dict[str, Any]], scope: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in rows:
        if not row.get("enabled", True):
            continue
        cmd = str(row.get("cmd") or "").strip()
        if not cmd:
            continue
        out.append(
            {
                "id": row.get("id"),
                "label": row.get("label"),
                "cmd": cmd if cmd.endswith("\n") else f"{cmd}\n",
                "sudo": bool(row.get("sudo")) or _cmd_is_sudo(cmd),
                "scope": scope,
            }
        )
    return out


def _custom_categories(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    qc = _quick_commands_cfg(cfg)
    cats = qc.get("custom_categories") or []
    return [c for c in cats if isinstance(c, dict)]


def _package_category_command_rows(cat_id: str, cfg: dict[str, Any]) -> list[dict[str, Any]]:
    from nordctl.tool_install import custom_package_quick_commands

    scope = f"custom:{cat_id}"
    rows: list[dict[str, Any]] = []
    for pkg in custom_package_quick_commands(cat_id, cfg):
        row = _normalize_command_row(
            {
                "id": f"pkg-{pkg.get('tool_id') or _slug(str(pkg.get('label') or 'run'))}",
                "label": pkg.get("label"),
                "cmd": pkg.get("cmd"),
                "enabled": True,
            },
            scope,
        )
        if row:
            rows.append(row)
    return rows


def _display_custom_categories(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    from nordctl.tool_install import custom_package_shell_categories

    by_id: dict[str, dict[str, Any]] = {}
    for cat in custom_package_shell_categories(cfg):
        cid = str(cat.get("id") or "").strip()
        if not cid:
            continue
        by_id[cid] = {
            "id": cid,
            "label": str(cat.get("label") or cid),
            "commands": list(cat.get("commands") or []),
            "from_packages": True,
            "package_count": cat.get("package_count") or 0,
        }
    for cat in _custom_categories(cfg):
        cid = str(cat.get("id") or "").strip()
        if not cid:
            continue
        commands = [
            row
            for row in (_normalize_command_row(r, f"custom:{cid}") for r in (cat.get("commands") or []) if isinstance(r, dict))
            if row
        ]
        if cid in by_id:
            seen = {str(c.get("cmd") or "") for c in by_id[cid]["commands"]}
            for cmd in commands:
                key = str(cmd.get("cmd") or "")
                if key and key not in seen:
                    by_id[cid]["commands"].append(cmd)
                    seen.add(key)
            if not by_id[cid].get("label"):
                by_id[cid]["label"] = str(cat.get("label") or cid)
        else:
            by_id[cid] = {
                "id": cid,
                "label": str(cat.get("label") or cid),
                "commands": commands,
                "from_packages": False,
            }
    return list(by_id.values())


def _custom_category_commands(cat_id: str, cfg: dict[str, Any], *, enabled_only: bool) -> list[dict[str, Any]]:
    cid = (cat_id or "").strip()
    if not cid:
        return []
    scope = f"custom:{cid}"
    manual: list[dict[str, Any]] = []
    for cat in _custom_categories(cfg):
        if str(cat.get("id") or "").strip() != cid:
            continue
        rows = cat.get("commands") or []
        if not isinstance(rows, list):
            break
        manual = [
            row
            for row in (_normalize_command_row(r, scope) for r in rows if isinstance(r, dict))
            if row
        ]
        break
    package = _package_category_command_rows(cid, cfg)
    if enabled_only:
        combined = manual + [r for r in package if r.get("enabled", True)]
        return _terminal_command_rows(combined, scope)
    return manual + package


def effective_quick_commands(cfg: dict[str, Any] | None, scope: str) -> list[dict[str, Any]]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    scope_key = (scope or "network").strip().lower()
    if scope_key.startswith("custom:"):
        return _custom_category_commands(scope_key[7:], cfg, enabled_only=True)

    qc = _quick_commands_cfg(cfg)
    stored = qc.get(scope_key)
    if stored is None:
        return _terminal_command_rows(_default_scope_commands(scope_key, cfg), scope_key)

    if not isinstance(stored, list):
        return _terminal_command_rows(_default_scope_commands(scope_key, cfg), scope_key)

    normalized = [
        row
        for row in (_normalize_command_row(r, scope_key) for r in stored if isinstance(r, dict))
        if row
    ]
    return _terminal_command_rows(normalized, scope_key)


def settings_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    qc = _quick_commands_cfg(cfg)
    scopes: dict[str, Any] = {}
    for scope in SCOPES:
        stored = qc.get(scope)
        using_defaults = stored is None
        if using_defaults:
            commands = _default_scope_commands(scope, cfg)
        else:
            commands = [
                row
                for row in (
                    _normalize_command_row(r, scope) for r in (stored or []) if isinstance(r, dict)
                )
                if row
            ]
        scopes[scope] = {
            "label": SCOPE_LABELS[scope],
            "using_defaults": using_defaults,
            "commands": commands,
        }

    categories: list[dict[str, Any]] = []
    for cat in _display_custom_categories(cfg):
        cat_id = str(cat.get("id") or "").strip()
        label = str(cat.get("label") or cat_id).strip()
        if not cat_id:
            continue
        commands = [
            row
            for row in (_normalize_command_row(r, f"custom:{cat_id}") for r in (cat.get("commands") or []) if isinstance(r, dict))
            if row
        ]
        categories.append({"id": cat_id, "label": label or cat_id, "commands": commands})

    return {
        "ok": True,
        "scopes": scopes,
        "custom_categories": categories,
    }


def _validate_scope_commands(rows: list[Any], scope: str) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("commands must be a list")
    if len(rows) > MAX_COMMANDS_PER_SCOPE:
        raise ValueError(f"At most {MAX_COMMANDS_PER_SCOPE} commands per scope")
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        row = _normalize_command_row(raw, scope, builtin=bool(raw.get("builtin")))
        if not row:
            continue
        key = _norm_cmd(row["cmd"])
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def _validate_custom_categories(rows: list[Any]) -> list[dict[str, Any]]:
    if not isinstance(rows, list):
        raise ValueError("custom_categories must be a list")
    if len(rows) > MAX_CUSTOM_CATEGORIES:
        raise ValueError(f"At most {MAX_CUSTOM_CATEGORIES} custom categories")
    out: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        label = str(raw.get("label") or "").strip()[:80]
        cat_id = str(raw.get("id") or "").strip() or _slug(label)
        cat_id = _slug(cat_id)
        if not label:
            raise ValueError("Each custom category needs a label")
        if cat_id in seen_ids:
            raise ValueError(f"Duplicate custom category id: {cat_id}")
        seen_ids.add(cat_id)
        commands = _validate_scope_commands(raw.get("commands") or [], f"custom:{cat_id}")
        if len(commands) > MAX_COMMANDS_PER_CATEGORY:
            raise ValueError(f"At most {MAX_COMMANDS_PER_CATEGORY} commands per custom category")
        out.append({"id": cat_id, "label": label, "commands": commands})
    return out


def save_settings(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config, save_config

    cfg = cfg or load_config()
    qc = _quick_commands_cfg(cfg)

    if "scopes" in body and isinstance(body.get("scopes"), dict):
        for scope in SCOPES:
            if scope not in body["scopes"]:
                continue
            entry = body["scopes"][scope]
            if entry is None or entry.get("reset_defaults"):
                qc[scope] = None
                continue
            commands = _validate_scope_commands(entry.get("commands") or [], scope)
            qc[scope] = commands

    if "custom_categories" in body:
        qc["custom_categories"] = _validate_custom_categories(body.get("custom_categories") or [])

    save_config(cfg)
    return settings_payload(cfg)


def reset_scope(scope: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config, save_config

    cfg = cfg or load_config()
    scope_key = (scope or "").strip().lower()
    if scope_key not in SCOPES:
        raise ValueError("Unknown scope")
    qc = _quick_commands_cfg(cfg)
    qc[scope_key] = None
    save_config(cfg)
    return settings_payload(cfg)
