"""Desktop alerts when VPN disconnects unexpectedly."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
import threading
import time
from typing import Any

from nordctl.config import load_config, save_config

_watch_thread: threading.Thread | None = None
_watch_stop = threading.Event()
_last_connected: bool | None = None


def _notify(title: str, body: str) -> bool:
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", "nordctl", "-i", "network-vpn", title, body],
                timeout=5,
                check=False,
            )
            return True
        except (subprocess.TimeoutExpired, OSError):
            pass
    return False


def _poll_loop(interval: float) -> None:
    global _last_connected
    from nordctl import nordvpn as nv
    from nordctl.config import load_config as lc

    while not _watch_stop.is_set():
        cfg = lc()
        if not (cfg.get("security") or {}).get("disconnect_alerts", True):
            _watch_stop.wait(interval)
            continue
        bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
        if not nv.available(bin_path):
            _watch_stop.wait(interval)
            continue
        r = nv.run(bin_path, ["status"], timeout=8)
        st = nv.parse_status(r.get("output", ""))
        connected = bool(st.get("connected"))
        if _last_connected is True and not connected:
            _notify(
                "VPN disconnected",
                "NordVPN tunnel is down. Reconnect from nordctl or check kill switch.",
            )
            try:
                from nordctl.alerts import fire_alert

                fire_alert(
                    "vpn_disconnect",
                    "VPN disconnected",
                    "NordVPN tunnel is down. Reconnect from nordctl.",
                )
            except Exception:
                pass
            from nordctl.activity_log import record_event

            record_event(
                "security",
                "VPN disconnected (alert sent)",
                detail="Disconnect detected by background monitor.",
                level="warn",
                ok=False,
            )
        _last_connected = connected
        _watch_stop.wait(interval)


def disconnect_watch_status() -> dict[str, Any]:
    cfg = load_config()
    sec = cfg.get("security") or {}
    return {
        "enabled": bool(sec.get("disconnect_alerts", True)),
        "running": _watch_thread is not None and _watch_thread.is_alive(),
        "notify_send": shutil.which("notify-send") is not None,
        "interval_seconds": int(sec.get("watch_interval") or 30),
        "hint": "Shows a desktop notification if VPN drops while you are logged in.",
    }


def start_disconnect_watch() -> dict[str, Any]:
    global _watch_thread
    if _watch_thread and _watch_thread.is_alive():
        return {"ok": True, "already_running": True, **disconnect_watch_status()}
    _watch_stop.clear()
    cfg = load_config()
    sec = cfg.setdefault("security", {})
    sec["disconnect_alerts"] = True
    save_config(cfg)
    interval = float(sec.get("watch_interval") or 30)
    _watch_thread = threading.Thread(
        target=_poll_loop,
        args=(interval,),
        name="nordctl-disconnect-watch",
        daemon=True,
    )
    _watch_thread.start()
    return {"ok": True, "started": True, **disconnect_watch_status()}


def stop_disconnect_watch() -> dict[str, Any]:
    _watch_stop.set()
    cfg = load_config()
    sec = cfg.setdefault("security", {})
    sec["disconnect_alerts"] = False
    save_config(cfg)
    return {"ok": True, "stopped": True, **disconnect_watch_status()}
