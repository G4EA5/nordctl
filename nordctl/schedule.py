"""Generate systemd user timers for scheduled presets."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config, save_config


def _systemd_user_dir() -> Path:
    d = Path.home() / ".config" / "systemd" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def list_schedules(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    return list(cfg.get("schedules") or [])


def add_schedule(entry: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    schedules = list(cfg.get("schedules") or [])
    sid = str(entry.get("id") or f"job-{len(schedules)+1}")
    job = {
        "id": sid,
        "preset": str(entry.get("preset") or ""),
        "time": str(entry.get("time") or "18:00"),
        "days": entry.get("days") or "Mon..Sun",
        "enabled": bool(entry.get("enabled", True)),
    }
    if not job["preset"]:
        return {"ok": False, "error": "preset required"}
    schedules = [s for s in schedules if s.get("id") != sid]
    schedules.append(job)
    cfg["schedules"] = schedules
    save_config(cfg)
    write_systemd_units(schedules)
    return {"ok": True, "schedule": job}


def remove_schedule(sid: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    schedules = [s for s in (cfg.get("schedules") or []) if s.get("id") != sid]
    cfg["schedules"] = schedules
    save_config(cfg)
    _systemd_user_dir().joinpath(f"nordctl-{sid}.timer").unlink(missing_ok=True)
    _systemd_user_dir().joinpath(f"nordctl-{sid}.service").unlink(missing_ok=True)
    return {"ok": True}


def write_systemd_units(schedules: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    schedules = schedules if schedules is not None else list_schedules()
    d = _systemd_user_dir()
    written: list[str] = []
    for job in schedules:
        if not job.get("enabled"):
            continue
        sid = job["id"]
        preset = job["preset"]
        time_spec = job.get("time") or "18:00"
        hour, minute = time_spec.split(":") if ":" in time_spec else ("18", "00")
        service = d / f"nordctl-{sid}.service"
        timer = d / f"nordctl-{sid}.timer"
        service.write_text(
            f"""[Unit]
Description=nordctl preset {preset}

[Service]
Type=oneshot
ExecStart=%h/.local/bin/nordctl apply {preset}
""",
            encoding="utf-8",
        )
        timer.write_text(
            f"""[Unit]
Description=nordctl schedule {sid}

[Timer]
OnCalendar={job.get('days', 'Mon..Sun')} *-*-* {hour}:{minute}:00
Persistent=true

[Install]
WantedBy=timers.target
""",
            encoding="utf-8",
        )
        written.extend([str(service), str(timer)])
    return {
        "ok": True,
        "written": written,
        "enable_hint": "systemctl --user daemon-reload && systemctl --user enable --now nordctl-<id>.timer",
    }
