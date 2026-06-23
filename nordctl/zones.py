"""WiFi zone detection and auto-preset triggers."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import subprocess
from typing import Any

from nordctl.config import load_config


def current_ssid() -> str | None:
    try:
        r = subprocess.run(
            ["nmcli", "-t", "-f", "active,ssid", "dev", "wifi"],
            capture_output=True,
            text=True,
            timeout=8,
        )
        for line in (r.stdout or "").splitlines():
            parts = line.split(":")
            if len(parts) >= 2 and parts[0] == "yes":
                ssid = parts[1].strip()
                if ssid:
                    return ssid
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def zone_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    zones = cfg.get("wifi_zones") or {}
    ssid = current_ssid()
    trusted = zones.get("trusted") or []
    untrusted_preset = zones.get("untrusted_preset") or zones.get("untrusted", {}).get("preset")

    matched = None
    for entry in trusted:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("ssid") or "") == ssid:
            matched = entry
            break

    return {
        "ssid": ssid,
        "trusted_match": matched,
        "suggested_preset": matched.get("preset") if matched else untrusted_preset,
        "is_trusted": matched is not None,
        "auto_apply_enabled": bool(zones.get("auto_apply")),
    }


def maybe_auto_apply(cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    cfg = cfg or load_config()
    zones = cfg.get("wifi_zones") or {}
    if not zones.get("auto_apply"):
        return None
    st = zone_status(cfg)
    preset = st.get("suggested_preset")
    if not preset or not st.get("ssid"):
        return None
    from nordctl.presets import apply_preset

    return apply_preset(str(preset), cfg)
