#!/usr/bin/env bash
# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
# nordctl installer for Linux — friendly first-run experience
#
# Future: install should ask only 3 product shapes; detailed setup moves to the
# dashboard welcome wizard. See docs/INSTALL_WIZARD.md (design — not built yet).
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -uo pipefail

PREFIX="${PREFIX:-$HOME/.local}"
SYSTEM=0
SKIP_UI=0
INSTALL_NORDVPN=0
INSTALL_TRAY=""
INSTALL_UI=""
INSTALL_MODE=""
# INSTALL_TRAY / INSTALL_UI: empty = ask if interactive, 1 = yes, 0 = no
# INSTALL_MODE: all | choose | minimal (or set via --all / --minimal)

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

info() { echo -e "${GREEN}==>${NC} $*"; }
warn() { echo -e "${YELLOW}!!${NC} $*" >&2; }
fail() { echo -e "${RED}ERROR:${NC} $*" >&2; exit 1; }

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
    warn "python3-venv missing — installing python3-venv python3-pip"
    if command -v apt-get >/dev/null 2>&1; then
      sudo apt-get update -qq
      sudo DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv python3-pip python3-full \
        || fail "Could not install python3-venv. Run: sudo apt install python3-venv python3-full"
    else
      fail "Could not create venv. Install python3-venv for your distro."
    fi
    python3 -m venv "$VENV_DIR" || fail "venv creation failed after installing python3-venv"
  fi
  PIP="$VENV_DIR/bin/pip"
  info "Using private Python environment at $VENV_DIR"
}

install_user_package() {
  local spec="$1"
  mkdir -p "$PREFIX/bin" "$PREFIX/share/nordctl"
  if pip_externally_managed; then
    ensure_user_venv
    "$PIP" install "$spec" || fail "pip install failed in venv"
    ln -sf "$VENV_DIR/bin/nordctl" "$PREFIX/bin/nordctl"
  else
    if pip3 install --user "$spec"; then
      :
    else
      warn "pip --user failed; using private Python environment"
      ensure_user_venv
      "$PIP" install "$spec" || fail "pip install failed"
      ln -sf "$VENV_DIR/bin/nordctl" "$PREFIX/bin/nordctl"
    fi
  fi
  export PATH="$PREFIX/bin:$PATH"
  BIN="${PREFIX}/bin/nordctl"
  [[ -x "$BIN" ]] || BIN="$(command -v nordctl || true)"
  [[ -n "$BIN" && -x "$BIN" ]] || fail "nordctl not found — add $PREFIX/bin to PATH"
}

pip_install_extra() {
  if [[ -n "${PIP:-}" && -x "$PIP" ]]; then
    "$PIP" install "$@"
  elif (( SYSTEM )); then
    sudo pip3 install --break-system-packages "$@" 2>/dev/null || sudo pip3 install "$@"
  else
    pip3 install --user "$@"
  fi
}

ask_yes_no() {
  local prompt="$1"
  local default="${2:-n}"
  local hint="y/N"
  [[ "$default" == "y" ]] && hint="Y/n"
  read -r -p "$prompt [$hint] " reply
  reply="${reply,,}"
  if [[ -z "$reply" ]]; then
    [[ "$default" == "y" ]] && return 0 || return 1
  fi
  case "$reply" in y|yes) return 0 ;; *) return 1 ;; esac
}

pick_setup_options() {
  # Skip if non-interactive or flags already decided everything
  if [[ -n "$INSTALL_MODE" ]]; then
    return 0
  fi
  if [[ ! -t 0 ]]; then
    INSTALL_MODE=minimal
    INSTALL_NORDVPN=0
    INSTALL_UI=0
    INSTALL_TRAY=0
    return 0
  fi
  if (( SKIP_UI )) && [[ "$INSTALL_TRAY" == "0" ]] && (( ! INSTALL_NORDVPN )); then
    INSTALL_MODE=minimal
    return 0
  fi

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  What would you like to set up?"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  1) Everything (recommended)"
  echo "     NordVPN client + web dashboard at login + system tray"
  echo "  2) Let me pick each option"
  echo "  3) nordctl only"
  echo "     CLI and manual dashboard — add extras later from the UI"
  echo ""
  read -r -p "Your choice [1/2/3] (default 2): " SETUP_PICK
  case "${SETUP_PICK:-2}" in
    1)
      INSTALL_MODE=all
      INSTALL_NORDVPN=1
      INSTALL_UI=1
      INSTALL_TRAY=1
      ;;
    3)
      INSTALL_MODE=minimal
      INSTALL_NORDVPN=0
      INSTALL_UI=0
      INSTALL_TRAY=0
      SKIP_UI=1
      ;;
    *)
      INSTALL_MODE=choose
      echo ""
      echo "Pick each optional component (Enter = sensible default):"
      if (( ! INSTALL_NORDVPN )); then
        if ask_yes_no "Install official NordVPN Linux client now?" n; then
          INSTALL_NORDVPN=1
        fi
      fi
      if (( ! SKIP_UI )) && [[ -z "$INSTALL_UI" ]]; then
        if ask_yes_no "Start web dashboard automatically at login?" y; then
          INSTALL_UI=1
        else
          INSTALL_UI=0
        fi
      fi
      if [[ -z "$INSTALL_TRAY" ]]; then
        echo "System tray — quick VPN / Smart DNS from the taskbar (needs pystray)."
        if ask_yes_no "Install system tray and start at login?" n; then
          INSTALL_TRAY=1
        else
          INSTALL_TRAY=0
        fi
      fi
      ;;
  esac
}

