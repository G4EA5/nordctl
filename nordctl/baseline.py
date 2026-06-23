"""One-time install baseline — backup everything nordctl can change, restore to pre-nordctl state."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nordctl import network_linux as net
from nordctl import nordvpn as nv
from nordctl.config import config_dir, config_path, load_config
from nordctl.files import user_presets_dir

BASELINE_DIRNAME = "baseline"
MANIFEST_NAME = "manifest.json"


def baseline_dir() -> Path:
    return config_dir() / BASELINE_DIRNAME


def manifest_path() -> Path:
    return baseline_dir() / MANIFEST_NAME


def baseline_exists() -> bool:
    return manifest_path().is_file()


def _run(argv: list[str], timeout: float = 20.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _list_nm_wifi_profiles(extra: list[str] | None = None) -> list[str]:
    names: list[str] = []
    ok, out = _run(["nmcli", "-t", "-f", "NAME,TYPE", "connection", "show"], timeout=12)
    if ok:
        for line in out.splitlines():
            if ":" not in line:
                continue
            name, typ = line.split(":", 1)
            if typ.strip() in ("802-11-wireless", "wifi"):
                n = name.strip()
                if n and n not in names:
                    names.append(n)
    for n in extra or []:
        if n and n not in names:
            names.append(n)
    return names


def _nm_dump(profile: str) -> dict[str, str]:
    fields = ("ipv4.dns", "ipv4.ignore-auto-dns", "ipv6.method", "ipv4.method")
    data: dict[str, str] = {"name": profile}
    for field in fields:
        ok, val = _run(["nmcli", "-g", field, "connection", "show", profile], timeout=8)
        data[field] = val.strip() if ok else ""
    return data


def _read_ipv6_sysctl() -> dict[str, str]:
    keys = (
        "net.ipv6.conf.all.disable_ipv6",
        "net.ipv6.conf.default.disable_ipv6",
        "net.ipv6.conf.lo.disable_ipv6",
    )
    out: dict[str, str] = {}
    for key in keys:
        proc = Path("/proc/sys") / Path(key.replace(".", "/"))
        try:
            out[key] = proc.read_text(encoding="utf-8").strip()
        except OSError:
            out[key] = ""
    return out


def _copy_if_readable(src: Path, dest: Path) -> bool:
    try:
        if src.is_file() or src.is_symlink():
            dest.parent.mkdir(parents=True, exist_ok=True)
            if src.is_symlink():
                dest.write_text(str(src.readlink()), encoding="utf-8")
                dest.with_suffix(dest.suffix + ".symlink").write_text("symlink", encoding="utf-8")
            else:
                shutil.copy2(src, dest)
            return True
    except OSError:
        pass
    return False


def baseline_status() -> dict[str, Any]:
    if not baseline_exists():
        return {
            "exists": False,
            "path": str(baseline_dir()),
            "message": "No install baseline yet — nordctl saves one automatically on first use, or click Create baseline on Tools → Rollback",
        }
    try:
        manifest = json.loads(manifest_path().read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        manifest = {}
    return {
        "exists": True,
        "path": str(baseline_dir()),
        "created": manifest.get("created"),
        "label": manifest.get("label", "install"),
        "components": manifest.get("components", []),
        "message": (
            "Install baseline saved on first use — restores config, Wi‑Fi DNS, Nord settings, and IPv6. "
            "Open Tools → Rollback to revert."
        ),
    }


def create_baseline(cfg: dict[str, Any] | None = None, *, force: bool = False, label: str = "install") -> dict[str, Any]:
    cfg = cfg or load_config()
    if baseline_exists() and not force:
        st = baseline_status()
        return {"ok": True, "created": False, "skipped": True, **st}

    root = baseline_dir()
    if force and root.is_dir():
        shutil.rmtree(root)
    root.mkdir(parents=True, exist_ok=True)

    components: list[str] = []
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")

    # config.yaml
    cfg_p = config_path()
    if cfg_p.is_file():
        shutil.copy2(cfg_p, root / "config.yaml")
        components.append("config.yaml")

    # user presets
    udir = user_presets_dir()
    bpresets = root / "presets"
    bpresets.mkdir(exist_ok=True)
    preset_count = 0
    for p in udir.glob("*.yaml"):
        shutil.copy2(p, bpresets / p.name)
        preset_count += 1
    if preset_count:
        components.append(f"presets ({preset_count})")

    # NordVPN CLI state
    nord_dir = root / "nordvpn"
    nord_dir.mkdir(exist_ok=True)
    if nv.available(bin_path):
        settings_r = nv.run(bin_path, ["settings"], timeout=12)
        status_r = nv.run(bin_path, ["status"], timeout=8)
        (nord_dir / "settings.txt").write_text(settings_r.get("output", ""), encoding="utf-8")
        (nord_dir / "status.txt").write_text(status_r.get("output", ""), encoding="utf-8")
        parsed = nv.parse_settings(settings_r.get("output", ""))
        (nord_dir / "parsed.json").write_text(json.dumps(parsed, indent=2), encoding="utf-8")
        components.append("NordVPN settings")
    else:
        (nord_dir / "settings.txt").write_text("# NordVPN not installed at baseline time\n", encoding="utf-8")

    # NetworkManager WiFi DNS per profile
    wifi = cfg.get("wifi") or {}
    profiles = _list_nm_wifi_profiles(list(wifi.get("profiles") or []))
    nm_dump = [_nm_dump(n) for n in profiles]
    net_dir = root / "network"
    net_dir.mkdir(exist_ok=True)
    (net_dir / "nm_profiles.json").write_text(json.dumps(nm_dump, indent=2), encoding="utf-8")
    if nm_dump:
        components.append(f"NetworkManager WiFi ({len(nm_dump)} profile(s))")

    # resolv.conf snapshot (read-only backup; restore needs sudo)
    resolv = Path("/etc/resolv.conf")
    if _copy_if_readable(resolv, net_dir / "resolv.conf"):
        components.append("resolv.conf snapshot")

    # IPv6 sysctl
    ipv6 = _read_ipv6_sysctl()
    (net_dir / "ipv6_sysctl.json").write_text(json.dumps(ipv6, indent=2), encoding="utf-8")
    components.append("IPv6 sysctl values")

    device = net.detect_wifi_device(wifi.get("device"))
    if device:
        ok, out = _run(["resolvectl", "status", device], timeout=6)
        if ok:
            (net_dir / "resolvectl_wifi.txt").write_text(out, encoding="utf-8")

    # systemd user units nordctl may write later (capture if any exist)
    systemd_dir = Path.home() / ".config" / "systemd" / "user"
    bsystemd = root / "systemd"
    bsystemd.mkdir(exist_ok=True)
    unit_names: list[str] = []
    if systemd_dir.is_dir():
        for p in systemd_dir.glob("nordctl-*"):
            if p.is_file():
                shutil.copy2(p, bsystemd / p.name)
                unit_names.append(p.name)
    (bsystemd / "index.json").write_text(json.dumps(unit_names, indent=2), encoding="utf-8")

    # tray autostart
    tray_desktop = Path.home() / ".config" / "autostart" / "nordctl-tray.desktop"
    btray = root / "tray"
    btray.mkdir(exist_ok=True)
    if tray_desktop.is_file():
        shutil.copy2(tray_desktop, btray / "nordctl-tray.desktop")
        components.append("tray autostart")

    manifest = {
        "created": datetime.now(tz=timezone.utc).isoformat(),
        "label": label,
        "version": 1,
        "components": components,
        "nordvpn_available": nv.available(bin_path),
        "wifi_profiles": profiles,
        "notes": [
            "Created automatically on first nordctl init / install.",
            "Restore puts back config, WiFi DNS, Nord settings, and IPv6 as captured here.",
            "resolv.conf is only restored if you run restore with sudo (optional, risky on some systems).",
        ],
    }
    manifest_path().write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "created": True,
        "path": str(root),
        "components": components,
        "created_at": manifest["created"],
        "message": "Install baseline saved — you can revert nordctl changes from Automate → Restore baseline",
    }


def ensure_baseline(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    """Create baseline once if missing (safe to call repeatedly)."""
    if baseline_exists():
        return {"ok": True, "created": False, **baseline_status()}
    return create_baseline(cfg, label="install")


def _apply_nord_settings(parsed: dict[str, Any], bin_path: str) -> list[dict[str, Any]]:
    from nordctl.snapshot import apply_parsed_settings

    return apply_parsed_settings(parsed, bin_path)


def restore_baseline(cfg: dict[str, Any] | None = None, *, restore_resolv: bool = False) -> dict[str, Any]:
    cfg = cfg or load_config()
    if not baseline_exists():
        return {"ok": False, "error": "No install baseline found — run nordctl baseline ensure first"}

    root = baseline_dir()
    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    steps: list[dict[str, Any]] = []

    # Safety copy of current config + Nord snapshot (does not overwrite install baseline)
    backups = config_dir() / "backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    if config_path().is_file():
        shutil.copy2(config_path(), backups / f"config-pre-restore-{stamp}.yaml")
    from nordctl.snapshot import capture_snapshot

    if nv.available(bin_path):
        capture_snapshot(label="pre-restore-auto", cfg=cfg)
    steps.append({"step": "pre_restore_backup", "ok": True, "path": str(backups)})

    bcfg = root / "config.yaml"
    if bcfg.is_file():
        dest = config_path()
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bcfg, dest)
        steps.append({"step": "config.yaml", "ok": True})

    bpresets = root / "presets"
    if bpresets.is_dir():
        udir = user_presets_dir()
        for p in udir.glob("*.yaml"):
            p.unlink(missing_ok=True)
        for p in bpresets.glob("*.yaml"):
            shutil.copy2(p, udir / p.name)
        steps.append({"step": "presets", "ok": True, "count": len(list(bpresets.glob("*.yaml")))})

    nord_parsed = root / "nordvpn" / "parsed.json"
    if nord_parsed.is_file() and nv.available(bin_path):
        parsed = json.loads(nord_parsed.read_text(encoding="utf-8"))
        nord_steps = _apply_nord_settings(parsed, bin_path)
        steps.append({"step": "nordvpn_settings", "ok": all(s.get("ok") for s in nord_steps), "detail": nord_steps})

    nm_file = root / "network" / "nm_profiles.json"
    if nm_file.is_file():
        profiles = json.loads(nm_file.read_text(encoding="utf-8"))
        nm_ok = True
        for prof in profiles:
            name = prof.get("name")
            if not name:
                continue
            r = net.run_cmd(
                [
                    "nmcli",
                    "con",
                    "mod",
                    name,
                    "ipv4.dns",
                    prof.get("ipv4.dns") or "",
                    "ipv4.ignore-auto-dns",
                    prof.get("ipv4.ignore-auto-dns") or "no",
                    "ipv6.method",
                    prof.get("ipv6.method") or "auto",
                ],
                timeout=15,
            )
            if not r["ok"]:
                nm_ok = False
        dev = net.detect_wifi_device((load_config().get("wifi") or {}).get("device"))
        if dev and profiles:
            net.bounce_wifi(dev)
        steps.append({"step": "networkmanager_dns", "ok": nm_ok, "profiles": len(profiles)})

    ipv6_file = root / "network" / "ipv6_sysctl.json"
    if ipv6_file.is_file():
        from nordctl.privileges import run_privileged

        ipv6 = json.loads(ipv6_file.read_text(encoding="utf-8"))
        ipv6_steps = []
        for key, val in ipv6.items():
            if val == "":
                continue
            ipv6_steps.append(run_privileged(["sysctl", "-w", f"{key}={val}"], timeout=10))
        steps.append({
            "step": "ipv6_sysctl",
            "ok": all(s.get("ok") for s in ipv6_steps),
            "needs_password": any(s.get("needs_password") for s in ipv6_steps),
        })

    if restore_resolv:
        resolv_b = root / "network" / "resolv.conf"
        if resolv_b.is_file():
            from nordctl.privileges import run_privileged

            r = run_privileged(["cp", str(resolv_b), "/etc/resolv.conf"], timeout=10)
            steps.append({"step": "resolv.conf", "ok": r.get("ok"), "needs_password": r.get("needs_password")})

    ok = all(s.get("ok", True) for s in steps if s.get("step") not in ("pre_restore_backup",))
    return {
        "ok": ok,
        "restored_from": str(root),
        "steps": steps,
        "note": "Restored install baseline. Reconnect WiFi or reboot if DNS still looks wrong.",
    }
