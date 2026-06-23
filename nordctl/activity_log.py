"""Human-readable activity log — what nordctl did and what it means."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl.config import config_dir

MAX_ENTRIES = 400
LOG_FILE = config_dir() / "activity.jsonl"

_CATEGORIES = {
    "vpn": {"label": "VPN", "icon": "🛡️", "hint": "Connect, disconnect, Nord settings"},
    "dns": {"label": "DNS", "icon": "🌐", "hint": "Smart DNS, resolv.conf, Nord DNS"},
    "network": {"label": "Network", "icon": "📡", "hint": "Routes, traffic, nettools, speed test"},
    "scan": {"label": "Scans", "icon": "🔍", "hint": "Lynis, rkhunter, chkrootkit, ClamAV, nmap"},
    "terminal": {"label": "Terminal", "icon": "⌨️", "hint": "Shell sessions and quick commands"},
    "install": {"label": "Packages", "icon": "📦", "hint": "apt install and remove from Security packages"},
    "audit": {"label": "Audits", "icon": "📋", "hint": "Leak lab, privacy audit, doctor checks"},
    "service": {"label": "Services", "icon": "⚙️", "hint": "nordctl UI, nordvpnd, tray"},
    "preset": {"label": "Presets", "icon": "⚡", "hint": "One-click workflows"},
    "system": {"label": "System", "icon": "💻", "hint": "Config, baseline, exports, UI"},
    "security": {"label": "Security", "icon": "🔒", "hint": "UFW, kill switch, IPv6, alerts"},
    "error": {"label": "Problems", "icon": "⚠️", "hint": "Failures and things to fix"},
}

_SCAN_MARKERS = (
    "lynis",
    "rkhunter",
    "chkrootkit",
    "clamscan",
    "nmap",
    "rootkit",
    "audit system",
    "fail2ban",
)
_INSTALL_TITLE_PREFIXES = ("installed ", "removed ", "batch install", "batch removed")


def _legacy_category_match(entry: dict[str, Any], category: str) -> bool:
    """Include older entries logged before scan/terminal/install categories existed."""
    cat = str(entry.get("category") or "")
    if cat == category:
        return True
    blob = f"{entry.get('title') or ''} {entry.get('detail') or ''}".lower()
    meta = entry.get("meta") or {}
    cmd = str(meta.get("cmd") or meta.get("source") or "")
    if category == "scan":
        if cat != "security":
            return False
        return any(m in blob or m in cmd.lower() for m in _SCAN_MARKERS)
    if category == "install":
        if cat != "system":
            return False
        return any(blob.startswith(p) for p in _INSTALL_TITLE_PREFIXES) or meta.get("tool_id") or meta.get("tool_ids")
    if category == "terminal":
        if cat != "system":
            return False
        return "terminal" in blob or meta.get("terminal_session")
    if category == "audit":
        if cat != "system":
            return False
        return any(w in blob for w in ("doctor", "leak lab", "privacy audit", "audit report"))
    return False

_last_vpn: dict[str, Any] = {"connected": None, "country": None, "ip": None}


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _log_path() -> Path:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    return LOG_FILE


def record_event(
    category: str,
    title: str,
    *,
    detail: str = "",
    technical: str = "",
    level: str = "info",
    ok: bool = True,
    meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one log entry (ring buffer on disk)."""
    entry = {
        "id": f"{int(time.time() * 1000)}",
        "ts": _now_iso(),
        "ts_ms": int(time.time() * 1000),
        "category": category if category in _CATEGORIES else "system",
        "level": level,
        "ok": ok,
        "title": title.strip(),
        "detail": detail.strip(),
        "technical": (technical or "")[:8000],
        "meta": meta or {},
    }
    path = _log_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    _trim_file(path)
    return entry


def _trim_file(path: Path) -> None:
    if not path.is_file():
        return
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    if len(lines) <= MAX_ENTRIES:
        return
    keep = lines[-MAX_ENTRIES:]
    path.write_text("\n".join(keep) + "\n", encoding="utf-8")


def list_entries(
    *,
    limit: int = 400,
    category: str | None = None,
    errors_only: bool = False,
) -> list[dict[str, Any]]:
    path = _log_path()
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    entries: list[dict[str, Any]] = []
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if category and not _legacy_category_match(e, category):
            continue
        if errors_only and e.get("ok", True) and e.get("level") != "error":
            continue
        entries.append(e)
        if len(entries) >= limit:
            break
    return entries


