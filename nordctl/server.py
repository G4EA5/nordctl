"""Local HTTP server for the nordctl web UI."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import mimetypes
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from nordctl.config import load_config
from nordctl.doctor import run_doctor
from nordctl.ports import is_port_free, resolve_listen_port
from nordctl.state import apply_action as state_apply_action, build_state

STATIC = Path(__file__).resolve().parent / "static"


class NordctlHandler(BaseHTTPRequestHandler):
    server_version = "nordctl/0.2"

    def log_message(self, fmt: str, *args: Any) -> None:
        return

    def _json(self, code: int, payload: dict[str, Any]) -> None:
        try:
            body = json.dumps(payload).encode()
        except (TypeError, ValueError):
            from nordctl.json_util import sanitize_for_json

            body = json.dumps(sanitize_for_json(payload)).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict[str, Any]:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode())
        except json.JSONDecodeError:
            return {}

    def _client_host(self) -> str:
        return (self.client_address[0] or "").strip()

    def _session_token(self) -> str:
        auth = self.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            return auth[7:].strip()
        return (self.headers.get("X-Nordctl-Token") or "").strip()

    def _auth_exempt(self, path: str, method: str) -> bool:
        if not path.startswith("/api/"):
            return True
        if path in (
            "/api/ui-auth/status",
            "/api/ui-auth/login",
            "/api/lab-auth/status",
            "/api/lab-auth/login",
        ) and method in ("GET", "POST"):
            return True
        return False

    def _enforce_auth(self, path: str, method: str) -> bool:
        if self._auth_exempt(path, method):
            return True
        from nordctl.ui_auth import auth_required_for_client, validate_session

        cfg = load_config()
        if not auth_required_for_client(self._client_host(), cfg):
            return True
        if validate_session(self._session_token()):
            return True
        self._json(401, {"ok": False, "error": "Dashboard login required.", "auth_required": True})
        return False

    def _serve_static(self, rel: str) -> None:
        rel = rel.lstrip("/")
        if rel in ("", "index.html"):
            rel = "index.html"
        path = (STATIC / rel).resolve()
        if not str(path).startswith(str(STATIC.resolve())) or not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        if rel == "index.html":
            js_ver = int((STATIC / "app.js").stat().st_mtime)
            css_ver = int((STATIC / "app.css").stat().st_mtime)
            html = data.decode("utf-8")
            html = html.replace("__JS_VER__", str(js_ver)).replace("__CSS_VER__", str(css_ver))
            data = html.encode("utf-8")
        ctype = mimetypes.guess_type(str(rel))[0] or "application/octet-stream"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        if rel == "index.html":
            self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        elif rel.endswith((".js", ".css")):
            self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        else:
            self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/") and not self._enforce_auth(path, "GET"):
            return
        try:
            self._do_get(path)
        except Exception as exc:
            self._post_error(exc, path)

    def _do_get(self, path: str) -> None:
        if path == "/api/settings":
            from nordctl.settings_panel import settings_payload

            self._json(200, settings_payload(load_config()))
            return
        if path in ("/api/ui-auth/status", "/api/lab-auth/status"):
            from nordctl.ui_auth import auth_required_for_client, ui_auth_status

            cfg = load_config()
            self._json(
                200,
                {
                    "ok": True,
                    **ui_auth_status(cfg),
                    "auth_required": auth_required_for_client(self._client_host(), cfg),
                },
            )
            return
        if path == "/api/state/quick":
            from nordctl.state import build_state_quick

            self._json(200, build_state_quick())
            return
        if path == "/api/state/app":
            from nordctl.state import build_state_app, merge_state

            self._json(200, merge_state(build_state_app()))
            return
        if path == "/api/state/nord":
            from nordctl.state import build_state_nord, merge_state

            self._json(200, merge_state(build_state_nord()))
            return
        if path == "/api/state/network":
            from nordctl.state import build_state_network, build_state_nord, merge_state

            cfg = load_config()
            nord = build_state_nord(cfg, include_countries=False, quick=True)
            self._json(
                200,
                merge_state(
                    build_state_network(
                        cfg,
                        status=nord.get("status"),
                        settings=nord.get("settings"),
                        mesh_ip=nord.get("mesh_ip"),
                        fast_ip=False,
                    )
                ),
            )
            return
        if path == "/api/connection-details":
            from nordctl.connection_details import build_connection_details
            from nordctl.state import build_state_nord

            cfg = load_config()
            nord = build_state_nord(cfg, include_countries=False, quick=True)
            self._json(
                200,
                build_connection_details(
                    cfg,
                    nord.get("status"),
                    settings=nord.get("settings"),
                    mesh_ip=nord.get("mesh_ip"),
                ),
            )
            return
        if path == "/api/demo":
            from nordctl.demo_mode import is_demo_mode

            self._json(200, {"ok": True, "demo_mode": is_demo_mode(load_config())})
            return
        if path == "/api/openapi":
            root = Path(__file__).resolve().parent.parent / "docs" / "openapi.yaml"
            if root.is_file():
                self.send_response(200)
                self.send_header("Content-Type", "application/yaml; charset=utf-8")
                body = root.read_bytes()
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            else:
                self._json(404, {"ok": False, "error": "openapi.yaml not found"})
            return
        if path == "/api/compatibility":
            from nordctl.compatibility import compatibility_matrix

            self._json(200, compatibility_matrix())
            return
        if path == "/api/presets/community":
            from nordctl.community_presets import list_community_presets

            self._json(200, list_community_presets(load_config()))
            return
        if path == "/api/presets/export":
            from urllib.parse import parse_qs

            from nordctl.presets import export_preset_yaml

            qs = parse_qs(urlparse(self.path).query)
            preset_id = (qs.get("id") or [""])[0]
            result = export_preset_yaml(str(preset_id), load_config())
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/state":
            from nordctl.state import build_state

            self._json(200, build_state())
            return
        if path == "/api/doctor":
            self._json(200, run_doctor())
            return
        if path == "/api/install-plan":
            from nordctl.nordvpn_install import install_plan

            self._json(200, install_plan())
            return
        if path == "/api/files":
            from nordctl.files import list_editable_files

            self._json(200, list_editable_files())
            return
        if path == "/api/files/read":
            from nordctl.files import read_file
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            fid = (qs.get("id") or ["config"])[0]
            result = read_file(fid)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/wifi-profiles":
            from nordctl.files import list_wifi_profiles

            self._json(200, list_wifi_profiles())
            return
        if path == "/api/help":
            from nordctl.help_content import help_payload

            self._json(200, help_payload(load_config()))
            return
        if path == "/api/leaklab":
            from nordctl.leaklab import run_leaklab

            self._json(200, run_leaklab())
            return
        if path == "/api/network-audit":
            from nordctl.network_audit import run_network_audit

            self._json(200, run_network_audit())
            return
        if path == "/api/overall-audit":
            from nordctl.overall_audit import run_overall_audit

            self._json(200, run_overall_audit())
            return
        if path == "/api/nettools":
            from nordctl.nettools import nettools_payload

            self._json(200, nettools_payload())
            return
        if path == "/api/tools":
            from nordctl.tool_install import tools_payload

            self._json(200, tools_payload())
            return
        if path == "/api/ufw":
            from nordctl.ufw_control import get_state

            self._json(200, get_state(load_config()))
            return
        if path == "/api/host/status":
            from nordctl.host_status import host_status_payload

            self._json(200, host_status_payload(load_config()))
            return
        if path == "/api/traffic":
            from urllib.parse import parse_qs

            from nordctl.traffic_map import build_traffic_map
            from nordctl.traffic_watch import run_traffic_watch

            qs = parse_qs(urlparse(self.path).query)
            fmt = (qs.get("format") or [""])[0].strip().lower()
            filt = (qs.get("filter") or [""])[0].strip().lower()
            if fmt == "simple" or filt:
                self._json(200, run_traffic_watch(filt or "all"))
                return
            self._json(200, build_traffic_map())
            return
        if path == "/api/logs":
            from nordctl.activity_log import logs_payload
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            cat = (qs.get("category") or [None])[0]
            errors = (qs.get("errors") or ["0"])[0] in ("1", "true", "yes")
            limit = int((qs.get("limit") or ["10"])[0])
            self._json(200, logs_payload(limit=min(max(limit, 1), 100), category=cat, errors_only=errors))
            return
        if path == "/api/security/summary":
            from nordctl.security_hub import security_hub_summary

            self._json(200, security_hub_summary(load_config()))
            return
        if path == "/api/security":
            from nordctl.security_hub import security_hub_payload

            self._json(200, security_hub_payload(load_config()))
            return
        if path == "/api/bandwidth":
            from nordctl.bandwidth import sample_bandwidth

            self._json(200, {"ok": True, **sample_bandwidth()})
            return
        if path == "/api/speedtest/history":
            from nordctl.speedtest_store import history_payload
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            limit = int((qs.get("limit") or ["100"])[0])
            self._json(200, history_payload(limit=limit))
            return
        if path == "/api/speedtest/export":
            from nordctl.speedtest_store import export_results
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            fmt = (qs.get("format") or ["json"])[0]
            limit = int((qs.get("limit") or ["200"])[0])
            self._json(200, export_results(fmt=fmt, limit=limit))
            return
        if path == "/api/speedtest/providers":
            from nordctl.speedtest import speedtest_providers_payload

            self._json(200, speedtest_providers_payload(load_config()))
            return
        if path == "/api/wifi/hub":
            from nordctl.wifi_hub import wifi_hub_payload

            self._json(200, wifi_hub_payload(load_config()))
            return
        if path == "/api/spectrum":
            from nordctl.spectrum_analyzer import spectrum_payload

            self._json(200, spectrum_payload(load_config()))
            return
        if path == "/api/bluetooth":
            from urllib.parse import parse_qs

            from nordctl.bluetooth_spectrum import bluetooth_payload

            qs = parse_qs(urlparse(self.path).query)
            rescan = (qs.get("rescan") or [""])[0].lower() in ("1", "true", "yes")
            self._json(200, bluetooth_payload(load_config(), rescan=rescan))
            return
        if path == "/api/wifi/doctor":
            from nordctl.wifi_doctor import run_all_wifi_hub_doctors

            self._json(200, run_all_wifi_hub_doctors(load_config()))
            return
        if path == "/api/onboarding":
            from nordctl.onboarding import onboard_payload

            self._json(200, onboard_payload(load_config()))
            return
        if path == "/api/setup-wizard":
            from nordctl.setup_wizard import wizard_payload

            self._json(200, wizard_payload(load_config()))
            return
        if path == "/api/ui-health":
            from nordctl.static_assets import ui_health_payload

            self._json(200, ui_health_payload())
            return
        if path == "/api/features":
            from nordctl.features import features_payload

            self._json(200, features_payload(load_config()))
            return
        if path == "/api/privacy":
            from nordctl.privacy import privacy_manifest

            self._json(200, privacy_manifest(load_config()))
            return
        if path == "/api/provenance":
            from nordctl.provenance import provenance_payload

            self._json(200, provenance_payload())
            return
        if path == "/api/roadmap":
            from nordctl.roadmap import roadmap_payload

            self._json(200, roadmap_payload(load_config()))
            return
        if path == "/api/alerts":
            from nordctl.alerts import alerts_status

            self._json(200, alerts_status(load_config()))
            return
        if path == "/api/alerts/pending":
            from nordctl.alerts import pending_browser_alerts
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            clear = (qs.get("clear") or ["0"])[0] in ("1", "true", "yes")
            self._json(200, pending_browser_alerts(clear=clear))
            return
        if path == "/api/recommendations":
            from nordctl.alerts import smart_recommendations

            self._json(200, smart_recommendations(load_config()))
            return
        if path == "/api/journal":
            from nordctl.alerts import connection_journal
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            limit = int((qs.get("limit") or ["100"])[0])
            self._json(200, connection_journal(limit=min(max(limit, 1), 100)))
            return
        if path == "/api/firewall":
            from nordctl.firewall_panel import firewall_overview

            cfg = load_config()
            st = build_state(cfg)
            fw = st.get("firewall") or firewall_overview(
                cfg,
                st.get("settings") or {},
                connected=bool((st.get("status") or {}).get("connected")),
                wifi_dns=(st.get("smart_dns") or {}).get("dns_servers") or [],
                smart_active=bool((st.get("smart_dns") or {}).get("active")),
            )
            self._json(200, {"ok": True, **fw})
            return
        if path == "/api/switches":
            from nordctl.switches_panel import switches_payload

            self._json(200, switches_payload(load_config()))
            return
        if path == "/api/baseline":
            from nordctl.baseline import baseline_status

            self._json(200, {"ok": True, **baseline_status()})
            return
        if path == "/api/service":
            from nordctl.service_mgr import service_overview

            self._json(200, {"ok": True, **service_overview(load_config())})
            return
        if path == "/api/allowlist":
            from nordctl.allowlist_mgr import get_allowlist

            self._json(200, get_allowlist())
            return
        if path == "/api/meshnet":
            from nordctl.meshnet_ui import meshnet_state

            self._json(200, meshnet_state())
            return
        if path == "/api/hooks":
            from nordctl.hooks import hooks_status

            self._json(200, hooks_status(load_config()))
            return
        if path.startswith("/api/locations/cities"):
            from urllib.parse import parse_qs

            cfg = load_config()
            bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
            q = parse_qs(urlparse(self.path).query)
            country = (q.get("country") or [""])[0]
            if not country:
                country = str(cfg.get("connect_country") or "").replace("_", " ")
            from nordctl import nordvpn as nv

            if not nv.available(bin_path):
                self._json(200, {"ok": False, "error": "Install NordVPN first to load city lists.", "cities": []})
                return
            cities = nv.list_cities(bin_path, country)
            self._json(200, {"ok": True, "country": country, "cities": cities})
            return
        if path == "/api/presets/builder/schema":
            from nordctl.preset_builder import builder_schema

            self._json(200, builder_schema(load_config()))
            return
        if path == "/api/presets/builder/from-current":
            from nordctl.preset_builder import capture_from_current

            self._json(200, capture_from_current(load_config()))
            return
        if path == "/api/presets/builder/from-preset":
            from urllib.parse import parse_qs

            from nordctl.preset_builder import spec_from_preset_document
            from nordctl.presets import get_preset

            q = parse_qs(urlparse(self.path).query)
            preset_id = str((q.get("id") or [""])[0]).strip()
            if not preset_id:
                self._json(400, {"ok": False, "error": "id query parameter required"})
                return
            cfg = load_config()
            preset = get_preset(preset_id, cfg)
            if not preset:
                self._json(404, {"ok": False, "error": f"unknown preset: {preset_id}"})
                return
            if not preset.get("user"):
                self._json(400, {"ok": False, "error": "Only custom presets can be edited in the builder"})
                return
            spec = spec_from_preset_document(preset)
            self._json(200, {
                "ok": True,
                "id": preset_id,
                "file_id": preset.get("_file_id"),
                "spec": spec,
            })
            return
        if path == "/api/profiles":
            from nordctl.profiles import list_profiles

            self._json(200, list_profiles())
            return
        if path == "/api/schedules":
            from nordctl.schedule import list_schedules

            self._json(200, {"ok": True, "schedules": list_schedules()})
            return
        if path == "/api/snapshots":
            from nordctl.snapshot import list_snapshots

            self._json(200, {"ok": True, "snapshots": list_snapshots()})
            return
        if path == "/api/zones":
            from nordctl.zones import zone_status

            self._json(200, zone_status())
            return
        if path in ("/api/ha/state", "/api/homeassistant"):
            st = build_state()
            self._json(200, {
                "vpn_connected": bool((st.get("status") or {}).get("connected")),
                "smart_dns_active": bool((st.get("smart_dns") or {}).get("active")),
                "public_ip": (st.get("smart_dns") or {}).get("public_ip"),
                "mesh_ip": st.get("mesh_ip"),
                "country": (st.get("status") or {}).get("Country"),
            })
            return
        if path == "/api/terminal/commands":
            from nordctl.terminal import quick_commands
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            scope = (qs.get("scope") or ["network"])[0]
            self._json(200, quick_commands(load_config(), scope=scope))
            return
        if path == "/api/terminal/quick-commands/settings":
            from nordctl.quick_commands_settings import settings_payload

            self._json(200, settings_payload(load_config()))
            return
        if path == "/api/terminal/sessions":
            from nordctl.terminal import list_sessions

            self._json(200, list_sessions())
            return
        if path == "/api/terminal/poll":
            from nordctl.terminal import terminal_poll
            from urllib.parse import parse_qs

            qs = parse_qs(urlparse(self.path).query)
            sid = (qs.get("session") or [""])[0]
            cursor = int((qs.get("cursor") or ["0"])[0])
            wait = (qs.get("wait") or ["1"])[0] not in ("0", "false", "no")
            self._json(200, terminal_poll(sid, cursor, wait=wait))
            return
        if path.startswith("/api/"):
            self._json(404, {"ok": False, "error": "not found"})
            return
        if path.startswith("/status/"):
            from nordctl.status_share import render_status_page

            token = path[len("/status/") :].strip("/").split("/")[0]
            code, html = render_status_page(token)
            self.send_response(code)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            body = html.encode()
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if path in ("/help", "/help.html"):
            self._serve_static("help.html")
            return
        if path in ("/LEGAL.md", "/OPEN_SOURCE.md"):
            root = Path(__file__).resolve().parent.parent
            fp = root / path.lstrip("/")
            if fp.is_file():
                body = fp.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
        self._serve_static(path)

    def _post_error(self, exc: BaseException, path: str) -> None:
        self._json(
            500,
            {
                "ok": False,
                "error": str(exc) or exc.__class__.__name__,
                "path": path,
                "hint": "Restart nordctl serve and check the terminal for a traceback. If POST /api/action fails, update to the latest nordctl (server.py fix).",
            },
        )

    def do_POST(self) -> None:
        path = urlparse(self.path).path
        if path.startswith("/api/") and not self._enforce_auth(path, "POST"):
            return
        try:
            self._do_post(path)
        except Exception as exc:
            self._post_error(exc, path)

    def _do_post(self, path: str) -> None:
        if path in ("/api/ui-auth/login", "/api/lab-auth/login"):
            from nordctl.ui_auth import login

            body = self._read_json()
            self._json(200, login(str(body.get("password") or ""), load_config()))
            return
        if path in ("/api/ui-auth/logout", "/api/lab-auth/logout"):
            from nordctl.ui_auth import revoke_session

            revoke_session(self._session_token())
            self._json(200, {"ok": True})
            return
        if path == "/api/action":
            body = self._read_json()
            result = state_apply_action(body)
            code = 200 if result.get("ok", True) else 400
            self._json(code, result)
            return
        if path == "/api/overall-audit/email":
            from nordctl.overall_audit import run_overall_audit, send_audit_report_email

            audit_data = run_overall_audit()
            self._json(200, send_audit_report_email(load_config(), audit_data))
            return
        if path == "/api/install-nordvpn":
            from nordctl.nordvpn_install import run_official_install

            body = self._read_json()
            dry = bool(body.get("dry_run"))
            self._json(200, run_official_install(dry_run=dry))
            return
        if path == "/api/files/write":
            from nordctl.files import write_file

            body = self._read_json()
            fid = str(body.get("id") or "config")
            content = body.get("content")
            if not isinstance(content, str):
                self._json(400, {"ok": False, "error": "content string required"})
                return
            result = write_file(fid, content)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/files/validate":
            from nordctl.files import validate_content

            body = self._read_json()
            fid = str(body.get("id") or "config")
            content = body.get("content")
            if not isinstance(content, str):
                self._json(400, {"ok": False, "error": "content string required"})
                return
            result = validate_content(fid, content)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/files/create":
            from nordctl.files import create_user_preset

            body = self._read_json()
            result = create_user_preset(
                str(body.get("name") or ""),
                template=str(body.get("template") or "blank"),
            )
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/files/restore-baseline":
            from nordctl.files import restore_file_from_baseline

            body = self._read_json()
            result = restore_file_from_baseline(str(body.get("id") or "config"))
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/files/delete":
            from nordctl.files import delete_user_preset

            body = self._read_json()
            fid = str(body.get("id") or "")
            result = delete_user_preset(fid)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/wifi-profiles/add":
            from nordctl.files import insert_wifi_profiles_into_config

            body = self._read_json()
            names = body.get("profiles") or []
            if not isinstance(names, list):
                self._json(400, {"ok": False, "error": "profiles list required"})
                return
            self._json(200, insert_wifi_profiles_into_config([str(n) for n in names]))
            return
        if path == "/api/presets/builder/preview":
            from nordctl.preset_builder import preview_from_spec

            body = self._read_json()
            spec = body.get("spec") if isinstance(body.get("spec"), dict) else body
            result = preview_from_spec(spec or {})
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/presets/builder/create":
            from nordctl.preset_builder import create_preset_from_spec

            body = self._read_json()
            name = str(body.get("name") or body.get("filename") or "")
            spec = body.get("spec") if isinstance(body.get("spec"), dict) else body
            if isinstance(spec, dict):
                spec = {k: v for k, v in spec.items() if k not in {"name", "filename"}}
            result = create_preset_from_spec(name, spec or {})
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/presets/builder/update":
            from nordctl.preset_builder import update_preset_from_spec

            body = self._read_json()
            file_id = str(body.get("file_id") or body.get("id") or "")
            spec = body.get("spec") if isinstance(body.get("spec"), dict) else body
            if isinstance(spec, dict):
                spec = {k: v for k, v in spec.items() if k not in {"file_id", "id", "name", "filename"}}
            result = update_preset_from_spec(file_id, spec or {})
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/presets/preview":
            from nordctl.presets import preview_preset_yaml

            body = self._read_json()
            content = body.get("content")
            if not isinstance(content, str):
                self._json(400, {"ok": False, "error": "content string required"})
                return
            result = preview_preset_yaml(content)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/support-bundle":
            from nordctl.support_bundle import build_anonymized_support_bundle, build_support_bundle

            body = self._read_json()
            if body.get("anonymized"):
                self._json(200, build_anonymized_support_bundle())
            else:
                self._json(200, build_support_bundle())
            return
        if path == "/api/schedules/write":
            from nordctl.schedule import write_systemd_units

            self._json(200, write_systemd_units())
            return
        if path == "/api/nettools/run":
            from nordctl.nettools import run_tool

            body = self._read_json()
            tool = str(body.get("tool") or "overview")
            target = str(body.get("target") or "")
            result = run_tool(tool, target)
            code = 200 if result.get("ok", True) or result.get("output") else 400
            self._json(code, result)
            return
        if path == "/api/traffic/refresh":
            from nordctl.traffic_watch import run_traffic_watch

            body = self._read_json()
            filt = str(body.get("filter") or "all")
            self._json(200, run_traffic_watch(filt))
            return
        if path == "/api/logs/clear":
            from nordctl.activity_log import clear_entries

            self._json(200, clear_entries())
            return
        if path == "/api/logs/append":
            from nordctl.activity_log import log_client_event

            body = self._read_json()
            result = log_client_event(
                str(body.get("type") or "ui"),
                str(body.get("message") or "UI event"),
                ok=bool(body.get("ok", True)),
                detail=str(body.get("detail") or ""),
                technical=str(body.get("technical") or ""),
            )
            self._json(200, {"ok": True, "entry": result})
            return
        if path == "/api/speedtest":
            from nordctl.speedtest import run_speedtest, speedtest_api_payload, speedtest_defaults

            cfg = load_config()
            body = self._read_json()
            defaults = speedtest_defaults(cfg)
            result = run_speedtest(
                profile=str(body.get("profile") or defaults["default_profile"]),
                method=str(body.get("method") or defaults["default_method"]),
                provider=str(body.get("provider") or defaults["default_provider"]),
                warmup=bool(body.get("warmup")) if "warmup" in body else defaults["warmup"],
                cfg=cfg,
            )
            meta = body.get("meta") if isinstance(body.get("meta"), dict) else {}
            save = body.get("save") if "save" in body else defaults["save_results"]
            payload = speedtest_api_payload(
                result,
                meta=meta,
                save=bool(save) and result.get("ok"),
            )
            self._json(200, payload)
            return
        if path == "/api/speedtest/clear":
            from nordctl.speedtest_store import clear_entries

            self._json(200, clear_entries())
            return
        if path == "/api/capture":
            from nordctl.packet_capture import run_capture

            body = self._read_json()
            sec = int(body.get("seconds") or 10)
            self._json(200, run_capture(sec))
            return
        if path == "/api/export/config":
            from nordctl.config_bundle import export_config_bundle

            self._json(200, export_config_bundle())
            return
        if path == "/api/config/import":
            from nordctl.config_bundle import import_config_bundle

            body = self._read_json()
            path_arg = str(body.get("path") or body.get("archive") or "")
            merge = body.get("merge", True) is not False
            result = import_config_bundle(path_arg, merge=merge)
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/presets/community/import":
            from nordctl.community_presets import import_preset_from_url

            body = self._read_json()
            result = import_preset_from_url(str(body.get("url") or ""), load_config())
            code = 200 if result.get("ok") else 400
            self._json(code, result)
            return
        if path == "/api/export/logs":
            from nordctl.status_share import export_logs_text

            self._json(200, export_logs_text())
            return
        if path == "/api/onboarding/complete":
            body = self._read_json()
            self._json(200, state_apply_action(body, load_config()))
            return
        if path == "/api/alerts/config":
            body = self._read_json()
            body["action"] = "alerts_save"
            self._json(200, state_apply_action(body, load_config()))
            return
        if path == "/api/alerts/test":
            self._json(200, state_apply_action({"action": "alerts_test"}, load_config()))
            return
        if path == "/api/tools/install":
            body = self._read_json()
            from nordctl.tool_install import install_hub_tools, install_tool, install_tools_batch

            tools = body.get("tools")
            if isinstance(tools, list) and tools:
                self._json(200, install_tools_batch(tools, load_config()))
                return
            if body.get("all") and body.get("hub"):
                self._json(200, install_hub_tools(str(body.get("hub") or ""), load_config()))
                return
            tool_id = str(body.get("tool") or body.get("id") or "")
            self._json(200, install_tool(tool_id, load_config()))
            return
        if path == "/api/tools/uninstall":
            body = self._read_json()
            from nordctl.tool_install import uninstall_tool, uninstall_tools_batch

            tools = body.get("tools")
            if isinstance(tools, list) and tools:
                self._json(200, uninstall_tools_batch(tools, load_config()))
                return
            tool_id = str(body.get("tool") or body.get("id") or "")
            self._json(200, uninstall_tool(tool_id, load_config()))
            return
        if path == "/api/tools/custom":
            body = self._read_json()
            from nordctl.tool_install import (
                add_custom_tool,
                move_custom_tool_category,
                remove_custom_tool,
            )

            op = str(body.get("action") or body.get("op") or "add").strip().lower()
            if op in {"remove", "delete"}:
                self._json(
                    200,
                    remove_custom_tool(str(body.get("tool") or body.get("id") or ""), load_config()),
                )
            elif op == "move":
                self._json(
                    200,
                    move_custom_tool_category(
                        str(body.get("tool") or body.get("id") or ""),
                        str(body.get("category") or ""),
                        load_config(),
                    ),
                )
            else:
                self._json(200, add_custom_tool(body, load_config()))
            return
        if path == "/api/tools/categories":
            body = self._read_json()
            from nordctl.tool_install import add_tool_category, remove_tool_category

            op = str(body.get("action") or body.get("op") or "add").strip().lower()
            if op in {"remove", "delete"}:
                self._json(
                    200,
                    remove_tool_category(str(body.get("id") or body.get("category") or ""), load_config()),
                )
            else:
                self._json(200, add_tool_category(body, load_config()))
            return
        if path == "/api/terminal/open":
            from nordctl.terminal import open_session

            body = self._read_json()
            self._json(200, open_session(str(body.get("label") or "").strip() or None))
            return
        if path == "/api/terminal/input":
            from nordctl.terminal import terminal_input

            body = self._read_json()
            self._json(
                200,
                terminal_input(str(body.get("session") or ""), str(body.get("data") or "")),
            )
            return
        if path == "/api/terminal/resize":
            from nordctl.terminal import terminal_resize

            body = self._read_json()
            self._json(
                200,
                terminal_resize(
                    str(body.get("session") or ""),
                    int(body.get("rows") or 24),
                    int(body.get("cols") or 80),
                ),
            )
            return
        if path == "/api/terminal/close":
            from nordctl.terminal import terminal_close

            body = self._read_json()
            self._json(200, terminal_close(str(body.get("session") or "")))
            return
        if path == "/api/terminal/run-once":
            from nordctl.terminal import run_command_once

            body = self._read_json()
            self._json(
                200,
                run_command_once(
                    str(body.get("cmd") or ""),
                    label=str(body.get("label") or ""),
                    timeout=int(body.get("timeout") or 600),
                ),
            )
            return
        if path == "/api/terminal/quick-commands/settings":
            from nordctl.quick_commands_settings import save_settings

            body = self._read_json()
            self._json(200, save_settings(body, load_config()))
            return
        if path == "/api/ufw":
            body = self._read_json()
            from nordctl.ufw_control import apply_action as ufw_apply_action

            self._json(200, ufw_apply_action(body, load_config()))
            return
        self._json(404, {"ok": False, "error": "not found"})


def run_server(
    bind: str | None = None,
    port: int | None = None,
    *,
    explicit_port: bool = False,
    demo: bool = False,
) -> None:
    cfg = load_config()
    if demo:
        from nordctl.demo_mode import set_demo_mode

        set_demo_mode(True, persist=False, cfg=cfg)
        os.environ["NORDCTL_DEMO"] = "1"
    srv = cfg.get("server") or {}
    host = bind or str(srv.get("bind") or "127.0.0.1")
    preferred = int(port if port is not None else srv.get("port") or 8765)
    try:
        listen_port, replaced = resolve_listen_port(host, preferred, explicit=explicit_port)
    except OSError as exc:
        if explicit_port and "already in use" in str(exc).lower():
            from nordctl.paths import resolve_nordctl_bin
            from nordctl.service_mgr import stop_manual_serve_processes, ui_service_status

            manual = stop_manual_serve_processes()
            if is_port_free(host, preferred):
                listen_port, replaced = preferred, None
            else:
                st = ui_service_status(cfg)
                bin_path = resolve_nordctl_bin()
                msg = (
                    f"Port {preferred} on {host} is already in use.\n\n"
                    f"Another nordctl serve is running (manual PIDs: {st.get('manual_pids') or 'none'}).\n"
                    f"Use ONE of these — not both:\n"
                    f"  {bin_path} service restart   # systemd user service (recommended)\n"
                    f"  {bin_path} serve             # manual foreground (Ctrl+C to stop)\n\n"
                    f"If restart does not free the port: ss -tlnp | grep {preferred}"
                )
                if manual.get("stopped"):
                    msg += f"\n\nStopped PIDs: {manual['stopped']} — try again."
                raise OSError(msg) from exc
        else:
            raise
    if replaced is not None:
        print(
            f"Port {replaced} is in use — serving on {listen_port} instead "
            f"(run `nordctl init --fix-port` to save this port)",
            flush=True,
        )
    from nordctl.activity_log import record_event

    from nordctl.demo_mode import is_demo_mode

    demo_active = demo or is_demo_mode(cfg)
    headless = bool((cfg.get("server") or {}).get("headless"))
    detail = f"Web UI available at http://{host}:{listen_port}/"
    if demo_active:
        detail += " — DEMO MODE (no real VPN changes)"
    if headless:
        detail += " — headless profile"
    record_event(
        "system",
        "Dashboard started",
        detail=detail + " — actions will be logged under Logs.",
        level="info",
        ok=True,
    )
    if not demo_active and not headless:
        try:
            from nordctl.disconnect_watch import start_disconnect_watch

            start_disconnect_watch()
        except Exception:
            pass
    if not demo_active:
        try:
            from nordctl.wifi_zone_watch import start_zone_watch
            from nordctl.config import load_config as lc

            if (lc().get("wifi_zones") or {}).get("watch_enabled"):
                start_zone_watch()
        except Exception:
            pass
        try:
            from nordctl.alerts import start_alerts_watch
            from nordctl.features import is_module_enabled
            from nordctl.config import load_config as lc2, is_headless

            c = lc2()
            if (
                not is_headless(c)
                and is_module_enabled("alerts", c)
                and (c.get("alerts") or {}).get("watch_enabled", True)
            ):
                start_alerts_watch()
        except Exception:
            pass
    httpd = ThreadingHTTPServer((host, listen_port), NordctlHandler)
    if demo_active:
        print(f"nordctl DEMO  http://{host}:{listen_port}/  (simulated VPN — no changes applied)", flush=True)
    else:
        print(f"nordctl UI  http://{host}:{listen_port}/", flush=True)
    print("Press Ctrl+C to stop.", flush=True)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.", flush=True)


def start_background(bind: str | None = None, port: int | None = None) -> threading.Thread:
    t = threading.Thread(target=run_server, args=(bind, port), name="nordctl-http", daemon=True)
    t.start()
    return t
