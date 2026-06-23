"""Persist speed test results under ~/.config/nordctl/speed_tests.jsonl."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import csv
import io
import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl.config import config_dir

MAX_ENTRIES = 200
LOG_FILE = config_dir() / "speed_tests.jsonl"
EXPORT_DIR = config_dir() / "exports"


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _log_path() -> Path:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return LOG_FILE


def _read_all() -> list[dict[str, Any]]:
    path = _log_path()
    if not path.is_file():
        return []
    out: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
            if isinstance(row, dict):
                out.append(row)
        except json.JSONDecodeError:
            continue
    return out


def _write_all(entries: list[dict[str, Any]]) -> None:
    path = _log_path()
    text = "\n".join(json.dumps(e, ensure_ascii=False) for e in entries)
    if text:
        text += "\n"
    path.write_text(text, encoding="utf-8")


def list_entries(*, limit: int = 100) -> list[dict[str, Any]]:
    lim = min(max(int(limit or 100), 1), MAX_ENTRIES)
    rows = _read_all()
    rows.reverse()
    return rows[:lim]


def append_result(payload: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "id": str(payload.get("id") or uuid.uuid4()),
        "ts": int(payload.get("ts") or time.time() * 1000),
        "ts_iso": str(payload.get("ts_iso") or _now_iso()),
        "mbps": float(payload.get("mbps") or 0),
        "bytes": payload.get("bytes"),
        "seconds": payload.get("seconds"),
        "profile": payload.get("profile"),
        "profile_label": payload.get("profile_label"),
        "method": payload.get("method"),
        "provider": payload.get("provider"),
        "provider_label": payload.get("provider_label"),
        "warmup": bool(payload.get("warmup")),
        "vpn": bool(payload.get("vpn")),
        "route": payload.get("route"),
        "dns": payload.get("dns"),
        "dns_label": payload.get("dns_label"),
        "url": payload.get("url"),
        "human": payload.get("human"),
        "runs": payload.get("runs"),
    }
    rows = _read_all()
    rows.append(entry)
    if len(rows) > MAX_ENTRIES:
        rows = rows[-MAX_ENTRIES:]
    _write_all(rows)
    return entry


def clear_entries() -> dict[str, Any]:
    path = _log_path()
    if path.is_file():
        path.unlink()
    return {"ok": True, "cleared": True}


def history_payload(*, limit: int = 100) -> dict[str, Any]:
    entries = list_entries(limit=limit)
    return {
        "ok": True,
        "entries": entries,
        "count": len(entries),
        "path": str(_log_path()),
        "max": MAX_ENTRIES,
    }


def _entries_to_csv(entries: list[dict[str, Any]]) -> str:
    buf = io.StringIO()
    fields = [
        "ts_iso", "mbps", "vpn", "route", "dns", "dns_label",
        "profile_label", "method", "provider_label", "warmup", "bytes", "seconds", "url", "id",
    ]
    w = csv.DictWriter(buf, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    for row in entries:
        w.writerow({k: row.get(k, "") for k in fields})
    return buf.getvalue()


def export_results(*, fmt: str = "json", limit: int = MAX_ENTRIES) -> dict[str, Any]:
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    entries = list_entries(limit=limit)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    fmt_l = (fmt or "json").lower()
    if fmt_l == "csv":
        content = _entries_to_csv(entries)
        path = EXPORT_DIR / f"speed-tests-{stamp}.csv"
        path.write_text(content, encoding="utf-8")
        return {
            "ok": True,
            "format": "csv",
            "count": len(entries),
            "path": str(path),
            "content": content,
            "filename": path.name,
        }
    content_obj = {"exported": _now_iso(), "count": len(entries), "runs": entries}
    content = json.dumps(content_obj, indent=2, ensure_ascii=False)
    path = EXPORT_DIR / f"speed-tests-{stamp}.json"
    path.write_text(content + "\n", encoding="utf-8")
    return {
        "ok": True,
        "format": "json",
        "count": len(entries),
        "path": str(path),
        "content": content,
        "filename": path.name,
    }
