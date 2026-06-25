"""Local web terminal — PTY shell sessions for the nordctl UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import fcntl
import os
import pty
import re
import shutil
import struct
import termios
import threading
import time
import uuid
from typing import Any

_SHELL_LABEL_RE = re.compile(r"^Shell(\s+\d+)?$", re.I)

MAX_OUTPUT_CHARS = 400_000
SESSION_IDLE_SEC = 1800
POLL_WAIT_SEC = 2.0

_sessions: dict[str, TerminalSession] = {}
_sessions_lock = threading.Lock()


class TerminalSession:
    def __init__(self, label: str = "Shell") -> None:
        self.id = uuid.uuid4().hex[:10]
        self.label = (label or "Shell").strip()[:80] or "Shell"
        self.output = ""
        self.cursor = 0
        self.lock = threading.Lock()
        self.closed = False
        self.created = time.time()
        self.last_active = time.time()
        self.master_fd: int | None = None
        self.pid: int | None = None
        self.pending_scan: str | None = None
        self.scan_emailed = False
        self._has_data = threading.Event()
        self._start_shell()

    def _start_shell(self) -> None:
        pid, master = pty.fork()
        if pid == 0:
            os.environ.setdefault("TERM", "xterm-256color")
            os.environ.setdefault("COLORTERM", "truecolor")
            home = os.path.expanduser("~")
            os.environ.setdefault("HOME", home)
            os.chdir(home)
            os.execvp("bash", ["bash", "--login"])
        self.pid = pid
        self.master_fd = master
        threading.Thread(target=self._reader_loop, name=f"nordctl-term-{self.id}", daemon=True).start()

    def _reader_loop(self) -> None:
        assert self.master_fd is not None
        while not self.closed:
            try:
                chunk = os.read(self.master_fd, 8192)
            except OSError:
                break
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="replace")
            with self.lock:
                self.output += text
                if len(self.output) > MAX_OUTPUT_CHARS:
                    self.output = self.output[-MAX_OUTPUT_CHARS:]
                self.last_active = time.time()
            self._has_data.set()
        self._mark_closed(exit_note="\r\n[session ended]\r\n")

    def _mark_closed(self, exit_note: str = "") -> None:
        with self.lock:
            if exit_note and not self.output.endswith(exit_note):
                self.output += exit_note
            self.closed = True
        self._maybe_email_scan_when_idle()
        self._has_data.set()

    def _note_scan_command(self, data: str) -> None:
        if self.pending_scan or self.scan_emailed:
            return
        from nordctl.scan_alerts import identify_scan

        scan_id = identify_scan(data)
        if scan_id:
            self.pending_scan = scan_id
            threading.Thread(
                target=self._scan_email_watch,
                name=f"nordctl-scan-email-{self.id}",
                daemon=True,
            ).start()

    def _scan_email_watch(self) -> None:
        from nordctl.scan_alerts import maybe_email_scan_result, scan_output_complete

        stable = 0
        last_len = -1
        for _ in range(360):
            if self.closed or self.scan_emailed:
                return
            time.sleep(5)
            with self.lock:
                if self.scan_emailed or not self.pending_scan:
                    return
                cur_len = len(self.output)
                out = self.output
                scan_id = self.pending_scan
            if cur_len == last_len:
                stable += 1
            else:
                stable = 0
                last_len = cur_len
            if stable >= 2 and scan_output_complete(scan_id, out):
                maybe_email_scan_result(
                    f"sudo {scan_id}",
                    out,
                    ok=True,
                    label=scan_id,
                    cfg=None,
                    scan_id=scan_id,
                )
                self.scan_emailed = True
                return

    def _maybe_email_scan_when_idle(self) -> None:
        if self.scan_emailed or not self.pending_scan:
            return
        with self.lock:
            out = self.output
            scan_id = self.pending_scan
        from nordctl.scan_alerts import maybe_email_scan_result, scan_output_complete

        if scan_output_complete(scan_id, out):
            maybe_email_scan_result(
                f"sudo {scan_id}",
                out,
                ok=True,
                label=scan_id,
                cfg=None,
                scan_id=scan_id,
            )
            self.scan_emailed = True

    def write(self, data: str) -> bool:
        if data:
            self._note_scan_command(data)
        if self.closed or self.master_fd is None:
            return False
        try:
            os.write(self.master_fd, data.encode("utf-8", errors="replace"))
            self.last_active = time.time()
            return True
        except OSError:
            self._mark_closed()
            return False

    def resize(self, rows: int, cols: int) -> None:
        if self.closed or self.master_fd is None:
            return
        rows = max(2, min(int(rows), 200))
        cols = max(20, min(int(cols), 500))
        try:
            winsize = struct.pack("HHHH", rows, cols, 0, 0)
            fcntl.ioctl(self.master_fd, termios.TIOCSWINSZ, winsize)
        except OSError:
            pass

    def read_from(self, cursor: int, *, wait: bool = False) -> dict[str, Any]:
        if wait and not self.closed:
            self._has_data.wait(timeout=POLL_WAIT_SEC)
        self._has_data.clear()
        with self.lock:
            cur = max(0, min(int(cursor), len(self.output)))
            chunk = self.output[cur:]
            new_cursor = len(self.output)
            alive = not self.closed
        return {
            "session": self.id,
            "chunk": chunk,
            "cursor": new_cursor,
            "alive": alive,
        }

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.master_fd is not None:
            try:
                os.close(self.master_fd)
            except OSError:
                pass
            self.master_fd = None
        if self.pid:
            try:
                os.kill(self.pid, 15)
            except OSError:
                pass


def _gc_sessions() -> None:
    now = time.time()
    stale: list[str] = []
    with _sessions_lock:
        for sid, sess in _sessions.items():
            if sess.closed or (now - sess.last_active) > SESSION_IDLE_SEC:
                stale.append(sid)
        for sid in stale:
            _sessions.pop(sid, None)


def _used_labels() -> set[str]:
    with _sessions_lock:
        return {s.label for s in _sessions.values()}


def _next_shell_label() -> str:
    used = _used_labels()
    n = 1
    while f"Shell {n}" in used:
        n += 1
    return f"Shell {n}"


def _normalize_shell_labels() -> None:
    """Renumber default shell tabs Shell 1, Shell 2, … by creation order."""
    with _sessions_lock:
        shells = [s for s in _sessions.values() if _SHELL_LABEL_RE.match(s.label or "")]
        if len(shells) < 2:
            return
        shells.sort(key=lambda s: (s.created, s.id))
        reserved = {s.label for s in _sessions.values() if s not in shells}
        n = 1
        for sess in shells:
            while f"Shell {n}" in reserved:
                n += 1
            label = f"Shell {n}"
            sess.label = label
            reserved.add(label)
            n += 1


def _resolve_shell_label(label: str | None) -> str:
    clean = (label or "").strip()[:80]
    used = _used_labels()
    if not clean or clean == "Shell":
        return _next_shell_label()
    if clean in used and _SHELL_LABEL_RE.match(clean):
        return _next_shell_label()
    return clean


def open_session(label: str | None = None) -> dict[str, Any]:
    _gc_sessions()
    clean = _resolve_shell_label(label)
    sess = TerminalSession(label=clean)
    with _sessions_lock:
        _sessions[sess.id] = sess
    _normalize_shell_labels()
    with _sessions_lock:
        sess = _sessions.get(sess.id) or sess
    from nordctl.activity_log import record_event

    record_event(
        "terminal",
        "Terminal session opened",
        detail=f"{sess.label} (session {sess.id})",
        level="info",
        ok=True,
        meta={"terminal_session": sess.id, "label": sess.label},
    )
    return {
        "ok": True,
        "session": sess.id,
        "label": sess.label,
        "shell": "bash --login",
        "note": "Local only — runs as your user on this machine. Sudo will prompt in this window if configured.",
    }


def list_sessions() -> dict[str, Any]:
    _gc_sessions()
    _normalize_shell_labels()
    items: list[dict[str, Any]] = []
    with _sessions_lock:
        for sid, sess in _sessions.items():
            with sess.lock:
                items.append(
                    {
                        "id": sid,
                        "label": sess.label,
                        "alive": not sess.closed,
                        "created": sess.created,
                        "last_active": sess.last_active,
                        "output_length": len(sess.output),
                    }
                )
    items.sort(key=lambda x: x.get("created") or 0)
    return {"ok": True, "sessions": items}


def get_session(session_id: str) -> TerminalSession | None:
    with _sessions_lock:
        return _sessions.get((session_id or "").strip())


def terminal_input(session_id: str, data: str) -> dict[str, Any]:
    sess = get_session(session_id)
    if not sess:
        return {"ok": False, "error": "session not found — open a new terminal"}
    if not sess.write(data or ""):
        return {"ok": False, "error": "session closed", "alive": False}
    return {"ok": True, "alive": True}


def terminal_poll(session_id: str, cursor: int = 0, *, wait: bool = True) -> dict[str, Any]:
    sess = get_session(session_id)
    if not sess:
        return {"ok": False, "error": "session not found", "alive": False}
    out = sess.read_from(cursor, wait=wait)
    return {"ok": True, **out}


def terminal_resize(session_id: str, rows: int, cols: int) -> dict[str, Any]:
    sess = get_session(session_id)
    if not sess:
        return {"ok": False, "error": "session not found"}
    sess.resize(rows, cols)
    return {"ok": True}


def terminal_close(session_id: str) -> dict[str, Any]:
    sess = get_session(session_id)
    if not sess:
        return {"ok": True, "closed": True}
    sess.close()
    with _sessions_lock:
        _sessions.pop(sess.id, None)
    return {"ok": True, "closed": True}


def _nord_quick_commands(bin_path: str) -> list[dict[str, Any]]:
    b = bin_path
    return [
        {"label": "nordvpn login", "cmd": "nordvpn login\n", "scope": "nord"},
        {"label": "nordvpn account", "cmd": "nordvpn account\n", "scope": "nord"},
        {"label": "nordvpn logout", "cmd": "nordvpn logout\n", "scope": "nord"},
        {"label": "nordvpn status", "cmd": "nordvpn status\n", "scope": "nord"},
        {"label": "nordvpn settings", "cmd": "nordvpn settings\n", "scope": "nord"},
        {"label": "nordvpn version", "cmd": "nordvpn version\n", "scope": "nord"},
        {"label": "nordvpn countries", "cmd": "nordvpn countries\n", "scope": "nord"},
        {"label": "nordvpn cities US", "cmd": "nordvpn cities United_States\n", "scope": "nord"},
        {"label": "nordvpn connect", "cmd": "nordvpn connect\n", "scope": "nord"},
        {"label": "nordvpn disconnect", "cmd": "nordvpn disconnect\n", "scope": "nord"},
        {"label": "nordvpn reconnect", "cmd": "nordvpn disconnect; sleep 1; nordvpn connect\n", "scope": "nord"},
        {"label": "nordctl status", "cmd": f"{b} status\n", "scope": "nord"},
        {"label": "nordctl doctor", "cmd": f"{b} doctor\n", "scope": "nord"},
        {"label": "nordctl leaklab", "cmd": f"{b} leaklab\n", "scope": "nord"},
        {"label": "nordctl presets", "cmd": f"{b} presets\n", "scope": "nord"},
        {"label": "nordctl public-ip", "cmd": f"{b} public-ip\n", "scope": "nord"},
        {"label": "nordctl journal", "cmd": f"{b} journal\n", "scope": "nord"},
        {"label": "dry-run disconnect", "cmd": f"{b} apply disconnect --dry-run\n", "scope": "nord"},
        {"label": "dry-run full-vpn", "cmd": f"{b} apply full-vpn --dry-run\n", "scope": "nord"},
        {"label": "dry-run smart-dns", "cmd": f"{b} apply streaming-smartdns --dry-run\n", "scope": "nord"},
        {"label": "nordctl wifi status", "cmd": f"{b} wifi status\n", "scope": "nord"},
        {"label": "nordctl wifi doctor", "cmd": f"{b} wifi doctor\n", "scope": "nord"},
        {"label": "killswitch on", "cmd": "nordvpn set killswitch on\n", "scope": "nord"},
        {"label": "killswitch off", "cmd": "nordvpn set killswitch off\n", "scope": "nord"},
        {"label": "autoconnect on", "cmd": "nordvpn set autoconnect on\n", "scope": "nord"},
        {"label": "autoconnect off", "cmd": "nordvpn set autoconnect off\n", "scope": "nord"},
        {"label": "technology NordLynx", "cmd": "nordvpn set technology NordLynx\n", "scope": "nord"},
        {"label": "threat protection on", "cmd": "nordvpn set threatprotection on\n", "scope": "nord"},
        {"label": "allowlist", "cmd": "nordvpn allowlist list\n", "scope": "nord"},
        {"label": "meshnet peers", "cmd": "nordvpn meshnet peer list\n", "scope": "nord"},
        {"label": "UI service status", "cmd": f"{b} service status\n", "scope": "nord"},
        {"label": "nordvpnd status", "cmd": f"{b} service nordvpnd status\n", "scope": "nord"},
        {"label": "nordvpnd restart", "cmd": "sudo systemctl restart nordvpnd\n", "sudo": True, "scope": "nord"},
        {"label": "snapshots", "cmd": f"{b} snapshot list\n", "scope": "nord"},
        {"label": "install nordvpn (preview)", "cmd": f"{b} install-nordvpn --dry-run\n", "scope": "nord"},
        {"label": "install nordvpn", "cmd": f"{b} install-nordvpn\n", "sudo": True, "scope": "nord"},
    ]


def _networking_quick_commands(bin_path: str) -> list[dict[str, Any]]:
    return [
        {"label": "IP & DNS", "cmd": "ip route; echo '---'; resolvectl status 2>/dev/null || cat /etc/resolv.conf\n", "scope": "network"},
        {"label": "Public IP", "cmd": f"{bin_path} public-ip\n", "scope": "network"},
        {"label": "Open ports", "cmd": "ss -tuln 2>/dev/null | head -35\n", "scope": "network"},
        {"label": "Connections", "cmd": "ss -tp state established 2>/dev/null | head -30\n", "scope": "network"},
        {"label": "WiFi / NM", "cmd": "nmcli dev status 2>/dev/null; echo '---'; nmcli connection show --active 2>/dev/null\n", "scope": "network"},
        {"label": "System snapshot", "cmd": "uptime; free -h | head -2; df -h / /home 2>/dev/null | tail -2\n", "scope": "network"},
        {"label": "Failed units", "cmd": "systemctl --failed --no-pager 2>/dev/null\n", "scope": "network"},
        {"label": "Restart UI", "cmd": f"{bin_path} service restart\n", "scope": "network"},
        {"label": "apt update", "cmd": "sudo apt update\n", "sudo": True, "scope": "network"},
        {"label": "Sample tcpdump", "cmd": "sudo timeout 15 tcpdump -i any -c 30 -n\n", "sudo": True, "scope": "network"},
    ]


def _security_quick_commands(bin_path: str, priv_script: Path) -> list[dict[str, Any]]:
    return [
        {"label": "UFW status", "cmd": "sudo ufw status numbered\n", "sudo": True, "scope": "security"},
        {"label": "UFW reload", "cmd": "sudo ufw reload; sudo ufw status numbered\n", "sudo": True, "scope": "security"},
        {"label": "nft rules", "cmd": "sudo nft list ruleset 2>/dev/null | head -120\n", "sudo": True, "scope": "security"},
        {"label": "Listen + PID", "cmd": "sudo ss -tulpn 2>/dev/null | head -40\n", "sudo": True, "scope": "security"},
        {"label": "Open ports", "cmd": "ss -tuln 2>/dev/null | head -35\n", "scope": "security"},
        {"label": "Journal errors", "cmd": "sudo journalctl -p err -b --no-pager 2>/dev/null | tail -50\n", "sudo": True, "scope": "security"},
        {"label": "SSH log tail", "cmd": "sudo journalctl -u ssh -n 40 --no-pager 2>/dev/null || sudo tail -30 /var/log/auth.log 2>/dev/null\n", "sudo": True, "scope": "security"},
        {"label": "fail2ban status", "cmd": "sudo fail2ban-client status\n", "sudo": True, "scope": "security"},
        {"label": "Lynis audit", "cmd": "sudo lynis audit system\n", "sudo": True, "scope": "security"},
        {"label": "rkhunter scan", "cmd": "sudo rkhunter --check --sk\n", "sudo": True, "scope": "security"},
        {"label": "chkrootkit", "cmd": "sudo chkrootkit\n", "sudo": True, "scope": "security"},
        {"label": "ClamAV home", "cmd": "clamscan -r --infected --remove=no ~\n", "scope": "security"},
        {"label": "apt update", "cmd": "sudo apt update\n", "sudo": True, "scope": "security"},
        {"label": "Install privileges", "cmd": f"sudo bash {priv_script}\n", "sudo": True, "scope": "security"},
    ]


def _norm_cmd(cmd: str) -> str:
    return re.sub(r"\s+", " ", (cmd or "").strip())


def _cmd_is_sudo(cmd: str) -> bool:
    return bool(re.match(r"^\s*sudo\b", cmd or ""))


def _builtin_cmd_available(cmd: str) -> bool:
    """Hide built-in quick commands when their primary tool is not installed."""
    text = (cmd or "").strip()
    if not text:
        return False
    checks = (
        (r"\bnmcli\b", "nmcli"),
        (r"\btcpdump\b", "tcpdump"),
        (r"\bufw\b", "ufw"),
        (r"\bnft\b", "nft"),
        (r"\bfail2ban-client\b", "fail2ban-client"),
        (r"\blynis\b", "lynis"),
        (r"\brkhunter\b", "rkhunter"),
        (r"\bchkrootkit\b", "chkrootkit"),
        (r"\bclamscan\b", "clamscan"),
    )
    for pattern, binary in checks:
        if re.search(pattern, text) and not shutil.which(binary):
            return False
    return True


def _catalog_quick_commands(hub: str, cfg: dict[str, Any] | None) -> list[dict[str, Any]]:
    from nordctl.tool_install import _row, catalog_items

    hub_key = (hub or "network").strip().lower()
    out: list[dict[str, Any]] = []
    for item in catalog_items(cfg):
        item_hub = str(item.get("hub") or "network").strip().lower()
        if item_hub != hub_key:
            continue
        row = _row(item)
        if not row.get("installed"):
            continue
        run_cmd = str(row.get("run_cmd") or "").strip()
        if not run_cmd:
            continue
        cmd = run_cmd if run_cmd.endswith("\n") else f"{run_cmd}\n"
        label = str(row.get("run_label") or row.get("label") or "Run").strip()
        out.append(
            {
                "label": label,
                "cmd": cmd,
                "sudo": bool(row.get("run_cmd") and _cmd_is_sudo(run_cmd)),
                "scope": hub_key,
                "tool_id": row.get("id"),
            }
        )
    out.sort(key=lambda c: str(c.get("label") or "").lower())
    return out


def _merge_quick_commands(
    builtins: list[dict[str, Any]],
    catalog: list[dict[str, Any]],
    scope: str,
) -> list[dict[str, Any]]:
    seen: set[str] = set()
    merged: list[dict[str, Any]] = []
    for src in (builtins, catalog):
        for cmd in src:
            key = _norm_cmd(str(cmd.get("cmd") or ""))
            if not key or key in seen:
                continue
            seen.add(key)
            merged.append({**cmd, "scope": scope})
    return merged


def run_command_once(cmd: str, *, label: str = "", timeout: int = 600) -> dict[str, Any]:
    """Run one shell command and return captured output (for inline network setup quick commands)."""
    import subprocess

    from nordctl.activity_log import record_event

    text = (cmd or "").strip()
    if not text:
        return {"ok": False, "error": "Empty command", "output": ""}
    wait = max(5, min(int(timeout or 600), 3600))
    title = (label or text.split("\n")[0][:60] or "Command").strip()
    scan_markers = ("lynis", "rkhunter", "chkrootkit", "clamscan", "nmap", "tcpdump", "fail2ban")
    cat = "scan" if any(m in text.lower() for m in scan_markers) else "terminal"
    try:
        proc = subprocess.run(
            ["bash", "-lc", text],
            capture_output=True,
            text=True,
            timeout=wait,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        ok = proc.returncode == 0
        record_event(
            cat,
            title if ok else f"{title} failed",
            detail="Quick command from Network → Configuration." if ok else f"Exit code {proc.returncode}.",
            technical=out[:8000],
            level="ok" if ok else "error",
            ok=ok,
            meta={"source": "network_setup", "cmd": text[:200]},
        )
        from nordctl.scan_alerts import maybe_email_scan_result

        mail = maybe_email_scan_result(text, out, ok=ok, label=title, cfg=None)
        result = {"ok": ok, "output": out[:8000], "returncode": proc.returncode, "label": title}
        if mail.get("emailed"):
            result["scan_email"] = mail
        return result
    except subprocess.TimeoutExpired:
        record_event(
            "error",
            f"{title} timed out",
            detail=f"Stopped after {wait} seconds.",
            ok=False,
        )
        return {"ok": False, "error": "Timed out", "output": f"Command timed out after {wait} seconds.\n"}
    except OSError as exc:
        return {"ok": False, "error": str(exc), "output": str(exc)}


def quick_commands(cfg: dict[str, Any] | None = None, scope: str = "network") -> dict[str, Any]:
    from nordctl.quick_commands_settings import effective_quick_commands

    scope_key = (scope or "network").strip().lower()
    commands = effective_quick_commands(cfg, scope_key)
    return {"ok": True, "scope": scope_key, "commands": commands}
