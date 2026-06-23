"""Parse security scan output and email results via user SMTP."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config

_SCAN_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("lynis", re.compile(r"\blynis\b", re.I)),
    ("rkhunter", re.compile(r"\brkhunter\b", re.I)),
    ("chkrootkit", re.compile(r"\bchkrootkit\b", re.I)),
    ("clamav", re.compile(r"\bclamscan\b", re.I)),
    ("nmap", re.compile(r"\bnmap\b", re.I)),
    ("fail2ban", re.compile(r"\bfail2ban-client\b", re.I)),
    ("debsecan", re.compile(r"\bdebsecan\b", re.I)),
    ("trivy", re.compile(r"\btrivy\b", re.I)),
)

_COMPLETION_MARKERS: dict[str, tuple[str, ...]] = {
    "lynis": ("hardening index", "lynis security scan details", "audit summary"),
    "rkhunter": ("rootkit hunter check completed", "rkhunter check finished", "warning count"),
    "chkrootkit": ("chkrootkit",),
    "clamav": ("scan summary", "infected files", "-----------"),
    "nmap": ("nmap scan report", "done:"),
    "fail2ban": ("status for", "jail list"),
    "debsecan": ("debsecan",),
    "trivy": ("total:", "report:"),
}


def identify_scan(cmd: str) -> str | None:
    text = (cmd or "").strip()
    if not text:
        return None
    for scan_id, pattern in _SCAN_PATTERNS:
        if pattern.search(text):
            return scan_id
    return None


def scan_output_complete(scan_id: str, output: str) -> bool:
    if not output or not output.strip():
        return False
    low = output.lower()
    if scan_id == "lynis" and re.search(r"hardening index\s*:\s*\[?\d+", low):
        return True
    if len(output.strip()) < 80:
        return False
    markers = _COMPLETION_MARKERS.get(scan_id) or (scan_id,)
    if any(m in low for m in markers):
        return True
    if scan_id == "rkhunter" and "rkhunter" in low and len(output) > 400:
        return True
    if scan_id == "chkrootkit" and len(output) > 200:
        return True
    return False


def _scan_email_defaults() -> dict[str, Any]:
    return {
        "enabled": True,
        "email_on_findings": True,
        "email_on_failure": True,
        "email_always": False,
        "lynis_min_score_alert": 65,
    }


def scan_email_settings(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ac = cfg.get("alerts") or {}
    email = ac.get("email") or {}
    raw = ac.get("scan_email") if isinstance(ac.get("scan_email"), dict) else {}
    out = {**_scan_email_defaults(), **raw}
    out["smtp_ready"] = bool(
        email.get("enabled")
        and str(email.get("smtp_host") or "").strip()
        and str(email.get("to") or "").strip()
    )
    return out


def _parse_lynis(output: str) -> dict[str, Any]:
    score = None
    for pat in (
        r"Hardening index\s*:\s*\[(\d+)\]",
        r"Hardening_index=(\d+)",
        r"Hardening index[:\s]+(\d+)",
    ):
        m = re.search(pat, output, re.I)
        if m:
            score = int(m.group(1))
            break
    warnings = len(re.findall(r"^\s*!\s", output, re.M))
    suggestions = len(re.findall(r"^\s*\[\s*\]\s", output, re.M))
    highlights: list[str] = []
    for line in output.splitlines():
        s = line.strip()
        if s.startswith("!") or (s.startswith("[") and "]" in s[:4]):
            if len(highlights) < 10:
                highlights.append(s[:180])
    has_findings = warnings > 0 or suggestions > 0
    summary = f"Lynis score {score if score is not None else '?'} — {warnings} warnings, {suggestions} suggestions"
    return {
        "has_findings": has_findings,
        "score": score,
        "warnings": warnings,
        "suggestions": suggestions,
        "highlights": highlights,
        "summary": summary,
    }


def _parse_rkhunter(output: str) -> dict[str, Any]:
    warnings = len(re.findall(r"warning", output, re.I))
    has_findings = warnings > 0
    return {
        "has_findings": has_findings,
        "warnings": warnings,
        "summary": f"rkhunter — {warnings} warning line(s)" if has_findings else "rkhunter — no warnings reported",
    }


def _parse_chkrootkit(output: str) -> dict[str, Any]:
    infected = sum(
        1
        for ln in output.splitlines()
        if "infected" in ln.lower() and "not infected" not in ln.lower()
    )
    suspicious = len(re.findall(r"suspicious", output, re.I))
    has_findings = infected > 0 or suspicious > 0
    parts = []
    if infected:
        parts.append(f"{infected} infected")
    if suspicious:
        parts.append(f"{suspicious} suspicious")
    summary = f"chkrootkit — {', '.join(parts)}" if parts else "chkrootkit — no infected lines reported"
    return {"has_findings": has_findings, "infected": infected, "suspicious": suspicious, "summary": summary}


def _parse_clamav(output: str) -> dict[str, Any]:
    infected = len(re.findall(r"FOUND$", output, re.M))
    has_findings = infected > 0
    return {
        "has_findings": has_findings,
        "infected": infected,
        "summary": f"ClamAV — {infected} infected file(s)" if has_findings else "ClamAV — no infected files",
    }


def _parse_nmap(output: str) -> dict[str, Any]:
    open_ports = len(re.findall(r"^\d+/tcp\s+open", output, re.M))
    has_findings = open_ports > 0
    return {
        "has_findings": has_findings,
        "open_ports": open_ports,
        "summary": f"nmap — {open_ports} open TCP port(s)" if has_findings else "nmap — no open ports in scan output",
    }


def _parse_fail2ban(output: str) -> dict[str, Any]:
    banned = 0
    for m in re.finditer(r"Currently banned:\s*(\d+)", output, re.I):
        banned += int(m.group(1))
    has_findings = banned > 0
    return {
        "has_findings": has_findings,
        "banned": banned,
        "summary": f"fail2ban — {banned} banned IP(s)" if has_findings else "fail2ban — no banned IPs",
    }


def _parse_generic(output: str, label: str) -> dict[str, Any]:
    err_markers = ("error:", "failed", "not found", "command not found", "password is required")
    low = output.lower()
    has_findings = any(m in low for m in err_markers) and "0 warning" not in low
    return {
        "has_findings": has_findings,
        "summary": f"{label} finished — review output in nordctl activity log",
    }


_PARSERS = {
    "lynis": _parse_lynis,
    "rkhunter": _parse_rkhunter,
    "chkrootkit": _parse_chkrootkit,
    "clamav": _parse_clamav,
    "nmap": _parse_nmap,
    "fail2ban": _parse_fail2ban,
}


def parse_scan_result(scan_id: str, output: str, *, ok: bool = True) -> dict[str, Any]:
    label = scan_id.replace("_", " ").title()
    parser = _PARSERS.get(scan_id)
    parsed = parser(output) if parser else _parse_generic(output, label)
    parsed["scan_id"] = scan_id
    parsed["ok"] = ok
    parsed["label"] = label
    return parsed


def _should_email_scan(scan_id: str, parsed: dict[str, Any], cfg: dict[str, Any]) -> bool:
    ac = cfg.get("alerts") or {}
    email = ac.get("email") or {}
    if not email.get("enabled"):
        return False
    settings = scan_email_settings(cfg)
    if not settings.get("enabled"):
        return False

    if not parsed.get("ok") and settings.get("email_on_failure", True):
        return True

    if settings.get("email_on_findings", True) and parsed.get("has_findings"):
        return True

    if scan_id == "lynis":
        if settings.get("email_always"):
            return True
        score = parsed.get("score")
        min_score = int(settings.get("lynis_min_score_alert") or 65)
        if score is not None and score < min_score:
            return True

    return False


def _scan_last_dir() -> Path:
    path = config_dir() / "scan-last"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _save_scan_last(scan_id: str, payload: dict[str, Any]) -> None:
    data = {**payload, "finished": time.strftime("%Y-%m-%dT%H:%M:%S")}
    try:
        (_scan_last_dir() / f"{scan_id}.json").write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError:
        pass


def _email_body(scan_id: str, parsed: dict[str, Any], output: str, label: str) -> str:
    host = os.uname().nodename
    lines = [
        f"Scan: {label or scan_id}",
        f"Host: {host}",
        f"Summary: {parsed.get('summary') or 'See output below'}",
        "",
    ]
    highlights = parsed.get("highlights") or []
    if highlights:
        lines.append("Highlights:")
        lines.extend(f"  {h}" for h in highlights[:8])
        lines.append("")
    tail = (output or "").strip()[-3500:]
    if tail:
        lines.extend(["--- output (tail) ---", tail, ""])
    lines.append("Open nordctl → Tools → Activity log for the full run.")
    return "\n".join(lines)


def maybe_email_scan_result(
    cmd: str,
    output: str,
    *,
    ok: bool = True,
    label: str = "",
    cfg: dict[str, Any] | None = None,
    scan_id: str | None = None,
) -> dict[str, Any]:
    """If cmd looks like a security scan, parse output and email when configured."""
    cfg = cfg or load_config()
    scan_id = scan_id or identify_scan(cmd)
    if not scan_id:
        return {"ok": True, "skipped": True, "reason": "not a scan command"}

    parsed = parse_scan_result(scan_id, output or "", ok=ok)
    _save_scan_last(scan_id, parsed)

    if not _should_email_scan(scan_id, parsed, cfg):
        return {
            "ok": True,
            "skipped": True,
            "scan_id": scan_id,
            "summary": parsed.get("summary"),
            "reason": "email not configured for this result",
        }

    from nordctl.alerts import send_email_alert

    title = parsed.get("summary") or f"{scan_id} scan finished"
    if not parsed.get("ok"):
        title = f"{scan_id} scan failed"
    body = _email_body(scan_id, parsed, output or "", label or str(parsed.get("label") or scan_id))
    mail = send_email_alert(title, body, cfg, rule_id=f"scan:{scan_id}")
    return {
        "ok": bool(mail.get("ok")),
        "scan_id": scan_id,
        "summary": parsed.get("summary"),
        "emailed": bool(mail.get("ok")),
        "email": mail,
    }
