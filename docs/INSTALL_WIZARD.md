<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Install & welcome wizard (design)

**Status:** Phase 2 welcome wizard **shipped** in the dashboard (`/api/setup-wizard`, Setup → Run setup wizard). Phase 1 install (`./install.sh`) still uses legacy prompts — align when convenient.

## Problem

Today, first-time users can land in a working UI but still need to discover WiFi profiles, countries, home ISP setup, Nord login, and module choices by reading help pages. That is too much hunting for a cold start.

**Goal:** the **installer asks almost nothing**. The **welcome wizard** (first dashboard open) walks through everything that still needs configuration — with skip buttons and a visible checklist — so users are never lost in help files on day one.

---

## Two phases

| Phase | When | Asks | Does not ask |
|-------|------|------|----------------|
| **1. Install** | `pip install`, `./install.sh`, or first `nordctl init` | Which *product shape* you want (3 choices) | WiFi names, countries, presets, home IP, module tick boxes |
| **2. Welcome wizard** | First `nordctl serve` / dashboard load (and re-runnable later) | Profile-specific setup steps, one screen at a time | Legal essay, advanced module catalog |

Copy shown at install time must say clearly:

> **You can finish everything else inside nordctl after install.**  
> The dashboard will guide you step by step — you do not need to read the help docs first.

---

## Phase 1 — Install (three choices only)

Replace the current multi-option install/onboard picker with **exactly three paths**:

### 1) nordctl only

- Installs the Python package / CLI.
- Does **not** auto-install NordVPN, systemd UI service, or tray (unless user explicitly opts in later).
- Sets `install_profile: minimal` (or equivalent).
- Message: *“Open the dashboard when ready — `nordctl serve`. A setup wizard will guide you through optional NordVPN, WiFi, and security tools.”*

### 2) Nord VPN focus

- For users who want **Nord Dashboard** — connect, presets, Meshnet, Smart DNS, Nord doctor.
- Network & Security hub tabs stay **hidden until enabled** in Optional extras (current `install_profile: nord` behavior).
- Optional single yes/no at install: *“Install NordVPN client now?”* (official package only) — default **offer**, not required to proceed.
- Does **not** ask for `connect_country`, WiFi profiles, or presets at install time.

### 3) Network & Security only

- For users **without** a Nord account — WiFi hub, UFW, doctors, lab, traffic, package tools.
- Sets `install_profile: network` / `usage_mode: tools_only`.
- Message: *“You can add NordVPN later from the dashboard — Setup wizard → Switch to VPN mode.”*

### Not offered at install (moved to welcome wizard)

- Per-module checkbox grid
- “Everything” vs “pick each” vs “minimal” (fold into the three shapes above; “full both stacks” = complete welcome wizard on Nord focus path + enable Optional extras step)
- `connect_country`, `wifi.profiles`, Smart DNS IPs
- Home ISP / trusted zones / `home_public_ip`
- Dashboard password (offer in wizard step “Share UI on LAN?”)
- Tray autostart, email alerts, schedules

### Install output (always)

After install, print:

```text
✓ nordctl installed

Next:  nordctl serve
       → http://127.0.0.1:8765/

A short setup wizard in the dashboard will walk you through WiFi, country, and anything else for your chosen mode.
Help is always available under Help — you do not need it to get started.
```

---

## Phase 2 — Welcome wizard (first dashboard)

Shown when `features.onboarding_complete` is false (or a new `setup_wizard_complete` flag — TBD at implementation).

### UX principles

1. **One concern per step** — full screen or modal slide, not a wall of checkboxes.
2. **Skip for now** on every optional step — never block dashboard access.
3. **Checklist** — persistent “Setup progress” chip or Dashboard → Setup tab showing done / todo.
4. **Inline actions** — buttons run doctor checks, sync WiFi profiles, open Nord install, save country — not “go read Help”.
5. **Deep links to Help** — “Learn more” only, not required reading.
6. **Re-run anytime** — Settings or `nordctl setup-wizard` (CLI name TBD).

### Shared steps (all profiles)

| Step | Purpose | Skip OK? |
|------|---------|----------|
| Welcome | Explain two-phase model; “We’ll only ask what’s needed for your mode.” | No (Continue) |
| Legal | Single checkbox — LEGAL.md excerpt (same as today) | Required once |
| UI access | Confirm bind (`127.0.0.1` vs LAN); optional dashboard password if LAN | Skip password on localhost |
| Done / checklist | Show summary + “Go to dashboard” | — |

### Nord VPN focus — additional steps

