# nordctl UI screenshots

Captured in **demo mode** where possible (`NORDCTL_DEMO=1`) — no real emails or account data.  
Some networking views (spectrum, live bandwidth) may show your local WiFi SSIDs if captured on a live session.

Regenerate automated captures:

```bash
NORDCTL_DEMO=1 nordctl serve --bind 127.0.0.1 --port 8779
bash scripts/capture-screenshots.sh
```

| File | Page |
|------|------|
| `01-dashboard-connect.png` | Nord Dashboard → Connect |
| `02-dashboard-switches.png` | Nord Dashboard → Switches |
| `03-dashboard-workflows.png` | Nord Dashboard → Workflows |
| `04-dashboard-meshnet.png` | Nord Dashboard → Meshnet |
| `05-dashboard-terminal-nord.png` | Nord Dashboard → Nord shell |
| `06-dashboard-scenario-presets.png` | Nord Dashboard → Connect → All scenario presets & location scenarios |
| `07-dashboard-favorites.png` | Nord Dashboard → My presets → Servers & favorites |
| `10-networking-wifi.png` | Networking → WiFi |
| `11-networking-internet-traffic.png` | Networking → Internet traffic |
| `12-networking-local-traffic.png` | Networking → Local traffic |
| `13-networking-live-bandwidth.png` | Networking → Live bandwidth |
| `14-networking-speed-test.png` | Networking → Speed test (history & chart) |
| `15-networking-routes-dns.png` | Networking → Routes & DNS → DNS assistant |
| `16-networking-services.png` | Networking → Services |
| `17-networking-packages.png` | Networking → Networking packages |
| `18-networking-spectrum.png` | Networking → Spectrum (WiFi analyzer) |
| `20-security-overview.png` | Security → Overview |
| `21-security-doctors.png` | Security → Doctors |
| `22-security-leak-tests.png` | Security → Leak tests |
| `23-security-audit.png` | Security → Audit |
| `24-security-ufw.png` | Security → UFW |
| `25-security-packages.png` | Security → Security packages |
| `26-security-privileges.png` | Security → Privileges |
| `30-tools-guide.png` | Tools → Guide |
| `31-tools-logs.png` | Tools → Logs |
| `32-tools-editor.png` | Tools → Editor |
| `40-help.png` | Help |
| `41-settings-general.png` | Settings → General |
