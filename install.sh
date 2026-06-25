#!/usr/bin/env bash
# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
# nordctl installer for Linux — blue-screen first-run wizard (whiptail)
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -uo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
SYSTEM=0
SKIP_UI=0
INSTALL_NORDVPN=0
INSTALL_TRAY=0
INSTALL_UI=0
INSTALL_MODE=""
USE_WHIPTAIL=0
WHIPTAIL=""
OPEN_BROWSER=0
UI_PORT=8765
UI_BACKTITLE="nordctl  ·  Linux VPN & network control"
BIN=""
PATH_UPDATED=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info() { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}!!${NC} $*" >&2; }
fail() { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --system            Install with sudo to /usr/local (system-wide)
  --prefix PATH       User install prefix (default: ~/.local)
  --install-nordvpn   Install official NordVPN client after nordctl
  --all               VPN focus + NordVPN + UI at login + tray (no prompts)
  --minimal           nordctl only — no extras (no prompts)
  --profile MODE      nord | network | minimal (skip wizard)
  --install-tray      Enable system tray + login autostart
  --no-tray           Skip tray
  --install-ui-service  Start web dashboard at login
  --no-ui-service     Skip UI systemd service
  --skip-ui           Skip UI service
  -h, --help          Show help

Interactive: run ./install.sh for the blue setup wizard.
Requires: Python 3.10+ (venv is created automatically on Ubuntu 24.04+)
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) SYSTEM=1; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --install-nordvpn) INSTALL_NORDVPN=1; shift ;;
    --all) INSTALL_MODE=all; INSTALL_NORDVPN=1; INSTALL_UI=1; INSTALL_TRAY=1; shift ;;
    --minimal) INSTALL_MODE=minimal; shift ;;
    --profile)
      case "${2:-}" in
        nord|vpn) INSTALL_MODE=vpn ;;
        network) INSTALL_MODE=network ;;
        minimal) INSTALL_MODE=minimal ;;
        *) fail "Unknown --profile (use nord, network, or minimal)" ;;
      esac
      shift 2
      ;;
    --install-tray) INSTALL_TRAY=1; shift ;;
    --no-tray) INSTALL_TRAY=0; shift ;;
    --install-ui-service) INSTALL_UI=1; shift ;;
    --no-ui-service) INSTALL_UI=0; shift ;;
    --skip-ui) SKIP_UI=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1 (try --help)" ;;
  esac
done

pip_externally_managed() {
  python3 -c 'import sys, pathlib
p = pathlib.Path(getattr(sys, "base_prefix", sys.prefix)) / "lib" / f"python{sys.version_info.major}.{sys.version_info.minor}" / "EXTERNALLY-MANAGED"
raise SystemExit(0 if p.is_file() else 1)' 2>/dev/null
}

ensure_user_venv() {
  VENV_DIR="${NORDCTL_VENV_DIR:-$HOME/.local/share/nordctl/venv}"
  if [[ -x "$VENV_DIR/bin/python" ]] && "$VENV_DIR/bin/python" -m pip --version >/dev/null 2>&1; then
    PIP="$VENV_DIR/bin/pip"
    export VENV_DIR PIP
    return 0
  fi
  if [[ -d "$VENV_DIR" ]]; then
    warn "Removing incomplete virtualenv at $VENV_DIR"
    rm -rf "$VENV_DIR"
  fi
  if python3 -m venv "$VENV_DIR" 2>/dev/null; then
    PIP="$VENV_DIR/bin/pip"
    export VENV_DIR PIP
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1; then
    local pyver
    pyver="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
    info "python3-venv missing — installing python${pyver}-venv (sudo may ask for your password)…"
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
      "python${pyver}-venv" python3-venv python3-pip \
      || fail "Could not install python${pyver}-venv. Run: sudo apt install python${pyver}-venv"
  else
    fail "Could not create venv. Install python3-venv for your distro."
  fi
  rm -rf "$VENV_DIR"
  python3 -m venv "$VENV_DIR" || fail "venv creation failed after installing python3-venv"
  PIP="$VENV_DIR/bin/pip"
  export VENV_DIR PIP
}

