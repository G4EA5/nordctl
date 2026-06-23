"""Live interface throughput from /proc/net/dev."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

VPN_IFACES = ("nordlynx", "nordtun", "tun0", "wg0", "wlan0", "wlp", "eth0", "enp")


def _read_counters() -> dict[str, tuple[int, int]]:
    path = Path("/proc/net/dev")
    if not path.is_file():
        return {}
    out: dict[str, tuple[int, int]] = {}
    for line in path.read_text(encoding="utf-8").splitlines()[2:]:
        if ":" not in line:
            continue
        iface, rest = line.split(":", 1)
        iface = iface.strip()
        parts = rest.split()
        if len(parts) < 9:
            continue
        rx = int(parts[0])
        tx = int(parts[8])
        out[iface] = (rx, tx)
    return out


def _fmt_bps(bps: float) -> str:
    if bps < 1024:
        return f"{bps:.0f} B/s"
    if bps < 1024 * 1024:
        return f"{bps / 1024:.1f} KB/s"
    return f"{bps / (1024 * 1024):.2f} MB/s"


def sample_bandwidth(*, wait: float = 1.0) -> dict[str, Any]:
    a = _read_counters()
    time.sleep(max(0.3, min(wait, 2.0)))
    b = _read_counters()
    samples: list[dict[str, Any]] = []
    for iface, (rx1, tx1) in a.items():
        if iface not in b:
            continue
        rx2, tx2 = b[iface]
        dt = wait
        rx_bps = max(0, (rx2 - rx1) / dt)
        tx_bps = max(0, (tx2 - tx1) / dt)
        is_vpn = any(v in iface for v in ("nordlynx", "nordtun", "tun", "wg"))
        if rx_bps < 50 and tx_bps < 50 and not is_vpn:
            continue
        samples.append({
            "iface": iface,
            "rx_bps": rx_bps,
            "tx_bps": tx_bps,
            "rx_human": _fmt_bps(rx_bps),
            "tx_human": _fmt_bps(tx_bps),
            "vpn": is_vpn,
        })
    samples.sort(key=lambda x: x["rx_bps"] + x["tx_bps"], reverse=True)
    primary = next((s for s in samples if s["vpn"]), samples[0] if samples else None)
    return {
        "ok": bool(samples),
        "interfaces": samples[:8],
        "primary": primary,
        "hint": "Shows download/upload speed per network interface — VPN tunnel highlighted.",
    }
