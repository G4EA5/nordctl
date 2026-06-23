"""Download speed test (curl-based, optional Ookla CLI for Speedtest.net)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import shutil
import statistics
import subprocess
import time
from typing import Any

_CLOUDFLARE = "https://speed.cloudflare.com/__down?bytes={bytes}"
_OVH = "https://proof.ovh.net/files/{mb}Mb.dat"
_TELE2 = "http://speedtest.tele2.net/{mb}MB.zip"
_THINKBROADBAND = "http://ipv4.download.thinkbroadband.com/{mb}MB.zip"
_LINODE_LONDON = "http://speedtest.london.linode.com/100MB-london.bin"
_LINODE_NEWARK = "http://speedtest.newark.linode.com/100MB-newark.bin"
_LINODE_DALLAS = "http://speedtest.dallas.linode.com/100MB-dallas.bin"
_LINODE_FREMONT = "http://speedtest.fremont.linode.com/100MB-fremont.bin"
_LINODE_ATLANTA = "http://speedtest.atlanta.linode.com/100MB-atlanta.bin"
_LINODE_FRANKFURT = "http://speedtest.frankfurt.linode.com/100MB-frankfurt.bin"
_LINODE_SINGAPORE = "http://speedtest.singapore.linode.com/100MB-singapore.bin"
_LINODE_TOKYO = "http://speedtest.tokyo2.linode.com/100MB-tokyo2.bin"
_LINODE_SYDNEY = "http://speedtest.sydney.linode.com/100MB-sydney.bin"
_FASTCOM = "https://speed.cloudflare.com/__down?bytes={bytes}"

_PROFILES: dict[str, dict[str, Any]] = {
    "quick": {"bytes": 10_000_000, "timeout": 25, "label": "Quick (10 MB)"},
    "standard": {"bytes": 25_000_000, "timeout": 45, "label": "Standard (25 MB)"},
    "large": {"bytes": 50_000_000, "timeout": 60, "label": "Large (50 MB)"},
    "max": {"bytes": 100_000_000, "timeout": 90, "label": "Max (100 MB)"},
}

# kind: cloudflare | ovh | tele2 | thinkbroadband | linode | linode_us | fast | ookla_cli
_PROVIDERS: dict[str, dict[str, Any]] = {
    "auto": {"kind": "auto", "label": "Auto (nearest mirror by IP)", "region": "global"},
    "cloudflare": {"kind": "cloudflare", "label": "Cloudflare CDN (global edge)", "region": "global"},
    "linode_newark": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Newark, US East)",
        "region": "us-east",
        "url": _LINODE_NEWARK,
    },
    "linode_atlanta": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Atlanta, US Southeast)",
        "region": "us-southeast",
        "url": _LINODE_ATLANTA,
    },
    "linode_dallas": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Dallas, US Central)",
        "region": "us-central",
        "url": _LINODE_DALLAS,
    },
    "linode_fremont": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Fremont, US West)",
        "region": "us-west",
        "url": _LINODE_FREMONT,
    },
    "linode_frankfurt": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Frankfurt, EU Central)",
        "region": "eu-central",
        "url": _LINODE_FRANKFURT,
    },
    "linode_singapore": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Singapore, APAC)",
        "region": "ap-southeast",
        "url": _LINODE_SINGAPORE,
    },
    "linode_tokyo": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Tokyo, Japan)",
        "region": "ap-northeast",
        "url": _LINODE_TOKYO,
    },
    "linode_sydney": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Sydney, Australia)",
        "region": "ap-southeast-2",
        "url": _LINODE_SYDNEY,
    },
    "ovh": {"kind": "ovh", "label": "OVH (France)", "region": "eu-west"},
    "tele2": {"kind": "tele2", "label": "Tele2 / Ookla mirror (Sweden)", "region": "eu-north"},
    "thinkbroadband": {"kind": "thinkbroadband", "label": "ThinkBroadband (UK)", "region": "uk"},
    # Legacy provider id (retired third-party host); Frankfurt Akamai mirror.
    "hetzner": {
        "kind": "linode_us",
        "label": "Linode / Akamai (Frankfurt, EU Central)",
        "region": "eu-central",
        "url": _LINODE_FRANKFURT,
    },
    "linode": {"kind": "linode", "label": "Linode / Akamai (London)", "region": "uk", "url": _LINODE_LONDON},
    "fast": {"kind": "fast", "label": "Fast.com style (Cloudflare)", "region": "global"},
    "speedtest_net": {"kind": "ookla_cli", "label": "Speedtest.net (Ookla CLI — nearest server)", "region": "global"},
}

_EU_COUNTRY_CODES = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT",
    "LV", "LT", "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "NO", "IS", "CH",
})

_ASIA_COUNTRY_CODES = frozenset({
    "JP", "KR", "CN", "TW", "HK", "MO", "SG", "MY", "TH", "VN", "PH", "ID", "IN", "PK", "BD",
    "LK", "NP", "MM", "KH", "LA", "BN", "MN", "KZ", "UZ", "AE", "SA", "QA", "KW", "BH", "OM",
    "IL", "JO", "LB", "TR", "GE", "AZ",
})

_OCEANIA_COUNTRY_CODES = frozenset({"AU", "NZ", "FJ", "PG"})

_LATAM_COUNTRY_CODES = frozenset({
    "BR", "AR", "CL", "CO", "PE", "VE", "EC", "BO", "PY", "UY", "CR", "PA", "DO", "GT", "HN",
    "SV", "NI", "CU", "PR",
})

_US_EAST_COLO = frozenset({
    "ewr", "iad", "bos", "mia", "atl", "phl", "clt", "dtw", "yul", "yyz", "ord", "buf", "ric", "jax",
})
_US_CENTRAL_COLO = frozenset({"dfw", "den", "stl", "msp", "iah", "mci", "oma", "sat", "aus", "bna"})
_US_WEST_COLO = frozenset({"sfo", "lax", "sea", "pdx", "slc", "phx", "san", "las", "sjc", "smf"})

_US_PROVIDERS = {
    "us-east": "linode_newark",
    "us-southeast": "linode_atlanta",
    "us-central": "linode_dallas",
    "us-west": "linode_fremont",
}


def _speedtest_cfg(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    if cfg is None:
        from nordctl.config import load_config

        cfg = load_config()
    st = cfg.get("speedtest")
    return st if isinstance(st, dict) else {}


def merged_providers(cfg: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
    """Built-in mirrors plus user-defined entries from config.yaml."""
    out = dict(_PROVIDERS)
    st = _speedtest_cfg(cfg)
    for row in st.get("custom_mirrors") or []:
        if not isinstance(row, dict):
            continue
        pid = str(row.get("id") or "").strip()
        url = str(row.get("url") or "").strip()
        if not pid or not url.startswith(("http://", "https://")):
            continue
        out[pid] = {
            "kind": "custom_url",
            "label": str(row.get("label") or pid),
            "region": str(row.get("region") or "custom"),
            "url": url,
        }
    return out


def speedtest_defaults(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    st = _speedtest_cfg(cfg)
    return {
        "default_provider": str(st.get("default_provider") or "auto"),
        "default_profile": str(st.get("default_profile") or "standard"),
        "default_method": str(st.get("default_method") or "single"),
        "warmup": bool(st.get("warmup")),
        "save_results": st.get("save_results", True) is not False,
    }


def speedtest_profiles() -> dict[str, str]:
    return {k: str(v["label"]) for k, v in _PROFILES.items()}


def speedtest_providers(cfg: dict[str, Any] | None = None) -> dict[str, str]:
    return {k: str(v["label"]) for k, v in merged_providers(cfg).items()}


def _curl_text(url: str, timeout: float = 5.0) -> str:
    if not shutil.which("curl"):
        return ""
    try:
        r = subprocess.run(
            ["curl", "-4", "-sS", "--max-time", str(max(1, int(timeout))), url],
            capture_output=True,
            text=True,
            timeout=timeout + 2,
        )
        if r.returncode == 0:
            return (r.stdout or "").strip()
    except (subprocess.TimeoutExpired, OSError):
        pass
    return ""


def _parse_kv_lines(text: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        if "=" not in line:
            continue
        key, val = line.split("=", 1)
        out[key.strip()] = val.strip()
    return out


def _geo_from_ip_api(ip: str) -> dict[str, Any]:
    ip = (ip or "").strip()
    if not ip:
        return {}
    raw = _curl_text(
        f"http://ip-api.com/json/{ip}?fields=status,country,countryCode,regionName,city,lat,lon",
        timeout=5,
    )
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    if data.get("status") != "success":
        return {}
    return {
        "source": "ip-api",
        "ip": ip,
        "country_code": str(data.get("countryCode") or "").upper(),
        "country": str(data.get("country") or ""),
        "region": str(data.get("regionName") or ""),
        "city": str(data.get("city") or ""),
        "lat": data.get("lat"),
        "lon": data.get("lon"),
    }


def detect_geo(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Best-effort client geo from Cloudflare trace, then ip-api fallback."""
    trace = _parse_kv_lines(_curl_text("https://1.1.1.1/cdn-cgi/trace", timeout=4))
    ip = trace.get("ip") or ""
    country_code = (trace.get("loc") or "").upper()
    if country_code:
        return {
            "source": "cloudflare_trace",
            "ip": ip,
            "country_code": country_code,
            "country": country_code,
            "colo": (trace.get("colo") or "").upper(),
            "region": "",
            "city": "",
        }
    if not ip:
        try:
            from nordctl.config import load_config
            from nordctl.network_linux import public_ipv4

            cfg = cfg or load_config()
            ip = public_ipv4(str(cfg.get("public_ip_check_url") or "https://ifconfig.me/ip")) or ""
        except Exception:
            ip = ""
    geo = _geo_from_ip_api(ip)
    if geo:
        return geo
    return {"source": "unknown", "ip": ip, "country_code": "", "country": "", "region": "", "city": ""}


