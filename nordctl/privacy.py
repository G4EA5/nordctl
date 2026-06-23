"""Privacy & safety manifest — what nordctl does NOT collect or transmit."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.config import config_dir, config_path, load_config


def privacy_manifest(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    srv = cfg.get("server") or {}
    alerts = cfg.get("alerts") or {}
    email = alerts.get("email") or {}
    bind = str(srv.get("bind") or "127.0.0.1")
    from nordctl.network_access import network_access_payload

    na = network_access_payload(cfg)
    loopback_only = bool(na.get("loopback_only"))
    local_lines = [
        "All config and logs stay under ~/.config/nordctl/ on your machine.",
        (
            "Web UI listens on loopback only — other devices on your network cannot open the dashboard."
            if loopback_only
            else "Web UI is reachable on your home LAN (192.168.x, 10.x, …) — anyone on that network can use it. "
            "Switch back to local-only in Advanced → Services → Network access."
        ),
        "Activity log is plain text on disk — never uploaded by nordctl.",
        "Smart DNS public-IP check uses only the URL you configure (optional).",
    ]
    return {
        "ok": True,
        "summary": "nordctl is local-first open source (MIT). No analytics, accounts, or vendor telemetry.",
        "local_only": local_lines,
        "never_collected": [
            "NordVPN account credentials or session tokens",
            "Browsing history or packet contents",
            "WiFi passwords",
            "Email contents (alerts only send what you configure, to your address only)",
        ],
        "user_controlled_outbound": [
            {
                "id": "email_alerts",
                "enabled": bool(email.get("enabled")),
                "description": "Optional SMTP — only to your configured To address via your mail server.",
                "data_sent": "Alert title and short message you define — no hidden fields.",
            },
            {
                "id": "public_ip_check",
                "url": str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip"),
                "description": "Optional WAN IP echo for Smart DNS allowlist display.",
            },
            {
                "id": "speedtest",
                "description": "Optional curl download to Cloudflare/OVH test endpoints when you click Run.",
            },
            {
                "id": "leak_test_links",
                "description": "External test URLs open in your browser only when you click them.",
            },
            {
                "id": "webhook",
                "enabled": bool((alerts.get("webhook") or {}).get("enabled")),
                "description": "Tier 6 optional — POST JSON to a URL you own. Disabled by default.",
            },
        ],
        "safe_defaults": {
            "server_bind": bind,
            "loopback_only": loopback_only,
            "lan_enabled": bool(na.get("lan_enabled")),
            "status_page_token": "Random token — share URL only on trusted LAN if enabled.",
        },
        "paths": {
            "config": str(config_path()),
            "config_dir": str(config_dir()),
        },
        "open_source": {
            "license": "MIT",
            "source_id": __import__("nordctl.provenance", fromlist=["SOURCE_ID"]).SOURCE_ID,
            "notice": "100% open source — inspect, fork, and audit the code. Not affiliated with Nord Security.",
        },
        "legal": {
            "disclaimer": "Use nordctl only in compliance with local law and NordVPN / streaming service terms.",
            "doc": "LEGAL.md",
        },
    }
