"""Security hub — orchestrates health, tools, and tier 1–3 features."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import load_config

_BUILTIN_SCENARIOS: list[dict[str, Any]] = [
    {"id": "home", "label": "Home", "emoji": "🏠", "hint": "Trusted WiFi — VPN optional, Smart DNS for TV", "preset": "streaming-smartdns", "connect": False, "country_key": "connect_country"},
    {"id": "work", "label": "Work", "emoji": "💼", "hint": "Full VPN + kill switch", "preset": "work-vpn", "connect": True, "country_key": "work_country"},
    {"id": "travel", "label": "Travel", "emoji": "✈️", "hint": "Public WiFi protection", "preset": "public-wifi", "connect": True, "country_key": "travel_country"},
    {"id": "streaming", "label": "Streaming", "emoji": "📺", "hint": "Smart DNS on WiFi — no VPN tunnel", "preset": "streaming-smartdns", "connect": False, "country_key": "connect_country"},
    {"id": "streaming-vpn", "label": "Stream via VPN", "emoji": "🎬", "hint": "Streaming through VPN exit", "preset": "streaming-vpn", "connect": True, "country_key": "connect_country"},
    {"id": "public", "label": "Public WiFi", "emoji": "☕", "hint": "Kill switch + firewall on open networks", "preset": "public-wifi", "connect": True, "country_key": "connect_country"},
    {"id": "cafe", "label": "Coffee shop", "emoji": "☕", "hint": "Same as public WiFi — untrusted hotspot", "preset": "public-wifi", "connect": True, "country_key": "connect_country"},
    {"id": "gaming", "label": "Gaming", "emoji": "🎮", "hint": "Low-latency VPN profile", "preset": "gaming", "connect": True, "country_key": "gaming_country"},
    {"id": "privacy", "label": "Privacy max", "emoji": "🔒", "hint": "Threat protection + firewall", "preset": "privacy-max", "connect": True, "country_key": "connect_country"},
    {"id": "full-vpn", "label": "Full VPN", "emoji": "🛡️", "hint": "Always-on VPN with default country", "preset": "full-vpn", "connect": True, "country_key": "connect_country"},
    {"id": "split-lan", "label": "LAN access", "emoji": "🏠", "hint": "VPN on but home LAN allowed", "preset": "split-lan", "connect": True, "country_key": "connect_country"},
    {"id": "mobile", "label": "Mobile hotspot", "emoji": "📱", "hint": "Lightweight profile for phone tether", "preset": "global-mobile", "connect": True, "country_key": "connect_country"},
    {"id": "eu", "label": "EU privacy", "emoji": "🇪🇺", "hint": "Regional — full VPN + threat protection", "preset": "eu-privacy", "connect": True, "country_key": "connect_country"},
    {"id": "disconnect", "label": "Disconnect VPN", "emoji": "⏸️", "hint": "Turn VPN off — restore defaults after", "preset": "disconnect", "connect": False, "country_key": "connect_country"},
    {"id": "restore", "label": "Restore defaults", "emoji": "↩️", "hint": "Undo Nord + WiFi DNS to baseline", "preset": "restore-defaults", "connect": False, "country_key": "connect_country"},
]


def _scenario_row(cfg: dict[str, Any], spec: dict[str, Any], *, custom: bool = False) -> dict[str, Any]:
    sec = cfg.get("security") or {}
    overrides = sec.get("location_profiles") or {}
    pid = spec["id"]
    ov = overrides.get(pid) or {}
    country_key = str(ov.get("country_key") or spec.get("country_key") or "connect_country")
    explicit_country = ov.get("country") if not custom else spec.get("country")
    return {
        "id": pid,
        "label": str(ov.get("label") or spec.get("label") or pid.replace("_", " ").title()),
        "emoji": str(ov.get("emoji") or spec.get("emoji") or "📍"),
        "hint": str(ov.get("hint") or spec.get("hint") or ""),
        "preset": str(ov.get("preset") or spec.get("preset") or "full-vpn"),
        "connect": bool(ov.get("connect", spec.get("connect", False))),
        "country": explicit_country or cfg.get(country_key) or cfg.get("connect_country"),
        "country_key": country_key,
        "country_override": bool(str(explicit_country or "").strip()) if not custom else True,
        "custom": custom,
    }


def location_profiles(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    sec = cfg.get("security") or {}
    hidden = set(str(x) for x in (sec.get("hidden_scenarios") or []))
    built_in = [_scenario_row(cfg, spec) for spec in _BUILTIN_SCENARIOS if spec["id"] not in hidden]
    return built_in + _custom_scenario_rows(cfg)


def hidden_scenarios(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    sec = cfg.get("security") or {}
    hidden = set(str(x) for x in (sec.get("hidden_scenarios") or []))
    out: list[dict[str, Any]] = []
    for spec in _BUILTIN_SCENARIOS:
        if spec["id"] in hidden:
            out.append(_scenario_row(cfg, spec))
    return out


def _custom_scenario_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    sec = cfg.get("security") or {}
    out: list[dict[str, Any]] = []
    for row in sec.get("custom_scenarios") or []:
        pid = str(row.get("id") or "").strip()
        if not pid:
            continue
        out.append(_scenario_row(cfg, row, custom=True))
    return out


def add_custom_scenario(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    import re

    cfg = cfg or load_config()
    label = str(body.get("label") or "").strip()
    if not label:
        return {"ok": False, "error": "Scenario name required"}
    sec = cfg.setdefault("security", {})
    scenarios = list(sec.get("custom_scenarios") or [])
    pid = re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or "scenario"
    existing = {str(s.get("id") or "") for s in scenarios}
    base = pid
    n = 2
    while pid in existing:
        pid = f"{base}_{n}"
        n += 1
    row = {
        "id": pid,
        "label": label,
        "emoji": str(body.get("emoji") or "📍").strip() or "📍",
        "hint": str(body.get("hint") or f"Custom scenario — applies {body.get('preset') or 'full-vpn'}"),
        "preset": str(body.get("preset") or "full-vpn").strip(),
        "connect": bool(body.get("connect")),
        "country": body.get("country") or cfg.get("connect_country"),
    }
    scenarios.append(row)
    sec["custom_scenarios"] = scenarios
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "scenario": row, "note": f"Added scenario: {label}"}


def hide_scenario(scenario_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    if not sid:
        return {"ok": False, "error": "Scenario id required"}
    sec = cfg.setdefault("security", {})
    hidden = list(sec.get("hidden_scenarios") or [])
    if sid in hidden:
        return {"ok": True, "note": "Scenario already hidden"}
    hidden.append(sid)
    sec["hidden_scenarios"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": f"Hidden scenario: {sid.replace('_', ' ')}"}


def remove_custom_scenario(scenario_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    sec = cfg.setdefault("security", {})
    scenarios = [s for s in (sec.get("custom_scenarios") or []) if str(s.get("id") or "") != sid]
    if len(scenarios) == len(sec.get("custom_scenarios") or []):
        return {"ok": False, "error": f"Unknown scenario: {sid}"}
    sec["custom_scenarios"] = scenarios
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Scenario removed"}


def update_scenario(scenario_id: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    if not sid:
        return {"ok": False, "error": "Scenario id required"}
    sec = cfg.setdefault("security", {})
    for row in sec.get("custom_scenarios") or []:
        if str(row.get("id") or "") == sid:
            if body.get("label") is not None:
                row["label"] = str(body.get("label") or "").strip() or row.get("label")
            if body.get("emoji") is not None:
                row["emoji"] = str(body.get("emoji") or "📍").strip() or "📍"
            if body.get("hint") is not None:
                row["hint"] = str(body.get("hint") or "").strip()
            if body.get("preset") is not None:
                row["preset"] = str(body.get("preset") or "full-vpn").strip()
            if "connect" in body:
                row["connect"] = bool(body.get("connect"))
            if body.get("country") is not None:
                c = str(body.get("country") or "").strip()
                row["country"] = c or cfg.get("connect_country")
            from nordctl.config import save_config

            save_config(cfg)
            return {"ok": True, "note": "Scenario updated"}
    if not any(spec["id"] == sid for spec in _BUILTIN_SCENARIOS):
        return {"ok": False, "error": f"Unknown scenario: {sid}"}
    ov = sec.setdefault("location_profiles", {}).setdefault(sid, {})
    if body.get("label") is not None:
        ov["label"] = str(body.get("label") or "").strip()
    if body.get("emoji") is not None:
        ov["emoji"] = str(body.get("emoji") or "").strip()
    if body.get("hint") is not None:
        ov["hint"] = str(body.get("hint") or "").strip()
    if body.get("preset") is not None:
        ov["preset"] = str(body.get("preset") or "").strip()
    if "connect" in body:
        ov["connect"] = bool(body.get("connect"))
    if body.get("country") is not None:
        c = str(body.get("country") or "").strip()
        if c:
            ov["country"] = c
        else:
            ov.pop("country", None)
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Scenario updated"}


def unhide_scenario(scenario_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    sec = cfg.setdefault("security", {})
    hidden = [x for x in (sec.get("hidden_scenarios") or []) if str(x) != sid]
    sec["hidden_scenarios"] = hidden
    from nordctl.config import save_config

    save_config(cfg)
    return {"ok": True, "note": "Scenario restored"}


def security_hub_summary(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fast Security tab paint — no leak lab, audit, or traffic sampling."""
    cfg = cfg or load_config()
    from nordctl.doctor import run_doctor
    from nordctl.health_score import compute_health_score
    from nordctl.disconnect_watch import disconnect_watch_status
    from nordctl.status_share import status_page_info
    from nordctl import nordvpn as nv
    from nordctl.service_mgr import service_overview
    from nordctl.meshnet_ui import meshnet_state

    doctor = run_doctor(cfg)
    services = service_overview(cfg)
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status: dict[str, Any] = {}
    if nv.available(bin_path):
        status = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))

    network_only = not nv.available(bin_path) or bool(doctor.get("tools_only"))
    health = compute_health_score(
        doctor=doctor,
        leaklab={},
        audit={},
        status=status,
        services=services,
        light=True,
        network_only=network_only,
    )
    mesh = meshnet_state(cfg)
    schedules = cfg.get("schedules") or []

    return {
        "ok": True,
        "summary": True,
        "health": health,
        "location_profiles": location_profiles(cfg),
        "hidden_scenarios": hidden_scenarios(cfg),
        "disconnect_watch": disconnect_watch_status(),
        "status_page": status_page_info(cfg),
        "meshnet": {
            "enabled": mesh.get("meshnet_enabled"),
            "mesh_ip": mesh.get("mesh_ip"),
            "peer_count": len(mesh.get("peers") or []),
            "peers": (mesh.get("peers") or [])[:12],
        },
        "schedules_summary": {
            "count": len(schedules),
            "enabled": sum(1 for s in schedules if s.get("enabled", True)),
            "hint": "Automate tab → add daily connect/disconnect times",
        },
        "quick_links": [
            {"id": "webrtc", "label": "WebRTC leak test", "url": "https://browserleaks.com/webrtc", "hint": "Opens in browser — check if real IP leaks"},
            {"id": "dns_leak", "label": "DNS leak test", "url": "https://dnscheck.tools/", "hint": "Should show Nord DNS when VPN is on"},
            {"id": "ipv6_test", "label": "IPv6 test", "url": "https://test-ipv6.com/", "hint": "Checks IPv6 reachability"},
        ],
    }


