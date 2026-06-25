#!/usr/bin/env bash
# Remove nordctl user install so you can re-run ./install.sh from a clean slate.
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -euo pipefail

YES=0
KEEP_CONFIG=0

usage() {
  cat <<'EOF'
Usage: ./wipe.sh [options]

Removes nordctl CLI, venv, login autostart, tray, and config added by install.sh.
Does NOT remove the NordVPN apt package (if you installed it separately).

Options:
  -y, --yes          Skip confirmation
  --keep-config      Keep ~/.config/nordctl
  -h, --help         Show help
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -y|--yes) YES=1; shift ;;
    --keep-config) KEEP_CONFIG=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 1 ;;
  esac
done

info() { echo "==> $*"; }
warn() { echo "!! $*" >&2; }

BIN="${HOME}/.local/bin/nordctl"
VENV="${NORDCTL_VENV_DIR:-${HOME}/.local/share/nordctl/venv}"
SHARE="${HOME}/.local/share/nordctl"
CFG="${NORDCTL_CONFIG_DIR:-${HOME}/.config/nordctl}"
PATH_MARK="# nordctl installer — add CLI to PATH"

if (( ! YES )); then
  cat <<'EOF'
This will remove nordctl from your user account:

  • stop nordctl serve / tray processes
  • UI systemd user service + tray autostart
  • ~/.local/bin/nordctl and ~/.local/share/nordctl/venv
  • PATH lines added by install.sh
EOF
  if (( ! KEEP_CONFIG )); then
    echo "  • ~/.config/nordctl (config, logs, snapshots)"
  fi
  cat <<'EOF'

NordVPN (nordvpn package) is left installed.

EOF
  read -r -p "Continue? [y/N] " ans
  [[ "${ans,,}" == "y" || "${ans,,}" == "yes" ]] || { echo "Cancelled."; exit 0; }
fi

if command -v nordctl >/dev/null 2>&1; then
  BIN="$(command -v nordctl)"
  info "Stopping nordctl services…"
  nordctl service stop 2>/dev/null || true
  nordctl service uninstall 2>/dev/null || true
  nordctl tray uninstall 2>/dev/null || true
fi

info "Stopping nordctl processes…"
pkill -f '[n]ordctl serve' 2>/dev/null || true
pkill -f '[n]ordctl-tray' 2>/dev/null || true
pkill -f '[n]ordctl tray' 2>/dev/null || true
sleep 1

if command -v systemctl >/dev/null 2>&1; then
  for unit in nordctl-ui.service nordctl-tray.service; do
    systemctl --user disable --now "$unit" 2>/dev/null || true
  done
  systemctl --user daemon-reload 2>/dev/null || true
fi
rm -f "${HOME}/.config/autostart/nordctl-tray.desktop" 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/nordctl-ui.service" 2>/dev/null || true
rm -f "${HOME}/.config/systemd/user/nordctl-tray.service" 2>/dev/null || true

if [[ -x "$VENV/bin/pip" ]]; then
  info "Removing nordctl from venv…"
  "$VENV/bin/pip" uninstall -y nordctl 2>/dev/null || true
fi
python3 -m pip uninstall -y nordctl UNKNOWN 2>/dev/null || true
pip3 uninstall -y nordctl UNKNOWN 2>/dev/null || true

if [[ -L "$HOME/.local/bin/nordctl" ]] || [[ -f "$HOME/.local/bin/nordctl" ]]; then
  info "Removing ${HOME}/.local/bin/nordctl"
  rm -f "${HOME}/.local/bin/nordctl"
fi

if [[ -d "$VENV" ]]; then
  info "Removing venv $VENV"
  rm -rf "$VENV"
fi

if [[ -d "$SHARE" ]]; then
  info "Removing $SHARE"
  rm -rf "$SHARE"
fi

strip_path_block() {
  local rc
  for rc in "${HOME}/.bashrc" "${HOME}/.profile"; do
    [[ -f "$rc" ]] || continue
    if grep -qF "$PATH_MARK" "$rc" 2>/dev/null; then
      info "Removing installer PATH block from $rc"
      python3 - "$rc" "$PATH_MARK" <<'PY'
import sys
path, mark = sys.argv[1], sys.argv[2]
with open(path, encoding="utf-8") as f:
    lines = f.read().splitlines(True)
out, skip = [], 0
for line in lines:
    if skip:
        skip -= 1
        continue
    if line.rstrip("\n") == mark:
        skip = 1
        continue
    out.append(line)
with open(path, "w", encoding="utf-8") as f:
    f.write("".join(out))
PY
    fi
  done
}
strip_path_block

if (( ! KEEP_CONFIG )) && [[ -d "$CFG" ]]; then
  info "Removing config $CFG"
  rm -rf "$CFG"
elif (( KEEP_CONFIG )); then
  echo "Config kept at $CFG"
fi

echo ""
echo "Wipe complete — you can run ./install.sh again."
echo "NordVPN client was not removed (use: sudo apt remove nordvpn if needed)."