usage() {
  cat <<'EOF'
Usage: ./install.sh [options]

  --system            Install with sudo to /usr/local (system-wide)
  --prefix PATH       User install prefix (default: ~/.local)
  --install-nordvpn   After nordctl, run official NordVPN apt install (Debian/Ubuntu)
  --all               Install everything: NordVPN + UI service + tray (no prompts)
  --minimal           nordctl CLI only — no NordVPN, no UI service, no tray
  --choose            Prompt for each optional component individually
  --skip-onboard      Skip feature module picker (init / install)
  --install-tray      Install system tray icon + login autostart (no prompt)
  --no-tray           Skip system tray (no prompt)
  --install-ui-service  Enable nordctl web UI at login (no prompt)
  --no-ui-service     Skip UI systemd service (no prompt)
  --skip-ui           CLI only, skip UI service prompt
  -h, --help          Show help

Requires: Python 3.10+ (venv is created automatically on Ubuntu 24.04+)
Optional: NordVPN Linux CLI, system tray (pystray + Pillow)

Help: after install, open http://127.0.0.1:PORT/help.html in the web UI
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --system) SYSTEM=1; shift ;;
    --prefix) PREFIX="$2"; shift 2 ;;
    --install-nordvpn) INSTALL_NORDVPN=1; shift ;;
    --all) INSTALL_MODE=all; INSTALL_NORDVPN=1; INSTALL_UI=1; INSTALL_TRAY=1; shift ;;
    --minimal) INSTALL_MODE=minimal; INSTALL_NORDVPN=0; INSTALL_UI=0; INSTALL_TRAY=0; SKIP_UI=1; shift ;;
    --choose) INSTALL_MODE=choose; shift ;;
    --install-tray) INSTALL_TRAY=1; shift ;;
    --no-tray) INSTALL_TRAY=0; shift ;;
    --install-ui-service) INSTALL_UI=1; shift ;;
    --no-ui-service) INSTALL_UI=0; shift ;;
    --skip-ui) SKIP_UI=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) fail "Unknown option: $1 (try --help)" ;;
  esac
done

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

if ! command -v python3 >/dev/null 2>&1; then
  fail "Python 3 is required. Install: sudo apt install python3 python3-pip python3-venv"
fi

PYVER="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)'; then
  :
else
  fail "Python 3.10+ required (found $PYVER)"
fi

info "Installing nordctl Python package"
if (( SYSTEM )); then
  if ! sudo pip3 install --break-system-packages . 2>/dev/null; then
    sudo pip3 install . || fail "pip install failed — try: sudo apt install python3-pip"
  fi
  sudo install -d /usr/share/nordctl
  sudo cp -r presets /usr/share/nordctl/
  BIN="nordctl"
else
  install_user_package .
  cp -r presets "$PREFIX/share/nordctl/"
fi

info "Initializing config (pick free UI port + safety baseline)"
"$BIN" init --fix-port 2>/dev/null || warn "init --fix-port had warnings (continuing)"
if [[ -f "$HOME/.config/nordctl/baseline/manifest.json" ]]; then
  info "Install baseline saved under ~/.config/nordctl/baseline/"
  info "  Undo nordctl changes later: nordctl baseline restore"
else
  warn "Install baseline was not created — run: nordctl baseline ensure"
fi

UI_PORT=8765
if [[ -f "$HOME/.config/nordctl/config.yaml" ]]; then
  UI_PORT="$(python3 - <<'PY' 2>/dev/null || echo 8765
import yaml, pathlib
p = pathlib.Path.home() / ".config/nordctl/config.yaml"
print((yaml.safe_load(p.read_text()) or {}).get("server", {}).get("port", 8765))
PY
)"
fi

pick_setup_options

# Feature modules (WiFi hub, alerts, traffic, …)
if [[ "$INSTALL_MODE" != "minimal" ]] && [[ -t 0 ]]; then
  info "Feature modules — pick individually or all (open source, local-only)"
  if ! "$BIN" onboard; then
    warn "Module picker skipped — first visit to web UI will offer setup"
  fi
