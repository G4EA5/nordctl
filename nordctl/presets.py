"""Preset loader and execution engine."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

import yaml

from nordctl.actions import describe_step, run_step, substitute
from nordctl.config import load_config, presets_directory

PRESET_REGION_BY_ID: dict[str, str] = {
    "eu-privacy": "europe",
    "uk-streaming": "europe",
    "us-streaming-dns": "americas",
    "latam-public": "americas",
    "apac-travel": "asia-pacific",
    "global-mobile": "global",
}


def preset_region(preset: dict[str, Any]) -> str:
    """Geographic grouping for UI — legal generic labels only."""
    explicit = preset.get("region")
    if explicit:
        return str(explicit).strip().lower()
    pid = str(preset.get("id", "")).strip().lower()
    if pid in PRESET_REGION_BY_ID:
        return PRESET_REGION_BY_ID[pid]
    if str(preset.get("category", "")).strip().lower() == "regional":
        return "global"
    return "general"


def load_presets(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    root = presets_directory(cfg)
    presets: list[dict[str, Any]] = []
    if not root.is_dir():
        return presets
    for path in sorted(root.glob("*.yaml")):
        with path.open(encoding="utf-8") as fh:
            doc = yaml.safe_load(fh) or {}
        if doc.get("id"):
            doc["_path"] = str(path)
            presets.append(doc)

    comm = root / "community"
    seen_early = {str(p.get("id", "")).lower() for p in presets}
    if comm.is_dir():
        for path in sorted(comm.glob("*.yaml")):
            with path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
            pid = str(doc.get("id") or path.stem).strip()
            if not pid or pid.lower() in seen_early:
                continue
            doc["id"] = pid
            doc["community"] = True
            doc["_path"] = str(path)
            presets.append(doc)
            seen_early.add(pid.lower())

    from nordctl.files import user_presets_dir

    seen = {str(p.get("id", "")).lower() for p in presets}
    udir = user_presets_dir()
    for path in sorted(udir.glob("*.yaml")):
        try:
            with path.open(encoding="utf-8") as fh:
                doc = yaml.safe_load(fh) or {}
        except OSError:
            continue
        pid = str(doc.get("id") or path.stem).strip()
        if not pid or pid.lower() in seen:
            continue
        doc["id"] = pid
        doc["_path"] = str(path)
        doc["user"] = True
        doc["_file_id"] = f"user/{path.name}"
        presets.append(doc)
        seen.add(pid.lower())
    return presets


def get_preset(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    pid = preset_id.strip().lower()
    for p in load_presets(cfg):
        if str(p.get("id", "")).lower() == pid:
            return p
    return None


def _check_requires(preset: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    from nordctl.config_fields import missing_requirement

    for req in preset.get("requires") or []:
        val = cfg.get(req)
        if not val:
            return missing_requirement(str(req), cfg)
    return None


def _classify_effect(step: dict[str, Any], effects: dict[str, list[str]], cfg: dict[str, Any]) -> None:
    action = str(step.get("action") or "").strip()
    text = describe_step(step, cfg)
    if action in ("nordvpn_connect", "nordvpn_reconnect", "nordvpn_disconnect"):
        effects["vpn"].append(text)
    elif action in ("network_smart_dns", "network_restore_dns", "nordvpn_set") and "dns" in action.lower():
        effects["dns"].append(text)
    elif "dns" in action or str(step.get("key") or "").lower() == "dns":
        effects["dns"].append(text)
    elif action.startswith("meshnet") or action == "meshnet_peer_connect":
        effects["meshnet"].append(text)
    elif "allowlist" in action or action == "nordvpn_settings":
        effects["firewall"].append(text)
    elif action.startswith("network_"):
        effects["network"].append(text)
    else:
        effects["network"].append(text)


def dry_run_preset(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"unknown preset: {preset_id}"}

    missing = _check_requires(preset, cfg)
    steps: list[dict[str, Any]] = []
    effects: dict[str, list[str]] = {
        "vpn": [],
        "dns": [],
        "meshnet": [],
        "firewall": [],
        "network": [],
    }
    for i, step in enumerate(preset.get("steps") or [], start=1):
        if not isinstance(step, dict):
            continue
        steps.append({
            "n": i,
            "text": describe_step(step, cfg),
            "action": step.get("action"),
        })
        _classify_effect(step, effects, cfg)

    return {
        "ok": True,
        "dry_run": True,
        "preset": preset_id,
        "label": preset.get("label"),
        "category": preset.get("category"),
        "summary": preset.get("summary"),
        "steps": steps,
        "effects": effects,
        "step_count": len(steps),
        "missing_config": missing.get("message") if missing else None,
        "missing_field": missing,
        "would_apply": missing is None,
    }


def apply_preset(
    preset_id: str,
    cfg: dict[str, Any] | None = None,
    *,
    dry_run: bool = False,
    verify: bool = True,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    if dry_run:
        return dry_run_preset(preset_id, cfg)

    from nordctl.demo_mode import is_demo_mode, simulate_preset_apply

    if is_demo_mode(cfg):
        return simulate_preset_apply(preset_id, cfg)

    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"unknown preset: {preset_id}"}

    missing = _check_requires(preset, cfg)
    if missing:
        return {
            "ok": False,
            "error": missing["message"],
            "missing_field": missing,
            "preset": preset_id,
            "preset_label": preset.get("label"),
        }

    from nordctl.hooks import run_preset_hooks

    pre_hooks = run_preset_hooks("pre", preset_id, cfg)
    if pre_hooks.get("blocked"):
        return {
            "ok": False,
            "error": pre_hooks.get("message") or "Pre-preset hook blocked apply",
            "hooks": pre_hooks,
            "preset": preset_id,
        }

    if cfg.get("auto_snapshot_before_preset", True):
        from nordctl.snapshot import capture_snapshot

        capture_snapshot(label=f"before-{preset_id}", cfg=cfg)

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    steps: list[dict[str, Any]] = []

    for step in preset.get("steps") or []:
        run_step(step, cfg, bin_path, steps)

    ok = all(
        s.get("ok", False)
        for s in steps
        if not (s.get("args") and s["args"][:1] == ["allowlist"])
    )

    from nordctl.state import build_state

    state = build_state(cfg)
    note = preset.get("note")
    if note:
        note = substitute(str(note), cfg)
    elif preset_id == "streaming-smartdns" and ok:
        pub = (state.get("smart_dns") or {}).get("public_ip") or "your public IP"
        note = (
            f"TV streaming (Smart DNS) active. Allowlist {pub} in your Nord Account "
            "if playback is blocked. See LEGAL.md — comply with provider terms."
        )

    result: dict[str, Any] = {
        "ok": ok,
        "preset": preset_id,
        "label": preset.get("label"),
        "category": preset.get("category"),
        "steps": steps,
        "state": state,
        "note": note,
    }
    if verify and ok:
        from nordctl.preset_verify import verify_after_preset

        result["verification"] = verify_after_preset(cfg, preset_id)

    post_hooks = run_preset_hooks("post", preset_id, cfg, result=result)
    if post_hooks.get("ran"):
        result["hooks"] = {"pre": pre_hooks.get("ran") or [], "post": post_hooks.get("ran")}

    from nordctl.connection_journal import record_preset_apply

    sd = (state.get("smart_dns") or {}) if isinstance(state, dict) else {}
    zones = state.get("zones") or {} if isinstance(state, dict) else {}
    record_preset_apply(
            preset_id,
            label=str(preset.get("label") or preset_id),
            ok=ok,
            dry_run=False,
            demo=is_demo_mode(cfg),
            verification=result.get("verification"),
            public_ip=sd.get("public_ip") or (state.get("status") or {}).get("IP"),
            ssid=zones.get("ssid"),
            note=str(result.get("note") or ""),
        )
    return result


def export_preset_yaml(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from pathlib import Path

    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"Unknown preset: {preset_id}"}
    path = preset.get("_path")
    if not path:
        return {"ok": False, "error": "Preset file path not found"}
    p = Path(str(path))
    if not p.is_file():
        return {"ok": False, "error": "Preset file not found"}
    text = p.read_text(encoding="utf-8")
    return {
        "ok": True,
        "id": preset.get("id"),
        "label": preset.get("label"),
        "content": text,
        "filename": p.name,
        "user": bool(preset.get("user")),
    }


def preview_preset_yaml(content: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Parse preset YAML and return human-readable step preview."""
    from nordctl.actions import describe_step

    cfg = cfg or load_config()
    try:
        doc = yaml.safe_load(content) or {}
    except yaml.YAMLError as exc:
        line = None
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
        return {"ok": False, "error": str(exc), "line": line}

    if not isinstance(doc, dict):
        return {"ok": False, "error": "Preset must be a YAML mapping"}

    steps_raw = doc.get("steps") or []
    if not isinstance(steps_raw, list):
        return {"ok": False, "error": "steps must be a list"}

    missing = _check_requires(doc, cfg)
    preview_steps = []
    for i, step in enumerate(steps_raw, start=1):
        if not isinstance(step, dict):
            preview_steps.append({"n": i, "text": "Invalid step (not a mapping)", "warn": True})
            continue
        preview_steps.append({"n": i, "text": describe_step(step, cfg), "warn": False})

    return {
        "ok": True,
        "id": doc.get("id"),
        "label": doc.get("label"),
        "summary": doc.get("summary"),
        "category": doc.get("category"),
        "requires": doc.get("requires") or [],
        "missing_config": missing.get("message") if missing else None,
        "missing_field": missing,
        "steps": preview_steps,
        "step_count": len(preview_steps),
    }