def clear_entries() -> dict[str, Any]:
    path = _log_path()
    if path.is_file():
        path.unlink()
    record_event(
        "system",
        "Log cleared",
        detail="Previous entries were removed. New actions will appear here.",
        level="info",
        ok=True,
    )
    return {"ok": True, "cleared": True}


def logs_payload(
    *,
    limit: int = 400,
    category: str | None = None,
    errors_only: bool = False,
) -> dict[str, Any]:
    entries = list_entries(limit=limit, category=category, errors_only=errors_only)
    err_count = sum(1 for e in entries if not e.get("ok") or e.get("level") == "error")
    return {
        "ok": True,
        "entries": entries,
        "categories": [
            {"id": k, **v}
            for k, v in _CATEGORIES.items()
        ],
        "path": str(_log_path()),
        "total_shown": len(entries),
        "recent_errors": err_count,
        "intro": (
            "Plain-English record of VPN, DNS, network diagnostics, security scans "
            "(Lynis, rkhunter, chkrootkit, ClamAV), package installs, shell commands, "
            "UFW, audits, and presets — up to 400 recent entries. Expand any row for technical output."
        ),
    }


def maybe_log_vpn_transition(status: dict[str, Any]) -> None:
    """Log connect/disconnect/country changes detected during status refresh."""
    global _last_vpn
    connected = bool(status.get("connected"))
    country = str(status.get("Country") or status.get("country") or "")
    ip = str(status.get("IP") or status.get("ip") or "")

    prev_conn = _last_vpn.get("connected")
    if prev_conn is None:
        _last_vpn = {"connected": connected, "country": country, "ip": ip}
        if connected:
            record_event(
                "vpn",
                f"VPN is connected — {country or 'unknown country'}",
                detail=f"Your traffic is routed through NordVPN. Exit IP: {ip or '—'}.",
                level="ok",
                ok=True,
                meta={"country": country, "ip": ip},
            )
        return

    if connected and not prev_conn:
        record_event(
            "vpn",
            f"VPN connected — {country or 'server selected'}",
            detail=f"You are now protected through NordVPN. Your visible IP: {ip or 'checking…'}.",
            level="ok",
            ok=True,
        )
    elif not connected and prev_conn:
        record_event(
            "vpn",
            "VPN disconnected",
            detail="Traffic is no longer going through the Nord tunnel. Meshnet may still be on.",
            level="warn",
            ok=True,
        )
    elif connected and prev_conn and country and country != _last_vpn.get("country"):
        record_event(
            "vpn",
            f"VPN server changed — {country}",
            detail=f"NordVPN switched location. New IP: {ip or '—'}.",
            level="info",
            ok=True,
        )

    _last_vpn = {"connected": connected, "country": country, "ip": ip}


