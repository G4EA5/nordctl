"""Extra settings payload — items not duplicated elsewhere in the UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from nordctl.alerts import alerts_status
from nordctl.config import load_config, save_config
from nordctl.config_fields import location_settings
from nordctl.ui_auth import ui_auth_status
from nordctl.network_access import network_access_payload
from nordctl.scan_alerts import scan_email_settings
from nordctl.service_mgr import service_overview
from nordctl.speedtest import merged_providers, speedtest_defaults, speedtest_profiles
from nordctl.ui_prefs import ui_prefs_from_config

_MIRROR_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")


def speedtest_settings_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    st = cfg.get("speedtest") or {}
    mirrors = st.get("custom_mirrors") or []
    if not isinstance(mirrors, list):
        mirrors = []
    defaults = speedtest_defaults(cfg)
    providers = merged_providers(cfg)
    return {
        **defaults,
        "custom_mirrors": [
            {
                "id": str(m.get("id") or ""),
                "label": str(m.get("label") or ""),
                "url": str(m.get("url") or ""),
                "region": str(m.get("region") or "custom"),
            }
            for m in mirrors
            if isinstance(m, dict) and m.get("id") and m.get("url")
        ],
        "builtin_providers": {
            k: v.get("label", k) for k, v in providers.items() if k not in ("auto",)
        },
        "profiles": speedtest_profiles(),
    }


def settings_config_payload(cfg: dict[str, Any]) -> dict[str, Any]:
    """Wizard-related config — editable from Tools → Settings."""
    wifi = cfg.get("wifi") or {}
    wz = cfg.get("wifi_zones") or {}
    sd = cfg.get("smart_dns") or {}
    svc = cfg.get("service") or {}
    tray = cfg.get("tray") or {}
    alerts = cfg.get("alerts") or {}
    features = cfg.get("features") or {}
    server = cfg.get("server") or {}
    return {
        "smart_dns": {
            "primary": str(sd.get("primary") or ""),
            "secondary": str(sd.get("secondary") or ""),
        },
        "wifi": {
            "device": wifi.get("device"),
            "profiles": list(wifi.get("profiles") or []),
            "profile_count": len(wifi.get("profiles") or []),
            "auto_sync_active": bool(wifi.get("auto_sync_active", True)),
            "heal_smart_dns": bool(wifi.get("heal_smart_dns", True)),
        },
        "wifi_zones": {
            "auto_apply": bool(wz.get("auto_apply")),
            "watch_enabled": bool(wz.get("watch_enabled")),
            "watch_interval": int(wz.get("watch_interval") or 30),
            "home_ip_learn": bool(wz.get("home_ip_learn", True)),
            "home_ip_when_trusted": bool(wz.get("home_ip_when_trusted", True)),
            "untrusted_preset": str(wz.get("untrusted_preset") or "public-wifi"),
            "trusted": list(wz.get("trusted") or []),
        },
        "vpn_defaults": {
            "lan_allowlist_cidr": str(cfg.get("lan_allowlist_cidr") or ""),
            "voip_ports": list(cfg.get("voip_ports") or []),
            "auto_snapshot_before_preset": bool(cfg.get("auto_snapshot_before_preset", True)),
            "nordvpn_bin": str(cfg.get("nordvpn_bin") or "nordvpn"),
        },
        "probes": {
            "public_ip_check_url": str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip"),
        },
        "home_ip_fallback": {
            "enabled": bool((cfg.get("home_ip_fallback") or {}).get("enabled")),
            "ip": str((cfg.get("home_ip_fallback") or {}).get("ip") or "").strip(),
        },
        "service_prefs": {
            "nord_autostart": bool(svc.get("autostart")),
            "tray_enabled": bool(tray.get("enabled")),
            "tray_autostart": bool(tray.get("autostart")),
        },
        "alerts_advanced": {
            "watch_interval": int(alerts.get("watch_interval") or 60),
            "rate_limit_minutes": int(alerts.get("rate_limit_minutes") or 15),
            "health_threshold": int(alerts.get("health_threshold") or 50),
        },
        "speedtest": speedtest_settings_payload(cfg),
        "server": {
            "port": int(server.get("port") or 8765),
            "demo_mode": bool(server.get("demo_mode")),
            "headless": bool(server.get("headless")),
        },
        "features": {
            "legal_accepted": bool(features.get("legal_accepted")),
            "setup_wizard_complete": bool(features.get("setup_wizard_complete")),
        },
        "usage_mode": str(cfg.get("usage_mode") or "auto"),
        "install_profile": str(cfg.get("install_profile") or "auto"),
    }


def _normalize_mirror_id(raw: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", str(raw or "").strip().lower()).strip("-")
    return slug[:48]


def _validate_mirror_url(url: str) -> str | None:
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        return None
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if not parsed.netloc:
        return None
    return url


def save_settings_config(section: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Persist a settings section from the web UI."""
    cfg = cfg or load_config()
    sec = str(section or "").strip().lower()

    if sec == "smart_dns":
        primary = str(body.get("primary") or "").strip()
        secondary = str(body.get("secondary") or "").strip()
        if not primary or not secondary:
            return {"ok": False, "error": "Primary and secondary Smart DNS IPs are required."}
        sd = cfg.setdefault("smart_dns", {})
        sd["primary"] = primary
        sd["secondary"] = secondary
        save_config(cfg)
        return {"ok": True, "note": "Smart DNS addresses saved.", "config": settings_config_payload(cfg)}

    if sec == "wifi":
        wifi = cfg.setdefault("wifi", {})
        if "auto_sync_active" in body:
            wifi["auto_sync_active"] = bool(body.get("auto_sync_active"))
        if "heal_smart_dns" in body:
            wifi["heal_smart_dns"] = bool(body.get("heal_smart_dns"))
        if body.get("device") is not None:
            dev = str(body.get("device") or "").strip()
            wifi["device"] = dev or None
        save_config(cfg)
        return {"ok": True, "note": "WiFi sync options saved.", "config": settings_config_payload(cfg)}

    if sec == "wifi_zones":
        wz = cfg.setdefault("wifi_zones", {})
        if "auto_apply" in body:
            wz["auto_apply"] = bool(body.get("auto_apply"))
        if "home_ip_learn" in body:
            wz["home_ip_learn"] = bool(body.get("home_ip_learn"))
        if "home_ip_when_trusted" in body:
            wz["home_ip_when_trusted"] = bool(body.get("home_ip_when_trusted"))
        if body.get("untrusted_preset"):
            wz["untrusted_preset"] = str(body.get("untrusted_preset")).strip()
        if body.get("watch_interval") is not None:
            wz["watch_interval"] = max(10, int(body.get("watch_interval") or 30))
        save_config(cfg)
        return {"ok": True, "note": "Trusted WiFi / home ISP options saved.", "config": settings_config_payload(cfg)}

    if sec == "vpn_defaults":
        if body.get("lan_allowlist_cidr") is not None:
            cfg["lan_allowlist_cidr"] = str(body.get("lan_allowlist_cidr") or "").strip()
        if body.get("voip_ports") is not None:
            raw = body.get("voip_ports")
            if isinstance(raw, list):
                ports = [int(p) for p in raw if str(p).strip().isdigit()]
            else:
                ports = [int(p.strip()) for p in str(raw or "").split(",") if p.strip().isdigit()]
            cfg["voip_ports"] = ports
        if "auto_snapshot_before_preset" in body:
            cfg["auto_snapshot_before_preset"] = bool(body.get("auto_snapshot_before_preset"))
        if body.get("nordvpn_bin") is not None:
            cfg["nordvpn_bin"] = str(body.get("nordvpn_bin") or "nordvpn").strip() or "nordvpn"
        save_config(cfg)
        return {"ok": True, "note": "VPN defaults saved.", "config": settings_config_payload(cfg)}

    if sec == "probes":
        url = str(body.get("public_ip_check_url") or "").strip()
        if not url.startswith(("http://", "https://")):
            return {"ok": False, "error": "Public IP check URL must start with http:// or https://"}
        cfg["public_ip_check_url"] = url
        save_config(cfg)
        return {"ok": True, "note": "Public IP probe URL saved.", "config": settings_config_payload(cfg)}

    if sec == "home_ip_fallback":
        import ipaddress

        fb = cfg.setdefault("home_ip_fallback", {})
        enabled = bool(body.get("enabled"))
        ip = str(body.get("ip") or "").strip()
        if enabled:
            if not ip:
                return {"ok": False, "error": "Enter your ISP public IPv4 address, or turn the fallback off."}
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                return {"ok": False, "error": "Invalid IPv4 address."}
            if addr.version != 4 or addr.is_private or addr.is_loopback or addr.is_reserved:
                return {"ok": False, "error": "Enter a public IPv4 address (not LAN or loopback)."}
        fb["enabled"] = enabled
        fb["ip"] = ip
        save_config(cfg)
        note = "Home ISP fallback saved — top bar will use it when live checks fail." if enabled else "Home ISP fallback disabled."
        return {"ok": True, "note": note, "config": settings_config_payload(cfg)}

    if sec == "service_prefs":
        svc = cfg.setdefault("service", {})
        tray = cfg.setdefault("tray", {})
        if "nord_autostart" in body:
            svc["autostart"] = bool(body.get("nord_autostart"))
        if "tray_enabled" in body:
            tray["enabled"] = bool(body.get("tray_enabled"))
        if "tray_autostart" in body:
            tray["autostart"] = bool(body.get("tray_autostart"))
        save_config(cfg)
        return {"ok": True, "note": "Service preferences saved.", "config": settings_config_payload(cfg)}

    if sec == "alerts_advanced":
        ac = cfg.setdefault("alerts", {})
        if body.get("watch_interval") is not None:
            ac["watch_interval"] = max(15, int(body.get("watch_interval") or 60))
        if body.get("rate_limit_minutes") is not None:
            ac["rate_limit_minutes"] = max(1, int(body.get("rate_limit_minutes") or 15))
        if body.get("health_threshold") is not None:
            ac["health_threshold"] = max(1, min(100, int(body.get("health_threshold") or 50)))
        save_config(cfg)
        return {"ok": True, "note": "Alert timing saved.", "config": settings_config_payload(cfg)}

    if sec == "speedtest":
        st = cfg.setdefault("speedtest", {})
        providers = merged_providers(cfg)

        if body.get("default_provider") is not None:
            prov = str(body.get("default_provider") or "auto").strip() or "auto"
            if prov not in providers:
                return {"ok": False, "error": f"Unknown speed test provider: {prov}"}
            st["default_provider"] = prov

        if body.get("default_profile") is not None:
            prof = str(body.get("default_profile") or "standard").strip() or "standard"
            if prof not in speedtest_profiles():
                return {"ok": False, "error": f"Unknown profile: {prof}"}
            st["default_profile"] = prof

        if body.get("default_method") is not None:
            meth = str(body.get("default_method") or "single").strip() or "single"
            if meth not in ("single", "average", "best"):
                return {"ok": False, "error": "Method must be single, average, or best."}
            st["default_method"] = meth

        if "warmup" in body:
            st["warmup"] = bool(body.get("warmup"))
        if "save_results" in body:
            st["save_results"] = bool(body.get("save_results"))

        if body.get("custom_mirrors") is not None:
            raw = body.get("custom_mirrors")
            if not isinstance(raw, list):
                return {"ok": False, "error": "custom_mirrors must be a list."}
            cleaned: list[dict[str, str]] = []
            seen: set[str] = set()
            for row in raw:
                if not isinstance(row, dict):
                    continue
                pid = _normalize_mirror_id(str(row.get("id") or row.get("label") or ""))
                if not pid or not _MIRROR_ID_RE.match(pid):
                    return {"ok": False, "error": "Each mirror needs a short id (letters, numbers, dash, underscore)."}
                if pid in seen:
                    continue
                url = _validate_mirror_url(str(row.get("url") or ""))
                if not url:
                    return {"ok": False, "error": f"Mirror '{pid}' needs a valid http:// or https:// download URL."}
                seen.add(pid)
                cleaned.append({
                    "id": pid,
                    "label": str(row.get("label") or pid).strip() or pid,
                    "url": url,
                    "region": str(row.get("region") or "custom").strip() or "custom",
                })
            st["custom_mirrors"] = cleaned

        save_config(cfg)
        return {
            "ok": True,
            "note": "Speed test settings saved — open Speed lab to use new defaults.",
            "config": settings_config_payload(cfg),
        }

    return {"ok": False, "error": f"Unknown settings section: {section}"}


