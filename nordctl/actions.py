"""Execute preset step actions against NordVPN and local network."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv

# Safe nordvpn subcommands for generic preset steps (no login/logout/register).
ALLOWED_NORDVPN_ROOT = frozenset({"disconnect", "connect", "set", "allowlist", "meshnet"})


def substitute(value: str, cfg: dict[str, Any]) -> str:
    mapping = {
        "connect_country": cfg.get("connect_country") or "",
        "travel_country": cfg.get("travel_country") or "",
        "gaming_country": cfg.get("gaming_country") or cfg.get("connect_country") or "",
        "work_country": cfg.get("work_country") or cfg.get("connect_country") or "",
        "connect_server": cfg.get("connect_server") or "",
        "connect_city": cfg.get("connect_city") or "",
        "lan_allowlist_cidr": cfg.get("lan_allowlist_cidr") or "",
        "mesh_peer": cfg.get("mesh_peer") or "",
        "custom_dns": " ".join(str(x) for x in (cfg.get("custom_dns") or [])),
    }
    out = str(value)
    for key, val in mapping.items():
        out = out.replace("{" + key + "}", str(val))
    return out


def _validate_nordvpn_args(args: list[str]) -> str | None:
    if not args:
        return "empty nordvpn args"
    root = args[0]
    if root not in ALLOWED_NORDVPN_ROOT:
        return f"nordvpn command not allowed: {root}"
    if root == "meshnet" and len(args) >= 2:
        sub = args[1]
        if sub not in {"peer"}:
            return f"meshnet subcommand not allowed: {sub}"
        if len(args) >= 3 and args[2] not in {"connect", "refresh", "list"}:
            return f"meshnet peer command not allowed: {args[2]}"
    return None


def run_step(
    step: dict[str, Any],
    cfg: dict[str, Any],
    bin_path: str,
    steps: list[dict[str, Any]],
) -> None:
    def nord(*args: str, timeout: float = 30.0) -> dict[str, Any]:
        r = nv.run(bin_path, list(args), timeout=timeout)
        steps.append(r)
        return r

    action = str(step.get("action") or "").strip()

    if action == "nordvpn_disconnect":
        nord("disconnect")
        return

    if action == "nordvpn_connect":
        target = substitute(str(step.get("target") or ""), cfg).strip()
        group = substitute(str(step.get("group") or ""), cfg).strip()
        args: list[str] = ["connect"]
        if group:
            args.extend(["--group", group])
        elif target:
            args.extend(target.split())
        nord(*args, timeout=60)
        return

    if action == "nordvpn_reconnect":
        nord("disconnect")
        target = substitute(str(step.get("target") or ""), cfg).strip()
        group = substitute(str(step.get("group") or ""), cfg).strip()
        args = ["connect"]
        if group:
            args.extend(["--group", group])
        elif target:
            args.extend(target.split())
        nord(*args, timeout=60)
        return

    if action == "meshnet_peer_connect":
        peer = substitute(str(step.get("peer") or cfg.get("mesh_peer") or ""), cfg).strip()
        if peer:
            nord("meshnet", "peer", "connect", peer, timeout=60)
        else:
            steps.append({"ok": False, "output": "mesh_peer not configured", "args": ["meshnet"]})
        return

    if action == "nordvpn_set":
        key = str(step.get("key") or "").strip()
        value = substitute(str(step.get("value") or ""), cfg).strip()
        extra = substitute(str(step.get("extra") or ""), cfg).strip()
        if key == "defaults":
            nord("set", "defaults")
        elif key == "dns" and value.lower() in {"off", "disabled", "disable", "0", "false"}:
            nord("set", "dns", "off")
        elif key == "dns" and value.lower() in {"on", "yes", "enabled"}:
            nord("set", "dns", "off")
        elif key == "dns" and value:
            nord("set", "dns", *value.split())
        elif key and value:
            args = ["set", key, value]
            if extra:
                args.extend(extra.split())
            nord(*args)
        return

    if action == "nordvpn_settings":
        for key, raw in (step.get("settings") or {}).items():
            value = substitute(str(raw), cfg).strip()
            if not key or not value:
                continue
            if str(key) == "defaults":
                nord("set", "defaults")
            elif str(key) == "dns" and value.lower() in {"off", "disabled"}:
                nord("set", "dns", "off")
            elif str(key) == "dns" and value.lower() in {"on", "yes", "enabled"}:
                nord("set", "dns", "off")
            elif str(key) == "dns":
                nord("set", "dns", *value.split())
            else:
                nord("set", str(key), value)
        return

    if action == "nordvpn_args":
        raw_args = step.get("args") or []
        args = [substitute(str(a), cfg) for a in raw_args]
        err = _validate_nordvpn_args(args)
        if err:
            steps.append({"ok": False, "output": err, "args": args})
            return
        timeout = float(step.get("timeout") or 60)
        nord(*args, timeout=timeout)
        return

    if action == "network_smart_dns":
        sd = cfg.get("smart_dns") or {}
        wifi = cfg.get("wifi") or {}
        steps.extend(
            net.apply_smart_dns(
                list(wifi.get("profiles") or []),
                str(sd.get("primary") or "103.86.96.103"),
                str(sd.get("secondary") or "103.86.99.103"),
                wifi.get("device"),
            )
        )
        return

    if action == "network_restore_dns":
        wifi = cfg.get("wifi") or {}
        steps.extend(net.restore_dns(list(wifi.get("profiles") or []), wifi.get("device")))
        return

    if action == "allowlist_voip_ports":
        step = {**step, "from_config": "voip_ports"}
        action = "allowlist_ports"

    if action == "allowlist_ports":
        ports = step.get("ports") or cfg.get(str(step.get("from_config") or "")) or []
        protocols = step.get("protocols") or ["TCP", "UDP"]
        for port in ports:
            for proto in protocols:
                nord("allowlist", "add", "port", str(port), "protocol", str(proto).upper(), timeout=12)
        return

    if action == "allowlist_subnets_from_config":
        for cidr in cfg.get("allowlist_subnets") or []:
            if cidr:
                nord("allowlist", "add", "subnet", str(cidr))
        return

    if action == "allowlist_subnet":
        cidr = substitute(str(step.get("cidr") or ""), cfg).strip()
        if cidr:
            nord("allowlist", "add", "subnet", cidr)
        return

    if action == "allowlist_remove_subnet":
        cidr = substitute(str(step.get("cidr") or ""), cfg).strip()
        if cidr:
            nord("allowlist", "remove", "subnet", cidr)
        return

    steps.append({"ok": False, "output": f"unknown action: {action}", "args": [action]})


def describe_step(step: dict[str, Any], cfg: dict[str, Any] | None = None) -> str:
    """Human-readable description of a preset step (for preview UI)."""
    cfg = cfg or {}
    action = str(step.get("action") or "").strip()

    if action == "nordvpn_disconnect":
        return "Disconnect VPN"
    if action == "nordvpn_connect":
        target = substitute(str(step.get("target") or ""), cfg).strip()
        group = substitute(str(step.get("group") or ""), cfg).strip()
        if group:
            return f"Connect — group {group}"
        return f"Connect — {target or 'default'}"
    if action == "nordvpn_reconnect":
        target = substitute(str(step.get("target") or ""), cfg).strip()
        return f"Reconnect VPN{f' to {target}' if target else ''}"
    if action == "meshnet_peer_connect":
        peer = substitute(str(step.get("peer") or cfg.get("mesh_peer") or ""), cfg).strip()
        return f"Meshnet peer connect — {peer or '(mesh_peer not set)'}"
    if action == "nordvpn_set":
        key = str(step.get("key") or "")
        value = substitute(str(step.get("value") or ""), cfg)
        return f"Set {key} → {value or 'defaults'}"
    if action == "nordvpn_settings":
        keys = ", ".join(str(k) for k in (step.get("settings") or {}).keys())
        return f"Apply settings: {keys or '—'}"
    if action == "nordvpn_args":
        args = step.get("args") or []
        return f"nordvpn {' '.join(str(a) for a in args)}"
    if action == "network_smart_dns":
        profiles = list((cfg.get("wifi") or {}).get("profiles") or [])
        return f"Apply Smart DNS on WiFi ({len(profiles)} profile(s))"
    if action == "network_restore_dns":
        return "Restore automatic DNS on WiFi"
    if action == "allowlist_ports":
        ports = step.get("ports") or cfg.get("voip_ports") or []
        return f"Allowlist ports: {', '.join(str(p) for p in ports)}"
    if action == "allowlist_voip_ports":
        return "Allowlist VoIP ports from config"
    if action == "allowlist_subnets_from_config":
        return "Allowlist subnets from config"
    if action == "allowlist_subnet":
        cidr = substitute(str(step.get("cidr") or ""), cfg)
        return f"Allowlist subnet {cidr}"
    if action == "allowlist_remove_subnet":
        cidr = substitute(str(step.get("cidr") or ""), cfg)
        return f"Remove allowlist subnet {cidr}"
    return action or "Unknown step"
