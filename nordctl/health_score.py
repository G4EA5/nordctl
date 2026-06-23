"""Unified VPN + network health score (0–100)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any


def compute_health_score(
    *,
    doctor: dict[str, Any],
    leaklab: dict[str, Any],
    audit: dict[str, Any],
    status: dict[str, Any],
    services: dict[str, Any],
    traffic_summary: dict[str, Any] | None = None,
    light: bool = False,
    network_only: bool = False,
) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    score = 100

    def add(ok: bool, name: str, detail: str, weight: int, fix: str = "") -> None:
        nonlocal score
        if not ok:
            score -= weight
        checks.append({"ok": ok, "name": name, "detail": detail, "weight": weight, "fix": fix})

    connected = bool((status or {}).get("connected"))

    if not network_only:
        nordvpnd = (services or {}).get("nordvpnd") or {}
        add(
            nordvpnd.get("active"),
            "Nord daemon",
            "nordvpnd is running" if nordvpnd.get("active") else "VPN daemon is down",
            25,
            "Nord Dashboard → Nord services → Start nordvpnd",
        )
        add(
            doctor.get("ready") or connected,
            "Nord logged in",
            "Account ready" if doctor.get("ready") else "Install/login required",
            15,
            "Nord Dashboard → Setup (install) or Nord doctor",
        )

    if not light:
        lab_score = leaklab.get("score", 0)
        lab_total = leaklab.get("total") or 1
        lab_ok = lab_score >= lab_total - 1 if lab_total else True
        add(lab_ok, "Leak lab", f"{lab_score}/{lab_total} privacy checks passed", 20, "Lab → Run all tests")

        audit_ok = all(c.get("ok") for c in (audit.get("checks") or [])[:4]) if audit.get("checks") else True
        add(audit_ok, "Network audit", "DNS and routing look sane" if audit_ok else "DNS/IPv6 issues found", 15, "Lab → Network audit")

    if not network_only:
        if connected:
            if not light:
                direct = int((traffic_summary or {}).get("direct_internet") or 0)
                if direct == 0:
                    add(
                        True,
                        "Internet via VPN",
                        "Every app connection to the internet is going through the NordVPN tunnel right now.",
                        15,
                    )
                else:
                    add(
                        False,
                        "Direct internet traffic",
                        f"{direct} connection(s) to the internet are bypassing the VPN (not using the tunnel). "
                        "Often normal with split tunnel or LAN allowlist — open Traffic → Direct to see which apps.",
                        15,
                        "Network & Security → Traffic → Direct filter",
                    )
            else:
                add(True, "VPN connected", "Tunnel is up — open Lab for leak and traffic checks.", 0)
        else:
            add(True, "VPN optional", "VPN is off — enable when on untrusted networks", 0)

    score = max(0, min(100, score))
    if network_only and light:
        grade, color = "Network", "on"
        summary = "Network-focused score — VPN install and connect live on Nord Dashboard."
    elif light and not connected and not network_only:
        grade, color = "Quick", "on"
        summary = "Quick score from Nord daemon and login — open Lab for leak tests and audit."
    elif score >= 85:
        grade, color, summary = "Excellent", "on", "Your VPN and network setup looks strong."
    elif score >= 65:
        grade, color, summary = "Good", "on", "Mostly protected — a few optional improvements remain."
    elif score >= 40:
        grade, color, summary = "Fair", "warn", "Some issues need attention before trusting privacy."
    else:
        grade, color, summary = "Poor", "off", "Fix critical items before relying on VPN privacy."

    return {
        "score": score,
        "grade": grade,
        "color": color,
        "summary": summary,
        "checks": checks,
    }
