"""Linux network helpers (NetworkManager + resolvectl)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import subprocess
import threading
import time
from typing import Any


def split_nmcli_terse(line: str) -> list[str]:
    """Split an nmcli -t line; unescape \\: inside field values."""
    parts: list[str] = []
    cur: list[str] = []
    i = 0
    n = len(line)
    while i < n:
        ch = line[i]
        if ch == "\\" and i + 1 < n:
            cur.append(line[i + 1])
            i += 2
            continue
        if ch == ":":
            parts.append("".join(cur))
            cur = []
            i += 1
            continue
        cur.append(ch)
        i += 1
    parts.append("".join(cur))
    return parts


def run_cmd(args: list[str], timeout: float = 25.0) -> dict[str, Any]:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        return {"ok": r.returncode == 0, "code": r.returncode, "output": out.strip(), "args": args}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "output": "command timed out", "args": args}
    except FileNotFoundError:
        return {"ok": False, "code": -1, "output": f"{args[0]} not found", "args": args}


def detect_wifi_device(preferred: str | None) -> str | None:
    if preferred:
        return preferred
    r = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE", "dev", "status"], timeout=8)
    if not r["ok"]:
        return None
    for line in r["output"].splitlines():
        if ":" not in line:
            continue
        dev, typ = line.split(":", 1)
        if typ.strip() == "wifi" and dev.strip():
            return dev.strip()
    return None


def wifi_dns_servers(device: str) -> list[str]:
    r = run_cmd(["resolvectl", "status", device], timeout=5)
    if not r["ok"]:
        return []
    servers: list[str] = []
    for line in r["output"].splitlines():
        line = line.strip()
        if line.startswith("DNS Servers:"):
            servers.extend(part.strip() for part in line.split(":", 1)[1].split() if part.strip())
        elif line.startswith("Current DNS Server:"):
            val = line.split(":", 1)[1].strip()
            if val and val not in servers:
                servers.insert(0, val)
    return servers


def active_wifi_connection(device: str) -> str | None:
    r = run_cmd(["nmcli", "-t", "-f", "NAME,DEVICE", "con", "show", "--active"], timeout=8)
    if not r["ok"]:
        return None
    for line in r["output"].splitlines():
        if ":" not in line:
            continue
        name, dev = line.split(":", 1)
        if dev.strip() == device:
            return name.strip()
    return None


def bounce_wifi(device: str) -> dict[str, Any]:
    name = active_wifi_connection(device)
    if not name:
        return {"ok": True, "output": "no active WiFi connection to bounce", "args": []}
    down = run_cmd(["nmcli", "con", "down", name], timeout=20)
    up = run_cmd(["nmcli", "con", "up", name], timeout=30)
    return {
        "ok": down["ok"] and up["ok"],
        "output": "\n".join(x for x in (down.get("output"), up.get("output")) if x),
        "args": ["nmcli", "bounce", name],
    }


def apply_smart_dns(profiles: list[str], primary: str, secondary: str, device: str | None) -> list[dict[str, Any]]:
    dns = f"{primary} {secondary}"
    steps: list[dict[str, Any]] = []
    for profile in profiles:
        if not profile:
            continue
        steps.append(
            run_cmd(
                [
                    "nmcli",
                    "con",
                    "mod",
                    profile,
                    "ipv4.dns",
                    dns,
                    "ipv4.ignore-auto-dns",
                    "yes",
                    "ipv6.method",
                    "disabled",
                ],
                timeout=15,
            )
        )
    dev = detect_wifi_device(device)
    if dev:
        steps.append(bounce_wifi(dev))
    elif not profiles:
        steps.append({"ok": False, "output": "no wifi profiles configured", "args": ["smart_dns"]})
    return steps


def restore_dns(profiles: list[str], device: str | None) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for profile in profiles:
        if not profile:
            continue
        steps.append(
            run_cmd(
                [
                    "nmcli",
                    "con",
                    "mod",
                    profile,
                    "ipv4.ignore-auto-dns",
                    "no",
                    "ipv4.dns",
                    "",
                ],
                timeout=15,
            )
        )
    dev = detect_wifi_device(device)
    if dev:
        steps.append(bounce_wifi(dev))
    return steps


def public_ipv4(url: str) -> str | None:
    global _PUBLIC_IP_CACHE
    now = time.monotonic()
    key = url or ""
    with _PUBLIC_IP_LOCK:
        hit = _PUBLIC_IP_CACHE.get(key)
        if hit and now - hit[0] < _PUBLIC_IP_TTL:
            return hit[1]
    try:
        import urllib.request

        with urllib.request.urlopen(url, timeout=8) as resp:
            ip = resp.read().decode().strip()
            result = ip or None
    except OSError:
        result = None
    with _PUBLIC_IP_LOCK:
        _PUBLIC_IP_CACHE[key] = (now, result)
    return result


_PUBLIC_IP_CACHE: dict[str, tuple[float, str | None]] = {}
_PUBLIC_IP_LOCK = threading.Lock()
_PUBLIC_IP_TTL = 20.0


def nm_connection_fields(profile: str, fields: list[str]) -> dict[str, str]:
    """Read selected nmcli connection fields."""
    out: dict[str, str] = {}
    for field in fields:
        r = run_cmd(["nmcli", "-g", field, "con", "show", profile], timeout=8)
        if r["ok"]:
            out[field] = r["output"].strip()
    return out


def profile_dns_settings(profile: str) -> dict[str, Any]:
    fields = nm_connection_fields(
        profile,
        ["ipv4.dns", "ipv4.ignore-auto-dns", "ipv6.method", "802-11-wireless.ssid"],
    )
    dns_raw = fields.get("ipv4.dns") or ""
    servers = [p.strip() for p in dns_raw.replace(",", " ").split() if p.strip()]
    return {
        "profile": profile,
        "ssid": fields.get("802-11-wireless.ssid") or "",
        "dns_servers": servers,
        "ignore_auto_dns": (fields.get("ipv4.ignore-auto-dns") or "").lower() in ("yes", "true", "1"),
        "ipv6_method": fields.get("ipv6.method") or "",
    }


def smart_dns_drift(
    profiles: list[str],
    primary: str,
    secondary: str,
    *,
    device: str | None = None,
) -> dict[str, Any]:
    """True if configured profiles don't match expected Smart DNS."""
    expected = {primary, secondary} - {""}
    drift_profiles: list[str] = []
    details: list[str] = []
    for profile in profiles:
        if not profile:
            continue
        ps = profile_dns_settings(profile)
        if not ps.get("ignore_auto_dns"):
            drift_profiles.append(profile)
            details.append(f"{profile}: auto DNS (not locked to Nord)")
            continue
        have = set(ps.get("dns_servers") or [])
        if expected and not expected.issubset(have):
            drift_profiles.append(profile)
            details.append(f"{profile}: DNS {', '.join(have) or 'empty'}")
    live = wifi_dns_servers(device) if device else []
    live_drift = bool(expected and live and primary not in live)
    return {
        "drift": bool(drift_profiles or live_drift),
        "profiles": drift_profiles,
        "detail": "; ".join(details[:4]) or ("Live DNS differs from Smart DNS" if live_drift else ""),
        "live_dns": live,
        "expected": list(expected),
    }


