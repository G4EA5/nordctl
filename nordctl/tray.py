"""Optional system tray icon for quick NordVPN / preset control."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import subprocess
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any

from nordctl.config import config_dir, load_config, save_config


def tray_dependencies_ok() -> tuple[bool, str | None]:
    try:
        import pystray  # noqa: F401
        from PIL import Image  # noqa: F401

        return True, None
    except ImportError:
        return False, "Install tray extras: pip install 'nordctl[tray]'  (pystray + Pillow)"


def _nordctl_bin() -> str:
    return shutil.which("nordctl") or "nordctl"


def _dashboard_url(cfg: dict[str, Any] | None = None) -> str:
    cfg = cfg or load_config()
    srv = cfg.get("server") or {}
    host = str(srv.get("bind") or "127.0.0.1")
    port = int(srv.get("port") or 8765)
    if host in ("0.0.0.0", "::"):
        host = "127.0.0.1"
    return f"http://{host}:{port}/"


def _make_icon(connected: bool, smart_dns: bool = False):
    from PIL import Image, ImageDraw

    color = "#4ade80" if connected else ("#a5b4fc" if smart_dns else "#fb7185")
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse((4, 4, 60, 60), fill=color, outline="#ffffff", width=2)
    draw.text((22, 18), "N", fill="#05080f")
    return img


def _current_flags() -> tuple[bool, bool, str]:
    from nordctl.state import build_state

    st = build_state()
    connected = bool((st.get("status") or {}).get("connected"))
    smart = bool((st.get("smart_dns") or {}).get("active"))
    label = "VPN ON" if connected else ("Smart DNS" if smart else "VPN OFF")
    return connected, smart, label


def _run_preset(preset_id: str) -> None:
    from nordctl.presets import apply_preset

    apply_preset(preset_id)


def _run_action(action: str, **kwargs: Any) -> None:
    from nordctl.state import apply_action

    body: dict[str, Any] = {"action": action, **kwargs}
    apply_action(body)


class NordctlTray:
    def __init__(self) -> None:
        import pystray

        self._pystray = pystray
        self._icon: pystray.Icon | None = None
        self._status = "nordctl"
        self._stop = threading.Event()

    def _open_dashboard(self, _icon: Any, _item: Any) -> None:
        webbrowser.open(_dashboard_url())

    def _apply(self, preset_id: str) -> None:
        def work() -> None:
            _run_preset(preset_id)
            self._refresh_icon()

        threading.Thread(target=work, daemon=True).start()

    def _disconnect(self, _icon: Any, _item: Any) -> None:
        def work() -> None:
            _run_action("disconnect")
            self._refresh_icon()

        threading.Thread(target=work, daemon=True).start()

    def _refresh_icon(self) -> None:
        if not self._icon:
            return
        connected, smart, label = _current_flags()
        self._status = label
        self._icon.icon = _make_icon(connected, smart)
        self._icon.title = f"nordctl — {label}"
        try:
            self._icon.update_menu()
        except Exception:
            pass

    def _status_item(self, _icon: Any, _item: Any) -> str:
        return self._status

    def _build_menu(self) -> Any:
        pystray = self._pystray
        return pystray.Menu(
            pystray.MenuItem(self._status_item, None, enabled=False),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open dashboard", self._open_dashboard),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("TV streaming (Smart DNS)", lambda i, it: self._apply("streaming-smartdns")),
            pystray.MenuItem("Full VPN", lambda i, it: self._apply("full-vpn")),
            pystray.MenuItem("Disconnect VPN", self._disconnect),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Refresh status", lambda i, it: self._refresh_icon()),
            pystray.MenuItem("Quit", self._quit),
        )

    def _quit(self, icon: Any, _item: Any) -> None:
        self._stop.set()
        icon.stop()

    def _poll_loop(self) -> None:
        while not self._stop.wait(15):
            self._refresh_icon()

    def run(self) -> None:
        ok, err = tray_dependencies_ok()
        if not ok:
            raise RuntimeError(err or "tray dependencies missing")

        connected, smart, label = _current_flags()
        self._status = label
        pystray = self._pystray
        self._icon = pystray.Icon(
            "nordctl",
            _make_icon(connected, smart),
            f"nordctl — {label}",
            menu=self._build_menu(),
        )

        def setup(icon: Any) -> None:
            icon.visible = True
            threading.Thread(target=self._poll_loop, daemon=True).start()

        self._icon.run(setup=setup)


def run_tray() -> None:
    NordctlTray().run()


def _autostart_desktop_path() -> Path:
    return Path.home() / ".config" / "autostart" / "nordctl-tray.desktop"


def _systemd_user_path() -> Path:
    return Path.home() / ".config" / "systemd" / "user" / "nordctl-tray.service"


def install_tray(*, autostart: bool = True) -> dict[str, Any]:
    ok, err = tray_dependencies_ok()
    if not ok:
        return {"ok": False, "error": err}

    cfg = load_config()
    tray_cfg = cfg.setdefault("tray", {})
    tray_cfg["enabled"] = True
    tray_cfg["autostart"] = autostart
    save_config(cfg)

    bin_path = _nordctl_bin()
    written: list[str] = []

    if autostart:
        desktop_dir = _autostart_desktop_path().parent
        desktop_dir.mkdir(parents=True, exist_ok=True)
        desktop = _autostart_desktop_path()
        desktop.write_text(
            f"""[Desktop Entry]
Type=Application
Name=nordctl
Comment=NordVPN control tray
Exec={bin_path} tray
Icon=network-vpn
Terminal=false
Categories=Network;
StartupNotify=false
X-GNOME-Autostart-enabled=true
""",
            encoding="utf-8",
        )
        written.append(str(desktop))

        systemd_dir = _systemd_user_path().parent
        systemd_dir.mkdir(parents=True, exist_ok=True)
        unit = _systemd_user_path()
        unit.write_text(
            f"""[Unit]
Description=nordctl system tray
After=graphical-session.target

[Service]
Type=simple
ExecStart={bin_path} tray
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
""",
            encoding="utf-8",
        )
        written.append(str(unit))

        try:
            subprocess.run(
                ["systemctl", "--user", "daemon-reload"],
                capture_output=True,
                timeout=10,
            )
            subprocess.run(
                ["systemctl", "--user", "enable", "--now", "nordctl-tray.service"],
                capture_output=True,
                timeout=15,
            )
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    return {
        "ok": True,
        "autostart": autostart,
        "written": written,
        "start_now": f"{bin_path} tray",
        "note": "Tray starts at login. Run 'nordctl tray' now to test.",
        "linux_hint": "If no icon appears, install: sudo apt install gir1.2-ayatanaappindicator3-0.1 python3-gi",
    }


def uninstall_tray() -> dict[str, Any]:
    cfg = load_config()
    tray_cfg = cfg.setdefault("tray", {})
    tray_cfg["enabled"] = False
    tray_cfg["autostart"] = False
    save_config(cfg)

    removed: list[str] = []
    for p in (_autostart_desktop_path(), _systemd_user_path()):
        if p.is_file():
            p.unlink()
            removed.append(str(p))

    try:
        subprocess.run(
            ["systemctl", "--user", "disable", "--now", "nordctl-tray.service"],
            capture_output=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return {"ok": True, "removed": removed}