fi

maybe_set_ui_password() {
  if [[ ! -t 0 ]]; then return 0; fi
  echo ""
  if ! ask_yes_no "Set a dashboard password for the web UI? (recommended on shared WiFi / LAN access)" n; then
    return 0
  fi
  read -r -s -p "New dashboard password (min 4 chars): " UI_PW1
  echo ""
  read -r -s -p "Confirm password: " UI_PW2
  echo ""
  if [[ "$UI_PW1" != "$UI_PW2" ]] || [[ ${#UI_PW1} -lt 4 ]]; then
    warn "Passwords did not match or were too short — skipped"
    return 1
  fi
  NORDCTL_UI_PASSWORD="$UI_PW1" python3 -c "
import os, sys
from nordctl.ui_auth import set_ui_password
r = set_ui_password(os.environ['NORDCTL_UI_PASSWORD'])
print(r.get('note') or r.get('error') or 'done')
sys.exit(0 if r.get('ok') else 1)
" || warn "Could not save dashboard password"
  unset NORDCTL_UI_PASSWORD
}

maybe_set_ui_password

# Defaults for flags that skip the menu but left tray/ui unset
[[ -z "$INSTALL_TRAY" ]] && INSTALL_TRAY=0
if (( SKIP_UI )); then
  INSTALL_UI=0
elif [[ -z "$INSTALL_UI" ]]; then
  INSTALL_UI=0
fi

if [[ "$INSTALL_TRAY" == "1" ]]; then
  info "Installing system tray support"
  pip_install_extra '.[tray]' 2>/dev/null || pip_install_extra 'pystray>=0.19.5' 'Pillow>=9.0' || warn "Could not install tray Python packages"
  if "$BIN" tray install; then
    info "System tray enabled (autostart at login)"
  else
    warn "Tray install failed — you can retry later: pip install 'nordctl[tray]' && nordctl tray install"
    warn "On Ubuntu/Debian if no icon shows: sudo apt install gir1.2-ayatanaappindicator3-0.1 python3-gi"
  fi
fi

if [[ "$INSTALL_UI" == "1" ]]; then
  info "Installing nordctl UI systemd user service"
  if "$BIN" service install; then
    info "UI service enabled — dashboard at http://127.0.0.1:${UI_PORT}/"
  else
    warn "UI service install failed — run later: nordctl service install"
  fi
fi

if (( INSTALL_NORDVPN )); then
  info "Installing official NordVPN client (Debian/Ubuntu only)"
  if ! "$BIN" install-nordvpn; then
    warn "Automatic NordVPN install did not complete."
    warn "Open the web UI Setup panel or run: nordctl install-nordvpn"
    warn "Full guide: http://127.0.0.1:${UI_PORT}/help.html"
  fi
fi

info "Running system check"
"$BIN" doctor || warn "Some checks failed — see fix steps above or the Help page"

echo ""
echo -e "${GREEN}Installed successfully.${NC}"
echo ""
echo "Next steps:"
echo "  1. If NordVPN is not installed:"
echo "       nordctl install-nordvpn    # or use Setup in the web UI"
echo "  2. Log in (once):  nordvpn login"
echo "  3. Edit ~/.config/nordctl/config.yaml"
echo "       wifi.profiles: your NetworkManager WiFi connection names"
echo "       connect_country: e.g. United Kingdom"
echo "  4. nordctl doctor"
echo "  5. nordctl serve   →  http://127.0.0.1:${UI_PORT}/  (or: nordctl service install for login autostart)"
echo "  6. Help guide:     http://127.0.0.1:${UI_PORT}/help.html  (or Help tab in UI)"
if [[ "$INSTALL_UI" == "1" ]]; then
  echo "  · UI service:     nordctl service {start|stop|restart|status}"
fi
if [[ "$INSTALL_TRAY" == "1" ]]; then
  echo "  7. System tray:    nordctl tray   (also starts at login)"
elif [[ "$INSTALL_TRAY" == "0" ]]; then
  echo ""
  echo "  Optional tray later:  pip install 'nordctl[tray]' && nordctl tray install"
fi
echo ""
echo "Read LEGAL.md and OPEN_SOURCE.md before using TV streaming presets."
echo "100% open source (MIT) — no telemetry, no vendor lock-in."
if (( ! SKIP_UI )) && [[ "$INSTALL_UI" != "1" ]]; then
  echo "Optional UI at login:  nordctl service install"
fi
if [[ "$BIN" != "nordctl" ]] && [[ "$BIN" == *".local"* || "$BIN" == *"nordctl"* ]]; then
  echo ""
  echo "Tip: add nordctl to your PATH (once per user):"
  echo "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc && source ~/.bashrc"
  echo "  Or use the full path: $BIN"
fi
