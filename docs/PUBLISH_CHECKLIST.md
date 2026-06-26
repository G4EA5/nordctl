<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Pre-publish checklist

Run these before pushing to GitHub or talking about the installer.

## 1. Public data audit

```bash
bash scripts/audit-public.sh
bash scripts/selftest.sh
```

The audit blocks personal hostnames, environment-specific subnets, custom UI ports, and old branded example preset names.

**Personal blocklist** (your username, SSID, LAN, custom port) lives in `scripts/audit-private-patterns.local` — copy from `audit-private-patterns.local.example`. That file is **gitignored** and never published. Only generic patterns ship in `audit-public.sh`.

**Your real config is never in the repo** — it lives only in `~/.config/nordctl/`. Do not commit `config.yaml` from your home directory.

## 2. Replace placeholders

| Placeholder | Update to |
|-------------|-----------|
| `yourusername` in README, pyproject.toml, PKGBUILD | `G4EA5` (done) |
| PyPI project name | Register `nordctl` on PyPI — see [PYPI_SETUP.md](PYPI_SETUP.md) |
| CI badge URL | Matches your repo path |

## 3. Help & docs sync

- In-app help: `/help` panel (from `help_content.py`) — **canonical**
- Static page: `/help.html` — getting started updated; full feature list is in the in-app help **New in v0.2** section

## 4. Optional screenshots

Add `docs/screenshots/` with demo mode (`nordctl demo`) — no real IPs or SSIDs visible.

## 5. GitHub settings

- Add repository description + topics: `nordvpn`, `linux`, `vpn`, `smart-dns`
- Enable GitHub Actions
- Configure PyPI trusted publishing — [docs/PYPI_SETUP.md](PYPI_SETUP.md) (workflow is manual until done)
- Add `LICENSE` (done); add `CHANGELOG.md` at first public release

## 6. Before installer discussion

- [x] Audit passes
- [x] Selftest passes  
- [x] No secrets in tree (`grep -r smtp_password\|ui_password_hash` should only hit examples/redaction code)
- [x] Example presets use neutral labels only
- [x] Demo mode uses RFC 5737 IPs only
- [x] Primary path: git clone + `./install.sh` (complete package); PyPI documented as manual/advanced

## 7. What stays local (never publish)

- `~/.config/nordctl/config.yaml` — WiFi names, countries, mesh peers
- `~/.config/nordctl/journal.jsonl`, `activity.jsonl`
- Support bundles in `~/.config/nordctl/support/`

Use `nordctl support-bundle --anonymized` when attaching diagnostics to GitHub issues.

## 8. Install & welcome wizard

Shipped — see [INSTALL_WIZARD.md](INSTALL_WIZARD.md):

- `./install.sh` — one optional checklist; installs CLI, dashboard, config, presets
- Dashboard **Wizard** — WiFi, country, Nord login, presets (not install prompts)
- `nordctl onboard` kept for power users / `--all` scripting
