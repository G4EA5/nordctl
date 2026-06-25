<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Install & setup wizard

## One installer — complete package

The normal install path is **`./install.sh`** from a git clone. It installs the **whole product** in one run: CLI, web dashboard, preset catalog, config, and (by default) a running UI you can open in the browser.

You do **not** pick “minimal vs full” or tick module boxes at install time. WiFi, country, Nord login, and presets are handled **after** install in the dashboard **Wizard**.

### What `./install.sh` does automatically

| Step | What happens |
|------|----------------|
| Python | Requires 3.10+; creates `~/.local/share/nordctl/venv` on PEP 668 systems |
| Package | Installs nordctl + copies `presets/` |
| Config | `nordctl init --fix-port --skip-onboard` — port, baseline snapshot, VPN-focused profile |
| Dashboard | `service bootstrap` — starts UI now; picks a free port if the default is busy |
| PATH | Adds `~/.local/bin` to `~/.bashrc` / `~/.profile` when needed |
| Extras | Optional NordVPN client install; optional tray (`--install-tray` / `--all`) |

### The only install prompt (one screen)

On a desktop with `whiptail`, you see a **single checklist**:

- **Install NordVPN Linux client** (optional, off by default)
- **Start dashboard at login** (recommended, on by default)
- **Open dashboard when install finishes** (on by default)

Non-interactive / SSH / CI skips the GUI and uses the same defaults (dashboard at login + open browser; NordVPN client only if you pass `--install-nordvpn` or check the box equivalent).

**Not asked at install:** WiFi SSIDs, `connect_country`, home ISP IP, module grid, preset choice, dashboard password.

### After install

```text
✓ nordctl installed

Dashboard:  http://127.0.0.1:8765/   (or the port shown in the installer log)

Use the in-app Wizard (top bar) for Nord login, WiFi, country, and presets.
Help is optional — you do not need to read it to get started.
```

---

## Dashboard wizard (phase 2)

Shipped in the dashboard: **Wizard** button or `#dashboard/wizard`.

| Principle | Behavior |
|-----------|----------|
| One concern per step | Full-screen cards, not a wall of checkboxes |
| Skip anytime | Optional steps never block the UI |
| Checklist | Setup progress visible until dismissed |
| Inline actions | Doctor, WiFi sync, Nord install — not “go read Help” |
| Re-run | Wizard button or Setup → resume |

Typical steps (profile-dependent): legal accept, NordVPN installed/logged in, sudo privileges, home country, WiFi profile sync, home ISP / trusted WiFi, Smart DNS, alerts, first connect or preset.

API: `GET /api/setup-wizard`, actions `setup_wizard_advance` / `setup_wizard_skip` / `setup_wizard_restart`. Progress: `~/.config/nordctl/setup_wizard.json`.

---

## Manual install (advanced)

Use this when you install from **PyPI**, package a `.deb`, or want full control over each step. It is **not** the path the README optimizes for.

```bash
pip install --user nordctl
pip install 'nordctl[tray]'          # optional system tray

nordctl init
nordctl service bootstrap            # or: nordctl serve
nordctl install-nordvpn            # optional, separate step
nordvpn login
nordctl apply streaming-smartdns     # example preset
```

`nordctl demo` — explore the UI without a Nord account.

---

## Scripting / power-user flags

For automation only (normal users run `./install.sh` with no flags):

| Flag | Effect |
|------|--------|
| `--all` | NordVPN + UI at login + tray, no prompts |
| `--minimal` | nordctl package only; no UI service extras |
| `--profile nord\|network\|minimal` | Set install profile without wizard |
| `--install-nordvpn` | Install official NordVPN client |
| `--no-ui-service` | Skip systemd user service |
| `--system` | Install to `/usr/local` with sudo |

`nordctl onboard --all` remains for scripts; the dashboard wizard is the default onboarding path.

---

## Related

- [README.md](../README.md) — quick start
- In-app **Help → First install & setup wizard**
- [ARCHITECTURE.md](ARCHITECTURE.md) — system overview