install_user_package() {
  local spec="$1"
  mkdir -p "$PREFIX/bin" "$PREFIX/share/nordctl"
  if [[ "$spec" == "." ]]; then
    rm -rf build/ ./*.egg-info UNKNOWN.egg-info 2>/dev/null || true
  fi
  ensure_user_venv
  "$PIP" install -q "$spec" || fail "pip install failed in venv"
  ln -sf "$VENV_DIR/bin/nordctl" "$PREFIX/bin/nordctl"
  export PATH="$PREFIX/bin:$PATH"
  BIN="${PREFIX}/bin/nordctl"
  [[ -x "$BIN" ]] || fail "nordctl not found after install (expected $BIN)"
}

pip_install_extra() {
  if [[ -n "${PIP:-}" && -x "$PIP" ]]; then
    "$PIP" install -q "$@" 2>/dev/null
  elif (( SYSTEM )); then
    sudo pip3 install --break-system-packages -q "$@" 2>/dev/null || sudo pip3 install -q "$@"
  else
    pip3 install --user -q "$@" 2>/dev/null
  fi
}

ensure_whiptail() {
  if command -v whiptail >/dev/null 2>&1; then
    WHIPTAIL=whiptail
    return 0
  fi
  if command -v dialog >/dev/null 2>&1; then
    WHIPTAIL=dialog
    return 0
  fi
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y whiptail >/dev/null 2>&1 || true
  fi
  command -v whiptail >/dev/null 2>&1 || command -v dialog >/dev/null 2>&1 || return 1
  WHIPTAIL="$(command -v whiptail || command -v dialog)"
}

ui_msg() {
  "$WHIPTAIL" --backtitle "$UI_BACKTITLE" --title "$1" --msgbox "$2" "${3:-18}" "${4:-72}" 2>/dev/null
}

ui_yesno() {
  "$WHIPTAIL" --backtitle "$UI_BACKTITLE" --title "$1" --yesno "$2" "${3:-14}" "${4:-72}" 2>/dev/null
}

ui_radiolist() {
  local title="$1" text="$2" height="$3" width="$4" menu_height="$5"
  shift 5
  "$WHIPTAIL" --backtitle "$UI_BACKTITLE" --title "$title" --radiolist "$text" "$height" "$width" "$menu_height" "$@" 3>&1 1>&2 2>/dev/null
}

ui_checklist() {
  local title="$1" text="$2" height="$3" width="$4" menu_height="$5"
  shift 5
  "$WHIPTAIL" --backtitle "$UI_BACKTITLE" --title "$title" --checklist "$text" "$height" "$width" "$menu_height" "$@" 3>&1 1>&2 2>/dev/null
}

WIZARD_KEYS="Up/Down move · Space select · Tab to OK/Cancel · Enter confirm"

wizard_pick_extras() {
  local picked
  picked="$(ui_checklist "Startup & browser" \
"Optional extras.

${WIZARD_KEYS}" \
14 72 2 \
  "login" "Start dashboard at login (recommended)" ON \
  "browser" "Open dashboard in browser when install finishes" ON)" || exit 0
  INSTALL_UI=0
  OPEN_BROWSER=0
  [[ "$picked" == *\"login\"* || "$picked" == *login* ]] && INSTALL_UI=1
  [[ "$picked" == *\"browser\"* || "$picked" == *browser* ]] && OPEN_BROWSER=1
}

open_dashboard_browser() {
  ensure_dashboard_reachable || true
  read_ui_port
  local url="http://127.0.0.1:${UI_PORT}/"
  if command -v xdg-open >/dev/null 2>&1; then
    xdg-open "$url" >/dev/null 2>&1 &
  elif command -v gio >/dev/null 2>&1; then
    gio open "$url" >/dev/null 2>&1 &
  elif command -v sensible-browser >/dev/null 2>&1; then
    sensible-browser "$url" >/dev/null 2>&1 &
  fi
}

blue_screen_wizard() {
  ui_msg "Welcome to nordctl" \
"          nordctl
    -----------------------
  VPN · WiFi · firewall · network control

${WIZARD_KEYS}

WiFi, country, Nord login, and presets are set up
inside the dashboard wizard — not here." 18 72 || exit 0

  local choice
  choice="$(ui_radiolist "Choose your starting mode" \
"What should nordctl focus on first?

${WIZARD_KEYS}" \
17 70 3 \
  "minimal" "CLI + dashboard only" OFF \
  "vpn" "Nord VPN — connect & presets (recommended)" ON \
  "network" "Network & Security — no Nord account" OFF)" || exit 0

  INSTALL_MODE="$choice"
  case "$INSTALL_MODE" in
    minimal)
      INSTALL_NORDVPN=0
      ;;
    vpn)
      if ui_yesno "NordVPN client" \
"Install the official NordVPN Linux client now?

Yes — you have a Nord account
No  — install later from the dashboard

${WIZARD_KEYS}" 14 72; then
        INSTALL_NORDVPN=1
      else
        INSTALL_NORDVPN=0
      fi
      ;;
    network)
      INSTALL_NORDVPN=0
      ;;
  esac

  wizard_pick_extras

  local boot_note="manual: nordctl serve"
  (( INSTALL_UI )) && boot_note="enabled at login (systemd user service)"
  local browser_note="no"
  (( OPEN_BROWSER )) && browser_note="yes — opens when you press OK below"

  ui_msg "Ready to install" \
"Profile: ${INSTALL_MODE}
Dashboard at boot: ${boot_note}
Open browser after: ${browser_note}

Press OK to install nordctl (~1 minute).

${WIZARD_KEYS}" 17 72 || exit 0
}

text_pick_setup() {
  [[ -n "$INSTALL_MODE" ]] && return 0
  if [[ ! -t 0 ]]; then
    INSTALL_MODE=minimal
    return 0
  fi
  echo ""
  echo -e "${BLUE}nordctl installer${NC}"
  echo "  1) nordctl only  2) Nord VPN (recommended)  3) Network & Security"
  read -r -p "Choice [2]: " pick
  case "${pick:-2}" in
    1) INSTALL_MODE=minimal ;;
    3) INSTALL_MODE=network ;;
    *) INSTALL_MODE=vpn ;;
  esac
}

ensure_path_configured() {
  (( SYSTEM )) && return 0
  local mark="# nordctl installer — add CLI to PATH"
  local line="export PATH=\"${PREFIX}/bin:\$PATH\""
  local updated=0
  for rc in "$HOME/.bashrc" "$HOME/.profile"; do
    if [[ -f "$rc" ]] && grep -qF "$mark" "$rc" 2>/dev/null; then
      continue
    fi
    {
      echo ""
      echo "$mark"
      echo "$line"
    } >>"$rc"
    updated=1
  done
  export PATH="${PREFIX}/bin:$PATH"
  PATH_UPDATED=$updated
}

read_ui_port() {
  UI_PORT=8765
  if [[ -f "$HOME/.config/nordctl/config.yaml" ]]; then
    local py=python3
    [[ -n "${VENV_DIR:-}" && -x "$VENV_DIR/bin/python" ]] && py="$VENV_DIR/bin/python"
    UI_PORT="$("$py" -c 'import yaml, pathlib; p=pathlib.Path.home()/".config/nordctl/config.yaml"; print((yaml.safe_load(p.read_text()) or {}).get("server",{}).get("port",8765))' 2>/dev/null || echo 8765)"
  fi
}

dashboard_quick_check() {
  local port="${1:-$UI_PORT}"
  curl -fsS -o /dev/null --connect-timeout 2 "http://127.0.0.1:${port}/api/state/quick" 2>/dev/null
}

ensure_dashboard_reachable() {
  read_ui_port
  if dashboard_quick_check "$UI_PORT"; then
    return 0
  fi
  info "Port ${UI_PORT} not responding — finding a free port and starting the dashboard…"
  local boot_out boot_ok=1
  boot_out="$("$BIN" service bootstrap 2>&1)" || boot_ok=0
  read_ui_port
  while IFS= read -r line; do
    [[ -n "$line" ]] && info "$line"
  done <<<"$boot_out"
  if dashboard_quick_check "$UI_PORT"; then
    return 0
  fi
  (( boot_ok )) || warn "Dashboard bootstrap reported a problem"
  warn "Could not reach http://127.0.0.1:${UI_PORT}/ yet"
  warn "Try: $BIN service bootstrap"
  warn "Log: ~/.local/share/nordctl/serve.log"
  return 1
}

print_port_busy_hint() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    local holders
    holders="$(ss -tlnp sport = :"${port}" 2>/dev/null | tail -n +2 | tr '\n' ' ' | sed 's/  */ /g' || true)"
    if [[ -n "$holders" ]]; then
      warn "Port ${port} is in use: ${holders}"
      return
    fi
  fi
  warn "Port ${port} appears to be in use (another nordctl install or another app)"
}

