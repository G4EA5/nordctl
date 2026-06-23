"""Smart preset builder — structured form → YAML workflow with compatibility rules."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any

import yaml

from nordctl.actions import describe_step
from nordctl.config import load_config
from nordctl.switches_panel import SERVER_GROUP_SWITCHES, SWITCH_DEFS

SERVER_GROUPS = {str(sg["connect_group"]): sg for sg in SERVER_GROUP_SWITCHES}

TOGGLE_FIELDS = [
    "meshnet",
    "lan_discovery",
    "routing",
    "killswitch",
    "firewall",
    "threat_protection",
    "analytics",
    "virtual_location",
    "autoconnect",
    "notify",
    "tray",
    "arp_ignore",
    "post_quantum",
    "obfuscate",
]

TRI_STATE = {"", "on", "off", "default"}

CONNECTION_MODES = [
    {"value": "vpn", "label": "Standard VPN connect"},
    {"value": "smart_dns", "label": "Smart DNS on WiFi (no VPN tunnel)"},
    {"value": "meshnet_only", "label": "Meshnet only (VPN disconnected)"},
    {"value": "disconnect", "label": "Disconnect VPN only"},
    {"value": "settings_only", "label": "Apply settings only (no connect/disconnect)"},
]

TECHNOLOGY_CHOICES = [
    {"value": "", "label": "Leave unchanged"},
    {"value": "NORDLYNX", "label": "NordLynx (WireGuard)"},
    {"value": "OPENVPN", "label": "OpenVPN"},
    {"value": "NORDWHISPER", "label": "NordWhisper"},
]

PROTOCOL_CHOICES = [
    {"value": "", "label": "Leave unchanged"},
    {"value": "UDP", "label": "UDP (faster)"},
    {"value": "TCP", "label": "TCP (more reliable)"},
]

DNS_MODES = [
    {"value": "", "label": "Leave unchanged"},
    {"value": "on", "label": "Nord DNS on"},
    {"value": "off", "label": "Nord DNS off"},
    {"value": "custom", "label": "Custom DNS from My places"},
]

LOCATION_SOURCES = [
    {"value": "none", "label": "Not specified in preset"},
    {"value": "config", "label": "Use My places value"},
    {"value": "inline", "label": "Pick country/city in this preset"},
]

PRESET_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}$", re.I)

EXTRA_STEP_FIELDS = [
    "split_tunnel_lan",
    "split_tunnel_voip",
    "split_tunnel_subnets",
    "smart_dns_wifi",
    "meshnet_peer",
    "restore_defaults",
    "restore_dns_wifi",
]

INCLUDE_OPTIONS = [
    {"value": "", "label": "Don't include"},
    {"value": "yes", "label": "Include in preset"},
]

COMPAT_INTRO = (
    "Only the preset name is required. Leave toggles on Default or extras on Don't include to skip them. "
    "Grey rows are blocked by another choice — read the orange note on that row. "
    "Examples: OpenVPN UDP/TCP only when Technology is OpenVPN; Double VPN and P2P use server groups "
    "instead of country; post-quantum and Onion over VPN turn Meshnet off; Smart DNS mode skips VPN connect."
)

BUILDER_FIELD_HELP: dict[str, str] = {
    "label": "Friendly name shown on your preset cards.",
    "filename": "YAML file name under ~/.config/nordctl/presets/ (lowercase, hyphens).",
    "summary": "One line shown as “What it does” on the preset card — e.g. Stream ITV via Smart DNS on WiFi.",
    "connection_mode": "What the preset does first — normal VPN, Smart DNS without tunnel, Meshnet-only, disconnect, or settings-only.",
    "server_group": "Specialty Nord servers (Double VPN, P2P, …). When set, country/city connect is not used.",
    "country_source": "Where the VPN connects — saved My places country, pick here, or leave unset.",
    "city_source": "Optional city for connect — from My places or pick inline when country is inline.",
    "technology": "Tunnel protocol. Changing this may reconnect you. OpenVPN unlocks the UDP/TCP row below.",
    "protocol": "Only applies when VPN protocol is OpenVPN — ignored for NordLynx and NordWhisper.",
    "fwmark": "Advanced routing mark — leave blank unless you know you need a custom fwmark.",
    "nord_dns": "Nord DNS while VPN is connected. Custom uses DNS IPs saved in My places.",
    "mesh_peer_value": "Hostname of the Meshnet device to route through (from nordvpn meshnet peer list). Use Move to My places on the preset card after saving.",
    "split_tunnel_lan": "Adds your Home LAN subnet to Nord allowlist so local NAS/printers work while VPN is on.",
    "split_tunnel_voip": "Allowlists VoIP ports from config — useful for calls while VPN is connected.",
    "split_tunnel_subnets": "Allowlists extra subnets stored in your nordctl config.",
    "smart_dns_wifi": "Applies Nord streaming DNS to WiFi profiles — no VPN tunnel. Needs Smart DNS IPs on Nord DNS tab.",
    "meshnet_peer": "Runs meshnet peer connect using the peer hostname below (or saved in My places).",
    "restore_defaults": "Resets all NordVPN settings to factory defaults before other steps.",
    "restore_dns_wifi": "Restores automatic DNS on your WiFi profiles at the start — recommended for most VPN presets.",
}


def _switch_id_for_field(fid: str) -> str:
    return {
        "lan_discovery": "lan-discovery",
        "threat_protection": "threat-protection",
        "virtual_location": "virtual-location",
        "arp_ignore": "arp-ignore",
        "post_quantum": "post-quantum",
    }.get(fid, fid.replace("_", "-"))


def _switch_meta(fid: str) -> dict[str, Any]:
    sid = _switch_id_for_field(fid)
    return next((s for s in SWITCH_DEFS if s.get("id") == sid), {})


def _slugify(name: str) -> str:
    raw = re.sub(r"[^a-z0-9_-]+", "-", (name or "").strip().lower())
    raw = re.sub(r"-+", "-", raw).strip("-")
    if not raw:
        raw = "my-preset"
    if not PRESET_NAME_RE.match(raw):
        raw = f"p-{raw[:46]}".strip("-")
    return raw[:49]


def default_spec() -> dict[str, Any]:
    return {
        "label": "",
        "filename": "",
        "summary": "",
        "category": "Custom",
        "connection_mode": "vpn",
        "server_group": "",
        "country_source": "config",
        "country": "",
        "city_source": "none",
        "city": "",
        "technology": "",
        "protocol": "",
        "meshnet": "on",
        "lan_discovery": "on",
        "routing": "on",
        "killswitch": "",
        "firewall": "",
        "fwmark": "",
        "nord_dns": "",
        "threat_protection": "",
        "analytics": "off",
        "virtual_location": "",
        "autoconnect": "",
        "notify": "",
        "tray": "",
        "arp_ignore": "",
        "post_quantum": "",
        "obfuscate": "",
        "split_tunnel_lan": False,
        "split_tunnel_voip": False,
        "split_tunnel_subnets": False,
        "smart_dns_wifi": False,
        "restore_dns_wifi": True,
        "meshnet_peer": False,
        "mesh_peer_value": "",
        "restore_defaults": False,
    }


def normalize_spec(raw: dict[str, Any] | None) -> dict[str, Any]:
    spec = default_spec()
    if not isinstance(raw, dict):
        return spec
    for key in spec:
        if key not in raw:
            continue
        val = raw[key]
        if isinstance(spec[key], bool):
            spec[key] = bool(val)
        elif key in TOGGLE_FIELDS or key in {"technology", "protocol", "nord_dns", "server_group"}:
            spec[key] = str(val or "").strip().lower() if key != "technology" and key != "protocol" and key != "server_group" else str(val or "").strip()
            if key in TOGGLE_FIELDS and spec[key] not in TRI_STATE:
                spec[key] = ""
            if key == "technology":
                spec[key] = spec[key].upper()
            if key == "protocol":
                spec[key] = spec[key].upper()
        else:
            spec[key] = str(val or "").strip()
    if spec["connection_mode"] not in {m["value"] for m in CONNECTION_MODES}:
        spec["connection_mode"] = "vpn"
    if spec["country_source"] not in {"none", "config", "inline"}:
        spec["country_source"] = "config"
    if spec["city_source"] not in {"none", "config", "inline"}:
        spec["city_source"] = "none"
    if not spec["filename"] and spec["label"]:
        spec["filename"] = _slugify(spec["label"])
    return spec


def _effective(spec: dict[str, Any]) -> dict[str, Any]:
    """Apply forced values from compatibility rules."""
    eff = dict(spec)
    group = str(eff.get("server_group") or "").strip()
    mode = str(eff.get("connection_mode") or "vpn")

    if eff.get("post_quantum") == "on":
        eff["meshnet"] = "off"

    if group == "Onion_Over_VPN":
        eff["meshnet"] = "off"

    if mode == "smart_dns":
        eff["smart_dns_wifi"] = True
        eff["connection_mode"] = "smart_dns"
        if eff.get("routing") in {"", "default"}:
            eff["routing"] = "on"
        if eff.get("autoconnect") in {"", "default"}:
            eff["autoconnect"] = "off"

    if mode == "meshnet_only":
        eff["connection_mode"] = "meshnet_only"
        if eff.get("routing") in {"", "default"}:
            eff["routing"] = "on"
        if eff.get("autoconnect") in {"", "default"}:
            eff["autoconnect"] = "off"

    if group:
        eff["country_source"] = "none"
        eff["city_source"] = "none"

    if mode in {"disconnect", "settings_only", "smart_dns", "meshnet_only"}:
        eff["server_group"] = ""

    if eff.get("technology") and eff["technology"] != "OPENVPN":
        eff["protocol"] = ""

    if mode == "smart_dns":
        eff["server_group"] = ""

    return eff


def evaluate_compatibility(spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    eff = _effective(spec)
    fields: dict[str, dict[str, Any]] = {}
    warnings: list[str] = []
    requires: list[str] = []

    mode = eff["connection_mode"]
    group = eff.get("server_group") or ""
    tech = eff.get("technology") or ""

    def set_field(fid: str, *, state: str = "enabled", reason: str = "", forced: str | None = None) -> None:
        entry: dict[str, Any] = {"state": state}
        if reason:
            entry["reason"] = reason
        if forced is not None:
            entry["forced"] = forced
        fields[fid] = entry

    for fid in TOGGLE_FIELDS:
        set_field(fid)

    set_field("technology")
    set_field("protocol")
    set_field("nord_dns")
    set_field("fwmark")
    set_field("server_group")
    set_field("country_source")
    set_field("city_source")
    set_field("country")
    set_field("city")
    set_field("split_tunnel_lan")
    set_field("split_tunnel_voip")
    set_field("split_tunnel_subnets")
    set_field("smart_dns_wifi")
    set_field("meshnet_peer")
    set_field("mesh_peer_value")
    set_field("restore_defaults")
    set_field("restore_dns_wifi")

    if tech and tech != "OPENVPN":
        set_field("protocol", state="disabled", reason="OpenVPN protocol (UDP/TCP) applies only when Technology is OpenVPN")

    if mode == "smart_dns":
        set_field("server_group", state="disabled", reason="Smart DNS mode does not use specialty server groups")
        set_field("smart_dns_wifi", state="forced", forced="on", reason="Smart DNS on WiFi is required for this mode")
        warnings.append("Smart DNS applies streaming DNS on WiFi — no VPN tunnel. Set Smart DNS IPs on Nord DNS first.")
        if not list((cfg.get("wifi") or {}).get("profiles") or []):
            warnings.append("No WiFi profiles in config — add them on WiFi → Profiles before running this preset.")

    if mode == "meshnet_only":
        set_field("server_group", state="disabled", reason="Meshnet-only mode keeps VPN disconnected")
        warnings.append("Meshnet only — preset disconnects VPN and keeps Meshnet/LAN discovery on.")

    if mode == "disconnect":
        for fid in TOGGLE_FIELDS + ["technology", "protocol", "nord_dns", "server_group"]:
            if fid not in {"notify", "tray"}:
                set_field(fid, state="disabled", reason="Disconnect-only preset runs nordvpn disconnect")
        set_field("country_source", state="disabled", reason="No connect step")
        set_field("city_source", state="disabled", reason="No connect step")
        set_field("split_tunnel_lan", state="disabled", reason="No VPN connect in this mode")

    if mode == "settings_only":
        set_field("server_group", state="disabled", reason="Settings-only preset does not connect")
        set_field("country_source", state="disabled", reason="No connect step")
        set_field("city_source", state="disabled", reason="No connect step")

    if group:
        set_field("country_source", state="disabled", reason=f"Connect uses server group {group.replace('_', ' ')}")
        set_field("city_source", state="disabled", reason="Country/city not used with server groups")
        set_field("country", state="disabled", reason="Server group connect")
        set_field("city", state="disabled", reason="Server group connect")
        prep = (SERVER_GROUPS.get(group) or {}).get("connect_prep") or {}
        if prep.get("meshnet") == "off":
            set_field("meshnet", state="forced", forced="off", reason=f"{group.replace('_', ' ')} requires Meshnet off")

    if eff.get("post_quantum") == "on":
        set_field("meshnet", state="forced", forced="off", reason="Post-quantum encryption requires Meshnet off")

    if eff.get("routing") == "off" and mode == "vpn":
        warnings.append("Routing off stops VPN/Meshnet traffic routing — connect step may not give a working VPN.")

    if eff.get("obfuscate") == "on" and tech == "NORDLYNX":
        warnings.append("Obfuscate is mainly used with NordWhisper or restrictive networks — NordLynx may ignore it.")

    if spec.get("country_source") == "config" and mode == "vpn" and not group:
        requires.append("connect_country")
    if spec.get("city_source") == "config" and mode == "vpn" and not group:
        requires.append("connect_city")
    if spec.get("country_source") == "inline" and not spec.get("country") and mode == "vpn" and not group:
        warnings.append("Pick a country or switch to “Use My places value”.")
    if spec.get("city_source") == "inline" and not spec.get("city") and mode == "vpn" and not group:
        warnings.append("Pick a city or leave city unset.")

    if spec.get("split_tunnel_lan"):
        requires.append("lan_allowlist_cidr")
    if spec.get("nord_dns") == "custom":
        requires.append("custom_dns")
    if spec.get("meshnet_peer"):
        peer_val = str(spec.get("mesh_peer_value") or cfg.get("mesh_peer") or "").strip()
        if not peer_val:
            warnings.append("Enter the Meshnet peer hostname — run nordvpn meshnet peer list or check Nord Dashboard → Meshnet.")
            set_field("mesh_peer_value", state="enabled", reason="Required when Meshnet peer connect is included")
        elif not cfg.get("mesh_peer") and not spec.get("mesh_peer_value"):
            requires.append("mesh_peer")

    if spec.get("smart_dns_wifi") and mode != "smart_dns":
        sd = cfg.get("smart_dns") or {}
        if not sd.get("primary") or not sd.get("secondary"):
            warnings.append("Set Smart DNS IPs on Nord DNS before enabling Smart DNS on WiFi.")

    # dedupe requires preserving order
    seen: set[str] = set()
    requires = [r for r in requires if not (r in seen or seen.add(r))]

    return {
        "ok": True,
        "spec": spec,
        "effective": eff,
        "fields": fields,
        "warnings": warnings,
        "requires": requires,
    }


def _connect_target(spec: dict[str, Any]) -> tuple[str, str]:
    """Return (target, group) for nordvpn_connect."""
    group = str(spec.get("server_group") or "").strip()
    if group:
        return "", group

    country_src = spec.get("country_source") or "config"
    city_src = spec.get("city_source") or "none"

    if city_src == "inline" and spec.get("city") and spec.get("country"):
        country = str(spec["country"]).replace("_", " ")
        city = str(spec["city"]).replace("_", " ")
        return f"{country} {city}", ""
    if city_src == "config":
        return "{connect_city}", ""
    if country_src == "inline" and spec.get("country"):
        return str(spec["country"]).replace("_", " "), ""
    if country_src == "config":
        return "{connect_country}", ""
    return "", ""


def _append_set(steps: list[dict[str, Any]], key: str, value: str, *, extra: str = "") -> None:
    if not key or not value:
        return
    step: dict[str, Any] = {"action": "nordvpn_set", "key": key, "value": value}
    if extra:
        step["extra"] = extra
    steps.append(step)


def build_preset_document(spec: dict[str, Any], meta: dict[str, Any] | None = None) -> dict[str, Any]:
    meta = meta or {}
    source_spec = normalize_spec(spec)
    spec = _effective(source_spec)
    eval_result = evaluate_compatibility(spec)
    steps: list[dict[str, Any]] = []

    if spec.get("restore_dns_wifi"):
        steps.append({"action": "network_restore_dns"})

    if spec.get("restore_defaults"):
        steps.append({"action": "nordvpn_set", "key": "defaults", "value": ""})

    mode = spec["connection_mode"]

    if mode in {"smart_dns", "meshnet_only", "disconnect"}:
        steps.append({"action": "nordvpn_disconnect"})

    batch: dict[str, str] = {}
    for fid in TOGGLE_FIELDS:
        val = str(spec.get(fid) or "").strip().lower()
        if not val or val == "default":
            continue
        nord_key = fid.replace("_", "-")
        if fid == "post_quantum":
            nord_key = "post-quantum"
        elif fid == "lan_discovery":
            nord_key = "lan-discovery"
        elif fid == "threat_protection":
            nord_key = "threatprotectionlite"
        elif fid == "virtual_location":
            nord_key = "virtual-location"
        elif fid == "arp_ignore":
            nord_key = "arp-ignore"
        batch[nord_key] = val

    if spec.get("technology"):
        _append_set(steps, "technology", spec["technology"])
    if spec.get("protocol"):
        _append_set(steps, "protocol", spec["protocol"])

    dns_mode = spec.get("nord_dns") or ""
    if dns_mode == "on":
        _append_set(steps, "dns", "off")
    elif dns_mode in {"off", "custom"}:
        _append_set(steps, "dns", "{custom_dns}")

    fwmark = str(spec.get("fwmark") or "").strip()
    if fwmark:
        _append_set(steps, "fwmark", fwmark)

    if batch:
        if len(batch) == 1 and not spec.get("technology") and not spec.get("protocol") and not dns_mode:
            k, v = next(iter(batch.items()))
            _append_set(steps, k, v)
        else:
            steps.append({"action": "nordvpn_settings", "settings": batch})

    if spec.get("split_tunnel_subnets"):
        steps.append({"action": "allowlist_subnets_from_config"})
    if spec.get("split_tunnel_lan"):
        steps.append({"action": "allowlist_subnet", "cidr": "{lan_allowlist_cidr}"})
    if spec.get("split_tunnel_voip"):
        steps.append({"action": "allowlist_voip_ports"})

    if spec.get("smart_dns_wifi") or mode == "smart_dns":
        steps.append({"action": "network_smart_dns"})

    if spec.get("meshnet_peer"):
        steps.append({"action": "meshnet_peer_connect"})

    if mode == "vpn":
        target, group = _connect_target(spec)
        if target or group:
            connect: dict[str, Any] = {"action": "nordvpn_connect"}
            if group:
                connect["group"] = group
            elif target:
                connect["target"] = target
            steps.append(connect)
            ac = str(spec.get("autoconnect") or "").strip().lower()
            if ac == "on":
                extra = ""
                if target in {"{connect_country}", "{connect_city}"}:
                    extra = target.replace("{", "").replace("}", "")
                    if extra == "connect_city" and spec.get("country_source") == "config":
                        extra = "{connect_country}"
                elif target and not group:
                    extra = target
                _append_set(steps, "autoconnect", "on", extra=extra or "{connect_country}")

    slug = _slugify(meta.get("filename") or spec.get("filename") or spec.get("label") or "my-preset")
    label = str(meta.get("label") or spec.get("label") or slug.replace("-", " ").title()).strip()
    summary = str(meta.get("summary") or spec.get("summary") or f"Custom workflow: {label}").strip()
    category = str(meta.get("category") or spec.get("category") or "Custom").strip()

    doc: dict[str, Any] = {
        "id": slug.replace("-", "_"),
        "label": label,
        "summary": summary,
        "category": category,
        "steps": steps,
    }
    req = eval_result.get("requires") or []
    if req:
        doc["requires"] = req
    stored = compact_builder_spec(source_spec)
    if stored:
        doc["builder_spec"] = stored
    return doc


def compact_builder_spec(spec: dict[str, Any]) -> dict[str, Any]:
    """Store only builder fields that differ from defaults (for edit + My places export)."""
    base = default_spec()
    out: dict[str, Any] = {}
    for key in base:
        val = spec.get(key)
        if val != base.get(key):
            out[key] = val
    return out


def spec_from_preset_document(doc: dict[str, Any]) -> dict[str, Any]:
    raw = doc.get("builder_spec")
    if isinstance(raw, dict) and raw:
        merged = default_spec()
        merged.update(raw)
        return normalize_spec(merged)
    return _infer_spec_from_document(doc)


def _infer_spec_from_document(doc: dict[str, Any]) -> dict[str, Any]:
    spec = default_spec()
    spec["label"] = str(doc.get("label") or "")
    spec["summary"] = str(doc.get("summary") or "")
    spec["category"] = str(doc.get("category") or "Custom")
    pid = str(doc.get("id") or "").strip()
    if pid:
        spec["filename"] = _slugify(pid)
    for step in doc.get("steps") or []:
        if not isinstance(step, dict):
            continue
        action = str(step.get("action") or "")
        if action == "nordvpn_connect":
            group = str(step.get("group") or "").strip()
            if group:
                spec["server_group"] = group
                continue
            target = str(step.get("target") or "").strip()
            if target == "{connect_country}":
                spec["country_source"] = "config"
            elif target == "{connect_city}":
                spec["city_source"] = "config"
            elif target:
                if " " in target:
                    country, city = target.rsplit(" ", 1)
                    spec["country_source"] = "inline"
                    spec["country"] = country.replace(" ", "_")
                    spec["city_source"] = "inline"
                    spec["city"] = city.replace(" ", "_")
                else:
                    spec["country_source"] = "inline"
                    spec["country"] = target.replace(" ", "_")
        elif action == "meshnet_peer_connect":
            spec["meshnet_peer"] = True
            peer = str(step.get("peer") or "").strip()
            if peer and not peer.startswith("{"):
                spec["mesh_peer_value"] = peer
    return normalize_spec(spec)


def _place_field_label(field_id: str) -> str:
    from nordctl.config_fields import FIELD_CATALOG

    return str((FIELD_CATALOG.get(field_id) or {}).get("label") or field_id.replace("_", " ").title())


def places_pending_from_spec(spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Values in the builder spec that can be copied into My places (not already saved)."""
    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    pending: list[dict[str, str]] = []

    def add(field_id: str, value: str) -> None:
        val = str(value or "").strip()
        if not val:
            return
        cur = str(cfg.get(field_id) or "").strip()
        if val.lower() == cur.lower():
            return
        pending.append({"field": field_id, "value": val, "label": _place_field_label(field_id)})

    if spec.get("country_source") == "inline" and spec.get("country"):
        add("connect_country", str(spec["country"]).replace("_", " "))
    if spec.get("city_source") == "inline" and spec.get("city"):
        add("connect_city", str(spec["city"]).replace("_", " "))
    if spec.get("meshnet_peer") and spec.get("mesh_peer_value"):
        add("mesh_peer", str(spec["mesh_peer_value"]))
    return pending


