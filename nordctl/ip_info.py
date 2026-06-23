"""Public / home / VPN IP snapshot for the dashboard top bar."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import ipaddress
import re
from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.home_ip import resolve_home_ip
from nordctl.vpn_detect import analyze_vpn

_TUNNEL_IFACES = frozenset({"nordlynx", "nordtun", "tun0", "tap0"})
_SKIP_IFACE_PREFIXES = ("docker", "br-", "veth", "lo", "virbr")
# wg* excluded from primary LAN — WireGuard tunnel; physical WiFi/eth used for ISP probe


def _valid_public_ipv4(text: str) -> bool:
    try:
        addr = ipaddress.ip_address(text.strip())
    except ValueError:
        return False
    return addr.version == 4 and not addr.is_private and not addr.is_loopback and not addr.is_reserved


def _parse_ipv4(text: str) -> str | None:
    m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", text or "")
    if not m:
        return None
    ip = m.group(1)
    return ip if _valid_public_ipv4(ip) else None


def _parse_ipv4_any(text: str) -> str | None:
    """Any dotted IPv4 (private mesh / tunnel addresses allowed)."""
    m = re.search(r"\b(\d{1,3}(?:\.\d{1,3}){3})\b", text or "")
    if not m:
        return None
    try:
        ipaddress.ip_address(m.group(1))
    except ValueError:
        return None
    return m.group(1)


def primary_lan_iface() -> str | None:
    """First non-tunnel interface with a global IPv4 address (Wi‑Fi / Ethernet)."""
    r = net.run_cmd(["ip", "-4", "-o", "addr", "show", "scope", "global"], timeout=4)
    if not r["ok"]:
        return None
    for line in r["output"].splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        dev = parts[1]
        if dev in _TUNNEL_IFACES:
            continue
        if any(dev.startswith(p) for p in _SKIP_IFACE_PREFIXES):
            continue
        return dev
    return None


def public_ipv4_via_iface(url: str, iface: str, *, timeout: float = 6.0) -> str | None:
    """Fetch public IPv4 leaving via a specific interface (home ISP while VPN is on)."""
    if not iface or not url:
        return None
    r = net.run_cmd(
        ["curl", "-s", "--max-time", str(max(1, int(timeout))), "--interface", iface, url],
        timeout=timeout + 2,
    )
    if r["ok"]:
        for line in r["output"].splitlines():
            ip = _parse_ipv4(line)
            if ip:
                return ip
    return None


def _looks_double_vpn(status: dict[str, Any]) -> bool:
    blob = " ".join(
        str(status.get(k) or "")
        for k in ("Server", "Hostname", "Country", "City", "Transfer")
    ).lower()
    return "double" in blob or "double_vpn" in blob


def home_allowlist_ip(
    cfg: dict[str, Any],
    status: dict[str, Any] | None = None,
    *,
    ip_info: dict[str, Any] | None = None,
    pub_routed: str | None = None,
) -> dict[str, Any]:
    """Home ISP for Smart DNS / WiFi hub — not default-route exit while VPN is on."""
    status = status or {}
    if pub_routed is None:
        pub_routed = net.public_ipv4(str(cfg.get("public_ip_check_url") or ""))
    allowlist_ip = pub_routed
    allowlist_note = None
    if ip_info:
        home_chain = next((x for x in (ip_info.get("chain") or []) if x.get("role") == "home"), None)
        home_ip = ip_info.get("home_ip") or (home_chain or {}).get("ip")
        if home_ip and home_ip != pub_routed:
            allowlist_ip = home_ip
            allowlist_note = "Home ISP — use this in Nord Account (not VPN exit)"
        elif status.get("connected") and pub_routed:
            allowlist_note = "Default-route check — may be VPN exit while connected"
    return {
        "public_ip": allowlist_ip,
        "public_ip_routed": pub_routed,
        "public_ip_note": allowlist_note,
    }


def display_public_ip(ip_info: dict[str, Any]) -> str:
    """Best home/public IP for dashboards — prefers home ISP over VPN exit."""
    home = ip_info.get("home_ip")
    if not home:
        home_chain = next((x for x in (ip_info.get("chain") or []) if x.get("role") == "home"), None)
        home = (home_chain or {}).get("ip")
    if home:
        return home
    if ip_info.get("vpn_active") or ip_info.get("connected"):
        return ip_info.get("vpn_ip") or ip_info.get("routed_ip") or ip_info.get("external_ip") or "—"
    return ip_info.get("external_ip") or ip_info.get("routed_ip") or "—"


def public_ip_report(
    cfg: dict[str, Any] | None = None,
    status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Diagnostics snapshot: home ISP vs default-route / VPN exit."""
    cfg = cfg or load_config()
    if status is None:
        bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
        status = {}
        if nv.available(bin_path):
            status = nv.parse_status(
                nv.run_cached(bin_path, ["status"], timeout=8).get("output", "")
            )
    url = str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip")
    pub_routed = net.public_ipv4(url)
    ip_info = build_ip_info(cfg, status, fast=False)
    allow = home_allowlist_ip(cfg, status, ip_info=ip_info, pub_routed=pub_routed)
    home = allow.get("public_ip")
    routed = allow.get("public_ip_routed")
    vpn_ip = ip_info.get("vpn_ip")
    connected = bool(status.get("connected"))
    lines: list[str] = []
    if home and routed and home != routed:
        lines.append(f"Home ISP (Smart DNS allowlist): {home}")
        lines.append(f"Default-route check (VPN exit):  {routed}")
    elif home:
        lines.append(f"Public IPv4: {home}")
    elif routed:
        lines.append(f"Public IPv4 (default route): {routed}")
    else:
        lines.append("Public IPv4: could not determine")
    if vpn_ip and home != vpn_ip and not (home and routed and home != routed):
        lines.append(f"VPN exit (Nord status):       {vpn_ip}")
    note = allow.get("public_ip_note")
    if note:
        lines.append(f"# {note}")
    elif connected and routed and (not home or home == routed):
        lines.append("# With VPN on, default-route check shows VPN exit — not home ISP.")
        lines.append("# Disconnect once on home WiFi to auto-learn, or set home_public_ip on a trusted zone.")
    return {
        "ok": bool(home or routed),
        "home_ip": home,
        "routed_ip": routed,
        "vpn_ip": vpn_ip,
        "allowlist_ip": home or routed,
        "note": note,
        "text": "\n".join(lines) + "\n",
        "connected": connected,
    }


