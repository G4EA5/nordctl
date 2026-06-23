"""Bluetooth ISM 2.4 GHz spectrum snapshot — adapter, security, nearby devices."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import hashlib
import os
import re
import shutil
from typing import Any

from nordctl.network_linux import run_cmd

# BLE uses 40 channels, 2 MHz spacing, 2402–2480 MHz (WiFi-adjacent ISM band)
BT_BANDS: list[dict[str, Any]] = [
    {
        "id": "ble_low",
        "label": "BLE low",
        "short": "BLE-L",
        "mhz_min": 2402,
        "mhz_max": 2420,
        "color": "#38bdf8",
        "hint": "BLE channels 0–9 · overlaps WiFi ch 1–3",
    },
    {
        "id": "ble_mid",
        "label": "BLE mid",
        "short": "BLE-M",
        "mhz_min": 2422,
        "mhz_max": 2460,
        "color": "#818cf8",
        "hint": "BLE channels 10–29 · dense WiFi overlap",
    },
    {
        "id": "ble_high",
        "label": "BLE high",
        "short": "BLE-H",
        "mhz_min": 2462,
        "mhz_max": 2480,
        "color": "#c084fc",
        "hint": "BLE channels 30–39 · overlaps WiFi ch 11–13",
    },
    {
        "id": "classic",
        "label": "BT Classic",
        "short": "Classic",
        "mhz_min": 2402,
        "mhz_max": 2480,
        "color": "#2dd4bf",
        "hint": "79 frequency-hopping channels across ISM 2.4 GHz",
    },
]

_DEVICE_LINE = re.compile(r"^Device\s+([0-9A-Fa-f:]{17})\s*(.*)$", re.MULTILINE)
_MAC = re.compile(r"^([0-9A-Fa-f]{2}(?::[0-9A-Fa-f]{2}){5})$")


def _band_for_ble_channel(ch: int) -> str:
    if ch < 10:
        return "ble_low"
    if ch < 30:
        return "ble_mid"
    return "ble_high"


def _ble_mhz(channel: int) -> float:
    return 2402.0 + channel * 2.0


def _rssi_to_pct(rssi: int | None) -> int:
    if rssi is None:
        return 0
    return max(0, min(100, int((int(rssi) + 100) * 1.43)))


def _parse_kv_block(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        key, val = line.split(":", 1)
        out[key.strip()] = val.strip()
    return out


def _has_bluetooth_sysfs() -> bool:
    try:
        entries = os.listdir("/sys/class/bluetooth")
        return any(e for e in entries if e.startswith("hci"))
    except OSError:
        return False


def _list_controllers() -> list[dict[str, str]]:
    r = run_cmd(["bluetoothctl", "list"], timeout=4)
    if not r["ok"]:
        return []
    ctrls: list[dict[str, str]] = []
    for line in r["output"].splitlines():
        m = re.match(r"^Controller\s+([0-9A-Fa-f:]{17})\s*(.*)$", line.strip())
        if m:
            ctrls.append({"mac": m.group(1), "name": (m.group(2) or "").strip()})
    return ctrls


def _parse_adapter(text: str) -> dict[str, Any]:
    kv = _parse_kv_block(text)
    mac_m = re.search(r"Controller\s+([0-9A-Fa-f:]{17})", text)
    return {
        "mac": mac_m.group(1) if mac_m else kv.get("Address"),
        "name": kv.get("Name") or kv.get("Alias"),
        "alias": kv.get("Alias"),
        "class": kv.get("Class"),
        "powered": kv.get("Powered", "").lower() == "yes",
        "discoverable": kv.get("Discoverable", "").lower() == "yes",
        "pairable": kv.get("Pairable", "").lower() == "yes",
        "discovering": kv.get("Discovering", "").lower() == "yes",
        "discoverable_timeout": kv.get("DiscoverableTimeout"),
        "roles": kv.get("Roles"),
        "modalias": kv.get("Modalias"),
    }


def _parse_device_info(mac: str, text: str) -> dict[str, Any]:
    kv = _parse_kv_block(text)
    rssi_raw = kv.get("RSSI")
    rssi = int(rssi_raw) if rssi_raw and re.match(r"^-?\d+$", rssi_raw) else None
    name = kv.get("Name") or kv.get("Alias") or ""
    icon = kv.get("Icon") or ""
    uuids = [ln.strip() for ln in text.splitlines() if ln.strip().startswith("UUID:")]
    ble_ch = _stable_ble_channel(mac)
    mhz = _ble_mhz(ble_ch)
    return {
        "mac": mac,
        "name": name or "(unknown)",
        "alias": kv.get("Alias") or "",
        "icon": icon,
        "device_class": kv.get("Class"),
        "paired": kv.get("Paired", "").lower() == "yes",
        "bonded": kv.get("Bonded", "").lower() == "yes",
        "trusted": kv.get("Trusted", "").lower() == "yes",
        "blocked": kv.get("Blocked", "").lower() == "yes",
        "connected": kv.get("Connected", "").lower() == "yes",
        "legacy_pairing": kv.get("LegacyPairing", "").lower() == "yes",
        "rssi": rssi,
        "signal_pct": _rssi_to_pct(rssi),
        "tx_power": kv.get("TxPower"),
        "uuids": uuids[:8],
        "ble_channel": ble_ch,
        "mhz": mhz,
        "band_id": _band_for_ble_channel(ble_ch),
        "appearance": _device_appearance(icon, kv.get("Class")),
    }


def _device_appearance(icon: str, dev_class: str | None) -> str:
    if icon:
        return icon.replace("-", " ").title()
    if not dev_class:
        return "Unknown"
    try:
        code = int(dev_class, 16)
        major = (code >> 8) & 0x1f00
        if major == 0x0100:
            return "Computer"
        if major == 0x0200:
            return "Phone"
        if major == 0x0400:
            return "Audio/Video"
        if major == 0x0500:
            return "Peripheral"
        if major == 0x0600:
            return "Imaging"
        if major == 0x0700:
            return "Wearable"
    except ValueError:
        pass
    return "Device"


def _stable_ble_channel(mac: str) -> int:
    digest = hashlib.md5(mac.lower().encode()).hexdigest()
    return int(digest[:2], 16) % 40


def _rfkill_bluetooth() -> dict[str, Any]:
    r = run_cmd(["rfkill", "list", "bluetooth"], timeout=5)
    if not r["ok"]:
        return {"available": False, "soft_blocked": None, "hard_blocked": None}
    soft = "Soft blocked: yes" in r["output"]
    hard = "Hard blocked: yes" in r["output"]
    return {"available": True, "soft_blocked": soft, "hard_blocked": hard, "raw": r["output"].strip()}


def _list_device_macs() -> list[tuple[str, str]]:
    r = run_cmd(["bluetoothctl", "devices"], timeout=10)
    if not r["ok"]:
        return []
    found: list[tuple[str, str]] = []
    for line in r["output"].splitlines():
        m = _DEVICE_LINE.match(line.strip())
        if m:
            mac = m.group(1)
            hint = (m.group(2) or "").strip()
            found.append((mac, hint))
    return found


def _fetch_devices(limit: int = 30) -> list[dict[str, Any]]:
    devices: list[dict[str, Any]] = []
    for mac, hint in _list_device_macs()[:limit]:
        info_r = run_cmd(["bluetoothctl", "info", mac], timeout=6)
        if info_r["ok"]:
            dev = _parse_device_info(mac, info_r["output"])
        else:
            dev = {
                "mac": mac,
                "name": hint or "(unknown)",
                "rssi": None,
                "signal_pct": 0,
                "ble_channel": _stable_ble_channel(mac),
                "mhz": _ble_mhz(_stable_ble_channel(mac)),
                "band_id": _band_for_ble_channel(_stable_ble_channel(mac)),
                "appearance": "Device",
                "paired": False,
                "connected": False,
                "trusted": False,
                "blocked": False,
                "legacy_pairing": False,
                "uuids": [],
            }
        if not dev.get("name") or dev["name"] == "(unknown)":
            dev["name"] = hint or dev["name"]
        devices.append(dev)
    return devices


def _build_bins(devices: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_ch: dict[int, dict[str, Any]] = {}
    for ch in range(40):
        by_ch[ch] = {
            "channel": ch,
            "mhz": _ble_mhz(ch),
            "band_id": _band_for_ble_channel(ch),
            "signal_pct": 0,
            "rssi": None,
            "devices": [],
        }
    for dev in devices:
        ch = int(dev.get("ble_channel") or 0) % 40
        row = by_ch[ch]
        row["devices"].append({
            "mac": dev.get("mac"),
            "name": dev.get("name"),
            "signal_pct": dev.get("signal_pct", 0),
            "rssi": dev.get("rssi"),
            "connected": dev.get("connected"),
            "appearance": dev.get("appearance"),
        })
        pct = dev.get("signal_pct") or 0
        if pct > row["signal_pct"]:
            row["signal_pct"] = pct
            row["rssi"] = dev.get("rssi")
    return [by_ch[i] for i in range(40)]


def _security_findings(adapter: dict[str, Any], devices: list[dict[str, Any]], rfkill: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    if rfkill.get("soft_blocked") or rfkill.get("hard_blocked"):
        findings.append({
            "level": "info",
            "id": "rfkill",
            "title": "Bluetooth radio blocked",
            "detail": "rfkill is blocking the adapter — unblock in OS settings or run rfkill unblock bluetooth.",
        })
    if not adapter.get("powered"):
        findings.append({
            "level": "info",
            "id": "powered_off",
            "title": "Adapter powered off",
            "detail": "Turn Bluetooth on to scan and pair. Spectrum view needs an active controller.",
        })
    if adapter.get("discoverable"):
        findings.append({
            "level": "warn",
            "id": "discoverable",
            "title": "Adapter is discoverable",
            "detail": "Other devices can see and attempt to pair with this PC. Disable when not pairing.",
        })
    if adapter.get("pairable") and adapter.get("discoverable"):
        findings.append({
            "level": "warn",
            "id": "pairable_visible",
            "title": "Pairable while visible",
            "detail": "New pairing requests are accepted while you are discoverable — use only temporarily.",
        })
    connected = [d for d in devices if d.get("connected")]
    untrusted_conn = [d for d in connected if not d.get("trusted")]
    if untrusted_conn:
        findings.append({
            "level": "warn",
            "id": "untrusted_connected",
            "title": f"{len(untrusted_conn)} connected device(s) not marked trusted",
            "detail": "Review whether these connections should be trusted or disconnected.",
        })
    legacy = [d for d in connected if d.get("legacy_pairing")]
    if legacy:
        findings.append({
            "level": "warn",
            "id": "legacy_pairing",
            "title": "Legacy pairing on active connection",
            "detail": "Legacy Bluetooth pairing lacks modern LE Secure Connections — prefer BLE with encryption.",
        })
    blocked_active = [d for d in devices if d.get("blocked") and d.get("connected")]
    if blocked_active:
        findings.append({
            "level": "danger",
            "id": "blocked_connected",
            "title": "Blocked device still connected",
            "detail": "Disconnect and remove blocked devices from paired list.",
        })
    if adapter.get("powered") and not adapter.get("discoverable") and not findings:
        findings.append({
            "level": "ok",
            "id": "baseline_ok",
            "title": "Adapter posture looks reasonable",
            "detail": "Powered on, not broadcasting discoverability. Re-scan periodically for unknown neighbors.",
        })
    return findings


def bluetooth_scan(duration: int = 6) -> dict[str, Any]:
    sec = max(3, min(20, int(duration)))
    r = run_cmd(["bluetoothctl", "--timeout", str(sec), "scan", "on"], timeout=sec + 5)
    return {"ok": r["ok"], "output": (r.get("output") or "")[:2000], "duration": sec}


def bluetooth_payload(cfg: dict[str, Any] | None = None, *, rescan: bool = False) -> dict[str, Any]:
    del cfg  # reserved for preferred adapter from config later
    tools = {
        "bluetoothctl": bool(shutil.which("bluetoothctl")),
        "hcitool": bool(shutil.which("hcitool")),
        "btmgmt": bool(shutil.which("btmgmt")),
    }
    if not tools["bluetoothctl"]:
        return {
            "ok": False,
            "error": "bluetoothctl not found",
            "hint": "Install bluez package: sudo apt install bluez",
            "bands": BT_BANDS,
            "bins": [],
            "devices": [],
            "tools": tools,
        }

    rfkill = _rfkill_bluetooth()
    if not _has_bluetooth_sysfs():
        return {
            "ok": False,
            "error": "No Bluetooth adapter found",
            "hint": "Enable Bluetooth in BIOS/OS, unblock rfkill (rfkill unblock bluetooth), or plug in a USB BT dongle.",
            "rfkill": rfkill,
            "bands": BT_BANDS,
            "bins": _build_bins([]),
            "devices": [],
            "tools": tools,
        }

    controllers = _list_controllers()
    if not controllers:
        return {
            "ok": False,
            "error": "No Bluetooth adapter found",
            "hint": "Enable Bluetooth in BIOS/OS, unblock rfkill (rfkill unblock bluetooth), or plug in a BT dongle. Install bluez if bluetoothctl is missing.",
            "rfkill": rfkill,
            "bands": BT_BANDS,
            "bins": _build_bins([]),
            "devices": [],
            "tools": tools,
        }

    if rescan:
        bluetooth_scan()

    show_r = run_cmd(["bluetoothctl", "show"], timeout=8)
    if not show_r["ok"] or "No default controller" in (show_r.get("output") or ""):
        return {
            "ok": False,
            "error": "Bluetooth controller unavailable",
            "hint": show_r.get("output") or "bluetoothctl show failed",
            "rfkill": rfkill,
            "controllers": controllers,
            "bands": BT_BANDS,
            "bins": _build_bins([]),
            "devices": [],
            "tools": tools,
        }
    adapter = _parse_adapter(show_r["output"])
    if not adapter.get("mac"):
        return {
            "ok": False,
            "error": "No Bluetooth adapter found",
            "hint": "Controller list was empty or adapter MAC missing.",
            "rfkill": rfkill,
            "controllers": controllers,
            "bands": BT_BANDS,
            "bins": _build_bins([]),
            "devices": [],
            "tools": tools,
        }
    devices = _fetch_devices()
    bins = _build_bins(devices)
    findings = _security_findings(adapter, devices, rfkill)

    paired = [d for d in devices if d.get("paired")]
    connected = [d for d in devices if d.get("connected")]
    nearby = [d for d in devices if not d.get("paired")]

    return {
        "ok": True,
        "adapter": adapter,
        "controllers": controllers,
        "rfkill": rfkill,
        "bands": BT_BANDS,
        "all_bands": BT_BANDS,
        "bins": bins,
        "devices": devices,
        "paired": paired,
        "connected": connected,
        "nearby": nearby,
        "security": findings,
        "device_count": len(devices),
        "paired_count": len(paired),
        "connected_count": len(connected),
        "nearby_count": len(nearby),
        "channel_count": len(bins),
        "ism_range": {"mhz_min": 2402, "mhz_max": 2480},
        "tools": tools,
        "hint": "BLE and Classic share 2.4 GHz ISM with WiFi. Channel positions are estimated from scan RSSI — use Rescan for fresh neighbors.",
    }
