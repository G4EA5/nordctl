# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# One-time setup: passwordless UFW control for the nordctl web UI user.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PKG_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

if [[ "$(id -u)" -ne 0 ]]; then
  exec sudo bash "$0" "$@"
fi

USER_NAME="${SUDO_USER:-${USER:-root}}"
if [[ "$USER_NAME" == "root" ]]; then
  echo "Run as your normal user: sudo bash $0" >&2
  echo "  (not: sudo -i bash $0 — that sets USER=root and skips the right account)" >&2
  exit 1
fi

UFW_BIN="$(command -v ufw 2>/dev/null || true)"
UFW_BIN="${UFW_BIN:-/usr/sbin/ufw}"

if [[ ! -x "$UFW_BIN" ]]; then
  echo "UFW not installed. Install first: sudo apt install -y ufw" >&2
  exit 1
fi

TARGET="/etc/sudoers.d/nordctl-ufw"
cat >"$TARGET" <<EOF
# nordctl dashboard — passwordless UFW for user ${USER_NAME}
${USER_NAME} ALL=(root) NOPASSWD: ${UFW_BIN}
EOF
chmod 440 "$TARGET"
visudo -cf "$TARGET"

echo "Installed $TARGET for user ${USER_NAME}"
echo ""
echo "Verifying passwordless UFW (as ${USER_NAME}, same as the web UI)…"
if sudo -u "$USER_NAME" bash -c "sudo -n '${UFW_BIN}' status numbered" >/dev/null 2>&1; then
  echo "OK — passwordless UFW works."
  sudo -u "$USER_NAME" bash -c "sudo -n '${UFW_BIN}' status numbered" 2>&1 | head -8
else
  echo "WARNING: sudoers file is installed but the test failed." >&2
  echo "  Try: log out and back in, or run: newgrp sudo" >&2
  echo "  Manual test: sudo -n ${UFW_BIN} status numbered" >&2
  exit 1
fi

NORDCTL_BIN=""
USER_HOME="$(getent passwd "$USER_NAME" | cut -d: -f6)"
for candidate in \
  "$(sudo -u "$USER_NAME" bash -lc 'command -v nordctl' 2>/dev/null || true)" \
  "${PKG_ROOT}/.venv/bin/nordctl" \
  "${USER_HOME}/.local/bin/nordctl"; do
  if [[ -n "$candidate" && -x "$candidate" ]]; then
    NORDCTL_BIN="$candidate"
    break
  fi
done

echo ""
echo "Restart the nordctl web UI so it picks up sudo access:"
if [[ -n "$NORDCTL_BIN" ]]; then
  echo "  ${NORDCTL_BIN} service restart"
  echo "  # or: systemctl --user restart nordctl-ui.service"
else
  echo "  ~/.local/bin/nordctl service restart"
  echo "  # or full path: /path/to/nordctl/.venv/bin/nordctl service restart"
  echo "  # Add ~/.local/bin to PATH if 'nordctl' is not found."
fi
