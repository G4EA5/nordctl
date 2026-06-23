"""Manage NordVPN allowlist (split tunnel) via CLI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from typing import Any

from nordctl import nordvpn as nv
from nordctl.config import load_config

# Known ports — used for on-page explanations (voip-friendly preset / config voip_ports).
PORT_HINTS: dict[int, str] = {
    53: "DNS — local resolver (Pi-hole, router, Unbound) when split tunnel should reach LAN DNS.",
    80: "HTTP — plain web; often allowlisted for captive portals and local HTTP services.",
    443: "HTTPS — secure web and many encrypted apps.",
    4244: "VoIP / messaging — common for Viber and similar voice/chat apps.",
    5242: "VoIP / messaging — peer connection setup (call signaling).",
    5243: "VoIP / messaging — peer media channel (call audio/video).",
    5643: "TCP allowlist — often added manually or by a third-party preset.",
    7985: "UDP voice/chat — used by several messaging and gaming apps.",
}


def _port_numbers_from_line(raw: str) -> list[int]:
    """Parse Nord lines like ``80 (UDP|TCP)`` or ``5242 - 5243 (UDP|TCP)``."""
    s = str(raw or "").strip()
    if not s:
        return []
    head = s.split("(", 1)[0].strip()
    nums: list[int] = []
    for part in re.split(r"\s*-\s*|\s+", head):
        part = part.strip()
        if part.isdigit():
            nums.append(int(part))
    return nums


def _protocols_from_line(raw: str) -> str:
    m = re.search(r"\(([^)]+)\)\s*$", str(raw or "").strip())
    return m.group(1).strip() if m else ""


def describe_port_entry(raw: str, voip_ports: list[Any]) -> dict[str, Any]:
    nums = _port_numbers_from_line(raw)
    voip_set = {int(p) for p in voip_ports if str(p).strip().isdigit()}
    hints: list[str] = []
    for n in nums:
        label = PORT_HINTS.get(n, "Custom allowlist — traffic on this port can bypass the VPN tunnel.")
        hints.append(f"{n}: {label}")
    from_voip = bool(nums) and all(n in voip_set for n in nums)
    partial_voip = bool(nums) and any(n in voip_set for n in nums) and not from_voip
    if from_voip:
        source = "voip_ports preset"
    elif partial_voip:
        source = "preset + custom"
    else:
        source = "Nord allowlist"
    return {
        "raw": raw,
        "ports": nums,
        "protocols": _protocols_from_line(raw),
        "summary": "; ".join(hints),
        "from_voip_config": from_voip,
        "partial_voip_config": partial_voip,
        "source": source,
    }


def get_allowlist(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    r = nv.run(bin_path, ["settings"], timeout=10)
    settings = nv.parse_settings(r.get("output", ""))
    ports = settings.get("allowlisted_ports") or []
    voip_ports = list(cfg.get("voip_ports") or [])
    port_details = [describe_port_entry(line, voip_ports) for line in ports]
    return {
        "ok": r.get("ok", False),
        "ports": ports,
        "port_details": port_details,
        "port_count": len(ports),
        "voip_ports_config": voip_ports,
        "subnets": settings.get("allowlisted_subnets") or [],
        "subnet_count": len(settings.get("allowlisted_subnets") or []),
        "config_subnets": list(cfg.get("allowlist_subnets") or []),
        "lan_cidr": cfg.get("lan_allowlist_cidr"),
        "metric_note": (
            "Counts rules stored in NordVPN right now (from presets, Add port below, or nordvpn allowlist CLI) — "
            "not empty form fields."
        ),
    }


def add_subnet(cidr: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    cidr = cidr.strip()
    if not cidr:
        return {"ok": False, "error": "cidr required"}
    r = nv.run(bin_path, ["allowlist", "add", "subnet", cidr], timeout=15)
    return {"ok": r["ok"], "result": r}


def remove_subnet(cidr: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    r = nv.run(bin_path, ["allowlist", "remove", "subnet", cidr.strip()], timeout=15)
    return {"ok": r["ok"], "result": r}


def add_port(port: int, protocol: str = "TCP", cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    r = nv.run(
        bin_path,
        ["allowlist", "add", "port", str(port), "protocol", protocol.upper()],
        timeout=15,
    )
    return {"ok": r["ok"], "result": r}


def apply_lan_from_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    cidr = str(cfg.get("lan_allowlist_cidr") or "").strip()
    if not cidr:
        return {"ok": False, "error": "lan_allowlist_cidr not set"}
    return add_subnet(cidr, cfg)


def remove_lan_from_config(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    cidr = str(cfg.get("lan_allowlist_cidr") or "").strip()
    if not cidr:
        return {"ok": False, "error": "lan_allowlist_cidr not set"}
    r = remove_subnet(cidr, cfg)
    return {**r, "note": f"Removed LAN allowlist {cidr}"}
