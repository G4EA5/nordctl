"""User hook scripts — run before/after preset apply."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config

HOOK_TIMEOUT = 120


def hooks_root(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    custom = cfg.get("hooks_dir")
    if custom:
        return Path(str(custom)).expanduser()
    return config_dir() / "hooks"


def _hook_candidates(phase: str, preset_id: str, root: Path) -> list[Path]:
    phase_dir = root / phase
    if not phase_dir.is_dir():
        return []
    pid = preset_id.strip().lower()
    names = [pid, preset_id, "default"]
    out: list[Path] = []
    seen: set[str] = set()
    for name in names:
        for ext in ("", ".sh"):
            p = phase_dir / f"{name}{ext}"
            key = str(p)
            if key in seen:
                continue
            seen.add(key)
            if p.is_file() and os.access(p, os.X_OK):
                out.append(p)
    for p in sorted(phase_dir.glob("*.sh")):
        if p.is_file() and os.access(p, os.X_OK) and str(p) not in seen:
            if p.stem.lower() in (pid, "default"):
                out.append(p)
    return out


def run_preset_hooks(
    phase: str,
    preset_id: str,
    cfg: dict[str, Any] | None = None,
    *,
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run executable hooks in hooks/{pre-preset|post-preset}/."""
    cfg = cfg or load_config()
    if cfg.get("hooks_enabled") is False:
        return {"ok": True, "skipped": True, "ran": []}

    root = hooks_root(cfg)
    phase_key = "pre-preset" if phase == "pre" else "post-preset" if phase == "post" else phase
    scripts = _hook_candidates(phase_key, preset_id, root)
    ran: list[dict[str, Any]] = []

    env = os.environ.copy()
    env["NORDCTL_PRESET"] = preset_id
    env["NORDCTL_HOOK_PHASE"] = phase
    if result is not None:
        env["NORDCTL_PRESET_OK"] = "1" if result.get("ok") else "0"

    for script in scripts:
        try:
            proc = subprocess.run(
                [str(script)],
                capture_output=True,
                text=True,
                timeout=HOOK_TIMEOUT,
                env=env,
                cwd=str(root),
            )
            row = {
                "script": str(script),
                "ok": proc.returncode == 0,
                "exit_code": proc.returncode,
                "stdout": (proc.stdout or "")[:2000],
                "stderr": (proc.stderr or "")[:2000],
            }
            ran.append(row)
            if phase == "pre" and proc.returncode != 0:
                return {
                    "ok": False,
                    "blocked": True,
                    "message": f"Pre-preset hook failed: {script.name} (exit {proc.returncode})",
                    "ran": ran,
                }
        except subprocess.TimeoutExpired:
            ran.append({"script": str(script), "ok": False, "error": "timeout"})
            if phase == "pre":
                return {"ok": False, "blocked": True, "message": f"Pre-preset hook timed out: {script.name}", "ran": ran}
        except OSError as exc:
            ran.append({"script": str(script), "ok": False, "error": str(exc)})

    return {"ok": True, "ran": ran}


def hooks_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    root = hooks_root(cfg or load_config())
    phases = {}
    for name in ("pre-preset", "post-preset"):
        d = root / name
        if d.is_dir():
            phases[name] = [p.name for p in sorted(d.iterdir()) if p.is_file()]
        else:
            phases[name] = []
    return {
        "ok": True,
        "root": str(root),
        "phases": phases,
        "docs": "See docs/HOOKS.md — executable scripts named {preset-id} or default",
    }
