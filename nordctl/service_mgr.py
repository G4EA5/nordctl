"""systemd user service for nordctl UI + nordvpnd status/control."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from nordctl.config import load_config, save_config
from nordctl.paths import resolve_nordctl_bin
from nordctl.ports import detect_nordctl_listen, is_port_free

UI_UNIT = "nordctl-ui.service"
NORD_UNIT = "nordvpnd.service"


def _nordctl_bin() -> str:
    return resolve_nordctl_bin()


def _server_bind_port(cfg: dict[str, Any]) -> tuple[str, int]:
    srv = cfg.get("server") or {}
    bind = str(srv.get("bind") or "127.0.0.1")
    port = int(srv.get("port") or 8765)
    return bind, port


def _wait_port_free(host: str, port: int, *, seconds: float = 6.0) -> bool:
    import time

    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if is_port_free(host, port):
            return True
        time.sleep(0.25)
    return is_port_free(host, port)


def _spawn_detached(argv: list[str]) -> bool:
    try:
        subprocess.Popen(
            argv,
            start_new_session=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        return True
    except OSError:
        return False


def _manual_serve_pids(*, exclude: list[int] | None = None) -> list[int]:
    ok, out = _run(["pgrep", "-f", r"nordctl serve"], timeout=5)
    if not ok or not out:
        return []
    skip = set(exclude or [])
    pids: list[int] = []
    for part in out.split():
        try:
            pid = int(part)
        except ValueError:
            continue
        if pid not in skip:
            pids.append(pid)
    return pids


def stop_manual_serve_processes(*, exclude: list[int] | None = None) -> dict[str, Any]:
    """Stop background `nordctl serve` processes not managed by systemd."""
    pids = _manual_serve_pids(exclude=exclude)
    stopped: list[int] = []
    errors: list[str] = []
    for pid in pids:
        ok, out = _run(["kill", str(pid)], timeout=3)
        if ok:
            stopped.append(pid)
        else:
            errors.append(f"pid {pid}: {out}")
    if stopped:
        import time

        time.sleep(0.6)
        for pid in list(stopped):
            if pid in _manual_serve_pids(exclude=exclude):
                _run(["kill", "-9", str(pid)], timeout=3)
    return {"stopped": stopped, "errors": errors, "remaining": _manual_serve_pids(exclude=exclude)}


def schedule_ui_restart(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Restart UI from an in-process API handler without suicide before systemctl runs."""
    cfg = cfg or load_config()
    bind, port = _server_bind_port(cfg)
    bin_path = _nordctl_bin()
    write_ui_unit(cfg)
    _systemctl_user("daemon-reload")
    log_dir = Path.home() / ".local" / "share" / "nordctl"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "serve.log"
    if os.environ.get("CI") or os.environ.get("GITHUB_ACTIONS"):
        script = (
            "set +e\n"
            "sleep 1\n"
            f"systemctl --user daemon-reload 2>/dev/null\n"
            f"systemctl --user restart {UI_UNIT} 2>/dev/null || systemctl --user start {UI_UNIT} 2>/dev/null\n"
        )
    else:
        script = (
            "set +e\n"
            "sleep 1\n"
            "systemctl --user daemon-reload 2>/dev/null\n"
            f"systemctl --user restart {UI_UNIT} 2>/dev/null || systemctl --user start {UI_UNIT} 2>/dev/null\n"
            "sleep 2\n"
            f"if ! systemctl --user is-active --quiet {UI_UNIT} 2>/dev/null; then\n"
            f"  pkill -f '{bin_path} serve' 2>/dev/null\n"
            "  sleep 0.5\n"
            f"  nohup {bin_path} serve --bind {bind} --port {port} >>{log_path} 2>&1 &\n"
            "fi\n"
        )
    if not _spawn_detached(["bash", "-c", script]):
        return {"ok": False, "error": "Could not schedule UI restart worker"}
    return {
        "ok": True,
        "scheduled": True,
        "url": _dashboard_url(cfg),
        "note": f"Restarting UI — refresh {_dashboard_url(cfg)} in a few seconds.",
        "status": ui_service_status(cfg),
        "bin": bin_path,
    }


