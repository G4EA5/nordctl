"""Save and restore NordVPN settings snapshots."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl import nordvpn as nv
from nordctl.config import config_dir, load_config

MAX_SNAPSHOTS = 10


def snapshots_dir() -> Path:
    d = config_dir() / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def capture_snapshot(label: str = "manual", cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {"ok": False, "error": "NordVPN CLI not available"}

    settings_r = nv.run(bin_path, ["settings"], timeout=10)
    status_r = nv.run(bin_path, ["status"], timeout=8)
    parsed = nv.parse_settings(settings_r.get("output", ""))

    snap = {
        "label": label,
        "ts": datetime.now(tz=timezone.utc).isoformat(),
        "settings_text": settings_r.get("output", ""),
        "status_text": status_r.get("output", ""),
        "settings": parsed,
    }
    sid = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    path = snapshots_dir() / f"{sid}.json"
    path.write_text(json.dumps(snap, indent=2), encoding="utf-8")
    latest = snapshots_dir() / "latest.json"
    latest.write_text(json.dumps(snap, indent=2), encoding="utf-8")

    _prune_old()
    return {"ok": True, "id": sid, "path": str(path), "label": label}


def list_snapshots() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for p in sorted(snapshots_dir().glob("*.json"), reverse=True):
        if p.name == "latest.json":
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            out.append({"id": p.stem, "label": data.get("label"), "ts": data.get("ts"), "path": str(p)})
        except (json.JSONDecodeError, OSError):
            continue
    return out[:MAX_SNAPSHOTS]


def _prune_old() -> None:
    files = sorted(snapshots_dir().glob("[0-9]*.json"), reverse=True)
    for p in files[MAX_SNAPSHOTS:]:
        p.unlink(missing_ok=True)


def apply_parsed_settings(settings: dict[str, Any], bin_path: str) -> list[dict[str, Any]]:
    """Re-apply NordVPN settings from parsed settings dict."""
    steps: list[dict[str, Any]] = []

    mapping = {
        "Kill Switch": ("killswitch",),
        "Firewall": ("firewall",),
        "Meshnet": ("meshnet",),
        "Auto-connect": ("autoconnect",),
        "LAN Discovery": ("lan-discovery",),
        "LAN discovery": ("lan-discovery",),
        "Routing": ("routing",),
        "Technology": ("technology",),
        "Threat Protection Lite": ("threatprotectionlite",),
        "DNS": ("dns",),
    }
    for key, (nord_key,) in mapping.items():
        val = settings.get(key)
        if not val:
            continue
        raw = str(val).strip()
        low = raw.lower()
        if nord_key == "dns":
            if "disabled" in low or low == "off":
                r = nv.run(bin_path, ["set", "dns", "off"], timeout=15)
            elif "enabled" in low:
                r = nv.run(bin_path, ["set", "dns", "on"], timeout=15)
            else:
                continue
        elif nord_key == "technology":
            r = nv.run(bin_path, ["set", "technology", raw.upper().split()[0]], timeout=15)
        else:
            v = raw.split()[0].lower()
            if v in ("enabled", "disabled", "on", "off"):
                v = "on" if v in ("enabled", "on") else "off"
                r = nv.run(bin_path, ["set", nord_key, v], timeout=15)
            else:
                continue
        steps.append(r)

    return steps


def restore_snapshot(snap_id: str | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {"ok": False, "error": "NordVPN CLI not available"}

    if snap_id:
        path = snapshots_dir() / f"{snap_id}.json"
    else:
        path = snapshots_dir() / "latest.json"
    if not path.is_file():
        return {"ok": False, "error": "No snapshot found"}

    snap = json.loads(path.read_text(encoding="utf-8"))
    settings = snap.get("settings") or {}
    steps = apply_parsed_settings(settings, bin_path)
    ok = all(s.get("ok", False) for s in steps) if steps else True
    return {"ok": ok, "restored_from": path.name, "steps": steps, "note": "Best-effort restore from snapshot"}
