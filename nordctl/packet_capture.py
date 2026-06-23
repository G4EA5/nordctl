"""Lite packet capture on VPN interface (tcpdump)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from nordctl.config import config_dir
from nordctl.traffic_watch import VPN_IFACES

MAX_LINES = 80
MAX_SECONDS = 45


def _vpn_iface() -> str | None:
    import subprocess as sp

    for iface in VPN_IFACES:
        r = sp.run(["ip", "link", "show", iface], capture_output=True, timeout=4)
        if r.returncode == 0 and b"UP" in r.stdout:
            return iface
    r = sp.run(["ip", "-br", "link"], capture_output=True, text=True, timeout=4)
    for line in (r.stdout or "").splitlines():
        parts = line.split()
        if parts and any(v in parts[0] for v in VPN_IFACES):
            return parts[0]
    return None


def run_capture(seconds: int = 10, *, max_packets: int = 60) -> dict[str, Any]:
    if not shutil.which("tcpdump"):
        return {
            "ok": False,
            "error": "Install tcpdump: sudo apt install tcpdump",
            "hint": "Read-only capture — no files saved unless you export.",
        }
    sec = max(3, min(int(seconds), MAX_SECONDS))
    iface = _vpn_iface()
    if not iface:
        return {
            "ok": False,
            "error": "No VPN interface up — connect VPN first or capture will miss tunnel traffic.",
        }
    out_path = config_dir() / "captures"
    out_path.mkdir(parents=True, exist_ok=True)
    pcap = out_path / f"capture-{int(time.time())}.pcap"
    try:
        r = subprocess.run(
            [
                "tcpdump",
                "-i",
                iface,
                "-c",
                str(max_packets),
                "-n",
                "-w",
                str(pcap),
            ],
            capture_output=True,
            text=True,
            timeout=sec + 10,
        )
        summary = subprocess.run(
            ["tcpdump", "-r", str(pcap), "-n", "-c", str(MAX_LINES)],
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = (summary.stdout or "").strip().splitlines()
        friendly = []
        for ln in lines[1:MAX_LINES]:
            if " IP " in ln:
                friendly.append(ln.split(" IP ", 1)[-1][:120])
            else:
                friendly.append(ln[:120])
        return {
            "ok": r.returncode == 0 or pcap.is_file(),
            "iface": iface,
            "seconds": sec,
            "pcap_path": str(pcap),
            "packet_count": len(friendly),
            "summary": friendly[:40],
            "plain": f"Captured {len(friendly)} packets on {iface}. File: {pcap}",
            "note": "Full .pcap for Wireshark — summary above is simplified.",
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Capture timed out"}
    except PermissionError:
        return {
            "ok": False,
            "error": "tcpdump needs root — run: sudo tcpdump -i nordlynx -c 20",
            "manual": f"sudo tcpdump -i {iface} -c {max_packets} -n",
        }