python_nordctl() {
  local py=python3
  [[ -n "${VENV_DIR:-}" && -x "$VENV_DIR/bin/python" ]] && py="$VENV_DIR/bin/python"
  "$py" "$@"
}

apply_chosen_profile() {
  case "$INSTALL_MODE" in
    network)
      python_nordctl -c "
from nordctl.config import load_config
from nordctl.features import apply_modules, module_catalog
cfg = load_config()
cfg['usage_mode'] = 'tools_only'
cfg['install_profile'] = 'network'
mods = {
    m['id']: m['id'] in ('dashboard','help','wifi','lab','security','control','traffic','services','logs','editor','terminal','automate')
    or bool(m.get('required'))
    for m in module_catalog()
}
apply_modules(mods, cfg, legal_accepted=True, complete=False)
" 2>/dev/null || warn "Could not apply network profile — change mode in dashboard Setup"
      ;;
    all)
      "$BIN" onboard --all --non-interactive >/dev/null 2>&1 || true
      ;;
    minimal|vpn|nord)
      ;;
  esac
}

show_success() {
  if (( OPEN_BROWSER )); then
    open_dashboard_browser
  fi
  if (( USE_WHIPTAIL )); then
    ui_msg "Installation complete" "$(success_message_text)" 22 74
  else
    echo ""
    echo -e "${GREEN}✓ nordctl is installed.${NC}"
    echo ""
    success_message_text
  fi
}

