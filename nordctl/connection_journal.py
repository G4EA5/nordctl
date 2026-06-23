"""Dedicated local journal for preset applies — structured JSON, no cloud."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl.config import config_dir

JOURNAL_FILE = config_dir() / "journal.jsonl"
MAX_ENTRIES = 250


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _trim(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    path.write_text("\n".join(lines[-MAX_ENTRIES:]) + "\n", encoding="utf-8")


def record_preset_apply(
    preset_id: str,
    *,
    label: str | None = None,
    ok: bool = True,
    dry_run: bool = False,
    demo: bool = False,
    verification: dict[str, Any] | None = None,
    public_ip: str | None = None,
    ssid: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "id": f"j{int(time.time() * 1000)}",
        "ts": _now_iso(),
        "event": "preset_apply",
        "preset": preset_id,
        "label": label or preset_id,
        "ok": ok,
        "dry_run": dry_run,
        "demo": demo,
        "public_ip": public_ip,
        "ssid": ssid,
        "note": (note or "")[:500],
    }
    if verification:
        entry["verification"] = {
            "ok": verification.get("ok"),
            "summary": verification.get("summary"),
            "passed": verification.get("passed"),
            "total": verification.get("total"),
        }

    path = JOURNAL_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _trim(path)
    return entry


def list_journal(*, limit: int = 40, preset: str | None = None) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    if JOURNAL_FILE.is_file():
        try:
            lines = JOURNAL_FILE.read_text(encoding="utf-8").splitlines()
        except OSError:
            lines = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            if preset and str(e.get("preset") or "").lower() != preset.lower():
                continue
            entries.append(e)
            if len(entries) >= limit:
                break
    return {
        "ok": True,
        "entries": entries,
        "path": str(JOURNAL_FILE),
        "note": "Local preset journal — safe to share summary lines; redact SSIDs if posting publicly.",
    }
