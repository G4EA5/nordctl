<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# nordctl

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/G4EA5/nordctl/actions/workflows/ci.yml/badge.svg)](https://github.com/G4EA5/nordctl/actions/workflows/ci.yml)
[![PyPI version](https://img.shields.io/pypi/v/nordctl.svg)](https://pypi.org/project/nordctl/)

**One command, any scenario** — preset-driven NordVPN control for Linux with a local web UI, leak lab, snapshots, and WiFi automation.

> Independent open-source project (MIT). Not affiliated with Nord Security. See [LEGAL.md](LEGAL.md).

---

## Quick start (5 steps)

| Step | What to do |
|------|------------|
| **1. Install nordctl** | `pip install nordctl` or clone + `./install.sh` |
| **2. Install & login NordVPN** | `nordctl install-nordvpn` then `nordvpn login` |
| **3. Initialize** | `nordctl init` — creates config, picks UI port, minimal VPN profile |
| **4. Apply a preset** | `nordctl apply streaming-smartdns` (or `full-vpn`, `meshnet-only`, …) |
| **5. Open the UI** | `nordctl serve` → http://127.0.0.1:8765/ |

Edit `~/.config/nordctl/config.yaml` first — set `connect_country` and `wifi.profiles` for Smart DNS.

**No Nord account yet?** Try `nordctl demo` to explore the UI with simulated state.

```bash
pip install 'nordctl[tray]'    # optional system tray
nordctl doctor                  # readiness check
nordctl apply --dry-run full-vpn   # preview before applying
```

---

## Why nordctl?

| | **nordvpn CLI** | **NordVPN GUI** | **nordctl** |
|---|:---:|:---:|:---:|
| One-shot connect/disconnect | ✓ | ✓ | ✓ |
| **Scenario presets** (streaming, travel, mesh-only, …) | — | limited | ✓ 58 built-in |
| **Smart DNS + WiFi** profile sync | manual | partial | ✓ |
| **Leak & DNS lab** | — | — | ✓ |
| **Snapshots / rollback** | — | — | ✓ |
| **WiFi zones** (SSID → preset) | — | — | ✓ |
| **Split tunnel / allowlist UI** | CLI only | partial | ✓ |
| **Local web dashboard + API** | — | ✓ | ✓ |
| **Headless / Home Assistant** | scripts | — | ✓ REST |
| **100% local, no telemetry** | ✓ | ✓ | ✓ |
| Linux CLI / automation | ✓ | — | ✓ |

nordctl wraps the official NordVPN client — it does not replace your subscription or bypass provider terms.

---

## Screenshots

UI captures from demo mode where possible ([full gallery](docs/screenshots/README.md)).

### Nord Dashboard

| Connect | Switches | Workflows |
|:---:|:---:|:---:|
| ![Connect](docs/screenshots/01-dashboard-connect.png) | ![Switches](docs/screenshots/02-dashboard-switches.png) | ![Workflows](docs/screenshots/03-dashboard-workflows.png) |

| Meshnet | Nord shell | Scenario presets |
|:---:|:---:|:---:|
| ![Meshnet](docs/screenshots/04-dashboard-meshnet.png) | ![Nord shell](docs/screenshots/05-dashboard-terminal-nord.png) | ![Scenario presets](docs/screenshots/06-dashboard-scenario-presets.png) |

| Favorites |
|:---:|
| ![Favorites](docs/screenshots/07-dashboard-favorites.png) |

### Networking

| WiFi | Internet traffic | Local traffic |
|:---:|:---:|:---:|
| ![WiFi](docs/screenshots/10-networking-wifi.png) | ![Internet traffic](docs/screenshots/11-networking-internet-traffic.png) | ![Local traffic](docs/screenshots/12-networking-local-traffic.png) |

| Live bandwidth | Speed test | Routes & DNS |
|:---:|:---:|:---:|
| ![Live bandwidth](docs/screenshots/13-networking-live-bandwidth.png) | ![Speed test](docs/screenshots/14-networking-speed-test.png) | ![Routes and DNS](docs/screenshots/15-networking-routes-dns.png) |

| Services | Packages | WiFi spectrum |
|:---:|:---:|:---:|
| ![Services](docs/screenshots/16-networking-services.png) | ![Packages](docs/screenshots/17-networking-packages.png) | ![Spectrum](docs/screenshots/18-networking-spectrum.png) |

### Security

| Overview | Doctors | Leak tests |
|:---:|:---:|:---:|
| ![Security overview](docs/screenshots/20-security-overview.png) | ![Doctors](docs/screenshots/21-security-doctors.png) | ![Leak tests](docs/screenshots/22-security-leak-tests.png) |

| Audit | UFW | Packages |
|:---:|:---:|:---:|
| ![Audit](docs/screenshots/23-security-audit.png) | ![UFW](docs/screenshots/24-security-ufw.png) | ![Security packages](docs/screenshots/25-security-packages.png) |

| Privileges |
|:---:|
| ![Privileges](docs/screenshots/26-security-privileges.png) |

### Tools, Help & Settings

| Guide | Logs | Editor |
|:---:|:---:|:---:|
| ![Tools guide](docs/screenshots/30-tools-guide.png) | ![Logs](docs/screenshots/31-tools-logs.png) | ![Editor](docs/screenshots/32-tools-editor.png) |

| Help | Settings |
|:---:|:---:|
| ![Help](docs/screenshots/40-help.png) | ![Settings](docs/screenshots/41-settings-general.png) |

---

## Install

### PyPI (recommended)

```bash
pip install --user nordctl
pip install 'nordctl[tray]'   # optional: system tray icon

nordctl init
nordctl serve
```

### From source

```bash
git clone https://github.com/G4EA5/nordctl.git
cd nordctl
sh install.sh          # or ./install.sh — both work on Ubuntu (dash + bash)
# optional: sh install.sh --install-nordvpn
```

### Packaging

| Format | Command |
|--------|---------|
| **Debian/Ubuntu .deb** | `bash scripts/build-deb.sh` → `dist/nordctl_*.deb` |
| **Arch (AUR template)** | [packaging/arch/PKGBUILD](packaging/arch/PKGBUILD) |
| **Uninstall** | `bash scripts/uninstall.sh [--purge-config]` |

PyPI releases are published on [GitHub Release](https://github.com/G4EA5/nordctl/releases) via CI.

---

## Architecture

```mermaid
flowchart LR
  CLI[nordctl CLI] --> API[Local HTTP API]
  UI[Web UI] --> API
  API --> Presets[Preset engine]
  Presets --> Nord[nordvpn subprocess]
  Presets --> NM[NetworkManager / DNS]
  Presets --> Hooks[User hooks]
  Presets --> Journal[journal.jsonl]
```

Details: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) · API: [docs/openapi.yaml](docs/openapi.yaml) · Hooks: [docs/HOOKS.md](docs/HOOKS.md)

**First run:** `./install.sh` shows one optional checklist (NordVPN client, dashboard at login, open browser). WiFi, country, Nord login, and presets are in the dashboard **Wizard** (`#dashboard/wizard`) — see [docs/INSTALL_WIZARD.md](docs/INSTALL_WIZARD.md).

---

## Features (v0.2)

- **Dashboard** — presets, Smart DNS hub, setup wizard, doctor
- **Networking** — WiFi hub, traffic maps, live bandwidth, **WiFi spectrum** (band filters + SSID picker), Bluetooth spectrum
- **Lab** — leak tests, network audit, anonymized support bundle
- **Automate** — WiFi zones, schedules, snapshots, [preset hooks](docs/HOOKS.md)
- **Connection journal** — `nordctl journal` / `GET /api/journal`
- **Community presets** — import YAML from URL
- **Demo mode** — `nordctl demo` (no Nord account)
- **Home Assistant** — `GET /api/ha/state`

Full preset catalog: [presets/README.md](presets/README.md)

---

## Requirements

- Linux + **NetworkManager** (`nmcli`, `resolvectl`) for Smart DNS presets  
- **Python 3.10+**  
- **NordVPN CLI** + subscription for VPN presets (`nordctl install-nordvpn`)  
- macOS not supported (different network stack)

Compatibility matrix: [docs/COMPATIBILITY.md](docs/COMPATIBILITY.md)

---

## Configuration

Copy [config.example.yaml](config.example.yaml). All personal data stays in `~/.config/nordctl/`.

**Preset hooks:** executable scripts in `~/.config/nordctl/hooks/pre-preset/` and `post-preset/`.

### Top bar IP addresses (Home / VPN / Mesh)

The dashboard top bar shows how traffic leaves this PC:

| Chip | Meaning |
|------|---------|
| **Home** or **Public** | Your ISP address on the current WiFi (or wired) network |
| **VPN** | Nord exit IP while the tunnel is up |
| **Mesh** | Nord Meshnet address on this device (when Meshnet is on) |

**Travel-safe by default:** with VPN on, the Home chip appears only on **home WiFi** — not at hotels or cafés. Home WiFi is any SSID in `wifi.profiles` or `wifi_zones.trusted`.

**One-time setup at home:**

1. Add your home connection names to `wifi.profiles` (WiFi tab → Profiles → **Add to config**).
2. Disconnect VPN once on home WiFi — nordctl auto-learns your ISP IP per network into `~/.config/nordctl/home_ip_cache.json`.
3. Optional: add `home_public_ip` on a trusted zone if your ISP IP is fixed and you never want to re-learn.

While traveling, unknown SSIDs show **VPN** and **Mesh** only — your home ISP address stays hidden. Hover the top bar for details.

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#ip-display-home--public--vpn--mesh) and in-app **Help → Top bar IP addresses**.

---

## Legal

Streaming presets change **local DNS/VPN settings only**. You must comply with Nord terms, streaming service terms, and local law. See [LEGAL.md](LEGAL.md).

---

## Before GitHub

Run `bash scripts/audit-public.sh` and follow [docs/PUBLISH_CHECKLIST.md](docs/PUBLISH_CHECKLIST.md). Personal settings (WiFi names, mesh peers, countries) belong only in `~/.config/nordctl/` — never in the repo.

---

## Development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
bash scripts/selftest.sh
nordctl serve
```

## License

MIT — see [LICENSE](LICENSE). Changelog: [CHANGELOG.md](CHANGELOG.md).