success_message_text() {
  local boot_line="Run manually:  nordctl serve"
  (( INSTALL_UI )) && boot_line="Dashboard starts at login (systemd user service)"
  if (( PATH_UPDATED )); then
    cat <<EOF

PATH updated in ~/.bashrc and ~/.profile.
Open a new terminal or:  source ~/.bashrc

${boot_line}

Dashboard URL:
  http://127.0.0.1:${UI_PORT}/

The in-app setup wizard covers WiFi, country, Nord login, and presets.
EOF
  else
    cat <<EOF

${boot_line}

Dashboard URL:
  http://127.0.0.1:${UI_PORT}/

The in-app setup wizard covers WiFi, country, Nord login, and presets.
EOF
  fi
  if (( OPEN_BROWSER )); then
    echo ""
    echo "Your browser should open automatically."
  fi
}

run_install_steps() {
  if (( USE_WHIPTAIL )); then
    ui_msg "Installing" "Installing nordctl now.

This usually takes under a minute.
Python packages, config, and PATH are set up automatically." 12 72
  else
    info "Installing nordctl"
  fi
  install_step check_python
  install_step install_package
  install_step init_config
  install_step apply_profile
  install_step path_setup
  install_step extras
}

install_step() {
  case "$1" in
    check_python)
      command -v python3 >/dev/null 2>&1 || fail "Python 3 required"
      python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)' \
        || fail "Python 3.10+ required"
      if ! (( SYSTEM )) && pip_externally_managed; then
        ensure_user_venv
      fi
      ;;
    install_package)
      if (( SYSTEM )); then
        if ! sudo pip3 install --break-system-packages -q . 2>/dev/null; then
          sudo pip3 install -q . || fail "pip install failed"
        fi
        sudo install -d /usr/share/nordctl
        sudo cp -r presets /usr/share/nordctl/
        BIN="nordctl"
      else
        install_user_package .
        cp -r presets "$PREFIX/share/nordctl/"
      fi
      ;;
    init_config)
      if command -v "$BIN" >/dev/null 2>&1; then
        "$BIN" service stop >/dev/null 2>&1 || true
      fi
      local init_out init_ok=0
      init_out="$("$BIN" init --fix-port --skip-onboard 2>&1)" || init_ok=1
      while IFS= read -r line; do
        case "$line" in
          *"Port "*|"UI port:"*) info "$line" ;;
        esac
      done <<<"$init_out"
      (( init_ok )) && warn "init had warnings — continuing"
      read_ui_port
      if ! dashboard_quick_check "$UI_PORT" 2>/dev/null; then
        print_port_busy_hint "$UI_PORT"
      fi
      ;;
    apply_profile)
      apply_chosen_profile
      ;;
    path_setup)
      ensure_path_configured
      ;;
    extras)
      (( SKIP_UI )) && INSTALL_UI=0
      if (( INSTALL_TRAY )); then
        pip_install_extra '.[tray]' || pip_install_extra 'pystray>=0.19.5' 'Pillow>=9.0' || true
        "$BIN" tray install >/dev/null 2>&1 || true
      fi
      if (( INSTALL_UI )); then
        ensure_dashboard_reachable || warn "Dashboard autostart may need logout/login — URL above still works after: $BIN service bootstrap"
        read_ui_port
      fi
      if (( INSTALL_NORDVPN )); then
        "$BIN" install-nordvpn >/dev/null 2>&1 || true
      fi
      "$BIN" doctor >/dev/null 2>&1 || true
      ;;
  esac
}

# --- main ---
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if [[ -z "$INSTALL_MODE" ]] && [[ -t 0 ]] && [[ -t 1 ]] && ensure_whiptail; then
  USE_WHIPTAIL=1
  blue_screen_wizard
else
  text_pick_setup
fi

[[ -n "$INSTALL_MODE" ]] || INSTALL_MODE=minimal
case "$INSTALL_MODE" in
  all)
    INSTALL_NORDVPN=1
    INSTALL_UI=1
    INSTALL_TRAY=1
    ;;
esac

run_install_steps install_step
show_success