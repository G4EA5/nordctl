"""UFW firewall control for nordctl dashboard (read + manage with passwordless sudo)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import ipaddress
import os
import re
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from nordctl.config import load_config
from nordctl.paths import UFW_SUDOERS_SCRIPT, install_script_path

_UFW_STATUS_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_UFW_STATUS_TTL = float(os.environ.get("UFW_STATUS_TTL", "20"))

UFW_BIN = os.environ.get("UFW_BIN", "/usr/sbin/ufw")
INSTALL_SCRIPT = install_script_path(UFW_SUDOERS_SCRIPT)
SUDOERS_FILE = Path("/etc/sudoers.d/nordctl-ufw")

# Rakuten Viber desktop — inbound TCP+UDP (https://help.viber.com/hc/en-us/articles/8805123374365)
VIBER_PORTS = (80, 443, 4244, 5242, 5243, 7985)


def _ufw_succeeded(result: dict[str, Any]) -> bool:
    if result.get("ok"):
        return True
    out = (result.get("output") or "").lower()
    return any(
        phrase in out
        for phrase in (
            "is active",
            "already enabled",
            "firewall is active",
            "rules updated",
            "skipping adding existing rule",
        )
    )


def _sudo_nopasswd_ok() -> bool:
    try:
        r = subprocess.run(
            ["sudo", "-n", UFW_BIN, "status", "numbered"],
            capture_output=True,
            text=True,
            timeout=4,
        )
        out = ((r.stdout or "") + (r.stderr or "")).strip().lower()
        if r.returncode == 0:
            return True
        return "status: active" in out or "status: inactive" in out
    except (OSError, subprocess.TimeoutExpired):
        return False


def _ufw_sudoers_installed() -> bool:
    return SUDOERS_FILE.is_file()


def _ufw_setup_note() -> str:
    script = str(INSTALL_SCRIPT)
    if not _ufw_sudoers_installed():
        return (
            "One-time setup (run in terminal as your user — not from a root shell):\n"
            f"sudo bash {script}\n\n"
            "Then restart the nordctl UI (Firewall tab → refresh, or restart nordctl serve)."
        )
    if not _sudo_nopasswd_ok():
        return (
            "UFW sudoers file exists but passwordless sudo is not active in this session.\n"
            "Log out and back in, or run: newgrp sudo\n"
            "Then restart nordctl serve and click ↻ Refresh on the Firewall tab."
        )
    return ""


def run_ufw(args: list[str], timeout: float = 12.0) -> dict[str, Any]:
    ufw = UFW_BIN if Path(UFW_BIN).is_file() else "ufw"
    attempts = (
        ["sudo", "-n", ufw, *args],
        [ufw, *args],
    )
    last: dict[str, Any] = {"ok": False, "code": -1, "output": "", "args": args}
    for cmd in attempts:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            out = ((r.stdout or "") + (r.stderr or "")).strip()
            entry = {"ok": r.returncode == 0, "code": r.returncode, "output": out, "args": args}
            last = entry
            if _ufw_succeeded(entry) or out:
                entry["ok"] = _ufw_succeeded(entry)
                return entry
        except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
            last = {"ok": False, "code": -1, "output": str(exc), "args": args}
    return last


def parse_rule_line(line: str, number: int | None = None) -> dict[str, Any]:
    raw = line.strip()
    comment = ""
    if "#" in raw:
        raw, _, comment = raw.partition("#")
        comment = comment.strip()
    rule_line = " ".join(raw.split())
    action = (
        "ALLOW"
        if "ALLOW" in rule_line
        else ("DENY" if "DENY" in rule_line else "REJECT" if "REJECT" in rule_line else "")
    )
    return {
        "number": number,
        "line": rule_line,
        "comment": comment,
        "action": action,
    }


def _store_ufw_status(data: dict[str, Any]) -> dict[str, Any]:
    _UFW_STATUS_CACHE["ts"] = time.time()
    _UFW_STATUS_CACHE["data"] = data
    return data


def ufw_status() -> dict[str, Any]:
    now = time.time()
    cached = _UFW_STATUS_CACHE.get("data")
    if cached and now - float(_UFW_STATUS_CACHE.get("ts") or 0) < _UFW_STATUS_TTL:
        return cached

    if not Path(UFW_BIN).is_file() and not __import__("shutil").which("ufw"):
        return _store_ufw_status(
            {
                "available": False,
                "installed": False,
                "enabled": False,
                "default_in": "",
                "default_out": "",
                "rules": [],
                "rule_count": 0,
                "can_manage": False,
                "note": "UFW is not installed — install it from Network → Package tools → Security.",
            }
        )

    text = ""
    for args in (["status", "numbered"], ["status", "verbose"], ["status"]):
        r = run_ufw(args, timeout=5)
        if r.get("ok") and r.get("output"):
            text = r["output"]
            break
    if text and not re.search(r"^\[\s*\d+\]", text, re.MULTILINE):
        r_num = run_ufw(["status", "numbered"], timeout=5)
        if r_num.get("ok") and r_num.get("output"):
            text = r_num["output"]

    if not text:
        return _store_ufw_status(
            {
                "available": True,
                "installed": True,
                "enabled": False,
                "default_in": "",
                "default_out": "",
                "rules": [],
                "rule_count": 0,
                "can_manage": False,
                "note": _ufw_setup_note() or "UFW status unreadable — check sudo setup.",
            }
        )

    active = "Status: active" in text
    default_in = default_out = ""
    for line in text.splitlines():
        low = line.lower()
        if low.startswith("default:"):
            if "deny (incoming)" in low or "deny (in)" in low:
                default_in = "deny"
            elif "allow (incoming)" in low:
                default_in = "allow"
            if "allow (outgoing)" in low or "allow (out)" in low:
                default_out = "allow"
            elif "deny (outgoing)" in low:
                default_out = "deny"

    rules: list[dict[str, Any]] = []
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("Status:") or s.startswith("Default:") or s.startswith("Logging:"):
            continue
        if s.startswith("To ") or s.startswith("--"):
            continue
        num_m = re.match(r"^\[\s*(\d+)\]\s*(.+)$", s)
        if num_m:
            rules.append(parse_rule_line(num_m.group(2), int(num_m.group(1))))
        elif "ALLOW" in s or "DENY" in s or "REJECT" in s:
            rules.append(parse_rule_line(s))

    probe = run_ufw(["status", "numbered"], timeout=4)
    out = probe.get("output") or ""
    can_manage = (
        _sudo_nopasswd_ok()
        and _ufw_succeeded(probe)
        and "ERROR" not in out
        and "need to be root" not in out.lower()
    )
    note = _ufw_setup_note() if not can_manage else ""

    return _store_ufw_status(
        {
            "available": True,
            "installed": True,
            "enabled": active,
            "default_in": default_in,
            "default_out": default_out,
            "rules": rules,
            "rule_count": len(rules),
            "can_manage": can_manage,
            "note": note,
            "install_script": str(INSTALL_SCRIPT),
        }
    )


def _valid_port(port: str) -> bool:
    port = port.strip()
    if re.fullmatch(r"\d{1,5}", port):
        return 1 <= int(port) <= 65535
    if re.fullmatch(r"\d{1,5}:\d{1,5}", port):
        a, b = port.split(":", 1)
        return 1 <= int(a) <= 65535 and 1 <= int(b) <= 65535 and int(a) <= int(b)
    return False


def _valid_cidr(value: str) -> bool:
    value = value.strip()
    try:
        if "/" in value:
            ipaddress.ip_network(value, strict=False)
        else:
            ipaddress.ip_address(value)
        return True
    except ValueError:
        return False


def _sanitize_comment(comment: str) -> str:
    return re.sub(r"[^\w\s\-./]", "", comment or "").strip()[:64]


def build_allow_args(body: dict[str, Any]) -> list[str]:
    port = str(body.get("port") or "").strip()
    proto = str(body.get("proto") or "tcp").strip().lower()
    from_addr = str(body.get("from") or "").strip()
    comment = _sanitize_comment(str(body.get("comment") or ""))

    args: list[str]
    if from_addr and port:
        if not _valid_cidr(from_addr) or not _valid_port(port):
            raise ValueError("invalid from or port")
        if proto in ("both", "tcpudp", "all"):
            args = ["allow", "from", from_addr, "to", "any", "port", port]
        else:
            args = ["allow", "from", from_addr, "to", "any", "port", port, "proto", proto]
    elif from_addr:
        if not _valid_cidr(from_addr):
            raise ValueError("invalid from address")
        args = ["allow", "from", from_addr]
    elif port:
        if not _valid_port(port):
            raise ValueError("invalid port")
        if proto in ("both", "tcpudp", "all"):
            r1 = run_ufw(["allow", f"{port}/tcp"] + (["comment", comment] if comment else []))
            r2 = run_ufw(["allow", f"{port}/udp"] + (["comment", comment] if comment else []))
            if not r1.get("ok") and not r2.get("ok"):
                raise ValueError(r1.get("output") or r2.get("output") or "allow failed")
            return []
        args = ["allow", f"{port}/{proto}"]
    else:
        raise ValueError("port or from required")

    if comment:
        args.extend(["comment", comment])
    return args


def _viber_rule_args() -> list[list[str]]:
    return [
        ["allow", f"{port}/{proto}", "comment", "Viber"]
        for port in VIBER_PORTS
        for proto in ("tcp", "udp")
    ]


def _preset_rule_lists(spec: dict[str, Any]) -> list[list[str]]:
    rules = spec.get("rules")
    if rules:
        return [list(r) for r in rules]
    args = spec.get("args")
    return [list(args)] if args else []


def _rule_lines(rules: list[dict[str, Any]]) -> list[str]:
    return [(rule.get("line") or "").lower() for rule in rules]


def _port_proto_allowed(lines: list[str], port: int, proto: str) -> bool:
    needle = f"{port}/{proto}"
    return any(needle in line for line in lines)


def _preset_defs(cfg: dict[str, Any]) -> dict[str, dict[str, Any]]:
    lan = str(cfg.get("lan_allowlist_cidr") or "192.168.0.0/16")
    port = int((cfg.get("server") or {}).get("port") or 8765)
    return {
        "ssh": {
            "args": ["allow", "22/tcp", "comment", "SSH"],
            "label": "SSH",
            "detail": "Allow TCP 22 from anywhere",
        },
        "lan": {
            "args": ["allow", "from", lan, "comment", "Home LAN"],
            "label": "Home LAN",
            "detail": f"Allow all from {lan}",
        },
        "meshnet": {
            "args": ["allow", "in", "on", "nordlynx", "comment", "Meshnet"],
            "label": "Meshnet in",
            "detail": "Allow inbound on nordlynx interface",
        },
        "ui": {
            "args": ["allow", f"{port}/tcp", "comment", "nordctl UI"],
            "label": "nordctl UI",
            "detail": f"Allow TCP {port} (dashboard port from config)",
        },
        "viber": {
            "rules": _viber_rule_args(),
            "label": "Viber",
            "detail": (
                "Allow inbound TCP+UDP on Viber desktop ports "
                f"({', '.join(str(p) for p in VIBER_PORTS)}) — calls and messaging on strict UFW"
            ),
        },
    }


def preset_catalog(cfg: dict[str, Any] | None = None, rules: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    defs = _preset_defs(cfg)
    if rules is None:
        rules = ufw_status().get("rules") or []
    lines = _rule_lines(rules)
    out: list[dict[str, Any]] = []
    for preset_id, spec in defs.items():
        exists = False
        if preset_id == "ssh":
            exists = any(re.search(r"\b22/tcp\b", line) for line in lines)
        elif preset_id == "lan":
            exists = any(str(defs["lan"]["args"][2]).lower() in line for line in lines)
        elif preset_id == "meshnet":
            exists = any("nordlynx" in line for line in lines)
        elif preset_id == "ui":
            ui_port = str(int((cfg.get("server") or {}).get("port") or 8765))
            exists = any(re.search(rf"\b{re.escape(ui_port)}/tcp\b", line) for line in lines)
        elif preset_id == "viber":
            exists = all(
                _port_proto_allowed(lines, port, proto)
                for port in VIBER_PORTS
                for proto in ("tcp", "udp")
            )
        out.append(
            {
                "id": preset_id,
                "label": spec["label"],
                "detail": spec["detail"],
                "exists": exists,
            }
        )
    return out


def apply_action(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    action = str(body.get("action") or "").strip().lower()
    _UFW_STATUS_CACHE["ts"] = 0

    if action == "enable":
        r = run_ufw(["--force", "enable"])
    elif action == "disable":
        r = run_ufw(["disable"])
    elif action == "reload":
        r = run_ufw(["reload"])
    elif action == "allow":
        try:
            args = build_allow_args(body)
            r = run_ufw(args) if args else {"ok": True, "output": "allowed tcp+udp"}
        except ValueError as exc:
            return {"ok": False, "error": str(exc), "state": get_state(cfg)}
    elif action == "delete":
        num = body.get("number")
        if num is None:
            return {"ok": False, "error": "number required", "state": get_state(cfg)}
        r = run_ufw(["--force", "delete", str(int(num))])
    elif action == "preset":
        preset = str(body.get("preset") or "").strip().lower()
        defs = _preset_defs(cfg)
        if preset not in defs:
            return {"ok": False, "error": f"unknown preset: {preset}", "state": get_state(cfg)}
        rule_lists = _preset_rule_lists(defs[preset])
        results: list[dict[str, Any]] = []
        skipped = 0
        failed: list[str] = []
        for args in rule_lists:
            entry = run_ufw(args)
            results.append(entry)
            out = (entry.get("output") or "").lower()
            if "skipping adding existing rule" in out:
                skipped += 1
            elif not _ufw_succeeded(entry):
                failed.append((entry.get("output") or "allow failed").strip())
        if failed:
            err = failed[0]
            if len(failed) > 1:
                err = f"{err}\n(+ {len(failed) - 1} more failed rule(s))"
            return {"ok": False, "error": err, "message": err, "state": get_state(cfg), "result": results[-1]}
        if skipped == len(rule_lists):
            state = get_state(cfg)
            from nordctl.activity_log import record_event

            record_event(
                "security",
                "UFW preset",
                detail=f"{defs[preset]['label']} — all rules already exist.",
                level="info",
                ok=True,
                meta={"ufw_action": "preset", "preset": preset},
            )
            return {
                "ok": True,
                "skipped": True,
                "message": f"{defs[preset]['label']} — all rules already exist.",
                "state": state,
            }
        added = len(rule_lists) - skipped
        msg = f"{defs[preset]['label']} — added {added} rule(s)."
        if skipped:
            msg += f" Skipped {skipped} existing."
        state = get_state(cfg)
        from nordctl.activity_log import record_event

        record_event(
            "security",
            "UFW preset",
            detail=msg,
            level="info",
            ok=True,
            meta={"ufw_action": "preset", "preset": preset},
        )
        return {"ok": True, "message": msg, "state": state}
    else:
        return {"ok": False, "error": f"unknown action: {action}", "state": get_state(cfg)}

    ok = _ufw_succeeded(r)
    state = get_state(cfg)
    out = (r.get("output") or "").strip()
    if ok:
        from nordctl.activity_log import record_event

        record_event(
            "security",
            f"UFW {action}",
            detail=out[:500],
            level="info",
            ok=True,
            meta={"ufw_action": action},
        )
        return {"ok": True, "message": out.splitlines()[0] if out else f"UFW {action} OK", "result": r, "state": state}
    manual = state.get("status", {}).get("install_script") or str(INSTALL_SCRIPT)
    err = out or "UFW command failed"
    if "need to be root" in err.lower() or "password" in err.lower():
        err = (
            f"{err}\n\nRun passwordless sudo setup, then restart nordctl serve:\n"
            f"sudo bash {manual}"
        )
    return {"ok": False, "result": r, "state": state, "error": err, "message": err, "manual": f"sudo bash {manual}"}


def get_state(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    status = ufw_status()
    host = {
        "hostname": socket.gethostname(),
        "label": "This machine",
    }
    return {
        "ok": status.get("available", False) or status.get("installed", False),
        "host": host,
        "status": status,
        "presets": preset_catalog(cfg, status.get("rules") or []),
    }
