# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# nordctl self-test — run before manual UI retest
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
if [[ -z "${NORDCTL_CONFIG_DIR:-}" && ( -n "${CI:-}" || -n "${GITHUB_ACTIONS:-}" ) ]]; then
  export NORDCTL_CONFIG_DIR="${RUNNER_TEMP:-/tmp}/nordctl-selftest-config"
  rm -rf "$NORDCTL_CONFIG_DIR"
  mkdir -p "$NORDCTL_CONFIG_DIR"
fi
if [[ -z "${PY:-}" ]]; then
  if [[ -x "$ROOT/.venv/bin/python" ]]; then
    PY="$ROOT/.venv/bin/python"
  else
    PY="$(command -v python3 || command -v python)"
  fi
fi
nordctl_cli() {
  if [[ -n "${BIN:-}" ]]; then
    "$BIN" "$@"
  elif [[ -x "$ROOT/.venv/bin/nordctl" ]]; then
    "$ROOT/.venv/bin/nordctl" "$@"
  elif command -v nordctl >/dev/null 2>&1; then
    nordctl "$@"
  else
    "$PY" -m nordctl "$@"
  fi
}
PORT="${PORT:-8778}"
ST_FAIL=0

red() { echo -e "\033[0;31mFAILED\033[0m $*" >&2; ST_FAIL=1; }
grn() { echo -e "\033[0;32mOK\033[0m $*" >&2; }

run() {
  if "$@"; then grn "$*"; else red "$*"; fi
}

run_nordctl() {
  if nordctl_cli "$@" >/dev/null 2>&1; then
    grn "nordctl $*"
  else
    red "nordctl $*"
  fi
}

echo "=== nordctl self-test ==="

run "$PY" -m py_compile \
  nordctl/traffic_watch.py \
  nordctl/traffic_map.py \
  nordctl/activity_log.py \
  nordctl/service_mgr.py \
  nordctl/state.py \
  nordctl/preset_builder.py \
  nordctl/server.py \
  nordctl/terminal.py \
  nordctl/cli.py \
  nordctl/nettools.py \
  nordctl/factory_reset.py \
  nordctl/tool_install.py \
  nordctl/ufw_control.py \
  nordctl/help_content.py \
  nordctl/security_hub.py \
  nordctl/health_score.py \
  nordctl/bandwidth.py \
  nordctl/speedtest.py \
  nordctl/dns_assistant.py \
  nordctl/ipv6_lan.py \
  nordctl/disconnect_watch.py \
  nordctl/packet_capture.py \
  nordctl/status_share.py \
  nordctl/wifi_hub.py \
  nordctl/wifi_doctor.py \
  nordctl/wifi_zone_watch.py \
  nordctl/network_linux.py \
  nordctl/ip_info.py \
  nordctl/network_access.py \
  nordctl/config_fields.py \
  nordctl/features.py \
  nordctl/alerts.py \
  nordctl/privacy.py \
  nordctl/onboarding.py \
  nordctl/roadmap.py \
  nordctl/ui_auth.py \
  nordctl/demo_mode.py \
  nordctl/preset_verify.py \
  nordctl/config_bundle.py \
  nordctl/community_presets.py \
  nordctl/compatibility.py \
  nordctl/connection_journal.py \
  nordctl/hooks.py \
  nordctl/home_ip.py \
  nordctl/settings_panel.py

run "$PY" -c "from nordctl.features import features_payload; assert features_payload()['ok']"
run "$PY" -c "from nordctl.privacy import privacy_manifest; p=privacy_manifest(); assert p['ok'] and p['open_source'].get('source_id')"
run "$PY" -c "from nordctl.provenance import SOURCE_ID, SOURCE_MARKER, provenance_payload; from pathlib import Path; assert provenance_payload()['source_id']==SOURCE_ID; assert SOURCE_MARKER in Path('nordctl/config.py').read_text(encoding='utf-8')"
run "$PY" -c "from nordctl.alerts import alerts_status, test_alerts; test_alerts()"
run "$PY" -c "from nordctl.roadmap import roadmap_payload; assert len(roadmap_payload()['tiers'])==6"
run "$PY" -c "from nordctl.presets import load_presets; p=load_presets(); assert any(x['id']=='eu-privacy' for x in p), 'regional presets'"
run "$PY" -c "from nordctl.presets import load_presets, preset_region; p=next(x for x in load_presets() if x['id']=='eu-privacy'); assert preset_region(p)=='europe', preset_region(p)"

