"""Factory reset — undo all nordctl changes and return to pre-install system state."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config, save_config


def _remove_nordctl_systemd_units() -> dict[str, Any]:
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    removed: list[str] = []
    if not systemd_dir.is_dir():
        return {"ok": True, "removed": removed}
    for pattern in ("nordctl-*.service", "nordctl-*.timer", "nordctl-ui.service", "nordctl-tray.service"):
        for p in systemd_dir.glob(pattern):
            try:
                name = p.name
                shutil.which("systemctl") and _systemctl_user_disable(name)
                p.unlink(missing_ok=True)
                removed.append(name)
            except OSError:
                pass
    return {"ok": True, "removed": removed}


def _systemctl_user_disable(unit: str) -> None:
    import subprocess

    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", unit],
            capture_output=True,
            timeout=15,
        )
        subprocess.run(["systemctl", "--user", "daemon-reload"], capture_output=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass


def _clear_data_dirs() -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    root = config_dir()

    from nordctl.snapshot import snapshots_dir

    snap = snapshots_dir()
    if snap.is_dir():
        shutil.rmtree(snap)
        snap.mkdir(parents=True, exist_ok=True)
        steps.append({"step": "snapshots", "ok": True})

    exports = root / "exports"
    if exports.is_dir():
        shutil.rmtree(exports)
        steps.append({"step": "exports", "ok": True})

    captures = root / "captures"
    if captures.is_dir():
        shutil.rmtree(captures)
        steps.append({"step": "captures", "ok": True})

    for name in ("activity.jsonl", "alerts.jsonl"):
        p = root / name
        if p.is_file():
            p.unlink()
            steps.append({"step": name, "ok": True})

    return steps


def factory_reset(
    cfg: dict[str, Any] | None = None,
    *,
    restore_resolv: bool = False,
) -> dict[str, Any]:
    """Restore baseline, remove nordctl services/schedules, and reset local nordctl data."""
    from nordctl.baseline import baseline_exists, restore_baseline

    cfg = cfg or load_config()
    steps: list[dict[str, Any]] = []

    try:
        from nordctl.disconnect_watch import stop_disconnect_watch

        steps.append({"step": "stop_disconnect_watch", **stop_disconnect_watch()})
    except Exception as exc:
        steps.append({"step": "stop_disconnect_watch", "ok": False, "error": str(exc)})

    try:
        from nordctl.wifi_zone_watch import stop_zone_watch

        steps.append({"step": "stop_zone_watch", **stop_zone_watch()})
    except Exception as exc:
        steps.append({"step": "stop_zone_watch", "ok": False, "error": str(exc)})

    try:
        from nordctl.alerts import stop_alerts_watch

        steps.append({"step": "stop_alerts_watch", **stop_alerts_watch()})
    except Exception as exc:
        steps.append({"step": "stop_alerts_watch", "ok": False, "error": str(exc)})

    try:
        from nordctl.status_share import set_status_page_enabled

        steps.append({"step": "status_page_off", **set_status_page_enabled(False, cfg)})
    except Exception as exc:
        steps.append({"step": "status_page_off", "ok": False, "error": str(exc)})

    try:
        from nordctl.service_mgr import uninstall_ui_service

        steps.append({"step": "ui_service", **uninstall_ui_service(cfg)})
    except Exception as exc:
        steps.append({"step": "ui_service", "ok": False, "error": str(exc)})

    try:
        from nordctl.tray import uninstall_tray

        steps.append({"step": "tray", **uninstall_tray()})
    except Exception as exc:
        steps.append({"step": "tray", "ok": False, "error": str(exc)})

    unit_step = _remove_nordctl_systemd_units()
    steps.append({"step": "systemd_units", **unit_step})

    cfg = load_config()
    cfg["schedules"] = []
    save_config(cfg)
    steps.append({"step": "clear_schedules", "ok": True})

    had_baseline = baseline_exists()
    if had_baseline:
        restore_result = restore_baseline(cfg, restore_resolv=restore_resolv)
        steps.append({"step": "restore_baseline", **restore_result})
        cfg = load_config()
    else:
        steps.append({
            "step": "restore_baseline",
            "ok": False,
            "error": "No install baseline — run nordctl init or Create baseline first",
            "skipped": True,
        })

    cfg = load_config()
    features = cfg.setdefault("features", {})
    features["onboarding_complete"] = False
    features["legal_accepted"] = False
    cfg["schedules"] = []
    sec = cfg.setdefault("security", {})
    sp = sec.setdefault("status_page", {})
    sp["enabled"] = False
    save_config(cfg)
    steps.append({"step": "reset_onboarding", "ok": True})

    steps.extend(_clear_data_dirs())

    from nordctl.activity_log import record_event

    record_event(
        "system",
        "Factory reset completed",
        detail=(
            "Restored install baseline where available, removed nordctl services and timers, "
            "cleared logs and snapshots. Re-run ./install.sh or onboarding to set up again."
        ),
        level="info",
        ok=True,
    )

    baseline_ok = any(
        isinstance(s, dict) and s.get("step") == "restore_baseline" and s.get("ok") for s in steps
    )
    ok = baseline_ok if had_baseline else False
    return {
        "ok": ok,
        "steps": steps,
        "baseline_used": baseline_exists(),
        "note": (
            "Factory reset complete — your system should match the state saved at first nordctl init. "
            "Refresh the page or run nordctl serve again. If DNS still looks wrong, reboot once."
        ),
        "warning": (
            None
            if baseline_ok
            else "Baseline was missing — services and nordctl data were cleared but network/Nord state may need manual fix."
        ),
    }
