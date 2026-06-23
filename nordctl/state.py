"""Extended API actions and rich application state."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.config import config_path, load_config, usage_payload
from nordctl.doctor import run_doctor
from nordctl.presets import load_presets
from nordctl.profiles import list_profiles
from nordctl.schedule import list_schedules
from nordctl.snapshot import list_snapshots
from nordctl.zones import zone_status


def _preset_rows(cfg: dict[str, Any], *, include_hidden: bool) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    from nordctl.preset_builder import places_pending_from_spec, spec_from_preset_document
    from nordctl.presets import load_presets, preset_region

    ui = cfg.get("ui") or {}
    hidden_presets = {str(x) for x in (ui.get("hidden_presets") or [])}
    preset_overrides = ui.get("preset_overrides") or {}
    visible: list[dict[str, Any]] = []
    hidden_rows: list[dict[str, Any]] = []
    for p in load_presets(cfg):
        pid = str(p.get("id") or "")
        ov = preset_overrides.get(pid) or {}
        row = {
            "id": pid,
            "label": ov.get("label") or p.get("label"),
            "summary": ov.get("summary") or p.get("summary"),
            "category": ov.get("category") or p.get("category") or "General",
            "region": preset_region(p),
            "requires": p.get("requires") or [],
            "user": bool(p.get("user")),
            "file_id": p.get("_file_id"),
            "hidden": pid in hidden_presets,
        }
        if p.get("user"):
            spec = spec_from_preset_document(p)
            pending = places_pending_from_spec(spec, cfg)
            row["places_pending"] = pending
            row["builder_spec"] = spec
        if pid in hidden_presets:
            if include_hidden:
                hidden_rows.append(row)
        else:
            visible.append(row)
    return visible, hidden_rows


def _fetch_nord_cli(
    bin_path: str,
    *,
    peers: bool = False,
    version: bool = False,
) -> dict[str, Any]:
    """Parallel Nord CLI reads with shared TTL cache."""
    jobs: list[tuple[str, list[str], float]] = [
        ("status", ["status"], 8),
        ("settings", ["settings"], 8),
    ]
    if peers:
        jobs.append(("peers", ["meshnet", "peer", "list"], 10))
    if version:
        jobs.append(("version", ["version"], 5))

    out: dict[str, Any] = {}
    with ThreadPoolExecutor(max_workers=min(4, len(jobs))) as pool:
        futs = {
            pool.submit(nv.run_cached, bin_path, args, timeout): name
            for name, args, timeout in jobs
        }
        for fut in futs:
            out[futs[fut]] = fut.result()
    return out


def _mesh_from_cli(settings: dict[str, Any], peers_raw: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl.meshnet_ui import parse_peers

    return {
        "ok": True,
        "mesh_ip": nv.mesh_ip(),
        "meshnet_enabled": "enabled" in str(settings.get("Meshnet", "")).lower(),
        "peers": parse_peers(peers_raw),
        "raw": peers_raw,
        "configured_peer": cfg.get("mesh_peer"),
    }


def _network_smart_dns(
    cfg: dict[str, Any],
    status: dict[str, Any],
    *,
    ip_info: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """WiFi / ISP DNS layer — separate from NordVPN tunnel settings."""
    sd_cfg = cfg.get("smart_dns") or {}
    wifi = cfg.get("wifi") or {}
    device = net.detect_wifi_device(wifi.get("device"))
    dns = net.wifi_dns_servers(device) if device else []
    primary = str(sd_cfg.get("primary") or "")
    secondary = str(sd_cfg.get("secondary") or "")
    smart_active = primary in dns and secondary in dns and not status.get("connected")
    pub_routed = net.public_ipv4(str(cfg.get("public_ip_check_url") or ""))
    from nordctl.ip_info import home_allowlist_ip

    allow = home_allowlist_ip(cfg, status, ip_info=ip_info, pub_routed=pub_routed)
    return {
        "active": smart_active,
        "dns_servers": dns,
        "public_ip": allow["public_ip"],
        "public_ip_routed": allow["public_ip_routed"],
        "public_ip_note": allow["public_ip_note"],
        "wifi_device": device,
        "profiles": list(wifi.get("profiles") or []),
        "primary": primary,
        "secondary": secondary,
        "allowlist_url": "https://my.nordaccount.com/dashboard/nordvpn/",
    }


def merge_state(*parts: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {"ok": True}
    for part in parts:
        if part:
            out.update(part)
    return out


def build_state_app(cfg: dict[str, Any] | None = None, *, include_doctor: bool = True) -> dict[str, Any]:
    """App metadata — presets, profiles, doctor, services (no Nord CLI, no WiFi probes)."""
    cfg = cfg or load_config()
    from nordctl.baseline import baseline_status, ensure_baseline

    bl_result = ensure_baseline(cfg)
    baseline = baseline_status()
    if bl_result.get("created"):
        baseline["newly_created"] = True
    visible, hidden = _preset_rows(cfg, include_hidden=True)

    from nordctl.config_fields import location_settings
    from nordctl.ui_auth import ui_auth_status
    from nordctl.privileges import privilege_status
    from nordctl.service_mgr import service_overview
    from nordctl.paths import resolve_nordctl_bin

    cli_bin = resolve_nordctl_bin()
    payload: dict[str, Any] = {
        "config_path": str(config_path()),
        "presets": visible,
        "hidden_presets": hidden,
        "profiles": list_profiles(cfg),
        "zones": zone_status(cfg),
        "schedules": list_schedules(cfg),
        "snapshots": list_snapshots()[:5],
        "baseline": baseline_status(),
        "usage": usage_payload(cfg),
        "locations": location_settings(cfg),
        "ui_auth": ui_auth_status(cfg),
        "services": service_overview(cfg),
        "privileges": privilege_status(),
        "cli": {
            "bin": cli_bin,
            "serve": f"{cli_bin} serve",
            "service_restart": f"{cli_bin} service restart",
            "path_hint": "Add ~/.local/bin to PATH if 'nordctl' is not found (pip install --user).",
        },
        "features": _features(cfg),
    }
    if include_doctor:
        payload["doctor"] = run_doctor(cfg)
    return payload


def build_state_nord(
    cfg: dict[str, Any] | None = None,
    *,
    include_countries: bool = True,
    quick: bool = False,
) -> dict[str, Any]:
    """NordVPN CLI layer — status, settings, mesh, countries."""
    cfg = cfg or load_config()
    from nordctl.demo_mode import build_demo_state_quick, is_demo_mode

    if is_demo_mode(cfg):
        demo = build_demo_state_quick(cfg)
        keep = (
            "demo_mode", "available", "nordvpn_available", "nordvpn", "status", "settings",
            "version", "mesh_ip", "mesh", "mesh_peers_raw", "countries", "connect_country",
        )
        return {k: demo[k] for k in keep if k in demo}

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")

    if not nv.available(bin_path):
        return {
            "available": False,
            "nordvpn_available": False,
            "nordvpn": {"installed": False, "logged_in": False, "connected": False},
            "connect_country": cfg.get("connect_country"),
            "countries": [],
            "status": {"connected": False},
            "settings": {},
            "mesh_ip": None,
            "mesh": {"enabled": False, "peers": []},
            "mesh_peers_raw": "",
            "version": "",
        }

    cli = _fetch_nord_cli(bin_path, peers=not quick, version=not quick)
    status = nv.parse_status(cli["status"].get("output", ""))
    settings = nv.parse_settings(cli["settings"].get("output", ""))
    peers_raw = cli["peers"].get("output", "") if not quick else ""
    ver_out = cli["version"].get("output", "").strip() if not quick else ""

    from nordctl.activity_log import maybe_log_vpn_transition

    maybe_log_vpn_transition(status)

    from nordctl.doctor import nordvpn_login_status

    logged_in, _acct = nordvpn_login_status(bin_path)
    mesh_ip = nv.mesh_ip() if not quick else None

    out: dict[str, Any] = {
        "available": True,
        "nordvpn_available": True,
        "nordvpn": {
            "installed": True,
            "logged_in": logged_in,
            "connected": bool(status.get("connected")),
        },
        "status": status,
        "settings": settings,
        "connect_country": cfg.get("connect_country"),
        "countries": nv.list_countries(bin_path) if include_countries and not quick else [],
        "mesh_ip": mesh_ip,
        "mesh_peers_raw": peers_raw,
    }
    if not quick:
        out["version"] = ver_out
        out["mesh"] = _mesh_from_cli(settings, peers_raw, cfg)
    return out


def build_state_network(
    cfg: dict[str, Any] | None = None,
    *,
    status: dict[str, Any] | None = None,
    settings: dict[str, Any] | None = None,
    mesh_ip: str | None = None,
    fast_ip: bool = False,
) -> dict[str, Any]:
    """Host/network layer — Smart DNS, UFW/Nord firewall panel, public IP (not Nord CLI settings)."""
    cfg = cfg or load_config()
    from nordctl.demo_mode import is_demo_mode

    if is_demo_mode(cfg):
        from nordctl.demo_mode import build_demo_state_quick

        demo = build_demo_state_quick(cfg)
        return {
            "smart_dns": demo.get("smart_dns") or {},
            "firewall": {"nord": {"firewall": False, "killswitch": False}, "dns": {}, "notes": []},
            "ip_info": demo.get("ip_info") or {},
            "leaklab_summary": {"score": None, "total": None},
        }

    status = status if status is not None else {"connected": False}
    settings = settings or {}

    from nordctl.firewall_panel import firewall_overview
    from nordctl.ip_info import build_ip_info

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if mesh_ip is None and nv.available(bin_path):
        mesh_ip = nv.mesh_ip()

    ip_info = build_ip_info(
        cfg,
        status,
        settings=settings,
        mesh_ip=mesh_ip,
        fast=fast_ip,
    )

    smart_dns = (
        {"active": False, "dns_servers": [], "public_ip": None, "wifi_device": None, "profiles": []}
        if fast_ip
        else _network_smart_dns(cfg, status, ip_info=ip_info)
    )
    dns = smart_dns.get("dns_servers") or []
    smart_active = bool(smart_dns.get("active"))

    firewall: dict[str, Any] = {}
    if nv.available(bin_path) and settings:
        firewall = firewall_overview(
            cfg,
            settings,
            connected=bool(status.get("connected")),
            wifi_dns=dns,
            smart_active=smart_active,
        )

    return {
        "smart_dns": smart_dns,
        "firewall": firewall,
        "ip_info": ip_info,
        "leaklab_summary": {"score": None, "total": None},
    }


def _features(cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl.features import ensure_onboarding_for_returning_user, features_payload

    ensure_onboarding_for_returning_user(cfg)
    return features_payload(cfg)


def _ensure_safety_baseline(cfg: dict[str, Any]) -> None:
    from nordctl.baseline import ensure_baseline

    ensure_baseline(cfg)


def build_state_quick(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Fast dashboard payload — Nord status + presets, no countries or network probes."""
    cfg = cfg or load_config()
    from nordctl.demo_mode import build_demo_state_quick, is_demo_mode

    if is_demo_mode(cfg):
        return build_demo_state_quick(cfg)

    presets, _hidden = _preset_rows(cfg, include_hidden=False)
    nord = build_state_nord(cfg, include_countries=False, quick=True)
    network = build_state_network(
        cfg,
        status=nord.get("status"),
        settings=nord.get("settings"),
        mesh_ip=nord.get("mesh_ip"),
        fast_ip=True,
    )
    return merge_state(
        {"quick": True},
        {"presets": presets, "usage": usage_payload(cfg)},
        nord,
        network,
    )