run "$PY" -c "from nordctl.factory_reset import factory_reset; assert callable(factory_reset)"
run "$PY" -c "from nordctl.config_fields import reset_presets_factory, PRESET_PANEL_CATEGORIES; assert 'split-tunnel' in PRESET_PANEL_CATEGORIES"
run "$PY" -c "from nordctl.switches_panel import switches_payload, SWITCH_BY_ID, apply_switch, apply_live_constraints, detect_server_group; p=switches_payload(); assert 'sections' in p; ids=['split-tunnel-lan','connect-p2p','connect-double-vpn','connect-onion-over-vpn','connect-dedicated-ip','obfuscate','protocol','restore-defaults','fwmark','user-consent']; assert all(i in SWITCH_BY_ID for i in ids); flat=[sw for s in p['sections'] for sw in s.get('switches',[])]; assert len(flat) >= 22, len(flat); assert not apply_switch('user-consent', 'off')['ok']; assert not apply_switch('fwmark', 'not-hex')['ok']"
run "$PY" -c "from nordctl.switches_panel import apply_live_constraints, SWITCH_BY_ID, detect_server_group; row={'id':'protocol','current':{}}; apply_live_constraints(row, SWITCH_BY_ID['protocol'], settings={'Technology':'NORDLYNX'}, status={}, connected=True, connection={}); assert row.get('blocked'); assert detect_server_group({'Server':'Onion Over VPN #12'}, {})=='Onion_Over_VPN'"
run "$PY" -c "from nordctl.tool_install import tools_payload, _hub_items; from nordctl.security_hub import location_profiles; p=tools_payload(); assert p['ok'] and len(p['groups']['network']['tools'])==30 and len(p['groups']['security']['tools'])==30 and len(_hub_items('network'))==30 and len(_hub_items('security'))==30 and len(location_profiles())==15"
run "$PY" -c "from nordctl.demo_mode import is_demo_mode, build_demo_state_quick, simulate_preset_apply; import os; os.environ['NORDCTL_DEMO']='1'; assert is_demo_mode(); q=build_demo_state_quick(); assert q.get('demo_mode'); s=simulate_preset_apply('disconnect'); assert s.get('ok')"
run "$PY" -c "from nordctl.presets import dry_run_preset; r=dry_run_preset('disconnect'); assert r.get('dry_run') and r.get('steps')"
run "$PY" -c "from nordctl.preset_verify import verify_after_preset; v=verify_after_preset(demo=True); assert v.get('total')>=4"
run "$PY" -c "from nordctl.config_bundle import redact_config, export_config_bundle; c=redact_config({'alerts':{'email':{'smtp_password':'secret'}}}); assert c['alerts']['email']['smtp_password']=='REDACTED'; e=export_config_bundle(); assert e.get('ok')"
run "$PY" -c "from nordctl.community_presets import list_community_presets; lp=list_community_presets(); assert lp.get('ok') and any(p['id']=='community-smart-dns-lite' for p in lp.get('presets',[]))"
run "$PY" -c "from nordctl.compatibility import compatibility_matrix; m=compatibility_matrix(); assert m.get('ok') and len(m.get('platforms',[]))>=5"
run "$PY" -c "from nordctl.hooks import hooks_status; assert hooks_status()['ok']"
run "$PY" -c "from nordctl.connection_journal import record_preset_apply, list_journal; record_preset_apply('disconnect', ok=True); assert list_journal(limit=1)['entries']"
run "$PY" -c "from nordctl.support_bundle import build_anonymized_support_bundle; b=build_anonymized_support_bundle(); assert b.get('ok') and b.get('anonymized')"
run "$PY" -c "from nordctl.state import build_state_app, build_state_nord, build_state_network, merge_state; a=build_state_app(include_doctor=False); n=build_state_nord(quick=True); m=merge_state(a,n,build_state_network(status=n.get('status'), settings=n.get('settings'), fast_ip=True)); assert m.get('ok')"
run "$PY" -c "
from unittest.mock import patch
from nordctl.home_ip import learn_public_ip, resolve_home_ip, cache_path
import json
from pathlib import Path
p = cache_path()
p.parent.mkdir(parents=True, exist_ok=True)
p.write_text('{\"by_network\":{}}')
cfg = {'wifi_zones': {'home_ip_when_trusted': True, 'trusted': [{'ssid': 'HomeWiFi', 'preset': 'x'}]}}
learn_public_ip(cfg, '217.0.0.1', ssid='HomeWiFi')
with patch('nordctl.zones.zone_status', lambda c: {'ssid': 'HomeWiFi', 'is_trusted': True, 'trusted_match': {'ssid': 'HomeWiFi'}}):
    r = resolve_home_ip(cfg, connected=True, probe_ip=None, live_public_ip=None, vpn_ip='212.129.44.236')
    assert r['show'] and r['ip'] == '217.0.0.1', r
