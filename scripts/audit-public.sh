#!/usr/bin/env bash
# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
# Fail if the tree contains patterns that must not ship on GitHub.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

FAIL=0
red() { echo "BLOCKED: $*" >&2; FAIL=1; }

# Optional local blocklist — see audit-private-patterns.local.example
PATTERNS=(




















)

# Search tracked-ish source only (not .venv, not user home config)
SEARCH_PATHS=(
  README.md
  OPEN_SOURCE.md
  LEGAL.md
  config.example.yaml
  presets
  examples
  docs
  nordctl
  scripts
  packaging
  install.sh
  pyproject.toml
  .github
)

for pat in "${PATTERNS[@]}"; do
  if command -v rg >/dev/null 2>&1; then
    hits=$(rg -i -n "$pat" "${SEARCH_PATHS[@]}" 2>/dev/null | rg -v 'audit-public\.sh|PUBLISH_CHECKLIST\.md' || true)
  else
    hits=$(grep -RIn -i -E "$pat" "${SEARCH_PATHS[@]}" 2>/dev/null | grep -v 'audit-public\.sh\|PUBLISH_CHECKLIST\.md' || true)
  fi
  if [[ -n "$hits" ]]; then
    echo "$hits"
    red "pattern /${pat}/i matched (see above)"
  fi
done

# Real-looking public IPs in demo code should use RFC 5737 documentation ranges only
if command -v rg >/dev/null 2>&1; then
  demo_hits=$(rg -n '89\.187\.|185\.230\.|103\.86\.96\.100' nordctl/demo_mode.py 2>/dev/null || true)
else
  demo_hits=$(grep -n -E '89\.187\.|185\.230\.|103\.86\.96\.100' nordctl/demo_mode.py 2>/dev/null || true)
fi
if [[ -n "$demo_hits" ]]; then
  echo "$demo_hits"
  red "demo_mode.py uses non-documentation IPs (use 203.0.113.x / 198.51.100.x)"
fi

if (( FAIL )); then
  echo ""
  echo "Public audit failed — remove or redact matches before publishing."
  exit 1
fi

echo "Public audit passed — no blocked patterns in source tree."
