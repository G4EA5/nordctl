<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# nordctl compatibility

Last updated for **v0.2.x**. This matrix describes what we test and what community users report — not a vendor guarantee from Nord Security.

## Linux distributions

| Distribution | Versions | Status | Notes |
|--------------|----------|--------|-------|
| Ubuntu | 22.04, 24.04 LTS | Tested | Official NordVPN `.deb`, NetworkManager |
| Debian | 12, 13 | Tested | Same Nord package as Ubuntu |
| Linux Mint | 21.x, 22.x | Compatible | Ubuntu-based |
| Fedora | 39, 40+ | Compatible | NordVPN RPM; Smart DNS needs `nmcli` |
| Arch Linux | rolling | Community | AUR / manual Nord install |

**Not supported:** macOS, Windows (different network stacks).

## Requirements

| Component | Requirement |
|-----------|-------------|
| Python | 3.10+ |
| NetworkManager | `nmcli`, `resolvectl` for Smart DNS presets |
| NordVPN CLI | 3.15.0 minimum; 3.18.0+ recommended |
| Subscription | Valid Nord account + `nordvpn login` for VPN presets |

Query live status on a running install:

```bash
curl -s http://127.0.0.1:8765/api/compatibility | jq .
```

(Replace port with your `server.port` in config.)

## NordVPN CLI version

Preset steps use supported subcommands only (`connect`, `disconnect`, `set`, `allowlist`, `meshnet`). After major Nord client upgrades, run:

```bash
nordctl doctor
nordctl apply --dry-run streaming-smartdns
```

## Headless / server use

Set `server.headless: true` or run `nordctl init --headless` for VPS-style installs (API + CLI, no tray). See README **Headless profile**.

## Demo mode

`nordctl demo` or `NORDCTL_DEMO=1 nordctl serve` — no Nord account required for UI exploration.
