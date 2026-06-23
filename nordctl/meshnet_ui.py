"""Meshnet peer parsing and actions."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any

from nordctl import nordvpn as nv
from nordctl.config import load_config


def parse_peers(raw: str) -> list[dict[str, str]]:
    peers: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            if current:
                peers.append(current)
                current = {}
            continue
        if ":" in line:
            k, v = line.split(":", 1)
            current[k.strip().lower()] = v.strip()
    if current:
        peers.append(current)
    # Fallback: hostname-like tokens
    if not peers:
        for m in re.finditer(r"([a-z0-9][a-z0-9.-]+\.nord)", raw, re.I):
            peers.append({"hostname": m.group(1), "name": m.group(1)})
    return [p for p in peers if str(p.get("hostname") or "").lower().endswith(".nord")]


def meshnet_state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    peers_r = nv.run_cached(bin_path, ["meshnet", "peer", "list"], timeout=12)
    settings_r = nv.run_cached(bin_path, ["settings"], timeout=8)
    settings = nv.parse_settings(settings_r.get("output", ""))
    status_r = nv.run_cached(bin_path, ["status"], timeout=8)
    status = nv.parse_status(status_r.get("output", "")) if status_r.get("ok") else {}
    raw = peers_r.get("output", "")
    peers = parse_peers(raw)
    return {
        "ok": peers_r.get("ok", False),
        "mesh_ip": nv.mesh_ip(),
        "meshnet_enabled": "enabled" in str(settings.get("Meshnet", "")).lower(),
        "vpn_connected": bool(status.get("connected")),
        "vpn_country": str(status.get("Country") or status.get("country") or ""),
        "lan_discovery": str(settings.get("LAN discovery") or settings.get("lan-discovery") or ""),
        "routing": str(settings.get("Routing") or settings.get("routing") or ""),
        "peers": peers,
        "peer_count": len(peers),
        "raw": raw,
        "configured_peer": cfg.get("mesh_peer"),
    }


def set_meshnet(enabled: bool, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if not nv.available(bin_path):
        return {"ok": False, "error": "Install NordVPN first"}
    val = "on" if enabled else "off"
    r = nv.run(bin_path, ["set", "meshnet", val], timeout=20)
    return {"ok": r["ok"], "result": r, "note": f"Meshnet {val}"}


def connect_peer(peer: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    target = peer.strip() or str(cfg.get("mesh_peer") or "")
    if not target:
        return {"ok": False, "error": "peer hostname required"}
    r = nv.run(bin_path, ["meshnet", "peer", "connect", target], timeout=60)
    return {"ok": r["ok"], "result": r}