def _region_bucket(country_code: str) -> str:
    cc = (country_code or "").upper()
    if cc == "US":
        return "us"
    if cc in _OCEANIA_COUNTRY_CODES:
        return "oceania"
    if cc in _ASIA_COUNTRY_CODES:
        return "asia"
    if cc in _LATAM_COUNTRY_CODES:
        return "latam"
    if cc in _EU_COUNTRY_CODES or cc == "GB":
        return "eu"
    if cc in ("CA", "MX"):
        return "na"
    return "global"


def _nearest_asia_provider(geo: dict[str, Any]) -> str:
    cc = str(geo.get("country_code") or "").upper()
    if cc in ("JP", "KR"):
        return "linode_tokyo"
    if cc in _OCEANIA_COUNTRY_CODES:
        return "linode_sydney"
    if cc in ("IN", "PK", "BD", "LK", "NP"):
        return "linode_singapore"
    # Middle East / Central Asia — Singapore is usually the lowest-latency Akamai POP in repo set.
    return "linode_singapore"


def _nearest_us_provider(geo: dict[str, Any]) -> str:
    colo = str(geo.get("colo") or "").lower()
    if colo in _US_WEST_COLO:
        return "linode_fremont"
    if colo in _US_CENTRAL_COLO:
        return "linode_dallas"
    if colo in _US_EAST_COLO:
        if colo in {"mia", "atl", "jax", "ric", "clt"}:
            return "linode_atlanta"
        return "linode_newark"
    lat = geo.get("lat")
    if isinstance(lat, (int, float)):
        if lat >= 39:
            return "linode_newark"
        if lat >= 33:
            return "linode_atlanta"
        if lat >= 29:
            return "linode_dallas"
        return "linode_fremont"
    return "linode_dallas"