def build_state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl.demo_mode import build_demo_state, is_demo_mode

    if is_demo_mode(cfg):
        return build_demo_state(cfg)

    nord = build_state_nord(cfg, include_countries=True, quick=False)
    network = build_state_network(
        cfg,
        status=nord.get("status"),
        settings=nord.get("settings"),
        mesh_ip=nord.get("mesh_ip"),
        fast_ip=False,
    )
    app = build_state_app(cfg, include_doctor=True)
    return merge_state(app, nord, network)


def apply_action(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    action = str(body.get("action") or "").strip().lower()

    def wrap(result: dict[str, Any]) -> dict[str, Any]:
        if "state" not in result:
            nv.invalidate_cache(bin_path=bin_path)
            result["state"] = build_state(cfg)
        from nordctl.activity_log import log_action

        skip = action in ("service_ui", "service_nordvpnd") and str(
            body.get("op") or body.get("service_action") or ""
        ).strip().lower() == "status"
        if action and not skip:
            log_action(action, body, result)
        return result

    def wrap_light(result: dict[str, Any]) -> dict[str, Any]:
        """Config-only saves — skip full build_state (faster, avoids UI timeouts)."""
        result.setdefault("connect_country", cfg.get("connect_country"))
        result["doctor"] = run_doctor(cfg)
        from nordctl.activity_log import log_action

        if action:
            log_action(action, body, result)
        return result

    if action == "preset":
        from nordctl.presets import apply_preset

        _ensure_safety_baseline(cfg)
        dry = bool(body.get("dry_run"))
        verify = body.get("verify", True) is not False
        return wrap(apply_preset(str(body.get("preset") or ""), cfg, dry_run=dry, verify=verify and not dry))

    if action == "preset_dry_run":
        from nordctl.presets import dry_run_preset

        return wrap(dry_run_preset(str(body.get("preset") or body.get("id") or ""), cfg))

    if action == "import_config":
        from nordctl.config_bundle import import_config_bundle

        path = str(body.get("path") or body.get("archive") or "")
        merge = body.get("merge", True) is not False
        return wrap(import_config_bundle(path, merge=merge))

    if action == "import_community_preset":
        from nordctl.community_presets import import_preset_from_url

        return wrap(import_preset_from_url(str(body.get("url") or ""), cfg))

    if action == "import_preset_yaml":
        from nordctl.community_presets import import_preset_from_content, import_preset_from_url

        url = str(body.get("url") or "").strip()
        if url:
            return wrap(import_preset_from_url(url, cfg))
        content = str(body.get("yaml") or body.get("content") or "").strip()
        return wrap(import_preset_from_content(content, cfg))

    if action == "save_preset_to_my_presets":
        from nordctl.community_presets import save_preset_to_my_presets

        return wrap(save_preset_to_my_presets(str(body.get("id") or body.get("preset") or ""), cfg))

    if action == "connect":
        target = str(body.get("target") or "").strip()
        if target:
            known = {c.lower(): c for c in nv.list_countries(bin_path)}
            key = target.lower().replace(" ", "_")
            key_spaced = target.lower()
            if key in known:
                target = known[key]
            elif key_spaced in known:
                target = known[key_spaced]
            else:
                for code, canonical in known.items():
                    if code.replace("_", " ") == key_spaced:
                        target = canonical
                        break
        args = ["connect"]
        if target:
            args.extend(target.split())
        r = nv.run(bin_path, args, timeout=60)
        return wrap({"ok": r["ok"], "result": r})

    if action == "disconnect":
        r = nv.run(bin_path, ["disconnect"], timeout=20)
        return wrap({"ok": r["ok"], "result": r})

    if action == "reconnect":
        r = nv.run(bin_path, ["connect"], timeout=60)
        return wrap({"ok": r["ok"], "result": r})

    if action == "set":
        key = str(body.get("key") or "").strip()
        value = str(body.get("value") or "").strip()
        if not key or not value:
            return {"ok": False, "error": "key and value required"}
        r = nv.run(bin_path, ["set", key, value], timeout=20)
        return wrap({"ok": r["ok"], "result": r})

    if action == "run":
        from nordctl.actions import _validate_nordvpn_args

        cmd_args = body.get("args")
        if not isinstance(cmd_args, list) or not cmd_args:
            return {"ok": False, "error": "args list required"}
        safe = [str(a) for a in cmd_args]
        err = _validate_nordvpn_args(safe)
        if err:
            return {"ok": False, "error": err}
        r = nv.run(bin_path, safe, timeout=60)
        return wrap({"ok": r["ok"], "result": r})

    if action == "snapshot":
        from nordctl.snapshot import capture_snapshot, restore_snapshot

        if body.get("restore"):
            return wrap(restore_snapshot(str(body.get("id") or "") or None, cfg))
        return wrap(capture_snapshot(str(body.get("label") or "manual"), cfg))

    if action == "allowlist_add_subnet":
        from nordctl.allowlist_mgr import add_subnet

        return wrap(add_subnet(str(body.get("cidr") or ""), cfg))

    if action == "allowlist_remove_subnet":
        from nordctl.allowlist_mgr import remove_subnet

        return wrap(remove_subnet(str(body.get("cidr") or ""), cfg))

    if action == "allowlist_add_port":
        from nordctl.allowlist_mgr import add_port

        return wrap(add_port(int(body.get("port") or 0), str(body.get("protocol") or "TCP"), cfg))

    if action == "allowlist_apply_lan":
        from nordctl.allowlist_mgr import apply_lan_from_config

        return wrap(apply_lan_from_config(cfg))

    if action == "allowlist_remove_lan":
        from nordctl.allowlist_mgr import remove_lan_from_config

        return wrap(remove_lan_from_config(cfg))

    if action == "mesh_connect":
        from nordctl.meshnet_ui import connect_peer

        return wrap(connect_peer(str(body.get("peer") or ""), cfg))

    if action == "meshnet_set":
        from nordctl.meshnet_ui import set_meshnet

        val = str(body.get("value") or "on").strip().lower()
        if val not in {"on", "off"}:
            return {"ok": False, "error": "value must be on or off"}
        return wrap(set_meshnet(val == "on", cfg))

    if action == "custom_place_add":
        from nordctl.config_fields import add_custom_place, location_settings

        result = add_custom_place(
            str(body.get("label") or ""),
            str(body.get("type") or "country"),
            cfg,
        )
        if not result.get("ok"):
            return wrap(result)
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "custom_place_remove":
        from nordctl.config_fields import location_settings, remove_custom_place

        result = remove_custom_place(str(body.get("id") or body.get("place_id") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "place_hide":
        from nordctl.config_fields import hide_place, location_settings

        result = hide_place(str(body.get("id") or body.get("field") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "place_unhide":
        from nordctl.config_fields import location_settings, unhide_place

        result = unhide_place(str(body.get("id") or body.get("field") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "place_update":
        from nordctl.config_fields import location_settings, update_place

        result = update_place(str(body.get("id") or body.get("field") or ""), body, cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "scenario_add":
        from nordctl.security_hub import add_custom_scenario

        result = add_custom_scenario(body, cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _location_scenarios_settings

        cfg = load_config()
        return wrap({**result, "location_scenarios": _location_scenarios_settings(cfg)})

    if action == "scenario_remove":
        from nordctl.security_hub import remove_custom_scenario

        result = remove_custom_scenario(str(body.get("id") or body.get("profile") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _location_scenarios_settings

        cfg = load_config()
        return wrap({**result, "location_scenarios": _location_scenarios_settings(cfg)})

    if action == "scenario_hide":
        from nordctl.security_hub import hide_scenario

        result = hide_scenario(str(body.get("id") or body.get("profile") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _location_scenarios_settings

        cfg = load_config()
        return wrap({**result, "location_scenarios": _location_scenarios_settings(cfg)})

    if action == "scenario_update":
        from nordctl.security_hub import update_scenario

        result = update_scenario(str(body.get("id") or body.get("profile") or ""), body, cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _location_scenarios_settings

        cfg = load_config()
        return wrap({**result, "location_scenarios": _location_scenarios_settings(cfg)})

    if action == "preset_scenario_update":
        from nordctl.wifi_hub import update_preset_scenario

        result = update_preset_scenario(str(body.get("id") or ""), body, cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _preset_scenarios_settings

        cfg = load_config()
        return wrap({**result, "preset_scenarios": _preset_scenarios_settings(cfg)})

    if action == "preset_scenario_hide":
        from nordctl.wifi_hub import hide_preset_scenario

        result = hide_preset_scenario(str(body.get("id") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _preset_scenarios_settings

        cfg = load_config()
        return wrap({**result, "preset_scenarios": _preset_scenarios_settings(cfg)})

    if action == "preset_scenario_unhide":
        from nordctl.wifi_hub import unhide_preset_scenario

        result = unhide_preset_scenario(str(body.get("id") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _preset_scenarios_settings

        cfg = load_config()
        return wrap({**result, "preset_scenarios": _preset_scenarios_settings(cfg)})

    if action == "scenario_unhide":
        from nordctl.security_hub import unhide_scenario

        result = unhide_scenario(str(body.get("id") or body.get("profile") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        from nordctl.settings_panel import _location_scenarios_settings

        cfg = load_config()
        return wrap({**result, "location_scenarios": _location_scenarios_settings(cfg)})

    if action == "location_clear":
        from nordctl.config_fields import clear_config_field, location_settings

        result = clear_config_field(str(body.get("field") or body.get("id") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "locations": location_settings(cfg)})

    if action == "preset_delete":
        from nordctl.files import delete_user_preset

        fid = str(body.get("file_id") or body.get("id") or "")
        if fid and not fid.startswith("user/") and fid.endswith(".yaml"):
            fid = f"user/{fid}"
        elif fid and not fid.startswith("user/"):
            from nordctl.presets import load_presets

            match = next(
                (p for p in load_presets(cfg) if str(p.get("id") or "").lower() == fid.lower() and p.get("_file_id")),
                None,
            )
            fid = str(match.get("_file_id") or "") if match else fid
        return wrap(delete_user_preset(fid))

    if action == "preset_hide":
        from nordctl.config_fields import hide_preset

        result = hide_preset(str(body.get("id") or body.get("preset") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "state": build_state(cfg)})

    if action == "preset_unhide":
        from nordctl.config_fields import unhide_preset

        result = unhide_preset(str(body.get("id") or body.get("preset") or ""), cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "state": build_state(cfg)})

    if action == "preset_update":
        from nordctl.config_fields import update_preset_display
        from nordctl.files import update_user_preset_meta

        pid = str(body.get("id") or body.get("preset") or "")
        file_id = str(body.get("file_id") or "")
        meta = {k: body.get(k) for k in ("label", "summary", "category") if k in body}
        if file_id or body.get("user"):
            result = update_user_preset_meta(file_id or pid, meta)
        else:
            result = update_preset_display(pid, meta, cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "state": build_state(cfg)})

    if action == "preset_to_places":
        from nordctl.preset_builder import move_preset_to_places

        pid = str(body.get("id") or body.get("preset") or "")
        result = move_preset_to_places(pid, cfg)
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "state": build_state(cfg)})

    if action == "preset_reset_factory":
        from nordctl.config_fields import reset_presets_factory

        raw_cats = body.get("categories")
        categories = raw_cats if isinstance(raw_cats, list) else None
        result = reset_presets_factory(
            categories,
            panel=str(body.get("panel") or ""),
            cfg=cfg,
        )
        if not result.get("ok"):
            return wrap(result)
        cfg = load_config()
        return wrap({**result, "state": build_state(cfg)})

    if action == "editor_restore_baseline":
        if body.get("all"):
            from nordctl.baseline import restore_baseline

            return wrap(restore_baseline(cfg, restore_resolv=bool(body.get("restore_resolv"))))
        from nordctl.files import restore_file_from_baseline

        return wrap(restore_file_from_baseline(str(body.get("id") or "config")))

    if action == "nord_doctor_prefs":
        ui = cfg.setdefault("ui", {})
        hidden = body.get("hidden")
        if hidden is None:
            hidden = []
        ui["nord_doctor_hidden"] = [str(x).strip() for x in hidden if str(x).strip()]
        save_config(cfg)
        from nordctl.wifi_doctor import run_nord_doctor

        return wrap({"ok": True, "hidden": ui["nord_doctor_hidden"], "doctor": run_nord_doctor(cfg)})

    if action == "profile_switch":
        from nordctl.profiles import switch_profile

        return wrap(switch_profile(str(body.get("name") or "default"), cfg))

    if action == "favorite_add":
        from nordctl.profiles import add_favorite

        return wrap(add_favorite(str(body.get("kind") or "country"), str(body.get("value") or ""), cfg))

    if action == "favorite_remove":
        from nordctl.profiles import remove_favorite

        return wrap(remove_favorite(str(body.get("kind") or "country"), str(body.get("value") or ""), cfg))

    if action == "favorite_hide":
        from nordctl.profiles import hide_favorite

        return wrap(hide_favorite(str(body.get("kind") or "country"), str(body.get("value") or ""), cfg))

    if action == "favorite_unhide":
        from nordctl.profiles import unhide_favorite

        return wrap(unhide_favorite(str(body.get("kind") or "country"), str(body.get("value") or ""), cfg))

    if action == "favorite_update":
        from nordctl.profiles import update_favorite_display

        return wrap(update_favorite_display(
            str(body.get("kind") or "country"),
            str(body.get("value") or ""),
            body,
            cfg,
        ))

    if action == "zone_auto":
        from nordctl.zones import maybe_auto_apply

        result = maybe_auto_apply(cfg)
        if result is None:
            return {"ok": False, "error": "Auto-apply disabled or no matching zone"}
        return result

    if action == "schedule_add":
        from nordctl.schedule import add_schedule

        return wrap(add_schedule(body, cfg))

    if action == "schedule_remove":
        from nordctl.schedule import remove_schedule

        return wrap(remove_schedule(str(body.get("id") or ""), cfg))

    if action == "fix_resolv_immutable":
        from nordctl.privileges import run_privileged

        result = run_privileged(["chattr", "-i", "/etc/resolv.conf"], timeout=15)
        if not result["ok"] and result.get("needs_password"):
            return wrap({
                "ok": False,
                "error": "sudo password required — run in terminal: sudo chattr -i /etc/resolv.conf",
                "manual": result.get("manual"),
            })
        return wrap(result)

    if action == "fix_resolv_stub":
        from nordctl.network_audit import fix_resolv_stub

        result = fix_resolv_stub()
        if not result["ok"] and result.get("needs_password"):
            return wrap({
                "ok": False,
                "error": "sudo password required — run in terminal",
                "manual": result.get("manual"),
                "note": result.get("note"),
            })
        return wrap(result)

    if action == "disable_ipv6":
        from nordctl.network_audit import disable_ipv6

        result = disable_ipv6()
        if not result["ok"] and result.get("needs_password"):
            return wrap({
                "ok": False,
                "error": "sudo password required — run in terminal",
                "manual": result.get("manual"),
                "note": result.get("note"),
            })
        return wrap(result)

    if action == "dns_save":
        from nordctl.config import save_config

        primary = str(body.get("primary") or "").strip()
        secondary = str(body.get("secondary") or "").strip()
        if not primary or not secondary:
            return {"ok": False, "error": "primary and secondary DNS required"}
        sd = cfg.setdefault("smart_dns", {})
        sd["primary"] = primary
        sd["secondary"] = secondary
        save_config(cfg)
        return wrap_light({"ok": True, "note": "Smart DNS addresses saved to config"})

    if action == "set_connect_country":
        from nordctl.config import save_config

        raw = str(body.get("country") or "").strip()
        if not raw:
            return {"ok": False, "error": "Pick a country from the list"}
        canonical = raw.replace(" ", "_")
        cfg["connect_country"] = canonical
        save_config(cfg)
        label = canonical.replace("_", " ")
        return wrap_light({"ok": True, "note": f"Default country set to {label}"})

    if action == "set_config_field":
        from nordctl.config_fields import location_settings, set_config_field

        result = set_config_field(cfg, str(body.get("field") or ""), body.get("value"))
        if not result.get("ok"):
            return wrap_light(result)
        retry_preset = str(body.get("retry_preset") or "").strip()
        if retry_preset:
            from nordctl.presets import apply_preset

            preset_result = apply_preset(retry_preset, cfg)
            preset_result["saved_field"] = result.get("field")
            preset_result["save_note"] = result.get("note")
            return wrap(preset_result)
        return wrap_light({**result, "locations": location_settings(cfg)})

    if action == "dns_apply_smart":
        _ensure_safety_baseline(cfg)
        sd = cfg.get("smart_dns") or {}
        wifi = cfg.get("wifi") or {}
        profiles = list(wifi.get("profiles") or [])
        primary = str(sd.get("primary") or "")
        secondary = str(sd.get("secondary") or "")
        if not profiles:
            return {
                "ok": False,
                "error": "WiFi profile names are not set yet.",
                "hint": "Open the WiFi tab → Sync profiles, or add your connection name there.",
                "help_view": "wifi",
            }
        steps = net.apply_smart_dns(profiles, primary, secondary, wifi.get("device"))
        ok = all(s.get("ok") for s in steps)
        return wrap({"ok": ok, "steps": steps, "note": "Smart DNS applied on WiFi profiles"})

    if action == "dns_restore":
        wifi = cfg.get("wifi") or {}
        steps = net.restore_dns(list(wifi.get("profiles") or []), wifi.get("device"))
        ok = all(s.get("ok") for s in steps) if steps else True
        return wrap({"ok": ok, "steps": steps, "note": "Restored automatic DNS on WiFi profiles"})

    if action == "dns_nord":
        value = str(body.get("value") or "on").strip().lower()
        if value not in {"on", "off"}:
            return {"ok": False, "error": "value must be on or off"}
        r = nv.apply_dns_preference(bin_path, value == "on", cfg, timeout=20)
        return wrap({"ok": r["ok"], "result": r, "note": f"Nord DNS {value}", "error": r.get("error"), "hint": r.get("hint")})

    if action == "nord_firewall":
        value = str(body.get("value") or "on").strip().lower()
        if value not in {"on", "off"}:
            return {"ok": False, "error": "value must be on or off"}
        r = nv.run(bin_path, ["set", "firewall", value], timeout=20)
        return wrap({"ok": r["ok"], "result": r, "note": f"Nord firewall {value}"})

    if action == "nord_killswitch":
        value = str(body.get("value") or "on").strip().lower()
        if value not in {"on", "off"}:
            return {"ok": False, "error": "value must be on or off"}
        r = nv.run(bin_path, ["set", "killswitch", value], timeout=20)
        return wrap({"ok": r["ok"], "result": r, "note": f"Kill switch {value}"})

    if action == "nord_switch":
        from nordctl.switches_panel import apply_switch

        return wrap(
            apply_switch(
                str(body.get("id") or body.get("switch") or ""),
                str(body.get("value") or ""),
                cfg,
            )
        )

    if action == "baseline_restore":
        from nordctl.baseline import restore_baseline

        _ensure_safety_baseline(cfg)
        return wrap(restore_baseline(cfg, restore_resolv=bool(body.get("restore_resolv"))))

    if action == "baseline_ensure":
        from nordctl.baseline import create_baseline, ensure_baseline

        if body.get("force"):
            return wrap(create_baseline(cfg, force=True, label="manual-recreate"))
        return wrap(ensure_baseline(cfg))

    if action == "factory_reset":
        from nordctl.factory_reset import factory_reset

        return wrap(factory_reset(cfg, restore_resolv=bool(body.get("restore_resolv"))))

    if action == "service_ui":
        from nordctl.service_mgr import control_ui_service, install_ui_service, uninstall_ui_service

        op = str(body.get("op") or body.get("service_action") or "status").strip().lower()
        if op == "install":
            enable = body.get("enable", True)
            if isinstance(enable, str):
                enable = enable.lower() not in {"0", "false", "no"}
            return wrap(install_ui_service(cfg, enable=bool(enable)))
        if op == "uninstall":
            return wrap(uninstall_ui_service(cfg))
        return wrap(control_ui_service(op, cfg))

    if action == "set_server_access":
        from nordctl.network_access import apply_network_access

        mode = str(body.get("mode") or "local").strip().lower()
        custom_bind = body.get("bind")
        restart = body.get("restart", True)
        if isinstance(restart, str):
            restart = restart.lower() not in {"0", "false", "no"}
        return wrap(
            apply_network_access(
                cfg,
                mode=mode,
                bind=str(custom_bind).strip() if custom_bind else None,
                restart_service=bool(restart),
            )
        )

    if action == "service_nordvpnd":
        from nordctl.service_mgr import control_nordvpnd

        op = str(body.get("op") or body.get("service_action") or "status").strip().lower()
        result = control_nordvpnd(op)
        if not result.get("ok") and result.get("needs_password"):
            return wrap({
                "ok": False,
                "error": result.get("error") or "sudo password required",
                "manual": result.get("manual"),
            })
        return wrap(result)

    if action == "location_apply":
        from nordctl.security_hub import location_profiles
        from nordctl.presets import apply_preset

        pid = str(body.get("profile") or "").strip().lower()
        profiles = {p["id"]: p for p in location_profiles(cfg)}
        prof = profiles.get(pid)
        if not prof:
            return {"ok": False, "error": f"unknown profile: {pid}"}
        preset_result = apply_preset(str(prof.get("preset") or ""), cfg)
        steps = [preset_result]
        if prof.get("connect") and prof.get("country"):
            r = nv.run(bin_path, ["connect", str(prof["country"])], timeout=60)
            steps.append({"ok": r["ok"], "result": r})
        ok = all(s.get("ok") for s in steps)
        return wrap({
            "ok": ok,
            "note": f"{prof['label']} profile applied",
            "steps": steps,
        })

    if action == "disconnect_watch":
        from nordctl.disconnect_watch import start_disconnect_watch, stop_disconnect_watch

        if body.get("enable"):
            return wrap(start_disconnect_watch())
        return wrap(stop_disconnect_watch())

    if action == "status_page":
        from nordctl.status_share import set_status_page_enabled

        return wrap(set_status_page_enabled(bool(body.get("enable")), cfg))

    if action == "speedtest":
        from nordctl.speedtest import run_speedtest

        return wrap(run_speedtest())

    if action == "packet_capture":
        from nordctl.packet_capture import run_capture

        sec = int(body.get("seconds") or 10)
        return wrap(run_capture(sec))

    if action == "export_config":
        from nordctl.status_share import export_config_bundle

        return wrap(export_config_bundle())

    if action == "export_logs":
        from nordctl.status_share import export_logs_text

        return wrap(export_logs_text())

    if action == "nord_notify":
        from nordctl.presets import apply_preset

        val = str(body.get("value") or "on").lower()
        pid = "notifications-on" if val == "on" else "notifications-off"
        return wrap(apply_preset(pid, cfg))

    if action == "wifi_sync_profiles":
        from nordctl.wifi_hub import sync_wifi_profiles

        return wrap(sync_wifi_profiles(cfg))

    if action == "wifi_remove_stale_profiles":
        from nordctl.wifi_hub import remove_stale_wifi_profiles

        return wrap(remove_stale_wifi_profiles(cfg))

    if action == "wifi_profile_toggle":
        from nordctl.wifi_hub import toggle_wifi_profile

        return wrap(toggle_wifi_profile(str(body.get("name") or ""), add=bool(body.get("add", True)), cfg=cfg))

    if action == "wifi_delete_profile":
        from nordctl.wifi_hub import delete_wifi_profile

        return wrap(delete_wifi_profile(str(body.get("name") or ""), cfg=cfg))

    if action == "wifi_connect":
        from nordctl.wifi_hub import connect_wifi

        return wrap(
            connect_wifi(
                cfg=cfg,
                ssid=str(body.get("ssid") or "") or None,
                password=str(body.get("password") or "") or None,
                profile=str(body.get("profile") or "") or None,
            )
        )

    if action == "wifi_zone_add":
        from nordctl.wifi_hub import add_trusted_zone

        return wrap(add_trusted_zone(str(body.get("ssid") or ""), str(body.get("preset") or "streaming-smartdns"), cfg))

    if action == "wifi_zone_remove":
        from nordctl.wifi_hub import remove_trusted_zone

        return wrap(remove_trusted_zone(str(body.get("ssid") or ""), cfg))

    if action == "wifi_zones_save":
        from nordctl.wifi_hub import save_wifi_zones

        trusted = body.get("trusted")
        return wrap(
            save_wifi_zones(
                cfg,
                auto_apply=body.get("auto_apply") if "auto_apply" in body else None,
                watch_enabled=body.get("watch_enabled") if "watch_enabled" in body else None,
                untrusted_preset=str(body.get("untrusted_preset")) if body.get("untrusted_preset") else None,
                trusted=trusted if isinstance(trusted, list) else None,
            )
        )

    if action == "wifi_heal":
        from nordctl.wifi_hub import heal_wifi

        return wrap(heal_wifi(cfg))

    if action == "wifi_self_heal":
        from nordctl.wifi_hub import set_wifi_self_heal_options

        return wrap(
            set_wifi_self_heal_options(
                cfg,
                auto_sync_active=body.get("auto_sync_active") if "auto_sync_active" in body else None,
                heal_smart_dns=body.get("heal_smart_dns") if "heal_smart_dns" in body else None,
            )
        )

    if action == "wifi_zone_watch":
        from nordctl.wifi_zone_watch import start_zone_watch, stop_zone_watch

        if body.get("enable"):
            return wrap(start_zone_watch())
        return wrap(stop_zone_watch())

    if action == "wifi_rescan":
        from nordctl import network_linux as net

        wifi = cfg.get("wifi") or {}
        return wrap(net.rescan_wifi(wifi.get("device")))

    if action == "bluetooth_scan":
        from nordctl.bluetooth_spectrum import bluetooth_scan

        duration = body.get("duration") or 6
        return wrap(bluetooth_scan(int(duration)))

    if action == "onboarding_save":
        from nordctl.features import apply_modules

        modules = body.get("modules") if isinstance(body.get("modules"), dict) else {}
        um = body.get("usage_mode")
        ip = body.get("install_profile")
        if um:
            cfg["usage_mode"] = str(um).strip().lower()
        if ip:
            cfg["install_profile"] = str(ip).strip().lower()
            from nordctl.config import save_config

            save_config(cfg)
        elif um:
            from nordctl.config import save_config

            save_config(cfg)
        return wrap(
            apply_modules(
                modules,
                cfg,
                legal_accepted=bool(body.get("legal_accepted")),
                complete=bool(body.get("complete", True)),
            )
        )

    if action == "enable_network_modules":
        from nordctl.features import enable_network_modules

        return wrap(enable_network_modules(cfg))

    if action == "set_usage_mode":
        from nordctl.config import save_config, usage_payload

        mode = str(body.get("mode") or body.get("usage_mode") or "auto").strip().lower()
        if mode not in {"auto", "vpn", "tools_only"}:
            return {"ok": False, "error": f"Unknown usage mode: {mode}. Use auto, vpn, or tools_only."}
        cfg["usage_mode"] = mode
        save_config(cfg)
        return wrap({"ok": True, "usage": usage_payload(cfg), "note": usage_payload(cfg).get("label")})

    if action == "onboarding_all":
        from nordctl.features import enable_all_modules

        cfg["usage_mode"] = "vpn"
        cfg["install_profile"] = "full"
        from nordctl.config import save_config

        save_config(cfg)
        return wrap(enable_all_modules(cfg, complete=True))

    if action == "onboarding_continue":
        from nordctl.features import apply_modules, get_enabled_modules

        return wrap(
            apply_modules(
                get_enabled_modules(cfg),
                cfg,
                legal_accepted=True,
                complete=True,
            )
        )

    if action == "alerts_save":
        from nordctl.alerts import save_alerts_config

        return wrap(save_alerts_config(body, cfg))

    if action == "alerts_test":
        from nordctl.alerts import test_alerts

        return wrap(test_alerts(cfg))

    if action == "audit_email_report":
        from nordctl.overall_audit import run_overall_audit, send_audit_report_email

        audit_data = run_overall_audit(cfg)
        result = send_audit_report_email(cfg, audit_data)
        return wrap({**result, "audit": audit_data})

    if action == "privacy_export":
        from nordctl.alerts import privacy_report_export

        return wrap(privacy_report_export())

    if action in ("ui_password_set", "lab_password_set"):
        from nordctl.ui_auth import set_ui_password

        return wrap(
            set_ui_password(
                str(body.get("password") or ""),
                current=body.get("current") or None,
            )
        )

    if action in ("ui_password_clear", "lab_password_clear"):
        from nordctl.ui_auth import clear_ui_password

        return wrap(clear_ui_password(current=body.get("current") or None))

    if action == "alerts_watch":
        from nordctl.alerts import start_alerts_watch, stop_alerts_watch

        if body.get("enable"):
            return wrap(start_alerts_watch())
        return wrap(stop_alerts_watch())

    if action == "settings_email_toggle":
        from nordctl.alerts import save_alerts_config

        email = (cfg.get("alerts") or {}).get("email") or {}
        if body.get("enabled") and not str(email.get("smtp_host") or "").strip():
            return wrap({
                "ok": False,
                "error": "Enter SMTP details under Tools → Extra settings → Email before turning email on.",
            })
        return wrap(save_alerts_config({"email": {"enabled": bool(body.get("enabled"))}}, cfg))

    if action == "ui_prefs_save":
        from nordctl.ui_prefs import save_ui_prefs

        return wrap(save_ui_prefs(body, cfg))

    if action == "settings_config_save":
        from nordctl.settings_panel import save_settings_config

        section = str(body.get("section") or "").strip()
        payload = {k: v for k, v in body.items() if k not in ("action", "section")}
        return wrap(save_settings_config(section, payload, cfg))

    if action == "setup_wizard_goto":
        from nordctl.setup_wizard import wizard_goto

        return wizard_goto(cfg, str(body.get("step") or "welcome"))

    if action == "setup_wizard_advance":
        from nordctl.setup_wizard import wizard_advance

        return wizard_advance(
            cfg,
            step=str(body.get("step") or "welcome"),
            skip=bool(body.get("skip")),
            mark_done=bool(body.get("mark_done")),
            legal_accepted=bool(body.get("legal_accepted")),
        )

    if action == "setup_wizard_complete":
        from nordctl.setup_wizard import wizard_complete

        return {**wizard_complete(cfg, legal_accepted=bool(body.get("legal_accepted", True))), "state": build_state(cfg)}

    if action == "setup_wizard_dismiss":
        from nordctl.setup_wizard import wizard_dismiss

        return {**wizard_dismiss(cfg, legal_accepted=bool(body.get("legal_accepted"))), "state": build_state(cfg)}

    if action == "setup_wizard_restart":
        from nordctl.setup_wizard import wizard_restart

        return wizard_restart(cfg)

    if action == "setup_wizard_reopen":
        from nordctl.setup_wizard import wizard_reopen

        step = str(body.get("step") or "").strip() or None
        return wizard_reopen(cfg, step=step)

    return {"ok": False, "error": f"unknown action: {action}"}