def explain_action(action: str, body: dict[str, Any], result: dict[str, Any]) -> tuple[str, str, str, str, bool]:
    """Return category, title, detail, technical, ok."""
    action = (action or "").strip().lower()
    ok = bool(result.get("ok", True))
    technical = ""
    r_out = result.get("result") or {}
    if isinstance(r_out, dict):
        technical = str(r_out.get("output") or result.get("output") or "")
    else:
        technical = str(result.get("output") or result.get("error") or "")

    if action == "connect":
        target = str(body.get("target") or "").strip()
        where = target or "last used server"
        if ok:
            return (
                "vpn",
                f"Connect requested — {where}",
                "NordVPN is establishing a tunnel. Status will update on Dashboard when ready.",
                technical,
                ok,
            )
        return ("vpn", "Connect failed", result.get("error") or "Could not connect.", technical, False)

    if action == "disconnect":
        return (
            "vpn",
            "Disconnected VPN" if ok else "Disconnect failed",
            "The VPN tunnel was turned off." if ok else (result.get("error") or "Try again or run nordvpn disconnect in a terminal."),
            technical,
            ok,
        )

    if action == "reconnect":
        return (
            "vpn",
            "Reconnecting VPN" if ok else "Reconnect failed",
            "Repeated the last NordVPN connection." if ok else (result.get("error") or ""),
            technical,
            ok,
        )

    if action == "preset":
        pid = str(body.get("preset") or "")
        note = str(result.get("note") or "")
        return (
            "preset",
            f"Preset applied — {pid}" if ok else f"Preset failed — {pid}",
            note or ("Workflow completed." if ok else result.get("error") or "See steps in Automate → baseline to undo."),
            technical,
            ok,
        )

    if action.startswith("dns_") or action == "dns_nord":
        titles = {
            "dns_save": ("DNS addresses saved", "Smart DNS primary/secondary stored in config.yaml."),
            "dns_apply_smart": ("Smart DNS applied on WiFi", "NetworkManager WiFi profiles now use Nord streaming DNS."),
            "dns_restore": ("WiFi DNS restored", "Automatic DNS returned on configured WiFi profiles."),
            "dns_nord": (f"Nord DNS turned {body.get('value', 'on')}", "Nord handles DNS while VPN is connected."),
        }
        t, d = titles.get(action, ("DNS change", result.get("note") or ""))
        return ("dns", t if ok else f"DNS action failed", d if ok else (result.get("error") or ""), technical, ok)

    if action == "set_connect_country":
        country = str(body.get("country") or result.get("note") or "")
        return (
            "system",
            "Default country saved" if ok else "Country save failed",
            result.get("note") or f"Presets will use {country}." if ok else (result.get("error") or ""),
            technical,
            ok,
        )

    if action in ("nord_firewall", "nord_killswitch"):
        name = "Firewall" if "firewall" in action else "Kill switch"
        val = str(body.get("value") or "on")
        return (
            "security",
            f"Nord {name} — {val}" if ok else f"{name} change failed",
            f"NordVPN {name.lower()} is now {val}." if ok else (result.get("error") or ""),
            technical,
            ok,
        )

    if action.startswith("service_"):
        op = str(body.get("op") or body.get("service_action") or "")
        target = "nordvpnd" if "nordvpnd" in action else "nordctl UI"
        return (
            "service",
            f"{target}: {op}" if ok else f"Service action failed — {op}",
            result.get("note") or (f"systemctl {op} on {target}." if ok else result.get("error") or result.get("manual") or ""),
            technical or str(result.get("manual") or ""),
            ok,
        )

    if action == "baseline_restore":
        return (
            "system",
            "Install baseline restored" if ok else "Baseline restore failed",
            "Config, WiFi DNS, Nord settings, and related files reverted to first-run snapshot."
            if ok
            else (result.get("error") or ""),
            technical,
            ok,
        )

    if action == "factory_reset":
        return (
            "system",
            "Factory reset completed" if ok else "Factory reset incomplete",
            result.get("note") or "Restored pre-install state where baseline exists.",
            technical,
            ok,
        )

    if action == "snapshot":
        if body.get("restore"):
            return ("system", "Nord snapshot restored" if ok else "Snapshot restore failed", result.get("note") or "", technical, ok)
        return ("system", "Nord settings snapshot saved" if ok else "Snapshot failed", "Quick undo point before bigger changes.", technical, ok)

    if action == "disable_ipv6":
        return (
            "security",
            "IPv6 disabled" if ok else "IPv6 disable needs sudo",
            result.get("note") or ("Reduces VPN bypass via IPv6." if ok else result.get("manual") or ""),
            technical or str(result.get("manual") or ""),
            ok,
        )

    if action == "fix_resolv_immutable":
        return (
            "dns",
            "resolv.conf immutable flag removed" if ok else "Needs sudo for resolv.conf",
            "Allows DNS changes from Nord or NetworkManager again." if ok else (result.get("manual") or ""),
            technical,
            ok,
        )

    if action == "fix_resolv_stub":
        return (
            "dns",
            "resolv.conf linked to systemd stub" if ok else "Needs sudo for resolv.conf",
            result.get("note") or ("Restores normal systemd-resolved DNS chain." if ok else result.get("manual") or ""),
            technical,
            ok,
        )

    if action == "audit_email_report":
        return (
            "audit",
            "Privacy audit report emailed" if ok else "Audit email failed",
            result.get("note") or ("Plain-text summary sent to your configured address." if ok else result.get("error") or ""),
            technical,
            ok,
        )

    if action == "location_apply":
        pid = str(body.get("profile") or "")
        return (
            "security",
            f"Location profile — {pid}" if ok else f"Profile failed — {pid}",
            result.get("note") or ("Preset and connection steps applied." if ok else result.get("error") or ""),
            technical,
            ok,
        )

    if action == "disconnect_watch":
        en = bool(body.get("enable"))
        return (
            "security",
            "Disconnect alerts enabled" if en and ok else ("Disconnect alerts disabled" if ok else "Alert toggle failed"),
            "Background monitor will notify you if VPN drops." if en and ok else "Monitor stopped.",
            technical,
            ok,
        )

    if action == "status_page":
        en = bool(body.get("enable"))
        return (
            "system",
            "LAN status page enabled" if en and ok else ("Status page disabled" if ok else "Status page toggle failed"),
            result.get("url") or result.get("lan_note") or "",
            technical,
            ok,
        )

    if action == "speedtest":
        return (
            "network",
            "Speed test complete" if ok else "Speed test failed",
            result.get("human") or result.get("note") or (result.get("error") or ""),
            technical,
            ok,
        )

    if action == "packet_capture":
        return (
            "network",
            "Packet capture finished" if ok else "Capture failed",
            result.get("plain") or result.get("note") or (result.get("error") or result.get("manual") or ""),
            technical or str(result.get("manual") or ""),
            ok,
        )

    if action in ("export_config", "export_logs"):
        label = "Config bundle exported" if action == "export_config" else "Activity log exported"
        return (
            "system",
            label if ok else "Export failed",
            result.get("path") or result.get("note") or "",
            technical,
            ok,
        )

    if action == "nord_notify":
        val = str(body.get("value") or "on")
        return (
            "vpn",
            f"Nord notifications {val}" if ok else "Notification setting failed",
            result.get("note") or "",
            technical,
            ok,
        )

    if action.startswith("wifi_"):
        titles = {
            "wifi_sync_profiles": ("WiFi profiles synced", "Added NetworkManager profiles to config."),
            "wifi_remove_stale_profiles": ("Stale WiFi profiles removed", result.get("note") or "Removed names not in NetworkManager."),
            "wifi_profile_toggle": ("WiFi profile updated", result.get("note") or ""),
            "wifi_zone_add": ("Trusted WiFi zone added", result.get("note") or ""),
            "wifi_zone_remove": ("Trusted zone removed", "SSID removed from trusted list."),
            "wifi_zones_save": ("WiFi zones saved", "Zone settings updated in config."),
            "wifi_heal": ("WiFi self-heal", result.get("note") or "Profiles, DNS, and zones checked."),
            "wifi_self_heal": ("Self-heal options saved", "Auto-sync and Smart DNS heal toggles updated."),
            "wifi_zone_watch": (
                "Zone watcher enabled" if body.get("enable") else "Zone watcher disabled",
                "Background SSID monitor for presets and heal.",
            ),
            "wifi_rescan": ("WiFi rescan", "Requested fresh scan of nearby networks."),
            "bluetooth_scan": ("Bluetooth scan", "Requested fresh BLE/Classic neighbor scan."),
        }
        t, d = titles.get(action, ("WiFi action", result.get("note") or ""))
        return ("network", t if ok else f"{t} failed", d if ok else (result.get("error") or ""), technical, ok)

    if action in ("onboarding_save", "onboarding_all"):
        return ("system", "Setup modules saved" if ok else "Onboarding failed", result.get("note") or "Feature modules stored locally.", technical, ok)

    if action in ("alerts_save", "alerts_test"):
        return ("security", "Alert settings saved" if action == "alerts_save" and ok else ("Test alert sent" if ok else "Alert failed"), result.get("note") or result.get("privacy_note") or "", technical, ok)

    if action == "privacy_export":
        return ("system", "Privacy report exported" if ok else "Export failed", result.get("path") or "", technical, ok)

    if action == "run":
        args = " ".join(str(a) for a in (body.get("args") or []))
        return (
            "vpn",
            f"Ran nordvpn {args}" if ok else f"nordvpn command failed",
            "Advanced CLI command executed." if ok else (result.get("error") or ""),
            technical,
            ok,
        )

    title = action.replace("_", " ").title() or "Action"
    return (
        "system",
        title if ok else f"{title} failed",
        str(result.get("note") or result.get("error") or ""),
        technical,
        ok,
    )


def log_action(action: str, body: dict[str, Any], result: dict[str, Any]) -> None:
    cat, title, detail, technical, ok = explain_action(action, body, result)
    level = "ok" if ok else "error"
    if not ok:
        cat = "error" if cat == "system" else cat
    record_event(cat, title, detail=detail, technical=technical, level=level, ok=ok, meta={"action": action})


def log_client_event(event_type: str, message: str, *, ok: bool = True, detail: str = "") -> dict[str, Any]:
    cat_map = {
        "nettools": "network",
        "traffic": "network",
        "install": "install",
        "save": "system",
        "config": "system",
        "ui": "system",
        "error": "error",
        "action": "system",
        "terminal": "terminal",
        "doctor": "audit",
        "audit": "audit",
        "lab": "audit",
        "ufw": "security",
        "speed test": "network",
    }
    key = (event_type or "").strip().lower()
    cat = cat_map.get(key, "system")
    return record_event(
        cat,
        message,
        detail=detail or f"Recorded from the web UI ({event_type}).",
        level="ok" if ok else "error",
        ok=ok,
        meta={"source": "ui", "type": event_type},
    )
