# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# Passwordless sudo for nordctl UI fixes: UFW, IPv6 sysctl, resolv.conf immutable.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

USER_NAME="${SUDO_USER:-${USER:-root}}"
if [[ "$USER_NAME" == "root" ]]; then
  echo "Run as your normal user: sudo bash $0" >&2
  exit 1
fi

UFW_BIN="$(command -v ufw 2>/dev/null || true)"
SYSCTL_BIN="$(command -v sysctl 2>/dev/null || true)"
CHATTR_BIN="$(command -v chattr 2>/dev/null || true)"

UFW_BIN="${UFW_BIN:-/usr/sbin/ufw}"
SYSCTL_BIN="${SYSCTL_BIN:-/usr/sbin/sysctl}"
CHATTR_BIN="${CHATTR_BIN:-/usr/bin/chattr}"

TARGET="/etc/sudoers.d/nordctl-privileges"
{
  echo "# nordctl — passwordless privileged fixes for user ${USER_NAME}"
  if [[ -x "$UFW_BIN" ]]; then
    echo "${USER_NAME} ALL=(root) NOPASSWD: ${UFW_BIN}"
  fi
  if [[ -x "$SYSCTL_BIN" ]]; then
    echo "${USER_NAME} ALL=(root) NOPASSWD: ${SYSCTL_BIN} -w net.ipv6.conf.all.disable_ipv6=1"
    echo "${USER_NAME} ALL=(root) NOPASSWD: ${SYSCTL_BIN} -w net.ipv6.conf.default.disable_ipv6=1"
    echo "${USER_NAME} ALL=(root) NOPASSWD: ${SYSCTL_BIN} -w net.ipv6.conf.lo.disable_ipv6=1"
  fi
  if [[ -x "$CHATTR_BIN" ]]; then
    echo "${USER_NAME} ALL=(root) NOPASSWD: ${CHATTR_BIN} -i /etc/resolv.conf"
  fi
} >"$TARGET"
chmod 440 "$TARGET"
visudo -cf "$TARGET"

echo "Installed $TARGET"
echo ""
echo "This enables passwordless sudo for specific nordctl commands only (not sudo -n true)."
echo "The Privileges tab should show Nordctl UI fixes: yes after you refresh the page."
echo ""
if [[ -x "$UFW_BIN" ]]; then
  echo -n "UFW passwordless test: "
  if sudo -u "$USER_NAME" bash -c "sudo -n '${UFW_BIN}' status numbered" >/dev/null 2>&1; then
    echo "OK"
  else
    echo "FAILED — log out/in or run: newgrp sudo"
  fi
fi
if [[ -x "$SYSCTL_BIN" ]]; then
  echo "IPv6 sysctl rules installed — test with Setup → Disable IPv6 in the UI."
fi
if [[ -x "$CHATTR_BIN" ]]; then
  echo "chattr rule installed — for immutable resolv.conf fixes in Advanced tab."
fi
echo ""
echo "Restart the nordctl web UI (see ${SCRIPT_DIR}/install-ufw-sudoers.sh for restart command examples)."
