"""Unified WiFi hub — view, edit, heal, zones, and scenario presets."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
from typing import Any

from nordctl.config import load_config, save_config
from nordctl import network_linux as net
from nordctl.zones import current_ssid, zone_status


# Curated one-click scenarios for the WiFi hub UI
WIFI_SCENARIOS: list[dict[str, Any]] = [
    {"id": "streaming-smartdns", "label": "Smart DNS TV", "emoji": "📺", "hint": "Nord streaming DNS on WiFi — no VPN tunnel"},
    {"id": "streaming-vpn", "label": "Stream via VPN", "emoji": "🎬", "hint": "VPN + streaming-friendly settings"},
    {"id": "public-wifi", "label": "Public WiFi", "emoji": "☕", "hint": "Kill switch + firewall + connect"},
    {"id": "work-vpn", "label": "Work VPN", "emoji": "💼", "hint": "Full tunnel + LAN split"},
    {"id": "travel", "label": "Travel", "emoji": "✈️", "hint": "Connect to travel country"},
    {"id": "full-vpn", "label": "Full VPN", "emoji": "🛡️", "hint": "Connect with default country"},
    {"id": "privacy-max", "label": "Privacy max", "emoji": "🔒", "hint": "Threat protection + firewall"},
    {"id": "gaming", "label": "Gaming", "emoji": "🎮", "hint": "Low-latency VPN profile"},
    {"id": "split-lan", "label": "LAN access", "emoji": "🏠", "hint": "VPN on, home LAN allowed"},
    {"id": "meshnet-on", "label": "Meshnet on", "emoji": "🔗", "hint": "Enable device mesh"},
    {"id": "voip-friendly", "label": "VoIP / calls", "emoji": "📞", "hint": "Allow common call ports"},
    {"id": "restore-defaults", "label": "Restore defaults", "emoji": "↩️", "hint": "Undo Nord + WiFi DNS"},
    {"id": "disconnect", "label": "Disconnect", "emoji": "⏸️", "hint": "Turn VPN off"},
    {"id": "killswitch-on", "label": "Kill switch", "emoji": "🚫", "hint": "Block traffic if VPN drops"},
    {"id": "firewall-on", "label": "Nord firewall", "emoji": "🔥", "hint": "Enable NordVPN firewall"},
    {"id": "nord-dns", "label": "Nord DNS", "emoji": "🌐", "hint": "Use Nord DNS while on VPN"},
    {"id": "eu-privacy", "label": "EU privacy", "emoji": "🇪🇺", "hint": "Regional — full VPN + threat protection"},
    {"id": "us-streaming-dns", "label": "US Smart DNS", "emoji": "🇺🇸", "hint": "Regional — WiFi streaming DNS"},
    {"id": "apac-travel", "label": "APAC travel", "emoji": "🌏", "hint": "Regional — public WiFi protection"},
    {"id": "latam-public", "label": "LATAM public", "emoji": "🌎", "hint": "Regional — kill switch on"},
    {"id": "global-mobile", "label": "Mobile data", "emoji": "📱", "hint": "Regional — lightweight NordLynx"},
]


def _wifi_scenario_row(cfg: dict[str, Any], spec: dict[str, Any]) -> dict[str, Any]:
    sec = cfg.get("security") or {}
    overrides = sec.get("preset_scenarios") or {}
    ov = overrides.get(spec["id"]) or {}
    return {
        "id": spec["id"],
        "label": str(ov.get("label") or spec.get("label") or spec["id"]),
        "emoji": str(ov.get("emoji") or spec.get("emoji") or "⚡"),
        "hint": str(ov.get("hint") or spec.get("hint") or ""),
        "builtin": True,
    }


def wifi_scenario_rows(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    sec = cfg.get("security") or {}
    hidden = set(str(x) for x in (sec.get("hidden_preset_scenarios") or []))
    return [_wifi_scenario_row(cfg, spec) for spec in WIFI_SCENARIOS if spec["id"] not in hidden]


def hidden_preset_scenarios(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    sec = cfg.get("security") or {}
    hidden = set(str(x) for x in (sec.get("hidden_preset_scenarios") or []))
    return [_wifi_scenario_row(cfg, spec) for spec in WIFI_SCENARIOS if spec["id"] in hidden]


def update_preset_scenario(scenario_id: str, body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    if not sid:
        return {"ok": False, "error": "Scenario id required"}
    if not any(spec["id"] == sid for spec in WIFI_SCENARIOS):
        return {"ok": False, "error": f"Unknown preset scenario: {sid}"}
    sec = cfg.setdefault("security", {})
    ov = sec.setdefault("preset_scenarios", {}).setdefault(sid, {})
    if body.get("label") is not None:
        ov["label"] = str(body.get("label") or "").strip()
    if body.get("emoji") is not None:
        ov["emoji"] = str(body.get("emoji") or "").strip()
    if body.get("hint") is not None:
        ov["hint"] = str(body.get("hint") or "").strip()
    save_config(cfg)
    return {"ok": True, "note": "Preset scenario updated"}


def hide_preset_scenario(scenario_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    if not sid:
        return {"ok": False, "error": "Scenario id required"}
    if not any(spec["id"] == sid for spec in WIFI_SCENARIOS):
        return {"ok": False, "error": f"Unknown preset scenario: {sid}"}
    sec = cfg.setdefault("security", {})
    hidden = list(sec.get("hidden_preset_scenarios") or [])
    if sid in hidden:
        return {"ok": True, "note": "Preset scenario already hidden"}
    hidden.append(sid)
    sec["hidden_preset_scenarios"] = hidden
    save_config(cfg)
    return {"ok": True, "note": f"Hidden preset scenario: {sid.replace('_', ' ')}"}


def unhide_preset_scenario(scenario_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sid = str(scenario_id or "").strip()
    sec = cfg.setdefault("security", {})
    hidden = [x for x in (sec.get("hidden_preset_scenarios") or []) if str(x) != sid]
    sec["hidden_preset_scenarios"] = hidden
    save_config(cfg)
    return {"ok": True, "note": "Preset scenario restored"}


def wifi_connection_status(
    cfg: dict[str, Any] | None = None,
    *,
    status: dict[str, Any] | None = None,
    ip_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    wifi = cfg.get("wifi") or {}
    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    nmcli_ok = shutil.which("nmcli") is not None
    dev_info = net.wifi_device_status(wifi.get("device"))
    device = dev_info.get("device")
    ssid = current_ssid()
    live_dns = net.wifi_dns_servers(device) if device else []
    drift = net.smart_dns_drift(
        list(wifi.get("profiles") or []),
        primary,
        secondary,
        device=device,
    )
    pub_routed = net.public_ipv4(str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip"))
    if ip_info is None and status is not None:
        from nordctl.ip_info import build_ip_info

        ip_info = build_ip_info(cfg, status, fast=False)
    from nordctl.ip_info import home_allowlist_ip

    allow = home_allowlist_ip(cfg, status or {}, ip_info=ip_info, pub_routed=pub_routed)
    return {
        "nmcli_ok": nmcli_ok,
        "device": device,
        "connected": dev_info.get("connected"),
        "state": dev_info.get("state"),
        "ssid": ssid,
        "active_profile": dev_info.get("active_profile"),
        "live_dns": live_dns,
        "smart_dns_drift": drift,
        "public_ip": allow["public_ip"],
        "public_ip_routed": allow["public_ip_routed"],
        "public_ip_note": allow["public_ip_note"],
        "primary": primary,
        "secondary": secondary,
    }


def wifi_profile_rows(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    from nordctl.files import list_wifi_profiles

    cfg = cfg or load_config()
    configured = list((cfg.get("wifi") or {}).get("profiles") or [])
    nm_list = list_wifi_profiles().get("profiles") or []
    nm_names = {p["name"] for p in nm_list}
    conn = wifi_connection_status(cfg)
    active = conn.get("active_profile")
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()

    for name in configured:
        seen.add(name)
        ps = net.profile_dns_settings(name) if name in nm_names else {}
        rows.append({
            "name": name,
            "in_config": True,
            "exists_in_nm": name in nm_names,
            "active": name == active,
            "ssid": ps.get("ssid") or "",
            "dns_servers": ps.get("dns_servers") or [],
            "ignore_auto_dns": ps.get("ignore_auto_dns"),
            "ipv6_method": ps.get("ipv6_method") or "",
        })

    for p in nm_list:
        name = p["name"]
        if name in seen:
            continue
        ps = net.profile_dns_settings(name)
        rows.append({
            "name": name,
            "in_config": False,
            "exists_in_nm": True,
            "active": name == active,
            "ssid": ps.get("ssid") or "",
            "dns_servers": ps.get("dns_servers") or [],
            "ignore_auto_dns": ps.get("ignore_auto_dns"),
            "ipv6_method": ps.get("ipv6_method") or "",
        })
    rows.sort(key=lambda r: (not r.get("active"), not r.get("in_config"), r["name"].lower()))
    return rows


def sync_wifi_profiles(cfg: dict[str, Any] | None = None, *, include_active: bool = True) -> dict[str, Any]:
    from nordctl.files import insert_wifi_profiles_into_config, list_wifi_profiles

    cfg = cfg or load_config()
    names: list[str] = []
    if include_active:
        conn = wifi_connection_status(cfg)
        if conn.get("active_profile"):
            names.append(str(conn["active_profile"]))
    for p in list_wifi_profiles().get("profiles") or []:
        names.append(p["name"])
    return insert_wifi_profiles_into_config(names)


def remove_stale_wifi_profiles(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Drop wifi.profiles entries that no longer exist in NetworkManager."""
    cfg = cfg or load_config()
    rows = wifi_profile_rows(cfg)
    stale = [r["name"] for r in rows if r.get("in_config") and not r.get("exists_in_nm")]
    if not stale:
        return {"ok": True, "removed": [], "note": "No stale WiFi profiles in config"}
    wifi = cfg.setdefault("wifi", {})
    profiles = [p for p in list(wifi.get("profiles") or []) if p not in stale]
    wifi["profiles"] = profiles
    save_config(cfg)
    return {
        "ok": True,
        "removed": stale,
        "profiles": profiles,
        "note": f"Removed {len(stale)} stale profile(s): {', '.join(stale)}",
    }


