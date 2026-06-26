"""Structured help content for the in-app help panel."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any


_HELP_SECTIONS_RAW: list[dict[str, Any]] = [
        {
            "id": "navigation",
            "title": "Navigation &amp; tabs",
            "html": """
<p>The top bar has five main areas — everything else is a tab underneath:</p>
<table class="help-table"><tr><th>Top menu</th><th>What it opens</th></tr>
<tr><td><strong>Nord Dashboard</strong></td><td>VPN connect, presets, switches, Nord DNS, Nord shell, Nord doctor, Nord services</td></tr>
<tr><td><strong>Wizard</strong></td><td>Inline setup — install NordVPN, checklist, quick or full walkthrough (<code>#dashboard/wizard</code>)</td></tr>
<tr><td><strong>Networking</strong></td><td>WiFi, traffic maps, live bandwidth, <strong>WiFi spectrum</strong>, Bluetooth spectrum, routes &amp; DNS, diagnostics shell, networking apt packages, UI services</td></tr>
<tr><td><strong>Security</strong></td><td>Health overview, doctors, leak tests, privacy audit, Linux UFW, security apt packages, sudo privileges</td></tr>
<tr><td><strong>Tools</strong></td><td>Activity log, automate, schedules, rollback, config editor</td></tr>
<tr><td><strong>Help</strong></td><td>This guide — one topic per sidebar item</td></tr></table>
<p>Each tab shows a short <strong>Help</strong> box at the top with numbered steps. Use <strong>More detail</strong> for the full write-up from this page, or follow <strong>Related pages</strong> links to jump elsewhere without hunting the menu.</p>
<h4>URL hashes (bookmarks)</h4>
<table class="help-table"><tr><th>Area</th><th>Example hash</th></tr>
<tr><td>Dashboard connect</td><td><code>#dashboard/connect</code></td></tr>
<tr><td>WiFi zones</td><td><code>#networking/wifi/zones</code> (also <code>#network/wifi/zones</code>)</td></tr>
<tr><td>Security overview</td><td><code>#security/overview</code></td></tr>
<tr><td>Privacy audit</td><td><code>#security/audit</code></td></tr>
<tr><td>Activity log</td><td><code>#tools/logs</code></td></tr>
<tr><td>General settings</td><td><code>#settings/general/password</code></td></tr>
<tr><td>Alert settings</td><td><code>#settings/alerts/notifications</code></td></tr></table>
<p>Old links still redirect — e.g. <code>#settings/password</code> → General, <code>#network/doctor</code> → Doctors.</p>
<p><strong>Refresh</strong> (top right) reloads global status and the current page.</p>
<p>The top-right <strong>IP chips</strong> (Home/Public → VPN · Mesh) show your ISP address, Nord exit, and Meshnet — see <strong>Help → Top bar IP addresses</strong>.</p>
<div class="tip">Click <strong>Nord Dashboard</strong> anytime to return home (<code>#dashboard/connect</code>).</div>
""",
        },
        {
            "id": "site-map",
            "title": "Site map &amp; common journeys",
            "html": """
<p>Use this as a mental map — every page also has <strong>Related pages</strong> buttons in its Help box for one-click jumps.</p>
<h4>Where things live</h4>
<table class="help-table"><tr><th>You want to…</th><th>Go to</th></tr>
<tr><td>Connect or disconnect VPN</td><td>Nord Dashboard → <strong>Connect</strong></td></tr>
<tr><td>Run a saved workflow</td><td>Nord Dashboard → <strong>My presets</strong></td></tr>
<tr><td>Build a new preset</td><td>Nord Dashboard → <strong>Create preset</strong></td></tr>
<tr><td>Smart DNS on home WiFi</td><td>Nord Dashboard → <strong>Nord DNS</strong>; zones under <strong>Networking → WiFi → Zones</strong></td></tr>
<tr><td>Auto-switch preset by WiFi</td><td>Networking → WiFi → Zones, then Tools → <strong>Zone watcher</strong></td></tr>
<tr><td>Check privacy / leaks</td><td>Security → <strong>Overview</strong>, <strong>Leak tests</strong>, or <strong>Privacy audit</strong></td></tr>
<tr><td>Host firewall (UFW)</td><td>Security → <strong>Linux UFW</strong> (top bar UFW chip jumps here too)</td></tr>
<tr><td>Install apt tools (nmap, Lynis…)</td><td>Networking → <strong>Networking packages</strong> or Security → <strong>Security packages</strong> (catalog); your own packages → Tools → <strong>Custom packages</strong></td></tr>
<tr><td>See what nordctl changed</td><td>Tools → <strong>Activity log</strong></td></tr>
<tr><td>Undo a bad change</td><td>Tools → <strong>Rollback</strong> (full baseline) or <strong>Nord snapshots</strong> (Nord settings only)</td></tr>
<tr><td>Traffic / bandwidth</td><td>Networking → <strong>Internet traffic</strong>, <strong>Live bandwidth</strong>, or <strong>Speed test</strong></td></tr>
<tr><td>WiFi channel scan</td><td>Networking → <strong>WiFi spectrum</strong> — band toggles, SSID buttons, rescan</td></tr>
<tr><td>Bluetooth nearby devices</td><td>Networking → <strong>Bluetooth spectrum</strong></td></tr>
<tr><td>Dashboard password &amp; alerts</td><td>⚙ → General / Alerts settings</td></tr></table>
<h4>Common journeys</h4>
<ol class="steps"><li><strong>First-time Nord setup</strong> — top bar <strong>Wizard</strong> → Nord shell login → Connect → apply a preset from My presets.</li>
<li><strong>Streaming on trusted WiFi</strong> — My places (country) → Nord DNS → WiFi profiles (track SSID) → Zones → Leak tests.</li>
<li><strong>Privacy health check</strong> — Security Overview → Leak tests → Privacy audit → install missing tools from Security packages.</li>
<li><strong>Something broke</strong> — Activity log (what changed) → Rollback (restore baseline) or Nord snapshots (preset undo only).</li>
<li><strong>Harden this PC</strong> — Security packages → Linux UFW → Privileges (one-time sudo) → Leak tests to verify.</li></ol>
<div class="tip">Press <strong>Ctrl+K</strong> for the command palette — type a page name to jump without clicking through menus.</div>
""",
        },
        {
            "id": "start",
            "title": "Getting started",
            "html": """
<p><strong>nordctl</strong> is a free helper for NordVPN on Linux. Install Nord’s official client, log in once, then use one-click presets and the web dashboard.</p>
<h4>Quick start</h4>
<ol class="steps"><li><strong>Install</strong> — <code>./install.sh</code> from git, or install the <strong>.deb</strong> and open <strong>nordctl</strong> from your app menu</li>
<li><strong>Wizard</strong> — top bar <strong>Wizard</strong> or <code>#dashboard/wizard</code> for Nord login, WiFi, country, and your first preset</li>
<li><strong>Connect</strong> — use a preset card or Connect on the dashboard</li></ol>
<p>No Nord account yet? <code>nordctl demo</code> runs the UI with simulated VPN state.</p>
<p class="muted-inline">Advanced: <code>pip install nordctl</code> then <code>nordctl init</code> and <code>nordctl service bootstrap</code> — see Help → Install nordctl.</p>
<div class="tip"><strong>Tip:</strong> Ctrl+S saves in the editor. Ctrl+K opens the command palette. Theme toggle is in the top bar.</div>
""",
        },
        {
            "id": "adoption",
            "title": "New in v0.2 — demo, dry-run, journal",
            "html": """
<p>Features added for safe testing and GitHub-friendly support:</p>
<table class="help-table"><tr><th>Feature</th><th>CLI</th></tr>
<tr><td>Demo mode (no Nord account)</td><td><code>nordctl demo</code></td></tr>
<tr><td>Preset preview</td><td><code>nordctl apply ID --dry-run</code> or <strong>Preview</strong> on preset cards</td></tr>
<tr><td>Post-apply checks</td><td>Automatic after apply (DNS, IP, routing)</td></tr>
<tr><td>Preset journal</td><td><code>nordctl journal</code> — <code>~/.config/nordctl/journal.jsonl</code></td></tr>
<tr><td>Preset hooks</td><td>Scripts in <code>~/.config/nordctl/hooks/pre-preset/</code> and <code>post-preset/</code> — see docs/HOOKS.md</td></tr>
<tr><td>Community presets</td><td>Workflows → Community presets → import URL</td></tr>
<tr><td>Config backup</td><td><code>nordctl config export</code> / <code>import FILE</code> (secrets redacted)</td></tr>
<tr><td>Anonymized support bundle</td><td><code>nordctl support-bundle --anonymized</code> or Lab → Export anonymized bundle</td></tr>
<tr><td>Headless / VPS</td><td><code>nordctl init --headless</code> — no tray, no browser alerts</td></tr></table>
<p>API reference: <code>GET /api/openapi</code> · Compatibility: <code>GET /api/compatibility</code></p>
""",
        },
        {
            "id": "install-nordctl",
            "title": "Install nordctl",
            "html": """
<h4>From git (recommended — complete package)</h4>
<pre class="code-block">git clone https://github.com/G4EA5/nordctl.git
cd nordctl
./install.sh</pre>
<p><code>./install.sh</code> installs nordctl, presets, config, and the dashboard in one run. <strong>One screen</strong> — optional NordVPN client, dashboard at login, open browser. WiFi, country, and Nord login are in the dashboard <strong>Wizard</strong>, not the installer.</p>
<h4>Debian/Ubuntu .deb (app menu launcher)</h4>
<pre class="code-block">bash scripts/build-deb.sh
sudo apt install ./dist/nordctl_*_all.deb</pre>
<p>Search for <strong>nordctl</strong> in your application menu (or run <code>nordctl-open</code>). The first launch creates config, starts the dashboard, opens your browser, and enables the UI at <strong>user login</strong> (<code>nordctl-ui.service</code>). Requires the official NordVPN Linux client for VPN presets.</p>
<h4>PyPI (manual — you start each step)</h4>
<pre class="code-block">pip install --user nordctl
pip install 'nordctl[tray]'   # optional system tray
nordctl init
nordctl service bootstrap   # or: nordctl serve
nordctl install-nordvpn     # optional</pre>
<h4>Other packages</h4>
<ul class="steps"><li>Build .deb: <code>bash scripts/build-deb.sh</code> → <code>dist/nordctl_*.deb</code></li>
<li>Arch: see <code>packaging/arch/PKGBUILD</code></li>
<li>Uninstall .deb: <code>sudo apt remove nordctl</code> (config in <code>~/.config/nordctl/</code> is kept)</li>
<li>Uninstall git install: <code>bash scripts/uninstall.sh</code></li></ul>
<p>Before publishing or sharing the repo, run <code>bash scripts/audit-public.sh</code> — it blocks personal hostnames and environment-specific strings.</p>
""",
        },
        {
            "id": "services",
            "title": "Services &amp; autostart",
            "html": """
<p>nordctl has three separate “services” — do not confuse them:</p>
<table class="help-table"><tr><th>Component</th><th>What it does</th><th>Autostart</th></tr>
<tr><td><code>nordvpnd</code></td><td>Nord’s VPN daemon (required for VPN)</td><td>System boot — <code>sudo systemctl enable nordvpnd</code></td></tr>
<tr><td><code>nordctl-ui</code></td><td>Web dashboard (<code>nordctl serve</code>)</td><td>User login — app menu / <code>nordctl-open</code>, or Advanced → Enable at login</td></tr>
<tr><td><code>nordctl-tray</code></td><td>System tray icon (optional)</td><td>User login — <code>nordctl tray install</code></td></tr></table>
<h4>Web UI — manual vs systemd</h4>
<ul class="steps"><li><strong>Manual:</strong> <code>nordctl serve</code> — runs until Ctrl+C. Good for testing.</li>
<li><strong>Service:</strong> <code>nordctl service install</code> or <code>nordctl service bootstrap</code> — writes <code>~/.config/systemd/user/nordctl-ui.service</code>, starts now, enables at login. Debian .deb users: the app menu runs <code>bootstrap</code> on first open.</li></ul>
<h4>CLI reference</h4>
<pre class="code-block">nordctl service status
nordctl service install          # write unit + start + enable at login
nordctl service start|stop|restart
nordctl service enable|disable   # login autostart only
nordctl service uninstall
nordctl service nordvpnd start   # needs sudo</pre>
<p>Changing the UI port in config requires reinstalling the service so ExecStart picks up the new port.</p>
""",
        },
        {
            "id": "install",
            "title": "Install NordVPN",
            "html": """
<p>nordctl uses Nord Security’s official package — nothing is bundled.</p>
<pre class="code-block">nordctl install-nordvpn</pre>
<p>Debian/Ubuntu manual:</p>
<pre class="code-block">curl -fsSL https://repo.nordvpn.com/deb/nordvpn/debian/pool/main/n/nordvpn-release/nordvpn-release_1.0.0_all.deb -o /tmp/nordvpn-release.deb
sudo dpkg -i /tmp/nordvpn-release.deb
sudo apt update && sudo apt install -y nordvpn
sudo systemctl enable --now nordvpnd</pre>
<div class="warn"><strong>Install failed?</strong> Run <code>sudo apt --fix-broken install</code>, reboot, retry.</div>
""",
        },
        {
            "id": "config",
            "title": "Configuration",
            "html": """
<p>Main file: <code>~/.config/nordctl/config.yaml</code></p>
<pre class="code-block">connect_country: United Kingdom
wifi:
  profiles:
    - MyWiFi-5G
    - MyWiFi
smart_dns:
  primary: "103.86.96.103"
  secondary: "103.86.99.103"
server:
  bind: 127.0.0.1
  port: 8765
service:
  autostart: false</pre>
<p>List WiFi profile names: <code>nmcli -t -f NAME connection show</code></p>
<p>Pick WiFi profile names from <strong>Network → WiFi → Profiles</strong>, or run <code>nmcli -t -f NAME connection show</code> and add them under <code>wifi.profiles</code> in the Editor.</p>
<p><strong>Home ISP in the top bar:</strong> names in <code>wifi.profiles</code> also mark that SSID as home for the <strong>Home</strong> chip (along with <code>wifi_zones.trusted</code>). Disconnect VPN once on home WiFi to auto-learn your ISP into <code>~/.config/nordctl/home_ip_cache.json</code>, or set <code>home_public_ip</code> on a trusted zone entry.</p>
<pre class="code-block">wifi_zones:
  home_ip_learn: true          # remember ISP per SSID when VPN is off
  home_ip_when_trusted: true   # hide Home chip on travel WiFi while VPN is on
  trusted:
    - ssid: MyHomeWiFi
      preset: streaming-smartdns
      home_public_ip: 203.0.113.1   # optional fixed ISP for this SSID</pre>
<p>Full behavior: <strong>Help → Top bar IP addresses</strong>.</p>
""",
        },
        {
            "id": "topbar-ip",
            "title": "Top bar IP addresses",
            "html": """
<p>The top-right bar shows how this PC reaches the internet. Hover it for a short explanation.</p>
<h4>Chips</h4>
<table class="help-table"><tr><th>Label</th><th>Meaning</th></tr>
<tr><td><strong>Home</strong></td><td>Your ISP public address on the current WiFi (or wired) network</td></tr>
<tr><td><strong>Public</strong></td><td>Same as Home, but on a network nordctl does not treat as home (e.g. hotel WiFi with VPN off)</td></tr>
<tr><td><strong>VPN</strong></td><td>Nord exit IP while the tunnel is connected</td></tr>
<tr><td><strong>Mesh</strong></td><td>Nord Meshnet address on this device (when Meshnet is on)</td></tr></table>
<p>Example with VPN and Meshnet on at home:</p>
<pre class="code-block">Home 203.0.113.1  →  VPN 198.51.100.2  ·  Mesh 100.74.36.230</pre>
<h4>Travel-safe (default)</h4>
<p>With VPN on, the <strong>Home</strong> chip is shown only on <strong>home WiFi</strong> — not at random cafés or hotels. That way your home ISP address is not displayed on untrusted networks.</p>
<p><strong>Home WiFi</strong> means either:</p>
<ul class="steps"><li>The SSID is listed under <code>wifi_zones.trusted</code>, or</li>
<li>The SSID matches a connection name in <code>wifi.profiles</code> (the same list used for Smart DNS — add profiles on <strong>Network → WiFi → Profiles</strong>)</li></ul>
<h4>One-time setup at home</h4>
<ol class="steps"><li>Add your home WiFi connection name(s) to <code>wifi.profiles</code>.</li>
<li><strong>Disconnect VPN once</strong> on home WiFi — nordctl learns your ISP IP into <code>~/.config/nordctl/home_ip_cache.json</code> (per SSID).</li>
<li>Reconnect VPN — the top bar can show <strong>Home → VPN</strong> using the cached ISP address (kill switch blocks a fresh LAN-side probe).</li>
<li>Optional: on <strong>Network → WiFi → Zones</strong>, add a trusted zone with <code>home_public_ip</code> in config if your ISP IP is fixed and you prefer not to rely on auto-learn.</li></ol>
<h4>Config keys</h4>
<table class="help-table"><tr><th>Key</th><th>Default</th><th>Effect</th></tr>
<tr><td><code>wifi_zones.home_ip_learn</code></td><td>true</td><td>Remember ISP per SSID when VPN is off</td></tr>
<tr><td><code>wifi_zones.home_ip_when_trusted</code></td><td>true</td><td>Hide Home on non-home WiFi while VPN is on</td></tr>
<tr><td><code>wifi_zones.trusted[].home_public_ip</code></td><td>—</td><td>Fixed ISP for that SSID only (travel-safe)</td></tr></table>
<h4>Why not show a random “external” IP?</h4>
<p>A default-route check (<code>curl ifconfig.me</code>) while VPN is on often returns a Nord relay or tunnel artifact — not your real ISP. nordctl ignores that for the Home chip. On home WiFi it uses cache, zone config, or a LAN-interface probe instead.</p>
<div class="warn"><strong>While traveling:</strong> expect <strong>VPN</strong> and <strong>Mesh</strong> only. That is intentional — your home ISP stays hidden until you join a configured home network again.</div>
""",
        },
        {
            "id": "presets",
            "title": "Presets",
            "html": """
<p>One-click workflows for VPN, Smart DNS, Meshnet, security, and more.</p>
<pre class="code-block">nordctl apply streaming-smartdns
nordctl apply meshnet-only
nordctl apply disconnect --dry-run
nordctl presets</pre>
<p>On the Dashboard, each preset card has <strong>Preview</strong> (dry-run) and <strong>Run preset</strong>. After a successful apply, post-apply verification shows DNS, IP, and routing checks.</p>
<p>Custom hooks: place executable scripts under <code>~/.config/nordctl/hooks/pre-preset/</code> and <code>post-preset/</code> (see docs/HOOKS.md).</p>
<p>When <code>auto_snapshot_before_preset</code> is true, Nord settings are snapshotted before each apply. Each apply is also logged to <code>journal.jsonl</code> (<code>nordctl journal</code>).</p>
""",
        },
        {
            "id": "smartdns",
            "title": "Smart DNS &amp; DNS panel",
            "html": """
<p class="tip"><strong>This PC, not just Nord online.</strong> Smart DNS and Wi‑Fi actions change NetworkManager profiles and DNS on <em>this computer</em>. Your router, TV, and other devices keep their own DNS unless you configure them separately.</p>
<p><strong>Smart DNS</strong> sets Nord streaming DNS on your WiFi profiles via NetworkManager — no VPN tunnel. Useful for TV streaming and region-aware apps in this laptop's browser when you are authorised to use them; TVs and other devices on the LAN need their own Smart DNS setup.</p>
<ol class="steps"><li>Enable Smart DNS in Nord Account</li>
<li>Allowlist your public IP (Dashboard shows it when active)</li>
<li>Set <code>wifi.profiles</code> in config</li>
<li>Dashboard → Nord DNS → Apply Smart DNS (writes to this PC's Wi‑Fi profiles)</li></ol>
<p><strong>Nord DNS</strong> (while VPN connected) is a NordVPN app setting only — separate from Smart DNS on WiFi.</p>
<p><strong>resolv.conf</strong> may be managed by systemd-resolved, NetworkManager, or Nord. Use Lab → Fix immutable resolv if DNS changes fail.</p>
""",
        },
        {
            "id": "firewall",
            "title": "Firewall &amp; kill switch",
            "html": """
<p>Three layers often interact:</p>
<ul class="steps"><li><strong>UFW</strong> — Linux host firewall (<code>ufw status</code>)</li>
<li><strong>Nord firewall</strong> — Nord’s nftables rules when VPN connects</li>
<li><strong>Kill switch</strong> — blocks traffic if VPN drops</li></ul>
<p>Running UFW <em>and</em> Nord firewall together can block LAN, Meshnet, or local services unless allowlisted in both places. Control tab → <strong>UFW firewall editor</strong> lists and edits host rules (one-time <code>{ufw_sudoers_cmd}</code> for passwordless manage from the UI).</p>
<p>Install UFW from Security → <strong>Security tools</strong> (or Advanced → Networking tools for curl, dig, mtr, etc.). Each card shows an <strong>Install</strong> button when the package is missing. Firewall tab → <strong>UFW firewall editor</strong> needs one-time <code>{ufw_sudoers_cmd}</code> for passwordless manage from the UI.</p>
<p>Split tunnel (allowlist) lives on the <strong>Nord Dashboard</strong> — subnets/ports that bypass the VPN tunnel.</p>
""",
        },
        {
            "id": "baseline",
            "title": "Baseline backup &amp; rollback",
            "html": """
<p class="tip"><strong>Auto-backup on first use.</strong> When you first open nordctl (or run <code>nordctl init</code>), an <strong>install baseline</strong> is saved under <code>~/.config/nordctl/baseline/</code>. It captures config, Wi‑Fi DNS, Nord settings, and IPv6 so you can revert from <strong>Tools → Rollback</strong>.</p>
<p>On first <code>nordctl init</code>, nordctl saves an <strong>install baseline</strong> under <code>~/.config/nordctl/baseline/</code> — a snapshot of your machine <em>before</em> nordctl changed anything:</p>
<ul class="steps"><li>config.yaml and user presets</li>
<li>NordVPN settings snapshot</li>
<li>NetworkManager WiFi DNS per profile</li>
<li>IPv6 sysctl, resolv.conf snippet</li>
<li>systemd units (UI, tray) if present at baseline time</li></ul>
<h4>Restore install baseline (lighter undo)</h4>
<p>Automate tab → <strong>Restore install baseline</strong> puts config, WiFi DNS, Nord settings, and IPv6 back. Keeps logs, snapshots, and services.</p>
<pre class="code-block">nordctl baseline status
nordctl baseline ensure
nordctl baseline restore
nordctl baseline restore --resolv   # also restore resolv.conf (sudo)</pre>
<h4>Factory reset (full undo)</h4>
<p>Automate tab → <strong>Factory reset</strong> does everything baseline restore does, plus:</p>
<ul class="steps"><li>Removes nordctl UI + tray autostart and schedule timers</li>
<li>Clears activity log, Nord snapshots, exports, captures</li>
<li>Resets onboarding — welcome screen shows again</li>
<li>Disables LAN status page and background watchers</li></ul>
<p>Does <strong>not</strong> uninstall NordVPN or remove the nordctl program.</p>
<pre class="code-block">nordctl factory-reset
nordctl factory-reset --resolv</pre>
<div class="warn">Preset snapshots (Nord settings only) are a quick undo after one preset — lighter than baseline.</div>
""",
        },
        {
            "id": "logs",
            "title": "Activity log",
            "html": """
<p>The <strong>Logs</strong> tab (or 📋 button in the top bar) shows everything nordctl did in plain English — not cryptic terminal output.</p>
<ul class="steps"><li><strong>Title</strong> — what happened (e.g. “VPN connected — United Kingdom”)</li>
<li><strong>Detail</strong> — what it means for you</li>
<li><strong>Technical details</strong> — optional expand for CLI output</li></ul>
<p>Filter by VPN, DNS, Network, Services, Presets, Security, or Problems. Use <strong>Copy for support</strong> when opening a ticket.</p>
<pre class="code-block">nordctl logs
nordctl logs --errors
nordctl logs --category dns -n 20</pre>
<p>Log file: <code>~/.config/nordctl/activity.jsonl</code></p>
""",
        },
        {
            "id": "onboarding",
            "title": "First install & setup wizard",
            "html": """
<p><strong>Install (<code>./install.sh</code>)</strong> — one checklist screen: optional NordVPN client, start dashboard at login, open browser when done. Everything else is in the dashboard.</p>
<p><strong>Dashboard wizard</strong> — open from the top bar <strong>Wizard</strong> button or <code>#dashboard/wizard</code> (inline page, not a popup). Walk through optional steps with Skip on each screen.</p>
<h4>Wizard steps (in-app)</h4>
<ul class="steps"><li>Welcome &amp; legal</li>
<li>NordVPN install, login &amp; nordvpnd</li>
<li>Sudo / UI privileges</li>
<li>Home country, WiFi, trusted zones &amp; Smart DNS</li>
<li>IPv6, UFW, browser &amp; email alerts</li>
<li>Install baseline &amp; first VPN connect</li>
<li>Optional apt security/network tools</li></ul>
<pre class="code-block">./install.sh
nordctl serve
# → top bar Wizard or #dashboard/wizard</pre>
<div class="tip">After the wizard, use <strong>Nord doctor</strong> and <strong>Nord services</strong> for ongoing NordVPN health. The wizard page keeps the live install checklist on the left.</div>
""",
        },
        {
            "id": "alerts-tier4",
            "title": "Alerts (Tier 4–6)",
            "html": """
<p><strong>Tier 4 — Alerts:</strong> Browser notifications (local UI) + optional email via <em>your</em> SMTP. Rules: VPN disconnect, Smart DNS drift, low health score, untrusted WiFi.</p>
<p><strong>Scan result email:</strong> After Lynis, rkhunter, chkrootkit, ClamAV, nmap, fail2ban, debsecan, or trivy runs in <strong>Diagnostics → Shell</strong> or <strong>Network → Configuration</strong>, nordctl can email a parsed summary (findings, low Lynis score, or failures). Configure under <code>#settings/network/email</code> → <em>Security scan results</em>.</p>
<p><strong>Tier 5 — Global:</strong> Regional presets (EU, US, UK, APAC, LATAM, mobile), connection journal, privacy report export — all local files.</p>
<p><strong>Tier 6 — Smart:</strong> Preset recommendations from doctors + zones; optional webhook to a URL you own (off by default).</p>
<pre class="code-block"># config.yaml — email only goes to YOUR address
alerts:
  browser_enabled: true
  email:
    enabled: true
    to: you@example.com
    smtp_host: smtp.example.com
    smtp_port: 587
    smtp_user: you@example.com
    smtp_password: app-specific-password
  scan_email:
    enabled: true
    email_on_findings: true
    email_on_failure: true
    email_always: false
    lynis_min_score_alert: 65</pre>
<p>Security tab → <strong>Tools → Settings → Browser alerts</strong> (<code>#settings/notifications</code>) for bell rules; <strong>Email</strong> tab for SMTP and scan-result hooks. Enable browser permission, then <strong>Send test alert</strong>.</p>
""",
        },
        {
            "id": "wifi-hub",
            "title": "WiFi hub",
            "html": """
<p class="tip"><strong>This PC, not just Nord online.</strong> The WiFi tab changes NetworkManager profiles and DNS on this computer. Routers, TVs, and phones on your LAN are not changed unless you configure them separately.</p>
<p>The <strong>WiFi</strong> tab is a pro-grade NetworkManager control center — view, edit, heal, and protect every network you join on this machine.</p>
<h3>View &amp; edit</h3>
<ul class="steps"><li><strong>Connection hero</strong> — SSID, active profile, live DNS, public IP, signal strength</li>
<li><strong>Profile table</strong> — <strong>Add to config</strong> / <strong>Remove from config</strong> for <code>wifi.profiles</code> (does not delete system WiFi). Profiles here also mark home WiFi for the top bar <strong>Home</strong> chip.</li>
<li><strong>Smart DNS</strong> — edit IPs, apply or restore on all configured profiles</li>
<li><strong>Trusted zones</strong> — map home/work SSIDs to presets; optional <code>home_public_ip</code> per zone; optional auto-apply</li></ul>
<h3>Home ISP address (top bar)</h3>
<p>See <strong>Help → Top bar IP addresses</strong>. Summary: add home profiles, disconnect VPN once at home to auto-learn, or set <code>home_public_ip</code> on a trusted zone.</p>
<h3>Doctors (free)</h3>
<ul class="steps"><li><strong>WiFi doctor</strong> — NM profiles, Smart DNS drift, active profile tracking</li>
<li><strong>Network doctor</strong> — DNS leaks, IPv6, resolv.conf, Pi-hole conflicts</li>
<li><strong>NordVPN doctor</strong> — daemon, login, firewall/kill switch guidance</li></ul>
<h3>Self-healing</h3>
<ul class="steps"><li><strong>Sync profiles</strong> — auto-add active NM connection to config</li>
<li><strong>Smart DNS heal</strong> — re-apply when drift detected</li>
<li><strong>Zone watcher</strong> — background SSID monitor (starts with UI if enabled)</li>
<li><strong>Run self-heal</strong> — one button runs all enabled fixes</li></ul>
<h3>Scenario presets</h3>
<p>16 one-click cards: streaming, public WiFi, work, travel, gaming, Meshnet, restore, and more.</p>
<pre class="code-block">nordctl wifi status
nordctl wifi doctor
nordctl wifi heal</pre>
""",
        },
        {
            "id": "security-hub",
            "title": "Security hub",
            "html": """
<p>The <strong>Security</strong> tab is your all-in-one privacy dashboard — health score, bandwidth, DNS/IPv6 tools, alerts, and exports. <strong>Scenarios</strong> (home / work / travel presets) live on <strong>Nord Dashboard → Presets &amp; places</strong>.</p>
<h3>Tier 1 — essentials</h3>
<ul class="steps"><li><strong>Health score</strong> — 0–100 from nordvpnd, leak lab, audit, and live traffic</li>
<li><strong>Scenarios</strong> — Nord Dashboard tab: Home / Work / Travel one-tap presets (optional auto-connect)</li>
<li><strong>Speed test</strong> — simple download test through current route</li>
<li><strong>External leak links</strong> — WebRTC, DNS, IPv6 tests in your browser</li></ul>
<h3>Tier 2 — local network</h3>
<ul class="steps"><li><strong>DNS assistant</strong> — Pi-hole / Unbound / resolved conflicts</li>
<li><strong>IPv6 LAN</strong> — guidance for local IPv6 vs leak protection</li>
<li><strong>Live bandwidth</strong> — per-interface throughput with VPN highlighted</li>
<li><strong>Log export</strong> — plain-English activity log for support tickets</li></ul>
<h3>Tier 3 — power users</h3>
<ul class="steps"><li><strong>Packet capture lite</strong> — short tcpdump on VPN iface (.pcap for Wireshark)</li>
<li><strong>Meshnet snapshot</strong> — peers at a glance</li>
<li><strong>LAN status page</strong> — read-only URL for phone on same WiFi</li>
<li><strong>Home Assistant</strong> — REST sensor YAML via <code>/api/ha/state</code></li></ul>
<h3>Security tools (install panel)</h3>
<p>Ten apt packages with one-click install when passwordless sudo is configured:</p>
<table class="help-table"><tr><th>Package</th><th>Used for</th></tr>
<tr><td>UFW</td><td>Firewall tab</td></tr>
<tr><td>tcpdump</td><td>Packet capture (lite)</td></tr>
<tr><td>nftables</td><td>Read kernel rules in Advanced diagnostics</td></tr>
<tr><td>fail2ban</td><td>SSH brute-force protection (manual: <code>sudo fail2ban-client status</code>)</td></tr>
<tr><td>rkhunter / chkrootkit</td><td>Rootkit scans (run in terminal after install)</td></tr>
<tr><td>Lynis</td><td>Hardening audit — <code>sudo lynis audit system</code></td></tr>
<tr><td>ClamAV</td><td>On-demand malware scan</td></tr>
<tr><td>libnotify</td><td>Desktop VPN disconnect alerts</td></tr>
<tr><td>AppArmor utils</td><td><code>sudo aa-status</code></td></tr></table>
<p>After install, panels refresh automatically. Without passwordless sudo, copy the apt command from each card.</p>
<pre class="code-block">nordctl security
nordctl security --json</pre>
<div class="tip">Disconnect alerts need <code>notify-send</code> (libnotify). Enable in Security → Disconnect alerts.</div>
""",
        },
        {
            "id": "traffic",
            "title": "Who is talking to who?",
            "html": """
<p>The <strong>Advanced</strong> tab shows a simple live map of network connections — easier than Wireshark, no capture files.</p>
<ul class="steps"><li>Each card is an app (Chrome, Discord, etc.)</li>
<li>Lines show who it is talking to and whether traffic uses the <strong>VPN tunnel</strong> or goes <strong>direct</strong></li>
<li>Filters: Everything · Internet · Through VPN · Direct ⚠️ · Home network</li>
<li><strong>Live update</strong> refreshes every 5 seconds while you browse</li></ul>
<pre class="code-block">nordctl traffic
nordctl traffic --filter vpn
nordctl traffic --filter direct</pre>
<div class="tip">If VPN is ON and you see many “direct” connections, open the Lab tab and run leak tests.</div>
""",
        },
        {
            "id": "wifi-spectrum",
            "title": "WiFi &amp; Bluetooth spectrum",
            "html": """
<p><strong>WiFi spectrum</strong> (<code>#networking/spectrum-analyzer</code>) charts channel occupancy and signal strength across 2.4 / 5 / 6 GHz.</p>
<ul class="steps"><li><strong>Band switches</strong> — focus on 2.4 GHz, UNII-1, DFS, UNII-3, or 6 GHz slices.</li>
<li><strong>SSID buttons</strong> — every scanned network; click to centre the chart on that AP (dual-band SSIDs group together).</li>
<li><strong>Scan table</strong> — click a row to jump the chart; colours match the curves.</li>
<li><strong>Rescan WiFi</strong> — refreshes NetworkManager data; on some adapters also restarts NetworkManager so 2.4 GHz APs appear while connected on 5 GHz.</li></ul>
<p><strong>Bluetooth spectrum</strong> (<code>#networking/bluetooth-spectrum</code>) shows 2.4 GHz ISM activity, BLE channels, nearby devices, and basic security notes (discoverable mode, pairing).</p>
<div class="tip">If the chart looks empty, enable at least one band above the chart and press <strong>Rescan WiFi</strong>.</div>
""",
        },
        {
            "id": "network",
            "title": "Network tools",
            "html": """
<p>Lab and Advanced tabs include read-only diagnostics — no sudo required for most tools. Missing packages show <span class="tool-missing-tag">needs install</span> on the button; install from Advanced → <strong>Networking tools</strong>.</p>
<table class="help-table"><tr><th>Tool</th><th>Purpose</th><th>Package if missing</th></tr>
<tr><td>Overview</td><td>Default route + path to common targets</td><td>ping</td></tr>
<tr><td>Routing table</td><td>Full <code>ip route</code></td><td>—</td></tr>
<tr><td>Route lookup</td><td>Which interface handles a host</td><td>—</td></tr>
<tr><td>Connections</td><td>Active sockets (<code>ss</code> / netstat)</td><td>net-tools</td></tr>
<tr><td>Traceroute</td><td>Path to target</td><td>mtr / traceroute</td></tr>
<tr><td>DNS lookup</td><td><code>dig</code> / host</td><td>dnsutils</td></tr>
<tr><td>Ping</td><td>ICMP test</td><td>iputils-ping</td></tr>
<tr><td>Public IP</td><td>WAN address via default route (not the top bar Home chip — see Help → Top bar IP addresses)</td><td>curl</td></tr>
<tr><td>Listening ports</td><td><code>ss -lntup</code></td><td>net-tools</td></tr>
<tr><td>Port scan</td><td>Quick nmap (-F)</td><td>nmap</td></tr>
<tr><td>WHOIS</td><td>Domain registration</td><td>whois</td></tr>
<tr><td>Port probe</td><td>TCP test with nc</td><td>netcat-openbsd</td></tr>
<tr><td>iperf3</td><td>Throughput to server</td><td>iperf3</td></tr>
<tr><td>DNS config</td><td>resolv.conf + resolvectl</td><td>—</td></tr>
<tr><td>UFW / nftables</td><td>Host firewall rules</td><td>ufw / nftables</td></tr></table>
<pre class="code-block">nordctl nettools overview
nordctl nettools traceroute -t cloudflare.com</pre>
<p>Lines mentioning <code>nordlynx</code> or <code>nordtun</code> usually mean traffic uses the VPN tunnel.</p>
""",
        },
        {
            "id": "sudo",
            "title": "Sudo &amp; privileges",
            "html": """
<p>The web UI <strong>cannot type your sudo password</strong>. Actions that need root either:</p>
<ul class="steps"><li>Work automatically if you have <strong>passwordless sudo</strong> (<code>sudo -n true</code> succeeds), or</li>
<li>Show a <strong>manual command</strong> to run in a terminal.</li></ul>
<p>Most VPN commands need no sudo if you are in the <code>nordvpn</code> group:</p>
<pre class="code-block">sudo usermod -aG nordvpn $USER
# log out and back in</pre>
<p>Privileged fixes: disable IPv6, chattr on resolv.conf, start/stop <code>nordvpnd</code>, full nftables dump.</p>
<div class="warn">Never add <code>NOPASSWD: ALL</code> to sudoers. Limit to specific commands if you use passwordless sudo.</div>
""",
        },
        {
            "id": "troubleshoot",
            "title": "Troubleshooting",
            "html": """
<pre class="code-block">nordctl doctor
nordctl leaklab
nordctl support-bundle</pre>
<table class="help-table"><tr><th>Problem</th><th>Fix</th></tr>
<tr><td>CLI missing</td><td>Top bar <strong>Wizard</strong> → Install NordVPN, or <code>nordctl install-nordvpn</code></td></tr>
<tr><td>Not logged in</td><td><code>nordvpn login</code></td></tr>
<tr><td>nordvpnd down</td><td><code>sudo systemctl start nordvpnd</code> or Advanced → Services</td></tr>
<tr><td>Smart DNS fails</td><td>Check wifi.profiles in Editor</td></tr>
<tr><td>Home IP missing (top bar)</td><td>Home shows on home WiFi only when VPN is on. Add <code>wifi.profiles</code>, disconnect VPN once at home to auto-learn, or set <code>home_public_ip</code> on a trusted zone — Help → Top bar IP addresses</td></tr>
<tr><td>Wrong “external” IP with VPN on</td><td>Default-route checks show Nord relay IPs — use Home chip (cache/zone) instead; see Help → Top bar IP addresses</td></tr>
<tr><td>Port busy</td><td><code>nordctl init --fix-port</code></td></tr>
<tr><td>UI not at login</td><td><code>nordctl service install</code></td></tr>
<tr><td>After bad preset</td><td>Automate → Restore install baseline, or Factory reset for full undo</td></tr>
<tr><td>Factory reset vs baseline?</td><td>Baseline restores settings. Factory reset also removes services, logs, snapshots.</td></tr></table>
""",
        },
        {
            "id": "cli",
            "title": "CLI reference",
            "html": """
<pre class="code-block">nordctl init [--fix-port]
nordctl status
nordctl doctor
nordctl serve [--bind 127.0.0.1] [--port 8765]
nordctl service {install|start|stop|restart|enable|disable|uninstall|status}
nordctl service nordvpnd {start|stop|restart|enable|disable}
nordctl apply &lt;preset-id&gt;
nordctl baseline {status|ensure|restore|recreate}
nordctl factory-reset [--resolv]
nordctl traffic [--filter all|internet|vpn|direct|local]
nordctl logs [--errors] [--category vpn] [-n 40]
nordctl nettools [tool] [-t target]
nordctl leaklab
nordctl tray {install|uninstall}
nordctl run set technology NORDLYNX
nordctl support-bundle
nordctl onboard [--all|--minimal]
nordctl wifi {status|doctor|heal}
nordctl security [--json]</pre>
""",
        },
        {
            "id": "factory-reset",
            "title": "Factory reset",
            "html": """
<p><strong>Factory reset</strong> returns your machine to the state captured at first <code>nordctl init</code>, and removes nordctl’s added services and local data.</p>
<h4>What it restores</h4>
<ul class="steps"><li>config.yaml and user presets from install baseline</li>
<li>NordVPN settings (firewall, DNS, kill switch, etc.)</li>
<li>NetworkManager WiFi DNS on each saved profile</li>
<li>IPv6 sysctl values</li></ul>
<h4>What it removes</h4>
<ul class="steps"><li>nordctl UI systemd service and tray autostart</li>
<li>Schedule timers (<code>nordctl-*.timer</code>)</li>
<li>Activity log, Nord snapshots, exports, packet captures</li>
<li>Onboarding completion — welcome screen returns</li>
<li>Background watchers (disconnect, zone, alerts)</li></ul>
<h4>What it does NOT do</h4>
<ul class="steps"><li>Uninstall NordVPN or the nordvpn CLI</li>
<li>Remove the nordctl Python package or <code>./install.sh</code> files</li>
<li>Delete the install baseline folder (so you can reset again)</li></ul>
<pre class="code-block">nordctl factory-reset
nordctl factory-reset --resolv   # also restore /etc/resolv.conf (sudo)</pre>
<div class="warn">Requires an install baseline. If missing, run <code>nordctl init</code> or Automate → Create baseline now first.</div>
<p>For a lighter undo that keeps logs and services, use <strong>Restore install baseline</strong> instead.</p>
""",
        },
        {
            "id": "buttons",
            "title": "Every button explained",
            "html": """
<p>Hover any button in the UI for a short tooltip. Below is the full reference by tab.</p>
<h4>Top bar</h4>
<table class="help-table"><tr><th>Element</th><th>What it does</th></tr>
<tr><td>Home / Public → VPN · Mesh</td><td>ISP address (home WiFi only when VPN on), Nord exit IP, Meshnet IP — hover for details</td></tr>
<tr><td>VPN ON / OFF badge</td><td>Quick tunnel state</td></tr>
<tr><td>⌘ / Ctrl+K</td><td>Command palette — quick actions without hunting menus</td></tr>
<tr><td>☀ / ☾</td><td>Switch light or dark theme (saved in browser)</td></tr>
<tr><td>📋 Logs</td><td>Open activity log — plain-English history</td></tr>
<tr><td>Wizard</td><td>Inline setup — install NordVPN, checklist, quick/full walkthrough</td></tr>
<tr><td>Hide guides / Show guides</td><td>Show or hide numbered <strong>Help</strong> boxes on every tab</td></tr>
<tr><td>↻ Refresh</td><td>Reload VPN status and health checks (no confirmation)</td></tr></table>
<p>Full IP behavior: <strong>Help → Top bar IP addresses</strong>.</p>
<h4>Dashboard</h4>
<table class="help-table"><tr><th>Button</th><th>What it does</th></tr>
<tr><td>Install NordVPN</td><td>Run official apt installer (needs sudo)</td></tr>
<tr><td>Preview install</td><td>Show install commands only</td></tr>
<tr><td>Save country</td><td>Pick home country from Nord’s list — no manual YAML editing</td></tr>
<tr><td>Advanced: Editor</td><td>Manual config.yaml editing (advanced users)</td></tr>
<tr><td>Reconnect / Disconnect / Connect</td><td>VPN tunnel control</td></tr>
<tr><td>Servers &amp; favorites</td><td>Star countries and connect quickly</td></tr>
<tr><td>Split tunnel</td><td>Allowlist LAN subnets/ports outside the VPN</td></tr>
<tr><td>Meshnet</td><td>Mesh IP and peer list</td></tr>
<tr><td>Apply Smart DNS / Restore auto DNS</td><td>WiFi streaming DNS on/off</td></tr>
<tr><td>Nord DNS on/off</td><td>DNS via VPN tunnel when connected</td></tr>
<tr><td>Nord firewall / Kill switch</td><td>Nord’s packet filter and drop-if-disconnected</td></tr>
<tr><td>Preset cards</td><td>One-click workflows (streaming, travel, etc.)</td></tr></table>
<h4>Lab — Full doctor</h4>
<p>Runs read-only checks and shows a full report on the page: what was checked, pass/fail counts, and plain-English fixes grouped by NordVPN, WiFi, network, and system.</p>
<h4>Firewall tab (UFW)</h4>
<table class="help-table"><tr><th>Button</th><th>What it does</th></tr>
<tr><td>Enable / Disable UFW</td><td>Turn host firewall on or off</td></tr>
<tr><td>Add allow rule</td><td>Allow port or source CIDR</td></tr>
<tr><td>SSH / LAN / Meshnet / UI / Viber presets</td><td>Common allow rules in one click</td></tr>
<tr><td>Remove (per rule)</td><td>Delete numbered UFW rule</td></tr>
<tr><td>UFW sudo setup</td><td>Show one-time script for passwordless UFW from UI</td></tr></table>
<h4>Automate</h4>
<table class="help-table"><tr><th>Button</th><th>What it does</th></tr>
<tr><td>Restore install baseline</td><td>Revert config, DNS, Nord settings to first run</td></tr>
<tr><td>Factory reset</td><td>Baseline + remove services, logs, snapshots, onboarding</td></tr>
<tr><td>Save / Restore Nord snapshot</td><td>Quick undo of Nord settings only</td></tr>
<tr><td>Add schedule / Write systemd</td><td>Timed preset automation</td></tr></table>
<h4>Advanced</h4>
<table class="help-table"><tr><th>Button</th><th>What it does</th></tr>
<tr><td>Install (networking tools)</td><td>Advanced tab — curl, dig, mtr, nmap, NetworkManager, …</td></tr>
<tr><td>Install (security tools)</td><td>Security tab — UFW, tcpdump, Lynis, ClamAV, …</td></tr>
<tr><td>Services</td><td>Start/stop nordctl UI and nordvpnd</td></tr>
<tr><td>Traffic Refresh</td><td>Update “who is talking to who” map</td></tr>
<tr><td>Network diagnostics Run</td><td>ping, traceroute, routes, UFW status, …</td></tr>
<tr><td>Nord Dashboard → Nord shell</td><td>Full <strong>NordVPN quick commands</strong> — login, connect, settings, presets, doctor</td></tr>
<tr><td>Networking / Security → Shell</td><td>Networking shell or Security shell — sudo, apt, UFW, Lynis, scans</td></tr></table>
<p>Actions that change VPN, DNS, firewall, WiFi, services, or config ask for confirmation first. Scans, refreshes, exports, lab tests, traffic maps, and navigation stay one-click. Sudo commands and terminal steps open a <strong>sticky notice</strong> you can read and copy.</p>
""",
        },
        {
            "id": "control-tab",
            "title": "Firewall tab guide",
            "html": """
<p>The <strong>Firewall</strong> tab manages Linux <strong>UFW</strong> (host firewall) — separate from NordVPN firewall on the Nord Dashboard.</p>
<ul class="steps"><li><strong>Enable / Disable</strong> — turn UFW on or off</li>
<li><strong>Add allow rule</strong> — port, protocol, optional source CIDR</li>
<li><strong>Presets</strong> — SSH, LAN, Meshnet, UI, and Viber common rules</li>
<li><strong>UFW sudo setup</strong> — one-time command for passwordless UFW from the UI</li></ul>
<div class="tip">NordVPN connect, Meshnet, split tunnel, and favorites live on the <strong>Nord Dashboard</strong> tab.</div>
""",
        },
        {
            "id": "automate-tab",
            "title": "Automate tab guide",
            "html": """
<ul class="steps"><li><strong>WiFi zones</strong> — map SSIDs to presets (Automate mirrors WiFi tab settings)</li>
<li><strong>Config profiles</strong> — switch between saved config variants (work vs home)</li>
<li><strong>Schedules</strong> — run presets at a time daily; Write systemd creates user timers</li>
<li><strong>Install baseline</strong> — undo nordctl changes to network/DNS/Nord (keeps logs)</li>
<li><strong>Factory reset</strong> — full return to pre-install state + clear nordctl data</li>
<li><strong>Snapshots</strong> — Nord settings only; auto-saved before presets when enabled</li></ul>
""",
        },
        {
            "id": "editor-tab",
            "title": "Editor tab guide",
            "html": """
<p>Edit <code>config.yaml</code> and preset YAML files with live YAML validation.</p>
<ul class="steps"><li><strong>Files</strong> (left) — pick config.yaml or a preset</li>
<li><strong>Save</strong> (Ctrl+S) — writes file to disk</li>
<li><strong>Revert</strong> — discard unsaved edits</li>
<li><strong>New preset</strong> — create a user preset under ~/.config/nordctl/presets/</li></ul>
<div class="tip">WiFi names, countries, and preset apply flows are on the Dashboard and Network tabs — the Editor is for direct YAML edits only.</div>
<div class="warn">Invalid YAML shows a red line number — fix before saving.</div>
""",
        },
        {
            "id": "network-tools-install",
            "title": "Package tools — Networking",
            "html": """
<p><strong>Network → Package tools → Networking</strong> lists thirty packages that power network diagnostics and the WiFi hub. Each card shows:</p>
<ul class="steps"><li><strong>Used for</strong> — which nordctl feature needs it</li>
<li><strong>Install in shell</strong> — runs apt in Networking shell (enter your sudo password), or copy the command</li>
<li><strong>Installed ✓</strong> — green badge when ready</li></ul>
<table class="help-table"><tr><th>Package</th><th>Used for</th></tr>
<tr><td>curl</td><td>Public IP, speed test</td></tr>
<tr><td>dnsutils (dig)</td><td>DNS lookup diagnostic</td></tr>
<tr><td>mtr / traceroute</td><td>Traceroute diagnostic</td></tr>
<tr><td>iputils-ping</td><td>Ping &amp; Overview</td></tr>
<tr><td>net-tools</td><td>netstat fallback</td></tr>
<tr><td>nmap</td><td>Port scan diagnostic</td></tr>
<tr><td>iperf3</td><td>Throughput test</td></tr>
<tr><td>whois</td><td>WHOIS diagnostic</td></tr>
<tr><td>netcat</td><td>Port probe diagnostic</td></tr>
<tr><td>NetworkManager</td><td>WiFi hub, Smart DNS, zones</td></tr></table>
<p>After install, Advanced diagnostics and badges refresh automatically.</p>
<p>Your own apt packages (not in this catalog) belong under <strong>Tools → Custom packages</strong> — one tab per category (default: <strong>Miscellaneous</strong>).</p>
""",
        },
        {
            "id": "security-tools-install",
            "title": "Package tools — Security",
            "html": """
<p><strong>Network → Package tools → Security</strong> lists thirty optional apt packages — same install UX as the Networking tab.</p>
<table class="help-table"><tr><th>Category</th><th>Examples</th></tr>
<tr><td>Firewall</td><td>UFW, nftables, iptables (via Network tab)</td></tr>
<tr><td>Capture &amp; logs</td><td>tcpdump, logwatch, auditd</td></tr>
<tr><td>Audits &amp; rootkits</td><td>Lynis, rkhunter, chkrootkit, unhide, OpenSCAP</td></tr>
<tr><td>Malware</td><td>ClamAV, YARA</td></tr>
<tr><td>Integrity</td><td>AIDE, debsums</td></tr>
<tr><td>Hardening</td><td>fail2ban, AppArmor, Firejail, USBGuard, file capabilities</td></tr>
<tr><td>Maintenance</td><td>unattended-upgrades, needrestart, process accounting (acct)</td></tr>
<tr><td>Alerts</td><td>libnotify (disconnect desktop alerts)</td></tr>
<tr><td>Web scan</td><td>Nikto (local HTTP services you run)</td></tr></table>
<div class="tip">Installed tools show <strong>Run in shell</strong> — nordctl sends the command to Networking or Security shell; you still confirm sudo there. Lynis, rkhunter, AIDE, and ClamAV home scans can take several minutes.</div>
""",
        },
        {
            "id": "tools-only-mode",
            "title": "Using nordctl without NordVPN",
            "html": """
<p>You do <strong>not</strong> need a NordVPN subscription to use most of nordctl.</p>
<p>On first launch, choose <strong>Network tools only (no NordVPN)</strong>. You still get:</p>
<ul class="steps"><li><strong>Advanced</strong> — network diagnostics, traffic map, services, LAN access</li>
<li><strong>Security</strong> — health checks, tool installs (UFW, tcpdump, …)</li>
<li><strong>Firewall</strong> — UFW editor</li>
<li><strong>WiFi hub</strong> — doctors and fixes</li>
<li><strong>Networking shell</strong> — real bash for sudo and apt (Diagnostics → Shell → Networking)</li>
<li><strong>Lab</strong> — DNS and privacy checks on this PC</li></ul>
<p>When you later install NordVPN, click <strong>I have NordVPN — switch to VPN mode</strong> on the dashboard or run <code>nordctl onboard</code> and pick full modules.</p>
<div class="tip">Config key: <code>usage_mode: tools_only</code> in config.yaml (also <code>auto</code> or <code>vpn</code>).</div>
""",
        },
        {
            "id": "network-access",
            "title": "Network access (LAN vs local only)",
            "html": """
<p>By default the dashboard listens on <code>127.0.0.1</code> — only this computer can open it.</p>
<p><strong>Advanced → Services → Network access</strong> lets you share the UI on your home LAN so phones and other PCs can connect using <code>192.168.x</code> or <code>10.x</code> addresses.</p>
<ul class="steps"><li><strong>This computer only</strong> — safest; recommended on public or shared WiFi</li>
<li><strong>Home LAN</strong> — binds to all interfaces; use from another device on the same network</li>
<li><strong>One LAN address</strong> — bind to a single interface IP</li></ul>
<p>After changing mode, nordctl restarts the UI automatically. Open the LAN URL shown in the panel from your phone or tablet.</p>
<div class="warn"><strong>Security:</strong> LAN mode exposes the full dashboard including <strong>Networking shell</strong> and <strong>Nord shell</strong> (real bash). Only enable on networks you trust.</div>
""",
        },
        {
            "id": "terminal-tab",
            "title": "Nord shell & networking shells",
            "html": """
<p>There are four shell entry points — same bash engine, different quick-command buttons:</p>
<ul class="steps"><li><strong>Nord Dashboard → Nord shell</strong> — full <strong>NordVPN quick commands</strong>: <code>nordvpn login</code>, connect, settings, presets, <code>nordctl doctor</code>, leaklab, WiFi doctor, and more</li>
<li><strong>Networking → Networking shell</strong> — routes, WiFi, apt, public IP, restart UI</li>
<li><strong>Security → Security shell</strong> — UFW, Lynis, fail2ban, rootkit scans, privilege install</li>
<li><strong>Tools → Custom shell</strong> — one interactive shell per <strong>custom category</strong> you define in <strong>Settings → Quick commands</strong></li></ul>
<p>Every list is editable under <strong>Settings → Quick commands</strong> (General scope). Disable, rename, or add buttons; save to <code>config.yaml</code>.</p>
<ul class="steps"><li><strong>Click the black area</strong> and type — Enter, arrows, Tab, Ctrl+C, and paste work</li>
<li><strong>Quick buttons</strong> each open their own shell tab</li>
<li><strong>Sudo</strong> (networking/security shells) prompts for your password — the rest of the UI cannot do that</li>
<li><strong>nordvpn login</strong> must run in <strong>Nord shell</strong> (or an external terminal) — never in a web form</li></ul>
<p>Opening a session is logged under <strong>Logs</strong>. Idle sessions close after 30 minutes.</p>
<p>If <strong>Network access</strong> is set to Home LAN, anyone on your WiFi who can open the dashboard can also use these shells — keep local-only mode unless you trust every device on the network.</p>
<div class="warn">Full shell access — same power as a normal terminal. Prefer <strong>This computer only</strong> in Networking → Services → Network access.</div>
""",
        },
        {
            "id": "regional-presets",
            "title": "Regional presets (Europe &amp; Americas)",
            "html": """
<p>Regional workflows are grouped so users in different parts of the world are not overwhelmed with irrelevant options.</p>
<table class="help-table"><tr><th>Tab filter</th><th>Examples</th><th>Notes</th></tr>
<tr><td><strong>Europe</strong></td><td>EU privacy focus, UK streaming setup</td><td>Set <code>connect_country</code> in config first</td></tr>
<tr><td><strong>Americas</strong></td><td>US Smart DNS, LATAM public WiFi</td><td>Smart DNS needs activation in Nord Account — comply with provider terms</td></tr>
<tr><td><strong>Asia-Pacific</strong></td><td>APAC travel</td><td>Set <code>travel_country</code> in config</td></tr>
<tr><td><strong>Worldwide</strong></td><td>Mobile / metered</td><td>Lightweight VPN for hotspots</td></tr>
<tr><td><strong>Everyday</strong></td><td>Privacy max, public WiFi, kill switch, etc.</td><td>Not tied to a geography</td></tr></table>
<p>On the Dashboard, use the pill buttons above the preset grid to filter. <strong>All</strong> shows every region with clear section headers.</p>
<div class="warn"><strong>Legal:</strong> Presets configure DNS/VPN only. They do not bypass copyright or broadcaster rules — see LEGAL.md.</div>
""",
        },
        {
            "id": "dashboard-layout",
            "title": "Nord Dashboard layout",
            "html": """
<p>The <strong>Nord Dashboard</strong> uses sub-tabs under the top menu. The <strong>Wizard</strong> button in the top bar opens the inline setup page (<code>#dashboard/wizard</code>) — not a sub-tab.</p>
<p>The top bar shows <strong>Home/Public → VPN · Mesh</strong> when available — see <strong>Help → Top bar IP addresses</strong>.</p>
<ul class="steps"><li><strong>Connect</strong> — VPN status, reconnect/disconnect, country search, quick-start presets</li>
<li><strong>My presets</strong> — My places, saved presets, create workflows, favorites</li>
<li><strong>Create preset</strong> — step-by-step preset builder</li>
<li><strong>Switches</strong> — live Nord toggles one at a time</li>
<li><strong>Connection details</strong> — full path to ISP and VPN, MACs, routes</li>
<li><strong>Split tunnel</strong> — LAN subnets and ports that bypass the VPN tunnel</li>
<li><strong>Nord DNS</strong> — Smart DNS on WiFi and Nord DNS while on VPN</li>
<li><strong>Nord shell</strong> — NordVPN and nordctl quick commands</li>
<li><strong>Nord doctor</strong> — read-only NordVPN health checks</li>
<li><strong>Nord services</strong> — <code>nordvpnd</code> daemon and optional system tray</li></ul>
<p><strong>Wizard</strong> (top bar) — install NordVPN, health checklist, quick or full setup walkthrough on one page.</p>
<p>WiFi hub, leak lab, traffic maps, and full UFW editor live under <strong>Networking</strong>, <strong>Security</strong>, and <strong>Tools</strong>.</p>
""",
        },
        {
            "id": "extra-settings",
            "title": "Extra settings",
            "html": """
<p>Click the <strong>⚙</strong> icon (top right) — settings are grouped by topic:</p>
<table class="help-table"><tr><th>Scope</th><th>Examples</th><th>Hash</th></tr>
<tr><td><strong>General</strong></td><td>Dashboard password, interface guides, speed test defaults, UI service, LAN access</td><td><code>#settings/general/password</code></td></tr>
<tr><td><strong>Places</strong></td><td>Countries, cities, DNS, servers for presets</td><td><code>#settings/locations/places</code></td></tr>
<tr><td><strong>WiFi &amp; DNS</strong></td><td>Smart DNS IPs, trusted WiFi, home ISP learning</td><td><code>#settings/wifi/smart-dns</code></td></tr>
<tr><td><strong>VPN</strong></td><td>Split tunnel defaults, public IP probes, wizard shortcuts</td><td><code>#settings/vpn/tunnel</code></td></tr>
<tr><td><strong>Alerts</strong></td><td>Browser bell and email (your SMTP only)</td><td><code>#settings/alerts/notifications</code></td></tr></table>
<p>Old hashes like <code>#settings/password</code> or <code>#settings/nord/password</code> redirect to the matching scope automatically.</p>
""",
        },
        {
            "id": "open-source",
            "title": "Open source",
            "html": """
<p><strong>nordctl</strong> is independent open-source software (MIT license). It is not affiliated with, endorsed by, or supported by Nord Security.</p>
<p>All processing runs on your machine — no nordctl cloud, no telemetry. Optional email alerts use <strong>your SMTP only</strong>.</p>
<div class="help-doc-actions disclaimer-actions">
  <button type="button" class="btn sm" data-help-doc="open-source">Read OPEN_SOURCE.md</button>
</div>
<p>Third-party notices, license text, and attribution live in the repository’s <code>OPEN_SOURCE.md</code> file.</p>
""",
        },
        {
            "id": "legal",
            "title": "Legal &amp; disclaimer",
            "html": """
<p>You are responsible for complying with applicable laws, NordVPN terms, and streaming service rules. Smart DNS and preset workflows configure DNS/VPN technically — they do not grant rights to bypass geo-restrictions or copyright.</p>
<p>Presets and doctors are guidance only. Test on your own hardware before relying on them for privacy or compliance.</p>
<div class="help-doc-actions disclaimer-actions">
  <button type="button" class="btn sm" data-help-doc="legal">Read LEGAL.md</button>
</div>
<div class="warn"><strong>Summary:</strong> Independent tool (MIT) — not Nord Security. Use at your own risk.</div>
""",
        },
        {
            "id": "start-nord",
            "title": "Getting started (Nord VPN)",
            "html": """
<p>nordctl ships as one full hub — Nord Dashboard, Network &amp; Security, and Tools are always in the top menu.</p>
<ol class="steps"><li>Top bar <strong>Wizard</strong> → Install NordVPN (or <code>nordctl install-nordvpn</code>)</li>
<li>Nord Dashboard → <strong>Nord shell</strong> → <code>nordvpn login</code></li>
<li>Set countries under <strong>My presets → My places</strong></li>
<li>Connect or apply a preset from the Dashboard</li></ol>
<p>WiFi doctors, UFW, traffic maps, and security apt tools live under <strong>Networking</strong> and <strong>Security</strong> — use <code>#networking/network-packages</code> and <code>#security/security-packages</code> for apt installs.</p>
""",
        },
        {
            "id": "start-network",
            "title": "Getting started (Network &amp; Security)",
            "html": """
<p><strong>Network &amp; Security only</strong> is no longer a separate install mode — everything is included. You can still use nordctl without a NordVPN account.</p>
<ol class="steps"><li>Open <strong>Networking</strong> or <strong>Security</strong> → <code>#networking/network-packages</code> or <code>#security/security-packages</code> for apt tools</li>
<li>Use <strong>Diagnostics → Shell</strong> for sudo and apt</li>
<li>Try <strong>Linux UFW</strong>, WiFi hub, Doctors, or Leak tests</li>
<li>Tools → Activity log tracks what nordctl did</li></ol>
<p>If you later install NordVPN, use the top bar <strong>Wizard</strong> button or <code>#dashboard/wizard</code>.</p>
""",
        },
        {
            "id": "faq",
            "title": "FAQ",
            "html": """
<dl class="faq"><dt>Does nordctl include NordVPN?</dt><dd>No — official package only.</dd>
<dt>Does nordctl run as a service?</dt><dd>The web UI can run manually (<code>nordctl serve</code>) or as a systemd user service (<code>nordctl service install</code> / <code>bootstrap</code>). Debian .deb: open <strong>nordctl</strong> from the app menu — first launch enables UI at login. Nord VPN itself uses the system service <code>nordvpnd</code>.</dd>
<dt>Ubuntu .deb / app menu?</dt><dd>Build with <code>bash scripts/build-deb.sh</code>, install <code>sudo apt install ./dist/nordctl_*_all.deb</code>, then launch <strong>nordctl</strong> from Activities. Uninstall: <code>sudo apt remove nordctl</code>.</dd>
<dt>System tray?</dt><dd>Optional: <code>pip install 'nordctl[tray]' && nordctl tray install</code> or say yes during <code>./install.sh</code>.</dd>
<dt>Why no login in the UI?</dt><dd>Security — use terminal <code>nordvpn login</code>.</dd>
<dt>Is the UI exposed to the network?</dt><dd>Default is <strong>This computer only</strong> (<code>127.0.0.1</code>). You can enable Home LAN in <strong>Advanced → Services → Network access</strong> so other devices on <code>192.168.x</code> or <code>10.x</code> can connect — only on networks you trust.</dd>
<dt>macOS?</dt><dd>Linux only in v0.2.</dd>
<dt>Button hovers?</dt><dd>Hover any action button for a tooltip. Help → Every button explained lists them all.</dd>
<dt>Why is Home IP missing in the top bar?</dt><dd>With VPN on, Home is shown only on home WiFi (<code>wifi.profiles</code> or <code>wifi_zones.trusted</code>). Disconnect VPN once at home to auto-learn, or set <code>home_public_ip</code> on a trusted zone. See Help → Top bar IP addresses.</dd>
<dt>Why not my real ISP when VPN is on?</dt><dd>Default-route IP checks often show a Nord relay. nordctl uses per-SSID cache or zone config on home WiFi instead.</dd></dl>
""",
        },
    ]


SECTION_AUDIENCE: dict[str, str] = {
    "navigation": "all",
    "site-map": "all",
    "start": "all",
    "services": "tools",
    "install": "nord",
    "config": "nord",
    "topbar-ip": "all",
    "presets": "nord",
    "smartdns": "nord",
    "firewall": "all",
    "baseline": "tools",
    "logs": "tools",
    "onboarding": "all",
    "alerts-tier4": "tools",
    "wifi-hub": "network",
    "security-hub": "network",
    "traffic": "network",
    "wifi-spectrum": "network",
    "network": "network",
    "sudo": "network",
    "troubleshoot": "all",
    "cli": "nord",
    "factory-reset": "tools",
    "buttons": "all",
    "control-tab": "network",
    "automate-tab": "tools",
    "editor-tab": "tools",
    "network-tools-install": "network",
    "security-tools-install": "network",
    "tools-only-mode": "network",
    "network-access": "network",
    "terminal-tab": "all",
    "regional-presets": "nord",
    "dashboard-layout": "nord",
    "extra-settings": "tools",
    "open-source": "all",
    "legal": "all",
    "faq": "all",
    "start-nord": "nord",
    "start-network": "network",
}


def _attach_help_audience(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sec in sections:
        row = dict(sec)
        row["audience"] = SECTION_AUDIENCE.get(row["id"], "all")
        out.append(row)
    return out


def _expand_help_paths(html: str) -> str:
    from nordctl.paths import (
        PRIV_SUDOERS_SCRIPT,
        UFW_SUDOERS_SCRIPT,
        install_script_sudo_cmd,
        package_root,
    )

    repl = {
        "{ufw_sudoers_cmd}": install_script_sudo_cmd(UFW_SUDOERS_SCRIPT),
        "{privileges_sudoers_cmd}": install_script_sudo_cmd(PRIV_SUDOERS_SCRIPT),
        "{package_root}": str(package_root()),
    }
    for key, value in repl.items():
        html = html.replace(key, value)
    return html


def get_help_sections() -> list[dict[str, Any]]:
    sections = _attach_help_audience(_HELP_SECTIONS_RAW)
    out: list[dict[str, Any]] = []
    for sec in sections:
        row = dict(sec)
        if row.get("html"):
            row["html"] = _expand_help_paths(row["html"])
        out.append(row)
    return out


def help_profile(cfg: dict[str, Any] | None = None) -> str:
    from nordctl.config import effective_install_profile

    return effective_install_profile(cfg)


def help_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config

    cfg = cfg or load_config()
    profile = help_profile(cfg)
    sections = get_help_sections()
    if profile == "nord":
        sections = [
            s
            for s in sections
            if s.get("audience", "all") in ("nord", "all") and s["id"] not in ("start", "start-network")
        ]
    elif profile == "network":
        sections = [
            s
            for s in sections
            if s.get("audience", "all") in ("network", "all") and s["id"] not in ("start", "start-nord")
        ]
    return {"ok": True, "sections": sections, "version": 20, "profile": profile}
