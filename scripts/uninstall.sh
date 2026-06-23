#!/usr/bin/env bash
# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
# Remove nordctl user install (keeps ~/.config/nordctl unless --purge-config)
if [ -z "${BASH_VERSION:-}" ]; then exec bash "$0" "$@"; fi
set -euo pipefail

PURGE_CONFIG=0
PURGE_SUDOERS=0
SYSTEM=0

usage() {
  echo "Usage: $0 [--purge-config] [--purge-sudoers] [--system]"
  echo "  --purge-config   Remove ~/.config/nordctl"
  echo "  --purge-sudoers  Remove /etc/sudoers.d/nordctl-* (requires sudo)"
  echo "  --system       Also pip uninstall from system Python (requires sudo)"
}

for arg in "$@"; do
  case "$arg" in
    --purge-config) PURGE_CONFIG=1 ;;
    --purge-sudoers) PURGE_SUDOERS=1 ;;
    --system) SYSTEM=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
  esac
done

BIN="${HOME}/.local/bin/nordctl"
if command -v nordctl >/dev/null 2>&1; then
  BIN="$(command -v nordctl)"
fi

info() { echo "==> $*"; }

if command -v nordctl >/dev/null 2>&1; then
  info "Stopping nordctl UI service (if installed)…"
  nordctl service stop 2>/dev/null || true
  nordctl service uninstall 2>/dev/null || true
  nordctl tray uninstall 2>/dev/null || true
fi

info "Removing pip package (user install)…"
python3 -m pip uninstall -y nordctl 2>/dev/null || pip uninstall -y nordctl 2>/dev/null || true

if (( SYSTEM )); then
  info "Removing system pip package…"
  sudo python3 -m pip uninstall -y nordctl 2>/dev/null || true
fi

if [[ -f "$BIN" ]]; then
  info "Removing $BIN"
  rm -f "$BIN"
fi

if (( PURGE_SUDOERS )); then
  info "Removing sudoers snippets…"
  sudo rm -f /etc/sudoers.d/nordctl-ui /etc/sudoers.d/nordctl-ufw 2>/dev/null || true
fi

if (( PURGE_CONFIG )); then
  CFG="${NORDCTL_CONFIG_DIR:-$HOME/.config/nordctl}"
  info "Removing config directory $CFG"
  rm -rf "$CFG"
else
  echo "Config kept at ~/.config/nordctl (use --purge-config to delete)"
fi

echo "nordctl uninstalled."
echo "NordVPN client (nordvpn package) was NOT removed — uninstall separately if needed."
