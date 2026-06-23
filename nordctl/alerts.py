"""Local alerts — browser queue + optional email via user SMTP only."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config, save_config

_pending: list[dict[str, Any]] = []
_pending_lock = threading.Lock()
_watch_thread: threading.Thread | None = None
_watch_stop = threading.Event()
_last_vpn_connected: bool | None = None
_last_email: dict[str, float] = {}


def _alerts_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("alerts") or {}


def _rate_ok(rule_id: str, cfg: dict[str, Any]) -> bool:
    ac = _alerts_cfg(cfg)
    minutes = float(ac.get("rate_limit_minutes") or 15)
    now = time.time()
    last = _last_email.get(rule_id, 0)
    if now - last < minutes * 60:
        return False
    _last_email[rule_id] = now
    return True


def queue_browser_alert(
    title: str,
    body: str,
    *,
    rule_id: str = "general",
    severity: str = "info",
) -> dict[str, Any]:
    entry = {
        "id": f"{int(time.time() * 1000)}",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "title": title.strip(),
        "body": body.strip(),
        "rule_id": rule_id,
        "severity": severity,
    }
    with _pending_lock:
        _pending.append(entry)
        if len(_pending) > 50:
            del _pending[:-50]
    _append_alert_log(entry)
    return entry


def pending_browser_alerts(*, clear: bool = False) -> dict[str, Any]:
    with _pending_lock:
        items = list(_pending)
        if clear:
            _pending.clear()
    return {"ok": True, "alerts": items, "count": len(items)}


def _append_alert_log(entry: dict[str, Any]) -> None:
    path = config_dir() / "alerts.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass


def send_email_alert(
    subject: str,
    body: str,
    cfg: dict[str, Any] | None = None,
    *,
    rule_id: str = "general",
) -> dict[str, Any]:
    """Send only to configured To address via user SMTP — never to third parties."""
    cfg = cfg or load_config()
    if not is_module_enabled_alerts(cfg):
        return {"ok": False, "skipped": True, "reason": "alerts module disabled"}
    ac = _alerts_cfg(cfg)
    email = ac.get("email") or {}
    if not email.get("enabled"):
        return {"ok": False, "skipped": True, "reason": "email disabled"}
    to_addr = str(email.get("to") or "").strip()
    if not to_addr or "@" not in to_addr:
        return {"ok": False, "error": "Set alerts.email.to in config — only this address receives mail"}
    if not _rate_ok(rule_id, cfg):
        return {"ok": True, "skipped": True, "reason": "rate limited"}

    host = str(email.get("smtp_host") or "").strip()
    port = int(email.get("smtp_port") or 587)
    user = str(email.get("smtp_user") or "").strip()
    password = str(email.get("smtp_password") or "")
    from_addr = str(email.get("from") or user or to_addr).strip()
    use_tls = bool(email.get("use_tls", True))

    if not host:
        return {"ok": False, "error": "Set alerts.email.smtp_host — use your own mail provider (Gmail app password, etc.)"}

    msg = EmailMessage()
    msg["Subject"] = f"[nordctl] {subject}"[:200]
    msg["From"] = from_addr
    msg["To"] = to_addr
    msg.set_content(
        f"{body}\n\n---\nLocal nordctl alert. No tracking. Config: ~/.config/nordctl/config.yaml\n"
    )

    try:
        if use_tls:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                smtp.ehlo()
                smtp.starttls(context=ssl.create_default_context())
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=20) as smtp:
                if user:
                    smtp.login(user, password)
                smtp.send_message(msg)
        return {"ok": True, "to": to_addr, "note": "Email sent to your configured address only"}
    except (smtplib.SMTPException, OSError, ssl.SSLError) as exc:
        return {"ok": False, "error": str(exc)}


def send_webhook_alert(
    title: str,
    body: str,
    cfg: dict[str, Any],
    *,
    rule_id: str = "general",
) -> dict[str, Any]:
    """POST alert JSON to a URL the user configured (optional tier 6)."""
    wh = (_alerts_cfg(cfg).get("webhook") or {})
    url = str(wh.get("url") or "").strip()
    if not wh.get("enabled") or not url:
        return {"ok": True, "skipped": True}
    if not url.startswith(("http://", "https://")):
        return {"ok": False, "error": "webhook url must start with http:// or https://"}
    payload = json.dumps(
        {"title": title, "body": body, "rule_id": rule_id, "source": "nordctl"}
    ).encode()
    try:
        import urllib.error
        import urllib.request

        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "nordctl-alerts/1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            code = getattr(resp, "status", 200) or 200
        return {"ok": True, "status": code, "url": url.split("?")[0][:120]}
    except urllib.error.URLError as exc:
        return {"ok": False, "error": str(exc.reason or exc)}


def is_module_enabled_alerts(cfg: dict[str, Any]) -> bool:
    from nordctl.features import is_module_enabled

    return is_module_enabled("alerts", cfg)


def fire_alert(
    rule_id: str,
    title: str,
    body: str,
    *,
    severity: str = "warn",
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    if not is_module_enabled_alerts(cfg):
        return {"ok": True, "skipped": True}
    ac = _alerts_cfg(cfg)
    rules = ac.get("rules") or {}
    if not rules.get(rule_id, True) and rule_id not in ("test", "general"):
        return {"ok": True, "skipped": True, "reason": f"rule {rule_id} disabled"}

    results: dict[str, Any] = {"ok": True, "rule_id": rule_id}
    if ac.get("browser_enabled", True):
        results["browser"] = queue_browser_alert(title, body, rule_id=rule_id, severity=severity)
    if (ac.get("email") or {}).get("enabled"):
        results["email"] = send_email_alert(title, body, cfg, rule_id=rule_id)
    webhook = ac.get("webhook") or {}
    if webhook.get("enabled") and webhook.get("url"):
        results["webhook"] = send_webhook_alert(title, body, cfg, rule_id=rule_id)

    from nordctl.activity_log import record_event

    record_event(
        "security",
        title,
        detail=body,
        level="warn" if severity != "info" else "info",
        ok=True,
        meta={"alert_rule": rule_id},
    )
    return results


RULE_DESCRIPTIONS: dict[str, str] = {
    "vpn_disconnect": "Fires when NordVPN was connected and drops unexpectedly — bell, toast, and email (if enabled).",
    "smart_dns_drift": "WiFi DNS no longer matches your Nord Smart DNS IPs — common after router or travel changes.",
    "health_score_low": "Security hub score falls below the threshold (VPN, leak tests, audit, traffic combined).",
    "security_audit": "Network audit finds a failed check — DNS, routes, IPv6, or related privacy items.",
    "wifi_untrusted": "You join a WiFi SSID that is not in your trusted zones — suggests a safer preset.",
}


def _default_rules() -> dict[str, bool]:
    return {
        "vpn_disconnect": True,
        "smart_dns_drift": True,
        "health_score_low": True,
        "security_audit": True,
        "wifi_untrusted": False,
        "test": True,
    }


def alerts_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ac = _alerts_cfg(cfg)
    email = ac.get("email") or {}
    webhook = ac.get("webhook") or {}
    return {
        "ok": True,
        "module_enabled": is_module_enabled_alerts(cfg),
        "browser_enabled": bool(ac.get("browser_enabled", True)),
        "email_enabled": bool(email.get("enabled")),
        "email_to": email.get("to") if email.get("enabled") else None,
        "webhook_enabled": bool(webhook.get("enabled")),
        "webhook_url_set": bool(webhook.get("url")),
        "rules": ac.get("rules") or _default_rules(),
        "rate_limit_minutes": int(ac.get("rate_limit_minutes") or 15),
        "watch_running": _watch_thread is not None and _watch_thread.is_alive(),
        "watch_enabled": bool(ac.get("watch_enabled", True)),
        "watch_interval_seconds": int(ac.get("watch_interval") or 60),
        "rule_descriptions": dict(RULE_DESCRIPTIONS),
        "privacy_note": "Alerts never leave your machine except email to YOUR address or webhook YOU configure.",
    }


def save_alerts_config(updates: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ac = cfg.setdefault("alerts", {})
    for key in ("browser_enabled", "rate_limit_minutes"):
        if key in updates:
            ac[key] = updates[key]
    if "rules" in updates and isinstance(updates["rules"], dict):
        ac["rules"] = {**_default_rules(), **(ac.get("rules") or {}), **updates["rules"]}
    if "email" in updates and isinstance(updates["email"], dict):
        em = ac.setdefault("email", {})
        for k, v in updates["email"].items():
            if k == "smtp_password" and v in ("", "••••", "***"):
                continue
            em[k] = v
    if "webhook" in updates and isinstance(updates["webhook"], dict):
        wh = ac.setdefault("webhook", {})
        wh.update(updates["webhook"])
    if "scan_email" in updates and isinstance(updates["scan_email"], dict):
        se = ac.setdefault("scan_email", {})
        for k, v in updates["scan_email"].items():
            se[k] = v
    save_config(cfg)
    return alerts_status(cfg)


def test_alerts(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    return fire_alert(
        "test",
        "nordctl test alert",
        "If you see this in the browser or inbox, alerts work. No data was sent anywhere else.",
        severity="info",
        cfg=cfg,
    )


def _check_conditions(cfg: dict[str, Any]) -> None:
    from nordctl import nordvpn as nv
    from nordctl import network_linux as net
    from nordctl.health_score import compute_health_score
    from nordctl.doctor import run_doctor
    from nordctl.leaklab import run_leaklab
    from nordctl.network_audit import run_network_audit
    from nordctl.service_mgr import service_overview
    from nordctl.traffic_watch import run_traffic_watch
    from nordctl.zones import zone_status

    ac = _alerts_cfg(cfg)
    rules = ac.get("rules") or {}
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    status: dict[str, Any] = {}
    if nv.available(bin_path):
        status = nv.parse_status(nv.run(bin_path, ["status"], timeout=8).get("output", ""))

    if rules.get("vpn_disconnect"):
        global _last_vpn_connected
        connected = bool(status.get("connected"))
        if _last_vpn_connected is True and not connected:
            fire_alert(
                "vpn_disconnect",
                "VPN disconnected",
                "NordVPN tunnel dropped. Reconnect from nordctl if unexpected.",
                cfg=cfg,
            )
        _last_vpn_connected = connected

    if rules.get("smart_dns_drift"):
        wifi = cfg.get("wifi") or {}
        sd = cfg.get("smart_dns") or {}
        drift = net.smart_dns_drift(
            list(wifi.get("profiles") or []),
            str(sd.get("primary") or ""),
            str(sd.get("secondary") or ""),
            device=wifi.get("device"),
        )
        if drift.get("drift"):
            fire_alert(
                "smart_dns_drift",
                "Smart DNS drift",
                drift.get("detail") or "WiFi DNS no longer matches Nord Smart DNS settings.",
                cfg=cfg,
            )

    if rules.get("health_score_low"):
        threshold = int(ac.get("health_threshold") or 50)
        doctor = run_doctor(cfg)
        leaklab = run_leaklab(cfg)
        audit = run_network_audit()
        services = service_overview(cfg)
        traffic = run_traffic_watch("internet")
        health = compute_health_score(
            doctor=doctor,
            leaklab=leaklab,
            audit=audit,
            status=status,
            services=services,
            traffic_summary=traffic.get("summary"),
        )
        score = int(health.get("score") or 100)
        if score < threshold:
            fire_alert(
                "health_score_low",
                f"Health score low ({score})",
                health.get("summary") or "Open Security tab for fixes.",
                cfg=cfg,
            )

    if rules.get("security_audit"):
        audit = run_network_audit()
        failed = [c for c in (audit.get("checks") or []) if not c.get("ok")]
        if failed:
            detail = str(failed[0].get("summary") or failed[0].get("id") or "See Audit tab")
            fire_alert(
                "security_audit",
                "Network audit found issues",
                detail if len(failed) == 1 else f"{len(failed)} checks failed — {detail}",
                cfg=cfg,
            )

    if rules.get("wifi_untrusted"):
        zs = zone_status(cfg)
        if zs.get("ssid") and not zs.get("is_trusted"):
            fire_alert(
                "wifi_untrusted",
                f"Untrusted WiFi — {zs.get('ssid')}",
                f"Suggested preset: {zs.get('suggested_preset')}. Consider public-wifi protection.",
                severity="info",
                cfg=cfg,
            )


def _watch_loop(interval: float) -> None:
    while not _watch_stop.is_set():
        cfg = load_config()
        if is_module_enabled_alerts(cfg) and _alerts_cfg(cfg).get("watch_enabled", True):
            try:
                _check_conditions(cfg)
            except Exception:
                pass
        _watch_stop.wait(interval)


def start_alerts_watch() -> dict[str, Any]:
    global _watch_thread
    if _watch_thread and _watch_thread.is_alive():
        return {"ok": True, "already_running": True, **alerts_status()}
    _watch_stop.clear()
    cfg = load_config()
    ac = cfg.setdefault("alerts", {})
    ac["watch_enabled"] = True
    save_config(cfg)
    interval = float(ac.get("watch_interval") or 60)
    _watch_thread = threading.Thread(target=_watch_loop, args=(interval,), name="nordctl-alerts", daemon=True)
    _watch_thread.start()
    return {"ok": True, "started": True, **alerts_status()}


def stop_alerts_watch() -> dict[str, Any]:
    _watch_stop.set()
    cfg = load_config()
    ac = cfg.setdefault("alerts", {})
    ac["watch_enabled"] = False
    save_config(cfg)
    return {"ok": True, "stopped": True, **alerts_status()}


def connection_journal(limit: int = 30) -> dict[str, Any]:
    """Tier 5 — local preset journal (structured JSONL)."""
    from nordctl.connection_journal import list_journal

    return list_journal(limit=limit)


def privacy_report_export() -> dict[str, Any]:
    """Tier 5 — export privacy + module status as local JSON file."""
    from nordctl.privacy import privacy_manifest
    from nordctl.features import features_payload

    cfg = load_config()
    report = {
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "privacy": privacy_manifest(cfg),
        "features": features_payload(cfg),
        "alerts": alerts_status(cfg),
    }
    out = config_dir() / "exports"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"privacy-report-{time.strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"ok": True, "path": str(path)}


def smart_recommendations(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Tier 6 — local preset suggestions from doctors (no ML, no cloud)."""
    cfg = cfg or load_config()
    from nordctl.wifi_doctor import run_all_wifi_hub_doctors
    from nordctl.zones import zone_status

    docs = run_all_wifi_hub_doctors(cfg)
    zs = zone_status(cfg)
    recs: list[dict[str, str]] = []
    if docs.get("blocking_count", 0) > 0:
        recs.append({"preset": "restore-defaults", "reason": "Fix critical doctor issues first, then retry"})
    if zs.get("ssid") and not zs.get("is_trusted"):
        recs.append({"preset": str(zs.get("suggested_preset") or "public-wifi"), "reason": f"Untrusted network {zs.get('ssid')}"})
    elif zs.get("is_trusted"):
        recs.append({"preset": str(zs.get("suggested_preset") or "streaming-smartdns"), "reason": "Trusted home WiFi"})
    if not recs:
        recs.append({"preset": "full-vpn", "reason": "General privacy when unsure"})
    return {"ok": True, "recommendations": recs[:5], "note": "Computed locally from zone + doctor status"}
