#!/usr/bin/env bash
# GitHub username must be changed in the web UI — PATCH /user does not accept "login".
set -euo pipefail

TARGET="G4EA5"

if ! gh auth status -h github.com &>/dev/null; then
  echo "Not logged in to GitHub."
  exit 1
fi

CURRENT="$(gh api user -q .login)"
if [[ "$CURRENT" == "$TARGET" ]] || [[ "${CURRENT,,}" == "${TARGET,,}" ]]; then
  echo "Already renamed to $CURRENT"
  exit 0
fi

echo "GitHub API cannot rename accounts (PATCH /user ignores 'login')."
echo "Current username: $CURRENT"
echo ""
echo "Change it in the browser:"
echo "  https://github.com/settings/admin"
echo ""
echo "Click 'Change username' and set: $TARGET"
echo ""
echo "Then verify:"
echo "  gh api user -q .login"
echo ""
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "https://github.com/settings/admin" 2>/dev/null || true
fi
exit 1