with patch('nordctl.zones.zone_status', lambda c: {'ssid': 'HotelGuest', 'is_trusted': False, 'trusted_match': None}):
    r2 = resolve_home_ip(cfg, connected=True, probe_ip=None, live_public_ip=None, vpn_ip='212.129.44.236')
    assert not r2['show'], r2
cfg_profiles = {'wifi': {'profiles': ['MyHomeWiFi']}, 'wifi_zones': {'home_ip_when_trusted': True, 'trusted': []}}
learn_public_ip(cfg_profiles, '217.70.251.209', ssid='MyHomeWiFi')
with patch('nordctl.zones.zone_status', lambda c: {'ssid': 'MyHomeWiFi', 'is_trusted': False, 'trusted_match': None}):
    r3 = resolve_home_ip(cfg_profiles, connected=True, probe_ip=None, live_public_ip='212.129.44.236', vpn_ip='212.129.44.236')
    assert r3['show'] and r3['ip'] == '217.70.251.209', r3
learn_public_ip(cfg_profiles, '212.129.44.236', ssid='BadLearn')
with patch('nordctl.zones.zone_status', lambda c: {'ssid': 'BadLearn', 'is_trusted': False, 'trusted_match': None}):
    r4 = resolve_home_ip(cfg_profiles, connected=True, probe_ip=None, live_public_ip='212.129.44.236', vpn_ip='212.129.44.236')
    assert not r4.get('show') or r4.get('ip') != '212.129.44.236', r4
"
run "$PY" -c "from nordctl.vpn_detect import analyze_vpn, default_route; assert 'device' in default_route(); a=analyze_vpn({'connected': False}, routed_public_ip='198.51.100.2'); assert isinstance(a, dict)"
run "$PY" -c "from nordctl.connection_details import build_connection_details; from nordctl.config import load_config; d=build_connection_details(load_config(), {'connected': False}); assert d.get('ok') and 'path' in d"
run "$PY" -c "from nordctl.service_mgr import control_ui_service, schedule_ui_restart; r=control_ui_service('restart'); assert r.get('ok') and r.get('scheduled'), r"

run "$PY" -c "from nordctl.wifi_hub import wifi_hub_payload; assert wifi_hub_payload()['ok']"

run "$PY" -c "from nordctl.wifi_doctor import run_all_wifi_hub_doctors; assert 'wifi' in run_all_wifi_hub_doctors()"

