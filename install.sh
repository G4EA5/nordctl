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
UI_PORT=8765
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
  if [[ -x "$VENV_DIR/bin/python" ]]; then
    PIP="$VENV_DIR/bin/pip"
    return 0
  fi
  if ! python3 -m venv "$VENV_DIR" 2>/dev/null; then
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -qq
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip python3-full \
        || fail "Could not install python3-venv. Run: sudo apt install python3-venv python3-full"
    else
      fail "Could not create venv. Install python3-venv for your distro."
    fi
    python3 -m venv "$VENV_DIR" || fail "venv creation failed"
  fi
  PIP="$VENV_DIR/bin/pip"
  export VENV_DIR PIP
}

install_user_package() {
  local spec="$1"
  mkdir -p "$PREFIX/bin" "$PREFIX/share/nordctl"
  if pip_externally_managed; then
    ensure_user_venv
    "$PIP" install -q "$spec" || fail "pip install failed in venv"
    ln -sf "$VENV_DIR/bin/nordctl" "$PREFIX/bin/nordctl"
  else
    if pip3 install --user -q "$spec" 2>/dev/null; then
      :
    else
      ensure_user_venv
      "$PIP" install -q "$spec" || fail "pip install failed"
      ln -sf "$VENV_DIR/bin/nordctl" "$PREFIX/bin/nordctl"
    fi
  fi
  export PATH="$PREFIX/bin:$PATH"
  BIN="${PREFIX}/bin/nordctl"
  [[ -x "$BIN" ]] || BIN="$(command -v nordctl || true)"
  [[ -n "$BIN" && -x "$BIN" ]] || fail "nordctl not found after install"
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
  "$WHIPTAIL" --backtitle "nordctl Setup" --title "$1" --msgbox "$2" "${3:-18}" "${4:-72}" 2>/dev/null
}

ui_yesno() {
  "$WHIPTAIL" --backtitle "nordctl Setup" --title "$1" --yesno "$2" "${3:-14}" "${4:-72}" 2>/dev/null
}

ui_radiolist() {
  local title="$1" text="$2" height="$3" width="$4" menu_height="$5"
  shift 5
  "$WHIPTAIL" --backtitle "nordctl Setup" --title "$title" --radiolist "$text" "$height" "$width" "$menu_height" "$@" 3>&1 1>&2 2>/dev/null
}

blue_screen_wizard() {
  ui_msg "Welcome" \
"Welcome to nordctl.

This installer will:
  • Install nordctl on your Linux system
  • Add nordctl to your PATH automatically
  • Pick a starting mode (you can change later)

WiFi names, country, Nord login, and presets are configured
inside the dashboard setup wizard — not here." 20 72 || exit 0

  local choice
  choice="$(ui_radiolist "Choose your starting mode" \
"What do you want nordctl to focus on first?

You can enable more features anytime from the dashboard." \
22 74 3 \
  "minimal" "nordctl only — CLI + dashboard; wizard guides the rest" OFF \
  "vpn" "Nord VPN focus — connect, presets, Smart DNS (recommended)" ON \
  "network" "Network & Security — WiFi, firewall, doctors (no Nord account)" OFF)" || exit 0

  INSTALL_MODE="$choice"
  case "$INSTALL_MODE" in
    minimal)
      INSTALL_NORDVPN=0
      INSTALL_UI=0
      INSTALL_TRAY=0
      ;;
    vpn)
      if ui_yesno "NordVPN client" \
"Install the official NordVPN Linux client now?

Choose Yes if you already have a Nord account.
Choose No to install it later from the dashboard." 12 72; then
        INSTALL_NORDVPN=1
      else
        INSTALL_NORDVPN=0
      fi
      INSTALL_UI=0
      INSTALL_TRAY=0
      ;;
    network)
      INSTALL_NORDVPN=0
      INSTALL_UI=0
      INSTALL_TRAY=0
      ;;
  esac

  ui_msg "Ready to install" \
"Mode: ${INSTALL_MODE}

Next screens install nordctl and update your PATH.
When finished, run:

  nordctl serve

The dashboard setup wizard will guide you through everything else." 18 72 || exit 0
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
  if (( PATH_UPDATED )); then
    cat <<EOF

PATH updated in ~/.bashrc and ~/.profile.

Open a new terminal, or run:
  source ~/.bashrc

Start the dashboard:
  nordctl serve

Then open in your browser:
  http://127.0.0.1:${UI_PORT}/

The setup wizard inside the dashboard will walk you through
WiFi, country, Nord login, and anything else you need.

You do not have to read Help first — open the wizard when ready.
EOF
  else
    cat <<EOF

Start the dashboard:
  nordctl serve

Then open in your browser:
  http://127.0.0.1:${UI_PORT}/

The setup wizard inside the dashboard will walk you through
WiFi, country, Nord login, and anything else you need.

You do not have to read Help first — open the wizard when ready.
EOF
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
      "$BIN" init --fix-port --skip-onboard >/dev/null 2>&1 || warn "init had warnings"
      read_ui_port
      ;;
    apply_profile)
      apply_chosen_profile
      ;;
    path_setup)
      ensure_path_configured
      ;;
    extras)
      (( SKIP_UI )) && INSTALL_UI=0
      [[ "$INSTALL_MODE" == "minimal" ]] && INSTALL_UI=0 && INSTALL_TRAY=0
      if (( INSTALL_TRAY )); then
        pip_install_extra '.[tray]' || pip_install_extra 'pystray>=0.19.5' 'Pillow>=9.0' || true
        "$BIN" tray install >/dev/null 2>&1 || true
      fi
      if (( INSTALL_UI )); then
        "$BIN" service install >/dev/null 2>&1 || true
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