def recommend_provider(geo: dict[str, Any] | None = None, cfg: dict[str, Any] | None = None) -> tuple[str, str]:
    geo = geo or detect_geo()
    providers = merged_providers(cfg)
    defaults = speedtest_defaults(cfg)
    configured = str(defaults.get("default_provider") or "auto")
    if configured and configured != "auto" and configured in providers:
        label = providers[configured]["label"]
        return configured, f"Your default — {label}"
    cc = str(geo.get("country_code") or "").upper()
    region = _region_bucket(cc)
    if region == "us":
        pick = _nearest_us_provider(geo)
        label = providers[pick]["label"]
        colo = geo.get("colo")
        hint = f"Detected US"
        if colo:
            hint += f" (edge {colo})"
        return pick, f"{hint} — using {label}"
    if cc == "GB":
        return "thinkbroadband", "Detected UK — ThinkBroadband mirror"
    if cc in ("DE", "AT", "CH"):
        return "linode_frankfurt", "Detected DACH — Frankfurt mirror"
    if cc == "FR":
        return "ovh", "Detected France — OVH mirror"
    if cc in ("SE", "NO", "FI", "DK"):
        return "tele2", "Detected Nordics — Tele2 mirror"
    if cc in _OCEANIA_COUNTRY_CODES:
        return "linode_sydney", "Detected Oceania — Sydney mirror"
    if cc in ("JP", "KR"):
        return "linode_tokyo", "Detected East Asia — Tokyo mirror"
    if cc in _ASIA_COUNTRY_CODES:
        pick = _nearest_asia_provider(geo)
        return pick, f"Detected Asia — {providers[pick]['label']}"
    if cc in _LATAM_COUNTRY_CODES:
        return "linode_dallas", "Detected Latin America — Dallas mirror"
    if region == "eu":
        return "cloudflare", "Detected Europe — Cloudflare edge"
    if cc == "CA":
        return "linode_newark", "Detected Canada — nearest US East mirror"
    return "cloudflare", "Global default — Cloudflare CDN edge"