run "$PY" -c "from nordctl.wifi_doctor import run_all_wifi_hub_doctors; d=run_all_wifi_hub_doctors(); assert 'wifi' in d and 'network' in d"
run "$PY" -c "from nordctl.files import read_file; r=read_file('bundled/streaming-smartdns.yaml'); assert r.get('ok'), r.get('error', r)"
run "$PY" -c "from nordctl.preset_builder import preview_from_spec, builder_schema; s=builder_schema(); assert s['ok']; p=preview_from_spec({'label':'Test','connection_mode':'vpn','server_group':'Double_VPN','country_source':'none'}); assert p['ok'] and any('Double' in r['value'] for r in p['breakdown']['switches']); f=preview_from_spec({'connection_mode':'vpn','technology':'NORDLYNX','protocol':'UDP'}); assert f['fields']['protocol']['state']=='disabled'"
run "$PY" -c "from nordctl.tool_install import _tool_by_id, _is_installed, _bin_exists; t=_tool_by_id('tshark'); assert t['id']=='tshark' and t['packages']==['tshark']; assert _tool_by_id('wireshark-common')['id']=='tshark'; assert _bin_exists('sh') or _bin_exists('bash'); print('tshark catalog ok')"
run "$PY" -c "from nordctl.overall_audit import run_overall_audit, audit_tool_requirements, format_audit_report_text; r=run_overall_audit(); assert 'categories' in r and 'tools' in r; assert format_audit_report_text(r); t=audit_tool_requirements(); assert 'missing_installable' in t and 'can_install' in t; print('audit', r['passed'], r['total'])"

run "$PY" -c "from nordctl.config_fields import location_settings, set_config_field, missing_requirement; assert location_settings()['ok']; assert missing_requirement('connect_city')['field']=='connect_city'"
run "$PY" -c "from nordctl.help_content import get_help_sections, help_payload; from nordctl.config import load_config; assert len(get_help_sections())>=37; c=load_config(); c['install_profile']='nord'; assert len(help_payload(c)['sections'])>=15; c['install_profile']='network'; assert len(help_payload(c)['sections'])>=18"

run "$PY" -c "from nordctl.nettools import run_tool, TOOL_DEFS; assert len(TOOL_DEFS)>=18; run_tool('public_ip'); ufw=next(t for t in TOOL_DEFS if t['id']=='ufw'); nft=next(t for t in TOOL_DEFS if t['id']=='nft'); nmap=next(t for t in TOOL_DEFS if t['id']=='nmap'); assert ufw.get('needs_root') and ufw.get('terminal_cmd','').startswith('sudo ufw'); assert nft.get('terminal_cmd','').startswith('sudo nft'); assert nmap.get('needs_root') and '{target}' in nmap.get('terminal_cmd','')"
run "$PY" -c "from nordctl.ufw_control import preset_catalog, VIBER_PORTS, _viber_rule_args; assert any(p['id']=='viber' for p in preset_catalog()); assert len(_viber_rule_args())==len(VIBER_PORTS)*2"
run "$PY" -c "from nordctl.settings_panel import settings_payload; s=settings_payload()['services']; assert 'ui_running' in s and 'ui_manual' in s; print('settings ui_running', s['ui_running'], 'manual', s['ui_manual'])"
run "$PY" -c "from nordctl.scan_alerts import identify_scan, parse_scan_result, scan_output_complete; assert identify_scan('sudo lynis audit system')=='lynis'; p=parse_scan_result('lynis', 'Hardening index : [42]\\n! warning\\n'); assert p['score']==42 and p['has_findings']; assert scan_output_complete('lynis', 'Hardening index : [42]')"
run "$PY" -c "from nordctl.terminal import quick_commands, _nord_quick_commands, _security_quick_commands; from nordctl.paths import install_script_path, PRIV_SUDOERS_SCRIPT, resolve_nordctl_bin; n=quick_commands(scope='nord'); w=quick_commands(scope='network'); s=quick_commands(scope='security'); assert n['scope']=='nord' and w['scope']=='network' and s['scope']=='security'; nord_raw=_nord_quick_commands(resolve_nordctl_bin()); assert any('login' in c['cmd'] for c in nord_raw); assert not any('nordvpn login' in c['cmd'] for c in w['commands']); sec_raw=_security_quick_commands(resolve_nordctl_bin(), install_script_path(PRIV_SUDOERS_SCRIPT)); assert any('lynis' in c['cmd'].lower() for c in sec_raw); assert not any('lynis' in c['cmd'].lower() for c in w['commands'])"
run "$PY" -c "from nordctl.activity_log import _CATEGORIES, clear_entries, list_entries, record_event, _legacy_category_match; assert 'scan' in _CATEGORIES and 'install' in _CATEGORIES and 'terminal' in _CATEGORIES; clear_entries(); record_event('scan', 'Lynis audit'); record_event('install', 'Installed tcpdump'); assert list_entries(category='scan'); assert _legacy_category_match({'category':'security','title':'Lynis audit failed'}, 'scan')"