def settings_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    alerts = alerts_status(cfg)
    auth = ui_auth_status(cfg)
    access = network_access_payload(cfg)
    services = service_overview(cfg)
    ui = (services.get("ui") or {}) if isinstance(services, dict) else {}
    ui_systemd = bool(ui.get("active"))
    ui_manual = bool(ui.get("manual_running"))
    email = (cfg.get("alerts") or {}).get("email") or {}
    scan_email = scan_email_settings(cfg)
    smtp_ready = bool(str(email.get("smtp_host") or "").strip() and str(email.get("to") or "").strip())

    return {
        "ok": True,
        "ui_auth": auth,
        "alerts": {
            "module_enabled": alerts.get("module_enabled"),
            "browser_enabled": alerts.get("browser_enabled"),
            "email_enabled": bool(email.get("enabled")),
            "email_configured": smtp_ready,
            "email_to": str(email.get("to") or "").strip(),
            "smtp_host": str(email.get("smtp_host") or "").strip(),
            "smtp_user": str(email.get("smtp_user") or "").strip(),
            "smtp_from": str(email.get("from") or email.get("smtp_user") or "").strip(),
            "smtp_port": int(email.get("smtp_port") or 587),
            "smtp_password_set": bool(str(email.get("smtp_password") or "").strip()),
            "smtp_use_tls": bool(email.get("use_tls", True)),
            "scan_email": scan_email,
            "watch_running": alerts.get("watch_running"),
            "watch_enabled": alerts.get("watch_enabled"),
            "watch_interval_seconds": alerts.get("watch_interval_seconds"),
            "rule_descriptions": alerts.get("rule_descriptions") or {},
            "rules": alerts.get("rules") or {},
            "privacy_note": alerts.get("privacy_note"),
        },
        "network_access": access,
        "services": {
            "ui_running": ui_systemd or ui_manual,
            "ui_systemd": ui_systemd,
            "ui_manual": ui_manual,
            "ui_enabled": bool(ui.get("enabled_at_login")),
            "ui_installed": bool(ui.get("installed")),
        },
        "links": {
            "alerts_tab": "settings/alerts/notifications",
            "services_tab": "network/services",
            "privileges_tab": "network/setup",
            "speedtest_tab": "settings/general/speed-test",
        },
        "bell_help": [
            "Browser alerts: Settings → Browser alerts — enable rules, then Save.",
            "Background watch must be running for alerts while this tab is closed (Start background watch).",
            "Toasts work without browser permission; desktop pop-ups need Allow browser notifications.",
            "Email copies use the Email tab — your SMTP only, never nordctl servers.",
        ],
        "ui_prefs": ui_prefs_from_config(cfg),
        "config": settings_config_payload(cfg),
        "locations": location_settings(cfg),
        "preset_scenarios": _preset_scenarios_settings(cfg),
        "location_scenarios": _location_scenarios_settings(cfg),
    }


def _preset_scenarios_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl.wifi_hub import hidden_preset_scenarios, wifi_scenario_rows

    return {
        "scenarios": wifi_scenario_rows(cfg),
        "hidden_scenarios": hidden_preset_scenarios(cfg),
    }


def _location_scenarios_settings(cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl.presets import load_presets
    from nordctl.security_hub import hidden_scenarios, location_profiles

    presets = [
        {
            "id": str(p.get("id") or ""),
            "label": str(p.get("label") or p.get("id") or ""),
            "summary": str(p.get("summary") or ""),
            "user": bool(p.get("user")),
        }
        for p in load_presets(cfg)
        if p.get("id")
    ]
    return {
        "scenarios": location_profiles(cfg),
        "hidden_scenarios": hidden_scenarios(cfg),
        "presets": presets,
    }
