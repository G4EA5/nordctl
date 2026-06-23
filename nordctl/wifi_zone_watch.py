"""Background WiFi zone watcher + optional Smart DNS self-heal."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import threading
import time
from typing import Any

from nordctl.config import load_config, save_config

_watch_thread: threading.Thread | None = None
_watch_stop = threading.Event()
_last_ssid: str | None = None


def zone_watch_status() -> dict[str, Any]:
    cfg = load_config()
    zones = cfg.get("wifi_zones") or {}
    wifi = cfg.get("wifi") or {}
    return {
        "enabled": bool(zones.get("watch_enabled")),
        "auto_apply": bool(zones.get("auto_apply")),
        "running": _watch_thread is not None and _watch_thread.is_alive(),
        "interval_seconds": int(zones.get("watch_interval") or 30),
        "heal_smart_dns": bool(wifi.get("heal_smart_dns", True)),
        "auto_sync_active": bool(wifi.get("auto_sync_active", True)),
        "hint": "Polls SSID changes — applies zone preset and optional Smart DNS heal.",
    }


def _poll_loop(interval: float) -> None:
    global _last_ssid
    from nordctl.zones import current_ssid, maybe_auto_apply
    from nordctl.wifi_hub import heal_wifi

    while not _watch_stop.is_set():
        cfg = load_config()
        zones = cfg.get("wifi_zones") or {}
        if not zones.get("watch_enabled"):
            _watch_stop.wait(interval)
            continue

        ssid = current_ssid()
        if ssid and ssid != _last_ssid:
            _last_ssid = ssid
            from nordctl.activity_log import record_event

            record_event(
                "network",
                f"WiFi changed — {ssid}",
                detail="Zone watcher detected a new network.",
                level="info",
                ok=True,
            )
            if zones.get("auto_apply"):
                maybe_auto_apply(cfg)
            wifi = cfg.get("wifi") or {}
            if wifi.get("heal_smart_dns") or wifi.get("auto_sync_active"):
                heal_wifi(cfg)

        _watch_stop.wait(interval)


def start_zone_watch() -> dict[str, Any]:
    global _watch_thread
    if _watch_thread and _watch_thread.is_alive():
        return {"ok": True, "already_running": True, **zone_watch_status()}
    _watch_stop.clear()
    cfg = load_config()
    zones = cfg.setdefault("wifi_zones", {})
    zones["watch_enabled"] = True
    save_config(cfg)
    interval = float(zones.get("watch_interval") or 30)
    _watch_thread = threading.Thread(
        target=_poll_loop,
        args=(interval,),
        name="nordctl-wifi-zone-watch",
        daemon=True,
    )
    _watch_thread.start()
    return {"ok": True, "started": True, **zone_watch_status()}


def stop_zone_watch() -> dict[str, Any]:
    _watch_stop.set()
    cfg = load_config()
    zones = cfg.setdefault("wifi_zones", {})
    zones["watch_enabled"] = False
    save_config(cfg)
    return {"ok": True, "stopped": True, **zone_watch_status()}
