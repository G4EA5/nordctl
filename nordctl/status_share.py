"""Read-only LAN status page + config export."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import secrets
import tarfile
import time
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, config_path, load_config, save_config


def _ensure_token(cfg: dict[str, Any]) -> str:
    sec = cfg.setdefault("security", {})
    sp = sec.setdefault("status_page", {})
    token = str(sp.get("token") or "").strip()
    if not token:
        token = secrets.token_urlsafe(16)
        sp["token"] = token
        sp["enabled"] = bool(sp.get("enabled", False))
        save_config(cfg)
    return token


def status_page_info(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sec = cfg.get("security") or {}
    sp = sec.get("status_page") or {}
    srv = cfg.get("server") or {}
    host = str(srv.get("bind") or "127.0.0.1")
    port = int(srv.get("port") or 8765)
    token = _ensure_token(cfg)
    if host in ("127.0.0.1", "localhost"):
        url = f"http://127.0.0.1:{port}/status/{token}"
        lan_note = "Bind server to 0.0.0.0 only on trusted LAN if phone access needed."
    else:
        url = f"http://{host}:{port}/status/{token}"
        lan_note = "Share this URL only on your home network."
    return {
        "enabled": bool(sp.get("enabled")),
        "token": token,
        "url": url,
        "lan_note": lan_note,
        "hint": "Read-only VPN status for phone/tablet on same WiFi.",
    }


def set_status_page_enabled(enabled: bool, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    sec = cfg.setdefault("security", {})
    sp = sec.setdefault("status_page", {})
    sp["enabled"] = bool(enabled)
    _ensure_token(cfg)
    save_config(cfg)
    return {"ok": True, **status_page_info(cfg)}


def export_config_bundle() -> dict[str, Any]:
    from nordctl.config_bundle import export_config_bundle as _export

    return _export()


def export_logs_text(*, limit: int = 200) -> dict[str, Any]:
    from nordctl.activity_log import list_entries

    entries = list_entries(limit=limit)
    lines: list[str] = []
    for e in entries:
        mark = "OK" if e.get("ok", True) else "FAIL"
        lines.append(f"[{e.get('ts', '?')}] [{mark}] {e.get('title', '')}")
        if e.get("detail"):
            lines.append(f"  {e.get('detail')}")
    text = "\n".join(lines) if lines else "No log entries yet."
    out = config_dir() / "exports"
    out.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d-%H%M%S")
    path = out / f"nordctl-logs-{ts}.txt"
    try:
        path.write_text(text, encoding="utf-8")
    except OSError as exc:
        return {"ok": False, "error": str(exc)}
    return {
        "ok": True,
        "path": str(path),
        "lines": len(entries),
        "note": "Plain-English activity log — safe to share (no Nord account secrets).",
    }


def homeassistant_guide(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    srv = cfg.get("server") or {}
    port = int(srv.get("port") or 8765)
    base = f"http://127.0.0.1:{port}"
    yaml_snippet = f"""# configuration.yaml — REST sensors
rest:
  - resource: {base}/api/ha/state
    scan_interval: 60
    sensor:
      - name: NordVPN Connected
        value_template: "{{{{ value_json.vpn_connected }}}}"
      - name: NordVPN Public IP
        value_template: "{{{{ value_json.public_ip }}}}"
      - name: Nord Smart DNS Active
        value_template: "{{{{ value_json.smart_dns_active }}}}"
"""
    return {
        "ok": True,
        "endpoint": f"{base}/api/ha/state",
        "aliases": [f"{base}/api/homeassistant"],
        "fields": ["vpn_connected", "smart_dns_active", "public_ip", "mesh_ip", "country"],
        "yaml_snippet": yaml_snippet,
        "mqtt_hint": "Use HA REST-to-MQTT or Node-RED — nordctl does not run MQTT broker.",
    }


def render_status_page(token: str) -> tuple[int, str]:
    """Return (http_code, html) for read-only mobile status."""
    cfg = load_config()
    sp = (cfg.get("security") or {}).get("status_page") or {}
    if not sp.get("enabled"):
        return 403, "<html><body><h1>Status page disabled</h1><p>Enable in nordctl Security tab.</p></body></html>"
    if token != str(sp.get("token") or ""):
        return 404, "<html><body><h1>Not found</h1></body></html>"
    from nordctl.state import build_state

    st = build_state(cfg)
    status = st.get("status") or {}
    sd = st.get("smart_dns") or {}
    health = (st.get("security_hub") or {}).get("health") if isinstance(st.get("security_hub"), dict) else {}
    if not health:
        from nordctl.security_hub import security_hub_payload

        health = security_hub_payload(cfg).get("health") or {}
    vpn = "Connected" if status.get("connected") else "Disconnected"
    country = status.get("Country") or "—"
    ip = status.get("IP") or sd.get("public_ip") or "—"
    score = health.get("score", "—")
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>nordctl status</title><style>body{{font-family:system-ui;background:#0f1419;color:#e7ecf3;padding:1rem;}}
.card{{background:#1a2332;border-radius:12px;padding:1rem;margin:0.5rem 0;}}</style></head><body>
<h1>🛡️ nordctl</h1><div class="card"><strong>VPN:</strong> {vpn}<br><strong>Country:</strong> {country}<br><strong>IP:</strong> {ip}</div>
<div class="card"><strong>Health score:</strong> {score}/100<br>{health.get('summary','')}</div>
<p style="color:#888;font-size:0.85rem">Read-only · refreshes on reload</p></body></html>"""
    return 200, html
