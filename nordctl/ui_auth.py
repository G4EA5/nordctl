"""Optional dashboard password — protects LAN access to the nordctl web UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from nordctl.config import load_config, save_config

_SESSIONS: dict[str, float] = {}
_SESSION_TTL = 86400.0

_LEGACY_PASSWORD_KEYS = (
    ("lab_password_hash", "ui_password_hash"),
    ("lab_password_salt", "ui_password_salt"),
    ("lab_password_exempt_local", "ui_password_exempt_local"),
)


def migrate_legacy_password_keys(cfg: dict[str, Any]) -> bool:
    """Rename legacy lab_password_* server keys to ui_password_* (in-place)."""
    srv = cfg.get("server")
    if not isinstance(srv, dict):
        return False
    changed = False
    for old, new in _LEGACY_PASSWORD_KEYS:
        if old not in srv:
            continue
        if srv.get(old) is not None and not srv.get(new):
            srv[new] = srv[old]
        srv.pop(old, None)
        changed = True
    return changed


def _server_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    return cfg.get("server") or {}


def _hash_password(password: str, salt: str) -> str:
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        200_000,
    )
    return digest.hex()


def ui_auth_status(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    srv = _server_cfg(cfg)
    enabled = bool(srv.get("ui_password_hash") and srv.get("ui_password_salt"))
    return {
        "ok": True,
        "enabled": enabled,
        "exempt_local": bool(srv.get("ui_password_exempt_local", True)),
        "note": (
            "Dashboard password is set — other devices on your LAN must log in."
            if enabled
            else "No dashboard password — anyone who can open this URL can use the UI."
        ),
    }


def set_ui_password(
    password: str,
    cfg: dict[str, Any] | None = None,
    *,
    current: str | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    migrate_legacy_password_keys(cfg)
    srv = cfg.setdefault("server", {})
    if srv.get("ui_password_hash"):
        if not current:
            return {"ok": False, "error": "Enter your current dashboard password first."}
        if not verify_ui_password(current, cfg):
            return {"ok": False, "error": "Current password is incorrect."}
    pwd = str(password or "")
    if len(pwd) < 4:
        return {"ok": False, "error": "Password must be at least 4 characters."}
    salt = secrets.token_hex(16)
    srv["ui_password_salt"] = salt
    srv["ui_password_hash"] = _hash_password(pwd, salt)
    srv.setdefault("ui_password_exempt_local", True)
    save_config(cfg)
    token = create_session()
    return {
        "ok": True,
        "token": token,
        "note": "Dashboard password saved locally in config.yaml (hashed).",
        **ui_auth_status(cfg),
    }


def clear_ui_password(
    cfg: dict[str, Any] | None = None,
    *,
    current: str | None = None,
) -> dict[str, Any]:
    cfg = cfg or load_config()
    migrate_legacy_password_keys(cfg)
    srv = _server_cfg(cfg)
    if not srv.get("ui_password_hash"):
        return {"ok": True, "note": "No dashboard password was set."}
    if not current or not verify_ui_password(current, cfg):
        return {"ok": False, "error": "Current password is incorrect."}
    srv.pop("ui_password_hash", None)
    srv.pop("ui_password_salt", None)
    save_config(cfg)
    return {"ok": True, "note": "Dashboard password removed.", **ui_auth_status(cfg)}


def verify_ui_password(password: str, cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    migrate_legacy_password_keys(cfg)
    srv = _server_cfg(cfg)
    salt = srv.get("ui_password_salt")
    stored = srv.get("ui_password_hash")
    if not salt or not stored:
        return True
    try:
        return secrets.compare_digest(_hash_password(password, str(salt)), str(stored))
    except (TypeError, ValueError):
        return False


def create_session() -> str:
    token = secrets.token_urlsafe(32)
    _SESSIONS[token] = time.time() + _SESSION_TTL
    return token


def validate_session(token: str | None) -> bool:
    if not token:
        return False
    exp = _SESSIONS.get(token)
    if not exp or time.time() > exp:
        _SESSIONS.pop(token or "", None)
        return False
    return True


def revoke_session(token: str | None) -> None:
    if token:
        _SESSIONS.pop(token, None)


def login(password: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    st = ui_auth_status(cfg)
    if not st["enabled"]:
        return {"ok": True, "token": create_session(), "auth_required": False}
    if verify_ui_password(password, cfg):
        return {"ok": True, "token": create_session(), "auth_required": True}
    return {"ok": False, "error": "Wrong dashboard password."}


def auth_required_for_client(client_host: str | None, cfg: dict[str, Any] | None = None) -> bool:
    cfg = cfg or load_config()
    st = ui_auth_status(cfg)
    if not st["enabled"]:
        return False
    host = (client_host or "").strip()
    if st.get("exempt_local") and host in ("127.0.0.1", "::1", "localhost"):
        return False
    return True
