"""Web UI bind address — local loopback vs home LAN (192.168.x, 10.x, …)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import ipaddress
import re
import subprocess
from typing import Any

from nordctl.config import load_config, save_config
from nordctl.paths import resolve_nordctl_bin

LOOPBACK_BINDS = frozenset({"127.0.0.1", "localhost", "::1"})
ALL_INTERFACE_BINDS = frozenset({"0.0.0.0", "::", ""})


def _server_bind_port(cfg: dict[str, Any]) -> tuple[str, int]:
    srv = cfg.get("server") or {}
    bind = str(srv.get("bind") or "127.0.0.1").strip()
    port = int(srv.get("port") or 8765)
    return bind, port


def infer_access_mode(bind: str) -> str:
    b = (bind or "127.0.0.1").strip()
    if b in LOOPBACK_BINDS:
        return "local"
    if b in ALL_INTERFACE_BINDS:
        return "lan"
    return "custom"


def _subnet_hint(ip: str) -> str:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return "LAN"
    if addr in ipaddress.ip_network("10.0.0.0/8"):
        return "10.x private"
    if addr in ipaddress.ip_network("172.16.0.0/12"):
        return "172.16–31 private"
    if addr in ipaddress.ip_network("192.168.0.0/16"):
        return "192.168.x private"
    if addr.is_link_local:
        return "link-local"
    return "private LAN"


def list_lan_ips() -> list[dict[str, str]]:
    """IPv4 addresses on up interfaces — typical home/office LAN ranges."""
    try:
        r = subprocess.run(
            ["ip", "-4", "-br", "addr"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        lines = (r.stdout or "").splitlines()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        lines = []

    found: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in lines:
        parts = line.split()
        if len(parts) < 3:
            continue
        iface, state = parts[0], parts[1]
        if state.upper() == "DOWN":
            continue
        for m in re.finditer(r"(\d+\.\d+\.\d+\.\d+)/", line):
            ip = m.group(1)
            try:
                addr = ipaddress.ip_address(ip)
            except ValueError:
                continue
            if not addr.is_private or addr.is_loopback or ip in seen:
                continue
            seen.add(ip)
            found.append(
                {
                    "iface": iface,
                    "ip": ip,
                    "subnet_hint": _subnet_hint(ip),
                }
            )
    return found


def _ip_on_machine(ip: str) -> bool:
    return any(row["ip"] == ip for row in list_lan_ips())


def dashboard_urls(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bind, port = _server_bind_port(cfg)
    mode = infer_access_mode(bind)
    lan_ips = list_lan_ips()

    this_browser = f"http://127.0.0.1:{port}/"
    primary = this_browser
    lan_urls: list[str] = []

    if mode == "local":
        primary = this_browser
    elif mode == "lan":
        primary = this_browser
        lan_urls = [f"http://{row['ip']}:{port}/" for row in lan_ips]
    elif mode == "custom":
        primary = f"http://{bind}:{port}/"
        lan_urls = [primary]

    return {
        "this_browser": this_browser,
        "primary": primary,
        "lan": lan_urls,
        "mode": mode,
        "bind": bind,
        "port": port,
    }


def network_access_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    bind, port = _server_bind_port(cfg)
    mode = str((cfg.get("server") or {}).get("access_mode") or infer_access_mode(bind))
    if mode not in {"local", "lan", "custom"}:
        mode = infer_access_mode(bind)

    urls = dashboard_urls(cfg)
    loopback_only = mode == "local"
    lan_ips = list_lan_ips()
    bin_path = resolve_nordctl_bin()

    warnings: list[str] = []
    if mode == "lan":
        warnings.extend(
            [
                "LAN mode is ON — phones, tablets, and other PCs on your WiFi or wired network can open this dashboard.",
                "The Terminal tab is a full bash shell. Use “This computer only” on shared or untrusted networks.",
            ]
        )
    elif mode == "custom":
        warnings.append(
            f"Dashboard listens on {bind}:{port} — only clients that can reach that address on your LAN can connect."
        )

    next_steps: list[str] = []
    if mode == "local":
        next_steps.append("Open this dashboard only on this PC — other devices cannot connect.")
    elif mode == "lan" and lan_ips:
        sample = lan_ips[0]["ip"]
        next_steps.append(
            f"After restart, on another device on the same network open http://{sample}:{port}/ "
            "(use your PC’s LAN IP from the list above)."
        )
    elif mode == "custom":
        next_steps.append(f"On another device, open http://{bind}:{port}/ if routing allows it.")

    return {
        "ok": True,
        "mode": mode,
        "bind": bind,
        "port": port,
        "loopback_only": loopback_only,
        "lan_enabled": not loopback_only,
        "lan_ips": lan_ips,
        "urls": urls,
        "warnings": warnings,
        "next_steps": next_steps,
        "restart_command": f"{bin_path} service restart",
        "manual_serve": f"{bin_path} serve --bind {bind} --port {port}",
    }


def apply_network_access(
    cfg: dict[str, Any],
    *,
    mode: str,
    bind: str | None = None,
    restart_service: bool = False,
) -> dict[str, Any]:
    mode = (mode or "local").strip().lower()
    old_bind, _ = _server_bind_port(cfg)

    if mode == "local":
        new_bind = "127.0.0.1"
    elif mode == "lan":
        new_bind = "0.0.0.0"
    elif mode == "custom":
        ip = (bind or "").strip()
        if not ip:
            return {
                "ok": False,
                "error": "Pick a LAN IP from the dropdown, or switch to “Home LAN” mode.",
            }
        if not _ip_on_machine(ip):
            return {
                "ok": False,
                "error": f"{ip} is not assigned to this machine right now. Run ip addr or pick another address.",
            }
        new_bind = ip
    else:
        return {"ok": False, "error": f"Unknown access mode: {mode}"}

    srv = cfg.setdefault("server", {})
    srv["bind"] = new_bind
    srv["access_mode"] = mode
    save_config(cfg)

    from nordctl.service_mgr import control_ui_service, write_ui_unit

    write_ui_unit(cfg)

    restart_result: dict[str, Any] | None = None
    if restart_service:
        restart_result = control_ui_service("restart", cfg)

    payload = network_access_payload(cfg)
    changed = old_bind != new_bind
    steps = [
        f"Saved listen address: {new_bind}:{payload['port']}",
        "Restart the nordctl UI so the new address takes effect.",
    ]
    if restart_service and restart_result and restart_result.get("ok"):
        steps.append("UI service restarted.")
    elif restart_service and restart_result and not restart_result.get("ok"):
        steps.append(restart_result.get("error") or "Restart failed — run the restart command manually.")

    return {
        "ok": True,
        "changed": changed,
        "mode": mode,
        "bind": new_bind,
        "restart": restart_result,
        "steps": steps,
        "human": payload["warnings"][0] if payload.get("warnings") and mode != "local" else (
            "Dashboard is local-only again." if mode == "local" and changed else "Network access unchanged."
        ),
        **payload,
    }