def toggle_wifi_profile(name: str, *, add: bool, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    wifi = cfg.setdefault("wifi", {})
    profiles = list(wifi.get("profiles") or [])
    n = str(name).strip()
    if not n:
        return {"ok": False, "error": "profile name required"}
    if add:
        if n not in profiles:
            profiles.append(n)
    else:
        profiles = [p for p in profiles if p != n]
    wifi["profiles"] = profiles
    save_config(cfg)
    return {"ok": True, "profiles": profiles, "note": f"{'Added' if add else 'Removed'} {n}"}


def delete_wifi_profile(name: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Delete a NetworkManager WiFi profile and drop it from nordctl config."""
    cfg = cfg or load_config()
    n = str(name).strip()
    if not n:
        return {"ok": False, "error": "profile name required"}
    if not shutil.which("nmcli"):
        return {"ok": False, "error": "nmcli not available"}
    rows = wifi_profile_rows(cfg)
    row = next((r for r in rows if r["name"] == n), None)
    if not row:
        return {"ok": False, "error": f"profile not found: {n}"}
    if not row.get("exists_in_nm"):
        toggle_wifi_profile(n, add=False, cfg=cfg)
        return {"ok": True, "note": f"Removed stale profile “{n}” from config only"}
    result = net.delete_wifi_connection(n)
    if not result.get("ok"):
        return result
    toggle_wifi_profile(n, add=False, cfg=cfg)
    result["note"] = result.get("note") or f"Deleted profile “{n}”"
    return result


def connect_wifi(
    *,
    ssid: str | None = None,
    password: str | None = None,
    profile: str | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Connect via saved profile name or join a new SSID (password optional for open networks)."""
    cfg = cfg or load_config()
    wifi = cfg.get("wifi") or {}
    if not shutil.which("nmcli"):
        return {"ok": False, "error": "nmcli not available"}
    profile_name = str(profile or "").strip()
    if profile_name:
        result = net.connect_wifi_profile(profile_name)
    else:
        result = net.connect_wifi_ssid(str(ssid or ""), password, wifi.get("device"))
    if not result.get("ok"):
        return result
    if wifi.get("auto_sync_active", True):
        sync_wifi_profiles(cfg)
    return result


def save_wifi_zones(
    cfg: dict[str, Any] | None = None,
    *,
    auto_apply: bool | None = None,
    watch_enabled: bool | None = None,
    untrusted_preset: str | None = None,
    trusted: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    zones = cfg.setdefault("wifi_zones", {})
    if auto_apply is not None:
        zones["auto_apply"] = bool(auto_apply)
    if watch_enabled is not None:
        zones["watch_enabled"] = bool(watch_enabled)
    if untrusted_preset is not None:
        zones["untrusted_preset"] = str(untrusted_preset).strip() or "public-wifi"
    if trusted is not None:
        zones["trusted"] = trusted
    save_config(cfg)
    return {"ok": True, "zones": zone_status(cfg)}


def add_trusted_zone(ssid: str, preset: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    zones = cfg.setdefault("wifi_zones", {})
    trusted = list(zones.get("trusted") or [])
    ssid = str(ssid).strip()
    preset = str(preset).strip() or "streaming-smartdns"
    if not ssid:
        return {"ok": False, "error": "SSID required"}
    trusted = [e for e in trusted if not (isinstance(e, dict) and e.get("ssid") == ssid)]
    trusted.append({"ssid": ssid, "preset": preset})
    zones["trusted"] = trusted
    save_config(cfg)
    return {"ok": True, "note": f"Trusted zone: {ssid} → {preset}", "zones": zone_status(cfg)}


def remove_trusted_zone(ssid: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    zones = cfg.setdefault("wifi_zones", {})
    ssid = str(ssid).strip()
    trusted = [e for e in (zones.get("trusted") or []) if not (isinstance(e, dict) and e.get("ssid") == ssid)]
    zones["trusted"] = trusted
    save_config(cfg)
    return {"ok": True, "zones": zone_status(cfg)}


def heal_wifi(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Self-heal: sync profiles, fix Smart DNS drift, apply zone if enabled."""
    cfg = cfg or load_config()
    wifi = cfg.get("wifi") or {}
    steps: list[dict[str, Any]] = []

    if wifi.get("auto_sync_active", True):
        steps.append({"step": "sync_profiles", **sync_wifi_profiles(cfg)})

    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    profiles = list((cfg.get("wifi") or {}).get("profiles") or [])
    drift = net.smart_dns_drift(profiles, primary, secondary, device=(wifi.get("device")))
    if wifi.get("heal_smart_dns", True) and drift.get("drift") and profiles and primary:
        mod_steps = net.apply_smart_dns(profiles, primary, secondary, wifi.get("device"))
        ok = all(s.get("ok") for s in mod_steps)
        steps.append({"step": "smart_dns", "ok": ok, "steps": mod_steps, "note": "Re-applied Smart DNS"})

    zones = cfg.get("wifi_zones") or {}
    if zones.get("auto_apply"):
        from nordctl.zones import maybe_auto_apply

        applied = maybe_auto_apply(cfg)
        if applied:
            steps.append({"step": "zone_preset", **applied})

    ok = all(s.get("ok", True) for s in steps) if steps else True
    return {"ok": ok, "steps": steps, "note": "Self-heal completed" if ok else "Some heal steps failed"}


def set_wifi_self_heal_options(
    cfg: dict[str, Any] | None = None,
    *,
    auto_sync_active: bool | None = None,
    heal_smart_dns: bool | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    wifi = cfg.setdefault("wifi", {})
    if auto_sync_active is not None:
        wifi["auto_sync_active"] = bool(auto_sync_active)
    if heal_smart_dns is not None:
        wifi["heal_smart_dns"] = bool(heal_smart_dns)
    save_config(cfg)
    return {"ok": True, "wifi": dict(wifi)}


def wifi_hub_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl import nordvpn as nv
    from nordctl.ip_info import build_ip_info
    from nordctl.wifi_doctor import run_all_wifi_hub_doctors
    from nordctl.wifi_zone_watch import zone_watch_status

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status: dict[str, Any] = {"connected": False}
    settings: dict[str, Any] = {}
    mesh_ip = None
    if nv.available(bin_path):
        status = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))
        settings = nv.parse_settings(nv.run_cached(bin_path, ["settings"], timeout=8).get("output", ""))
        mesh_ip = nv.mesh_ip()
    ip_info = build_ip_info(cfg, status, settings=settings, mesh_ip=mesh_ip, fast=False)
    conn = wifi_connection_status(cfg, status=status, ip_info=ip_info)
    rows = wifi_profile_rows(cfg)
    zones = zone_status(cfg)
    wifi = cfg.get("wifi") or {}
    zone_cfg = cfg.get("wifi_zones") or {}
    scan = net.wifi_scan(wifi.get("device")) if conn.get("device") else []

    return {
        "ok": True,
        "connection": conn,
        "profiles": rows,
        "zones": zones,
        "zones_config": {
            "auto_apply": bool(zone_cfg.get("auto_apply")),
            "watch_enabled": bool(zone_cfg.get("watch_enabled")),
            "watch_interval": int(zone_cfg.get("watch_interval") or 30),
            "untrusted_preset": zone_cfg.get("untrusted_preset") or "public-wifi",
            "trusted": list(zone_cfg.get("trusted") or []),
        },
        "self_heal": {
            "auto_sync_active": bool(wifi.get("auto_sync_active", True)),
            "heal_smart_dns": bool(wifi.get("heal_smart_dns", True)),
        },
        "zone_watch": zone_watch_status(),
        "nearby": scan,
        "scenarios": wifi_scenario_rows(cfg),
        "doctors": run_all_wifi_hub_doctors(cfg),
        "hints": [
            "Add your home WiFi connection name to wifi.profiles before Smart DNS — it also marks home WiFi for the top bar Home chip.",
            "Trusted zones auto-suggest presets — optional home_public_ip per SSID; enable watch for hands-free switching.",
            "Disconnect VPN once at home to auto-learn your ISP into home_ip_cache.json.",
            "Run all three doctors after changing network or Nord settings.",
        ],
    }
