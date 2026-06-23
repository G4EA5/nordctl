"""Unified privacy audit — leak lab + network stack with explanations and fix actions."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any

from nordctl.config import load_config
from nordctl.leaklab import run_leaklab
from nordctl.network_audit import run_network_audit

AUDIT_TOOLS: list[dict[str, Any]] = [
    {
        "id": "curl",
        "label": "curl",
        "bins": ["curl"],
        "packages": ["curl"],
        "install_tool": "curl",
        "required": True,
        "used_for": "Fetch your public IP for leak and allowlist checks",
    },
    {
        "id": "iproute2",
        "label": "ip (iproute2)",
        "bins": ["ip"],
        "packages": ["iproute2"],
        "install_tool": "iproute2",
        "required": True,
        "used_for": "Routing checks — VPN tunnel vs default gateway",
    },
    {
        "id": "ping",
        "label": "ping",
        "bins": ["ping"],
        "packages": ["iputils-ping"],
        "install_tool": "iputils-ping",
        "required": True,
        "used_for": "Basic internet reachability test",
    },
    {
        "id": "getent",
        "label": "getent",
        "bins": ["getent"],
        "packages": [],
        "required": True,
        "used_for": "DNS name resolution test (usually pre-installed with glibc)",
        "builtin": True,
    },
    {
        "id": "resolvectl",
        "label": "resolvectl",
        "bins": ["resolvectl"],
        "packages": ["systemd"],
        "required": False,
        "used_for": "Verify systemd-resolved and per-interface DNS",
    },
    {
        "id": "nmcli",
        "label": "nmcli",
        "bins": ["nmcli"],
        "packages": ["network-manager"],
        "install_tool": "network-manager",
        "required": False,
        "used_for": "Smart DNS on WiFi and WiFi interface DNS",
    },
    {
        "id": "nordvpn",
        "label": "nordvpn",
        "bins": ["nordvpn"],
        "packages": [],
        "required": False,
        "used_for": "VPN status, Nord DNS, and kill-switch context when NordVPN is used",
    },
    {
        "id": "lsattr",
        "label": "lsattr",
        "bins": ["lsattr"],
        "packages": ["e2fsprogs"],
        "install_tool": "e2fsprogs",
        "required": False,
        "used_for": "Detect immutable resolv.conf flags",
    },
]


def _item(
    *,
    id: str,
    category: str,
    name: str,
    ok: bool,
    summary: str,
    explain: str,
    fix: list[str] | None = None,
    severity: str | None = None,
    action: str | None = None,
    action_label: str | None = None,
    jump: str | None = None,
    jump_label: str | None = None,
    detail: str | None = None,
) -> dict[str, Any]:
    sev = severity or ("ok" if ok else "error")
    return {
        "id": id,
        "category": category,
        "name": name,
        "ok": ok,
        "severity": sev,
        "summary": summary,
        "explain": explain,
        "fix": [x for x in (fix or []) if x],
        "action": action if not ok else None,
        "action_label": action_label if not ok else None,
        "jump": jump if not ok else None,
        "jump_label": jump_label if not ok else None,
        "detail": detail or "",
    }


def _format_connectivity_detail(detail: Any) -> str:
    if not isinstance(detail, dict):
        text = str(detail or "").strip()
        return text[:120] + ("…" if len(text) > 120 else "")
    ping_ok = detail.get("ping")
    dns_ok = detail.get("dns")
    parts: list[str] = []
    if ping_ok is not None:
        parts.append(f"Ping 1.1.1.1: {'OK' if ping_ok else 'failed'}")
    if dns_ok is not None:
        parts.append(f"DNS (cloudflare.com): {'OK' if dns_ok else 'failed'}")
    if ping_ok is False and detail.get("ping_out"):
        parts.append(str(detail["ping_out"]).strip().splitlines()[0][:72])
    if dns_ok is False and detail.get("dns_out"):
        parts.append(str(detail["dns_out"]).strip()[:72])
    return " · ".join(parts)


def _format_route_detail(output: Any, *, ok: bool) -> str:
    line = " ".join(str(output or "").strip().split())
    if not line:
        return ""
    if ok:
        via = re.search(r"via (\S+)", line)
        dev = re.search(r"dev (\S+)", line)
        bits: list[str] = []
        if via:
            bits.append(f"via {via.group(1)}")
        if dev:
            bits.append(f"dev {dev.group(1)}")
        return " · ".join(bits) if bits else line[:80]
    return line[:120] + ("…" if len(line) > 120 else "")


def _enrich_leak_test(t: dict[str, Any], *, connected: bool) -> dict[str, Any]:
    tid = str(t.get("id") or "")
    ok = bool(t.get("ok"))
    detail = str(t.get("detail") or "")
    hint = str(t.get("hint") or "")

    if tid == "smart_dns_wifi":
        return _item(
            id=tid,
            category="dns",
            name=str(t.get("name") or "Smart DNS on WiFi"),
            ok=ok,
            summary="Smart DNS active on WiFi" if ok else "Smart DNS not applied on WiFi",
            explain=(
                "TV streaming uses Nord Smart DNS on your WiFi connection — not through the VPN tunnel. "
                "Your home ISP IP must be allowlisted in Nord Account; WiFi DNS should match the Smart DNS pair in config."
            ),
            fix=[
                hint or "Open WiFi → Smart DNS and apply the TV streaming preset.",
                "Or use Fix to push Smart DNS to configured WiFi profiles.",
            ],
            severity="warning" if not ok and not connected else ("ok" if ok else "info"),
            action=None if ok or connected else "dns_apply_smart",
            action_label="Apply Smart DNS",
            jump="dashboard/nord-dns",
            jump_label="Open Nord DNS",
            detail=detail,
        )

    if tid == "vpn_dns":
        return _item(
            id=tid,
            category="dns",
            name=str(t.get("name") or "DNS while VPN connected"),
            ok=ok,
            summary="VPN DNS looks correct" if ok else "Possible DNS leak while VPN is on",
            explain=(
                "When the VPN tunnel is up, DNS queries should go through Nord (103.86.x, 103.87.x, or 185.230.x). "
                "ISP or router DNS on the WiFi interface can leak what sites you visit even though traffic is tunneled."
            ),
            fix=[
                hint or "Enable Nord DNS under Dashboard → Switches.",
                "Check LAN allowlist — local DNS servers may bypass the tunnel.",
            ],
            severity="error" if not ok else "ok",
            jump="dashboard/switches",
            jump_label="Fix Nord DNS (Switches)",
            detail=detail,
        )

    if tid == "public_ip":
        return _item(
            id=tid,
            category="privacy",
            name=str(t.get("name") or "Public IP visible"),
            ok=ok,
            summary="Public IP detected" if ok else "Could not detect public IP",
            explain=(
                "This is the address Nord and streaming services see from this PC. "
                "For Smart DNS, allowlist your home ISP IP in Nord Account — not the VPN exit when connected."
            ),
            fix=[hint] if hint else [],
            severity="ok" if ok else "warning",
            jump="dashboard/connection-details" if ok else None,
            detail=detail,
        )

    if tid == "resolv_conf":
        return _item(
            id="leak_resolv_conf",
            category="dns",
            name=str(t.get("name") or "resolv.conf health"),
            ok=ok,
            summary=detail or ("resolv.conf OK" if ok else "resolv.conf problem"),
            explain=(
                "/etc/resolv.conf tells apps which DNS resolver to use. "
                "A stale Nord-generated file, immutable flag, or wrong symlink breaks DNS after disconnecting VPN."
            ),
            fix=[hint] if hint else ["See Doctors → Net doctor or run Fix if offered."],
            severity="error" if not ok else "ok",
            jump="network/diagnostics",
            jump_label="Open Diagnostics",
            detail=detail,
        )

    if tid == "route":
        return _item(
            id=tid,
            category="routing",
            name=str(t.get("name") or "Default route"),
            ok=ok,
            summary="Routing matches VPN state" if ok else "Route may not use VPN tunnel",
            explain=(
                "Shows which interface handles traffic to 1.1.1.1. "
                "When VPN is connected, the path should mention nordlynx; when disconnected, your normal gateway is expected."
            ),
            fix=[hint] if hint else ["Reconnect VPN or check split tunnel / allowlist settings."],
            severity="warning" if not ok else "ok",
            jump="dashboard/split-tunnel" if not ok and connected else ("network/audit/leak" if not ok else None),
            jump_label="Review split tunnel" if not ok and connected else ("Run leak tests" if not ok else None),
            detail=_format_route_detail(detail, ok=ok),
        )

    if tid == "killswitch":
        return _item(
            id=tid,
            category="privacy",
            name=str(t.get("name") or "Kill switch"),
            ok=True,
            summary="Kill switch enabled while VPN off",
            explain=(
                "Kill switch blocks all internet when VPN is disconnected — this is intentional for travel safety, "
                "not a leak. Disable it under Switches if you need normal internet without VPN."
            ),
            fix=[hint] if hint else [],
            severity="info",
            jump="dashboard/switches",
            detail=detail,
        )

    return _item(
        id=tid or "leak",
        category="privacy",
        name=str(t.get("name") or tid),
        ok=ok,
        summary=detail or ("OK" if ok else "Check failed"),
        explain=hint or detail or "Leak lab check.",
        fix=[hint] if hint and not ok else [],
        severity="warning" if not ok else "ok",
        jump="network/audit/leak" if not ok else None,
        jump_label="Run leak tests" if not ok else None,
        detail=detail,
    )


def _enrich_network_check(c: dict[str, Any]) -> dict[str, Any]:
    cid = str(c.get("id") or "")
    ok = bool(c.get("ok"))
    summary = str(c.get("summary") or "")
    fixes = [str(x) for x in (c.get("fix") or []) if x]
    detail = c.get("detail") or {}
    severity = str(c.get("severity") or ("ok" if ok else "error"))

    if cid == "resolv_conf":
        action = None
        action_label = None
        if not ok:
            if detail.get("immutable"):
                action = "fix_resolv_immutable"
                action_label = "Remove immutable flag"
            elif "plain file" in summary.lower():
                action = "fix_resolv_stub"
                action_label = "Link systemd stub"
        explain = (
            "System resolver configuration at /etc/resolv.conf. "
            "Immutable flags, Nord leftovers, or a plain file instead of the systemd stub cause DNS failures."
        )
        return _item(
            id=cid,
            category="dns",
            name="resolv.conf",
            ok=ok,
            summary=summary,
            explain=explain,
            fix=fixes,
            severity=severity,
            action=action,
            action_label=action_label,
            jump="network/diagnostics",
            jump_label="Open Diagnostics",
            detail="; ".join(str(x) for x in (detail.get("head") or [])[:3]),
        )

    if cid == "dns_manager":
        return _item(
            id=cid,
            category="dns",
            name="DNS manager",
            ok=ok,
            summary=summary,
            explain=(
                "systemd-resolved (resolvectl) manages DNS on most Linux desktops. "
                "If it is not running, WiFi DNS and Smart DNS presets cannot apply reliably."
            ),
            fix=fixes,
            severity=severity,
            jump="network/doctors/net",
            jump_label="Open Net doctor",
        )

    if cid == "ipv6":
        why = str(detail.get("why") or fixes[0] if fixes else "")
        return _item(
            id=cid,
            category="privacy",
            name="IPv6",
            ok=ok,
            summary=summary,
            explain=why or (
                "IPv6 can bypass an IPv4-only VPN tunnel and expose your real address. "
                "Disabling IPv6 system-wide is a common hardening step."
            ),
            fix=fixes[1:] if len(fixes) > 1 else fixes,
            severity=severity,
            action=c.get("action") if not ok else None,
            action_label="Disable IPv6" if not ok else None,
            jump="network/network/ipv6",
            jump_label="Open IPv6 settings",
        )

    if cid == "connectivity":
        return _item(
            id=cid,
            category="connectivity",
            name="Internet & DNS",
            ok=ok,
            summary=summary,
            explain=(
                "Basic reachability: ICMP ping to 1.1.1.1 and name lookup for cloudflare.com. "
                "Failure often means kill switch, broken resolv.conf, or no network — not necessarily a privacy leak."
            ),
            fix=fixes,
            severity=severity,
            jump="network/diagnostics",
            jump_label="Open Diagnostics",
            detail=_format_connectivity_detail(detail) if not ok else "",
        )

    return _item(
        id=cid,
        category="system",
        name=cid.replace("_", " ").title(),
        ok=ok,
        summary=summary,
        explain=fixes[0] if fixes else summary,
        fix=fixes[1:],
        severity=severity,
        jump="network/diagnostics" if not ok else None,
        jump_label="Open Diagnostics" if not ok else None,
    )


def audit_tool_requirements(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl.config import effective_usage_mode
    from nordctl.tool_install import _bin_exists, _tool_by_id, tools_payload

    tools_only = effective_usage_mode(cfg) == "tools_only"
    tp = tools_payload(cfg=cfg)
    rows: list[dict[str, Any]] = []
    for spec in AUDIT_TOOLS:
        if tools_only and spec["id"] == "nordvpn":
            continue
        if spec.get("builtin"):
            installed = _bin_exists(str((spec.get("bins") or ["getent"])[0]))
        else:
            installed = any(_bin_exists(str(b)) for b in (spec.get("bins") or []))
        missing = not installed
        pkgs = [str(p) for p in (spec.get("packages") or []) if p]
        install_tool = str(spec.get("install_tool") or spec.get("id") or "")
        catalog = _tool_by_id(install_tool, cfg) if install_tool else None
        if catalog and not pkgs:
            pkgs = [str(p) for p in (catalog.get("packages") or []) if p]
        install_cmd = f"sudo apt install -y {' '.join(pkgs)}" if pkgs else ""
        installable = bool(install_cmd) and spec["id"] not in ("nordvpn",)
        rows.append({
            **spec,
            "installed": installed,
            "missing": missing,
            "install_tool": install_tool if installable else None,
            "install_cmd": install_cmd if installable else "",
            "installable": installable,
        })
    missing_required = [t for t in rows if t.get("required") and t.get("missing")]
    missing_optional = [t for t in rows if not t.get("required") and t.get("missing")]
    return {
        "tools": rows,
        "ready": len(missing_required) == 0,
        "missing_required": [t["id"] for t in missing_required],
        "missing_optional": [t["id"] for t in missing_optional],
        "missing_installable": [t["id"] for t in rows if t.get("missing") and t.get("installable")],
        "can_install": bool(tp.get("can_install")),
        "can_install_terminal": bool(tp.get("can_install_terminal")),
        "summary": (
            "All required tools installed"
            if not missing_required
            else f"Install {len(missing_required)} required tool(s) for accurate results"
        ),
    }


def audit_email_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    from nordctl.alerts import is_module_enabled_alerts

    email = (cfg.get("alerts") or {}).get("email") or {}
    to_addr = str(email.get("to") or "").strip()
    host = str(email.get("smtp_host") or "").strip()
    configured = bool(host and to_addr and "@" in to_addr)
    password_set = bool(str(email.get("smtp_password") or "").strip())
    enabled = bool(email.get("enabled"))
    ready = configured and enabled and password_set and is_module_enabled_alerts(cfg)
    return {
        "configured": configured,
        "enabled": enabled,
        "password_set": password_set,
        "ready": ready,
        "to": to_addr if configured else "",
        "smtp_host": host if configured else "",
        "setup_hint": (
            "Open Settings → Email, enter SMTP host, recipient, and app password, then enable email alerts."
            if not ready
            else f"Reports can be sent to {to_addr}"
        ),
        "setup_route": "settings/network/email",
    }


def format_audit_report_text(data: dict[str, Any]) -> str:
    lines = [
        "nordctl privacy audit report",
        "=" * 32,
        data.get("headline") or data.get("summary") or "Audit complete",
        f"Score: {data.get('passed', 0)}/{data.get('total', 0)} checks passed",
        f"Leak lab: {data.get('leak_score', '—')}",
    ]
    if data.get("connected"):
        vpn_line = "VPN: connected"
        if data.get("vpn_ip"):
            vpn_line += f" — exit {data['vpn_ip']}"
        lines.append(vpn_line)
    elif data.get("home_ip"):
        lines.append(f"VPN: off — home ISP {data.get('home_ip')}")
    lines.extend(["", "Findings:", ""])
    for cat in data.get("categories") or []:
        lines.append(f"[{cat.get('label')}] {cat.get('passed')}/{cat.get('total')}")
        for item in cat.get("items") or []:
            mark = "OK" if item.get("ok") else str(item.get("severity") or "FAIL").upper()
            lines.append(f"  [{mark}] {item.get('name')}: {item.get('summary')}")
            if not item.get("ok") and item.get("fix"):
                lines.append(f"         Fix: {item['fix'][0]}")
        lines.append("")
    tools = data.get("tools") or {}
    missing = tools.get("missing_required") or []
    if missing:
        lines.append(f"Missing required tools: {', '.join(missing)}")
    lines.append("")
    lines.append("Generated locally by nordctl — no data sent except this email to your address.")
    return "\n".join(lines)


def send_audit_report_email(cfg: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    data = data or run_overall_audit(cfg)
    mail = audit_email_status(cfg)
    if not mail.get("ready"):
        return {
            "ok": False,
            "error": "Email not ready — configure SMTP under Settings → Email and enable email alerts.",
            "email": mail,
        }
    from nordctl.alerts import send_email_alert

    passed = data.get("passed", 0)
    total = data.get("total", 0)
    subject = f"Privacy audit — {passed}/{total} passed"
    body = format_audit_report_text(data)
    result = send_email_alert(subject, body, cfg, rule_id="audit_report")
    result["email"] = mail
    result["note"] = f"Audit report emailed to {mail.get('to')}" if result.get("ok") else result.get("error")
    return result


def run_overall_audit(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    leak = run_leaklab(cfg)
    audit = run_network_audit()
    connected = bool(leak.get("connected"))

    items: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for t in leak.get("tests") or []:
        if str(t.get("id") or "") == "resolv_conf":
            continue
        item = _enrich_leak_test(t, connected=connected)
        items.append(item)
        seen_ids.add(item["id"])

    for c in audit.get("checks") or []:
        item = _enrich_network_check(c)
        if item["id"] in seen_ids:
            continue
        items.append(item)
        seen_ids.add(item["id"])

    route = audit.get("route_sample") or {}
    if route:
        via_vpn = route.get("via_vpn")
        route_ok = bool(route.get("ok")) and (via_vpn == connected or not connected)
        if "route" not in seen_ids:
            items.append(
                _item(
                    id="route_sample",
                    category="routing",
                    name="Sample route (8.8.8.8)",
                    ok=route_ok,
                    summary="Route sample OK" if route_ok else "Route sample mismatch",
                    explain=(
                        "Quick check of which path the kernel would use to reach 8.8.8.8. "
                        "Should align with whether VPN is connected."
                    ),
                    fix=["Reconnect VPN or review split tunnel."] if not route_ok else [],
                    severity="warning" if not route_ok else "ok",
                    detail=_format_route_detail(route.get("output"), ok=route_ok),
                    jump="dashboard/split-tunnel" if not route_ok and connected else ("network/audit/leak" if not route_ok else None),
                    jump_label="Review split tunnel" if not route_ok and connected else ("Run leak tests" if not route_ok else None),
                )
            )

    passed = sum(1 for i in items if i["ok"])
    total = len(items)
    issues = [i for i in items if not i["ok"]]
    blocking = [i for i in issues if i.get("severity") == "error"]
    warnings = [i for i in issues if i.get("severity") in ("warning", "info")]

    categories_order = [
        ("privacy", "Privacy & IP"),
        ("dns", "DNS & resolver"),
        ("routing", "Routing"),
        ("connectivity", "Connectivity"),
        ("system", "System"),
    ]
    categories: list[dict[str, Any]] = []
    for cat_id, label in categories_order:
        cat_items = [i for i in items if i["category"] == cat_id]
        if not cat_items:
            continue
        cat_pass = sum(1 for i in cat_items if i["ok"])
        categories.append({
            "id": cat_id,
            "label": label,
            "passed": cat_pass,
            "total": len(cat_items),
            "items": cat_items,
        })

    if blocking:
        headline = f"{len(blocking)} issue{'s' if len(blocking) != 1 else ''} need attention"
    elif warnings:
        headline = f"Mostly OK — {len(warnings)} optional improvement{'s' if len(warnings) != 1 else ''}"
    else:
        headline = "All checks passed — privacy stack looks healthy"

    tools = audit_tool_requirements(cfg)
    email = audit_email_status(cfg)
    payload = {
        "ok": len(blocking) == 0 and passed == total,
        "passed": passed,
        "total": total,
        "issue_count": len(issues),
        "blocking_count": len(blocking),
        "warning_count": len(warnings),
        "headline": headline,
        "summary": headline,
        "leak_score": f"{leak.get('score', 0)}/{leak.get('total', 0)}",
        "connected": connected,
        "vpn_ip": leak.get("vpn_ip"),
        "home_ip": leak.get("home_ip"),
        "categories": categories,
        "items": items,
        "tools": tools,
        "email": email,
    }
    payload["report_text"] = format_audit_report_text(payload)
    return payload