def build_ip_info(
    cfg: dict[str, Any],
    status: dict[str, Any] | None = None,
    *,
    settings: dict[str, Any] | None = None,
    mesh_ip: str | None = None,
    meshnet_enabled: bool | None = None,
    fast: bool = False,
) -> dict[str, Any]:
    """Build top-bar IP payload: home/public + VPN exit when connected; Mesh when enabled."""
    settings = settings or {}
    status = status or {}
    if meshnet_enabled is None:
        meshnet_enabled = "enabled" in str(settings.get("Meshnet", "")).lower()
    url = str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip")
    nord_connected = bool(status.get("connected"))
    nord_ip = _parse_ipv4(str(status.get("IP") or ""))

    routed_ip: str | None = None
    home_ip: str | None = None
    lan_iface = primary_lan_iface() if not fast else None
    home_ctx: dict[str, Any] = {}
    vpn: dict[str, Any] = {}

    if fast:
        vpn_active = nord_connected
        vpn_ip = nord_ip
        exit_label = "VPN"
        if nord_connected:
            home_ctx = resolve_home_ip(
                cfg,
                connected=True,
                probe_ip=None,
                live_public_ip=None,
                vpn_ip=vpn_ip,
            )
        external_ip = home_ctx.get("ip") if home_ctx.get("show") else None
    else:
        probe_timeout = min(3.0, float(cfg.get("public_ip_timeout") or 3))

        def _fetch_public() -> str | None:
            r = net.run_cmd(
                ["curl", "-s", "--max-time", str(max(1, int(probe_timeout))), url],
                timeout=probe_timeout + 1,
            )
            if r["ok"]:
                for line in r["output"].splitlines():
                    ip = _parse_ipv4(line)
                    if ip:
                        return ip
            return None

        if lan_iface:
            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=2) as pool:
                routed_fut = pool.submit(_fetch_public)
                home_fut = pool.submit(lambda: public_ipv4_via_iface(url, lan_iface, timeout=probe_timeout))
                routed_ip = routed_fut.result()
                home_ip = home_fut.result()
        else:
            routed_ip = _fetch_public()

        vpn = analyze_vpn(status, routed_public_ip=routed_ip)
        vpn_active = bool(vpn.get("active"))
        vpn_ip = nord_ip if nord_connected else (_parse_ipv4(str(vpn.get("exit_ip") or "")) or routed_ip if vpn_active else None)
        exit_label = str(vpn.get("provider_label") or "VPN") if vpn_active and not nord_connected else "VPN"

        home_ctx = resolve_home_ip(
            cfg,
            connected=vpn_active,
            probe_ip=home_ip,
            live_public_ip=routed_ip,
            vpn_ip=vpn_ip,
        )

    if not fast:
        external_ip = home_ctx.get("ip") if home_ctx else None

    double_vpn = nord_connected and _looks_double_vpn(status)
    chain: list[dict[str, str]] = []

    if home_ctx.get("show") and home_ctx.get("ip"):
        ip = str(home_ctx["ip"])
        if not vpn_active or ip != vpn_ip:
            chain.append({
                "role": "home",
                "label": str(home_ctx.get("label") or "Home"),
                "ip": ip,
                "source": str(home_ctx.get("source") or ""),
            })

    if vpn_active and vpn_ip:
        chain.append({
            "role": "vpn",
            "label": exit_label if not fast else "VPN",
            "ip": vpn_ip,
            "provider": str(vpn.get("provider") or "nordvpn" if nord_connected else ""),
        })
    elif not vpn_active and external_ip and not any(x.get("role") == "home" for x in chain):
        chain.append({
            "role": "home",
            "label": str(home_ctx.get("label") or "Public"),
            "ip": external_ip,
            "source": str(home_ctx.get("source") or "live"),
        })

    mesh_display: str | None = None
    if meshnet_enabled:
        mesh_val = _parse_ipv4_any(str(mesh_ip or ""))
        if not mesh_val:
            mesh_val = _parse_ipv4_any(str(nv.tunnel_local_ip() or ""))
        chain_ips = {item["ip"] for item in chain}
        if mesh_val and mesh_val not in chain_ips:
            chain.append({"role": "mesh", "label": "Mesh", "ip": mesh_val})
            mesh_display = mesh_val

    note = home_ctx.get("note")
    if double_vpn and not note:
        note = "Double VPN — Nord CLI only reports the final exit IP, not each hop."
    if not note and vpn_active and not nord_connected and vpn.get("provider_label"):
        note = f"{vpn.get('provider_label')} active — Home ISP from LAN probe or cache when on home WiFi."

    return {
        "external_ip": external_ip,
        "home_ip": home_ctx.get("ip") if home_ctx else home_ip,
        "home_ip_source": home_ctx.get("source"),
        "home_ip_label": home_ctx.get("label"),
        "home_trusted_network": home_ctx.get("is_trusted_network"),
        "vpn_ip": vpn_ip if vpn_active else None,
        "routed_ip": routed_ip,
        "routed_ip_note": (
            "Default-route check — VPN exit or relay (not shown as Home ISP)."
            if vpn_active and routed_ip and routed_ip != vpn_ip
            else None
        ),
        "connected": nord_connected,
        "vpn_active": vpn_active,
        "vpn_provider": vpn.get("provider"),
        "vpn_provider_label": vpn.get("provider_label"),
        "vpn_interface": vpn.get("interface"),
        "double_vpn": double_vpn,
        "lan_iface": lan_iface,
        "chain": chain,
        "note": note,
        "mesh_ip": mesh_display,
        "tunnel_local": nv.tunnel_local_ip() if not fast else None,
        "fast": fast,
    }
