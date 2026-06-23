"""Post-preset verification — quick DNS, IP, and routing checks."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.config import load_config
from nordctl.demo_mode import is_demo_mode
from nordctl.network_audit import check_resolv_conf, route_check


def verify_after_preset(
    cfg: dict[str, Any] | None = None,
    preset_id: str | None = None,
    *,
    demo: bool = False,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    if demo or is_demo_mode(cfg):
        checks = [
            {"id": "demo", "name": "Demo verification", "ok": True, "detail": "Simulated pass", "hint": ""},
            {"id": "public_ip", "name": "Public IP", "ok": True, "detail": "203.0.113.10 (demo)", "hint": ""},
            {"id": "dns", "name": "DNS configuration", "ok": True, "detail": "Demo DNS OK", "hint": ""},
            {"id": "route", "name": "Routing", "ok": True, "detail": "Demo route OK", "hint": ""},
        ]
        return {"ok": True, "demo_mode": True, "preset": preset_id, "checks": checks, "passed": 4, "total": 4}

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    connected = False
    if nv.available(bin_path):
        st_r = nv.run(bin_path, ["status"], timeout=8)
        status = nv.parse_status(st_r.get("output", ""))
        connected = bool(status.get("connected"))

    checks: list[dict[str, Any]] = []

    pub = net.public_ipv4(str(cfg.get("public_ip_check_url") or ""))
    checks.append({
        "id": "public_ip",
        "name": "Public IP reachable",
        "ok": bool(pub),
        "detail": pub or "Could not fetch public IP",
        "hint": "Allowlist this IP in Nord Account for Smart DNS" if pub and not connected else "",
    })

    wifi = cfg.get("wifi") or {}
    device = net.detect_wifi_device(wifi.get("device"))
    dns_wifi = net.wifi_dns_servers(device) if device else []
    sd = cfg.get("smart_dns") or {}
    primary = str(sd.get("primary") or "")
    secondary = str(sd.get("secondary") or "")
    smart_active = primary in dns_wifi and secondary in dns_wifi
    checks.append({
        "id": "dns",
        "name": "DNS on WiFi",
        "ok": smart_active or connected or bool(dns_wifi),
        "detail": ", ".join(dns_wifi) if dns_wifi else "No WiFi DNS (check VPN DNS if connected)",
        "hint": "Re-apply Smart DNS preset if streaming DNS is wrong" if not smart_active and preset_id and "smart" in preset_id else "",
    })

    rc = check_resolv_conf()
    checks.append({
        "id": "resolv_conf",
        "name": "resolv.conf",
        "ok": rc["ok"],
        "detail": rc.get("summary") or "—",
        "hint": "; ".join((rc.get("fix") or [])[:2]),
    })

    route = route_check("1.1.1.1")
    route_ok = bool(route.get("ok")) and (
        route.get("via_vpn") == connected if connected else True
    )
    checks.append({
        "id": "route",
        "name": "Route check (1.1.1.1)",
        "ok": route_ok,
        "detail": (route.get("output") or "")[:120],
        "hint": "Traffic should use VPN tunnel when connected" if connected else "",
    })

    passed = sum(1 for c in checks if c.get("ok"))
    total = len(checks)
    return {
        "ok": passed == total,
        "preset": preset_id,
        "checks": checks,
        "passed": passed,
        "total": total,
        "summary": f"{passed}/{total} checks passed",
    }