def _auto_chain(geo: dict[str, Any] | None = None, cfg: dict[str, Any] | None = None) -> tuple[str, ...]:
    geo = geo or detect_geo()
    region = _region_bucket(str(geo.get("country_code") or ""))
    if region == "us":
        nearest = _nearest_us_provider(geo)
        raw = (
            "cloudflare",
            nearest,
            "linode_dallas",
            "linode_newark",
            "linode_atlanta",
            "linode_fremont",
            "linode_frankfurt",
            "tele2",
        )
    elif region == "eu":
        raw = (
            "cloudflare",
            "linode_frankfurt",
            "ovh",
            "tele2",
            "thinkbroadband",
            "linode",
            "linode_newark",
        )
    elif region == "asia":
        nearest = _nearest_asia_provider(geo)
        raw = (
            "cloudflare",
            nearest,
            "linode_tokyo",
            "linode_singapore",
            "linode_sydney",
            "linode_frankfurt",
            "tele2",
            "ovh",
        )
    elif region == "oceania":
        raw = (
            "cloudflare",
            "linode_sydney",
            "linode_singapore",
            "linode_tokyo",
            "linode_dallas",
            "linode_fremont",
        )
    elif region == "latam":
        raw = (
            "cloudflare",
            "linode_dallas",
            "linode_atlanta",
            "linode_newark",
            "linode_fremont",
            "ovh",
            "tele2",
        )
    elif region == "na":
        raw = ("cloudflare", "linode_newark", "linode_dallas", "linode_fremont", "linode_atlanta")
    else:
        raw = (
            "cloudflare",
            "linode_singapore",
            "linode_tokyo",
            "linode_sydney",
            "linode_frankfurt",
            "linode_dallas",
            "linode_newark",
            "tele2",
            "ovh",
            "thinkbroadband",
        )
    custom_ids = [
        pid for pid, meta in merged_providers(cfg).items() if meta.get("kind") == "custom_url"
    ]
    seen: set[str] = set()
    out: list[str] = []
    for item in (*raw, *custom_ids):
        if item not in seen:
            seen.add(item)
            out.append(item)
    return tuple(out)


