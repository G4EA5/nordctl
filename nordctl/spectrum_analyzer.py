"""WiFi spectrum snapshot from iw + NetworkManager scan."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import shutil
from typing import Any

from nordctl.network_linux import detect_wifi_device, run_cmd, split_nmcli_terse

# Regulatory / WiFi band groups — toggled in the UI
SPECTRUM_BANDS: list[dict[str, Any]] = [
    {
        "id": "2g",
        "label": "2.4 GHz",
        "short": "2.4G",
        "mhz_min": 2400,
        "mhz_max": 2500,
        "color": "#22d3ee",
        "hint": "Channels 1–14 · longest range, most crowded",
    },
    {
        "id": "5g_unii1",
        "label": "5 GHz UNII-1",
        "short": "5G-L",
        "mhz_min": 5150,
        "mhz_max": 5250,
        "color": "#4ade80",
        "hint": "Indoor low band · ch 36–48",
    },
    {
        "id": "5g_unii2",
        "label": "5 GHz UNII-2",
        "short": "5G-M",
        "mhz_min": 5250,
        "mhz_max": 5350,
        "color": "#a3e635",
        "hint": "Mid 5 GHz · ch 52–64",
    },
    {
        "id": "5g_dfs",
        "label": "5 GHz DFS",
        "short": "DFS",
        "mhz_min": 5470,
        "mhz_max": 5725,
        "color": "#fbbf24",
        "hint": "Radar-sensitive · ch 100–140",
    },
    {
        "id": "5g_unii3",
        "label": "5 GHz UNII-3",
        "short": "5G-H",
        "mhz_min": 5725,
        "mhz_max": 5850,
        "color": "#fb923c",
        "hint": "High 5 GHz · ch 149–165",
    },
    {
        "id": "6g",
        "label": "6 GHz",
        "short": "6G",
        "mhz_min": 5925,
        "mhz_max": 7125,
        "color": "#c084fc",
        "hint": "WiFi 6E/7 · only if your adapter supports it",
    },
]

_FREQ_LINE = re.compile(
    r"^\s*\*?\s*(\d+(?:\.\d+)?)\s*MHz\s*\[(\d+)\]\s*(?:\(([^)]+)\))?",
    re.IGNORECASE,
)
_LINK_FREQ = re.compile(r"^\s*freq:\s*(\d+(?:\.\d+)?)", re.IGNORECASE)
_LINK_SSID = re.compile(r"^\s*SSID:\s*(.+)", re.IGNORECASE)
_LINK_SIGNAL = re.compile(r"^\s*signal:\s*(-?\d+)", re.IGNORECASE)


def _band_for_mhz(mhz: float) -> str | None:
    for band in SPECTRUM_BANDS:
        if band["mhz_min"] <= mhz < band["mhz_max"]:
            return str(band["id"])
    return None


def _nm_signal_to_dbm(signal_pct: int) -> int:
    """Approximate dBm from NetworkManager 0–100 scale."""
    s = max(0, min(100, int(signal_pct)))
    return -90 + int(s * 0.55)


def _parse_phy_frequencies(phy_text: str) -> list[dict[str, Any]]:
    channels: list[dict[str, Any]] = []
    for line in phy_text.splitlines():
        m = _FREQ_LINE.match(line)
        if not m:
            continue
        mhz = float(m.group(1))
        ch = int(m.group(2))
        flags = (m.group(3) or "").lower()
        disabled = "disabled" in flags or "no ir" in flags
        band_id = _band_for_mhz(mhz)
        channels.append({
            "mhz": round(mhz, 1),
            "channel": ch,
            "band_id": band_id,
            "disabled": disabled,
            "tx_power": flags or None,
        })
    return channels


def _parse_nm_scan(device: str) -> list[dict[str, Any]]:
    r = run_cmd(
        [
            "nmcli",
            "-t",
            "-f",
            "IN-USE,SSID,BSSID,CHAN,FREQ,SIGNAL,SECURITY",
            "dev",
            "wifi",
            "list",
            "ifname",
            device,
        ],
        timeout=15,
    )
    if not r["ok"]:
        return []
    nets: list[dict[str, Any]] = []
    for line in r["output"].splitlines():
        if not line.strip():
            continue
        parts = split_nmcli_terse(line)
        if len(parts) < 7:
            continue
        freq_raw = parts[4].strip()
        mhz = None
        fm = re.search(r"(\d+(?:\.\d+)?)", freq_raw)
        if fm:
            mhz = float(fm.group(1))
        ch = int(parts[3]) if parts[3].isdigit() else None
        sig = int(parts[5]) if parts[5].isdigit() else 0
        if mhz is None and ch is not None:
            mhz = _channel_to_mhz(ch)
        if mhz is None:
            continue
        nets.append({
            "in_use": parts[0].strip() == "*",
            "ssid": parts[1].strip() or "(hidden)",
            "bssid": parts[2].strip(),
            "channel": ch,
            "mhz": round(mhz, 1),
            "band_id": _band_for_mhz(mhz),
            "signal_pct": sig,
            "signal_dbm": _nm_signal_to_dbm(sig),
            "security": parts[6].strip() or "—",
        })
    return nets


def _channel_to_mhz(channel: int) -> float | None:
    if 1 <= channel <= 14:
        return 2407.0 + channel * 5.0
    if 36 <= channel <= 177:
        return 5000.0 + channel * 5.0
    if 1 <= channel <= 233:
        return 5950.0 + channel * 5.0
    return None


def _parse_link(device: str) -> dict[str, Any]:
    r = run_cmd(["iw", "dev", device, "link"], timeout=6)
    if not r["ok"]:
        return {}
    out: dict[str, Any] = {}
    for line in r["output"].splitlines():
        m = _LINK_FREQ.match(line)
        if m:
            out["mhz"] = float(m.group(1))
            out["band_id"] = _band_for_mhz(out["mhz"])
        m = _LINK_SSID.match(line)
        if m:
            out["ssid"] = m.group(1).strip()
        m = _LINK_SIGNAL.match(line)
        if m:
            out["signal_dbm"] = int(m.group(1))
    if out.get("mhz"):
        out["channel"] = _mhz_to_channel(out["mhz"])
    return out


def _mhz_to_channel(mhz: float) -> int | None:
    if 2412 <= mhz <= 2484:
        return int(round((mhz - 2407) / 5))
    if 5170 <= mhz <= 5885:
        return int(round((mhz - 5000) / 5))
    if 5955 <= mhz <= 7115:
        return int(round((mhz - 5950) / 5))
    return None


def _build_bins(
    phy_channels: list[dict[str, Any]],
    scan: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """One row per supported channel with peak signal from scan."""
    by_mhz: dict[float, dict[str, Any]] = {}
    for ch in phy_channels:
        if ch.get("disabled"):
            continue
        mhz = float(ch["mhz"])
        by_mhz[mhz] = {
            "mhz": mhz,
            "channel": ch["channel"],
            "band_id": ch.get("band_id"),
            "signal_dbm": None,
            "signal_pct": 0,
            "networks": [],
        }
    for net in scan:
        mhz = float(net["mhz"])
        row = by_mhz.get(mhz)
        if not row:
            row = {
                "mhz": mhz,
                "channel": net.get("channel"),
                "band_id": net.get("band_id"),
                "signal_dbm": None,
                "signal_pct": 0,
                "networks": [],
            }
            by_mhz[mhz] = row
        row["networks"].append({
            "ssid": net["ssid"],
            "signal_pct": net["signal_pct"],
            "signal_dbm": net["signal_dbm"],
            "in_use": net.get("in_use"),
        })
        if net["signal_pct"] > row["signal_pct"]:
            row["signal_pct"] = net["signal_pct"]
            row["signal_dbm"] = net["signal_dbm"]
    bins = sorted(by_mhz.values(), key=lambda x: x["mhz"])
    return bins


def spectrum_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    device = detect_wifi_device(None)
    if not device:
        return {
            "ok": False,
            "error": "No WiFi adapter found",
            "hint": "Connect a WiFi interface or install NetworkManager.",
            "bands": SPECTRUM_BANDS,
            "bins": [],
            "scan": [],
        }

    phy_idx = "0"
    phy_r = run_cmd(["iw", "dev", device, "info"], timeout=8)
    if phy_r["ok"]:
        pm = re.search(r"wiphy\s+(\d+)", phy_r["output"])
        if pm:
            phy_idx = pm.group(1)

    phy_info = run_cmd(["iw", "phy", f"phy{phy_idx}", "info"], timeout=10)
    phy_channels = _parse_phy_frequencies(phy_info["output"]) if phy_info["ok"] else []

    scan = _parse_nm_scan(device)
    link = _parse_link(device)
    bins = _build_bins(phy_channels, scan)

    bands_present = {b["id"] for b in SPECTRUM_BANDS if any(
        x.get("band_id") == b["id"] for x in phy_channels
    )}
    for net in scan:
        if net.get("band_id"):
            bands_present.add(net["band_id"])

    active_bands = [b for b in SPECTRUM_BANDS if b["id"] in bands_present or b["id"] in {"2g", "5g_unii1", "5g_unii3"}]

    return {
        "ok": True,
        "device": device,
        "phy": f"phy{phy_idx}",
        "bands": active_bands if active_bands else SPECTRUM_BANDS,
        "all_bands": SPECTRUM_BANDS,
        "bins": bins,
        "scan": scan,
        "link": link,
        "network_count": len(scan),
        "channel_count": len(bins),
        "tools": {
            "iw": bool(shutil.which("iw")),
            "wavemon": bool(shutil.which("wavemon")),
        },
        "hint": "Rescan from WiFi hub refreshes scan data. Spectrum uses your last NM scan — click Rescan here or on WiFi.",
    }
