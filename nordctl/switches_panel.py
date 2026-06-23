"""Live NordVPN toggles — change one setting mid-session with plain-English help."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl import nordvpn as nv

# settings_key: label(s) in `nordvpn settings` output
# nord_key: CLI `nordvpn set <nord_key> <value>`
# type: toggle | choice
SWITCH_DEFS: list[dict[str, Any]] = [
    {
        "id": "killswitch",
        "section": "Safety",
        "label": "Kill switch",
        "nord_key": "killswitch",
        "settings_keys": ["Kill Switch"],
        "type": "toggle",
        "explain": "Blocks all internet if the VPN tunnel drops unexpectedly. Turn off only when you deliberately need traffic without VPN.",
        "warn_enable": "If the VPN disconnects while this is on, you will have no internet until you reconnect or turn kill switch off.",
        "warn_disable": "Traffic may go over your normal WiFi if the VPN drops.",
    },
    {
        "id": "firewall",
        "section": "Safety",
        "label": "Nord firewall",
        "nord_key": "firewall",
        "settings_keys": ["Firewall"],
        "type": "toggle",
        "explain": "NordVPN’s own packet filter while connected — not Linux UFW. Can block LAN unless subnets are allowlisted under Split tunnel.",
        "warn_enable": "Local printers and NAS may stop working until you add a split-tunnel allowlist.",
    },
    {
        "id": "fwmark",
        "section": "Safety",
        "label": "Firewall mark (fwmark)",
        "nord_key": "fwmark",
        "settings_keys": ["Firewall Mark"],
        "type": "value",
        "placeholder": "0xe1f1",
        "explain": "Policy-routing mark Nord tags on packets for split routing. Change only if you know you need a custom mark.",
        "warn_change": "Wrong values can break VPN routing — note your current mark before changing.",
    },
    {
        "id": "routing",
        "section": "VPN tunnel",
        "label": "Routing",
        "nord_key": "routing",
        "settings_keys": ["Routing"],
        "type": "toggle",
        "explain": "Routes traffic through the VPN tunnel and Meshnet. Turn off for mesh-only or Smart DNS setups with no VPN tunnel.",
        "disconnect_before_off": True,
        "warn_disable": "Turning routing off will disconnect the VPN first, then apply the change.",
    },
    {
        "id": "arp-ignore",
        "section": "VPN tunnel",
        "label": "ARP ignore",
        "nord_key": "arp-ignore",
        "settings_keys": ["ARP Ignore", "ARP ignore"],
        "type": "toggle",
        "explain": "When on, this device ignores LAN ARP while the VPN is up (default). Turn off only if you need LAN discovery through VPN.",
    },
    {
        "id": "meshnet",
        "section": "Meshnet & LAN",
        "label": "Meshnet",
        "nord_key": "meshnet",
        "settings_keys": ["Meshnet"],
        "type": "toggle",
        "explain": "NordVPN Meshnet — link devices and route via peers. Some modes (post-quantum) require Meshnet off.",
        "warn_disable": "Post-quantum VPN cannot stay on if you turn Meshnet off while it was required off already.",
    },
    {
        "id": "lan-discovery",
        "section": "Meshnet & LAN",
        "label": "LAN discovery",
        "nord_key": "lan-discovery",
        "settings_keys": ["LAN Discovery", "LAN discovery"],
        "type": "toggle",
        "explain": "Lets NordVPN discover devices on your local network. Useful at home; often turned off on public WiFi.",
    },
    {
        "id": "nord-dns",
        "section": "DNS",
        "label": "Nord DNS (while VPN connected)",
        "nord_key": "dns",
        "settings_keys": ["DNS"],
        "type": "toggle",
        "dns_mode": True,
        "explain": "Uses Nord’s DNS through the VPN tunnel. On this CLI, nordvpn set dns off means Nord automatic DNS (103.86.x on the tunnel). Separate from Smart DNS on WiFi.",
    },
    {
        "id": "threat-protection",
        "section": "Privacy",
        "label": "Threat Protection Lite",
        "nord_key": "threatprotectionlite",
        "settings_keys": ["Threat Protection Lite", "Threat Protection"],
        "type": "toggle",
        "explain": "Blocks ads and malicious sites at DNS level while connected (Nord’s lite filter).",
    },
    {
        "id": "analytics",
        "section": "Privacy",
        "label": "Analytics",
        "nord_key": "analytics",
        "settings_keys": ["Analytics"],
        "type": "toggle",
        "explain": "NordVPN usage analytics sent to Nord. Most privacy-focused setups keep this off.",
        "default_off": True,
    },
    {
        "id": "user-consent",
        "section": "Privacy",
        "label": "User consent",
        "settings_keys": ["User Consent"],
        "type": "readonly",
        "explain": "NordVPN local-network consent state from nordvpn settings. Not settable on this CLI — use the NordVPN app if you need to change it.",
    },
    {
        "id": "virtual-location",
        "section": "Connection",
        "label": "Virtual locations",
        "nord_key": "virtual-location",
        "settings_keys": ["Virtual Location", "Virtual location"],
        "type": "toggle",
        "explain": "Allows connecting to virtual server locations where Nord provides them.",
    },
    {
        "id": "autoconnect",
        "section": "Connection",
        "label": "Auto-connect",
        "nord_key": "autoconnect",
        "settings_keys": ["Auto-connect", "Auto connect"],
        "type": "toggle",
        "explain": "Connects to VPN automatically when nordvpnd starts. Country comes from your saved connect country.",
        "warn_enable": "VPN may connect on boot without you pressing Connect.",
    },
    {
        "id": "notify",
        "section": "App",
        "label": "Notifications",
        "nord_key": "notify",
        "settings_keys": ["Notify", "Notifications"],
        "type": "toggle",
        "explain": "Desktop notifications from the NordVPN app/daemon.",
    },
    {
        "id": "tray",
        "section": "App",
        "label": "Tray icon",
        "nord_key": "tray",
        "settings_keys": ["Tray"],
        "type": "toggle",
        "explain": "Show NordVPN in the system tray (if supported on your desktop).",
    },
    {
        "id": "technology",
        "section": "Technology",
        "label": "VPN protocol",
        "nord_key": "technology",
        "settings_keys": ["Technology"],
        "type": "choice",
        "choices": [
            {"value": "NORDLYNX", "label": "NordLynx (WireGuard)"},
            {"value": "OPENVPN", "label": "OpenVPN"},
            {"value": "NORDWHISPER", "label": "NordWhisper"},
        ],
        "explain": "Which tunnel protocol Nord uses. Changing this may reconnect you — often to the same country if still connected.",
        "warn_change": "Changing protocol may briefly disconnect and reconnect the VPN.",
    },
    {
        "id": "post-quantum",
        "section": "Technology",
        "label": "Post-quantum encryption",
        "nord_key": "post-quantum",
        "settings_keys": ["Post-quantum VPN", "Post-quantum", "Post-Quantum"],
        "status_keys": ["Post-quantum VPN", "Post-quantum"],
        "type": "toggle",
        "explain": "Extra encryption layer. Requires Meshnet off — nordctl will turn Meshnet off if you enable this.",
        "warn_enable": "Enabling post-quantum turns Meshnet off and may reconnect the VPN.",
        "requires_meshnet_off": True,
    },
    {
        "id": "obfuscate",
        "section": "Technology",
        "label": "Obfuscate",
        "nord_key": "obfuscate",
        "settings_keys": ["Obfuscate"],
        "type": "toggle",
        "explain": "Hides VPN traffic from network sensors that block or throttle VPN protocols. Used with NordWhisper or restrictive networks.",
        "warn_change": "May reconnect the VPN when toggled.",
    },
    {
        "id": "protocol",
        "section": "Technology",
        "label": "OpenVPN protocol",
        "nord_key": "protocol",
        "settings_keys": ["Protocol"],
        "type": "choice",
        "choices": [
            {"value": "UDP", "label": "UDP (faster)"},
            {"value": "TCP", "label": "TCP (more reliable)"},
        ],
        "explain": "TCP or UDP when Technology is OpenVPN. Ignored for NordLynx/NordWhisper.",
        "warn_change": "Changing protocol may briefly disconnect and reconnect the VPN.",
    },
    {
        "id": "restore-defaults",
        "section": "App",
        "label": "Restore Nord defaults",
        "type": "action",
        "virtual": "restore_defaults",
        "action_label": "Restore defaults",
        "explain": "Runs nordvpn set defaults — resets all NordVPN settings to factory values.",
        "warn_change": "Undoes your custom toggles. Use Automate → Snapshots first if you may want to roll back.",
    },
]

SWITCH_BY_ID = {str(s["id"]): s for s in SWITCH_DEFS}

SMART_DNS_WIFI_SWITCH: dict[str, Any] = {
    "id": "smart-dns-wifi",
    "section": "DNS",
    "label": "Smart DNS on WiFi",
    "type": "toggle",
    "virtual": "smart_dns_wifi",
    "affects_local_network": True,
    "explain": (
        "Applies Nord streaming DNS to this computer's saved Wi‑Fi profiles via NetworkManager. "
        "Does not change your router, TV, or phone — only Wi‑Fi connections on this PC."
    ),
    "warn_enable": (
        "Writes DNS into NetworkManager on this computer. "
        "Disconnects VPN first if it is still connected."
    ),
}

SWITCH_BY_ID[str(SMART_DNS_WIFI_SWITCH["id"])] = SMART_DNS_WIFI_SWITCH

SPLIT_TUNNEL_LAN_SWITCH: dict[str, Any] = {
    "id": "split-tunnel-lan",
    "section": "Split tunnel",
    "label": "LAN split tunnel",
    "type": "toggle",
    "virtual": "split_tunnel_lan",
    "explain": "Allowlists your home LAN subnet so local NAS, printers, and servers bypass the VPN tunnel while you stay connected.",
    "warn_enable": "Traffic to the allowlisted LAN goes outside the VPN — use only for trusted local devices.",
    "warn_disable": "Removes the LAN subnet from Nord allowlist (other allowlisted ports stay).",
    "helper_jump": "dashboard/split-tunnel",
    "helper_label": "Edit subnets & ports",
}

SWITCH_BY_ID[str(SPLIT_TUNNEL_LAN_SWITCH["id"])] = SPLIT_TUNNEL_LAN_SWITCH

SERVER_GROUP_SWITCHES: list[dict[str, Any]] = [
    {
        "id": "connect-p2p",
        "section": "Server groups",
        "label": "P2P",
        "type": "connect",
        "virtual": "server_group",
        "connect_group": "P2P",
        "connect_prep": {"meshnet": "on", "lan-discovery": "on", "routing": "on"},
        "explain": "Connect through Nord’s P2P server group — torrenting and file sharing (subscription must include P2P).",
        "warn_enable": "Reconnects the VPN through P2P servers — may change country/server.",
    },
    {
        "id": "connect-double-vpn",
        "section": "Server groups",
        "label": "Double VPN",
        "type": "connect",
        "virtual": "server_group",
        "connect_group": "Double_VPN",
        "connect_prep": {"meshnet": "on", "routing": "on"},
        "explain": "Route through two VPN hops for extra privacy — slower than a normal connection.",
        "warn_enable": "Reconnects the VPN through Double VPN servers.",
    },
    {
        "id": "connect-onion-over-vpn",
        "section": "Server groups",
        "label": "Onion over VPN",
        "type": "connect",
        "virtual": "server_group",
        "connect_group": "Onion_Over_VPN",
        "connect_prep": {"meshnet": "off", "routing": "on"},
        "explain": "VPN first, then Tor — Onion Over VPN specialty servers.",
        "warn_enable": "Turns Meshnet off and reconnects through Onion Over VPN.",
    },
    {
        "id": "connect-dedicated-ip",
        "section": "Server groups",
        "label": "Dedicated IP",
        "type": "connect",
        "virtual": "server_group",
        "connect_group": "Dedicated_IP",
        "connect_prep": {"meshnet": "on", "lan-discovery": "on", "routing": "on"},
        "explain": "Connect to your Nord Dedicated IP add-on server group — same IP each session.",
        "warn_enable": "Reconnects through Dedicated IP servers (requires Nord add-on).",
    },
]

for _sg in SERVER_GROUP_SWITCHES:
    SWITCH_BY_ID[str(_sg["id"])] = _sg

SERVER_GROUP_LABELS: dict[str, str] = {
    "Onion_Over_VPN": "Onion over VPN",
    "Double_VPN": "Double VPN",
    "P2P": "P2P",
    "Dedicated_IP": "Dedicated IP",
}

SERVER_GROUP_HINTS: dict[str, tuple[str, ...]] = {
    "Onion_Over_VPN": ("onion over vpn", "onion_over_vpn", "onion-over-vpn", "onionovervpn"),
    "Double_VPN": ("double vpn", "double_vpn", "double-vpn"),
    "P2P": ("#p2p", " p2p", "p2p "),
    "Dedicated_IP": ("dedicated ip", "dedicated_ip", "dedicated-ip"),
}


def _current_technology(settings: dict[str, Any]) -> str:
    raw = _settings_raw(settings, ["Technology"])
    if not raw:
        return ""
    return raw.upper().split()[0]


def _post_quantum_on(settings: dict[str, Any], status: dict[str, Any]) -> bool:
    raw = _settings_raw(settings, ["Post-quantum VPN", "Post-quantum", "Post-Quantum"])
    if not raw:
        raw = _status_raw(status, ["Post-quantum VPN", "Post-quantum"])
    low = raw.lower()
    return low.startswith("enabled") or low.startswith("on") or low.split()[0:1] == ["on"]


def detect_server_group(status: dict[str, Any], connection: dict[str, Any]) -> str | None:
    """Best-effort specialty server group from nordvpn status (Onion, Double VPN, P2P, …)."""
    hay = " ".join(
        str(v or "")
        for v in (
            status.get("Server"),
            status.get("Hostname"),
            status.get("City"),
            status.get("Country"),
            connection.get("server"),
            connection.get("country"),
        )
    ).lower()
    for group, hints in SERVER_GROUP_HINTS.items():
        if any(h in hay for h in hints):
            return group
    return None


def apply_live_constraints(
    row: dict[str, Any],
    sw: dict[str, Any],
    *,
    settings: dict[str, Any],
    status: dict[str, Any],
    connected: bool,
    connection: dict[str, Any],
    cfg: dict[str, Any] | None = None,
) -> None:
    """Disable or warn on switches that clash with the current live VPN session."""
    sid = str(sw.get("id") or row.get("id") or "")
    tech = _current_technology(settings)
    active_group = detect_server_group(status, connection) if connected else None

    if sid == "protocol":
        if tech and tech != "OPENVPN":
            row["blocked"] = True
            label = tech.replace("_", " ").title()
            row["blocked_reason"] = (
                f"OpenVPN UDP/TCP only applies when Technology is OpenVPN (currently {label})."
            )

    if sid == "smart-dns-wifi" and connected:
        row["requires_vpn_disconnect"] = True
        row["change_warning"] = (
            "VPN is connected — turning on will disconnect first, then apply Smart DNS on WiFi."
        )

    if sid == "nord-dns":
        raw = _settings_raw(settings, list(sw.get("settings_keys") or []))
        nord_on = nv.nord_dns_active(raw)
        custom = [str(x).strip() for x in ((cfg or {}).get("custom_dns") or []) if str(x).strip()]
        if nord_on and not custom:
            row["toggle_blocked_off"] = True
            row["blocked_reason_off"] = (
                "Add custom DNS under My places before turning Nord DNS off — "
                "this Nord CLI only supports automatic Nord DNS (dns off) or explicit server IPs."
            )

    if sid == "meshnet":
        if connected and active_group == "Onion_Over_VPN":
            row["toggle_blocked_on"] = True
            row["blocked_reason"] = "Onion over VPN requires Meshnet off while connected."
        elif _post_quantum_on(settings, status):
            row["toggle_blocked_on"] = True
            row["blocked_reason"] = "Post-quantum VPN requires Meshnet off."

    if sw.get("virtual") == "server_group":
        group = str(sw.get("connect_group") or "")
        if connected and active_group == group:
            row["active"] = True
            row["blocked"] = True
            row["blocked_reason"] = f"Already connected via {sw.get('label') or SERVER_GROUP_LABELS.get(group, group)}."
            cur = dict(row.get("current") or {})
            cur["display"] = f"Active · {connection.get('country') or '—'}"
            row["current"] = cur
        elif connected:
            if active_group:
                cur_label = SERVER_GROUP_LABELS.get(active_group, active_group.replace("_", " "))
                row["connect_warning"] = (
                    f"You are connected via {cur_label} — pressing Connect will switch to {sw.get('label')}."
                )
            else:
                row["connect_warning"] = (
                    f"VPN is connected ({connection.get('country') or 'current server'}) — "
                    f"this will reconnect via {sw.get('label')}."
                )

    if connected and sid in ("technology", "protocol", "obfuscate", "post-quantum"):
        row["change_warning"] = "VPN is connected — changing this may disconnect and reconnect you."


def _enrich_section_rows(
    section_list: list[dict[str, Any]],
    *,
    settings: dict[str, Any],
    status: dict[str, Any],
    connected: bool,
    connection: dict[str, Any],
    cfg: dict[str, Any] | None = None,
) -> None:
    for sec in section_list:
        for row in sec.get("switches") or []:
            sid = str(row.get("id") or "")
            sw = SWITCH_BY_ID.get(sid) or row
            apply_live_constraints(
                row, sw,
                settings=settings,
                status=status,
                connected=connected,
                connection=connection,
                cfg=cfg,
            )


def _settings_raw(settings: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        val = settings.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _status_raw(status: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        val = status.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    return ""


def _parse_toggle(raw: str, *, dns_mode: bool = False, default_off: bool = False) -> dict[str, Any]:
    low = raw.lower()
    if not raw:
        return {"state": "off", "on": False, "display": "Off"}
    if dns_mode:
        return nv.parse_dns_toggle(raw)
    if low.split()[0] in {"enabled", "on", "yes"}:
        return {"state": "on", "on": True, "display": "On"}
    if low.split()[0] in {"disabled", "off", "no"}:
        return {"state": "off", "on": False, "display": "Off"}
    if "enabled" in low:
        return {"state": "on", "on": True, "display": "On"}
    if "disabled" in low:
        return {"state": "off", "on": False, "display": "Off"}
    return {"state": "off", "on": False, "display": "Off"}


def _parse_value(raw: str) -> dict[str, Any]:
    val = str(raw or "").strip()
    if not val:
        return {"state": "unset", "on": None, "display": "Not set", "value": ""}
    return {"state": "set", "on": None, "display": val, "value": val}


def _parse_choice(raw: str, choices: list[dict[str, str]]) -> dict[str, Any]:
    token = raw.upper().split()[0] if raw else ""
    match = next((c for c in choices if c["value"] == token), None)
    label = match["label"] if match else (raw or "Unknown")
    return {"state": token.lower() if token else "unknown", "on": None, "display": label, "value": token}


def _smart_dns_wifi_row(*, smart_active: bool) -> dict[str, Any]:
    row = {
        **{k: SMART_DNS_WIFI_SWITCH[k] for k in (
            "id", "section", "label", "type", "explain", "warn_enable", "virtual",
        ) if k in SMART_DNS_WIFI_SWITCH},
        "current": {
            "state": "on" if smart_active else "off",
            "on": smart_active,
            "display": "On" if smart_active else "Off",
        },
        "choices": [],
    }
    return row


def _server_group_connect_row(
    sw: dict[str, Any],
    *,
    connected: bool,
    connection: dict[str, Any],
) -> dict[str, Any]:
    if connected:
        display = f"VPN on · {connection.get('country') or '—'}"
    else:
        display = "VPN off — press Connect"
    row = {
        **{k: sw[k] for k in (
            "id", "section", "label", "type", "explain", "virtual", "connect_group",
            "warn_enable", "connect_prep",
        ) if k in sw},
        "current": {
            "state": "connected" if connected else "ready",
            "on": None,
            "display": display,
        },
        "choices": [],
    }
    return row


def _action_switch_row(sw: dict[str, Any]) -> dict[str, Any]:
    return {
        **{k: sw[k] for k in (
            "id", "section", "label", "type", "explain", "virtual", "action_label",
            "warn_change",
        ) if k in sw},
        "current": {"state": "ready", "on": None, "display": "Ready"},
        "choices": [],
    }


def _split_tunnel_lan_row(settings: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    subnets = list(settings.get("allowlisted_subnets") or [])
    ports = list(settings.get("allowlisted_ports") or [])
    lan_cidr = str(cfg.get("lan_allowlist_cidr") or "").strip()
    lan_on = bool(lan_cidr and lan_cidr in subnets)
    active = bool(subnets or ports)
    if lan_on:
        display = f"On (LAN {lan_cidr})"
    elif active:
        parts = []
        if subnets:
            parts.append(f"{len(subnets)} subnet{'s' if len(subnets) != 1 else ''}")
        if ports:
            parts.append(f"{len(ports)} port{'s' if len(ports) != 1 else ''}")
        display = f"On — {', '.join(parts)}"
    else:
        display = "Off"
    row = {
        **{k: SPLIT_TUNNEL_LAN_SWITCH[k] for k in (
            "id", "section", "label", "type", "explain", "warn_enable", "warn_disable", "virtual",
            "helper_jump", "helper_label",
        ) if k in SPLIT_TUNNEL_LAN_SWITCH},
        "lan_cidr": lan_cidr,
        "current": {
            "state": "on" if active else "off",
            "on": active,
            "display": display,
        },
        "choices": [],
    }
    return row


def _build_switch_row(sw: dict[str, Any], parsed: dict[str, Any], *, connected: bool) -> dict[str, Any]:
    row = {
        **{k: sw[k] for k in (
            "id", "section", "label", "type", "explain", "nord_key", "virtual", "lan_cidr",
            "warn_enable", "warn_disable", "warn_change", "disconnect_before_off",
            "action_label", "connect_group", "connect_prep", "placeholder",
            "helper_jump", "helper_label",
        ) if k in sw},
        "current": parsed,
        "choices": sw.get("choices") or [],
    }
    if sw.get("disconnect_before_off"):
        row["disconnect_warning_off"] = (
            "Will disconnect VPN first, then turn routing off."
            if connected
            else "No VPN connected — routing will turn off only."
        )
    return row


def _assemble_sections(
    sections: dict[str, list[dict[str, Any]]],
    *,
    settings: dict[str, Any],
    cfg: dict[str, Any],
    smart_active: bool,
    connected: bool = False,
    connection: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    split_row = _split_tunnel_lan_row(settings, cfg)
    smart_row = _smart_dns_wifi_row(smart_active=smart_active)
    sections.setdefault("DNS", [])
    sections["DNS"] = [smart_row] + sections["DNS"]
    conn = connection or {}
    server_rows = [
        _server_group_connect_row(sw, connected=connected, connection=conn)
        for sw in SERVER_GROUP_SWITCHES
    ]
    action_rows = [_action_switch_row(sw) for sw in SWITCH_DEFS if sw.get("type") == "action"]
    app_section = sections.get("App") or []
    sections["App"] = action_rows + app_section
    return [
        {"id": "split-tunnel", "title": "Split tunnel", "switches": [split_row]},
        {"id": "server-groups", "title": "Server groups", "switches": server_rows},
        *[
            {"id": k.lower().replace(" ", "-").replace("&", "and"), "title": k, "switches": v}
            for k, v in sections.items()
        ],
    ]


def _catalog_sections(*, connected: bool = False, smart_active: bool = False) -> list[dict[str, Any]]:
    cfg: dict[str, Any] = {}
    sections: dict[str, list[dict[str, Any]]] = {}
    unknown = {"state": "off", "on": False, "display": "Off"}
    for sw in SWITCH_DEFS:
        if sw.get("type") == "action":
            continue
        parsed = unknown
        if sw.get("type") == "choice":
            parsed = {"state": "unknown", "on": None, "display": "Unknown", "value": ""}
        elif sw.get("type") == "value":
            parsed = {"state": "unset", "on": None, "display": "Unknown", "value": ""}
        elif sw.get("type") == "readonly":
            parsed = {"state": "off", "on": False, "display": "Unknown"}
        sections.setdefault(str(sw["section"]), []).append(
            _build_switch_row(sw, parsed, connected=connected)
        )
    return _assemble_sections(
        sections, settings={}, cfg=cfg, smart_active=smart_active, connected=connected,
    )


def switches_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {
            "ok": True,
            "available": False,
            "message": "Install and log in to NordVPN from Setup to apply switches.",
            "connected": False,
            "connection": {"country": "—", "server": "—", "ip": "—"},
            "sections": _catalog_sections(),
        }

    settings_r = nv.run(bin_path, ["settings"], timeout=10)
    status_r = nv.run(bin_path, ["status"], timeout=8)
    settings = nv.parse_settings(settings_r.get("output", ""))
    status = nv.parse_status(status_r.get("output", ""))
    connected = bool(status.get("connected"))

    sd = cfg.get("smart_dns") or {}
    wifi = cfg.get("wifi") or {}
    from nordctl import network_linux as net

    device = net.detect_wifi_device(wifi.get("device"))
    dns = net.wifi_dns_servers(device) if device else []
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    smart_active = bool(
        primary and secondary and primary in dns and secondary in dns and not connected
    )

    sections: dict[str, list[dict[str, Any]]] = {}
    for sw in SWITCH_DEFS:
        if sw.get("type") == "action":
            continue
        raw = _settings_raw(settings, list(sw.get("settings_keys") or []))
        if not raw and sw.get("status_keys"):
            raw = _status_raw(status, list(sw.get("status_keys") or []))
        if sw.get("type") == "choice":
            parsed = _parse_choice(raw, list(sw.get("choices") or []))
        elif sw.get("type") == "value":
            parsed = _parse_value(raw)
        elif sw.get("type") == "readonly":
            parsed = _parse_toggle(raw, default_off=False)
        else:
            parsed = _parse_toggle(
                raw,
                dns_mode=bool(sw.get("dns_mode")),
                default_off=bool(sw.get("default_off")),
            )
        sections.setdefault(str(sw["section"]), []).append(
            _build_switch_row(sw, parsed, connected=connected)
        )

    connection = {
        "country": status.get("Country") or status.get("country") or "—",
        "server": status.get("Server") or status.get("server") or "—",
        "ip": status.get("IP") or status.get("ip") or "—",
    }
    section_list = _assemble_sections(
        sections,
        settings=settings,
        cfg=cfg,
        smart_active=smart_active,
        connected=connected,
        connection=connection,
    )
    active_group = detect_server_group(status, connection) if connected else None
    _enrich_section_rows(
        section_list,
        settings=settings,
        status=status,
        connected=connected,
        connection=connection,
        cfg=cfg,
    )

    return {
        "ok": True,
        "available": True,
        "connected": connected,
        "connection": connection,
        "active_server_group": active_group,
        "active_server_group_label": SERVER_GROUP_LABELS.get(active_group or "", "") or None,
        "technology": _current_technology(settings) or None,
        "sections": section_list,
        "settings_raw": settings,
    }


def _apply_smart_dns_wifi(value: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl import network_linux as net

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    wifi = cfg.get("wifi") or {}
    profiles = list(wifi.get("profiles") or [])
    device = wifi.get("device")
    steps: list[dict[str, Any]] = []
    if value == "on":
        sd = cfg.get("smart_dns") or {}
        primary = str(sd.get("primary") or "")
        secondary = str(sd.get("secondary") or "")
        if not primary or not secondary:
            return {"ok": False, "error": "Set Smart DNS IPs on the Nord DNS tab first"}
        if not profiles:
            return {
                "ok": False,
                "error": "WiFi profile names are not set yet.",
                "hint": "Open the WiFi tab → Sync profiles, or add your connection name there.",
            }
        status_r = nv.run(bin_path, ["status"], timeout=8)
        connected = bool(nv.parse_status(status_r.get("output", "")).get("connected"))
        if connected:
            steps.append(nv.run(bin_path, ["disconnect"], timeout=20))
        steps.extend(net.apply_smart_dns(profiles, primary, secondary, device))
        ok = all(s.get("ok") for s in steps)
        note = "Smart DNS applied on WiFi profiles"
        if connected:
            note = f"VPN disconnected — {note}"
        return {"ok": ok, "steps": steps, "note": note}
    steps.extend(net.restore_dns(profiles, device))
    ok = all(s.get("ok") for s in steps) if steps else True
    return {"ok": ok, "steps": steps, "note": "Restored automatic DNS on WiFi profiles"}


def _apply_restore_defaults(cfg: dict[str, Any]) -> dict[str, Any]:
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    steps = [nv.run(bin_path, ["set", "defaults"], timeout=45)]
    ok = all(s.get("ok", False) for s in steps)
    return {"ok": ok, "steps": steps, "note": "NordVPN settings restored to defaults"}


def _apply_server_group_connect(sw: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl import network_linux as net

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    group = str(sw.get("connect_group") or "").strip()
    if not group:
        return {"ok": False, "error": "Missing server group"}
    steps: list[dict[str, Any]] = []
    wifi = cfg.get("wifi") or {}
    profiles = list(wifi.get("profiles") or [])
    device = wifi.get("device")
    if profiles:
        steps.extend(net.restore_dns(profiles, device))
    for key, val in (sw.get("connect_prep") or {}).items():
        steps.append(nv.run(bin_path, ["set", str(key), str(val)], timeout=15))
    steps.append(nv.run(bin_path, ["connect", "--group", group], timeout=90))
    ok = all(s.get("ok", False) for s in steps)
    return {
        "ok": ok,
        "steps": steps,
        "note": f"Connected via {sw.get('label') or group} server group",
    }


def _apply_split_tunnel_lan(value: str, cfg: dict[str, Any]) -> dict[str, Any]:
    from nordctl.allowlist_mgr import apply_lan_from_config, remove_lan_from_config

    if value == "on":
        r = apply_lan_from_config(cfg)
        if not r.get("ok"):
            return r
        cidr = str(cfg.get("lan_allowlist_cidr") or "").strip()
        return {**r, "note": f"LAN split tunnel on ({cidr})"}
    return remove_lan_from_config(cfg)


def _finalize_virtual_result(
    result: dict[str, Any],
    *,
    sid: str,
    val: str,
    cfg: dict[str, Any],
) -> dict[str, Any]:
    from nordctl.state import build_state

    steps = result.get("steps") or []
    ok = bool(result.get("ok"))
    error = result.get("error")
    hint = result.get("hint")
    if not ok and not error:
        for step in steps:
            if not step.get("ok"):
                error = step.get("error") or step.get("output") or "Command failed"
                hint = hint or step.get("hint")
                break
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if ok:
        nv.invalidate_cache(bin_path=bin_path)
    out: dict[str, Any] = {
        **result,
        "ok": ok,
        "switch": sid,
        "value": val,
        "steps": steps,
        "state": build_state(cfg),
    }
    if error:
        out["error"] = error
    if hint:
        out["hint"] = hint
    return out


def apply_switch(switch_id: str, value: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {"ok": False, "error": "NordVPN CLI not available"}

    sid = str(switch_id or "").strip()
    sw = SWITCH_BY_ID.get(sid)
    if not sw:
        return {"ok": False, "error": f"Unknown switch: {sid}"}

    val = str(value or "").strip()
    if sw.get("type") == "toggle":
        low = val.lower()
        if low not in {"on", "off"}:
            return {"ok": False, "error": "value must be on or off"}
        val = low
    elif sw.get("type") == "choice":
        allowed = {c["value"] for c in sw.get("choices") or []}
        val = val.upper()
        if val not in allowed:
            return {"ok": False, "error": f"Invalid choice — use one of: {', '.join(sorted(allowed))}"}
    elif sw.get("type") == "connect":
        if val.lower() != "connect":
            return {"ok": False, "error": "value must be connect"}
        val = "connect"
    elif sw.get("type") == "action":
        if val.lower() not in {"run", "connect"}:
            return {"ok": False, "error": "invalid action"}
        val = "run"
    elif sw.get("type") == "readonly":
        return {"ok": False, "error": "Read-only — not settable via this NordVPN CLI"}
    elif sw.get("type") == "value":
        import re

        val = str(value or "").strip()
        if not val:
            return {"ok": False, "error": "Value required (hex e.g. 0xe1f1 or decimal)"}
        if not re.fullmatch(r"0x[0-9a-fA-F]+|\d+", val):
            return {"ok": False, "error": "Use hex (0xe1f1) or a decimal number"}

    virtual = sw.get("virtual")
    if virtual == "smart_dns_wifi":
        return _finalize_virtual_result(_apply_smart_dns_wifi(val, cfg), sid=sid, val=val, cfg=cfg)
    if virtual == "split_tunnel_lan":
        return _finalize_virtual_result(_apply_split_tunnel_lan(val, cfg), sid=sid, val=val, cfg=cfg)
    if virtual == "server_group":
        return _finalize_virtual_result(_apply_server_group_connect(sw, cfg), sid=sid, val=val, cfg=cfg)
    if virtual == "restore_defaults":
        return _finalize_virtual_result(_apply_restore_defaults(cfg), sid=sid, val=val, cfg=cfg)

    steps: list[dict[str, Any]] = []
    status_r = nv.run(bin_path, ["status"], timeout=8)
    connected = bool(nv.parse_status(status_r.get("output", "")).get("connected"))

    if sw.get("disconnect_before_off") and val == "off" and connected:
        steps.append(nv.run(bin_path, ["disconnect"], timeout=20))

    if sw.get("requires_meshnet_off") and val == "on":
        steps.append(nv.run(bin_path, ["set", "meshnet", "off"], timeout=15))

    nord_key = str(sw.get("nord_key") or "")
    if sw.get("type") == "value" and nord_key == "fwmark":
        steps.append(nv.run(bin_path, ["set", "fwmark", val], timeout=15))
        ok = all(s.get("ok", False) for s in steps)
        from nordctl.state import build_state

        return {
            "ok": ok,
            "switch": sid,
            "value": val,
            "steps": steps,
            "note": f"{sw['label']} → {val}",
            "state": build_state(cfg),
        }
    if nord_key == "dns":
        steps.append(nv.apply_dns_preference(bin_path, val == "on", cfg, timeout=15))
    elif nord_key == "protocol":
        steps.append(nv.run(bin_path, ["set", "protocol", val.upper()], timeout=20))
    else:
        steps.append(nv.run(bin_path, ["set", nord_key, val], timeout=20))

    ok = all(s.get("ok", False) for s in steps)
    error = None
    hint = None
    if not ok:
        for step in steps:
            if not step.get("ok"):
                error = step.get("error") or step.get("output") or "Switch command failed"
                hint = step.get("hint")
                break
    note_parts = [f"{sw['label']} → {val}"]
    if sw.get("disconnect_before_off") and val == "off" and connected:
        note_parts.insert(0, "VPN disconnected")
    if sw.get("requires_meshnet_off") and val == "on":
        note_parts.append("Meshnet turned off for post-quantum")

    from nordctl.state import build_state

    if ok:
        nv.invalidate_cache(bin_path=bin_path)
    out: dict[str, Any] = {
        "ok": ok,
        "switch": sid,
        "value": val,
        "steps": steps,
        "note": " — ".join(note_parts),
        "state": build_state(cfg),
    }
    if error:
        out["error"] = error
    if hint:
        out["hint"] = hint
    return out
