#!/usr/bin/env bash
# Capture nordctl UI screenshots (run demo server on 8779 first: NORDCTL_DEMO=1 nordctl serve --port 8779)
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/docs/screenshots"
BASE="${NORDCTL_SCREENSHOT_URL:-http://127.0.0.1:8779}"
CHROME="${CHROME:-google-chrome}"
SIZE="${NORDCTL_SCREENSHOT_SIZE:-1440,900}"
BUDGET="${NORDCTL_SCREENSHOT_BUDGET:-12000}"

mkdir -p "$OUT"

capture() {
  local file="$1"
  local hash="$2"
  if [[ -f "$OUT/$file" ]] && [[ "${NORDCTL_SCREENSHOT_FORCE:-0}" != "1" ]]; then
    local sz
    sz=$(stat -c%s "$OUT/$file" 2>/dev/null || echo 0)
    if (( sz > 50000 )); then
      echo "↷ skip $file (exists)"
      return 0
    fi
  fi
  echo "→ $file"
  timeout 45s "$CHROME" --headless=new --disable-gpu --hide-scrollbars \
    --window-size="$SIZE" \
    --screenshot="$OUT/$file" \
    --virtual-time-budget="$BUDGET" \
    "${BASE}/${hash}" 2>/dev/null || echo "  ! timeout/fail $file"
}

# Nord Dashboard
capture "01-dashboard-connect.png" "#dashboard"
capture "02-dashboard-switches.png" "#dashboard/switches"
capture "03-dashboard-workflows.png" "#dashboard/workflows/places"
capture "04-dashboard-meshnet.png" "#dashboard/meshnet"
# Terminal uses live shell WebSocket — skip in headless batch (capture manually if needed).
# capture "05-dashboard-terminal-nord.png" "#dashboard/terminal/nord"

# Networking hub
capture "10-networking-wifi.png" "#networking/wifi"
capture "11-networking-internet-traffic.png" "#networking/map-internet"
capture "12-networking-local-traffic.png" "#networking/map-local"
capture "13-networking-live-bandwidth.png" "#networking/traffic-live"
capture "14-networking-speed-test.png" "#networking/traffic-speed"
capture "15-networking-routes-dns.png" "#networking/network"
capture "16-networking-services.png" "#networking/services"
capture "17-networking-packages.png" "#networking/network-packages"

# Security hub
capture "20-security-overview.png" "#security/monitoring"
capture "21-security-doctors.png" "#security/doctors"
capture "22-security-leak-tests.png" "#security/leak-tests"
capture "23-security-audit.png" "#security/audit"
capture "24-security-ufw.png" "#security/host-ufw"
capture "25-security-packages.png" "#security/security-packages"
capture "26-security-privileges.png" "#security/privileges"

# Tools & help
capture "30-tools-guide.png" "#tools/auto-guide"
capture "31-tools-logs.png" "#tools/logs"
capture "32-tools-editor.png" "#tools/editor"
capture "40-help.png" "#help"
capture "41-settings-general.png" "#settings/general/interface"

echo "Done — $(ls -1 "$OUT"/*.png 2>/dev/null | wc -l) PNG files in $OUT"
