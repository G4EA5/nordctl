<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Changelog

## 0.2.0

- Preset-driven NordVPN control: CLI + local web UI
- 58 built-in presets, leak lab, snapshots, WiFi zones
- Demo mode, dry-run, post-apply verification
- Community presets, config export/import, OpenAPI
- Connection journal, preset hooks, anonymized support bundle
- Minimal install profile, headless server mode

## Unreleased

- GitHub polish: CI, PyPI packaging, comparison docs, localization groundwork
- Top bar IP chain: Home/Public + VPN + Mesh with travel-safe rules
- Home ISP auto-learn per WiFi (`home_ip_cache.json`); `wifi.profiles` counts as home network
- Split state API (`/api/state/app`, `/api/state/nord`, `/api/state/network`) for faster UI loads
- Single-screen `./install.sh` (complete package) + dashboard setup wizard — [docs/INSTALL_WIZARD.md](docs/INSTALL_WIZARD.md)