def wifi_device_status(device: str | None) -> dict[str, Any]:
    dev = detect_wifi_device(device)
    if not dev:
        return {"device": None, "connected": False, "state": "missing"}
    r = run_cmd(["nmcli", "-t", "-f", "DEVICE,TYPE,STATE,CONNECTION", "dev", "status"], timeout=8)
    state = "unknown"
    connection = None
    if r["ok"]:
        for line in r["output"].splitlines():
            parts = line.split(":")
            if len(parts) >= 4 and parts[0] == dev:
                state = parts[2]
                connection = parts[3] or None
                break
    return {
        "device": dev,
        "connected": state == "connected",
        "state": state,
        "active_profile": connection,
    }


def wifi_scan(device: str | None, *, limit: int = 15) -> list[dict[str, Any]]:
    dev = detect_wifi_device(device)
    if not dev:
        return []
    r = run_cmd(
        [
            "nmcli",
            "-t",
            "-f",
            "IN-USE,SSID,BSSID,MODE,CHAN,RATE,SIGNAL,SECURITY",
            "dev",
            "wifi",
            "list",
            "ifname",
            dev,
        ],
        timeout=12,
    )
    if not r["ok"]:
        return []
    nets: list[dict[str, Any]] = []
    for line in r["output"].splitlines():
        parts = line.split(":")
        if len(parts) < 8:
            continue
        ssid = parts[1] or "(hidden)"
        nets.append({
            "in_use": parts[0] == "*",
            "ssid": ssid,
            "signal": int(parts[6]) if parts[6].isdigit() else 0,
            "security": parts[7] or "—",
            "channel": parts[4] or "",
        })
        if len(nets) >= limit:
            break
    nets.sort(key=lambda x: (-x["in_use"], -x["signal"]))
    return nets


def rescan_wifi(device: str | None) -> dict[str, Any]:
    dev = detect_wifi_device(device)
    if not dev:
        return {"ok": False, "error": "no wifi device"}
    return run_cmd(["nmcli", "dev", "wifi", "rescan", "ifname", dev], timeout=15)


def delete_wifi_connection(name: str) -> dict[str, Any]:
    n = str(name).strip()
    if not n:
        return {"ok": False, "error": "profile name required"}
    result = run_cmd(["nmcli", "connection", "delete", n], timeout=20)
    if result["ok"]:
        result["note"] = f"Deleted WiFi profile “{n}” from NetworkManager"
    return result


def connect_wifi_profile(name: str) -> dict[str, Any]:
    n = str(name).strip()
    if not n:
        return {"ok": False, "error": "profile name required"}
    result = run_cmd(["nmcli", "connection", "up", n], timeout=35)
    if result["ok"]:
        result["note"] = f"Connected using profile “{n}”"
    return result


def connect_wifi_ssid(ssid: str, password: str | None = None, device: str | None = None) -> dict[str, Any]:
    dev = detect_wifi_device(device)
    if not dev:
        return {"ok": False, "error": "no wifi device"}
    ssid = str(ssid).strip()
    if not ssid or ssid == "(hidden)":
        return {"ok": False, "error": "SSID required"}
    cmd = ["nmcli", "dev", "wifi", "connect", ssid, "ifname", dev]
    pwd = str(password or "").strip()
    if pwd:
        cmd.extend(["password", pwd])
    result = run_cmd(cmd, timeout=45)
    if result["ok"]:
        result["note"] = f"Connected to “{ssid}”"
    return result

