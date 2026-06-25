"""Lightweight host stats for the top status bar."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import shutil
import socket
import time
from pathlib import Path
from typing import Any

_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_TTL = float(os.environ.get("NORDCTL_HOST_STATUS_TTL", "5"))


def _read_loadavg() -> tuple[float, float, float, int]:
    try:
        parts = Path("/proc/loadavg").read_text(encoding="utf-8").split()
        cores = os.cpu_count() or 1
        return float(parts[0]), float(parts[1]), float(parts[2]), int(cores)
    except (OSError, ValueError, IndexError):
        return 0.0, 0.0, 0.0, os.cpu_count() or 1


def _read_memory() -> dict[str, Any]:
    info: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, val = line.partition(":")
            if not val:
                continue
            num = val.strip().split()[0]
            if num.isdigit():
                info[key.strip()] = int(num)
    except OSError:
        return {"total_kb": 0, "used_kb": 0, "used_pct": None}
    total = info.get("MemTotal") or 0
    avail = info.get("MemAvailable")
    if avail is None:
        avail = info.get("MemFree") or 0
    used = max(total - avail, 0) if total else 0
    pct = round(100 * used / total, 1) if total else None
    return {"total_kb": total, "used_kb": used, "used_pct": pct}


def _read_swap() -> dict[str, Any]:
    total = free = 0
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("SwapTotal:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    total = int(parts[1])
            elif line.startswith("SwapFree:"):
                parts = line.split()
                if len(parts) >= 2 and parts[1].isdigit():
                    free = int(parts[1])
    except OSError:
        return {"total_kb": 0, "used_kb": 0, "used_pct": None}
    used = max(total - free, 0) if total else 0
    pct = round(100 * used / total, 1) if total else None
    return {"total_kb": total, "used_kb": used, "used_pct": pct}


def _read_disk(path: str = "/") -> dict[str, Any]:
    try:
        du = shutil.disk_usage(path)
        pct = round(100 * du.used / du.total, 1) if du.total else None
        return {
            "mount": path,
            "total_gb": round(du.total / (1024**3), 1),
            "used_gb": round(du.used / (1024**3), 1),
            "free_gb": round(du.free / (1024**3), 1),
            "used_pct": pct,
        }
    except OSError:
        return {"mount": path, "used_pct": None, "free_gb": None}


def _read_uptime_sec() -> float | None:
    try:
        return float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return None


def _read_cpu_temp_c() -> float | None:
    """Best-effort CPU temperature in °C via Linux thermal sysfs."""
    try:
        zones = sorted(Path("/sys/class/thermal").glob("thermal_zone*/temp"))
        for zone in zones:
            raw = zone.read_text(encoding="utf-8").strip()
            if not raw.isdigit():
                continue
            val = int(raw)
            if val > 0:
                return round(val / 1000, 1)
    except OSError:
        pass
    return None


def _ufw_summary() -> dict[str, Any]:
    try:
        from nordctl.ufw_control import ufw_status

        st = ufw_status()
        enabled = bool(st.get("enabled"))
        installed = st.get("installed") is not False and st.get("available") is not False
        if not installed:
            return {"installed": False, "enabled": False, "rule_count": 0, "label": "UFW n/a"}
        label = "UFW on" if enabled else "UFW off"
        rules = int(st.get("rule_count") or 0)
        if enabled and rules:
            label = f"UFW on · {rules}"
        return {
            "installed": True,
            "enabled": enabled,
            "rule_count": rules,
            "label": label,
        }
    except Exception:
        return {"installed": False, "enabled": False, "rule_count": 0, "label": "UFW —"}


def _ui_service_summary(cfg: dict[str, Any] | None) -> dict[str, Any]:
    try:
        from nordctl.service_mgr import ui_service_status

        st = ui_service_status(cfg)
        active = bool(st.get("active") or st.get("manual_running"))
        return {
            "active": active,
            "label": "UI on" if active else "UI off",
        }
    except Exception:
        return {"active": None, "label": "UI —"}


def host_status_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    now = time.time()
    cached = _CACHE.get("data")
    if cached and now - float(_CACHE.get("ts") or 0) < _TTL:
        return cached

    cfg = cfg or load_config()
    load1, load5, load15, cores = _read_loadavg()
    mem = _read_memory()
    disk = _read_disk("/")
    uptime = _read_uptime_sec()
    hostname = socket.gethostname().split(".")[0] or "host"

    load_pct = round(100 * load1 / cores, 0) if cores else None
    cpu_temp_c = _read_cpu_temp_c()
    payload: dict[str, Any] = {
        "ok": True,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "hostname": hostname,
        "uptime_sec": uptime,
        "cpu_temp_c": cpu_temp_c,
        "load": {"1m": load1, "5m": load5, "15m": load15, "cores": cores, "pct": load_pct},
        "memory": mem,
        "swap": _read_swap(),
        "disk": disk,
        "ufw": _ufw_summary(),
        "ui_service": _ui_service_summary(cfg),
    }
    _CACHE["ts"] = now
    _CACHE["data"] = payload
    return payload