run_nordctl service status
run_nordctl traffic --filter internet
run_nordctl logs -n 5
run_nordctl security
run_nordctl wifi status
run_nordctl wifi doctor
run_nordctl onboard --all --non-interactive

# Static assets reference check
run "$PY" scripts/check_static_ui.py


run "$PY" -c "
from nordctl.speedtest import _PROVIDERS, _PROFILES, _auto_chain, _provider_url
src = open('nordctl/speedtest.py', encoding='utf-8').read()
assert 'hetzner.de' not in src, 'deprecated speed.hetzner.de must not be used'
for pid in ('linode_frankfurt', 'linode_singapore', 'linode_tokyo', 'linode_sydney', 'cloudflare'):
    assert pid in _PROVIDERS, pid
    url = _provider_url(pid, _PROFILES['quick'])
    assert url.startswith('http'), url
chain = _auto_chain({'country_code': 'SG'})
assert chain[0] == 'cloudflare' and 'linode_singapore' in chain
print('speedtest global mirrors ok')
"

# API smoke (temp server)
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${PORT}/tcp" 2>/dev/null || true
  sleep 0.3
fi
nordctl_cli serve --port "$PORT" &
SPID=$!
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${PORT}/api/state/quick" >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
cleanup() { kill "$SPID" 2>/dev/null || true; wait "$SPID" 2>/dev/null || true; }
trap cleanup EXIT

check_api() {
  local path="$1" expect="$2"
  local body
  body=$(curl -sf "http://127.0.0.1:${PORT}${path}" || echo "")
  if "$PY" -c "import json,sys; d=json.loads(sys.argv[1]); sys.exit(0 if d.get('ok')${expect} else 1)" "$body" 2>/dev/null; then
    grn "GET $path"
  else
    red "GET $path"
  fi
}

check_api "/api/state" "!=False"
check_api "/api/state/quick" "!=False"
check_api "/api/state/app" "!=False"
check_api "/api/state/nord" "!=False"
check_api "/api/state/network" "!=False"
check_api "/api/security/summary" "!=False"
"$PY" -c "
import json, urllib.request
d = json.load(urllib.request.urlopen('http://127.0.0.1:${PORT}/api/state/quick'))
ip = d.get('ip_info') or {}
assert 'chain' in ip, ip
print('ip_info chain:', len(ip.get('chain') or []))
" && grn "ip_info in /api/state/quick" || red "ip_info in /api/state/quick"
check_api "/api/service" "!=False"
check_api "/api/traffic?filter=all" "!=False"
check_api "/api/traffic" "!=False"
check_api "/api/logs" "!=False"
check_api "/api/security" "!=False"
check_api "/api/wifi/hub" "!=False"
check_api "/api/onboarding" "!=False"
check_api "/api/privacy" "!=False"
check_api "/api/provenance" "!=False"
check_api "/api/alerts" "!=False"
check_api "/api/roadmap" "!=False"
check_api "/api/bandwidth" "!=False"
check_api "/api/tools" "!=False"
check_api "/api/ufw" "!=False"
check_api "/api/switches" "!=False"
check_api "/api/terminal/commands" "!=False"
check_api "/api/terminal/sessions" "!=False"
check_api "/api/help" "!=False"
check_api "/api/presets/builder/schema" "!=False"
check_api "/api/demo" "!=False"
check_api "/api/compatibility" "!=False"
check_api "/api/presets/community" "!=False"
check_api "/api/hooks" "!=False"
run "$PY" -c "from nordctl.security_hub import security_hub_summary; s=security_hub_summary(); assert s.get('ok') and s.get('summary') and s.get('health')"