def _user_systemd_dir() -> Path:
    d = Path.home() / ".config" / "systemd" / "user"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ui_unit_path() -> Path:
    return _user_systemd_dir() / UI_UNIT


def _run(argv: list[str], timeout: float = 15.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _systemctl_user(*args: str) -> dict[str, Any]:
    ok, out = _run(["systemctl", "--user", *args], timeout=20)
    return {"ok": ok, "output": out, "command": "systemctl --user " + " ".join(args)}


def _systemctl_system(*args: str) -> dict[str, Any]:
    ok, out = _run(["systemctl", *args], timeout=20)
    return {"ok": ok, "output": out, "command": "systemctl " + " ".join(args)}


def _unit_state(unit: str, *, user: bool = True) -> dict[str, str]:
    prefix = ["systemctl", "--user"] if user else ["systemctl"]
    active_ok, active = _run([*prefix, "is-active", unit], timeout=5)
    enabled_ok, enabled = _run([*prefix, "is-enabled", unit], timeout=5)
    return {
        "active": active if active_ok else "inactive",
        "enabled": enabled if enabled_ok else "disabled",
        "installed": "not-found" not in enabled.lower() and "could not be found" not in enabled.lower(),
    }


def _dashboard_url(cfg: dict[str, Any]) -> str:
    from nordctl.network_access import dashboard_urls

    return str(dashboard_urls(cfg).get("primary") or "http://127.0.0.1:8765/")


def write_ui_unit(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or load_config()
    srv = cfg.get("server") or {}
    bind = str(srv.get("bind") or "127.0.0.1")
    port = int(srv.get("port") or 8765)
    bin_path = _nordctl_bin()
    unit = ui_unit_path()
    unit.write_text(
        f"""[Unit]
Description=nordctl web dashboard (local VPN control UI)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
ExecStart={bin_path} serve --bind {bind} --port {port}
Restart=always
RestartSec=3
TimeoutStopSec=15
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target
""",
        encoding="utf-8",
    )
    return unit


def ui_service_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    st = _unit_state(UI_UNIT, user=True)
    manual = _manual_serve_pids()
    installed = ui_unit_path().is_file()
    bind, configured_port = _server_bind_port(cfg)
    configured_url = _dashboard_url(cfg)
    live = detect_nordctl_listen()
    live_url = f"http://{live[0]}:{live[1]}/" if live else None
    url = live_url or configured_url
    port_mismatch = bool(live and live[1] != configured_port)
    return {
        "unit": UI_UNIT,
        "installed": installed,
        "active": st["active"] == "active",
        "enabled_at_login": st["enabled"] in ("enabled", "enabled-runtime"),
        "status_text": st["active"],
        "enabled_text": st["enabled"],
        "manual_pids": manual,
        "manual_running": bool(manual),
        "unit_path": str(ui_unit_path()),
        "url": url,
        "configured_url": configured_url,
        "configured_port": configured_port,
        "live_port": live[1] if live else None,
        "port_mismatch": port_mismatch,
        "exec_hint": f"{_nordctl_bin()} serve",
    }


def nordvpnd_status() -> dict[str, Any]:
    st = _unit_state(NORD_UNIT, user=False)
    return {
        "unit": NORD_UNIT,
        "active": st["active"] == "active",
        "enabled_at_boot": st["enabled"] == "enabled",
        "status_text": st["active"],
        "enabled_text": st["enabled"],
        "note": "System service — start/stop needs sudo unless passwordless sudo is configured",
    }


def service_overview(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    svc_cfg = cfg.get("service") or {}
    ui = ui_service_status(cfg)
    nord = nordvpnd_status()
    tray_cfg = cfg.get("tray") or {}
    from nordctl.network_access import network_access_payload

    return {
        "ui": ui,
        "nordvpnd": nord,
        "tray_autostart": bool(tray_cfg.get("autostart")),
        "tray_enabled": bool(tray_cfg.get("enabled")),
        "autostart_preference": bool(svc_cfg.get("autostart", False)),
        "network_access": network_access_payload(cfg),
        "help": [
            "nordctl UI runs as a systemd user service (starts at login when enabled).",
            "You can also run manually: nordctl serve (Ctrl+C to stop).",
            "nordvpnd is Nord’s system daemon — required for VPN. Enable at boot with sudo systemctl enable nordvpnd.",
        ],
    }


def _start_background_serve(bind: str, port: int) -> bool:
    bin_path = _nordctl_bin()
    log_path = Path.home() / ".local/share/nordctl/serve.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        f"nohup {bin_path} serve --bind {bind} --port {port} "
        f">>{log_path} 2>&1 &"
    )
    return _spawn_detached(["bash", "-c", script])


def _probe_ui_url(url: str, *, seconds: float = 15.0) -> bool:
    import time
    import urllib.error
    import urllib.request

    probe = url.rstrip("/") + "/api/state/quick"
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(probe, timeout=2.0) as resp:
                if resp.status == 200:
                    return True
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.45)
    return False


def bootstrap_ui_service(
    cfg: dict[str, Any] | None = None,
    *,
    enable: bool = True,
    wait_seconds: float = 18.0,
) -> dict[str, Any]:
    """Install/start the dashboard after setup — free a port, start UI, wait until it responds."""
    from nordctl.config import ensure_server_port

    cfg = cfg or load_config()
    notes: list[str] = []

    if shutil.which("systemctl"):
        _systemctl_user("stop", UI_UNIT)
    stop_manual_serve_processes()

    port, replaced = ensure_server_port(cfg, update_config=True)
    if replaced is not None:
        notes.append(f"Port {replaced} was in use — dashboard will use {port}")
    bind, _ = _server_bind_port(cfg)
    _wait_port_free(bind, port, seconds=5.0)

    method = "manual"
    systemd_ok = False
    if shutil.which("systemctl"):
        install_r = install_ui_service(cfg, enable=enable)
        if install_r.get("ok"):
            active = _systemctl_user("is-active", UI_UNIT)
            if active.get("ok") and (active.get("output") or "").strip() == "active":
                method = "systemd"
                systemd_ok = True
            else:
                notes.append("systemd unit did not become active — starting background serve")
        else:
            err = install_r.get("error") or "systemd install failed"
            notes.append(str(err))

    if not systemd_ok:
        if not _wait_port_free(bind, port, seconds=3.0):
            port, replaced2 = ensure_server_port(cfg, update_config=True)
            if replaced2 is not None:
                notes.append(f"Port {replaced2} still busy — switched to {port}")
            bind, _ = _server_bind_port(cfg)
            _wait_port_free(bind, port, seconds=3.0)
        if not _start_background_serve(bind, port):
            return {
                "ok": False,
                "port": port,
                "url": _dashboard_url(cfg),
                "method": method,
                "notes": notes,
                "error": "Could not start background nordctl serve",
            }

    url = _dashboard_url(cfg)
    ready = _probe_ui_url(url, seconds=wait_seconds)
    return {
        "ok": ready,
        "ready": ready,
        "port": port,
        "url": url,
        "method": method,
        "port_replaced": replaced,
        "notes": notes,
        "error": None
        if ready
        else (
            f"Dashboard did not respond at {url} within {int(wait_seconds)}s. "
            f"Check ~/.local/share/nordctl/serve.log or run: {_nordctl_bin()} service bootstrap"
        ),
    }


def install_ui_service(cfg: dict[str, Any] | None = None, *, enable: bool = True) -> dict[str, Any]:
    cfg = cfg or load_config()
    if not shutil.which("systemctl"):
        return {"ok": False, "error": "systemctl not found"}
    from nordctl.config import ensure_server_port

    stop_manual_serve_processes()
    port, replaced = ensure_server_port(cfg, update_config=True)
    if replaced is not None:
        srv = cfg.setdefault("server", {})
        srv["port"] = port
        save_config(cfg)
    bind, _ = _server_bind_port(cfg)
    _wait_port_free(bind, port, seconds=5.0)
    path = write_ui_unit(cfg)
    steps = [_systemctl_user("daemon-reload")]
    if enable:
        svc = cfg.setdefault("service", {})
        svc["autostart"] = True
        save_config(cfg)
        steps.append(_systemctl_user("enable", UI_UNIT))
    steps.append(_systemctl_user("start", UI_UNIT))
    ok = all(s.get("ok") for s in steps)
    return {
        "ok": ok,
        "installed": True,
        "enabled": enable,
        "unit_path": str(path),
        "url": _dashboard_url(cfg),
        "steps": steps,
        "note": "UI service installed" + (" and enabled at login" if enable else ""),
    }


def uninstall_ui_service(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    steps: list[dict[str, Any]] = []
    if ui_unit_path().is_file():
        steps.append(_systemctl_user("disable", "--now", UI_UNIT))
        ui_unit_path().unlink(missing_ok=True)
        steps.append(_systemctl_user("daemon-reload"))
    svc = cfg.setdefault("service", {})
    svc["autostart"] = False
    save_config(cfg)
    return {"ok": True, "removed": True, "steps": steps}


def control_ui_service(action: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    action = action.strip().lower()
    allowed = {"start", "stop", "restart", "enable", "disable", "status"}
    if action not in allowed:
        return {"ok": False, "error": f"unknown action: {action}"}

    bind, port = _server_bind_port(cfg)
    bin_path = _nordctl_bin()

    if action == "enable":
        svc = cfg.setdefault("service", {})
        svc["autostart"] = True
        save_config(cfg)
        write_ui_unit(cfg)
        _systemctl_user("daemon-reload")
        stop_manual_serve_processes()
        _wait_port_free(bind, port)
        r = _systemctl_user("enable", "--now", UI_UNIT)
        return {**r, "note": "UI will start at login", "bin": bin_path}

    if action == "disable":
        svc = cfg.setdefault("service", {})
        svc["autostart"] = False
        save_config(cfg)
        r = _systemctl_user("disable", "--now", UI_UNIT)
        return {**r, "note": "UI service disabled at login"}

    if action in ("start", "restart") and not ui_unit_path().is_file():
        write_ui_unit(cfg)
        _systemctl_user("daemon-reload")

    if action == "status":
        return {"ok": True, **ui_service_status(cfg), "bin": bin_path}

    if action == "restart":
        return schedule_ui_restart(cfg)

    manual: dict[str, Any] | None = None
    if action == "start":
        write_ui_unit(cfg)
        _systemctl_user("daemon-reload")
        manual = stop_manual_serve_processes()
        if not _wait_port_free(bind, port):
            hint = (
                f"Port {port} on {bind} is still in use after stopping manual nordctl serve. "
                f"Check: ss -tlnp | grep {port}  then kill the PID, or run: "
                f"{bin_path} service restart"
            )
            return {
                "ok": False,
                "error": hint,
                "manual_stopped": manual.get("stopped"),
                "manual_remaining": manual.get("remaining"),
                "status": ui_service_status(cfg),
            }

    r = _systemctl_user(action, UI_UNIT)
    note = None
    if action == "start" and manual and manual.get("stopped"):
        note = f"Stopped manual serve PIDs: {', '.join(map(str, manual['stopped']))}"
    return {**r, "status": ui_service_status(cfg), "bin": bin_path, "note": note}


def control_nordvpnd(action: str) -> dict[str, Any]:
    action = action.strip().lower()
    if action not in {"start", "stop", "restart", "enable", "disable", "status"}:
        return {"ok": False, "error": f"unknown action: {action}"}

    if action == "status":
        return {"ok": True, **nordvpnd_status()}

    from nordctl.privileges import run_privileged

    if action == "enable":
        r = run_privileged(["systemctl", "enable", "--now", NORD_UNIT])
    elif action == "disable":
        r = run_privileged(["systemctl", "disable", "--now", NORD_UNIT])
    else:
        r = run_privileged(["systemctl", action, NORD_UNIT])

    if r.get("needs_password"):
        return {
            "ok": False,
            "needs_password": True,
            "manual": f"sudo systemctl {action} {NORD_UNIT}",
            "error": "sudo password required — run the command in a terminal",
        }
    return {**r, "status": nordvpnd_status()}
