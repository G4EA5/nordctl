"""WiFi, network, and NordVPN helper doctors for the WiFi hub."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import load_config
from nordctl.network_linux import _scan_missing_2g, wifi_scan


def _check(
    cid: str,
    ok: bool,
    summary: str,
    *,
    fix: list[str] | None = None,
    severity: str = "error",
    action: str | None = None,
) -> dict[str, Any]:
    return {
        "id": cid,
        "ok": ok,
        "severity": severity if not ok else "info",
        "summary": summary,
        "fix": fix or [],
        "action": action,
    }


def run_wifi_doctor(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """NetworkManager + Smart DNS + profile alignment checks."""
    from nordctl.wifi_hub import wifi_connection_status, wifi_profile_rows

    cfg = cfg or load_config()
    checks: list[dict[str, Any]] = []
    conn = wifi_connection_status(cfg)
    rows = wifi_profile_rows(cfg)
    wifi_cfg = cfg.get("wifi") or {}
    profiles = list(wifi_cfg.get("profiles") or [])
    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")

    checks.append(
        _check(
            "nmcli",
            conn.get("nmcli_ok", False),
            "NetworkManager CLI available" if conn.get("nmcli_ok") else "nmcli not found — install NetworkManager",
            fix=["sudo apt install network-manager"],
            severity="error",
        )
    )
    checks.append(
        _check(
            "wifi_device",
            bool(conn.get("device")),
            f"WiFi device: {conn.get('device')}" if conn.get("device") else "No WiFi device detected",
            fix=["Plug in WiFi adapter or enable wireless in BIOS/settings"],
            severity="warning",
        )
    )
    checks.append(
        _check(
            "wifi_connected",
            bool(conn.get("connected")),
            f"Connected to {conn.get('ssid') or '—'}" if conn.get("connected") else "Not connected to WiFi",
            fix=["Connect to a network in system settings, then refresh"],
            severity="info",
        )
    )

    scan_rows = wifi_scan(conn.get("device")) if conn.get("device") else []
    scan_thin = bool(conn.get("device")) and _scan_missing_2g(scan_rows)
    checks.append(
        _check(
            "wifi_dualband_scan",
            not scan_thin,
            "WiFi scan lists 2.4 GHz networks"
            if not scan_thin
            else "Scan looks 5 GHz-only — 2.4 GHz SSIDs (e.g. C1) may be missing from the desktop list",
            fix=[
                "WiFi tab → Rescan (restarts NetworkManager when needed)",
                "Or run: sudo systemctl restart NetworkManager",
            ],
            severity="warning" if scan_thin else "info",
            action="wifi_rescan",
        )
    )
    checks.append(
        _check(
            "wifi_profiles_configured",
            bool(profiles),
            f"{len(profiles)} profile(s) in config" if profiles else "No wifi.profiles in config — Smart DNS cannot apply",
            fix=["WiFi tab → Sync profiles, or add active connection"],
            severity="warning" if not profiles else "info",
            action="wifi_sync_profiles",
        )
    )

    missing_nm = [r for r in rows if r.get("in_config") and not r.get("exists_in_nm")]
    checks.append(
        _check(
            "profiles_exist_in_nm",
            not missing_nm,
            "All configured profiles exist in NetworkManager"
            if not missing_nm
            else f"Missing in NM: {', '.join(r['name'] for r in missing_nm[:3])}",
            fix=["Click Fix to remove placeholder names from config.yaml"],
            severity="warning",
            action="wifi_remove_stale_profiles",
        )
    )

    active = conn.get("active_profile")
    if active and profiles:
        in_list = active in profiles
        checks.append(
            _check(
                "active_profile_in_config",
                in_list,
                f"Active profile “{active}” is tracked in config"
                if in_list
                else f"Active profile “{active}” not in wifi.profiles — Smart DNS skips it",
                fix=["WiFi tab → Add active profile to config"],
                severity="warning",
                action="wifi_sync_profiles",
            )
        )

    drift = conn.get("smart_dns_drift") or {}
    if profiles and primary:
        checks.append(
            _check(
                "smart_dns_drift",
                not drift.get("drift"),
                "Smart DNS matches config on all profiles"
                if not drift.get("drift")
                else drift.get("detail") or "Smart DNS drift detected",
                fix=["WiFi tab → Apply Smart DNS, or enable self-heal"],
                severity="warning",
                action="wifi_heal_smart_dns",
            )
        )

    live = conn.get("live_dns") or []
    if primary and live:
        expected = {primary, secondary} - {""}
        live_set = set(live)
        live_ok = expected.issubset(live_set) or primary in live_set
        checks.append(
            _check(
                "live_dns",
                live_ok,
                f"Live DNS: {', '.join(live)}" if live_ok else f"Live DNS {', '.join(live)} ≠ expected Nord Smart DNS",
                fix=["Apply Smart DNS and bounce WiFi"],
                severity="warning",
                action="dns_apply_smart",
            )
        )

    blocking = sum(1 for c in checks if not c["ok"] and c["severity"] == "error")
    warnings = sum(1 for c in checks if not c["ok"] and c["severity"] == "warning")
    return {
        "ok": blocking == 0,
        "title": "WiFi doctor",
        "checks": checks,
        "blocking_count": blocking,
        "warning_count": warnings,
        "hint": "Fixes WiFi profiles, Smart DNS drift, and NetworkManager alignment.",
    }


def run_network_doctor(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """DNS, IPv6, resolv.conf — network path checks."""
    from nordctl.network_audit import run_network_audit
    from nordctl.dns_assistant import dns_assistant_report

    cfg = cfg or load_config()
    audit = run_network_audit()
    dns_asst = dns_assistant_report()
    checks: list[dict[str, Any]] = []

    for c in audit.get("checks") or []:
        checks.append(
            _check(
                str(c.get("id") or "audit"),
                bool(c.get("ok")),
                str(c.get("summary") or ""),
                fix=list(c.get("fix") or []),
                severity=str(c.get("severity") or "warning"),
                action="disable_ipv6" if c.get("id") == "ipv6" and not c.get("ok") else None,
            )
        )

    for f in dns_asst.get("findings") or []:
        if not f.get("detected"):
            continue
        checks.append(
            _check(
                f"dns_{f.get('name', '').lower().replace(' ', '_')}",
                not f.get("active") or f.get("name") == "systemd-resolved",
                f"{f.get('name')}: {f.get('detail', '')}",
                fix=list(dns_asst.get("tips") or [])[:2],
                severity="info" if f.get("active") else "info",
            )
        )

    blocking = sum(1 for c in checks if not c["ok"] and c["severity"] == "error")
    warnings = sum(1 for c in checks if not c["ok"] and c["severity"] == "warning")
    return {
        "ok": blocking == 0,
        "title": "Network doctor",
        "checks": checks,
        "blocking_count": blocking,
        "warning_count": warnings,
        "hint": "DNS leaks, IPv6 bypass, and resolver conflicts.",
    }


def run_nord_doctor(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """NordVPN daemon, login, firewall, kill switch readiness."""
    from nordctl.doctor import run_doctor
    from nordctl import nordvpn as nv

    cfg = cfg or load_config()
    doctor = run_doctor(cfg)
    nord_ids = {
        "nordvpn_cli",
        "nordvpnd",
        "nordvpn_login",
        "connect_country",
    }
    checks: list[dict[str, Any]] = []
    for c in doctor.get("checks") or []:
        if c.get("id") not in nord_ids:
            continue
        checks.append(
            _check(
                str(c.get("id")),
                bool(c.get("ok")),
                str(c.get("summary") or ""),
                fix=list(c.get("fix") or []),
                severity=str(c.get("severity") or "error"),
            )
        )

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if nv.available(bin_path):
        ver_r = nv.run_cached(bin_path, ["version"], timeout=8)
        ver_lines = [ln.strip() for ln in (ver_r.get("output") or "").splitlines() if ln.strip()]
        ver_line = ver_lines[0] if ver_lines else "unknown"
        checks.append(
            _check(
                "nord_version",
                bool(ver_r.get("ok")),
                f"NordVPN client: {ver_line}",
                severity="info",
            )
        )

        st = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=8).get("output", ""))
        if st.get("connected"):
            host = st.get("Hostname") or st.get("Server") or st.get("Country") or "connected"
            vpn_summary = f"VPN connected — {host}"
        else:
            vpn_summary = "VPN disconnected"
        checks.append(_check("nord_vpn_connected", True, vpn_summary, severity="info"))

        settings = nv.parse_settings(nv.run_cached(bin_path, ["settings"], timeout=8).get("output", ""))
        tech = settings.get("Technology") or settings.get("technology") or "unknown"
        proto = settings.get("Protocol") or settings.get("protocol") or ""
        tech_summary = f"Technology: {tech}" + (f" ({proto})" if proto else "")
        checks.append(_check("nord_technology", True, tech_summary, severity="info"))

        ac = settings.get("Auto-connect") or settings.get("autoconnect") or "unknown"
        checks.append(_check("nord_autoconnect", True, f"Auto-connect: {ac}", severity="info"))

        mesh = settings.get("Meshnet") or settings.get("meshnet") or "unknown"
        checks.append(_check("nord_meshnet", True, f"Meshnet: {mesh}", severity="info"))

        dns = settings.get("DNS") or settings.get("dns") or "unknown"
        checks.append(_check("nord_dns_setting", True, f"DNS: {dns}", severity="info"))

        tp = (
            settings.get("Threat Protection")
            or settings.get("Threat protection")
            or settings.get("threatprotection")
            or "unknown"
        )
        checks.append(_check("nord_threat_protection", True, f"Threat Protection: {tp}", severity="info"))

        fw = str(settings.get("Firewall") or settings.get("firewall") or "").lower()
        ks = str(settings.get("Kill Switch") or settings.get("killswitch") or "").lower()
        fw_on = fw in ("enabled", "on", "yes")
        ks_on = ks in ("enabled", "on", "yes")
        checks.append(
            _check(
                "nord_firewall",
                True,
                f"Nord firewall: {fw or 'unknown'}{' ✓' if fw_on else ' — enable on public WiFi'}",
                fix=[] if fw_on else ["Use public-wifi preset or WiFi doctor Fix"],
                severity="info",
                action=None if fw_on else "nord_firewall_on",
            )
        )
        checks.append(
            _check(
                "nord_killswitch",
                True,
                f"Kill switch: {ks or 'unknown'}{' ✓' if ks_on else ' — recommended on untrusted WiFi'}",
                fix=[] if ks_on else ["Enable kill switch when traveling"],
                severity="info",
                action=None if ks_on else "nord_killswitch_on",
            )
        )

        from nordctl.privileges import privilege_status

        priv = privilege_status()
        in_grp = bool(priv.get("nordvpn_group"))
        checks.append(
            _check(
                "nordvpn_group",
                in_grp,
                "User in nordvpn group — CLI works without sudo"
                if in_grp
                else "Not in nordvpn group — some nordvpn commands need sudo",
                fix=[]
                if in_grp
                else [
                    "sudo usermod -aG nordvpn $USER",
                    "Log out and back in for the group to apply",
                ],
                severity="info" if in_grp else "warning",
            )
        )

    smart = cfg.get("smart_dns") or {}
    smart_primary = smart.get("primary") or smart.get("ip") or ""
    smart_secondary = smart.get("secondary") or ""
    if smart_primary:
        dns_bits = [smart_primary]
        if smart_secondary:
            dns_bits.append(smart_secondary)
        checks.append(
            _check(
                "nordctl_smart_dns",
                True,
                f"Smart DNS IPs saved in nordctl ({', '.join(dns_bits)})",
                severity="info",
            )
        )
    else:
        checks.append(
            _check(
                "nordctl_smart_dns",
                False,
                "Smart DNS IPs not configured in nordctl",
                ["Set IPs under Nord Dashboard → Nord DNS or WiFi → Smart DNS"],
                severity="info",
            )
        )

    hidden = set((cfg.get("ui") or {}).get("nord_doctor_hidden") or [])
    visible = [c for c in checks if c.get("id") not in hidden]
    blocking = sum(1 for c in visible if not c["ok"] and c["severity"] == "error")
    warnings = sum(1 for c in visible if not c["ok"] and c["severity"] == "warning")
    return {
        "ok": blocking == 0,
        "title": "NordVPN doctor",
        "checks": visible,
        "all_checks": [{"id": c["id"], "label": c.get("summary") or c["id"]} for c in checks],
        "hidden": sorted(hidden),
        "blocking_count": blocking,
        "warning_count": warnings,
        "hint": "Daemon, account, and travel-safe Nord settings.",
    }


def run_all_wifi_hub_doctors(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    wifi = run_wifi_doctor(cfg)
    network = run_network_doctor(cfg)
    nord = run_nord_doctor(cfg)
    total_block = wifi["blocking_count"] + network["blocking_count"] + nord["blocking_count"]
    total_warn = wifi["warning_count"] + network["warning_count"] + nord["warning_count"]
    return {
        "ok": total_block == 0,
        "wifi": wifi,
        "network": network,
        "nord": nord,
        "blocking_count": total_block,
        "warning_count": total_warn,
        "summary": f"{total_block} critical · {total_warn} warnings across WiFi, network, and Nord checks",
    }