OPENAPI_OK=$("$PY" -c "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:${PORT}/api/openapi'); print('ok' if b'openapi:' in r.read() else 'fail')" 2>/dev/null || echo "fail")
if [[ "$OPENAPI_OK" == "ok" ]]; then grn "GET /api/openapi"; else red "GET /api/openapi"; fi

HELP_N=$("$PY" -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:${PORT}/api/help')); print(len(d.get('sections',[])))")
if [[ "$HELP_N" -ge 15 ]]; then grn "help sections via API (profile-filtered): $HELP_N"; else red "help sections via API: $HELP_N"; fi

TRAFFIC_N=$("$PY" -c "import json,urllib.request; d=json.load(urllib.request.urlopen('http://127.0.0.1:${PORT}/api/traffic')); c=d.get('counts') or {}; print(int(c.get('internet_outbound') or 0)+int(c.get('local_sessions') or 0)+int(c.get('internet_inbound') or 0))")
if [[ "$TRAFFIC_N" -ge 0 ]]; then grn "traffic map via API: $TRAFFIC_N sessions"; else red "traffic map via API"; fi

check_post() {
  local label="$1"
  local path="$2"
  local body="$3"
  local expect_ok="${4:-1}"
  if POST_BODY="$body" POST_PATH="$path" POST_EXPECT="$expect_ok" POST_PORT="$PORT" "$PY" -c '
import json, os, sys, urllib.error, urllib.request
body = os.environ["POST_BODY"]
path = os.environ["POST_PATH"]
port = os.environ["POST_PORT"]
expect_ok = os.environ["POST_EXPECT"] == "1"
req = urllib.request.Request(
    f"http://127.0.0.1:{port}{path}",
    data=body.encode(),
    headers={"Content-Type": "application/json"},
    method="POST",
)
try:
    with urllib.request.urlopen(req, timeout=90) as r:
        d = json.loads(r.read())
except urllib.error.HTTPError as e:
    d = json.loads(e.read().decode() or "{}")
ok = bool(d.get("ok", True))
sys.exit(0 if ok == expect_ok else 1)
' 2>/dev/null; then
    grn "POST ${path} (${label})"
  else
    red "POST ${path} (${label})"
  fi
}

check_post "set_server_access local" "/api/action" '{"action":"set_server_access","mode":"local","restart":false}'
check_post "set_usage_mode tools_only" "/api/action" '{"action":"set_usage_mode","mode":"tools_only"}'
check_post "set_connect_country" "/api/action" '{"action":"set_connect_country","country":"Germany"}'
check_post "preset_reset_factory server-groups" "/api/action" '{"action":"preset_reset_factory","panel":"server-groups"}'
check_post "preset builder preview" "/api/presets/builder/preview" '{"spec":{"label":"Selftest","connection_mode":"vpn","technology":"OPENVPN","protocol":"UDP","country_source":"config"}}'
check_post "preset dry run" "/api/action" '{"action":"preset_dry_run","preset":"disconnect"}'
check_post "ufw JSON error path" "/api/ufw" '{"action":"__invalid__"}' 0

bash -n scripts/audit-public.sh && grn "audit-public.sh syntax" || red "audit-public.sh syntax"
bash scripts/audit-public.sh && grn "audit-public.sh scan" || red "audit-public.sh scan"
bash -n scripts/build-deb.sh && grn "build-deb.sh syntax" || red "build-deb.sh syntax"
bash -n scripts/uninstall.sh && grn "uninstall.sh syntax" || red "uninstall.sh syntax"

bash -n install.sh && grn "install.sh syntax" || red "install.sh syntax"
bash -n scripts/install-ufw-sudoers.sh && grn "install-ufw-sudoers.sh syntax" || red "install-ufw-sudoers.sh syntax"
bash -n scripts/install-privilege-sudoers.sh && grn "install-privilege-sudoers.sh syntax" || red "install-privilege-sudoers.sh syntax"

echo ""
if (( ST_FAIL )); then
  echo "Some checks failed." >&2
  exit 1
fi
echo "All self-tests passed."
