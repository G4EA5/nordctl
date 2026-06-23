"""Context-aware ISP / home public IP — trusted WiFi zones, auto-learn, travel-safe."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl.config import config_dir


def cache_path() -> Path:
    return config_dir() / "home_ip_cache.json"


def _load_cache() -> dict[str, Any]:
    path = cache_path()
    try:
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
    except (OSError, json.JSONDecodeError):
        pass
    return {"by_network": {}}


def _save_cache(data: dict[str, Any]) -> None:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def network_key(ssid: str | None) -> str:
    """Cache key for current L2 network (Wi‑Fi SSID or wired)."""
    return ssid.strip() if ssid and ssid.strip() else "__wired__"


def _looks_like_vpn_ip(
    candidate: str | None,
    *,
    vpn_ip: str | None = None,
    routed_ip: str | None = None,
) -> bool:
    """True when an address is likely a VPN exit, not home ISP."""
    if not candidate:
        return True
    if vpn_ip and candidate == vpn_ip:
        return True
    if routed_ip and candidate == routed_ip and vpn_ip:
        return True
    return False


def learn_public_ip(cfg: dict[str, Any], ip: str, *, ssid: str | None = None) -> None:
    """Remember public IP for this network when VPN is off (safe to learn anywhere)."""
    zones = cfg.get("wifi_zones") or {}
    if zones.get("home_ip_learn") is False:
        return
    from nordctl import nordvpn as nv

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    nord_ip = None
    if nv.available(bin_path):
        st = nv.parse_status(nv.run_cached(bin_path, ["status"], timeout=6).get("output", ""))
        if st.get("connected"):
            nord_ip = str(st.get("IP") or "").strip() or None
    if _looks_like_vpn_ip(ip, vpn_ip=nord_ip):
        return
    key = network_key(ssid)
    cache = _load_cache()
    by_net = cache.setdefault("by_network", {})
    by_net[key] = {
        "ip": ip,
        "ssid": ssid or "",
        "updated": datetime.now(tz=timezone.utc).isoformat(timespec="seconds"),
    }
    _save_cache(cache)


def cached_public_ip(
    cfg: dict[str, Any],
    *,
    ssid: str | None = None,
    vpn_ip: str | None = None,
    routed_ip: str | None = None,
) -> str | None:
    """Last learned public IP for this network — used on home WiFi when VPN is on."""
    key = network_key(ssid)
    row = (_load_cache().get("by_network") or {}).get(key) or {}
    ip = str(row.get("ip") or "").strip()
    if not ip or _looks_like_vpn_ip(ip, vpn_ip=vpn_ip, routed_ip=routed_ip):
        return None
    return ip


def _zone_home_ip(cfg: dict[str, Any], trusted_match: dict[str, Any] | None) -> str | None:
    if trusted_match:
        raw = str(trusted_match.get("home_public_ip") or "").strip()
        if raw:
            return raw
    zones = cfg.get("wifi_zones") or {}
    raw = str(zones.get("home_public_ip") or "").strip()
    return raw or None


def _legacy_global_home_ip(cfg: dict[str, Any]) -> str | None:
    """Deprecated top-level keys — only used on trusted WiFi when VPN is on."""
    for key in ("known_home_ip", "home_public_ip", "isp_public_ip"):
        raw = str(cfg.get(key) or "").strip()
        if raw:
            return raw
    return None


def static_fallback_ip(cfg: dict[str, Any]) -> str | None:
    """User-configured ISP address when live checks fail (Settings → Home ISP)."""
    fb = cfg.get("home_ip_fallback") or {}
    if not fb.get("enabled"):
        return None
    raw = str(fb.get("ip") or "").strip()
    return raw or None


def is_home_network(cfg: dict[str, Any], *, ssid: str | None, is_trusted: bool) -> bool:
    """Home WiFi for ISP display: explicit trusted zone or wifi.profiles entry."""
    if is_trusted:
        return True
    if not ssid or not ssid.strip():
        return False
    profiles = [
        str(p).strip()
        for p in ((cfg.get("wifi") or {}).get("profiles") or [])
        if str(p).strip()
    ]
    return ssid.strip() in profiles


def resolve_home_ip(
    cfg: dict[str, Any],
    *,
    connected: bool,
    probe_ip: str | None,
    live_public_ip: str | None,
    vpn_ip: str | None = None,
) -> dict[str, Any]:
    """Decide whether and how to show a home / public ISP address in the top bar."""
    from nordctl.zones import zone_status

    zs = zone_status(cfg)
    ssid = zs.get("ssid")
    is_trusted = bool(zs.get("is_trusted"))
    trusted_match = zs.get("trusted_match") if isinstance(zs.get("trusted_match"), dict) else None
    zones = cfg.get("wifi_zones") or {}
    only_when_trusted = zones.get("home_ip_when_trusted", True) is not False
    at_home = is_home_network(cfg, ssid=ssid, is_trusted=is_trusted)

    out: dict[str, Any] = {
        "ip": None,
        "label": "Home",
        "source": None,
        "show": False,
        "is_trusted_network": at_home,
        "ssid": ssid,
        "network_key": network_key(ssid),
    }

    if not connected:
        if live_public_ip:
            from nordctl.vpn_detect import analyze_vpn

            if not analyze_vpn({}, routed_public_ip=live_public_ip).get("active"):
                learn_public_ip(cfg, live_public_ip, ssid=ssid)
            out.update({
                "ip": live_public_ip,
                "label": "Home" if at_home else "Public",
                "source": "live",
                "show": True,
            })
        return out

    routed_ip = live_public_ip
    if (
        probe_ip
        and not _looks_like_vpn_ip(probe_ip, vpn_ip=vpn_ip, routed_ip=live_public_ip)
        and at_home
    ):
        out.update({"ip": probe_ip, "label": "Home", "source": "probe", "show": True})
        return out

    if only_when_trusted and not at_home:
        fb_ip = static_fallback_ip(cfg)
        if fb_ip and not _looks_like_vpn_ip(fb_ip, vpn_ip=vpn_ip, routed_ip=live_public_ip):
            out.update({
                "ip": fb_ip,
                "label": "Home",
                "source": "static_fallback",
                "show": True,
                "note": "Your saved ISP address (static fallback in Settings).",
            })
            return out
        out["note"] = (
            "On an untrusted network — home ISP address hidden. "
            "Add this WiFi as a trusted zone at home to remember your ISP IP."
        )
        return out

    # Home WiFi (or only_when_trusted disabled): zone config → cache → legacy global → static fallback
    for candidate, source in (
        (_zone_home_ip(cfg, trusted_match), "zone"),
        (cached_public_ip(cfg, ssid=ssid, vpn_ip=vpn_ip, routed_ip=live_public_ip), "learned"),
        (_legacy_global_home_ip(cfg) if at_home or not only_when_trusted else None, "config"),
        (static_fallback_ip(cfg), "static_fallback"),
    ):
        if candidate and not _looks_like_vpn_ip(candidate, vpn_ip=vpn_ip, routed_ip=live_public_ip):
            out.update({"ip": candidate, "label": "Home", "source": source, "show": True})
            if source == "learned":
                out["note"] = "Home ISP from last visit (VPN was off on this WiFi)."
            elif source == "zone":
                out["note"] = "Home ISP from trusted WiFi zone settings."
            elif source == "config":
                out["note"] = "Home ISP from config — prefer wifi_zones trusted entry + auto-learn."
            elif source == "static_fallback":
                out["note"] = "Your saved ISP address (Settings → Home ISP fallback)."
            return out

    out["note"] = (
        "Home ISP check blocked while VPN is on. "
        "Disconnect once on home WiFi to auto-learn, or set home_public_ip on your trusted zone."
    )
    return out