def speedtest_providers_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    geo = detect_geo(cfg)
    recommended, reason = recommend_provider(geo, cfg)
    return {
        "ok": True,
        "profiles": speedtest_profiles(),
        "providers": speedtest_providers(cfg),
        "recommended": recommended,
        "recommended_reason": reason,
        "defaults": speedtest_defaults(cfg),
        "geo": geo,
    }


def _closest_mb(nbytes: int, allowed: tuple[int, ...]) -> int:
    want = max(1, round(nbytes / 1_000_000))
    return min(allowed, key=lambda x: abs(x - want))


def _provider_url(
    provider: str,
    profile: dict[str, Any],
    providers: dict[str, dict[str, Any]] | None = None,
) -> str:
    providers = providers or merged_providers()
    meta = providers.get(provider, providers["auto"])
    kind = meta["kind"]
    nbytes = int(profile["bytes"])
    if kind == "ovh":
        mb = max(1, min(10, nbytes // 1_000_000))
        return _OVH.format(mb=mb)
    if kind == "tele2":
        mb = _closest_mb(nbytes, (1, 10, 100, 500, 1000))
        return _TELE2.format(mb=mb)
    if kind == "thinkbroadband":
        mb = _closest_mb(nbytes, (5, 10, 20, 50, 100, 200))
        return _THINKBROADBAND.format(mb=mb)
    if kind == "custom_url":
        url = str(meta.get("url") or "")
        if "{bytes}" in url:
            return url.format(bytes=nbytes)
        if "{mb}" in url:
            mb = max(1, min(100, nbytes // 1_000_000))
            return url.format(mb=mb)
        return url
    if kind == "linode_us":
        return str(meta.get("url") or _LINODE_DALLAS)
    if kind == "linode":
        return str(meta.get("url") or _LINODE_LONDON)
    if kind == "fast":
        return _FASTCOM.format(bytes=min(nbytes, 100_000_000))
    return _CLOUDFLARE.format(bytes=nbytes)


def _curl_download(url: str, timeout: float = 45.0) -> dict[str, Any]:
    if not shutil.which("curl"):
        return {
            "ok": False,
            "error": "curl not installed",
            "manual": "Install curl from Networking → Networking packages.",
        }
    start = time.perf_counter()
    try:
        r = subprocess.run(
            [
                "curl", "-4", "-sS", "-L", "-o", "/dev/null",
                "-w", "%{size_download}|%{time_total}|%{speed_download}",
                "--max-time", str(int(timeout)),
                url,
            ],
            capture_output=True,
            text=True,
            timeout=timeout + 5,
        )
        elapsed = time.perf_counter() - start
        if r.returncode != 0:
            err = (r.stderr or r.stdout or "curl failed").strip()
            return {"ok": False, "error": err, "url": url}
        parts = (r.stdout or "").strip().split("|")
        try:
            nbytes = int(float(parts[0])) if parts else 0
        except ValueError:
            nbytes = 0
        curl_secs = float(parts[1]) if len(parts) > 1 else elapsed
        curl_bps = float(parts[2]) if len(parts) > 1 and parts[2] else 0
        secs = curl_secs if curl_secs > 0 else elapsed
        mbps = (curl_bps * 8 / 1_000_000) if curl_bps > 0 else ((nbytes * 8 / 1_000_000) / secs if secs > 0 else 0)
        return {
            "ok": True,
            "bytes": nbytes,
            "seconds": round(secs, 2),
            "mbps": round(mbps, 2),
            "human": f"{mbps:.1f} Mbps down ({nbytes // 1024} KB in {secs:.1f}s)",
            "url": url,
        }
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": "Download timed out", "url": url}


def _run_ookla_cli(timeout: float) -> dict[str, Any]:
    """Speedtest.net via official Ookla CLI or legacy speedtest-cli."""
    last: dict[str, Any] = {
        "ok": False,
        "error": "Speedtest.net CLI not installed",
        "manual": "Install Ookla CLI: https://www.speedtest.net/apps/cli — or pip install speedtest-cli",
        "provider": "speedtest_net",
    }
    attempts: list[tuple[list[str], str]] = [
        (["speedtest", "--format=json", "--accept-license", "--accept-gdpr"], "speedtest"),
        (["speedtest", "--format=json"], "speedtest"),
        (["speedtest-cli", "--json"], "speedtest-cli"),
    ]
    for args, label in attempts:
        if not shutil.which(args[0]):
            continue
        try:
            r = subprocess.run(
                args,
                capture_output=True,
                text=True,
                timeout=min(timeout + 30, 120),
            )
            if r.returncode != 0:
                last = {"ok": False, "error": (r.stderr or r.stdout or f"{label} failed").strip(), "provider": "speedtest_net"}
                continue
            raw = (r.stdout or "").strip()
            data = json.loads(raw.split("\n")[-1] if "\n" in raw else raw)
            if "download" in data and isinstance(data["download"], dict):
                bps = float(data["download"].get("bandwidth") or 0)
                nbytes = int(data["download"].get("bytes") or 0)
                elapsed_ms = data["download"].get("elapsed")
                elapsed = float(elapsed_ms) / 1000 if elapsed_ms else 0
                mbps = (bps * 8 / 1_000_000) if bps else 0
                server = (data.get("server") or {}).get("name") or "Ookla server"
                url = f"speedtest.net → {server}"
            else:
                bps = float(data.get("download") or 0)
                mbps = (bps * 8 / 1_000_000) if bps else 0
                nbytes = None
                elapsed = 0
                url = "speedtest.net (speedtest-cli)"
            if mbps <= 0:
                last = {"ok": False, "error": f"{label} returned no download speed", "provider": "speedtest_net"}
                continue
            return {
                "ok": True,
                "bytes": nbytes,
                "seconds": round(elapsed, 2) if elapsed else None,
                "mbps": round(mbps, 2),
                "human": f"{mbps:.1f} Mbps down (Speedtest.net / {label})",
                "url": url,
                "provider": "speedtest_net",
            }
        except subprocess.TimeoutExpired:
            return {"ok": False, "error": "Speedtest.net CLI timed out", "provider": "speedtest_net"}
        except json.JSONDecodeError as e:
            last = {"ok": False, "error": f"Could not parse {label} output: {e}", "provider": "speedtest_net"}
        except OSError as e:
            last = {"ok": False, "error": str(e), "provider": "speedtest_net"}
    return last


def _run_once(
    provider: str,
    profile_key: str,
    geo: dict[str, Any] | None = None,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    profile = _PROFILES.get(profile_key, _PROFILES["standard"])
    providers = merged_providers(cfg)
    prov = provider if provider in providers else "auto"
    kind = providers[prov]["kind"]

    if kind == "ookla_cli":
        return _run_ookla_cli(float(profile["timeout"]))

    if prov == "auto":
        last: dict[str, Any] = {"ok": False, "error": "All auto mirrors failed"}
        for candidate in _auto_chain(geo, cfg):
            url = _provider_url(candidate, profile, providers)
            result = _curl_download(url, timeout=float(profile["timeout"]))
            if result.get("ok"):
                result["provider_used"] = candidate
                return result
            last = result
        return last

    url = _provider_url(prov, profile, providers)
    return _curl_download(url, timeout=float(profile["timeout"]))


def run_speedtest(
    *,
    profile: str = "standard",
    method: str = "single",
    provider: str = "auto",
    warmup: bool = False,
    cfg: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    defaults = speedtest_defaults(cfg)
    providers = merged_providers(cfg)
    profile_key = profile if profile in _PROFILES else str(defaults["default_profile"])
    if profile_key not in _PROFILES:
        profile_key = "standard"
    prov = provider if provider in providers else str(defaults["default_provider"])
    if prov not in providers:
        prov = "auto"
    meth = method if method in ("single", "average", "best") else str(defaults["default_method"])
    if meth not in ("single", "average", "best"):
        meth = "single"
    prof = _PROFILES[profile_key]
    geo = detect_geo(cfg)
    use_warmup = warmup or bool(defaults.get("warmup"))

    if use_warmup:
        _curl_download(_CLOUDFLARE.format(bytes=1_000_000), timeout=10)

    runs: list[dict[str, Any]] = []
    count = 3 if meth in ("average", "best") else 1
    for i in range(count):
        if i:
            time.sleep(0.35)
        one = _run_once(prov, profile_key, geo=geo, cfg=cfg)
        one["run"] = i + 1
        runs.append(one)
        if not one.get("ok") and count == 1:
            break

    ok_runs = [r for r in runs if r.get("ok")]
    if not ok_runs:
        err = runs[-1] if runs else {"ok": False, "error": "No test runs"}
        err.update({
            "profile": profile_key,
            "method": meth,
            "provider": prov,
            "geo": dict(geo),
            "runs": [dict(r) for r in runs if isinstance(r, dict)],
        })
        return err

    if meth == "average":
        mbps = round(statistics.mean(r["mbps"] for r in ok_runs), 2)
        pick = ok_runs[-1]
    elif meth == "best":
        pick = max(ok_runs, key=lambda r: r["mbps"])
        mbps = pick["mbps"]
    else:
        pick = ok_runs[0]
        mbps = pick["mbps"]

    used = pick.get("provider_used") or pick.get("provider") or prov
    prov_label = providers.get(used, providers.get(prov, {})).get("label", prov)

    out: dict[str, Any] = {
        "ok": True,
        "mbps": mbps,
        "bytes": pick.get("bytes"),
        "seconds": pick.get("seconds"),
        "human": f"{mbps:.1f} Mbps down ({meth}, {prof['label']})",
        "url": pick.get("url"),
        "profile": profile_key,
        "profile_label": prof["label"],
        "method": meth,
        "provider": used,
        "provider_label": prov_label,
        "warmup": bool(warmup),
        "geo": dict(geo),
        "runs": [dict(r) for r in runs if isinstance(r, dict)],
        "run_count": len(ok_runs),
        "note": "Download test through your current route (VPN if connected).",
    }
    if meth == "average" and len(ok_runs) > 1:
        spread = [r["mbps"] for r in ok_runs]
        out["human"] = f"{mbps:.1f} Mbps avg ({min(spread):.1f}–{max(spread):.1f}) · {prof['label']}"
    return out


def speedtest_api_payload(
    result: dict[str, Any],
    *,
    meta: dict[str, Any] | None = None,
    save: bool = True,
) -> dict[str, Any]:
    """Build a JSON-safe API body (no shared refs that break json.dumps)."""
    from nordctl.speedtest_store import LOG_FILE, append_result

    runs = [dict(r) for r in (result.get("runs") or []) if isinstance(r, dict)]
    out: dict[str, Any] = {
        "ok": bool(result.get("ok")),
        "mbps": result.get("mbps"),
        "bytes": result.get("bytes"),
        "seconds": result.get("seconds"),
        "human": result.get("human"),
        "url": result.get("url"),
        "profile": result.get("profile"),
        "profile_label": result.get("profile_label"),
        "method": result.get("method"),
        "provider": result.get("provider"),
        "provider_label": result.get("provider_label"),
        "warmup": bool(result.get("warmup")),
        "geo": dict(result.get("geo") or {}),
        "runs": runs,
        "run_count": result.get("run_count"),
        "note": result.get("note"),
    }
    if not out["ok"]:
        if result.get("error"):
            out["error"] = str(result.get("error"))
        if result.get("manual"):
            out["manual"] = str(result.get("manual"))
        return out
    if save:
        m = meta or {}
        save_row = {
            **{k: out[k] for k in (
                "mbps", "bytes", "seconds", "human", "url", "profile", "profile_label",
                "method", "provider", "provider_label", "warmup",
            )},
            "vpn": bool(m.get("vpn")),
            "route": str(m.get("route") or ""),
            "dns": str(m.get("dns") or ""),
            "dns_label": str(m.get("dns_label") or "DNS"),
        }
        out["saved"] = append_result(save_row)
        out["saved_path"] = str(LOG_FILE)
    return out
