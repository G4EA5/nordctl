# nordctl UI screenshots

Captured in **demo mode** where possible (`NORDCTL_DEMO=1`) — no real emails or account data.  
Some networking views (spectrum, live bandwidth) may show local WiFi SSIDs if captured on a live session.

Regenerate:

```bash
NORDCTL_DEMO=1 nordctl serve --bind 127.0.0.1 --port 8779
bash scripts/capture-screenshots.sh
```

## Nord Dashboard

### Connect — `#dashboard/connect`

![Nord Dashboard — Connect](01-dashboard-connect.png)

### Switches — `#dashboard/switches`

![Nord Dashboard — Switches](02-dashboard-switches.png)

### Workflows — `#dashboard/workflows`

![Nord Dashboard — Workflows](03-dashboard-workflows.png)

### Meshnet — `#dashboard/meshnet`

![Nord Dashboard — Meshnet](04-dashboard-meshnet.png)

### Nord shell — `#dashboard/terminal-nord`

![Nord Dashboard — Nord shell](05-dashboard-terminal-nord.png)

### Scenario presets — `#dashboard/connect` (presets panel)

![Nord Dashboard — Scenario presets](06-dashboard-scenario-presets.png)

### Favorites — `#dashboard/favorites`

![Nord Dashboard — Favorites](07-dashboard-favorites.png)

## Networking

### WiFi — `#networking/wifi`

![Networking — WiFi](10-networking-wifi.png)

### Internet traffic — `#networking/map-internet`

![Networking — Internet traffic](11-networking-internet-traffic.png)

### Local traffic — `#networking/map-local`

![Networking — Local traffic](12-networking-local-traffic.png)

### Live bandwidth — `#networking/traffic-live`

![Networking — Live bandwidth](13-networking-live-bandwidth.png)

### Speed test — `#networking/traffic-speed`

![Networking — Speed test](14-networking-speed-test.png)

### Routes & DNS — `#networking/routes-dns`

![Networking — Routes and DNS](15-networking-routes-dns.png)

### Services — `#networking/services`

![Networking — Services](16-networking-services.png)

### Networking packages — `#networking/network-packages`

![Networking — Packages](17-networking-packages.png)

### WiFi spectrum — `#networking/spectrum-analyzer`

![Networking — WiFi spectrum](18-networking-spectrum.png)

## Security

### Overview — `#security/overview`

![Security — Overview](20-security-overview.png)

### Doctors — `#security/doctors`

![Security — Doctors](21-security-doctors.png)

### Leak tests — `#security/leak-tests`

![Security — Leak tests](22-security-leak-tests.png)

### Audit — `#security/audit`

![Security — Audit](23-security-audit.png)

### UFW — `#security/ufw`

![Security — UFW](24-security-ufw.png)

### Security packages — `#security/security-packages`

![Security — Packages](25-security-packages.png)

### Privileges — `#security/privileges`

![Security — Privileges](26-security-privileges.png)

## Tools

### Guide — `#tools/guide`

![Tools — Guide](30-tools-guide.png)

### Logs — `#tools/logs`

![Tools — Logs](31-tools-logs.png)

### Editor — `#tools/editor`

![Tools — Editor](32-tools-editor.png)

## Help & Settings

### Help — `#help`

![Help panel](40-help.png)

### Settings — `#settings/general`

![Settings — General](41-settings-general.png)