def security_hub_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl.doctor import run_doctor
    from nordctl.leaklab import run_leaklab
    from nordctl.network_audit import run_network_audit
    from nordctl.health_score import compute_health_score
    from nordctl.dns_assistant import dns_assistant_report
    from nordctl.ipv6_lan import ipv6_lan_status
    from nordctl.disconnect_watch import disconnect_watch_status
    from nordctl.status_share import homeassistant_guide, status_page_info
    from nordctl import nordvpn as nv
    from nordctl.service_mgr import service_overview
    from nordctl.traffic_watch import run_traffic_watch
    from nordctl.meshnet_ui import meshnet_state

    doctor = run_doctor(cfg)
    leaklab = run_leaklab(cfg)
    audit = run_network_audit()
    services = service_overview(cfg)
    traffic = run_traffic_watch("internet")
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status: dict[str, Any] = {}
    if nv.available(bin_path):
        status = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))

    network_only = not nv.available(bin_path) or bool(doctor.get("tools_only"))
    health = compute_health_score(
        doctor=doctor,
        leaklab=leaklab,
        audit=audit,
        status=status,
        services=services,
        traffic_summary=traffic.get("summary"),
        network_only=network_only,
    )

    mesh = meshnet_state(cfg)
    schedules = cfg.get("schedules") or []

    return {
        "ok": True,
        "health": health,
        "location_profiles": location_profiles(cfg),
        "hidden_scenarios": hidden_scenarios(cfg),
        "dns_assistant": dns_assistant_report(),
        "ipv6_lan": ipv6_lan_status(),
        "disconnect_watch": disconnect_watch_status(),
        "status_page": status_page_info(cfg),
        "homeassistant": homeassistant_guide(cfg),
        "meshnet": {
            "enabled": mesh.get("meshnet_enabled"),
            "mesh_ip": mesh.get("mesh_ip"),
            "peer_count": len(mesh.get("peers") or []),
            "peers": (mesh.get("peers") or [])[:12],
        },
        "schedules_summary": {
            "count": len(schedules),
            "enabled": sum(1 for s in schedules if s.get("enabled", True)),
            "hint": "Automate tab → add daily connect/disconnect times",
        },
        "quick_links": [
            {"id": "webrtc", "label": "WebRTC leak test", "url": "https://browserleaks.com/webrtc", "hint": "Opens in browser — check if real IP leaks"},
            {"id": "dns_leak", "label": "DNS leak test", "url": "https://dnscheck.tools/", "hint": "Should show Nord DNS when VPN is on"},
            {"id": "ipv6_test", "label": "IPv6 test", "url": "https://test-ipv6.com/", "hint": "Checks IPv6 reachability"},
        ],
        "features": {
            "bandwidth": True,
            "speedtest": True,
            "packet_capture": True,
            "export": True,
        },
    }
