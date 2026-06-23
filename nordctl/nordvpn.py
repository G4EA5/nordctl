"""NordVPN CLI wrapper."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
import subprocess
import threading
import time
from typing import Any

BLOCKED_COMMANDS = frozenset({"login", "logout", "register"})
NORD_DNS_PREFIXES = ("103.86.", "103.87.")


def nord_dns_active(raw: str | None) -> bool:
    """True when NordVPN uses Nord DNS (automatic/disabled setting or Nord server IPs)."""
    raw = str(raw or "").strip()
    if not raw:
        return False
    low = raw.lower()
    if "disabled" in low:
        return True
    ips = re.findall(r"\d+\.\d+\.\d+\.\d+", raw)
    if ips:
        return all(any(ip.startswith(prefix) for prefix in NORD_DNS_PREFIXES) for ip in ips)
    if low in {"on", "yes", "enabled"}:
        return True
    return False


def parse_dns_toggle(raw: str) -> dict[str, Any]:
    """Map nordvpn settings DNS line to nordctl Nord DNS toggle state."""
    raw = str(raw or "").strip()
    if not raw:
        return {"state": "off", "on": False, "display": "Off"}
    if nord_dns_active(raw):
        low = raw.lower()
        if "disabled" in low:
            return {"state": "on", "on": True, "display": "On"}
        if re.search(r"\d+\.\d+\.\d+\.\d+", raw):
            return {"state": "custom", "on": True, "display": f"On ({raw})"}
        return {"state": "on", "on": True, "display": "On"}
    return {"state": "custom", "on": False, "display": f"Custom ({raw})"}


def apply_dns_preference(
    bin_path: str,
    enable_nord: bool,
    cfg: dict[str, Any],
    *,
    timeout: float = 15.0,
) -> dict[str, Any]:
    """Apply Nord DNS on/off using current Nord CLI semantics."""
    if enable_nord:
        return run(bin_path, ["set", "dns", "off"], timeout=timeout)
    custom = [str(x).strip() for x in (cfg.get("custom_dns") or []) if str(x).strip()]
    if not custom:
        return {
            "ok": False,
            "code": -1,
            "output": (
                "Add custom DNS servers under My places first. "
                "This Nord CLI only accepts dns off (Nord automatic) or explicit IP addresses."
            ),
            "error": "No custom DNS configured",
            "hint": "Settings → custom DNS, then turn Nord DNS off here.",
            "args": ["set", "dns"],
        }
    return run(bin_path, ["set", "dns", *custom], timeout=timeout)

_NORD_CACHE: dict[tuple[str, tuple[str, ...]], tuple[float, dict[str, Any]]] = {}
_NORD_LOCK = threading.Lock()

_TTL_BY_CMD: dict[str, float] = {
    "status": 6.0,
    "settings": 6.0,
    "countries": 300.0,
    "cities": 120.0,
    "version": 60.0,
    "account": 30.0,
}


def _cache_ttl(args: list[str]) -> float:
    if not args:
        return 8.0
    return _TTL_BY_CMD.get(str(args[0]), 8.0)


def invalidate_cache(*, bin_path: str | None = None) -> None:
    """Drop cached CLI results after Nord-changing actions."""
    with _NORD_LOCK:
        if bin_path is None:
            _NORD_CACHE.clear()
            return
        for key in [k for k in _NORD_CACHE if k[0] == bin_path]:
            del _NORD_CACHE[key]


def run_cached(
    bin_path: str,
    args: list[str],
    timeout: float = 45.0,
    *,
    ttl: float | None = None,
) -> dict[str, Any]:
    """Run Nord CLI with a short TTL cache to avoid duplicate subprocess storms."""
    key = (bin_path, tuple(args))
    max_age = ttl if ttl is not None else _cache_ttl(args)
    now = time.monotonic()
    with _NORD_LOCK:
        hit = _NORD_CACHE.get(key)
        if hit and now - hit[0] < max_age:
            return hit[1]
    result = run(bin_path, args, timeout)
    with _NORD_LOCK:
        _NORD_CACHE[key] = (now, result)
    return result


def available(bin_path: str) -> bool:
    try:
        r = subprocess.run(["which", bin_path], capture_output=True, text=True, timeout=3)
        return r.returncode == 0 and bool(r.stdout.strip())
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def run(bin_path: str, args: list[str], timeout: float = 45.0) -> dict[str, Any]:
    if args and args[0] in BLOCKED_COMMANDS:
        return {"ok": False, "code": -1, "output": f"command not allowed: {args[0]}", "args": args}
    cmd = [bin_path, *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "") + (r.stderr or "")
        ok = r.returncode == 0
        if not ok and len(args) >= 3 and args[0] == "set" and "already" in out.lower():
            ok = True
        if not ok and args[:1] == ["disconnect"] and "not connected" in out.lower():
            ok = True
        return {"ok": ok, "code": r.returncode, "output": out.strip(), "args": args}
    except subprocess.TimeoutExpired:
        return {"ok": False, "code": -1, "output": "command timed out", "args": args}
    except FileNotFoundError:
        return {"ok": False, "code": -1, "output": f"{bin_path} not found", "args": args}


def _parse_kv_block(text: str) -> dict[str, str]:
    data: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Allowlisted"):
            continue
        if ":" in line:
            key, val = line.split(":", 1)
            data[key.strip()] = val.strip()
    return data


def parse_status(text: str) -> dict[str, Any]:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {"connected": False, "raw": text}
    first = lines[0]
    if first.startswith("Status: Disconnected"):
        return {"connected": False, "status": "disconnected", "raw": text}
    info = _parse_kv_block(text)
    info["connected"] = "Connected" in first or info.get("Status") == "Connected"
    info["status"] = "connected" if info["connected"] else "disconnected"
    return info


def parse_settings(text: str) -> dict[str, Any]:
    settings = _parse_kv_block(text)
    allowlisted_ports: list[str] = []
    allowlisted_subnets: list[str] = []
    section = ""
    for line in text.splitlines():
        s = line.strip()
        if s == "Allowlisted ports:":
            section = "ports"
            continue
        if s == "Allowlisted subnets:":
            section = "subnets"
            continue
        if not s or (":" in s and section == ""):
            continue
        if section == "ports" and s and not s.endswith(":"):
            allowlisted_ports.append(s)
        elif section == "subnets" and s and not s.endswith(":"):
            allowlisted_subnets.append(s)
    settings["allowlisted_ports"] = allowlisted_ports
    settings["allowlisted_subnets"] = allowlisted_subnets
    return settings


def mesh_ip() -> str | None:
    return tunnel_local_ip("nordlynx")


def tunnel_local_ip(dev: str = "nordlynx") -> str | None:
    try:
        r = subprocess.run(
            ["ip", "-4", "-o", "addr", "show", "dev", dev],
            capture_output=True,
            text=True,
            timeout=2,
        )
        if r.returncode == 0:
            m = re.search(r"\binet (\d+\.\d+\.\d+\.\d+)", r.stdout)
            if m:
                return m.group(1)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return None


def list_countries(bin_path: str) -> list[str]:
    r = run_cached(bin_path, ["countries"], timeout=20)
    if not r["ok"]:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for line in r["output"].splitlines():
        line = line.strip()
        if not line or line.startswith("Country"):
            continue
        # NordVPN may print several countries per line (column layout in some terminals).
        chunks = re.split(r"\s{2,}", line) if re.search(r"\s{2,}", line) else [line]
        for chunk in chunks:
            name = chunk.strip()
            if len(name) > 1 and name not in seen:
                seen.add(name)
                out.append(name)
    return out


def list_cities(bin_path: str, country: str) -> list[str]:
    """Cities for a country — returns full connect targets like 'Germany Berlin'."""
    country = str(country or "").strip().replace(" ", "_")
    if not country:
        return []
    r = run_cached(bin_path, ["cities", country], timeout=20)
    if not r["ok"]:
        return []
    country_label = country.replace("_", " ")
    out: list[str] = []
    for line in r["output"].splitlines():
        city = line.strip()
        if not city or city.lower().startswith("usage"):
            continue
        if city.lower().startswith("please"):
            continue
        out.append(f"{country_label} {city}")
    return out
