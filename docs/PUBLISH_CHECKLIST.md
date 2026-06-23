<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Pre-publish checklist

Run these before pushing to GitHub or talking about the installer.

## 1. Public data audit

```bash
bash scripts/audit-public.sh
bash scripts/selftest.sh
```

The audit blocks personal hostnames, environment-specific subnets, custom UI ports, and old branded example preset names.

**Your real config is never in the repo** — it lives only in `~/.config/nordctl/`. Do not commit `config.yaml` from your home directory.

## 2. Replace placeholders

| Placeholder | Update to |
|-------------|-----------|
| `yourusername` in README, pyproject.toml, PKGBUILD | `G4EA5` (done) |
| PyPI project name | Register `nordctl` on PyPI if available |
| CI badge URL | Matches your repo path |

## 3. Help & docs sync

- In-app help: `/help` panel (from `help_content.py`) — **canonical**
- Static page: `/help.html` — getting started updated; full feature list is in the in-app help **New in v0.2** section

## 4. Optional screenshots

Add `docs/screenshots/` with demo mode (`nordctl demo`) — no real IPs or SSIDs visible.

## 5. GitHub settings

- Add repository description + topics: `nordvpn`, `linux`, `vpn`, `smart-dns`
- Enable GitHub Actions
- Configure PyPI trusted publishing for the release workflow
- Add `LICENSE`, `CHANGELOG.md` (done)

## 6. Before installer discussion

- [x] Audit passes
- [x] Selftest passes  
- [x] No secrets in tree (`grep -r smtp_password\|ui_password_hash` should only hit examples/redaction code)
- [x] Example presets use neutral labels only
- [x] Demo mode uses RFC 5737 IPs only
- [ ] Decide: PyPI first or git clone + `install.sh` as primary path

## 7. What stays local (never publish)

- `~/.config/nordctl/config.yaml` — WiFi names, countries, mesh peers
- `~/.config/nordctl/journal.jsonl`, `activity.jsonl`
- Support bundles in `~/.config/nordctl/support/`

Use `nordctl support-bundle --anonymized` when attaching diagnostics to GitHub issues.

## 8. Install & welcome wizard (future)

When implementing the installer UX, follow [INSTALL_WIZARD.md](INSTALL_WIZARD.md):

- Install asks **three product shapes only** (nordctl only / Nord VPN focus / Network & Security only)
- WiFi, country, home ISP, presets → **dashboard welcome wizard**, not install prompts or help-only paths
- Keep `nordctl onboard` for power users; do not remove until wizard ships
