<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Legal notice & disclaimer

**This document is not legal advice.** If you need advice for your situation, consult a qualified lawyer in your jurisdiction.

## Independence

**nordctl** is an independent open-source project. It is **not** affiliated with, endorsed by, or sponsored by:

- Nord Security / NordVPN
- Any television broadcaster, streaming platform, or content provider
- Any network equipment manufacturer

NordVPN® is a trademark of Nord Security. All other product and company names are trademarks of their respective owners. Use of those names is for identification only and does not imply endorsement.

## What this software does

nordctl runs commands against the **NordVPN command-line client** already installed on your system and may adjust **local network DNS settings** (for example via NetworkManager on Linux). It does not modify NordVPN’s service, bypass payment, or grant access to any paid or licensed content.

## Your responsibilities

By using nordctl you agree that **you alone** are responsible for:

1. **Compliance with law** in your country or region.
2. **Compliance with terms of service** of NordVPN and any streaming, telecommunications, or other services you use.
3. **Valid subscriptions and licences** where required (including TV licences where applicable).
4. **Smart DNS activation** in your Nord Account and keeping your allowlisted IP up to date.

Presets labelled **“TV streaming”** or similar describe **technical DNS/VPN configuration only**. They do not instruct or encourage violating geo-restrictions or provider terms. Configure presets for legitimate uses (for example privacy, travel within permitted regions, or DNS setup you are authorised to use).

## No warranty

The software is provided **“as is”** under the MIT License. See [LICENSE](LICENSE).

## Privacy

nordctl stores configuration locally (typically `~/.config/nordctl/`). It does **not** phone home or run analytics.

Optional features and their data handling:

| Feature | Data leaves your machine? |
|---------|---------------------------|
| Web UI (default) | No — binds to `127.0.0.1` unless you change it |
| Public IP check | Yes — only to the URL you configure (for Smart DNS display) |
| Speed test | Yes — only when you click Run (curl to test CDN) |
| Browser alerts | No — shown in your local browser via the UI |
| Email alerts | Yes — only to **your** configured SMTP → **your** To address |
| Webhook (optional, off by default) | Yes — only to a URL **you** configure |
| Activity log | No — plain text under `~/.config/nordctl/` |

Email alert passwords live in your local `config.yaml`. Do not share that file. Use an app-specific SMTP password.

See **OPEN_SOURCE.md** and the in-app Privacy manifest (`/api/privacy`).

## Reporting

For security issues, open a private report on the project issue tracker. Do not include personal credentials or account tokens.