| Step | Purpose | Skip OK? |
|------|---------|----------|
| NordVPN installed? | Run doctor / offer official install + Terminal login | Yes |
| Services | Start nordvpnd; optional UI systemd autostart | Yes |
| Logged in? | Detect `nordvpn account`; show `nordvpn login` instruction | Yes (same step) |
| Sudo / privileges | Copy one-time privilege script command | Yes |
| Home country | Save `connect_country` (dropdown) | Yes |
| WiFi profiles | Sync active NM profile → `wifi.profiles` | Yes |
| Home ISP / trusted WiFi | Trusted zone + disconnect once to learn home IP | Yes |
| Smart DNS on WiFi | Apply Smart DNS to saved profiles | Yes |
| IPv6 | Optional disable when doctor flags leak risk | Yes |
| UFW | Read-only host firewall status | Yes |
| Alerts | Browser notifications + VPN disconnect watcher | Yes |
| Email | Optional SMTP to your address only | Yes |
| Dashboard password | If UI listens on LAN | Yes |
| Install baseline | Confirm rollback snapshot exists | Yes |
| First connect | Connect to home country or apply streaming preset | Yes |
| Optional apt tools | Networking + security package installs | Yes |

### Network & Security only — additional steps

| Step | Purpose | Skip OK? |
|------|---------|----------|
| WiFi profiles | Same sync as above if using Smart DNS / zones | Yes |
| Host firewall | UFW status; link to Linux UFW tab | Yes |
| Optional tools | Package tools apt install hints (lynis, nmap, …) | Yes |
| Add Nord later? | “I have NordVPN — switch to VPN mode” (existing flow) | Yes |

### nordctl only (minimal install)

Shorter wizard:

1. Welcome + legal  
2. “Start UI: `nordctl serve`” (if not already open)  
3. Pick path: **Nord VPN focus** / **Network & Security** / **Both** → sets `install_profile` and continues into the matching step list above  

---

## Setup checklist (dashboard)

After wizard, show a compact checklist until all *recommended* items for the profile are done (or user dismisses).

Example (Nord focus):

- [ ] NordVPN installed  
- [ ] Logged in (`nordvpn login`)  
- [ ] Home country saved  
- [ ] WiFi profile in config  
- [ ] First connect or preset applied  

Each row: **Fix now** button → wizard step or relevant tab.

Reuse doctor results where possible (`nordctl doctor` / Setup panel) instead of duplicating logic.

---

## Relationship to existing code

| Today | Planned |
|-------|---------|
| `install.sh` — 3 options (everything / pick / CLI only) + many sub-prompts | 3 product shapes only; defer rest to wizard |
| `nordctl onboard` — module catalog in terminal | Becomes “advanced” re-run; default path is welcome wizard |
| Web `#onboardOverlay` — Nord focus / Network only / Everything + module grid | Replace with **step wizard**; keep “Continue with current setup” for returning users |
| Dashboard **Setup** tab | Becomes checklist + “Resume setup wizard” |
| Help → Getting started | Points to wizard first, help second |

**Do not remove** `nordctl onboard --all` / module APIs — power users and scripts still need them.

---

## API / config (implementation notes)

When building:

- Consider `features.setup_wizard_complete` separate from `onboarding_complete` during migration.
- `GET /api/setup-wizard` — current step, checklist, profile.
- `POST /api/action` — `setup_wizard_advance`, `setup_wizard_skip`, `setup_wizard_restart`.
- Store progress in `~/.config/nordctl/setup_wizard.json` (step id, skipped ids, completed ids).
- `install.sh` should call `nordctl init --profile nord|network|minimal` (flag TBD) without interactive module picker.

---

## Copy templates (install)

**Choice prompt:**

```text
What do you want nordctl for?

  1) Nord VPN focus     — presets, connect, Meshnet, Smart DNS (Nord account)
  2) Network & Security — WiFi, firewall, doctors, tools (no Nord required)
  3) nordctl only       — CLI + dashboard; choose more inside the app

You’ll finish WiFi, country, and other details in a short setup wizard — not here.
```

**After choice 1 or 2:**

```text
Install NordVPN client now? [Y/n]   (only for choice 1; skippable)
```

---

## Success criteria

- New user can go from `pip install nordctl` → working connect or first preset **without opening Help**.
- Install never asks for WiFi SSIDs or ISP IP.
- Travel-safe home IP setup is **one optional wizard step**, not config.yaml archaeology.
- Returning users with existing config see “Continue with current setup”, not forced re-wizard.

---

## Related docs

- [ARCHITECTURE.md](ARCHITECTURE.md) — IP display / home WiFi  
- [README.md](../README.md) — quick start (will align with wizard when shipped)  
- In-app **Help → First install & setup wizard** (user-facing summary)
