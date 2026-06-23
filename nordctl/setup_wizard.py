"""First-run setup wizard — step checklist driven by doctor + config."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config, save_config

WIZARD_FILE = "setup_wizard.json"

STEP_DEFS: list[dict[str, Any]] = [
    {"id": "welcome", "title": "Welcome", "summary": "What this wizard will help you configure.", "skippable": False},
    {"id": "legal", "title": "Legal", "summary": "Accept LEGAL.md once — required to use nordctl.", "skippable": False},
    {
        "id": "nordvpn",
        "title": "NordVPN",
        "summary": "Official NordVPN client — install and log in for Connect and presets.",
        "skippable": True,
    },
    {
        "id": "services",
        "title": "Services",
        "summary": "Start nordvpnd and optional UI autostart so Connect works after reboot.",
        "skippable": True,
    },
    {
        "id": "privileges",
        "title": "Sudo & privileges",
        "summary": "One-time sudo setup so the UI can manage UFW, WiFi DNS, and IPv6.",
        "skippable": True,
    },
    {
        "id": "country",
        "title": "Home country",
        "summary": "Default country for presets and quick connect.",
        "skippable": True,
    },
    {
        "id": "wifi",
        "title": "WiFi profiles",
        "summary": "Sync your active WiFi into config for Smart DNS and home IP.",
        "skippable": True,
    },
    {
        "id": "home_isp",
        "title": "Home ISP & trusted WiFi",
        "summary": "Trusted home WiFi and ISP address for the top bar (travel-safe).",
        "skippable": True,
    },
    {
        "id": "smart_dns",
        "title": "Smart DNS on WiFi",
        "summary": "Apply Nord Smart DNS to saved WiFi profiles when VPN is off.",
        "skippable": True,
    },
    {
        "id": "ipv6",
        "title": "IPv6 hardening",
        "summary": "Optional — disable IPv6 to reduce VPN bypass leaks.",
        "skippable": True,
    },
    {"id": "ufw", "title": "Host firewall (UFW)", "summary": "Quick check that Linux UFW is available.", "skippable": True},
    {
        "id": "alerts",
        "title": "Alerts & notifications",
        "summary": "Browser notifications and VPN disconnect watcher.",
        "skippable": True,
    },
    {
        "id": "email",
        "title": "Email alerts",
        "summary": "Optional SMTP — mail goes only to your address.",
        "skippable": True,
    },
    {
        "id": "ui_access",
        "title": "Dashboard access",
        "summary": "Password if you open the UI on your LAN.",
        "skippable": True,
    },
    {
        "id": "baseline",
        "title": "Install baseline",
        "summary": "Rollback snapshot saved on first run — undo preset mistakes safely.",
        "skippable": True,
    },
    {
        "id": "first_connect",
        "title": "First connect",
        "summary": "Connect VPN or apply a starter preset so you see it working.",
        "skippable": True,
    },
    {
        "id": "packages",
        "title": "Optional apt tools",
        "summary": "Networking and security scanners (lynis, nmap, …).",
        "skippable": True,
    },
    {
        "id": "ui_health",
        "title": "Dashboard UI",
        "summary": "Verify CSS and static files so every page renders correctly.",
        "skippable": True,
    },
    {"id": "finish", "title": "All set", "summary": "Review checklist and open the dashboard.", "skippable": False},
]

CHECKLIST_DEFS: list[tuple[str, str, str]] = [
    ("nordvpn", "NordVPN installed", "nordvpn"),
    ("login", "Logged in to NordVPN", "nordvpn"),
    ("services", "nordvpnd running", "services"),
    ("privileges", "UI sudo privileges", "privileges"),
    ("country", "Home country saved", "country"),
    ("wifi", "WiFi profile in config", "wifi"),
    ("home_isp", "Home WiFi / ISP ready", "home_isp"),
    ("smart_dns", "Smart DNS on WiFi", "smart_dns"),
    ("ipv6", "IPv6 check OK", "ipv6"),
    ("ufw", "UFW available", "ufw"),
    ("alerts", "Browser alerts on", "alerts"),
    ("watch", "VPN disconnect watcher", "alerts"),
    ("email", "Email alerts configured", "email"),
    ("baseline", "Install baseline saved", "baseline"),
    ("connected", "VPN connected once", "first_connect"),
    ("ui_health", "Dashboard UI assets OK", "ui_health"),
]


def _wizard_path() -> Path:
    return config_dir() / WIZARD_FILE


def load_wizard_progress(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    feats = cfg.get("features") or {}
    path = _wizard_path()
    data: dict[str, Any] = {
        "complete": bool(feats.get("setup_wizard_complete")),
        "skipped": [],
        "visited": [],
        "current": "welcome",
    }
    if path.is_file():
        try:
            stored = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(stored, dict):
                data.update(stored)
        except (OSError, json.JSONDecodeError):
            pass
    if data.get("complete"):
        data["complete"] = True
    data.setdefault("skipped", [])
    data.setdefault("visited", [])
    if not data.get("current"):
        data["current"] = "welcome"
    return data


def save_wizard_progress(data: dict[str, Any]) -> None:
    path = _wizard_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _check_by_id(doctor: dict[str, Any], check_id: str) -> dict[str, Any] | None:
    for c in doctor.get("checks") or []:
        if c.get("id") == check_id:
            return c
    return None


def _wizard_context(cfg: dict[str, Any], doctor: dict[str, Any]) -> dict[str, Any]:
    from nordctl import nordvpn as nv
    from nordctl.alerts import alerts_status
    from nordctl.baseline import baseline_status
    from nordctl.firewall_panel import ufw_state
    from nordctl.home_ip import cache_path, cached_public_ip
    from nordctl.service_mgr import service_overview
    from nordctl.state import _network_smart_dns
    from nordctl.zones import zone_status

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status: dict[str, Any] = {}
    if nv.available(bin_path):
        status = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))
    zones = zone_status(cfg)
    ssid = zones.get("ssid")
    smart = _network_smart_dns(cfg, status)
    svc = service_overview(cfg)
    alerts = alerts_status(cfg)
    bl = baseline_status()
    ufw = ufw_state()
    ipv6 = _check_by_id(doctor, "ipv6")
    home_cached = cached_public_ip(cfg, ssid=ssid) if ssid else None
    tray = cfg.get("tray") or {}
    import shutil

    cli_bin = shutil.which("nordctl") or "nordctl"
    email_cfg = (cfg.get("alerts") or {}).get("email") or {}
    return {
        "vpn_connected": bool(status.get("connected")),
        "vpn_country": status.get("country"),
        "services": svc,
        "nordvpnd_active": bool((svc.get("nordvpnd") or {}).get("active")),
        "ui_service_installed": bool((svc.get("ui") or {}).get("installed")),
        "ui_autostart": bool(svc.get("autostart_preference") or (svc.get("ui") or {}).get("enabled")),
        "tray_autostart": bool(tray.get("autostart")),
        "zones": zones,
        "home_ip_cached": home_cached,
        "home_ip_cache_path": str(cache_path()),
        "smart_dns": smart,
        "smart_dns_active": bool(smart.get("active")),
        "ufw": ufw,
        "ufw_active": bool(ufw.get("active")),
        "ipv6_ok": bool(ipv6 and ipv6.get("ok")),
        "baseline": bl,
        "alerts": alerts,
        "alert_watch_running": bool(alerts.get("watch_running")),
        "cli_serve": f"{cli_bin} serve",
        "email": {
            "enabled": bool(email_cfg.get("enabled")),
            "to": str(email_cfg.get("to") or "").strip(),
            "smtp_host": str(email_cfg.get("smtp_host") or "").strip(),
            "smtp_user": str(email_cfg.get("smtp_user") or "").strip(),
            "password_set": bool(email_cfg.get("smtp_password")),
            "configured": bool(
                email_cfg.get("enabled")
                and str(email_cfg.get("to") or "").strip()
                and str(email_cfg.get("smtp_host") or "").strip()
            ),
        },
    }


def _step_auto_done(step_id: str, cfg: dict[str, Any], doctor: dict[str, Any], ctx: dict[str, Any]) -> bool:
    from nordctl.ui_auth import ui_auth_status

    if step_id == "welcome":
        return True
    if step_id == "legal":
        return bool((cfg.get("features") or {}).get("legal_accepted"))
    if step_id == "nordvpn":
        return bool(doctor.get("nord_installed") and doctor.get("logged_in"))
    if step_id == "services":
        if not doctor.get("nord_installed"):
            return True
        return bool(ctx.get("nordvpnd_active"))
    if step_id == "privileges":
        priv = doctor.get("privileges") or {}
        return bool(priv.get("ui_privileges_ok") or priv.get("passwordless_sudo"))
    if step_id == "country":
        cc = _check_by_id(doctor, "connect_country")
        return bool(cc and cc.get("ok")) or bool(str(cfg.get("connect_country") or "").strip())
    if step_id == "wifi":
        wc = _check_by_id(doctor, "wifi_profiles")
        return bool(wc and wc.get("ok"))
    if step_id == "home_isp":
        zones = ctx.get("zones") or {}
        if zones.get("is_trusted"):
            return True
        if ctx.get("home_ip_cached"):
            return True
        if not zones.get("ssid"):
            return True
        return False
    if step_id == "smart_dns":
        return bool(ctx.get("smart_dns_active"))
    if step_id == "ipv6":
        return bool(ctx.get("ipv6_ok"))
    if step_id == "ufw":
        ufw = ctx.get("ufw") or {}
        if ufw.get("installed") is False:
            return True
        return bool(ctx.get("ufw_active"))
    if step_id == "alerts":
        ac = cfg.get("alerts") or {}
        return bool(ac.get("browser_enabled", True)) and bool(ac.get("watch_enabled", True))
    if step_id == "email":
        em = (cfg.get("alerts") or {}).get("email") or {}
        return bool(em.get("enabled") and str(em.get("to") or "").strip())
    if step_id == "ui_access":
        srv = cfg.get("server") or {}
        bind = str(srv.get("bind") or "127.0.0.1").strip()
        ui_auth = ui_auth_status(cfg)
        if bind in ("127.0.0.1", "localhost", "::1"):
            return True
        return bool(ui_auth.get("enabled"))
    if step_id == "baseline":
        return bool((ctx.get("baseline") or {}).get("exists"))
    if step_id == "first_connect":
        return bool(ctx.get("vpn_connected"))
    if step_id == "packages":
        return False
    if step_id == "ui_health":
        from nordctl.static_assets import verify_static_ui

        return bool(verify_static_ui().get("ok"))
    if step_id == "finish":
        return False
    return False


def _checklist_ok(check_id: str, cfg: dict[str, Any], doctor: dict[str, Any], ctx: dict[str, Any]) -> bool:
    if check_id == "nordvpn":
        return bool(doctor.get("nord_installed"))
    if check_id == "login":
        return bool(doctor.get("logged_in"))
    if check_id == "services":
        return _step_auto_done("services", cfg, doctor, ctx)
    if check_id == "privileges":
        priv = doctor.get("privileges") or {}
        return bool(priv.get("ui_privileges_ok"))
    if check_id == "country":
        return _step_auto_done("country", cfg, doctor, ctx)
    if check_id == "wifi":
        return _step_auto_done("wifi", cfg, doctor, ctx)
    if check_id == "home_isp":
        return _step_auto_done("home_isp", cfg, doctor, ctx)
    if check_id == "smart_dns":
        return _step_auto_done("smart_dns", cfg, doctor, ctx)
    if check_id == "ipv6":
        return _step_auto_done("ipv6", cfg, doctor, ctx)
    if check_id == "ufw":
        return _step_auto_done("ufw", cfg, doctor, ctx)
    if check_id == "alerts":
        ac = cfg.get("alerts") or {}
        return bool(ac.get("browser_enabled", True))
    if check_id == "watch":
        ac = cfg.get("alerts") or {}
        return bool(ac.get("watch_enabled", True))
    if check_id == "email":
        return _step_auto_done("email", cfg, doctor, ctx)
    if check_id == "baseline":
        return _step_auto_done("baseline", cfg, doctor, ctx)
    if check_id == "connected":
        return bool(ctx.get("vpn_connected"))
    if check_id == "ui_health":
        from nordctl.static_assets import verify_static_ui

        return bool(verify_static_ui().get("ok"))
    return False


def _step_state(
    step_id: str,
    cfg: dict[str, Any],
    doctor: dict[str, Any],
    progress: dict[str, Any],
    ctx: dict[str, Any],
) -> str:
    if step_id in (progress.get("skipped") or []):
        return "skipped"
    if _step_auto_done(step_id, cfg, doctor, ctx):
        return "done"
    if step_id == progress.get("current"):
        return "current"
    if step_id in (progress.get("visited") or []):
        return "todo"
    return "todo"


def _next_step_id(current: str) -> str | None:
    ids = [s["id"] for s in STEP_DEFS]
    if current not in ids:
        return ids[0] if ids else None
    idx = ids.index(current)
    if idx + 1 < len(ids):
        return ids[idx + 1]
    return None


def wizard_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.doctor import run_doctor
    from nordctl.features import features_payload, is_returning_user
    from nordctl.ui_auth import ui_auth_status

    cfg = cfg or load_config()
    doctor = run_doctor(cfg)
    ctx = _wizard_context(cfg, doctor)
    progress = load_wizard_progress(cfg)
    feats = cfg.get("features") or {}
    complete = bool(progress.get("complete") or feats.get("setup_wizard_complete"))

    steps: list[dict[str, Any]] = []
    for meta in STEP_DEFS:
        sid = meta["id"]
        state = "done" if complete else _step_state(sid, cfg, doctor, progress, ctx)
        steps.append(
            {
                **meta,
                "state": "done" if complete and sid != "finish" else state,
                "auto_done": _step_auto_done(sid, cfg, doctor, ctx),
            }
        )

    current = progress.get("current") or "welcome"
    if complete:
        current = "finish"

    checklist = [
        {
            "id": cid,
            "label": label,
            "wizard_step": step,
            "ok": _checklist_ok(cid, cfg, doctor, ctx),
        }
        for cid, label, step in CHECKLIST_DEFS
    ]

    srv = cfg.get("server") or {}
    return {
        "ok": True,
        "complete": complete,
        "current_step": current,
        "steps": steps,
        "checklist": checklist,
        "context": ctx,
        "returning_user": is_returning_user(cfg),
        "onboarding_complete": bool(feats.get("onboarding_complete")),
        "legal_accepted": bool(feats.get("legal_accepted")),
        "doctor": {
            "nord_installed": doctor.get("nord_installed"),
            "logged_in": doctor.get("logged_in"),
            "ready": doctor.get("ready"),
            "setup_level": doctor.get("setup_level"),
            "privileges": doctor.get("privileges"),
        },
        "ui_bind": str(srv.get("bind") or "127.0.0.1"),
        "ui_port": int(srv.get("port") or 8765),
        "ui_auth": ui_auth_status(cfg),
        "connect_country": cfg.get("connect_country"),
        "features": features_payload(cfg),
        "ui_health": __import__("nordctl.static_assets", fromlist=["ui_health_payload"]).ui_health_payload(),
    }


def wizard_advance(
    cfg: dict[str, Any],
    *,
    step: str,
    skip: bool = False,
    mark_done: bool = False,
    legal_accepted: bool = False,
) -> dict[str, Any]:
    if legal_accepted:
        cfg.setdefault("features", {})["legal_accepted"] = True
        save_config(cfg)
    progress = load_wizard_progress(cfg)
    if step not in [s["id"] for s in STEP_DEFS]:
        return {"ok": False, "error": f"Unknown wizard step: {step}"}
    meta = next(s for s in STEP_DEFS if s["id"] == step)
    if skip and not meta.get("skippable"):
        return {"ok": False, "error": "This step cannot be skipped"}
    visited = list(progress.get("visited") or [])
    if step not in visited:
        visited.append(step)
    skipped = list(progress.get("skipped") or [])
    if skip and step not in skipped:
        skipped.append(step)
    elif mark_done and step in skipped:
        skipped = [x for x in skipped if x != step]
    nxt = _next_step_id(step)
    progress.update({"visited": visited, "skipped": skipped, "current": nxt or step})
    save_wizard_progress(progress)
    return {"ok": True, "wizard": wizard_payload(cfg)}


def wizard_goto(cfg: dict[str, Any], step: str) -> dict[str, Any]:
    if step not in [s["id"] for s in STEP_DEFS]:
        return {"ok": False, "error": f"Unknown wizard step: {step}"}
    progress = load_wizard_progress(cfg)
    progress["current"] = step
    save_wizard_progress(progress)
    return {"ok": True, "wizard": wizard_payload(cfg)}


def wizard_complete(cfg: dict[str, Any], *, legal_accepted: bool = True) -> dict[str, Any]:
    from nordctl.features import enable_all_modules

    if legal_accepted:
        feats = cfg.setdefault("features", {})
        feats["legal_accepted"] = True
    cfg["usage_mode"] = "vpn"
    cfg["install_profile"] = "full"
    save_config(cfg)
    enable_all_modules(cfg, complete=True)
    cfg = load_config()
    feats = cfg.setdefault("features", {})
    feats["setup_wizard_complete"] = True
    save_config(cfg)
    progress = load_wizard_progress(cfg)
    progress["complete"] = True
    progress["current"] = "finish"
    save_wizard_progress(progress)
    return {"ok": True, "wizard": wizard_payload(cfg), "note": "Setup wizard complete"}


def wizard_dismiss(cfg: dict[str, Any], *, legal_accepted: bool = False) -> dict[str, Any]:
    from nordctl.features import enable_all_modules

    if legal_accepted:
        cfg.setdefault("features", {})["legal_accepted"] = True
    cfg["usage_mode"] = "vpn"
    cfg["install_profile"] = "full"
    save_config(cfg)
    enable_all_modules(cfg, complete=True)
    cfg = load_config()
    feats = cfg.setdefault("features", {})
    feats["setup_wizard_complete"] = True
    save_config(cfg)
    progress = load_wizard_progress(cfg)
    progress["complete"] = True
    progress["dismissed"] = True
    save_wizard_progress(progress)
    return {"ok": True, "wizard": wizard_payload(cfg), "note": "Wizard skipped — resume anytime from Setup"}


def wizard_reopen(cfg: dict[str, Any], *, step: str | None = None) -> dict[str, Any]:
    """Clear wizard-complete flag so user can fix remaining checklist items without wiping progress."""
    feats = cfg.setdefault("features", {})
    feats["setup_wizard_complete"] = False
    save_config(cfg)
    progress = load_wizard_progress(cfg)
    progress["complete"] = False
    if step and step in [s["id"] for s in STEP_DEFS]:
        progress["current"] = step
    save_wizard_progress(progress)
    return {"ok": True, "wizard": wizard_payload(cfg), "note": "Setup wizard reopened"}


def wizard_restart(cfg: dict[str, Any]) -> dict[str, Any]:
    path = _wizard_path()
    if path.is_file():
        try:
            path.unlink()
        except OSError:
            pass
    feats = cfg.setdefault("features", {})
    feats["setup_wizard_complete"] = False
    save_config(cfg)
    return {"ok": True, "wizard": wizard_payload(cfg), "note": "Setup wizard restarted"}
