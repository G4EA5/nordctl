"""DNS leak and privacy verification lab."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.config import load_config
from nordctl.network_audit import check_resolv_conf, route_check

NORD_DNS_PREFIXES = ("103.86.", "103.87.", "185.230.")


def _is_nord_dns(ip: str) -> bool:
    return any(ip.startswith(p) for p in NORD_DNS_PREFIXES)


def run_leaklab(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    wifi = cfg.get("wifi") or {}
    device = net.detect_wifi_device(wifi.get("device"))
    dns_wifi = net.wifi_dns_servers(device) if device else []
    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")

    status = {"connected": False}
    settings: dict[str, Any] = {}
    if nv.available(bin_path):
        st_r = nv.run(bin_path, ["status"], timeout=8)
        set_r = nv.run(bin_path, ["settings"], timeout=8)
        status = nv.parse_status(st_r.get("output", ""))
        settings = nv.parse_settings(set_r.get("output", ""))

    connected = bool(status.get("connected"))
    killswitch = "enabled" in str(settings.get("Kill Switch", "")).lower()
    firewall = "enabled" in str(settings.get("Firewall", "")).lower()

    tests: list[dict[str, Any]] = []

    # DNS on WiFi
    smart_ok = primary in dns_wifi and secondary in dns_wifi
    tests.append({
        "id": "smart_dns_wifi",
        "name": "Smart DNS on WiFi",
        "ok": smart_ok or connected,
        "detail": f"WiFi DNS: {', '.join(dns_wifi) or 'none'}",
        "hint": "Apply TV streaming (Smart DNS) preset" if not smart_ok and not connected else "",
    })

    # Nord DNS when VPN on
    if connected:
        nord_dns = all(_is_nord_dns(d) for d in dns_wifi) if dns_wifi else None
        tests.append({
            "id": "vpn_dns",
            "name": "DNS while VPN connected",
            "ok": nord_dns is not False,
            "detail": f"WiFi interface DNS: {', '.join(dns_wifi) or 'check resolvectl'}",
            "hint": "If ISP DNS appears, enable Nord DNS or check LAN allowlist leaks",
        })

    # Public IP — home ISP for allowlist, not VPN exit when connected
    from nordctl.ip_info import public_ip_report

    rep = public_ip_report(cfg, status)
    pub = rep.get("allowlist_ip") or rep.get("home_ip") or rep.get("routed_ip")
    tests.append({
        "id": "public_ip",
        "name": "Public IP visible",
        "ok": bool(pub),
        "detail": (rep.get("text") or "").strip() or "Could not fetch",
        "hint": "Allowlist the Home ISP line in Nord Account for Smart DNS — not the VPN exit." if pub and connected else (
            "Allowlist this IP in Nord Account for Smart DNS" if pub and not connected else ""
        ),
        "copy_value": pub,
    })

    # resolv.conf
    rc = check_resolv_conf()
    tests.append({
        "id": "resolv_conf",
        "name": "resolv.conf health",
        "ok": rc["ok"],
        "detail": rc["summary"],
        "hint": "; ".join(rc.get("fix") or [])[:200],
    })

    # Route leak sample
    route = route_check("1.1.1.1")
    route_ok = route.get("ok") and (route.get("via_vpn") == connected or not connected)
    tests.append({
        "id": "route",
        "name": "Route to 1.1.1.1",
        "ok": route_ok,
        "detail": route.get("output", "")[:120],
        "hint": "Traffic should use nordlynx when VPN connected" if connected else "",
    })

    # Kill switch advisory
    if killswitch and not connected:
        tests.append({
            "id": "killswitch",
            "name": "Kill switch while disconnected",
            "ok": True,
            "detail": "Kill switch enabled — no internet without VPN is expected",
            "hint": "Disable kill switch if you need internet while VPN off",
        })

    score = sum(1 for t in tests if t["ok"])
    return {
        "ok": score == len(tests),
        "score": score,
        "total": len(tests),
        "connected": connected,
        "external_ip": pub,
        "home_ip": rep.get("home_ip"),
        "routed_ip": rep.get("routed_ip"),
        "vpn_ip": status.get("IP") if connected else None,
        "killswitch": killswitch,
        "firewall": firewall,
        "smart_dns_expected": [primary, secondary],
        "tests": tests,
    }