def apply_spec_to_places(spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config_fields import set_config_field

    cfg = cfg or load_config()
    pending = places_pending_from_spec(spec, cfg)
    if not pending:
        return {"ok": False, "error": "Nothing to copy — values are already in My places or the preset uses My places fields."}
    saved: list[dict[str, str]] = []
    for row in pending:
        result = set_config_field(cfg, row["field"], row["value"])
        if not result.get("ok"):
            return result
        saved.append(row)
        cfg = load_config()
    return {"ok": True, "saved": saved, "note": f"Copied {len(saved)} value(s) to My places."}


def build_breakdown(doc: dict[str, Any], spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    eval_result = evaluate_compatibility(spec, cfg)

    switch_rows: list[dict[str, Any]] = []

    def row(section: str, label: str, value: str, *, note: str = "") -> None:
        switch_rows.append({"section": section, "label": label, "value": value, "note": note})

    row("Basics", "Name", str(doc.get("label") or "—"))
    row("Basics", "File", f"{_slugify(doc.get('id') or 'preset')}.yaml")
    row("Basics", "Summary", str(doc.get("summary") or "—"))
    row("Basics", "Category", str(doc.get("category") or "Custom"))

    mode_labels = {m["value"]: m["label"] for m in CONNECTION_MODES}
    row("Connection", "Mode", mode_labels.get(spec["connection_mode"], spec["connection_mode"]))

    if spec.get("server_group"):
        sg = SERVER_GROUPS.get(spec["server_group"]) or {}
        row("Connection", "Server group", sg.get("label") or spec["server_group"])

    if spec["connection_mode"] == "vpn" and not spec.get("server_group"):
        if spec.get("country_source") == "config":
            row("Connection", "Country", cfg.get("connect_country") or "(set in My places)")
        elif spec.get("country_source") == "inline":
            row("Connection", "Country", spec.get("country") or "—")
        if spec.get("city_source") == "config":
            row("Connection", "City", cfg.get("connect_city") or "(optional in My places)")
        elif spec.get("city_source") == "inline" and spec.get("city"):
            row("Connection", "City", spec.get("city"))

    if spec.get("technology"):
        tech = next((c["label"] for c in TECHNOLOGY_CHOICES if c["value"] == spec["technology"]), spec["technology"])
        row("Technology", "VPN protocol", tech)
    if spec.get("protocol"):
        row("Technology", "OpenVPN protocol", spec["protocol"])

    switch_meta = {s["id"]: s for s in SWITCH_DEFS if s.get("id")}
    _fid_to_switch = {
        "lan_discovery": "lan-discovery",
        "threat_protection": "threat-protection",
        "virtual_location": "virtual-location",
        "arp_ignore": "arp-ignore",
        "post_quantum": "post-quantum",
    }
    for fid in TOGGLE_FIELDS:
        val = str(spec.get(fid) or "").strip().lower()
        if not val or val == "default":
            continue
        sw_id = _fid_to_switch.get(fid, fid.replace("_", "-"))
        meta_sw = switch_meta.get(sw_id) or {}
        display = val.capitalize()
        forced = (eval_result.get("fields") or {}).get(fid, {}).get("forced")
        note = " (auto)" if forced and forced == val else ""
        row(str(meta_sw.get("section") or "Settings"), str(meta_sw.get("label") or fid), display, note=note)

    if spec.get("nord_dns"):
        dns_labels = {"on": "On", "off": "Off", "custom": "Custom from My places"}
        row("DNS", "Nord DNS", dns_labels.get(spec["nord_dns"], spec["nord_dns"]))
    if spec.get("smart_dns_wifi") or spec["connection_mode"] == "smart_dns":
        row("DNS", "Smart DNS on WiFi", "On")
    if spec.get("split_tunnel_lan"):
        row("Split tunnel", "LAN allowlist", cfg.get("lan_allowlist_cidr") or "{lan_allowlist_cidr}")
    if spec.get("split_tunnel_voip"):
        row("Split tunnel", "VoIP ports", "From config")
    if spec.get("split_tunnel_subnets"):
        row("Split tunnel", "Extra subnets", "From config allowlist")
    if spec.get("meshnet_peer"):
        peer = str(spec.get("mesh_peer_value") or cfg.get("mesh_peer") or "{mesh_peer}")
        row("Meshnet", "Peer connect", peer)
    if spec.get("restore_defaults"):
        row("App", "Restore Nord defaults", "Yes")

    preview_steps = []
    for i, step in enumerate(doc.get("steps") or [], start=1):
        if isinstance(step, dict):
            preview_steps.append({"n": i, "text": describe_step(step, cfg)})

    return {
        "switches": switch_rows,
        "steps": preview_steps,
        "requires": doc.get("requires") or [],
        "warnings": eval_result.get("warnings") or [],
    }


def _field_help_entries() -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for key, text in BUILDER_FIELD_HELP.items():
        entries.append({"id": key, "help": text})
    for fid in TOGGLE_FIELDS:
        sw = _switch_meta(fid)
        if sw.get("explain"):
            entries.append({"id": fid, "help": str(sw["explain"])})
    for mode in CONNECTION_MODES:
        entries.append({"id": f"connection_mode_{mode['value']}", "help": mode["label"]})
    for sg in SERVER_GROUP_SWITCHES:
        entries.append({"id": f"server_group_{sg['connect_group']}", "help": str(sg.get("explain") or sg.get("label") or "")})
    return entries


def builder_schema(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    return {
        "ok": True,
        "compat_intro": COMPAT_INTRO,
        "defaults": default_spec(),
        "include_options": INCLUDE_OPTIONS,
        "connection_modes": CONNECTION_MODES,
        "technologies": TECHNOLOGY_CHOICES,
        "protocols": PROTOCOL_CHOICES,
        "dns_modes": DNS_MODES,
        "location_sources": LOCATION_SOURCES,
        "server_groups": [
            {"value": "", "label": "None (normal country/city connect)"},
            *[
                {"value": sg["connect_group"], "label": sg["label"], "prep": sg.get("connect_prep") or {}}
                for sg in SERVER_GROUP_SWITCHES
            ],
        ],
        "toggles": [
            {
                "id": fid,
                "label": str(_switch_meta(fid).get("label") or fid.replace("_", " ").title()),
                "section": str(_switch_meta(fid).get("section") or "Settings"),
                "help": str(_switch_meta(fid).get("explain") or BUILDER_FIELD_HELP.get(fid, "")),
            }
            for fid in TOGGLE_FIELDS
        ],
        "extras": [
            {
                "id": fid,
                "label": {
                    "split_tunnel_lan": "LAN split tunnel",
                    "split_tunnel_voip": "VoIP port allowlist",
                    "split_tunnel_subnets": "Extra subnet allowlist",
                    "smart_dns_wifi": "Smart DNS on WiFi",
                    "meshnet_peer": "Meshnet peer connect",
                    "restore_defaults": "Restore Nord defaults first",
                    "restore_dns_wifi": "Restore WiFi DNS at start",
                }.get(fid, fid.replace("_", " ").title()),
                "help": BUILDER_FIELD_HELP.get(fid, ""),
            }
            for fid in EXTRA_STEP_FIELDS
        ],
        "field_help": BUILDER_FIELD_HELP,
        "config_hints": {
            "connect_country": cfg.get("connect_country") or "",
            "connect_city": cfg.get("connect_city") or "",
            "lan_allowlist_cidr": cfg.get("lan_allowlist_cidr") or "",
            "mesh_peer": cfg.get("mesh_peer") or "",
            "wifi_profiles": list((cfg.get("wifi") or {}).get("profiles") or []),
        },
    }


_SWITCH_ID_TO_SPEC_FIELD = {
    "killswitch": "killswitch",
    "firewall": "firewall",
    "routing": "routing",
    "meshnet": "meshnet",
    "lan-discovery": "lan_discovery",
    "threat-protection": "threat_protection",
    "analytics": "analytics",
    "virtual-location": "virtual_location",
    "autoconnect": "autoconnect",
    "notify": "notify",
    "tray": "tray",
    "arp-ignore": "arp_ignore",
    "post-quantum": "post_quantum",
    "obfuscate": "obfuscate",
}


def _tri_state_from_toggle(parsed: dict[str, Any]) -> str:
    if parsed.get("on") is True:
        return "on"
    if parsed.get("state") in {"off", "disabled"} or parsed.get("on") is False:
        return "off"
    return ""


def _capture_toggle_value(
    settings: dict[str, Any],
    status: dict[str, Any],
    sw: dict[str, Any],
) -> str:
    from nordctl.switches_panel import _parse_toggle, _settings_raw, _status_raw

    keys = list(sw.get("settings_keys") or [])
    raw = _settings_raw(settings, keys)
    if not raw and sw.get("status_keys"):
        raw = _status_raw(status, list(sw.get("status_keys") or []))
    if not raw:
        return ""
    parsed = _parse_toggle(raw, dns_mode=bool(sw.get("dns_mode")), default_off=bool(sw.get("default_off")))
    return _tri_state_from_toggle(parsed)


def capture_from_current(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Read live nordvpn settings/status and build a preset-builder spec."""
    from nordctl import network_linux as net
    from nordctl import nordvpn as nv
    from nordctl.allowlist_mgr import describe_port_entry
    from nordctl.switches_panel import (
        SWITCH_DEFS,
        _current_technology,
        _parse_choice,
        _parse_toggle,
        _settings_raw,
        detect_server_group,
    )

    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {
            "ok": False,
            "available": False,
            "error": "Install and log in to NordVPN from Setup to capture live settings.",
            "message": "Install NordVPN from Setup to read live settings.",
        }

    settings_r = nv.run(bin_path, ["settings"], timeout=10)
    status_r = nv.run(bin_path, ["status"], timeout=8)
    settings_out = str(settings_r.get("output") or "").strip()
    if not settings_out and not settings_r.get("ok"):
        return {
            "ok": False,
            "available": False,
            "error": settings_r.get("output") or "Could not run nordvpn settings",
        }

    settings = nv.parse_settings(settings_out)
    status = nv.parse_status(status_r.get("output", ""))
    connected = bool(status.get("connected"))

    sd = cfg.get("smart_dns") or {}
    wifi = cfg.get("wifi") or {}
    device = net.detect_wifi_device(wifi.get("device"))
    dns = net.wifi_dns_servers(device) if device else []
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    smart_active = bool(
        primary and secondary and primary in dns and secondary in dns and not connected
    )

    spec = default_spec()
    spec["label"] = "Current setup"
    spec["summary"] = "Captured from live NordVPN settings on this machine."
    spec["restore_dns_wifi"] = False

    summary_lines: list[str] = []
    connection = {
        "country": str(status.get("Country") or status.get("country") or "—"),
        "server": str(status.get("Server") or status.get("server") or "—"),
        "ip": str(status.get("IP") or status.get("ip") or "—"),
    }

    if smart_active:
        spec["connection_mode"] = "smart_dns"
        spec["smart_dns_wifi"] = True
        summary_lines.append("Mode: Smart DNS on WiFi (no VPN tunnel)")
    elif connected:
        spec["connection_mode"] = "vpn"
        country = str(status.get("Country") or status.get("country") or "").strip()
        city = str(status.get("City") or status.get("city") or "").strip()
        server = connection["server"]
        ip = connection["ip"]
        active_group = detect_server_group(status, connection)
        if active_group:
            spec["server_group"] = active_group
            sg = SERVER_GROUPS.get(active_group) or {}
            summary_lines.append(f"VPN: {sg.get('label') or active_group.replace('_', ' ')}")
            if ip and ip != "—":
                summary_lines.append(f"IP: {ip}")
        else:
            if country:
                spec["country_source"] = "inline"
                spec["country"] = country.replace(" ", "_")
            if city:
                spec["city_source"] = "inline"
                spec["city"] = city.replace(" ", "_")
            loc = " · ".join(x for x in (country, city, server) if x and x != "—")
            summary_lines.append(f"VPN: {loc or server}")
            if ip and ip != "—":
                summary_lines.append(f"IP: {ip}")
    else:
        spec["connection_mode"] = "settings_only"
        summary_lines.append("VPN: disconnected — preset applies switches only")

    for sw in SWITCH_DEFS:
        sid = str(sw.get("id") or "")
        if sw.get("type") in {"action", "readonly"}:
            continue
        field = _SWITCH_ID_TO_SPEC_FIELD.get(sid)
        if not field:
            continue
        if sw.get("type") == "choice":
            raw = _settings_raw(settings, list(sw.get("settings_keys") or []))
            if not raw:
                continue
            parsed = _parse_choice(raw, list(sw.get("choices") or []))
            val = str(parsed.get("value") or "").strip()
            if val:
                spec[field if field != "protocol" else "protocol"] = val
            continue
        if sw.get("type") == "value":
            raw = _settings_raw(settings, list(sw.get("settings_keys") or []))
            if raw and field == "fwmark":
                spec["fwmark"] = raw.split()[0]
            continue
        val = _capture_toggle_value(settings, status, sw)
        if val:
            spec[field] = val

    raw_dns = _settings_raw(settings, ["DNS"])
    if raw_dns:
        dns_parsed = _parse_toggle(raw_dns, dns_mode=True)
        if dns_parsed.get("state") == "custom":
            spec["nord_dns"] = "custom"
        elif dns_parsed.get("on"):
            spec["nord_dns"] = "on"
        else:
            spec["nord_dns"] = "off"

    allow_ports = list(settings.get("allowlisted_ports") or [])
    allow_subnets = list(settings.get("allowlisted_subnets") or [])
    lan_cidr = str(cfg.get("lan_allowlist_cidr") or "").strip()
    if lan_cidr and any(lan_cidr == s or lan_cidr in s for s in allow_subnets):
        spec["split_tunnel_lan"] = True
    voip_ports = list(cfg.get("voip_ports") or [])
    if allow_ports and voip_ports and any(
        describe_port_entry(line, voip_ports).get("from_voip_config") for line in allow_ports
    ):
        spec["split_tunnel_voip"] = True
    config_subnets = list(cfg.get("allowlist_subnets") or [])
    if config_subnets and any(s in allow_subnets for s in config_subnets):
        spec["split_tunnel_subnets"] = True

    tech = _current_technology(settings)
    if tech:
        spec["technology"] = tech
        summary_lines.append(f"Technology: {tech.replace('_', ' ').title()}")
    proto_raw = _settings_raw(settings, ["Protocol"])
    if proto_raw and tech == "OPENVPN":
        proto = _parse_choice(proto_raw, [{"value": "UDP", "label": "UDP"}, {"value": "TCP", "label": "TCP"}])
        if proto.get("value"):
            spec["protocol"] = str(proto["value"])
            summary_lines.append(f"OpenVPN: {proto['value']}")

    toggle_labels = {
        "killswitch": "Kill switch",
        "firewall": "Nord firewall",
        "meshnet": "Meshnet",
        "routing": "Routing",
        "lan_discovery": "LAN discovery",
        "threat_protection": "Threat Protection",
        "autoconnect": "Auto-connect",
    }
    for fid, label in toggle_labels.items():
        val = str(spec.get(fid) or "").strip().lower()
        if val in {"on", "off"}:
            summary_lines.append(f"{label}: {val.capitalize()}")

    if allow_ports:
        summary_lines.append(f"Allowlisted ports: {len(allow_ports)}")
    if allow_subnets:
        summary_lines.append(f"Allowlisted subnets: {len(allow_subnets)}")

    spec = normalize_spec(spec)
    eval_result = evaluate_compatibility(spec, cfg)
    return {
        "ok": True,
        "available": True,
        "connected": connected,
        "smart_dns_active": smart_active,
        "spec": spec,
        "summary_lines": summary_lines[:14],
        "warnings": eval_result.get("warnings") or [],
    }


def preview_from_spec(spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    eval_result = evaluate_compatibility(spec, cfg)
    doc = build_preset_document(spec)
    breakdown = build_breakdown(doc, spec, cfg)
    yaml_text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    return {
        "ok": True,
        "spec": spec,
        "effective": eval_result.get("effective"),
        "fields": eval_result.get("fields"),
        "warnings": eval_result.get("warnings"),
        "requires": eval_result.get("requires"),
        "document": doc,
        "yaml": yaml_text,
        "breakdown": breakdown,
    }


def create_preset_from_spec(name: str, spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.files import user_presets_dir

    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    filename = _slugify(name or spec.get("filename") or spec.get("label") or "my-preset")
    raw_name = f"{filename}.yaml"

    dest = user_presets_dir() / raw_name
    if dest.is_file():
        return {"ok": False, "error": "Preset already exists", "id": f"user/{raw_name}"}

    if spec.get("meshnet_peer"):
        peer = str(spec.get("mesh_peer_value") or cfg.get("mesh_peer") or "").strip()
        if not peer:
            return {
                "ok": False,
                "error": "Enter a Meshnet peer hostname — e.g. my-phone.nord (see Nord Dashboard → Meshnet or nordvpn meshnet peer list).",
            }

    preview = preview_from_spec(spec, cfg)
    if not preview.get("ok"):
        return preview

    dest.write_text(str(preview["yaml"]), encoding="utf-8")
    return {
        "ok": True,
        "id": f"user/{raw_name}",
        "path": str(dest),
        "document": preview["document"],
        "yaml": preview["yaml"],
        "breakdown": preview["breakdown"],
        "warnings": preview.get("warnings"),
        "requires": preview.get("requires"),
    }


def update_preset_from_spec(file_id: str, spec: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    import shutil

    import yaml

    from nordctl.files import _resolve_file_id

    cfg = cfg or load_config()
    spec = normalize_spec(spec)
    try:
        path, editable = _resolve_file_id(file_id)
    except ValueError as exc:
        return {"ok": False, "error": str(exc)}

    if not file_id.startswith("user/") or not editable:
        return {"ok": False, "error": "Only your custom preset files can be edited in the builder"}

    if not path.is_file():
        return {"ok": False, "error": "Preset file not found"}

    if spec.get("meshnet_peer"):
        peer = str(spec.get("mesh_peer_value") or cfg.get("mesh_peer") or "").strip()
        if not peer:
            return {
                "ok": False,
                "error": "Enter a Meshnet peer hostname — e.g. my-phone.nord (see Nord Dashboard → Meshnet or nordvpn meshnet peer list).",
            }

    try:
        with path.open(encoding="utf-8") as fh:
            existing = yaml.safe_load(fh) or {}
    except OSError as exc:
        return {"ok": False, "error": str(exc)}

    if not isinstance(existing, dict):
        return {"ok": False, "error": "Preset file must be a YAML mapping"}

    preview = preview_from_spec(spec, cfg)
    if not preview.get("ok"):
        return preview

    doc = preview.get("document") or {}
    if existing.get("id"):
        doc["id"] = existing["id"]

    yaml_text = yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)
    backup = path.with_suffix(path.suffix + ".bak")
    shutil.copy2(path, backup)
    path.write_text(yaml_text, encoding="utf-8")
    return {
        "ok": True,
        "id": file_id,
        "path": str(path),
        "document": doc,
        "yaml": yaml_text,
        "breakdown": preview.get("breakdown"),
        "warnings": preview.get("warnings"),
        "requires": preview.get("requires"),
    }


def move_preset_to_places(preset_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.presets import get_preset

    cfg = cfg or load_config()
    preset = get_preset(preset_id, cfg)
    if not preset:
        return {"ok": False, "error": f"unknown preset: {preset_id}"}
    if not preset.get("user"):
        return {"ok": False, "error": "Only custom presets can export values to My places"}
    spec = spec_from_preset_document(preset)
    result = apply_spec_to_places(spec, cfg)
    if not result.get("ok"):
        return result
    cfg = load_config()
    return {**result, "places_pending": places_pending_from_spec(spec, cfg)}
