/* nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a */
(() => {
  const $ = (id) => document.getElementById(id);
  let busy = false;
  let lastState = null;
  let lastSwitchesData = null;
  let countries = [];
  /** Preserve country picks on city rows across dropdown rebuilds (field id → country code). */
  const pendingCityCountries = {};
  let nettoolSelected = { adv: "overview", network: "overview" };
  let trafficFilter = "all";
  let trafficLiveTimer = null;
  let logsFilter = "all";
  let logsLiveTimer = null;
  let cachedLogEntries = [];
  const LOGS_LIMIT_KEY = "nordctl_logs_limit";
  const LOGS_LIMIT_DEFAULT = 10;
  const LOGS_LIMIT_MAX = 100;
  function getLogsDisplayLimit() {
    const n = parseInt(localStorage.getItem(LOGS_LIMIT_KEY) || String(LOGS_LIMIT_DEFAULT), 10);
    return Math.min(LOGS_LIMIT_MAX, Math.max(1, Number.isFinite(n) ? n : LOGS_LIMIT_DEFAULT));
  }
  function setLogsDisplayLimit(n) {
    const v = Math.min(LOGS_LIMIT_MAX, Math.max(1, parseInt(n, 10) || LOGS_LIMIT_DEFAULT));
    localStorage.setItem(LOGS_LIMIT_KEY, String(v));
    return v;
  }
  const LOG_CATEGORY_META = {
    vpn: "🛡️", dns: "🌐", network: "📡", scan: "🔍", terminal: "⌨️", install: "📦",
    audit: "📋", service: "⚙️", preset: "⚡", system: "💻", security: "🔒", error: "⚠️",
  };
  const TOOLS_NORD_ONLY_TABS = new Set(["auto-watcher", "schedules", "snapshots"]);

  const NETTOOL_SCOPES = {
    adv: {
      buttons: "advNettoolButtons",
      target: "advNettoolTarget",
      targets: "advNettoolTargets",
      output: "advNettoolOutput",
      badge: "advNettoolBadge",
      help: "advNettoolHelp",
    },
    network: {
      buttons: "networkSetupButtons",
      target: null,
      targets: null,
      output: "networkSetupOutput",
      badge: "networkSetupBadge",
      help: "networkSetupHelp",
    },
  };
  const NETWORK_SETUP_TOOLS = new Set([
    "overview", "routes", "interfaces", "resolv", "connections", "neighbors", "public_ip", "listening", "networkmanager",
  ]);

  const LOG_KEY = "nordctl_activity";
  const UI_TOKEN_KEY = "nordctl_ui_token";
  const LEGACY_UI_TOKEN_KEY = "nordctl_lab_token";
  const DIAGNOSTICS_TAB_KEY = "nordctl_diagnostics_tab";
  const LEGACY_DIAGNOSTICS_TAB_KEY = "nordctl_lab_tab";
  (function migrateLegacyBrowserKeys() {
    if (!sessionStorage.getItem(UI_TOKEN_KEY) && sessionStorage.getItem(LEGACY_UI_TOKEN_KEY)) {
      sessionStorage.setItem(UI_TOKEN_KEY, sessionStorage.getItem(LEGACY_UI_TOKEN_KEY));
    }
    if (!localStorage.getItem(DIAGNOSTICS_TAB_KEY) && localStorage.getItem(LEGACY_DIAGNOSTICS_TAB_KEY)) {
      localStorage.setItem(DIAGNOSTICS_TAB_KEY, localStorage.getItem(LEGACY_DIAGNOSTICS_TAB_KEY));
    }
  })();
  const THEME_KEY = "nordctl_theme";
  const SETUP_DISMISS_KEY = "nordctl_optional_setup_dismiss";
  const DASH_SUBNAV_REV = 9;
  const HUB_SUBNAV_REV = 6;
  const TOOLS_SUBNAV_REV = 3;
  const DASH_SUBNAV_REV_KEY = "nordctl_dash_subnav_rev";
  const HUB_SUBNAV_REV_KEY = "nordctl_hub_subnav_rev";
  const TOOLS_SUBNAV_REV_KEY = "nordctl_tools_subnav_rev";
  const DASH_TAB_KEY = "nordctl_dash_tab";
  const WIFI_TAB_KEY = "nordctl_wifi_tab";
  const HELP_CACHE_KEY = "nordctl_help_cache_v";
  function esc(value) {
    return String(value ?? "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** User-facing copy: local network changes vs Nord account-only settings. */
  const LOCAL_NETWORK_NOTICE =
    "These actions change Wi‑Fi, DNS, firewall, or other network settings on this computer itself (NetworkManager, UFW, system DNS) — not just your NordVPN account online.";
  const LOCAL_NETWORK_NOTICE_SHORT =
    "Changes this PC's Wi‑Fi / network — not just Nord online.";
  const LOCAL_NETWORK_SCOPES = {
    wifi_dns:
      "Smart DNS and Wi‑Fi profile actions edit NetworkManager connection profiles on this laptop — every device on your home LAN still uses its own DNS unless you configure them separately.",
    ufw:
      "UFW rules apply to this Linux host's firewall — separate from NordVPN's in-app firewall and from your router.",
    ipv6:
      "IPv6 changes apply to this computer's network stack — not to your Nord account or router by themselves.",
    rollback:
      "Rollback restores Wi‑Fi DNS, config, Nord settings, and IPv6 on this machine to the install baseline.",
    generic: LOCAL_NETWORK_NOTICE,
  };

  function localNetworkNoticeHtml(opts = {}) {
    const scope = opts.scope || "generic";
    const text = opts.short ? LOCAL_NETWORK_NOTICE_SHORT : (LOCAL_NETWORK_SCOPES[scope] || LOCAL_NETWORK_SCOPES.generic);
    return `<aside class="local-network-notice glass-inset" role="note"><strong>This PC — not just Nord online.</strong> ${esc(text)}</aside>`;
  }

  function switchAffectsLocalNetwork(sw) {
    if (!sw) return false;
    if (sw.affects_local_network) return true;
    const id = String(sw.id || sw.virtual || "");
    return id === "smart-dns-wifi" || sw.virtual === "smart_dns_wifi";
  }

  const BASELINE_NOTICE_SAVED =
    "On first use, nordctl saved an install baseline — a snapshot of config, Wi‑Fi DNS, Nord settings, and IPv6 on this computer. Revert anytime from Tools → Rollback.";
  const BASELINE_NOTICE_MISSING =
    "No install backup yet. nordctl normally creates one automatically on first use — open Tools → Rollback and click Create baseline now if you changed settings before that.";

  function baselineSafetyNoticeHtml(bl, opts = {}) {
    const jump = opts.jump !== false;
    const rollbackBtn = jump
      ? ` <button type="button" class="btn sm jump-link" data-view-jump="network/tools/rollback">Tools → Rollback</button>`
      : "";
    if (!bl?.exists) {
      return `<aside class="baseline-safety-notice glass-inset is-missing" role="note"><strong>No install backup yet.</strong> ${esc(BASELINE_NOTICE_MISSING)}${rollbackBtn}</aside>`;
    }
    const created = bl.created ? String(bl.created).slice(0, 10) : "";
    const when = created ? ` Saved ${esc(created)}.` : "";
    return `<aside class="baseline-safety-notice glass-inset" role="note"><strong>Install backup saved.</strong> ${esc(BASELINE_NOTICE_SAVED)}${when}${rollbackBtn}</aside>`;
  }

  function maybeAnnounceBaseline(data) {
    const bl = data?.baseline;
    if (!bl) return;
    const key = "nordctl_baseline_announced";
    if (sessionStorage.getItem(key)) return;
    if (bl.newly_created) {
      sessionStorage.setItem(key, "1");
      toast("Install baseline saved — revert anytime from Tools → Rollback", true);
      return;
    }
    if (bl.exists && !localStorage.getItem(key)) {
      localStorage.setItem(key, "1");
    }
  }

  function mountBaselineSafetyNotice(mountId, data) {
    const el = $(mountId);
    if (!el) return;
    el.innerHTML = baselineSafetyNoticeHtml(data?.baseline || lastState?.baseline || {});
    bindViewJumps(el);
  }

  const UI_DIAG_MAX = 40;
  const uiDiagEntries = [];
  let uiDiagOpen = false;

  function formatDiagTime(ts) {
    return formatLocaleTime(ts, true);
  }

  function localeTimeOpts(withSeconds = false) {
    const h24 = (uiPrefs.clock_format || "24h") === "24h";
    return h24
      ? {
          hour: "2-digit",
          minute: "2-digit",
          ...(withSeconds ? { second: "2-digit" } : {}),
          hour12: false,
        }
      : {
          hour: "2-digit",
          minute: "2-digit",
          ...(withSeconds ? { second: "2-digit" } : {}),
        };
  }

  function formatLocaleTime(ts, withSeconds = false) {
    try {
      return new Date(ts).toLocaleTimeString([], localeTimeOpts(withSeconds));
    } catch (_) {
      return "";
    }
  }

  function formatLocaleWeekday(ts) {
    try {
      return new Date(ts).toLocaleDateString([], { weekday: "long" });
    } catch (_) {
      return "";
    }
  }

  function formatLocaleDateShort(ts) {
    try {
      return new Date(ts).toLocaleDateString([], {
        day: "numeric",
        month: "short",
        year: "numeric",
      });
    } catch (_) {
      return "";
    }
  }

  function pushUiDiag(entry) {
    const msg = String(entry.message ?? entry.err ?? "").trim();
    if (!msg && !entry.title) return;
    const e = {
      ts: entry.ts || Date.now(),
      title: entry.title || "Error",
      message: msg || "Unknown error",
      source: entry.source || "app",
      hint: entry.hint || "",
    };
    const dupe = uiDiagEntries.find((x) => x.title === e.title && x.message === e.message && (Date.now() - x.ts) < 8000);
    if (dupe) return;
    uiDiagEntries.unshift(e);
    if (uiDiagEntries.length > UI_DIAG_MAX) uiDiagEntries.pop();
    renderUiDiag();
  }

  function uiDiagExportText() {
    return uiDiagEntries.slice().reverse().map((e) => {
      const lines = [`[${formatDiagTime(e.ts)}] ${e.title}`];
      if (e.source) lines.push(`Source: ${e.source}`);
      lines.push(e.message);
      if (e.hint) lines.push(`Hint: ${e.hint}`);
      return lines.join("\n");
    }).join("\n\n---\n\n");
  }

  function setUiDiagOpen(open) {
    uiDiagOpen = !!open;
    $("uiDiagPanel")?.classList.toggle("hidden", !uiDiagOpen);
    $("uiDiagBar")?.classList.toggle("open", uiDiagOpen);
    $("btnUiDiagToggle")?.setAttribute("aria-expanded", uiDiagOpen ? "true" : "false");
    document.body.classList.toggle("ui-diag-open", uiDiagOpen && uiDiagEntries.length > 0);
    if (uiDiagOpen) {
      requestAnimationFrame(() => {
        const panel = $("uiDiagPanel");
        if (panel) {
          document.documentElement.style.setProperty("--ui-diag-panel-h", `${panel.offsetHeight}px`);
        }
      });
    }
  }

  function renderUiDiag() {
    const bar = $("uiDiagBar");
    const countEl = $("uiDiagCount");
    const summary = $("uiDiagSummary");
    const list = $("uiDiagList");
    if (!bar) return;
    const n = uiDiagEntries.length;
    bar.classList.toggle("hidden", n === 0);
    document.body.classList.toggle("ui-diag-visible", n > 0);
    if (n === 0) {
      setUiDiagOpen(false);
      document.body.classList.remove("ui-diag-open");
      document.documentElement.style.removeProperty("--ui-diag-bar-h");
      document.documentElement.style.removeProperty("--ui-diag-panel-h");
      return;
    }
    if (countEl) countEl.textContent = String(n);
    if (summary) {
      summary.textContent = n === 1 ? "1 issue — click to view details" : `${n} issues — click to view details`;
    }
    if (list) {
      list.innerHTML = uiDiagEntries.map((e) =>
        `<article class="ui-diag-entry">
          <div class="ui-diag-entry-head">
            <strong>${esc(e.title)}</strong>
            <time datetime="${esc(new Date(e.ts).toISOString())}">${esc(formatDiagTime(e.ts))}</time>
          </div>
          <p class="ui-diag-entry-msg">${esc(e.message)}</p>
          ${e.source ? `<p class="ui-diag-entry-src">Where: ${esc(e.source)}</p>` : ""}
          ${e.hint ? `<p class="ui-diag-entry-hint">${esc(e.hint)}</p>` : ""}
        </article>`
      ).join("");
    }
    requestAnimationFrame(() => {
      const toggle = $("btnUiDiagToggle");
      if (toggle) {
        document.documentElement.style.setProperty("--ui-diag-bar-h", `${toggle.offsetHeight}px`);
      }
    });
  }

  function resetNordctlBrowserUiState() {
    for (const k of Object.keys(localStorage)) {
      if (k.startsWith("nordctl")) localStorage.removeItem(k);
    }
    for (const k of Object.keys(sessionStorage)) {
      if (k.startsWith("nordctl")) sessionStorage.removeItem(k);
    }
    const base = location.pathname + location.search.split("?")[0];
    location.href = `${base}?_=${Date.now()}${location.hash || "#dashboard"}`;
  }

  function drainUiDiagQueue() {
    const q = window.__nordctlDiagQueue;
    if (!Array.isArray(q) || !q.length) return;
    q.forEach((entry) => pushUiDiag(entry));
    window.__nordctlDiagQueue = [];
  }

  function initUiDiag() {
    drainUiDiagQueue();
    $("btnUiDiagToggle")?.addEventListener("click", () => setUiDiagOpen(!uiDiagOpen));
    $("btnUiDiagClear")?.addEventListener("click", () => {
      uiDiagEntries.length = 0;
      renderUiDiag();
    });
    $("btnUiDiagCopy")?.addEventListener("click", async () => {
      const text = uiDiagExportText();
      if (!text) return;
      try {
        await navigator.clipboard.writeText(text);
        toast("Diagnostics copied", true);
      } catch (_) {
        showNotice(text, { ok: true, title: "UI diagnostics", copyText: text });
      }
    });
    $("btnUiDiagReset")?.addEventListener("click", () => {
      if (confirm(
        "Clear nordctl saved routes and browser login token, then reload?\n\n"
        + "Your VPN config (~/.config/nordctl/) is not changed.\n\n"
        + "Use this when the page works in incognito but not here."
      )) resetNordctlBrowserUiState();
    });
    $("btnResetUiCache")?.addEventListener("click", resetNordctlBrowserUiState);
    $("btnTopbarRestartNordctl")?.addEventListener("click", () => serviceAction("ui", "restart"));
    window.addEventListener("error", (ev) => {
      pushUiDiag({
        title: "JavaScript error",
        message: ev.message || "Script error",
        source: ev.filename ? `${ev.filename}:${ev.lineno || 0}` : "script",
        hint: "Hard refresh (Ctrl+Shift+R) or Reset UI cache (top right)",
      });
    });
    window.addEventListener("unhandledrejection", (ev) => {
      const reason = ev.reason;
      pushUiDiag({
        title: "Unhandled promise rejection",
        message: String(reason?.message || reason || "Unknown rejection"),
        source: reason?.stack ? String(reason.stack).split("\n")[0] : "promise",
        hint: "Try Reset UI cache (top right) or Ctrl+Shift+R",
      });
    });
  }

  const apiCache = new Map();
  const CACHE_TTL = {
    tools: 45000,
    nettools: 30000,
    help: 120000,
    state: 25000,
    stateQuick: 8000,
    network: 20000,
    connectionDetails: 15000,
    lab: 30000,
    overallAudit: 30000,
    security: 45000,
    securitySummary: 15000,
    wifi: 25000,
    ufw: 25000,
    listeners: 15000,
    host: 8000,
    meshnet: 15000,
  };

  if (window.__nordctlPreboot?.ok) {
    apiCache.set("/api/state/quick", {
      data: window.__nordctlPreboot,
      ts: window.__nordctlPreboot._ts || Date.now(),
    });
  }

  function invalidateApiCache(prefix) {
    if (!prefix) {
      apiCache.clear();
      return;
    }
    for (const key of [...apiCache.keys()]) {
      if (key.startsWith(prefix)) apiCache.delete(key);
    }
  }

  async function apiCached(path, opts = {}, ttlMs = 0) {
    const method = (opts.method || "GET").toUpperCase();
    if (method !== "GET" || !ttlMs) return api(path, opts);
    const hit = apiCache.get(path);
    if (hit && Date.now() - hit.ts < ttlMs) return hit.data;
    const data = await api(path, opts);
    apiCache.set(path, { data, ts: Date.now() });
    return data;
  }

  const REGION_ORDER = ["general", "europe", "americas", "asia-pacific", "global"];
  const REGION_LABELS = {
    general: "General",
    europe: "Europe",
    americas: "Americas",
    "asia-pacific": "Asia-Pacific",
    global: "Global",
  };

  const QUICK_START = [
    { preset: "reconnect-country", icon: "🏠", label: "Reconnect (country)", summary: "Reconnect to your home country from config" },
    { preset: "streaming-smartdns", icon: "📡", label: "TV streaming (Smart DNS)", summary: "VPN off, Nord Smart DNS on WiFi, Meshnet stays on" },
    { preset: "public-wifi", icon: "☕", label: "Public Wi‑Fi safe", summary: "Kill switch and firewall on — for cafés, hotels, airports" },
    { preset: "privacy-max", icon: "🔒", label: "Privacy max", summary: "Kill switch, firewall, and Nord DNS enabled" },
  ];

  const PRESET_CATEGORY_ORDER = [
    "Basics", "Connect", "Streaming", "Privacy", "Security", "Performance",
    "Regional", "Settings",
  ];
  /** Preset categories on dedicated dashboard tabs — empty for now (build later). */
  const DASHBOARD_PRESET_PANELS = {};
  /** Live toggles on Switches — no dedicated preset tab (CLI presets still apply). */
  const SWITCHES_ONLY_PRESET_CATEGORIES = [
    "Technology", "Advanced", "Nord firewall", "DNS", "Kill switch", "Meshnet",
  ];
  const DASHBOARD_TABS_MOVED_TO_SWITCHES = new Set([
    "advanced", "technology", "nord-firewall", "kill-switch",
  ]);
  /** Removed dashboard tabs — old bookmarks redirect here. */
  const DASHBOARD_TABS_REMOVED = {
    "server-groups": "connect",
    "home-lan": "split-tunnel",
  };
  const WORKFLOWS_EXCLUDED_PRESET_CATEGORIES = [
    ...Object.values(DASHBOARD_PRESET_PANELS).map((p) => p.category),
    ...SWITCHES_ONLY_PRESET_CATEGORIES,
  ];
  const PRESET_CATEGORY_INTRO = {
    Basics: "Simple fixes — disconnect VPN or restore Nord defaults.",
    Connect: "Connect using your saved country, city, or server from My places.",
    Streaming: "Smart DNS and streaming-friendly setups — VPN off, streaming apps work.",
    Privacy: "Threat protection, analytics off, and maximum privacy bundles.",
    Security: "Public WiFi and other safe-network bundles.",
    DNS: "Custom DNS and Nord DNS while connected.",
    "Nord firewall": "Turn NordVPN firewall on or off when connected.",
    Performance: "Gaming, VoIP, and lightweight VPN modes.",
    "Split tunnel": "Work VPN and LAN allowlists — local devices stay reachable.",
    Meshnet: "Meshnet on/off and peer access.",
    "Server groups": "Dedicated IP, Double VPN, Onion over VPN, and specialty servers.",
    Regional: "Region-specific travel and streaming presets (EU, UK, US, APAC, etc.).",
    Settings: "Tray, notifications, autoconnect, and virtual locations.",
    Technology: "NordLynx, OpenVPN, NordWhisper, and post-quantum.",
    Advanced: "Routing and low-level Nord toggles — use Help if unsure.",
    "Kill switch": "Turn kill switch on or off — blocks internet if VPN drops.",
  };

  const HUB_TAB_KEY = "nordctl_hub_tab";
  const PAGE_HOW_HIDDEN_KEY = "nordctl_page_how_hidden";
  const PAGE_HOW_USER_SET_KEY = "nordctl_page_how_user_set";
  const HUB_PRIMARY_KEY = "nordctl_hub_primary_tab";
  const TOOLS_TAB_KEY = "nordctl_tools_tab";

  const HUB_TABS = {
    wifi: { view: "wifi", page: null, label: "WiFi", title: "WiFi profiles, zones, and checks", group: "networking" },
    "map-internet": { view: "advanced", page: "traffic-internet", label: "Internet traffic", title: "Outbound and inbound internet sessions from this PC", group: "networking" },
    "map-local": { view: "advanced", page: "traffic-local", label: "Local traffic", title: "LAN and Meshnet sessions on this PC", group: "networking" },
    "traffic-live": { view: "advanced", page: "traffic-live", label: "Live bandwidth", title: "Real-time throughput per interface", group: "networking" },
    "traffic-speed": { view: "advanced", page: "traffic-speed", label: "Speed test", title: "Download speed lab with history and VPN comparison", group: "networking" },
    "spectrum-analyzer": { view: "advanced", page: "spectrum-analyzer", label: "Spectrum", title: "WiFi spectrum analyzer with band filters", group: "networking" },
    "bluetooth-spectrum": { view: "advanced", page: "bluetooth-spectrum", label: "Bluetooth", title: "Bluetooth ISM spectrum, devices, and security", group: "networking" },
    network: { view: "security", page: null, label: "Routes & DNS", title: "DNS assistant and IPv6 controls", group: "networking" },
    services: { view: "advanced", page: "services", label: "Services", title: "nordctl UI and LAN access", group: "networking" },
    "network-packages": { view: "advanced", page: "network-packages", label: "Networking packages", title: "Diagnostics and WiFi apt packages", group: "networking" },
    "networking-shell": { view: "lab", page: "audit", label: "Networking shell", title: "Interactive bash for routes, WiFi, and apt networking tools", group: "networking", shellScope: "network" },
    monitoring: { view: "security", page: "overview", label: "Overview", title: "Health score and summary", group: "security" },
    doctors: { view: "doctors", page: null, label: "Doctors", title: "Health and network doctors", group: "security" },
    "leak-tests": { view: "lab", page: "leak", label: "Leak tests", title: "DNS and routing leak tests", group: "security" },
    audit: { view: "lab", page: "overall", label: "Audit", title: "Overall privacy audit", group: "security" },
    "host-ufw": { view: "control", page: null, label: "Linux UFW", title: "Linux UFW firewall editor", group: "security" },
    listeners: { view: "advanced", page: "listeners", label: "Listeners", title: "TCP listening ports on this computer", group: "security" },
    "security-packages": { view: "advanced", page: "security-packages", label: "Security packages", title: "Firewall, audit, and hardening apt packages", group: "security" },
    "security-shell": { view: "lab", page: "audit", label: "Security shell", title: "Interactive bash for UFW, Lynis, fail2ban, and security apt tools", group: "security", shellScope: "security" },
    privileges: { view: "advanced", page: "privileges", label: "Privileges", title: "Passwordless sudo for UI fixes", group: "security" },
  };

  /** Old hub tab ids — redirect bookmarks only. */
  const LEGACY_HUB_TABS = {
    setup: { redirectTab: "security-packages", redirectSub: null },
    diagnostics: { redirectTab: "networking-shell", redirectSub: null },
  };

  const HUB_PRIMARY_TABS = {
    networking: { label: "Networking", title: "WiFi, traffic, routes, diagnostics, services, and packages" },
    security: { label: "Security", title: "Overview, doctors, leak tests, audit, firewall, listeners, packages, and privileges" },
  };

  const HUB_PRIMARY_DEFAULT_TAB = {
    networking: "wifi",
    security: "monitoring",
  };

  function hubRoutePrefixForTab(tabId, sectionHint) {
    if (sectionHint === "networking" || sectionHint === "security") return sectionHint;
    if (tabId === "tools") return "tools";
    const group = hubTabGroup(tabId);
    return group === "security" ? "security" : "networking";
  }

  function canonicalHubPath(key) {
    const parts = String(key || "").split("/").filter(Boolean);
    if (!parts.length) return key;
    if (parts[0] === "networking" || parts[0] === "security" || parts[0] === "tools") return parts.join("/");
    if (parts[0] !== "network") return parts.join("/");
    if (parts[1] === "tools") {
      return parts.length > 2 ? `tools/${parts.slice(2).join("/")}` : "tools/auto-guide";
    }
    if (parts[1] === "networking" || parts[1] === "security") return parts.slice(1).join("/");
    const tab = parts[1];
    if (!tab) return hubPrimaryTab || "networking";
    return [hubRoutePrefixForTab(tab), ...parts.slice(1)].join("/");
  }

  function isHubRouteSection(section) {
    return section === "network" || section === "networking" || section === "security";
  }

  function hubTabGroup(tabId) {
    if (tabId === "tools") return null;
    return HUB_TABS[tabId]?.group || "networking";
  }

  function isToolsHubRoute(route) {
    return route?.section === "network" && route?.tab === "tools";
  }

  function isToolsHubActive(viewName) {
    if (TOOLS_VIEWS.has(viewName)) return true;
    if (viewName === "terminal" && termRouteSection() === "tools") return true;
    const route = parseRouteHash();
    return route?.section === "tools" || isToolsHubRoute(route);
  }

  function hubTabsInGroup(group) {
    return Object.entries(HUB_TABS).filter(([, cfg]) => cfg.group === group).map(([id]) => id);
  }

  const TOOLS_TABS = {
    settings: { view: "settings", page: null, label: "Settings", title: "Nord and Network & Security settings" },
    "auto-guide": { view: "automate", page: "guide", label: "Overview", title: "Tools overview — log, editor, rollback, automation" },
    logs: { view: "logs", page: null, label: "Activity log", title: "Plain-English activity log" },
    "auto-watcher": { view: "automate", page: "watcher", label: "Zone watcher", title: "WiFi zone watcher (Nord presets)", nordOnly: true },
    schedules: { view: "automate", page: "schedules", label: "Schedules", title: "Scheduled presets", nordOnly: true },
    rollback: { view: "automate", page: "rollback", label: "Rollback", title: "Restore install baseline" },
    reset: { view: "automate", page: "reset", label: "Factory reset", title: "Factory reset" },
    snapshots: { view: "automate", page: "snapshots", label: "Nord snapshots", title: "NordVPN settings snapshots", nordOnly: true },
    editor: { view: "editor", page: null, label: "Editor", title: "Edit config files — last resort" },
    "custom-shell": { view: "customShell", page: null, label: "Custom shell", title: "Shells for your custom quick-command categories" },
    "custom-packages": { view: "customPackages", page: null, label: "Custom packages", title: "Your apt packages by category — separate from Networking and Security catalogs" },
    "pc-info": { view: "pcInfo", page: null, label: "PC info", title: "Complete hardware and system inventory for this computer" },
  };

  const WORKFLOW_SECTIONS = new Set(["places", "my-presets", "workflows", "favorites", "scenarios"]);

  function normalizeDashboardTab(tab) {
    if (tab === "scenarios" || tab === "places" || tab === "favorites") return "workflows";
    if (tab === "presets") return "workflows";
    if (tab === "setup") return "wizard";
    if (tab === "nord-services") return "nord-services";
    if (DASHBOARD_TABS_REMOVED[tab]) return DASHBOARD_TABS_REMOVED[tab];
    if (DASHBOARD_TABS_MOVED_TO_SWITCHES.has(tab)) return "switches";
    return tab;
  }

  function defaultDashboardTab(data) {
    return "connect";
  }

  function resolveDashboardTab(routeTab, fallbackTab) {
    let tab = normalizeDashboardTab(routeTab || fallbackTab || defaultDashboardTab());
    if (tab === null) tab = defaultDashboardTab();
    if (tab === "optional-extras") tab = "connect";
    /* Wizard is topbar-only — open only when the URL explicitly requests it */
    if (!routeTab && tab === "wizard") tab = defaultDashboardTab();
    if (!DASHBOARD_TABS[tab]) tab = defaultDashboardTab();
    return tab;
  }

  function dashboardPanelTab(tab) {
    return tab;
  }

  function scrollToLanRangeOnly() {
    const box = $("splitLanSetup");
    const input = $("lanAllowlistCidr");
    if (!box) return false;
    box.scrollIntoView({ behavior: "smooth", block: "center" });
    box.classList.add("loc-highlight");
    setTimeout(() => box.classList.remove("loc-highlight"), 2800);
    input?.focus();
    return true;
  }

  function scrollToWorkflowSection(sectionId) {
    const el = document.getElementById(`workflowsSection-${sectionId}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function scrollToDiagnosticsTerminal(opts = {}) {
    if (termRouteSection() !== "network") return false;
    const postBar = $("termPostInstallBar");
    const preferPostBar = opts.preferPostInstallBar !== false
      && postBar
      && !postBar.classList.contains("hidden");
    const target = preferPostBar ? postBar : ($("termViewport") || $("terminalPanel"));
    if (!target) return false;
    const behavior = opts.behavior || "smooth";
    const run = () => {
      target.scrollIntoView({ behavior, block: preferPostBar ? "end" : "center" });
      const stage = target.closest(".stage-scroll");
      if (stage) {
        const rect = target.getBoundingClientRect();
        const stageRect = stage.getBoundingClientRect();
        const offset = rect.top - stageRect.top + stage.scrollTop - (preferPostBar ? 8 : 20);
        if (Math.abs(stage.scrollTop - offset) > 8) {
          stage.scrollTo({ top: Math.max(0, offset), behavior });
        }
      }
    };
    requestAnimationFrame(() => requestAnimationFrame(run));
    return true;
  }

  function scrollToPostInstallBar(opts = {}) {
    return scrollToDiagnosticsTerminal({ ...opts, preferPostInstallBar: true });
  }

  function termCommandIsPackageChange(cmd) {
    const text = String(cmd || "");
    return /\bapt(-get)?\s+(install|remove|purge|autoremove)\b/i.test(text)
      || /\bdpkg\s+-i\b/i.test(text)
      || /\bnordctl\s+install-nordvpn\b/i.test(text)
      || /NordVPN official apt install/i.test(text);
  }

  function dashboardTabForPresetSub(sub) {
    const want = String(sub || "").toLowerCase();
    if (DASHBOARD_TABS_REMOVED[want]) return DASHBOARD_TABS_REMOVED[want];
    if (DASHBOARD_TABS_MOVED_TO_SWITCHES.has(want) || want === "dns" || want === "nord-dns") return "switches";
    if (want === "server-groups" || want === categorySlug("Server groups")) return "connect";
    for (const cat of SWITCHES_ONLY_PRESET_CATEGORIES) {
      if (want === categorySlug(cat)) return "switches";
    }
    for (const [tabId, panel] of Object.entries(DASHBOARD_PRESET_PANELS)) {
      if (want === tabId || want === categorySlug(panel.category)) return tabId;
    }
    return null;
  }

  function presetPanelConfigForGrid(gridId) {
    return Object.values(DASHBOARD_PRESET_PANELS).find((p) => p.grid === gridId) || null;
  }

  function applyWorkflowsSubRoute(sub) {
    if (!sub) return;
    if (sub === "presets" || sub === "scenarios") sub = "my-presets";
    if (sub === "workflows") sub = "my-presets";
    if (WORKFLOW_SECTIONS.has(sub)) {
      requestAnimationFrame(() => scrollToWorkflowSection(sub));
      return;
    }
    const dashTab = dashboardTabForPresetSub(sub);
    if (dashTab) {
      navigateRoute("dashboard", dashTab);
      return;
    }
    pendingPresetCategory = sub;
    if (lastState?.presets) renderWorkflowPresets(lastState);
    requestAnimationFrame(() => {
      scrollToWorkflowSection("workflows");
      scrollToPresetCategory(sub);
    });
  }

  function scrollToPresetCategory(catOrSlug) {
    const el = document.getElementById(`preset-category-${categorySlug(catOrSlug)}`);
    if (el) el.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  function toggleInlineEdit(panel) {
    if (!panel) return;
    panel.classList.toggle("hidden");
  }

  function rootHasOpenInlineEdit(root) {
    if (!root) return false;
    return !!root.querySelector(".wf-inline-edit:not(.hidden), .preset-inline-edit:not(.hidden)");
  }

  function skipRenderWhileEditing(root) {
    return rootHasOpenInlineEdit(root);
  }

  function renderHiddenPanel(container, title, rowsHtml) {
    if (!container) return;
    if (!rowsHtml) {
      container.innerHTML = "";
      container.classList.add("hidden");
      return;
    }
    container.classList.remove("hidden");
    container.innerHTML = `<details class="wf-hidden-panel" open><summary>${esc(title)}</summary><div class="wf-hidden-list">${rowsHtml}</div></details>`;
  }

  const DASHBOARD_TABS = {
    connect: { label: "Connect", title: "VPN status and connect" },
    workflows: { label: "My presets", title: "My presets, saved places, custom workflows, and favorites" },
    "create-presets": { label: "Create preset", title: "Smart preset builder — every Nord setting" },
    "connection-details": { label: "Connection details", title: "Full path — device, ISP, VPN, interfaces" },
    switches: { label: "Switches", title: "Live Nord toggles — change one setting mid-session" },
    "split-tunnel": { label: "Split tunnel", title: "LAN allowlist editor" },
    "nord-dns": { label: "Nord DNS", title: "Smart DNS IPs and Nord Account setup" },
    meshnet: { label: "Meshnet", title: "Device mesh, peers, and routing" },
    terminal: { label: "Nord shell", title: "NordVPN login, status, and doctor commands" },
    "nord-doctor": { label: "Nord doctor", title: "NordVPN install, login, settings, and health checks" },
    "nord-services": { label: "Nord services", title: "nordvpnd daemon and system tray" },
    wizard: { label: "Wizard", title: "Setup wizard — NordVPN, WiFi, alerts, and checklist", topbarOnly: true },
  };

  /** Dashboard tabs that require NordVPN to be installed before presets/connect work (not hidden — shown with hints). */
  const DASHBOARD_NORDVPN_TABS = new Set([
    "connect", "meshnet", "workflows", "create-presets", "switches", "split-tunnel", "nord-dns",
  ]);

  /** Plain-English intro + help section id for each route (section/tab). */
  const TAB_INTROS = {
    dashboard: { title: "Nord Dashboard", text: "Connect, Meshnet, presets, switches, Nord DNS, wizard, Nord doctor, Nord services, and Nord shell. Use the top <strong>Wizard</strong> button for first-run setup.", help: "dashboard-layout" },
    network: { title: "Networking & Security", text: "Use the top <strong>Networking</strong> or <strong>Security</strong> pill, then pick a section tab below. Activity log and automate live under top <strong>Tools</strong>.", help: "navigation" },
    networking: { title: "Networking", text: "WiFi, internet and local traffic maps, routes and DNS, diagnostics shell, networking apt packages, and UI services.", help: "navigation" },
    security: { title: "Security", text: "Health overview, doctors, leak tests, privacy audit, Linux UFW firewall, security apt packages, and one-time sudo privileges.", help: "navigation" },
    "network/networking": { title: "Networking", text: "WiFi, traffic maps, routes & DNS, diagnostics shell, and services. Activity log and automate live under the top <strong>Tools</strong> tab.", help: "navigation" },
    "network/security": { title: "Security", text: "Health overview, doctors, leak tests, privacy audit, UFW firewall, package tools, and sudo privileges.", help: "navigation" },
    settings: { title: "Settings", text: "Nord settings (password, UI service) and alert settings (browser and email notifications for VPN, WiFi, and health events).", help: "extra-settings" },
    tools: { title: "Tools", text: "Activity log, config editor, rollback, and optional VPN automation (schedules, WiFi zone watcher, snapshots). NordVPN commands are on <strong>Nord Dashboard → Nord shell</strong>; system bash under <strong>Networking → Diagnostics → Shell</strong>.", help: "automate-tab" },
    "dashboard/connect": { title: "Connect", text: "Quick connect, everyday presets, full scenario library, and location scenarios.", help: "dashboard-layout" },
    "dashboard/meshnet": { title: "Meshnet", text: "Turn Meshnet on, see your mesh IP, link devices, and route traffic through a peer — without opening router ports.", help: "dashboard-layout" },
    "dashboard/connection-details": { title: "Connection details", text: "Full path from this PC to ISP and VPN — MAC addresses, interfaces, routes, and NordVPN settings when connected.", help: "topbar-ip" },
    "dashboard/workflows": { title: "My presets", text: "Step 1: My places (saved values). Step 2: My presets (run, edit, hide, delete). Step 3: Create preset wizard tab. Step 4: Favorites.", help: "presets" },
    "dashboard/workflows/places": { title: "My places", text: "Save countries and cities once — custom workflows substitute these placeholders automatically.", help: "config" },
    "dashboard/workflows/workflows": { title: "Custom workflows", text: "Your preset YAML files — create blank or from example, then run with one tap.", help: "presets" },
    "dashboard/workflows/scenarios": { title: "My presets", text: "Your saved one-click presets — Run, Edit preset (full builder), edit name, edit YAML, hide, or delete from each card.", help: "presets" },
    "dashboard/workflows/favorites": { title: "Favorites", text: "Star countries or cities for one-tap NordVPN connect.", help: "dashboard-layout" },
    "dashboard/workflows/my-presets": { title: "My presets", text: "Your saved one-click presets — Run, edit name, edit YAML, hide, or delete from each card.", help: "presets" },
    "dashboard/create-presets": { title: "Create preset", text: "Step-by-step wizard with help beside every option. Save when done — run it later from My presets.", help: "presets" },
    "dashboard/switches": {
      title: "Switches",
      text: "Live Nord toggles — one setting at a time. When VPN is on, incompatible switches are greyed out; others may reconnect you. For a full multi-step setup, use Create preset.",
      help: "presets",
    },
    "dashboard/wizard": { title: "Setup wizard", text: "Install NordVPN, run quick or full setup, and fix checklist items — step by step on this page.", help: "install" },
    "dashboard/nord-doctor": { title: "Nord doctor", text: "Read-only NordVPN health checks — install, login, nordvpnd, settings, Meshnet, DNS, and travel-safe options.", help: "troubleshoot" },
    "dashboard/nord-services": { title: "Nord services", text: "Start, stop, and enable <strong>nordvpnd</strong> at boot, plus optional system tray autostart.", help: "services" },
    "dashboard/terminal": { title: "Nord shell", text: "NordVPN and nordctl commands — login, status, and doctor. Customize buttons in Settings → Quick commands. For system bash use Networking or Security shell.", help: "terminal-tab" },
    "dashboard/optional-extras": { title: "Optional extras", text: "Enable Network & Security modules (Nord VPN focus) or install networking and security apt packages.", help: "dashboard-layout" },
    "dashboard/split-tunnel": { title: "Split tunnel", text: "Set Home LAN range (local subnet while LAN split tunnel is on), plus extra subnets and ports that bypass the VPN.", help: "dashboard-layout" },
    "dashboard/nord-dns": { title: "Nord DNS setup", text: "Nord DNS (NordVPN setting while VPN is on) and Smart DNS on WiFi (changes this PC's Wi‑Fi via NetworkManager). Copy home ISP for Nord Account allowlisting.", help: "smartdns" },
    "network/monitoring": { title: "Overview", text: "Network health from leak tests, audit, DNS, and routing. VPN status and connect are on Nord Dashboard.", help: "security-hub" },
    "network/profiles": { title: "Custom workflows", text: "Moved to Nord Dashboard → My presets → Custom workflows.", help: "presets" },
    "network/network": { title: "Network", text: "Live bandwidth, speed test, DNS assistant, IPv6, and current configuration — pick a tab below.", help: "security-hub" },
    "network/network/bandwidth": { title: "Live bandwidth", text: "Download and upload per interface — VPN tunnel highlighted.", help: "security-hub" },
    "network/network/speed": { title: "Speed test", text: "Simple download test through your current route (VPN if connected).", help: "security-hub" },
    "network/network/dns": { title: "DNS assistant", text: "Detects Pi-hole, Unbound, and systemd-resolved conflicts with Nord DNS on this computer.", help: "security-hub" },
    "network/network/ipv6": { title: "IPv6 on your LAN", text: "Balance local device IPv6 vs internet leak risk.", help: "security-hub" },
    "network/network/config": { title: "Network configuration", text: "Moved to Diagnostics → Checks — read-only routes, DNS, interfaces, and security scans.", help: "security-hub" },
    "network/diagnostics/packages": { title: "Networking packages", text: "Diagnostics, WiFi, and network apt packages — curl, dig, mtr, nmap, NetworkManager, …", help: "network-tools-install" },
    "network/setup": { title: "Packages", text: "Security apt packages and one-time sudo privileges for automated fixes.", help: "security-tools-install" },
    "network/traffic/live": { title: "Live bandwidth", text: "Real-time throughput per interface with history graph, VPN route context, and download speed test.", help: "security-hub" },
    "network/sec-tools": { title: "Security packages", text: "Firewall, capture, audit, and hardening apt packages.", help: "security-tools-install" },
    "network/network-packages": { title: "Networking packages", text: "Diagnostics, WiFi, and network apt packages — curl, dig, mtr, nmap, NetworkManager, …", help: "network-tools-install" },
    "network/security-packages": { title: "Security packages", text: "UFW, tcpdump, Lynis, ClamAV, fail2ban, SSHGuard, psad, AIDE, USBGuard, and more.", help: "security-tools-install" },
    "network/alerts": { title: "Alerts (moved)", text: "Smart suggestions are on My presets; connection journal is on Activity log; disconnect watch is under Settings → Browser alerts.", help: "alerts-tier4" },
    "network/alerts/tiers": { title: "Suggested presets", text: "Smart preset suggestions moved to Nord Dashboard → My presets.", help: "alerts-tier4" },
    "network/alerts/disconnect": { title: "Disconnect alerts", text: "Desktop disconnect watch moved to Settings → Browser alerts.", help: "alerts-tier4" },
    "network/leak-tests": { title: "Leak tests", text: "DNS, public IP, resolv.conf, and routing checks on this machine — run after connecting VPN to verify nothing bypasses the tunnel.", help: "network" },
    "security/leak-tests": { title: "Leak tests", text: "DNS, public IP, resolv.conf, and routing checks on this machine — run after connecting VPN to verify nothing bypasses the tunnel.", help: "network" },
    "network/doctors": { title: "Doctors", text: "Health overview, WiFi, network privacy, system checks, and net doctor — NordVPN doctor is on Nord Dashboard → Nord doctor.", help: "troubleshoot" },
    "network/doctors/overview": { title: "Doctor overview", text: "Summary of network health checks — WiFi, network, and system.", help: "troubleshoot" },
    "network/doctors/nordvpn": { title: "NordVPN doctor", text: "Moved to Nord Dashboard → Nord doctor.", help: "troubleshoot" },
    "network/doctors/wifi": { title: "WiFi doctor", text: "NetworkManager profiles, Smart DNS, and resolv.conf checks.", help: "troubleshoot" },
    "network/doctors/privacy": { title: "Network & privacy", text: "IPv6 leak risk and basic internet connectivity.", help: "troubleshoot" },
    "network/doctors/system": { title: "System doctor", text: "Python runtime and sudo privileges for automated fixes.", help: "troubleshoot" },
    "network/doctors/net": { title: "Net doctor", text: "DNS leaks, IPv6, resolv.conf, and Pi-hole conflicts on this PC.", help: "wifi-hub" },
    "network/doctors/health": { title: "Doctor overview", text: "Moved to Doctors → Overview.", help: "troubleshoot" },
    "network/doctor": { title: "Health doctor", text: "Moved to Doctors → Health.", help: "troubleshoot" },
    "network/audit": { title: "Privacy audit", text: "Combined leak tests and network checks with plain-English explanations and one-click fixes where safe.", help: "network" },
    "network/host-ufw": { title: "Linux UFW", text: "Add, remove, and review Linux host firewall rules on this computer — not NordVPN firewall and not your router.", help: "control-tab" },
    "network/listeners": { title: "Listeners", text: "TCP ports listening on this computer — who is bound where, localhost vs LAN.", help: "control-tab" },
    "network/traffic": { title: "Internet traffic", text: "Outbound and inbound internet sessions from this PC — WAN stats, feeds, and connection tables.", help: "traffic" },
    "network/traffic/internet": { title: "Internet traffic", text: "Outbound and inbound internet sessions from this PC — WAN stats, feeds, and connection tables.", help: "traffic" },
    "network/traffic/local": { title: "Local traffic", text: "LAN and Meshnet sessions — connection path, peers, and local listen sockets.", help: "traffic" },
    "network/spectrum-analyzer": { title: "WiFi spectrum", text: "Channel chart across 2.4 / 5 / 6 GHz — band toggles, SSID buttons, and rescan.", help: "wifi-spectrum" },
    "network/bluetooth-spectrum": { title: "Bluetooth spectrum", text: "2.4 GHz ISM activity, BLE channels, nearby devices, and security notes.", help: "wifi-spectrum" },
    "network/services": { title: "Services", text: "nordctl web UI, LAN access, and login autostart. nordvpnd and tray are on Nord Dashboard → Nord services.", help: "services" },
    "network/diagnostics": { title: "Diagnostics", text: "Privacy audit, read-only network tools, and an interactive shell for sudo and installs — use Checks or Shell below.", help: "network" },
    "network/install-tools": { title: "Networking packages", text: "Networking apt packages moved under Networking → Networking packages; security packages under Security → Security packages.", help: "network-tools-install" },
    "network/install-tools/networking": { title: "Networking packages", text: "Diagnostics, WiFi, and network apt packages — curl, dig, mtr, nmap, NetworkManager, …", help: "network-tools-install" },
    "network/install-tools/security": { title: "Security packages", text: "Firewall, capture, audit, and hardening apt packages.", help: "security-tools-install" },
    "network/install-tools/custom": { title: "Custom packages", text: "Your apt packages now live under Tools → Custom packages — one tab per category.", help: "network-tools-install" },
    "network/privileges": { title: "Privileges", text: "One-time sudo setup so buttons can run ufw, apt, and fixes without typing your password each time.", help: "sudo" },
    "network/wifi": { title: "WiFi hub", text: "NetworkManager profiles, trusted zones, and Smart DNS on this computer — not just Nord account settings.", help: "wifi-hub" },
    "network/wifi/profiles": { title: "WiFi profiles", text: "Track profiles in config for zones and self-heal, connect to saved or new networks, and see Smart DNS drift.", help: "wifi-hub" },
    "network/wifi/smart-dns": { title: "WiFi Smart DNS", text: "Moved to Nord Dashboard → Nord DNS.", help: "smartdns" },
    "network/wifi/zones": { title: "WiFi zones", text: "Map trusted SSIDs to Nord preset ids — auto-apply when you join home, work, or café WiFi.", help: "wifi-hub" },
    "network/wifi/scenarios": { title: "WiFi scenarios", text: "Moved to Nord Dashboard → Connect.", help: "wifi-hub" },
    "network/wifi/nearby": { title: "WiFi nearby", text: "Scan and view nearby WiFi networks from NetworkManager.", help: "wifi-hub" },
    "network/wifi/wifi-doctor": { title: "WiFi doctor", text: "Checks NM profiles, Smart DNS drift, and active profile tracking.", help: "wifi-hub" },
    "network/wifi-profiles": { title: "WiFi profiles", text: "Moved to WiFi → Profiles.", help: "wifi-hub" },
    "network/wifi-smart-dns": { title: "WiFi Smart DNS", text: "Moved to WiFi → Smart DNS.", help: "smartdns" },
    "network/wifi-zones": { title: "WiFi zones", text: "Moved to WiFi → Zones.", help: "wifi-hub" },
    "network/wifi-scenarios": { title: "WiFi scenarios", text: "Moved to WiFi → Scenarios.", help: "wifi-hub" },
    "network/wifi-nearby": { title: "WiFi nearby", text: "Moved to WiFi → Nearby.", help: "wifi-hub" },
    "network/wifi-doctor": { title: "WiFi doctor", text: "Moved to WiFi → WiFi doctor.", help: "wifi-hub" },
    "network/wifi-net-doctor": { title: "Net doctor", text: "Moved to Doctors → Net doctor.", help: "wifi-hub" },
    "network/wifi-nord-doctor": { title: "Nord doctor", text: "Moved to Nord Dashboard → Nord doctor.", help: "troubleshoot" },
    "network/wifi/net-doctor": { title: "Net doctor", text: "Moved to Doctors → Net doctor.", help: "wifi-hub" },
    "network/wifi/nord-doctor": { title: "Nord doctor", text: "Moved to Nord Dashboard → Nord doctor.", help: "troubleshoot" },
    "network/diagnostics/shell": { title: "Networking shell", text: "Interactive bash for routes, WiFi, apt networking packages, and tcpdump. Security scans and UFW use <strong>Security shell</strong> below.", help: "terminal-tab" },
    "networking/networking-shell": { title: "Networking shell", text: "Interactive bash for routes, WiFi, apt networking packages, and tcpdump.", help: "terminal-tab" },
    "network/diagnostics/security-shell": { title: "Security shell", text: "Interactive bash for UFW, Lynis, fail2ban, apt security packages, and sudo privileges. NordVPN login is on <strong>Nord Dashboard → Nord shell</strong>.", help: "terminal-tab" },
    "security/security-shell": { title: "Security shell", text: "Interactive bash for UFW, Lynis, fail2ban, apt security packages, and sudo privileges.", help: "terminal-tab" },
    "network/terminal": { title: "Shell", text: "Moved to Diagnostics → Shell.", help: "terminal-tab" },
    "tools/terminal": { title: "Terminal", text: "Moved to <strong>Nord Dashboard → Nord shell</strong>.", help: "terminal-tab" },
    "network/tools": { title: "Tools", text: "Activity log, config editor, rollback, and optional VPN automation.", help: "automate-tab" },
    "network/tools/logs": { title: "Activity log", text: "All nordctl activity — filter by Scans, Packages, Terminal, Audits, VPN, DNS, UFW, and more. Default 10 entries; show up to 100. Expand scans for full Lynis/rkhunter output; export one or all.", help: "logs" },
    "network/tools/auto-guide": { title: "Tools overview", text: "Start here: activity log, editor, and rollback. With NordVPN installed, also schedules, zone watcher, and snapshots.", help: "automate-tab" },
    "network/tools/auto-watcher": { title: "Zone watcher", text: "NordVPN only — background monitor that applies WiFi zone presets when your SSID changes.", help: "wifi-hub" },
    "network/tools/schedules": { title: "Schedules", text: "Run presets at set times — morning connect, evening disconnect, etc.", help: "automate-tab" },
    "network/tools/rollback": { title: "Rollback", text: "Restore the install baseline — config, WiFi DNS, Nord settings, IPv6 — without uninstalling.", help: "baseline" },
    "network/tools/reset": { title: "Factory reset", text: "Full undo of everything nordctl changed since install — heavier than baseline restore.", help: "factory-reset" },
    "network/tools/snapshots": { title: "Nord snapshots", text: "Quick undo for NordVPN settings after a preset — lighter than install baseline.", help: "baseline" },
    "network/tools/editor": { title: "Editor", text: "Edit config.yaml and preset YAML. Revert undoes unsaved edits; Restore from install puts files back to first-run baseline.", help: "editor-tab" },
    "tools/logs": { title: "Activity log", text: "All nordctl activity — filter by Scans, Packages, Terminal, Audits, VPN, DNS, UFW, and more. Default 10 entries; show up to 100. Expand scans for full output; export one or all.", help: "logs" },
    "tools/custom-shell": { title: "Custom shell", text: "Interactive bash with your custom quick-command categories — add categories in Settings → Quick commands.", help: "terminal-tab" },
    "tools/custom-packages": { title: "Custom packages", text: "Your apt packages by category — separate from Networking and Security catalogs.", help: "network-tools-install" },
    "tools/pc-info": { title: "PC info", text: "Full hardware inventory — CPU, RAM, disks, firmware, PCI, USB, sensors, battery, and more. Local machine only; not networking or security.", help: "automate-tab" },
    "tools/auto-watcher": { title: "Zone watcher", text: "Background monitor that applies WiFi zone presets when your SSID changes.", help: "wifi-hub" },
    "tools/schedules": { title: "Schedules", text: "Run presets at set times — morning connect, evening disconnect, etc.", help: "automate-tab" },
    "tools/rollback": { title: "Rollback", text: "Your first-run install baseline — auto-saved on first use — restores config, WiFi DNS, Nord settings, and IPv6 without uninstalling.", help: "baseline" },
    "tools/reset": { title: "Factory reset", text: "Full undo of everything nordctl changed since install — heavier than baseline restore.", help: "factory-reset" },
    "tools/snapshots": { title: "Snapshots", text: "Quick NordVPN settings snapshots saved before presets — lighter undo than baseline.", help: "baseline" },
    "settings/nord/password": { title: "Dashboard password", text: "Optional password when the UI is exposed on LAN — stored locally only.", help: "extra-settings" },
    "settings/nord/services": { title: "UI service", text: "Start, stop, or restart the nordctl web dashboard.", help: "services" },
    "settings/nord/interface": { title: "Interface", text: "Default visibility for page guides and the summary strip — saved in config.yaml for all browsers on this PC.", help: "extra-settings" },
    "settings/general/quick-commands": { title: "Quick commands", text: "Customize shell buttons for Networking, Security, Nord, and custom categories — each category gets Tools → Custom shell.", help: "terminal-tab" },
    "settings/network/notifications": { title: "Browser alerts", text: "Five numbered sections: browser permission, master switch, event rules, background watch, and save/test. Background watch polls VPN, DNS, and health while the UI runs.", help: "alerts-tier4" },
    "settings/network/email": { title: "Email alerts", text: "Your SMTP only — recipient, host, password, and which events send email.", help: "alerts-tier4" },
    "settings/password": { title: "Dashboard password", text: "Optional password when the UI is exposed on LAN — stored locally only.", help: "extra-settings" },
    "settings/notifications": { title: "Browser alerts", text: "Six numbered sections: browser permission, master switch, event rules, background watch, desktop disconnect bubble, and save/test.", help: "alerts-tier4" },
    "settings/email": { title: "Email alerts", text: "Your SMTP only — recipient, host, password, and which events send email.", help: "alerts-tier4" },
    "settings/services": { title: "UI service", text: "Start, stop, or restart the nordctl web dashboard.", help: "services" },
    "tools/editor": { title: "Editor", text: "Edit config.yaml and preset YAML when the guided menus are not enough. Pick a file on the left, edit in the center, Save when done.", help: "editor-tab" },
    help: { title: "Help", text: "Full documentation for every tab — updated as nordctl grows. Use the sidebar to jump to a topic.", help: "navigation" },
  };

  /** Extended bullets when “More detail” is expanded — optional per route; fallback is generated. */
  const PAGE_HOW_DEPTH = {
    "dashboard/connect": [
      "The Connection card reflects live <code>nordvpn status</code> — use <strong>Reconnect</strong> after sleep, router changes, or a stuck tunnel.",
      "Country connect picks from your Nord account; specialty servers (Double VPN, Onion, P2P) need the matching group on Switches or in a preset.",
      "Quick start cards are saved presets — customize them under <strong>My presets</strong> if streaming or travel setups differ at home.",
      "Location scenarios apply a preset plus optional VPN country — set countries under <strong>My places</strong>.",
    ],
    "dashboard/meshnet": [
      "Meshnet gives each device a private <strong>100.x mesh IP</strong> — visible in the top bar when enabled.",
      "Turn Meshnet on here or on <strong>Switches</strong>; link phones and PCs from the NordVPN app on each device first.",
      "<strong>Route via peer</strong> sends traffic through another mesh device (e.g. home PC while traveling) — different from a normal VPN country connect.",
      "Save a default peer hostname under <strong>My places → Meshnet peer</strong> for preset workflows.",
      "See live mesh sessions under <strong>Networking → Local traffic</strong>.",
    ],
    "dashboard/workflows": [
      "<strong>Placeholders</strong> in preset YAML (e.g. <code>{connect_country}</code>) read from My places — save each place before running custom presets.",
      "<strong>Hide</strong> on a card removes it from the list without deleting saved values — restore from the Hidden panel below each section.",
      "Community presets import raw YAML from a URL — review the file before <strong>Run</strong>; treat unknown presets like pasted config.",
      "Use <strong>Save to My presets</strong> on Community, Favorites, or bundled cards to copy them into your presets folder.",
      "Advanced YAML is for power users — most people should use <strong>Create preset</strong> or edit from a My presets card.",
    ],
    "dashboard/create-presets": [
      "Only the preset <strong>name</strong> is required — leave toggles on <strong>Default</strong> to skip them.",
      "Grey rows are blocked by another choice — read the orange note on that row (e.g. OpenVPN UDP/TCP only when Technology is OpenVPN).",
      "Use <strong>Pick country/city in this preset</strong> under Country to choose inline — countries load from NordVPN.",
      "Click <strong>Edit preset</strong> on any of your saved presets below to reload every field in the builder, then <strong>Save changes</strong>.",
      "After saving: <strong>Share</strong>, add to <strong>favorites</strong> (if it connects to one place), open <strong>My presets</strong>, or delete from the green banner.",
    ],
    "dashboard/switches": [
      "With VPN <strong>on</strong>, incompatible switches stay grey — e.g. OpenVPN UDP/TCP only when Technology is OpenVPN.",
      "Still-clickable switches may reconnect or drop VPN — read the yellow warning on the card and the confirm dialog.",
      "Server group cards show <strong>Active</strong> when you are already on that specialty route.",
      "For country + DNS + Meshnet + ports together, use <strong>Create preset</strong> instead of many single toggles.",
    ],
    "dashboard/split-tunnel": [
      "Each <strong>port rule</strong> lets matching TCP/UDP traffic bypass the VPN tunnel while you stay connected — typical for VoIP, messaging, or local web services.",
      "Default <code>voip_ports</code> in config (80, 443, 4244, 5242–5243, 7985) is applied by the <strong>VoIP / messaging friendly</strong> preset — that is why you may see six rules without using Add port.",
      "Subnets allowlist whole LAN ranges; ports allowlist specific services — independent lists in NordVPN.",
      "Remove with <code>nordvpn allowlist remove port …</code> — nordctl cannot remove ports from the UI yet.",
    ],
    "dashboard/wizard": [
      "Green checks mean that step passed — red items block presets until resolved.",
      "Reopen anytime from the top bar <strong>Wizard</strong> button — the page does not pop up on its own.",
      "Optional IPv6 and WiFi tuning live here — skip them if your network already behaves.",
      "For ongoing NordVPN health and <strong>nordvpnd</strong>, use <strong>Nord doctor</strong> and <strong>Nord services</strong> tabs.",
    ],
    "dashboard/nord-doctor": [
      "Read-only checks for NordVPN install, login, <strong>nordvpnd</strong>, settings, Meshnet, DNS, and kill switch.",
      "Checks take a few seconds — <strong>Doctor checking — please wait…</strong> shows while they run.",
      "Required before VPN presets work reliably — fix red items first; install CLI from top bar <strong>Wizard</strong> if missing.",
      "Use <strong>Fix</strong> or <strong>Open Switches</strong> — nothing changes until you act.",
    ],
    "dashboard/nord-services": [
      "Control <strong>nordvpnd</strong> (NordVPN daemon) — start, stop, restart, and enable at boot.",
      "Optional <strong>system tray</strong> for quick VPN / Smart DNS from the taskbar.",
      "The <strong>nordctl web UI</strong> and LAN access stay under <strong>Networking → Services</strong>.",
    ],
    "network/wifi": [
      "Trusted zones map SSIDs to presets — pair with <strong>Zone watcher</strong> (Tools) for automatic switching when you roam.",
      "<strong>Sync profiles</strong> and <strong>Run self-heal</strong> on the hero fix Smart DNS drift after travel.",
      "Profiles must be tracked in config before zones or self-heal can manage them.",
    ],
    "network/host-ufw": [
      "UFW rules apply to <strong>this Linux computer</strong> — not NordVPN's in-app firewall and not your router.",
      "Linux UFW here is separate from NordVPN’s built-in firewall on the Nord Dashboard.",
      "Allow rules need port, protocol, and optional source — use presets for SSH, HTTP, or LAN-only access.",
      "Enable UFW only after you have an allow rule for how you reach this PC (e.g. SSH).",
    ],
    "network/audit": [
      "Full audit combines leak lab checks with read-only network stack review on this machine.",
      "Install missing tools from Networking or Security packages before re-running.",
      "Email report uses your SMTP from Settings — enable master email switch there too.",
    ],
    "network/leak-tests": [
      "<strong>Smart DNS on WiFi</strong> — compares WiFi DNS to your configured streaming DNS pair.",
      "<strong>DNS while VPN connected</strong> — WiFi interface should show Nord DNS (103.86.x), not ISP DNS.",
      "<strong>Public IP</strong> — shows home ISP vs VPN exit; Smart DNS allowlist uses home ISP, not VPN IP.",
      "<strong>resolv.conf</strong> — stub resolver and immutability issues that break DNS through VPN.",
      "<strong>Route to 1.1.1.1</strong> — traffic should go via <code>nordlynx</code> when VPN is connected.",
    ],
    "tools/logs": [
      "Filters group entries by topic — Scans, Packages, Terminal, Audits, VPN, DNS, UFW, WiFi, and more.",
      "<strong>Copy for support</strong> exports plain text — no secrets, but may include paths and IPs.",
      "<strong>Clear log</strong> adds a note only — it does not undo VPN, firewall, or package changes.",
    ],
    "settings/nord/interface": [
      "Defaults here apply to every browser on this PC after save — per-browser Hide/Show overrides until reset.",
      "Page summary strip is the one-line blurb under sub-nav on Networking, Security, and Tools.",
      "<strong>Reset UI cache</strong> clears theme, last tab, and guide visibility in this browser only.",
    ],
    "settings/network/notifications": [
      "Background watch must be running for alerts while this tab is closed — it polls about every 60 seconds.",
      "Desktop disconnect bubble (section 5) uses <code>notify-send</code> — separate from in-app toasts.",
      "Save after changing rules; <strong>Send test alert</strong> confirms bell and email paths.",
    ],
    "network/network/ipv6": [
      "Disabling IPv6 reduces VPN bypass leaks on some networks — local LAN devices may still use IPv6 on other hosts.",
      "Run <strong>Leak tests</strong> before and after changes to confirm traffic stays on the VPN tunnel.",
      "Rollback restores IPv6 sysctl state from your install baseline if you need to undo.",
    ],
  };

  /** Quick cross-links shown under page guides — keyed by route; first link may use primary styling. */
  const PAGE_HOW_RELATED = {
    "dashboard/connect": [
      { route: "dashboard/workflows", label: "My presets", primary: true },
      { route: "network/leak-tests", label: "Leak tests" },
      { route: "dashboard/nord-doctor", label: "Nord doctor" },
    ],
    "dashboard/terminal": [
      { route: "settings/general/quick-commands", label: "Edit quick commands", primary: true },
      { route: "dashboard/wizard", label: "Setup wizard" },
      { route: "network/networking-shell", label: "Networking shell" },
    ],
    "dashboard/workflows": [
      { route: "dashboard/create-presets", label: "Create preset", primary: true },
      { route: "dashboard/workflows/my-places", label: "My places" },
      { route: "tools/schedules", label: "Schedules" },
    ],
    "network/wifi": [
      { route: "network/wifi/zones", label: "Trusted zones", primary: true },
      { route: "dashboard/nord-dns", label: "Nord DNS" },
      { route: "tools/auto-watcher", label: "Zone watcher" },
    ],
    "network/wifi/zones": [
      { route: "tools/auto-watcher", label: "Zone watcher", primary: true },
      { route: "dashboard/workflows", label: "My presets" },
      { route: "tools/rollback", label: "Install baseline" },
    ],
    "network/host-ufw": [
      { route: "network/listeners", label: "Listeners", primary: true },
      { route: "network/security-packages", label: "Security packages" },
      { route: "network/leak-tests", label: "Leak tests" },
      { route: "network/monitoring", label: "Security overview" },
    ],
    "network/listeners": [
      { route: "network/host-ufw", label: "Linux UFW", primary: true },
      { route: "network/diagnostics/security-shell", label: "Security shell" },
      { route: "network/security-packages", label: "Security packages" },
    ],
    "network/audit": [
      { route: "network/leak-tests", label: "Leak tests", primary: true },
      { route: "network/security-packages", label: "Security packages" },
      { route: "network/monitoring", label: "Security overview" },
    ],
    "network/leak-tests": [
      { route: "network/audit", label: "Privacy audit", primary: true },
      { route: "dashboard/nord-dns", label: "Nord DNS" },
      { route: "network/network/ipv6", label: "IPv6 settings" },
    ],
    "network/monitoring": [
      { route: "network/leak-tests", label: "Leak tests", primary: true },
      { route: "network/audit", label: "Privacy audit" },
      { route: "network/host-ufw", label: "Linux UFW" },
    ],
    "network/map-internet": [
      { route: "network/traffic-live", label: "Live bandwidth", primary: true },
      { route: "network/monitoring", label: "Security overview" },
      { route: "network/leak-tests", label: "Leak tests" },
    ],
    "network/traffic-live": [
      { route: "network/map-internet", label: "Traffic map", primary: true },
      { route: "network/traffic-speed", label: "Speed test lab" },
      { route: "dashboard/connect", label: "VPN connect" },
    ],
    "network/network/ipv6": [
      { route: "network/leak-tests", label: "Leak tests", primary: true },
      { route: "network/audit", label: "Privacy audit" },
      { route: "tools/rollback", label: "Install baseline" },
    ],
    "tools/logs": [
      { route: "tools/rollback", label: "Install baseline", primary: true },
      { route: "dashboard/connect", label: "VPN connect" },
      { route: "network/monitoring", label: "Security overview" },
    ],
    "tools/rollback": [
      { route: "tools/snapshots", label: "Nord snapshots", primary: true },
      { route: "tools/reset", label: "Factory reset" },
      { route: "tools/logs", label: "Activity log" },
    ],
    "tools/custom-shell": [
      { route: "settings/general/quick-commands", label: "Edit quick commands", primary: true },
      { route: "tools/custom-packages", label: "Custom packages" },
      { route: "network/networking-shell", label: "Networking shell" },
    ],
    "tools/custom-packages": [
      { route: "network/network-packages", label: "Networking packages", primary: true },
      { route: "network/security-packages", label: "Security packages" },
      { route: "tools/custom-shell", label: "Custom shell" },
    ],
    "tools/auto-guide": [
      { route: "tools/logs", label: "Activity log", primary: true },
      { route: "dashboard/connect", label: "VPN connect" },
      { route: "network/wifi/zones", label: "WiFi zones" },
    ],
  };

  const STATIC_PAGE_HOW_KEYS = {
    workflowsHow: "dashboard/workflows",
    presetBuilderHow: "dashboard/create-presets",
    switchesHow: "dashboard/switches",
  };

  /** Numbered Help boxes — keyed by currentRouteKey(). Static HTML blocks override on Workflows, Create preset, Switches, Automate guide. */
  const PAGE_HOW_TITLES = {
    "dashboard/create-presets": "Help",
  };

  const PAGE_HOW_STEPS = {
    dashboard: [
      "<strong>Connect</strong> — VPN status, country connect, reconnect, and disconnect.",
      "<strong>My presets</strong> — saved places, presets, favorites, and custom workflows.",
      "<strong>Switches</strong> — live Nord toggles one at a time; <strong>Create preset</strong> for multi-step workflows.",
      "Sub-tabs: Connect, Meshnet, My presets, Switches, split tunnel, Nord DNS, Nord shell, Nord doctor, and Nord services. First-run setup: top bar <strong>Wizard</strong>.",
    ],
    "dashboard/connect": [
      "<strong>Connection</strong> (top-left) — VPN status, Reconnect/Disconnect, and country connect.",
      "<strong>Quick start</strong> (top-right) — one-tap presets for streaming, public WiFi, privacy, and reconnect.",
      "<strong>All scenario presets</strong> and <strong>Location scenarios</strong> — click a card to run it.",
      "<strong>Need more?</strong> — build a custom preset or jump to Meshnet, My places, Switches, and Nord doctor.",
    ],
    "dashboard/meshnet": [
      "<strong>Status</strong> — turn Meshnet on, see mesh IP, LAN discovery, and routing at a glance.",
      "<strong>Linked devices</strong> — peers you invited in the NordVPN app; route through one with a single click.",
      "<strong>Route through a peer</strong> — type a <code>.nord</code> hostname or use a saved My places peer.",
      "Live mesh traffic is under <strong>Networking → Local traffic</strong>.",
    ],
    "dashboard/wizard": [
      "Inline setup page — install NordVPN, health checklist on the left, wizard steps on the right.",
      "Open from the top bar <strong>Wizard</strong> button or <code>#dashboard/wizard</code> — it does not auto-open on every visit.",
      "<strong>Quick setup</strong> runs only unfinished checklist items; <strong>All wizard steps</strong> walks every page.",
      "NordVPN health and <strong>nordvpnd</strong> control live on <strong>Nord doctor</strong> and <strong>Nord services</strong> sub-tabs.",
    ],
    "dashboard/split-tunnel": [
      "The <strong>Port rules</strong> count is what NordVPN stores today — often from a VoIP preset, not from an empty Add port box.",
      "Set your <strong>Home LAN range</strong> so printers and NAS stay reachable while VPN and LAN split tunnel are on.",
      "Add extra <strong>subnets</strong> and <strong>ports</strong> below — or remove rules with <code>nordvpn allowlist remove</code> in a terminal.",
      "Turn <strong>LAN split tunnel</strong> on or off on <strong>Switches</strong>; press <strong>Apply to Nord</strong> after saving Home LAN here.",
    ],
    "dashboard/nord-dns": [
      "<strong>Nord DNS</strong> is a NordVPN app setting (while VPN is on) — separate from VPN “connected” in the top bar.",
      "<strong>Smart DNS on WiFi</strong> changes DNS on this computer's saved Wi‑Fi profiles via NetworkManager — not your TV/router unless configured there too. Disconnect VPN before turning it on.",
      "Edit Smart DNS IPs below, save, then use the toggles — status badges show what is actually on this PC now.",
      "<strong>Install baseline</strong> (Tools → Rollback) is auto-saved on first use — revert config and Wi‑Fi DNS if something goes wrong.",
    ],
    "dashboard/connection-details": [
      "Shows the full chain: this PC → Wi‑Fi → router → ISP → VPN (any provider).",
      "MAC addresses, tunnel interfaces, and NordVPN status/settings when Nord is connected.",
      "Home ISP comes from LAN probe or cache — not the VPN exit shown on default-route checks.",
      "Press <strong>Refresh details</strong> after changing VPN or network.",
    ],
    "tools/terminal": [
      "NordVPN commands moved to <strong>Nord Dashboard → Nord shell</strong>.",
    ],
    "dashboard/terminal": [
      "<strong>Nord shell</strong> — full <strong>NordVPN quick commands</strong> for login, connect, settings, presets, and doctor checks.",
      "Customize every button in <strong>Settings → Quick commands → Nord shell (Dashboard)</strong> — add, rename, disable, or remove commands, then save.",
      "Click the black area to type; quick-command buttons open their own tabs.",
      "For sudo, apt, and UFW use <strong>Networking → Diagnostics → Shell</strong> (Networking or Security).",
    ],
    "dashboard/nord-doctor": [
      "Read-only NordVPN checks — install, login, <strong>nordvpnd</strong>, settings, Meshnet, DNS, and kill switch.",
      "Checks take a few seconds — <strong>Re-run checks</strong> after you fix something.",
      "Install NordVPN from top bar <strong>Wizard</strong> if the CLI is missing.",
      "Use <strong>Fix</strong> or <strong>Open Switches</strong> — nothing changes until you act.",
    ],
    "dashboard/nord-services": [
      "Control <strong>nordvpnd</strong> — start, stop, restart, and enable at boot.",
      "Optional <strong>system tray</strong> for quick VPN / Smart DNS from the taskbar.",
      "The <strong>nordctl web UI</strong> service stays under <strong>Networking → Services</strong>.",
    ],
    networking: [
      "<strong>WiFi</strong> — profiles, zones, Smart DNS drift, and nearby networks.",
      "<strong>Traffic</strong> — internet map, local LAN map, live bandwidth, WiFi spectrum, and Bluetooth spectrum.",
      "<strong>Routes &amp; DNS</strong> — read-only network stack; <strong>Diagnostics</strong> for shell and apt tools.",
      "Pick a tab in the sub-nav below — each page has numbered steps explaining what it does.",
    ],
    security: [
      "<strong>Overview</strong> — combined health score from VPN, leak tests, audit, and traffic.",
      "<strong>Doctors &amp; leak lab</strong> — targeted checks; <strong>Audit</strong> runs a full privacy review.",
      "<strong>Linux UFW</strong> — host firewall rules; <strong>Packages</strong> — UFW, Lynis, fail2ban, and hardening apt tools.",
      "Pick a tab below — use <strong>Hide guides</strong> in the top bar if you already know the layout.",
    ],
    "network/map-internet": [
      "Live map of <strong>outbound and inbound internet sessions</strong> from this PC — which apps talk where.",
      "Shows VPN tunnel vs direct route; refresh or turn on <strong>live update</strong> while you browse.",
      "“Direct” often means split tunnel or LAN — compare with <strong>Security → Overview</strong> health score.",
    ],
    "network/map-local": [
      "<strong>Local LAN and Meshnet traffic</strong> — peers, connection paths, and listen sockets on this machine.",
      "Useful for finding which device or app is on your home network; not a full IDS.",
      "Meshnet peers also appear here when Meshnet is enabled on Nord Dashboard → Switches.",
    ],
    "network/traffic-live": [
      "Real-time <strong>download and upload</strong> per network interface with a history graph.",
      "VPN tunnel interface is highlighted — compare with your physical Wi‑Fi or Ethernet adapter.",
      "Open <strong>Speed test</strong> tab for download benchmarks and VPN vs direct comparison.",
    ],
    "network/traffic-speed": [
      "Download speed lab — tune file size, CDN mirror, and 3-run averaging for stable results.",
      "Route and <strong>DNS</strong> show at the top — run once with VPN on, once off, to compare overhead.",
      "Results save in this browser with charts; export or clear history anytime.",
    ],
    "network/spectrum-analyzer": [
      "<strong>WiFi spectrum</strong> — channel occupancy and signal strength across 2.4 / 5 / 6 GHz bands.",
      "Toggle <strong>band switches</strong> above the chart; use <strong>SSID buttons</strong> or table rows to centre on a network.",
      "Dual-band SSIDs (e.g. <code>Name</code> + <code>Name_5G</code>) share one button when grouped.",
      "<strong>Rescan WiFi</strong> refreshes scan data — restarts NetworkManager when needed for full 2.4 GHz visibility.",
    ],
    "network/bluetooth-spectrum": [
      "<strong>Bluetooth spectrum</strong> — 2.4 GHz ISM activity shared with WiFi; BLE channel occupancy and nearby devices.",
      "Review <strong>security findings</strong> — discoverable mode, trusted connections, and legacy pairing.",
      "<strong>Scan nearby</strong> runs a fresh bluetoothctl discovery pass; live mode refreshes every few seconds.",
      "Connected and paired devices are listed with RSSI, trust state, and pairing security notes.",
    ],
    "network/doctors": [
      "Pick a doctor sub-tab — <strong>Overview</strong> summarizes; others drill into WiFi, privacy, system, or net checks.",
      "NordVPN install and login checks live on <strong>Nord Dashboard → Nord doctor</strong>, not under Doctors.",
      "Re-run after VPN connect/disconnect or router changes; Fix buttons appear where automation is safe.",
    ],
    "network/network": [
      "Sub-tabs: <strong>Live bandwidth</strong>, speed test, DNS assistant, IPv6, and read-only configuration.",
      "Most checks are read-only — apply fixes from WiFi, Doctors, or Diagnostics shell.",
      "DNS conflicts with Pi-hole or Unbound show under <strong>DNS assistant</strong>.",
    ],
    "dashboard/workflows": [
      "<strong>My places</strong> — save countries, DNS, and placeholders once for custom presets.",
      "<strong>My presets</strong> — one-click workflows; Run, edit, hide, or delete from each card.",
      "<strong>Create preset</strong> tab — step-by-step wizard; <strong>Favorites</strong> — star countries for quick connect.",
    ],
    "tools/logs": [
      "<strong>Activity log</strong> — everything nordctl did on this PC (default 10 entries, up to 100).",
      "Filter by Scans for Lynis, rkhunter, and shell scan output — expand any row for full text.",
      "<strong>Export</strong> one entry or all; <strong>Copy for support</strong> for clipboard.",
    ],
    "tools/custom-shell": [
      "Each category from <strong>Tools → Custom packages</strong> or <strong>Settings → Quick commands</strong> gets its own shell tab here.",
      "Built-in shells are <strong>text-only</strong> — simple CLI tools work; full-screen or graphical programs (e.g. <code>mc</code>, games) may not display correctly. Use your own Linux terminal for those.",
      "Add or edit extra buttons in <strong>Settings → Quick commands → Custom categories</strong>.",
    ],
    "tools/custom-packages": [
      "Your apt packages — separate from Networking and Security <strong>recommended</strong> catalogs.",
      "Each category tab (e.g. <strong>Miscellaneous</strong>) holds packages you added — create new tabs with <strong>Create category tab</strong>.",
      "Custom categories can be deleted with <strong>Delete category</strong> — that removes the tab and all package entries in it (apt packages stay installed).",
      "Install here; run installed packages from <strong>Tools → Custom shell</strong>. Shells are text-only — graphical apps belong in your own Linux terminal.",
    ],
    "settings/general/quick-commands": [
      "Pick a tab — <strong>Networking shell</strong>, <strong>Security shell</strong>, <strong>Nord shell (Dashboard)</strong>, or <strong>Custom categories</strong>.",
      "Toggle <strong>On</strong>, edit label and command text, or press <strong>Add command</strong> (footer or inline) to add more buttons.",
      "Add a <strong>custom category</strong> for your own scripts — each category opens under <strong>Tools → Custom shell</strong>.",
      "Press <strong>Save quick commands</strong> — stored in <code>config.yaml</code>. <strong>Reset list</strong> restores built-in defaults for the selected scope.",
    ],
    "tools/auto-guide": [
      "<strong>Start here</strong> — jump cards for Activity log, Editor, Rollback, and (with NordVPN) Schedules and zone watcher.",
      "This tab is <em>not</em> Networking or Security — those pills cover WiFi, diagnostics, UFW, and apt packages.",
      "Custom quick-command categories live under <strong>Custom shell</strong> — configure them in Settings → Quick commands.",
    ],
    "tools/auto-watcher": [
      "<strong>Zone watcher</strong> — background task that applies a WiFi zone preset when your SSID changes.",
      "Requires NordVPN and zones configured under <strong>Networking → WiFi → Zones</strong>.",
      "Enable/disable here; undo preset side-effects from <strong>Rollback</strong> if needed.",
    ],
    "tools/schedules": [
      "Run saved presets at set times — morning connect, evening disconnect, custom cron-style entries.",
      "Test the preset manually from <strong>My presets</strong> before scheduling.",
      "Schedules use the system timer — they run even when this browser tab is closed.",
    ],
    "tools/rollback": [
      "<strong>Install baseline</strong> — auto-saved on first nordctl use (or <code>nordctl init</code>) as a full backup before changes.",
      "Restores config, this PC's Wi‑Fi DNS (NetworkManager), Nord settings, and IPv6 — open this tab and click <strong>Restore install baseline</strong>.",
      "Lighter than Factory reset — keeps logs and services. Nord snapshots only undo one preset's Nord settings.",
    ],
    "tools/reset": [
      "<strong>Factory reset</strong> — undo everything nordctl changed since install (services, timers, logs, snapshots).",
      "Shows the welcome screen again; does <em>not</em> uninstall NordVPN — use your OS package manager for that.",
      "Use <strong>Rollback</strong> first if you only want config and DNS back to first-run state.",
    ],
    "tools/snapshots": [
      "<strong>NordVPN settings snapshots</strong> — kill switch, Meshnet, DNS, technology, autoconnect, etc.",
      "Auto-saved before presets when enabled; up to 10 files in <code>~/.config/nordctl/snapshots/</code>.",
      "<strong>Restore latest</strong> undoes one preset’s Nord changes — use Rollback for WiFi DNS or full config.",
    ],
    "tools/editor": [
      "Edit <code>config.yaml</code> and preset YAML when guided menus are not enough.",
      "Pick a file on the left; <strong>Save</strong> writes to disk; <strong>Revert</strong> drops unsaved edits.",
      "<strong>Restore from install</strong> puts the selected file back to first-run baseline.",
    ],
    network: [
      "<strong>Monitoring</strong> — health score, bandwidth, leak tests, and traffic.",
      "<strong>WiFi</strong> — profiles, Smart DNS, zones, and scenarios.",
      "<strong>Doctors &amp; Diagnostics</strong> — health checks and read-only network tools.",
      "Pick a tab in the sub-nav below — each page has its own how-to steps.",
    ],
    "network/monitoring": [
      "<strong>Security hub</strong> — one score from VPN, leak lab, audit, and live traffic.",
      "“Direct internet traffic” often means split tunnel or local apps — not always a leak.",
      "Open sub-tabs under <strong>Network</strong> for bandwidth, DNS, and configuration detail.",
    ],
    "network/network/bandwidth": [
      "Live <strong>download and upload</strong> per network interface — VPN tunnel highlighted.",
      "Use <strong>Refresh</strong> or enable live update while copying a file or streaming.",
      "Compare VPN vs physical interface to see what carries your traffic.",
    ],
    "network/network/speed": [
      "Simple <strong>download speed test</strong> through your current route (VPN if connected).",
      "Run twice — once disconnected and once connected — to compare overhead.",
      "Not a full ISP audit; good enough for quick before/after checks.",
    ],
    "network/network/dns": [
      "<strong>DNS assistant</strong> — detects Pi-hole, Unbound, and systemd-resolved conflicts with Nord DNS.",
      "Read-only — fix conflicts from Doctors or by adjusting local DNS services.",
      "After changes, re-check on <strong>Doctors → Net doctor</strong>.",
    ],
    "network/network/ipv6": [
      "Changes <strong>IPv6 on this computer</strong> — not your Nord account or router by themselves.",
      "Balance <strong>local device IPv6</strong> vs <strong>internet leak</strong> risk on this PC.",
      "Disabling IPv6 reduces bypass leaks; some LAN devices may need IPv6 left on.",
      "Confirm dialogs explain each action — sudo may be required.",
    ],
    "network/network/config": [
      "Read-only snapshot: routes, interfaces, DNS, NetworkManager, and active sockets.",
      "Run <strong>quick commands</strong> and security scans (Lynis, rkhunter, chkrootkit) from here.",
      "Commands marked <strong>sudo</strong> open Shell and prompt for your password when needed.",
    ],
    "network/alerts/tiers": [
      "<strong>Suggested presets</strong> from doctor and WiFi checks — now at <strong>Nord Dashboard → My presets</strong>.",
      "Connection history is on <strong>Tools → Activity log</strong> (Connection journal section).",
    ],
    "network/alerts/disconnect": [
      "<strong>Desktop disconnect watch</strong> — moved to <strong>Settings → Browser alerts</strong> (section 5).",
      "Uses <code>notify-send</code> when VPN drops — separate from background watch rules above it.",
    ],
    "network/leak-tests": [
      "Press <strong>Run leak tests</strong> — local checks in a few seconds (no sudo).",
      "Connect VPN first for meaningful DNS and routing results; disconnected runs still check resolv.conf and public IP.",
      "Each result card explains what was checked and links to the tab that fixes failures.",
      "For IPv6, Pi-hole, and broader review, use <strong>Privacy audit</strong> (Full audit tab above).",
    ],
    "network/doctors/overview": [
      "Summary of <strong>all health checks</strong> — NordVPN, WiFi, network privacy, and system.",
      "Open a sub-tab to drill into one area; Fix buttons appear where automation is safe.",
      "Re-run after network changes or VPN connect/disconnect.",
    ],
    "network/doctors/nordvpn": [
      "Checks <strong>NordVPN install</strong>, login, <strong>nordvpnd</strong>, settings, Meshnet, DNS, firewall, and kill switch.",
      "Checks take a few seconds — <strong>Doctor checking — please wait…</strong> shows while they run.",
      "Required before VPN presets will work — fix red items first.",
      "Nord Dashboard <strong>Setup</strong> tab covers install if CLI is missing; <strong>Nord doctor</strong> has full health checks.",
    ],
    "network/doctors/wifi": [
      "NetworkManager profiles, Smart DNS drift, and resolv.conf checks.",
      "Use with <strong>WiFi → Profiles</strong> and <strong>Smart DNS</strong> tabs to apply fixes.",
      "<strong>Run self-heal</strong> on the WiFi hub hero refreshes active profile DNS.",
    ],
    "network/doctors/privacy": [
      "<strong>IPv6 leak risk</strong> and basic internet connectivity on this PC.",
      "Complements <strong>Leak tests</strong> — run both after connecting VPN.",
      "IPv6 disable is under Setup or Network → IPv6 if you need a stronger fix.",
    ],
    "network/doctors/system": [
      "Python runtime and <strong>sudo</strong> privileges for automated fixes.",
      "Run <strong>Privileges</strong> setup once so buttons work without repeated passwords.",
      "Red items here block WiFi heal, UFW, and preset apply actions.",
    ],
    "network/doctors/net": [
      "DNS leaks, IPv6, resolv.conf, and Pi-hole conflicts on this PC.",
      "Read-only diagnosis — apply DNS or firewall changes from WiFi or UFW tabs.",
      "Re-test from <strong>Audit</strong> or <strong>Leak tests</strong> after fixing DNS.",
    ],
    "network/audit": [
      "<strong>Run full audit</strong> — combines leak lab and network stack checks.",
      "Check <strong>Tools required</strong> — install curl, iproute2, and ping from Networking packages if missing.",
      "Tick <strong>Email me the report</strong> to get a plain-text summary via your SMTP — or use Set up email first.",
    ],
    "network/diagnostics": [
      "<strong>Checks</strong> pane — privacy audit plus read-only ping, routes, IP, and DNS tools.",
      "<strong>Shell</strong> pane — pick <strong>Networking</strong> or <strong>Security</strong> for scoped quick commands (same bash engine, separate tabs).",
      "NordVPN login stays on <strong>Nord Dashboard → Nord shell</strong>.",
    ],
    "network/diagnostics/shell": [
      "<strong>Networking shell</strong> — routes, WiFi, apt networking tools, tcpdump.",
      "Quick commands open their own tab; <strong>sudo</strong> shows a password box when needed.",
      "Customize buttons in <strong>Settings → Quick commands</strong>; custom categories use <strong>Tools → Custom shell</strong>.",
    ],
    "network/diagnostics/security-shell": [
      "<strong>Security shell</strong> — UFW, Lynis, fail2ban, chkrootkit, apt security tools, and privileges.",
      "Quick commands open their own tab; <strong>sudo</strong> shows a password box when needed.",
      "Customize buttons in <strong>Settings → Quick commands</strong>; custom categories use <strong>Tools → Custom shell</strong>.",
    ],
    "network/host-ufw": [
      "Linux <strong>UFW host firewall</strong> — separate from NordVPN firewall on the Nord Dashboard.",
      "Add allow rules by port, protocol, and optional source IP; use presets for common services.",
      "Enable/disable UFW here — sudo required unless Privileges setup is done.",
    ],
    "network/listeners": [
      "TCP sockets in <strong>LISTEN</strong> state on this computer — from <code>ss -tlnp</code> plus <code>/proc</code> when readable.",
      "<strong>LAN</strong> means bound on all interfaces (<code>0.0.0.0</code> or <code>::</code>) — review with <strong>Linux UFW</strong> if unexpected.",
      "Blank process names often need <code>sudo ss -tulpn</code> in Security shell or Privileges setup.",
    ],
    "network/traffic": [
      "Live map of which apps connect where — VPN vs direct vs local, without capture files.",
      "Refresh or turn on <strong>live update</strong> while you browse to see new connections.",
      "“Direct” often means split tunnel or LAN — compare with Monitoring health score.",
    ],
    "network/services": [
      "Control <strong>nordvpnd</strong>, <strong>nordctl UI</strong>, optional <strong>tray</strong>, and LAN access.",
      "Enable <strong>autostart</strong> so services survive reboot without manual <code>nordctl serve</code>.",
      "Changing LAN access restarts the UI — bookmark your URL first.",
    ],
    "network/install-tools": [
      "Moved to <strong>Networking → Networking packages</strong> and <strong>Security → Security packages</strong>.",
      "Old bookmark paths still open the right page — links now use the canonical tab URLs.",
      "Install/remove needs sudo — opens Shell when passwordless sudo is not configured.",
    ],
    "network/network-packages": [
      "Opens on <strong>Recommended packages</strong> — curl, dig, mtr, nmap, NetworkManager, and the rest of the catalog.",
      "Each card shows what the package is for, install status, and one-click install when sudo allows.",
      "Your own apt packages live under <strong>Tools → Custom packages</strong> — not mixed with this catalog.",
      "Use filters for <strong>Not installed</strong> or batch-select packages for a single apt run.",
    ],
    "network/security-packages": [
      "Opens on <strong>Recommended packages</strong> — UFW, tcpdump, Lynis, ClamAV, fail2ban, and the rest of the catalog.",
      "Firewall, capture, audit, and hardening packages — same install UX as Networking packages.",
      "Your own apt packages live under <strong>Tools → Custom packages</strong> — one tab per category you create.",
      "Install UFW before using <strong>Linux UFW</strong>; Lynis/rkhunter output can email from Settings.",
    ],
    "network/install-tools/networking": [
      "Redirected to <strong>Networking → Networking packages</strong>.",
      "Filter <strong>All</strong>, <strong>Not installed</strong>, or <strong>Installed</strong> — batch install or remove.",
      "After install, the result box shows where to run each tool (Diagnostics, Shell, WiFi, …).",
    ],
    "network/install-tools/security": [
      "Redirected to <strong>Security → Security packages</strong>.",
      "Same batch install/uninstall as Networking packages.",
      "UFW and tcpdump link to their dedicated tabs after install.",
    ],
    "network/install-tools/custom": [
      "Redirected to <strong>Tools → Custom packages</strong>.",
      "Each category you create gets its own tab — Miscellaneous is the default.",
      "Add packages with the form at the bottom of each category tab.",
    ],
    "network/privileges": [
      "One-time <strong>sudo</strong> setup for nordctl — UFW, IPv6, resolv.conf, and preset apply.",
      "Not full passwordless sudo — only specific nordctl commands are allowed.",
      "Run the shown command in a real terminal if the copy button is not enough.",
    ],
    "network/wifi": [
      "<strong>WiFi hub</strong> — changes NetworkManager profiles and DNS on this computer, not just Nord online.",
      "Sub-tabs: <strong>Profiles</strong>, <strong>Smart DNS</strong>, <strong>Zones</strong>, <strong>Scenarios</strong>, <strong>Nearby</strong>, <strong>WiFi doctor</strong>.",
      "<strong>Sync profiles</strong> and <strong>Run self-heal</strong> fix drift after travel or router changes.",
    ],
    "network/wifi/profiles": [
      "Lists NetworkManager WiFi profiles on this PC — <strong>Add to config</strong> only for networks nordctl should manage.",
      "<strong>Connect</strong> joins saved or new networks on this machine; <strong>Delete profile</strong> removes from NetworkManager.",
      "Smart DNS and zone automation require profiles tracked in config.",
    ],
    "network/wifi/smart-dns": [
      "Apply Nord <strong>streaming DNS</strong> to this PC's Wi‑Fi connection profiles (NetworkManager) — not your Nord account page alone; no VPN tunnel for streaming apps.",
      "Edit primary/secondary IPs, save, then <strong>Apply Smart DNS</strong> or <strong>Restore auto DNS</strong>.",
      "Self-healing below keeps DNS aligned when you roam between networks on this laptop.",
    ],
    "network/wifi/zones": [
      "Map <strong>trusted SSIDs</strong> to presets — auto-apply when you join home, work, or café WiFi.",
      "Enable <strong>zone watcher</strong> on Automate or WiFi Smart DNS tab for background switching.",
      "Schedules and undo live under <strong>Tools → Schedules / Rollback</strong>.",
    ],
    "network/wifi/scenarios": [
      "One-click <strong>WiFi workflows</strong> — streaming, public WiFi, travel, gaming, and restore.",
      "Each scenario runs a preset tuned for that situation — read the card before running.",
      "Customize presets under <strong>Create preset</strong> on the Nord Dashboard.",
    ],
    "network/wifi/nearby": [
      "Scan and view <strong>nearby WiFi networks</strong> from NetworkManager.",
      "Useful before joining a new SSID — then add it on the Profiles tab.",
      "<strong>Rescan</strong> on the WiFi hero refreshes the list.",
    ],
    "network/wifi/wifi-doctor": [
      "Checks NM profiles, Smart DNS drift, and which profile nordctl tracks as active.",
      "Run after changing routers or when streaming DNS stops working on WiFi.",
      "Fix issues from Profiles or Smart DNS tabs — doctor shows what is wrong.",
    ],
    "network/tools/logs": [
      "<strong>Activity log</strong> — default 10 entries; use the number box to show up to 100.",
      "Security scans (Lynis, rkhunter, chkrootkit) appear under <strong>Scans</strong> — expand for full output, or <strong>Export</strong> one entry or all.",
      "<strong>Copy for support</strong> for clipboard; <strong>Clear log</strong> adds a note — does not undo system changes.",
    ],
    "network/tools/auto-guide": [
      "<strong>Overview</strong> — pick a card to jump to Activity log, Editor, Rollback, or (with Nord) Schedules.",
      "This is not Networking or Security — use those top pills for WiFi, diagnostics, UFW, and apt packages.",
      "Everyday VPN connect uses <strong>Nord Dashboard → Connect</strong>, not Tools.",
    ],
    "network/tools/auto-watcher": [
      "<strong>NordVPN only</strong> — zone watcher applies WiFi zone presets when your SSID changes.",
      "Without Nord, use <strong>WiFi → Zones</strong> to manage trusted networks only.",
      "Enable Nord under Optional extras or install NordVPN from Setup.",
    ],
    "network/tools/schedules": [
      "Run presets at set times — morning connect, evening disconnect, and custom cron-style entries.",
      "Requires nordctl schedule timer — enabled when you add a schedule.",
      "Test the preset manually from <strong>My presets</strong> before scheduling.",
    ],
    "network/tools/rollback": [
      "<strong>Install baseline</strong> — auto-saved on first nordctl use as a full backup of settings on this computer.",
      "Restores config, this PC's Wi‑Fi DNS (NetworkManager), Nord settings, and IPv6 — click <strong>Restore install baseline</strong> on this tab.",
      "Lighter than Factory reset — keeps logs and services. Nord snapshots only undo one preset's Nord settings.",
    ],
    "network/tools/reset": [
      "<strong>Factory reset</strong> — undo everything nordctl changed since install.",
      "Removes UI/tray services, timers, logs, and snapshots; shows welcome again.",
      "Does <em>not</em> uninstall NordVPN — use OS package manager for that.",
    ],
    "network/tools/snapshots": [
      "<strong>NordVPN settings only</strong> — kill switch, Meshnet, DNS, technology, autoconnect, etc. (from <code>nordvpn settings</code>).",
      "Auto-saved before each preset when <code>auto_snapshot_before_preset</code> is on; up to 10 files in <code>~/.config/nordctl/snapshots/</code>.",
      "<strong>Restore latest snapshot</strong> — undo one preset’s Nord changes. For WiFi DNS or full config undo, use <strong>Rollback → Install baseline</strong>.",
    ],
    "network/tools/editor": [
      "Edit <code>config.yaml</code> and preset YAML when guided menus are not enough.",
      "Pick a file on the left; <strong>Save</strong> writes to disk; <strong>Revert</strong> drops unsaved edits.",
      "<strong>Restore from install</strong> puts the file back to first-run baseline.",
    ],
    settings: [
      "<strong>Nord</strong> scope — dashboard password and UI service.",
      "<strong>Network</strong> scope — browser and email alerts for VPN, WiFi, and health events.",
      "Switch scope with the tabs below — each section has its own steps.",
    ],
    "settings/nord/password": [
      "Optional <strong>dashboard password</strong> when the UI listens on LAN, not just localhost.",
      "Stored locally only — nordctl never sends it off this machine.",
      "Remove password to go back to open access on trusted networks.",
    ],
    "settings/nord/services": [
      "Start, stop, or restart the <strong>nordctl web UI</strong> service.",
      "Use after config changes to bind address or port.",
      "Full service control (nordvpnd, tray) is under <strong>Networking → Services</strong>.",
    ],
    "settings/nord/interface": [
      "<strong>Page guides</strong> — default show or hide for numbered <strong>Help</strong> boxes on every tab.",
      "<strong>Summary strip</strong> — title and one-line blurb under the sub-nav on Networking, Security, and Tools.",
      "<strong>This browser only</strong> — theme, last-open tab, and quick Hide guides (Reset UI cache clears them).",
      "Press <strong>Save interface settings</strong> — writes to <code>config.yaml</code> for all browsers on this PC.",
    ],
    "settings/network/notifications": [
      "<strong>Section 1</strong> — optional browser permission for desktop pop-ups (toasts work without it).",
      "<strong>Section 2–3</strong> — master switch and which events (VPN drop, DNS drift, health score, …) can alert.",
      "<strong>Section 4 — Background watch</strong> — must be running for alerts while the tab is closed; polls every ~60s.",
      "Save after changing rules; <strong>Send test alert</strong> confirms bell and email. Not the same as Network → Disconnect desktop bubble.",
    ],
    "settings/network/email": [
      "<strong>Email alerts</strong> via your own SMTP — nordctl never sends through its servers.",
      "Fill host, user, password, and recipient — use an app password if your provider requires it.",
      "<strong>Scan results</strong> box emails Lynis, rkhunter, chkrootkit summaries after Diagnostics runs.",
      "VPN drop and health alerts follow rules on the Browser alerts tab — enable email master switch here too.",
    ],
    help: [
      "Full nordctl documentation — every tab, button, and troubleshooting path.",
      "Use the sidebar to jump topics; hover UI buttons elsewhere for quick tooltips.",
      "Updated with your installed nordctl version — no account required.",
    ],
  };

  function pageHowTitleForKey(key) {
    return PAGE_HOW_TITLES[key] || "Help";
  }

  function pageHowLookupKeys(key) {
    const keys = [key];
    if (key.startsWith("networking/")) keys.push(key.replace(/^networking\//, "network/"));
    if (key.startsWith("security/")) keys.push(key.replace(/^security\//, "network/"));
    if (key.startsWith("tools/")) keys.push(key.replace(/^tools\//, "network/tools/"));
    if (key === "networking") keys.push("network/networking");
    if (key === "security") keys.push("network/security");
    return keys;
  }

  function createPageHowHideBtn() {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn sm page-how-hide-btn";
    btn.textContent = "Hide all";
    btn.title = "Hide page guides on all tabs — use Show guides in the top bar or the banner below to bring them back";
    return btn;
  }

  function isPageHowHidden() {
    if (localStorage.getItem(PAGE_HOW_USER_SET_KEY) === "1") {
      return localStorage.getItem(PAGE_HOW_HIDDEN_KEY) === "1";
    }
    return uiPrefs.page_guides_visible_default === false;
  }

  function setPageHowHidden(hidden, opts = {}) {
    if (opts.userAction) localStorage.setItem(PAGE_HOW_USER_SET_KEY, "1");
    if (hidden) localStorage.setItem(PAGE_HOW_HIDDEN_KEY, "1");
    else localStorage.removeItem(PAGE_HOW_HIDDEN_KEY);
    applyPageHowVisibility();
  }

  function applyUiPrefsFromConfig(prefs) {
    if (!prefs || typeof prefs !== "object") return;
    uiPrefs.page_guides_visible_default = prefs.page_guides_visible_default !== false;
    uiPrefs.page_intro_visible = prefs.page_intro_visible !== false;
    uiPrefs.clock_format = prefs.clock_format === "12h" ? "12h" : "24h";
    if (localStorage.getItem(PAGE_HOW_USER_SET_KEY) !== "1") {
      if (uiPrefs.page_guides_visible_default) localStorage.removeItem(PAGE_HOW_HIDDEN_KEY);
      else localStorage.setItem(PAGE_HOW_HIDDEN_KEY, "1");
    }
    applyPageHowVisibility();
    syncPageIntro();
    tickTopbarClock();
  }

  function renderSettingsInterfacePanel(prefs) {
    const show = prefs?.page_guides_visible_default !== false;
    $("settingsPageGuidesShow") && ($("settingsPageGuidesShow").checked = show);
    $("settingsPageGuidesHide") && ($("settingsPageGuidesHide").checked = !show);
    if ($("settingsPageIntroVisible")) {
      $("settingsPageIntroVisible").checked = prefs?.page_intro_visible !== false;
    }
    const h24 = (prefs?.clock_format || "24h") === "24h";
    $("settingsClock24") && ($("settingsClock24").checked = h24);
    $("settingsClock12") && ($("settingsClock12").checked = !h24);
  }

  function togglePageHowVisibility() {
    setPageHowHidden(!isPageHowHidden(), { userAction: true });
  }

  function syncPageHowRestoreControls() {
    const hidden = isPageHowHidden();
    $("pageHowRestoreBar")?.classList.toggle("hidden", !hidden);
    $("btnSettingsShowPageGuides")?.classList.toggle("hidden", !hidden);
    $("btnSettingsHidePageGuides")?.classList.toggle("hidden", hidden);
  }

  function applyPageHowVisibility() {
    const hidden = isPageHowHidden();
    document.documentElement.classList.toggle("page-how-suppressed", hidden);
    const btn = $("btnTogglePageHow");
    if (btn) {
      btn.textContent = hidden ? "Show guides" : "Hide guides";
      btn.title = hidden
        ? "Show numbered Help boxes on every tab"
        : "Hide numbered Help boxes on every tab";
      btn.setAttribute("aria-pressed", hidden ? "true" : "false");
      btn.classList.toggle("primary", hidden);
    }
    syncPageHowRestoreControls();
  }

  function pageHowHelpIdForKey(key) {
    return tabIntroForRouteKey(key)?.help || "navigation";
  }

  function pageHowDepthBulletsForKey(key) {
    for (const k of pageHowLookupKeys(key)) {
      if (PAGE_HOW_DEPTH[k]) return PAGE_HOW_DEPTH[k];
    }
    const bullets = [];
    const intro = tabIntroForRouteKey(key);
    let allSteps = [];
    for (const k of pageHowLookupKeys(key)) {
      if (PAGE_HOW_STEPS[k]) {
        allSteps = PAGE_HOW_STEPS[k];
        break;
      }
    }
    const summary = pageHowStepsForKey(key);
    if (allSteps.length > summary.length) {
      bullets.push(...allSteps.slice(summary.length));
    }
    if (intro?.text && bullets.length < 3) {
      bullets.unshift(intro.text);
    }
    if (!bullets.length) {
      bullets.push(
        "Confirm dialogs explain risky actions before anything runs on this PC.",
        "Stale badges or empty panels usually clear after <strong>Refresh</strong> in the top bar.",
        "The <strong>Activity log</strong> (Tools) records what nordctl changed in plain English.",
        "Use <strong>More detail</strong> below for the full help article on this page.",
      );
    }
    return bullets;
  }

  function pageHowKeyFromBlock(block) {
    if (!block) return currentRouteKey();
    return block.dataset.pageHowKey || STATIC_PAGE_HOW_KEYS[block.id] || currentRouteKey();
  }

  async function ensureHelpSectionsForPageHow() {
    if (helpSections.length) return helpSections;
    const data = await apiCached("/api/help", {}, CACHE_TTL.help);
    helpSections = data.sections || [];
    helpCatalogVersion = data.version || 0;
    return helpSections;
  }

  function bindHelpDocButtons(root) {
    root?.querySelectorAll("[data-help-doc]").forEach((btn) => {
      if (btn.dataset.helpDocBound) return;
      btn.dataset.helpDocBound = "1";
      btn.addEventListener("click", () => {
        const doc = btn.getAttribute("data-help-doc");
        if (doc === "open-source") window.open("/OPEN_SOURCE.md", "_blank");
        else if (doc === "legal") window.open("/LEGAL.md", "_blank");
      });
    });
  }

  function pageHowDepthHtmlForKey(key) {
    const bullets = pageHowDepthBulletsForKey(key);
    const list = bullets.map((b) => `<li>${b}</li>`).join("");
    return (
      `<div class="page-how-depth glass-inner hidden" data-page-how-depth data-page-how-key="${esc(key)}">` +
      `<div class="page-how-depth-head">` +
      `<strong class="page-how-depth-title">Quick tips</strong>` +
      `<button type="button" class="btn sm page-how-collapse-btn" title="Collapse extended help for this page">Hide detail</button>` +
      `</div>` +
      `<ul class="page-how-depth-list">${list}</ul>` +
      `<div class="page-how-depth-article" data-page-how-article aria-live="polite"></div>` +
      `</div>`
    );
  }

  function renderPageHowHead(key) {
    return (
      `<div class="page-how-head">` +
      `<strong class="page-how-title">${pageHowTitleForKey(key)}</strong>` +
      `<div class="page-how-actions">` +
      `<button type="button" class="btn sm page-how-expand-btn" title="Expand full help for this page in this panel">More detail</button>` +
      `<button type="button" class="btn sm page-how-hide-btn" title="Hide page guides on all tabs — restore with Show guides in the top bar">Hide all</button>` +
      `</div></div>`
    );
  }

  async function hydratePageHowDepthArticle(block) {
    if (!block) return;
    const articleEl = block.querySelector("[data-page-how-article]");
    if (!articleEl || articleEl.dataset.loaded === "1") return;
    const key = pageHowKeyFromBlock(block);
    const helpId = pageHowHelpIdForKey(key);
    articleEl.innerHTML = `<p class="help-text muted-inline page-how-article-loading">Loading detailed help…</p>`;
    try {
      await ensureHelpSectionsForPageHow();
      const sec = helpSections.find((s) => s.id === helpId);
      if (sec?.html) {
        const title = String(sec.title || "").replace(/&amp;/g, "&");
        articleEl.innerHTML =
          `<h3 class="page-how-article-title">${esc(title)}</h3>` +
          `<div class="help-full-body page-how-article-body">${sec.html}</div>`;
        bindHelpDocButtons(articleEl);
      } else {
        articleEl.innerHTML = `<p class="help-text muted-inline">No extended help article is mapped for this page yet.</p>`;
      }
    } catch (e) {
      articleEl.innerHTML = `<p class="help-text err">Could not load help: ${esc(formatFetchError(e))}</p>`;
    }
    articleEl.dataset.loaded = "1";
  }

  async function setPageHowDepthOpen(block, open) {
    if (!block) return;
    const depth = block.querySelector("[data-page-how-depth]");
    const expandBtn = block.querySelector(".page-how-expand-btn");
    if (depth) depth.classList.toggle("hidden", !open);
    if (expandBtn) expandBtn.classList.toggle("hidden", open);
    block.classList.toggle("page-how-depth-open", open);
    if (open) {
      await hydratePageHowDepthArticle(block);
      try {
        block.scrollIntoView({ behavior: "smooth", block: "nearest" });
      } catch (_) { /* ignore */ }
    }
  }

  function ensurePageHowHeadActions(block) {
    const head = block.querySelector(".page-how-head");
    if (!head || head.querySelector(".page-how-actions")) return;
    const hideBtn = head.querySelector(".page-how-hide-btn");
    if (!hideBtn) return;
    const actions = document.createElement("div");
    actions.className = "page-how-actions";
    const expandBtn = document.createElement("button");
    expandBtn.type = "button";
    expandBtn.className = "btn sm page-how-expand-btn";
    expandBtn.textContent = "More detail";
    expandBtn.title = "Expand full help for this page in this panel";
    actions.appendChild(expandBtn);
    actions.appendChild(hideBtn);
    head.appendChild(actions);
  }

  function ensurePageHowDepth(block, key) {
    if (!block || !key) return;
    block.dataset.pageHowKey = key;
    const depth = block.querySelector("[data-page-how-depth]");
    if (!depth) {
      block.insertAdjacentHTML("beforeend", pageHowDepthHtmlForKey(key));
      return;
    }
    if (!depth.dataset.pageHowKey) depth.dataset.pageHowKey = key;
    if (!depth.querySelector("[data-page-how-article]")) {
      depth.querySelector(".page-how-depth-foot")?.remove();
      depth.insertAdjacentHTML(
        "beforeend",
        `<div class="page-how-depth-article" data-page-how-article aria-live="polite"></div>`,
      );
    }
    const titleEl = depth.querySelector(".page-how-depth-title");
    if (titleEl && titleEl.textContent === "In-depth help") titleEl.textContent = "Quick tips";
  }

  function enhanceStaticPageHowBlocks() {
    document.querySelectorAll(".page-how[data-page-how-static]").forEach((block) => {
      const key = STATIC_PAGE_HOW_KEYS[block.id] || block.dataset.pageHowKey;
      if (!key) return;
      ensurePageHowHeadActions(block);
      ensurePageHowDepth(block, key);
    });
  }

  function wrapStaticPageHowHeaders() {
    document.querySelectorAll(".page-how[data-page-how-static]").forEach((block) => {
      if (block.querySelector(".page-how-head")) return;
      const title = block.querySelector(":scope > .page-how-title");
      if (!title) return;
      const head = document.createElement("div");
      head.className = "page-how-head";
      block.insertBefore(head, title);
      head.appendChild(title);
      head.appendChild(createPageHowHideBtn());
    });
    enhanceStaticPageHowBlocks();
  }

  function initPageHowUi() {
    wrapStaticPageHowHeaders();
    applyPageHowVisibility();
    $("btnTogglePageHow")?.addEventListener("click", togglePageHowVisibility);
    $("btnPageHowRestore")?.addEventListener("click", () => setPageHowHidden(false, { userAction: true }));
    $("btnSettingsShowPageGuides")?.addEventListener("click", () => setPageHowHidden(false, { userAction: true }));
    $("btnSettingsHidePageGuides")?.addEventListener("click", () => setPageHowHidden(true, { userAction: true }));
    document.addEventListener("click", (e) => {
      if (e.target.closest(".page-how-expand-btn")) {
        e.preventDefault();
        void setPageHowDepthOpen(e.target.closest(".page-how"), true);
        return;
      }
      if (e.target.closest(".page-how-collapse-btn")) {
        e.preventDefault();
        void setPageHowDepthOpen(e.target.closest(".page-how"), false);
        return;
      }
      if (e.target.closest(".page-how-hide-btn")) {
        e.preventDefault();
        setPageHowHidden(true, { userAction: true });
      }
    });
  }

  async function bootstrapPageHowPrefs() {
    try {
      const boot = window.__nordctlPreboot;
      if (boot?.ui_prefs) {
        applyUiPrefsFromConfig(boot.ui_prefs);
        return;
      }
      const st = await api("/api/state/quick");
      if (st?.ui_prefs) applyUiPrefsFromConfig(st.ui_prefs);
    } catch (_) {
      applyPageHowVisibility();
    }
  }

  function pageHowStepsForKey(key) {
    for (const k of pageHowLookupKeys(key)) {
      if (PAGE_HOW_STEPS[k]) return PAGE_HOW_STEPS[k];
    }
    const intro = tabIntroForRouteKey(key);
    if (!intro) {
      return [
        "Use the controls on this page — confirm dialogs explain anything risky before it runs.",
        "Press <strong>Refresh</strong> in the top bar if status or lists look stale.",
        "Click <strong>More detail</strong> on this guide for the full help article without leaving the page.",
      ];
    }
    const plain = String(intro.text || "").replace(/<[^>]+>/g, "");
    const sentences = plain.split(/(?<=[.!?])\s+/).filter((s) => s.trim());
    if (sentences.length >= 3) return sentences.slice(0, 5);
    return [
      intro.text,
      "Use the buttons and forms below — save or confirm when you are ready.",
      "Click <strong>More detail</strong> for the full help write-up on this page, or <strong>Hide guides</strong> if you already know it.",
    ];
  }

  function pageHowRelatedHtmlForKey(key) {
    let links = null;
    for (const k of pageHowLookupKeys(key)) {
      if (PAGE_HOW_RELATED[k]) {
        links = PAGE_HOW_RELATED[k];
        break;
      }
    }
    if (!links?.length) return "";
    const btns = links.map((l) =>
      `<button type="button" class="btn sm jump-link${l.primary ? " primary" : ""}" data-view-jump="${esc(l.route)}">${esc(l.label)}</button>`,
    ).join("");
    return (
      `<div class="page-how-related">` +
      `<span class="page-how-related-label">Related pages</span>` +
      `<div class="panel-nav-actions inline-jump-actions page-how-related-actions">${btns}</div>` +
      `</div>`
    );
  }

  function renderPageHowInner(key) {
    const steps = pageHowStepsForKey(key);
    const items = steps
      .map((s, i) => `<li><span class="wf-step-num">${i + 1}</span> ${s}</li>`)
      .join("");
    return `${renderPageHowHead(key)}<ol class="page-how-steps">${items}</ol>${pageHowRelatedHtmlForKey(key)}${pageHowDepthHtmlForKey(key)}`;
  }

  function pageHowInsertBefore(container) {
    if (!container) return null;
    if (container.matches("[data-settings-panel]")) {
      return container.firstElementChild;
    }
    const head = container.querySelector(":scope > .hero-card-head, :scope > .setup-header");
    if (head) {
      let n = head.nextElementSibling;
      while (n && n.matches(".page-how")) n = n.nextElementSibling;
      return n;
    }
    const subHead = container.querySelector(":scope > .settings-subhead-row, :scope > h3.settings-subhead");
    if (subHead) {
      let n = subHead.nextElementSibling;
      while (n && n.matches(".page-how")) n = n.nextElementSibling;
      return n;
    }
    const h2 = container.querySelector(":scope > h2");
    if (h2) {
      let n = h2.nextElementSibling;
      while (n && n.matches(".page-how")) n = n.nextElementSibling;
      return n;
    }
    const help = container.querySelector(":scope > .help-text, :scope > p.help-text");
    if (help) {
      let n = help.nextElementSibling;
      while (n && n.matches(".page-how")) n = n.nextElementSibling;
      return n;
    }
    return container.firstElementChild;
  }

  function ensurePageHow(container, key) {
    if (!container || !key) return;
    if (container.querySelector(".page-how[data-page-how-static]")) return;
    if (container.id === "setupBanner") return;
    let el = container.querySelector(".page-how[data-dynamic-page-how]");
    if (!el) {
      el = document.createElement("div");
      el.className = "page-how glass";
      el.dataset.dynamicPageHow = "1";
      container.insertBefore(el, container.firstElementChild);
    } else if (container.firstElementChild !== el) {
      container.insertBefore(el, container.firstElementChild);
    }
    el.innerHTML = renderPageHowInner(key);
    bindViewJumps(el);
  }

  function getPageHowTargets(route, key) {
    const targets = [];
    const activeView = document.querySelector(".view.active");

    if (route.section === "help") {
      const body = $("helpFullBody");
      if (body) targets.push({ el: body, key: route.sub ? `help/${route.sub}` : "help" });
      return targets;
    }

    if (activeView?.id === "viewCustomShell") {
      const panel = activeView.querySelector(".custom-shell-hub");
      if (panel) targets.push({ el: panel, key: "tools/custom-shell" });
      return targets;
    }

    if (activeView?.id === "viewCustomPackages") {
      const panel = activeView.querySelector(".custom-packages-hub");
      if (panel) targets.push({ el: panel, key: "tools/custom-packages" });
      return targets;
    }

    if (route.section === "settings" || getActiveView() === "settings") {
      const panel = document.querySelector("[data-settings-panel].active");
      if (panel) targets.push({ el: panel, key });
      return targets;
    }

    if (route.section === "tools" && route.tab === "terminal") {
      const panel = $("terminalPanel");
      if (panel) targets.push({ el: panel, key: "dashboard/terminal" });
      return targets;
    }

    if (route.section === "dashboard" && route.tab === "terminal") {
      const panel = $("terminalPanel");
      if (panel) targets.push({ el: panel, key: "dashboard/terminal" });
      return targets;
    }

    if (activeView?.id === "viewLogs") {
      const panel = activeView.querySelector(".logs-panel");
      if (panel) targets.push({ el: panel, key: key || "tools/logs" });
      return targets;
    }

    if (activeView?.id === "viewEditor") {
      const center = activeView.querySelector(".editor-center");
      if (center) targets.push({ el: center, key: key || "tools/editor" });
      return targets;
    }

    if (activeView?.id === "viewControl") {
      const panel = $("ufwEditorPanel");
      if (panel) targets.push({ el: panel, key: "network/host-ufw" });
      return targets;
    }

    if (route.section === "network" && route.tab === "diagnostics" && diagnosticsPane === "shell") {
      const panel = $("terminalPanel");
      if (panel) targets.push({ el: panel, key: "network/diagnostics/shell" });
      return targets;
    }

    if (activeView?.id === "viewWifi") {
      const mount = $("wifiPageHowMount");
      if (mount) {
        targets.push({ el: mount, key: key || "network/wifi" });
        return targets;
      }
    }

    if (activeView) {
      const panels = [...activeView.querySelectorAll(".page-tab-panel.active")].filter(
        (p) => !p.classList.contains("dashboard-row-2")
          && !p.classList.contains("connect-home-grid")
          && p.id !== "setupBanner",
      );
      if (panels.length) {
        panels.forEach((p) => targets.push({ el: p, key }));
        return targets;
      }
    }

    const fallback = activeView?.querySelector(".panel.glass:not(.wifi-hero)");
    if (fallback) targets.push({ el: fallback, key });
    return targets;
  }

  function syncPageHow() {
    const route = parseRouteHash();
    const key = currentRouteKey();
    const targets = getPageHowTargets(route, key);
    const keep = new Set();
    targets.forEach(({ el, key: k }) => {
      ensurePageHow(el, k);
      const dyn = el?.querySelector("[data-dynamic-page-how]");
      if (dyn) keep.add(dyn);
    });
    document.querySelectorAll("[data-dynamic-page-how]").forEach((el) => {
      if (!keep.has(el)) el.remove();
    });
  }

  let pendingHelpSection = null;
  let pendingPresetCategory = null;
  let pendingPresetEditId = null;
  let pendingPresetBuilderSpec = null;

  const SETTINGS_SCOPE_META = {
    general: { label: "General", title: "General settings", intro: "Dashboard password, interface, UI service, and LAN access — wizard steps for access and services." },
    locations: { label: "Places", title: "My places", intro: "Countries, cities, DNS, and servers used by presets — wizard home country and travel fields." },
    wifi: { label: "WiFi & DNS", title: "WiFi & Smart DNS", intro: "Smart DNS IPs, trusted WiFi, home ISP learning, and profile sync." },
    vpn: { label: "VPN", title: "VPN & probes", intro: "Split tunnel defaults, public IP probes, alert timing, and wizard shortcuts." },
    alerts: { label: "Alerts", title: "Alert settings", intro: "Browser and email alerts for VPN, WiFi, health, and security events." },
  };
  const SETTINGS_TAB_META = {
    password: { label: "Password", title: "Dashboard login password", scopes: ["general"] },
    interface: { label: "Interface", title: "Page guides and summary bar", scopes: ["general"] },
    "quick-commands": { label: "Quick commands", title: "Shell quick-command buttons", scopes: ["general"] },
    "speed-test": { label: "Speed test", title: "Speed lab defaults & mirrors", scopes: ["general"] },
    services: { label: "Services", title: "UI service & autostart", scopes: ["general"] },
    access: { label: "Access", title: "LAN vs local dashboard", scopes: ["general"] },
    places: { label: "My places", title: "Preset location fields", scopes: ["locations"] },
    "smart-dns": { label: "Smart DNS", title: "Streaming DNS on WiFi", scopes: ["wifi"] },
    zones: { label: "Zones & Home", title: "Trusted WiFi and home ISP", scopes: ["wifi"] },
    profiles: { label: "Profiles", title: "WiFi sync and self-heal", scopes: ["wifi"] },
    tunnel: { label: "Split tunnel", title: "LAN and VoIP defaults", scopes: ["vpn"] },
    probes: { label: "Probes", title: "Public IP and nordvpn path", scopes: ["vpn"] },
    "home-isp": { label: "Home ISP", title: "Static ISP fallback for top bar", scopes: ["vpn"] },
    advanced: { label: "Advanced", title: "Alert timing and wizard", scopes: ["vpn"] },
    notifications: { label: "Browser alerts", title: "Bell and alert rules", scopes: ["alerts"] },
    email: { label: "Email", title: "SMTP alerts", scopes: ["alerts"] },
  };
  const SETTINGS_TABS_BY_SCOPE = {
    general: ["password", "interface", "quick-commands", "speed-test", "services", "access"],
    locations: ["places"],
    wifi: ["smart-dns", "zones", "profiles"],
    vpn: ["tunnel", "probes", "home-isp", "advanced"],
    alerts: ["notifications", "email"],
  };
  const LEGACY_SETTINGS_SCOPE = { nord: "general", network: "alerts" };

  const NOTIFY_RULES = [
    { id: "setRuleVpnDisc", key: "vpn_disconnect", label: "VPN disconnect" },
    { id: "setRuleDnsDrift", key: "smart_dns_drift", label: "Smart DNS drift" },
    { id: "setRuleHealth", key: "health_score_low", label: "Low health score" },
    { id: "setRuleAudit", key: "security_audit", label: "Security audit issues" },
    { id: "setRuleUntrusted", key: "wifi_untrusted", label: "Untrusted WiFi" },
  ];

  function renderNotifyRules(rules, descriptions) {
    const desc = descriptions || {};
    const fallback = {
      vpn_disconnect: "NordVPN was connected and dropped unexpectedly.",
      smart_dns_drift: "WiFi DNS no longer matches your Nord Smart DNS IPs.",
      health_score_low: "Security hub score fell below the alert threshold.",
      security_audit: "Network audit reported a failed privacy or DNS check.",
      wifi_untrusted: "You joined a WiFi network not marked as trusted in zones.",
    };
    const defaultOn = (key) => key !== "wifi_untrusted";
    return NOTIFY_RULES.map((r) => {
      const on = rules && Object.prototype.hasOwnProperty.call(rules, r.key)
        ? !!rules[r.key]
        : defaultOn(r.key);
      const help = desc[r.key] || fallback[r.key] || "";
      return `<label class="settings-rule-card">
        <div class="settings-rule-head">
          <input type="checkbox" id="${r.id}" ${on ? "checked" : ""} />
          <strong>${esc(r.label)}</strong>
        </div>
        <p class="settings-rule-help">${esc(help)}</p>
      </label>`;
    }).join("");
  }
  const SETTINGS_SCOPE_KEY = "nordctl_settings_scope";
  const SETTINGS_TAB_KEY = "nordctl_settings_tab";
  let settingsScope = localStorage.getItem(SETTINGS_SCOPE_KEY) || "general";
  if (LEGACY_SETTINGS_SCOPE[settingsScope]) settingsScope = LEGACY_SETTINGS_SCOPE[settingsScope];
  let settingsTab = localStorage.getItem(SETTINGS_TAB_KEY) || "password";
  let uiPrefs = { page_guides_visible_default: true, page_intro_visible: true, clock_format: "24h" };

  let toolsTab = localStorage.getItem(TOOLS_TAB_KEY) || "auto-guide";
  let quickCommandsEditScope = "network";
  let quickCommandsSettingsDraft = null;
  let customShellCategory = localStorage.getItem("nordctl_custom_shell_cat") || null;
  let customPackagesCategory = localStorage.getItem("nordctl_custom_packages_cat") || "miscellaneous";

  const PAGE_TAB_VIEWS = {
    dashboard: { nav: "dashSubnav", scope: "#viewDashboard", key: DASH_TAB_KEY, default: "connect" },
    wifi: { nav: null, scope: "#viewWifi", key: WIFI_TAB_KEY, default: "profiles" },
    security: { nav: null, scope: "#viewSecurity", key: "nordctl_sec_tab", default: "overview" },
    lab: { nav: null, scope: "#viewLab", key: DIAGNOSTICS_TAB_KEY, default: "overall" },
    doctors: { nav: null, scope: "#viewDoctors", key: "nordctl_doctors_hub_tab", default: "overview" },
    advanced: { nav: null, scope: "#viewAdvanced", key: "nordctl_adv_tab", default: "traffic-internet" },
    automate: { nav: null, scope: "#viewAutomate", key: "nordctl_auto_tab", default: "guide" },
  };

  let dashTab = localStorage.getItem(DASH_TAB_KEY) || "connect";
  if (dashTab === "wizard") {
    dashTab = "connect";
    localStorage.setItem(DASH_TAB_KEY, dashTab);
  }
  let wifiTab = localStorage.getItem(WIFI_TAB_KEY) || "profiles";

  const INSTALL_TOOLS_FILTER_KEY = "nordctl_install_tools_filter";
  const installToolsFilter = {
    network: localStorage.getItem(`${INSTALL_TOOLS_FILTER_KEY}_network`) || "all",
    security: localStorage.getItem(`${INSTALL_TOOLS_FILTER_KEY}_security`) || "all",
    custom: localStorage.getItem(`${INSTALL_TOOLS_FILTER_KEY}_custom`) || "all",
  };
  const installToolsSelected = { network: new Set(), security: new Set(), custom: new Set() };
  const PACKAGE_CATEGORY_FILTER_KEY = "nordctl_pkg_category";
  function packageCategoryFilterKey(hub) {
    return `${PACKAGE_CATEGORY_FILTER_KEY}_${hub}`;
  }
  function getPackageCategoryFilter(hub) {
    if (hub === "custom") {
      return localStorage.getItem(packageCategoryFilterKey(hub)) || customPackagesCategory || "miscellaneous";
    }
    return localStorage.getItem(packageCategoryFilterKey(hub)) || "recommended";
  }
  function setPackageCategoryFilter(hub, catId) {
    localStorage.setItem(packageCategoryFilterKey(hub), catId || (hub === "custom" ? "miscellaneous" : "recommended"));
    if (hub === "custom" && catId) {
      customPackagesCategory = catId;
      localStorage.setItem("nordctl_custom_packages_cat", catId);
    }
  }
  function resolvePackageCategoryFilter(hub, categories) {
    const ids = new Set((categories || []).map((c) => c.id));
    ids.add("all");
    let cat = getPackageCategoryFilter(hub);
    if (hub === "custom") {
      if (customPackagesCategory && ids.has(customPackagesCategory)) return customPackagesCategory;
      if (ids.has(cat)) return cat;
      return categories[0]?.id || "miscellaneous";
    }
    if (cat === "all" || ids.has(cat)) return cat;
    return "recommended";
  }
  let wifiHubTab = localStorage.getItem("nordctl_wifi_hub_tab") || wifiTab || "profiles";
  let doctorsHubTab = localStorage.getItem("nordctl_doctors_hub_tab") || "overview";
  if (doctorsHubTab === "health") {
    doctorsHubTab = "overview";
    localStorage.setItem("nordctl_doctors_hub_tab", doctorsHubTab);
  }
  let networkHubTab = localStorage.getItem("nordctl_network_hub_tab") || "dns";
  let networkSetupQuickCommands = [];

  const PACKAGE_HUB_TABS = {
    "network-packages": { apiHub: "network", page: "network-packages", label: "Networking packages" },
    "security-packages": { apiHub: "security", page: "security-packages", label: "Security packages" },
  };

  const LEGACY_INSTALL_TOOLS_SUB = {
    network: "network-packages",
    networking: "network-packages",
    security: "security-packages",
    custom: "custom-packages",
  };

  function packageHubTabId(tabId) {
    if (PACKAGE_HUB_TABS[tabId]) return tabId;
    if (tabId === "install-tools") return "network-packages";
    return null;
  }

  function packageApiHub(tabId) {
    if (tabId === "security-packages") return "security";
    if (tabId === "custom-packages") return "custom";
    if (tabId === "network-packages") return "network";
    if (tabId === "install-tools") return "network";
    return PACKAGE_HUB_TABS[tabId]?.apiHub || "network";
  }

  function normalizeInstallToolsSub(sub) {
    if (!sub) return "network-packages";
    const s = String(sub).toLowerCase();
    if (LEGACY_INSTALL_TOOLS_SUB[s]) return LEGACY_INSTALL_TOOLS_SUB[s];
    if (PACKAGE_HUB_TABS[s]) return s;
    return "network-packages";
  }

  function installToolsPackagesRoute(hub, category) {
    if (hub === "custom") {
      const cat = category || customPackagesCategory;
      return cat ? `tools/custom-packages/${cat}` : "tools/custom-packages";
    }
    return hub === "security" ? "network/security-packages" : "network/network-packages";
  }

  function resolveLegacyHubRoute(tabId, sub) {
    const leg = LEGACY_HUB_TABS[tabId];
    if (!leg) return null;
    return { tab: leg.redirectTab, sub: leg.redirectSub || sub || null };
  }

  function packageHubTabFromLegacySub(sub) {
    return normalizeInstallToolsSub(sub);
  }

  const AUDIT_RETURN_ROUTE = "network/audit";
  const INSTALL_RETURN_ROUTE_KEY = "nordctl_install_return_route";
  const INSTALL_RETURN_CAT_KEY = "nordctl_install_return_cat";
  const WIZARD_RETURN_ROUTE = "dashboard/wizard";

  function installTermScope(hub, category) {
    if (hub === "security") return "security";
    if (hub === "custom") return customPackageTermScope(category);
    return "network";
  }

  function setInstallReturnContext(opts = {}) {
    const hub = opts.hub || packageApiHub(hubTab) || (getActiveView() === "customPackages" ? "custom" : "network");
    sessionStorage.setItem("nordctl_install_return_hub", hub);
    if (hub === "custom") {
      sessionStorage.setItem(INSTALL_RETURN_CAT_KEY, opts.category || customPackagesCategory || "");
    } else {
      sessionStorage.removeItem(INSTALL_RETURN_CAT_KEY);
    }
    const returnRoute = opts.returnRoute || installToolsPackagesRoute(hub, opts.category || customPackagesCategory);
    if (returnRoute && hub !== "network") {
      sessionStorage.setItem(INSTALL_RETURN_ROUTE_KEY, returnRoute);
    } else if (opts.returnRoute) {
      sessionStorage.setItem(INSTALL_RETURN_ROUTE_KEY, opts.returnRoute);
    } else {
      sessionStorage.removeItem(INSTALL_RETURN_ROUTE_KEY);
    }
  }

  function postInstallBackMeta(sess) {
    const route = sess?.packageInstallReturnRoute || sessionStorage.getItem(INSTALL_RETURN_ROUTE_KEY) || "";
    if (route === AUDIT_RETURN_ROUTE) {
      return { route: AUDIT_RETURN_ROUTE, label: "Back to audit", auditReturn: true };
    }
    if (route === WIZARD_RETURN_ROUTE) {
      return { route: WIZARD_RETURN_ROUTE, label: "Back to wizard", wizardReturn: true };
    }
    return {
      route: installToolsPackagesRoute(
        sess?.packageInstallHub || sessionStorage.getItem("nordctl_install_return_hub") || "network",
        sess?.packageInstallCategory || sessionStorage.getItem(INSTALL_RETURN_CAT_KEY) || customPackagesCategory,
      ),
      label: "Back to packages",
      auditReturn: false,
    };
  }

  function termRehydratePackageInstallContext(sess) {
    if (!sess || sess.afterPackageInstall) return;
    const returnRoute = sessionStorage.getItem(INSTALL_RETURN_ROUTE_KEY) || "";
    if (!returnRoute) return;
    const labelLooksInstall = /\binstall\b/i.test(sess.label || "");
    const displayLooksInstall = /\bapt(-get)?\s+install\b/i.test(sess.display || "");
    if (!labelLooksInstall && !displayLooksInstall) return;
    sess.afterPackageInstall = true;
    sess.packageInstallReturnRoute = returnRoute;
    sess.packageInstallHub = sessionStorage.getItem("nordctl_install_return_hub") || packageApiHub(hubTab) || "network";
    sess.packageInstallCategory = sessionStorage.getItem(INSTALL_RETURN_CAT_KEY) || customPackagesCategory || "";
  }

  function wirePostInstallBackButton(bar, sess, backMeta) {
    const btn = bar.querySelector("[data-post-install-back]");
    if (!btn) return;
    btn.addEventListener("click", async (e) => {
      e.preventDefault();
      hideNotice();
      sess.postInstall = null;
      sess.afterPackageInstall = false;
      sessionStorage.removeItem(INSTALL_RETURN_ROUTE_KEY);
      termRenderPostInstallBar(sess);
      if (backMeta.auditReturn) {
        invalidateApiCache("/api/overall-audit");
        const jump = resolveViewJump(backMeta.route);
        navigateRoute(jump.section, jump.tab, { force: true, sub: jump.sub || null });
        await loadOverallAudit(true);
      } else if (backMeta.wizardReturn) {
        const jump = resolveViewJump(backMeta.route);
        navigateRoute(jump.section, jump.tab, { force: true, sub: jump.sub || null });
        await refreshWizardContext();
      } else {
        const jump = resolveViewJump(backMeta.route);
        navigateRoute(jump.section, jump.tab, { force: true, sub: jump.sub || null });
      }
    });
  }

  function postInstallBackButtonHtml(backMeta, opts = {}) {
    const primary = !!opts.primary;
    return `<button type="button" class="btn sm${primary ? " primary" : ""} jump-link" data-post-install-back data-view-jump="${esc(backMeta.route)}">${esc(backMeta.label)}</button>`;
  }

  const INSTALL_TOOLS_TOOLBARS = {
    network: "networkToolsToolbar",
    security: "secToolsToolbar",
    custom: "customToolsToolbar",
  };
  const INSTALL_TOOLS_RESULT_BOXES = {
    network: "networkToolsResult",
    security: "secToolsResult",
    custom: "customToolsResult",
  };
  const INSTALL_TOOLS_FILTER_OPTS = [
    { id: "all", label: "All" },
    { id: "missing", label: "Not installed" },
    { id: "installed", label: "Installed" },
  ];

  const WIFI_HUB_TABS = {
    profiles: { label: "Profiles", title: "WiFi profiles, nearby networks, and checks" },
    zones: { label: "Zones", title: "Trusted WiFi zones and self-healing" },
  };

  const WIFI_LEGACY_SUB = {
    nearby: "profiles",
    "wifi-doctor": "profiles",
    scenarios: "profiles",
    "smart-dns": "profiles",
  };

  const TRAFFIC_HUB_TABS = {
    live: { label: "Live", title: "Bandwidth and speed test" },
    internet: { label: "Internet", title: "Outbound/inbound internet sessions" },
    local: { label: "Local", title: "LAN and Meshnet sessions" },
  };

  let trafficHubTab = localStorage.getItem("nordctl_traffic_hub_tab") || "internet";
  if (localStorage.getItem("nordctl_adv_tab") === "traffic") {
    localStorage.setItem("nordctl_adv_tab", "traffic-internet");
  }

  const NETWORK_HUB_TABS = {
    dns: { label: "DNS", title: "DNS assistant and conflicts" },
    ipv6: { label: "IPv6", title: "IPv6 on your LAN" },
  };

  const NETWORK_LEGACY_SUB = {
    bandwidth: { tab: "traffic-live", sub: null },
    speed: { tab: "traffic-speed", sub: null },
    config: { tab: "diagnostics", sub: null },
  };

  if (NETWORK_LEGACY_SUB[networkHubTab]) {
    const leg = NETWORK_LEGACY_SUB[networkHubTab];
    if (leg.tab === "traffic-live") {
      localStorage.setItem("nordctl_adv_tab", "traffic-live");
    }
    if (leg.tab === "traffic-speed") {
      localStorage.setItem("nordctl_adv_tab", "traffic-speed");
    }
    networkHubTab = "dns";
    localStorage.setItem("nordctl_network_hub_tab", networkHubTab);
  }

  const DIAG_PANE_KEY = "nordctl_diag_pane";
  const AUDIT_PANE_KEY = "nordctl_audit_pane";

  const DOCTORS_HUB_TABS = {
    overview: { label: "Overview", title: "Health doctor summary" },
    wifi: { label: "WiFi & DNS", title: "WiFi profiles and Smart DNS" },
    privacy: { label: "Network", title: "IPv6 and connectivity" },
    system: { label: "System", title: "Python and sudo privileges" },
    net: { label: "Net doctor", title: "DNS, IPv6, resolv.conf" },
  };

  const DOCTOR_TAB_GROUPS = {
    wifi: 0,
    privacy: 1,
    system: 2,
  };

  const WIFI_LEGACY_HUB = {
    "wifi-profiles": "profiles",
    "wifi-zones": "zones",
    "wifi-nearby": "nearby",
    "wifi-doctor": "wifi-doctor",
  };

  let hubTabRaw = localStorage.getItem(HUB_TAB_KEY) || "monitoring";
  if (hubTabRaw === "alerts") {
    hubTabRaw = "monitoring";
    localStorage.setItem(HUB_TAB_KEY, "monitoring");
  }
  if (hubTabRaw === "doctor") {
    doctorsHubTab = "overview";
    localStorage.setItem("nordctl_doctors_hub_tab", doctorsHubTab);
    hubTabRaw = "doctors";
    localStorage.setItem(HUB_TAB_KEY, "doctors");
  }
  if (localStorage.getItem(DIAGNOSTICS_TAB_KEY) === "doctor") {
    localStorage.setItem(DIAGNOSTICS_TAB_KEY, "leak");
    localStorage.setItem("nordctl_doctors_hub_tab", "overview");
    if (!localStorage.getItem(HUB_TAB_KEY) || localStorage.getItem(HUB_TAB_KEY) === "doctor") {
      hubTabRaw = "doctors";
      localStorage.setItem(HUB_TAB_KEY, "doctors");
    }
  }
  if (localStorage.getItem("nordctl_sec_tab") === "tools") {
    localStorage.setItem("nordctl_sec_tab", "overview");
  }
  const legacySecTab = localStorage.getItem("nordctl_sec_tab");
  if (legacySecTab === "network" || legacySecTab === "alerts") {
    localStorage.setItem("nordctl_sec_tab", "overview");
  }
  if (WIFI_LEGACY_HUB[hubTabRaw]) {
    wifiHubTab = WIFI_LEGACY_HUB[hubTabRaw];
    localStorage.setItem("nordctl_wifi_hub_tab", wifiHubTab);
    localStorage.setItem(WIFI_TAB_KEY, wifiHubTab);
    hubTabRaw = "wifi";
    localStorage.setItem(HUB_TAB_KEY, "wifi");
  }
  if (wifiHubTab === "scenarios" || wifiHubTab === "smart-dns") {
    wifiHubTab = "profiles";
    localStorage.setItem("nordctl_wifi_hub_tab", wifiHubTab);
    localStorage.setItem(WIFI_TAB_KEY, wifiHubTab);
  }
  if (doctorsHubTab === "nordvpn") {
    doctorsHubTab = "overview";
    localStorage.setItem("nordctl_doctors_hub_tab", doctorsHubTab);
  }
  let diagnosticsPane = localStorage.getItem(DIAG_PANE_KEY) || "checks";
  let diagnosticsShellScope = localStorage.getItem("nordctl_diag_shell_scope") || "network";
  let auditPane = localStorage.getItem(AUDIT_PANE_KEY) || "full";
  if (hubTabRaw === "terminal") {
    hubTabRaw = "networking-shell";
    localStorage.setItem(HUB_TAB_KEY, "networking-shell");
    diagnosticsPane = "shell";
    localStorage.setItem(DIAG_PANE_KEY, "shell");
  }
  if (hubTabRaw === "diagnostics") {
    hubTabRaw = "networking-shell";
    localStorage.setItem(HUB_TAB_KEY, "networking-shell");
    diagnosticsPane = "shell";
    localStorage.setItem(DIAG_PANE_KEY, "shell");
  }
  if (hubTabRaw === "install-tools") {
    const legacyPkg = localStorage.getItem("nordctl_install_tools_tab") || "networking";
    hubTabRaw = legacyPkg === "security" ? "security-packages" : "network-packages";
    localStorage.setItem(HUB_TAB_KEY, hubTabRaw);
  }
  if (hubTabRaw === "setup") {
    hubTabRaw = "security-packages";
    localStorage.setItem(HUB_TAB_KEY, hubTabRaw);
    localStorage.setItem("nordctl_adv_tab", "security-packages");
  }
  if (hubTabRaw === "nord-cli") {
    hubTabRaw = "map-internet";
    localStorage.setItem(HUB_TAB_KEY, "map-internet");
  }
  if (hubTabRaw === "traffic") {
    const legSub = localStorage.getItem("nordctl_traffic_hub_tab") || "internet";
    hubTabRaw = legSub === "local" ? "map-local" : legSub === "live" ? "traffic-live" : "map-internet";
    localStorage.setItem(HUB_TAB_KEY, hubTabRaw);
  }
  if (localStorage.getItem("nordctl_adv_tab") === "install") {
    localStorage.setItem("nordctl_adv_tab", "network-packages");
  }
  if (localStorage.getItem("nordctl_adv_tab") === "setup") {
    localStorage.setItem("nordctl_adv_tab", "security-packages");
  }
  if (localStorage.getItem("nordctl_adv_tab") === "cli") {
    localStorage.setItem("nordctl_adv_tab", "traffic-internet");
  }
  if (hubTabRaw === "tools") {
    const primary = localStorage.getItem(HUB_PRIMARY_KEY) || "networking";
    hubTabRaw = HUB_PRIMARY_DEFAULT_TAB[primary] || "wifi";
    localStorage.setItem(HUB_TAB_KEY, hubTabRaw);
  }
  let hubTab = hubTabRaw;
  let hubPrimaryTab = localStorage.getItem(HUB_PRIMARY_KEY) || hubTabGroup(hubTab);
  if (!HUB_PRIMARY_TABS[hubPrimaryTab]) hubPrimaryTab = hubTabGroup(hubTab);
  if (HUB_TABS[hubTab] && hubTabGroup(hubTab) !== hubPrimaryTab) {
    hubPrimaryTab = hubTabGroup(hubTab);
    localStorage.setItem(HUB_PRIMARY_KEY, hubPrimaryTab);
  }
  let termPanelMount = "network";

  const REQUIRED_SETUP_IDS = new Set(["python", "nordvpn_cli", "nordvpnd", "nordvpn_login"]);

  const NORD_FOCUS_MODULES = {
    dashboard: true,
    help: true,
    logs: true,
    editor: true,
    terminal: true,
    automate: true,
    lab: false,
    wifi: false,
    security: false,
    control: false,
    traffic: false,
    services: false,
    alerts: false,
  };

  const NETWORK_FOCUS_MODULES = {
    dashboard: true,
    lab: true,
    help: true,
    logs: true,
    editor: true,
    terminal: true,
    wifi: true,
    security: true,
    control: true,
    traffic: true,
    services: true,
    automate: true,
    alerts: false,
  };

  /** @deprecated alias */
  const TOOLS_ONLY_MODULES = NETWORK_FOCUS_MODULES;

  const TOOLS_WELCOME_LINKS = [
    { route: "network/network-packages", label: "Networking packages", desc: "Diagnostics and WiFi apt packages — curl, dig, mtr, nmap, …" },
    { route: "network/security-packages", label: "Security packages", desc: "UFW, tcpdump, Lynis, ClamAV, fail2ban, privileges, …" },
    { route: "network/host-ufw", label: "Firewall editor", desc: "Add or remove UFW rules in plain English" },
    { route: "network/listeners", label: "Listeners", desc: "TCP ports open on this computer" },
    { route: "network/wifi", label: "WiFi hub", desc: "Fix WiFi, DNS drift, and connection issues" },
    { route: "network/diagnostics/shell", label: "Networking shell", desc: "Routes, WiFi, apt networking tools, tcpdump" },
    { route: "network/diagnostics/security-shell", label: "Security shell", desc: "UFW, Lynis, fail2ban, apt security tools, sudo" },
    { route: "network/leak-tests", label: "Leak lab", desc: "Privacy and DNS checks on this machine" },
  ];

  const DOCTOR_GROUPS = [
    {
      title: "NordVPN",
      hint: "Install, login, and nordvpnd service — required for VPN presets.",
      ids: ["nordvpn_cli", "nordvpnd", "nordvpn_login"],
    },
    {
      title: "WiFi & Smart DNS",
      hint: "NetworkManager profiles and country config for streaming presets.",
      ids: ["networkmanager", "resolved", "wifi_profiles", "connect_country", "dns_manager", "resolv_conf"],
    },
    {
      title: "Network & privacy",
      hint: "IPv6 leak risk and basic internet connectivity.",
      ids: ["ipv6", "connectivity"],
    },
    {
      title: "System",
      hint: "Python runtime and sudo privileges for automated fixes.",
      ids: ["python", "privileges"],
    },
  ];

  const editor = {
    active: false,
    id: "config",
    savedContent: "",
    readonly: false,
    lintTimer: null,
    errorLine: null,
  };

  /** Hover help for every action button — applied on load and after dynamic renders. */
  const BUTTON_TITLES = {
    btnOpenSource: "Read OPEN_SOURCE.md — license and third-party notices",
    btnLegal: "Read LEGAL.md — disclaimer and acceptable use",
    btnDisconnect: "Turn off the VPN tunnel (Meshnet may stay on)",
    btnConnect: "Connect VPN to the country and optional city selected above",
    btnDryRun: "Show NordVPN apt install commands without running them",
    btnDnsSave: "Save Smart DNS IP addresses to config.yaml (does not apply to WiFi yet)",
    btnApplySmartDns: "Write Nord streaming DNS to this PC's WiFi profiles (NetworkManager) — not just Nord online",
    btnRestoreDns: "Set this PC's WiFi profiles back to automatic ISP DNS (NetworkManager)",
    btnNordDnsOn: "Use Nord DNS while the VPN tunnel is connected",
    btnNordDnsOff: "Stop forcing Nord DNS when VPN is connected",
    btnCopyIp: "Copy your current public IP address to the clipboard",
    btnNordAccount: "Open Nord Account in a new browser tab",
    btnNordFwOn: "Enable NordVPN’s own firewall (iptables/nft rules)",
    btnNordFwOff: "Disable NordVPN firewall — UFW may still filter traffic",
    btnKillOn: "Block internet if the VPN connection drops unexpectedly",
    btnKillOff: "Allow traffic when VPN is disconnected (less safe)",
    btnUfwEnable: "Turn on Linux UFW host firewall",
    btnUfwDisable: "Turn off UFW — does not change Nord firewall",
    btnUfwReload: "Reload UFW rules after manual edits in a terminal",
    btnUfwAdd: "Add an ALLOW rule (port, optional source IP, comment)",
    btnWifiRescan: "Ask NetworkManager to scan for WiFi networks again",
    btnWifiSync: "Add the active WiFi profile name to config.yaml automatically",
    btnWifiHeal: "Run all enabled self-healing fixes (DNS, profiles, zones)",
    btnWifiDnsSave: "Save Smart DNS IPs to config from the WiFi tab",
    btnWifiApplySmart: "Apply Smart DNS on this PC's configured WiFi profiles (NetworkManager)",
    btnWifiRestoreDns: "Restore automatic DNS on this PC's WiFi profiles",
    btnWifiWatchOn: "Background monitor: apply zone preset when SSID changes",
    btnWifiWatchOff: "Stop automatic preset apply on WiFi change",
    btnWifiZoneApply: "Apply the preset mapped to the current WiFi SSID now",
    btnWifiZoneAdd: "Save SSID → preset mapping to config trusted zones",
    btnWifiZonesSave: "Save zone auto-apply and untrusted preset settings",
    btnWifiConnectSsid: "Join a new WiFi network by SSID (password optional for open networks)",
    btnRunLab: "Run DNS leak, WebRTC, and routing checks",
    btnRunDoctor: "Full health check: Nord, WiFi, DNS, IPv6, sudo",
    btnLabToAdvanced: "Open Network & Security → Audit for diagnostics and network tools",
    btnEditConfig: "Open Tools → Editor to edit config.yaml manually",
    btnSpeedLabRun: "Run download speed test with selected profile and method",
    btnSecDisableIpv6: "Disable IPv6 system-wide to reduce VPN bypass leaks",
    btnSettingsNotifySave: "Save browser alerts, bell rules, and notification toggle",
    btnSettingsNotifyTest: "Send a test browser/email alert now",
    btnSettingsAlertsWatchOn: "Start polling for VPN drops, DNS drift, health score, and other enabled rules (~60s interval)",
    btnSettingsAlertsWatchOff: "Stop automatic alert checks — alerts only while dashboard is open",
    btnSettingsPrivacyExport: "Save a local JSON privacy and module report to your config exports folder",
    btnSettingsEmailSave: "Save SMTP credentials, recipient, and email alert rules",
    btnSettingsEmailTest: "Send a test alert through browser and email if enabled",
    btnSetupSwitchVpn: "Switch nordctl from tools-only to full VPN mode",
    btnPrivacyExport: "Save a local privacy manifest JSON file",
    btnSecWatchOn: "Poll VPN every ~30s and show a Linux desktop notification if it drops (notify-send)",
    btnSecWatchOff: "Stop desktop disconnect notifications only — browser alerts unchanged",
    btnSecCapture: "Short tcpdump on VPN interface — saves .pcap file",
    btnSecStatusOn: "Enable read-only status page for phone on same WiFi",
    btnSecStatusOff: "Disable LAN status page and token URL",
    btnSecCopyStatusUrl: "Copy the local status page URL",
    btnSecExportConfig: "Export config + settings bundle for support",
    btnSecExportLogs: "Export plain-English activity log as text file",
    btnSecCopyHa: "Copy Home Assistant REST sensor YAML snippet",
    btnAddFavCountry: "Add selected country to favorites list",
    btnConnectFav: "Connect VPN to the favorite country selected above",
    btnAddSubnet: "Add subnet to Nord split-tunnel allowlist",
    btnAddPort: "Add TCP/UDP port to Nord allowlist",
    btnApplyLan: "Apply default LAN CIDR from config to allowlist",
    btnZoneApply: "Apply the preset mapped to your current WiFi SSID (Tools → Zone watcher)",
    btnSwitchProfile: "Switch active config profile (countries, presets)",
    btnAddSchedule: "Add a daily preset schedule to config",
    btnWriteSystemd: "Write systemd user timers for schedules in config",
    btnSnapshotSave: "Save current NordVPN settings only (quick undo)",
    btnSnapshotRestore: "Restore Nord settings from latest snapshot",
    btnSnapshotRestoreOnly: "Restore Nord settings from latest snapshot only",
    btnSvcUiInstall: "Install nordctl web UI as systemd user service + enable at login",
    btnSvcUiStart: "Start the nordctl web UI service now",
    btnSvcUiStop: "Stop the nordctl web UI service",
    btnSvcUiRestart: "Restart the nordctl web UI service",
    btnSvcUiEnable: "Start UI automatically when you log in",
    btnSvcUiDisable: "Do not start UI at login (manual nordctl serve)",
    btnSvcUiUninstall: "Remove UI systemd unit and disable login autostart",
    btnSvcNordStart: "Start nordvpnd VPN daemon (may need sudo)",
    btnSvcNordStop: "Stop nordvpnd VPN daemon (may need sudo)",
    btnSvcNordRestart: "Restart nordvpnd VPN daemon (may need sudo)",
    btnSvcNordEnable: "Start nordvpnd automatically at system boot",
    btnSvcNordDisable: "Do not start nordvpnd at boot",
    btnAdvNettoolRun: "Run selected network diagnostic tool on target",
    btnOnboardAll: "Nord + Network & Security + Tools — every module",
    btnOnboardNordFocus: "Nord Dashboard only — VPN, presets, login (hide network hub until you enable it)",
    btnOnboardNetworkOnly: "Network & Security + Tools — no NordVPN account",
    btnOnboardMinimal: "Core only — dashboard, help, logs, editor, terminal",
    btnOnboardSave: "Save checked modules and continue",
    editorSave: "Save the open file (config or preset YAML)",
    editorRevert: "Discard unsaved edits to the last saved version on disk (not install baseline)",
    editorRestoreBaseline: "Restore this file from the install baseline snapshot",
    editorRestoreAllBaseline: "Restore config.yaml and all your presets from install baseline",
    editorDeletePreset: "Delete this custom preset file",
    editorNewPreset: "Create a new user preset YAML file",
    btnFactoryReset: "Restore pre-install state — baseline, remove services, clear logs",
  };

  function applyButtonTitles(root) {
    Object.entries(BUTTON_TITLES).forEach(([id, title]) => {
      const node = (root && root.querySelector ? root.querySelector(`#${id}`) : null) || document.getElementById(id);
      if (node && title) {
        node.setAttribute("title", title);
        node.setAttribute("aria-label", title);
      }
    });
    const scope = root || document;
    scope.querySelectorAll("button.btn, button.icon-btn, button.linkish").forEach((btn) => {
      if (!btn.getAttribute("title") && btn.textContent.trim()) {
        const t = btn.textContent.trim().replace(/\s+/g, " ");
        if (t.length > 1 && t.length < 80) btn.setAttribute("title", t);
      }
    });
  }

  function renderFactoryResetPanel(data) {
    const bl = data?.baseline || {};
    const badge = $("resetBadge");
    if (badge) {
      badge.textContent = bl.exists ? "Ready" : "No baseline";
      badge.className = "badge " + (bl.exists ? "on" : "warn");
    }
    if ($("resetMetrics")) {
      $("resetMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Baseline</div><div class="val ${bl.exists ? "on" : "off"}">${bl.exists ? "Ready" : "Missing"}</div><div class="sub">Install snapshot</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Factory reset</div><div class="val ${bl.exists ? "on" : "warn"}">${bl.exists ? "Available" : "Blocked"}</div><div class="sub">Full undo path</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Clears</div><div class="val">Logs</div><div class="sub">Schedules &amp; snapshots</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Keeps</div><div class="val on">NordVPN</div><div class="sub">Program stays installed</div></div>`,
      ].join("");
    }
    const box = $("factoryResetBox");
    if (box) {
      box.innerHTML = [
        statCell("Baseline", bl.exists ? "Ready" : "Missing", bl.exists ? "on" : "off"),
        statCell("Factory reset", bl.exists ? "Available" : "Create baseline first", bl.exists ? "on" : "warn"),
      ].join("");
    }
    const hint = $("factoryResetHint");
    if (hint) {
      hint.textContent = bl.exists
        ? (bl.message || "Uses install baseline from first nordctl init.")
        : "No baseline yet — click Create baseline now above, or run nordctl init, before factory reset.";
    }
    const btn = $("btnFactoryReset");
    if (btn) btn.disabled = !bl.exists;
  }

  function healthFixRoute(fix) {
    if (!fix) return null;
    if (/traffic|direct/i.test(fix)) return "network/map-internet";
    if (/lab|leak/i.test(fix)) return "network/leak-tests";
    if (/audit/i.test(fix)) return "network/audit";
    if (/service|nordvpnd/i.test(fix)) return "dashboard/nord-services";
    if (/nord dashboard|nord doctor/i.test(fix)) return "dashboard/nord-doctor";
    if (/wizard|setup/i.test(fix)) return "dashboard/wizard";
    return null;
  }

  function openUrlBtn(url, label) {
    const u = String(url || "").trim();
    if (!u || u === "#") return esc(label || "—");
    return `<button type="button" class="btn sm" data-open-url="${esc(u)}">${esc(label || u)}</button>`;
  }

  function bindOpenUrlButtons(root) {
    (root || document).querySelectorAll("[data-open-url]").forEach((btn) => {
      if (btn.dataset.urlBound) return;
      btn.dataset.urlBound = "1";
      btn.addEventListener("click", () => window.open(btn.getAttribute("data-open-url"), "_blank", "noopener"));
    });
  }

  const VIEW_JUMP_LABELS = {
    advanced: "Advanced",
    security: "Security",
    wizard: "Wizard",
    "nord-doctor": "Nord doctor",
    "nord-services": "Nord services",
    terminal: "Terminal",
    lab: "Lab",
    help: "Help",
    automate: "Automate",
    wifi: "WiFi",
    control: "Control",
    logs: "Logs",
    editor: "Editor",
    firewall: "Firewall",
  };

  function viewLink(view, label, anchor) {
    const jump = jumpRouteString(anchor ? `${view}#${anchor}` : view);
    const text = label || VIEW_JUMP_LABELS[view] || view;
    return `<button type="button" class="btn sm jump-link" data-view-jump="${esc(jump)}">${esc(text)}</button>`;
  }

  function bindViewJumps(root) {
    (root || document).querySelectorAll("[data-view-jump]").forEach((el) => {
      if (el.dataset.jumpBound) return;
      el.dataset.jumpBound = "1";
      if (el.tagName === "BUTTON") {
        el.classList.remove("linkish");
        if (!el.classList.contains("btn")) {
          el.classList.add("btn", "sm");
        }
      }
      el.addEventListener("click", (e) => {
        e.preventDefault();
        hideNotice();
        const route = resolveViewJump(el.dataset.viewJump || "");
        navigateRoute(route.section, route.tab, { force: true, sub: route.sub || null });
      });
    });
    bindOpenUrlButtons(root);
  }

  function diagnosticsShellHubTab(sub) {
    const scope = diagnosticsShellScopeFromSub(sub || "");
    if (scope === "security") return "security-shell";
    if (scope === "network") return "networking-shell";
    return null;
  }

  function hubShellRouteSub(scope, sessionId) {
    return diagnosticsShellRouteSub(scope === "security" ? "security" : "network", sessionId);
  }

  function hubShellTabHash(tabId) {
    const cfg = HUB_TABS[tabId];
    if (!cfg?.shellScope) return null;
    const scope = cfg.shellScope;
    const sid = termPreferredSessionId(scope);
    const prefix = hubRoutePrefixForTab(tabId);
    return `#${prefix}/diagnostics/${hubShellRouteSub(scope, sid)}`;
  }

  function syncHubShellTabHashes() {
    $("hubSubnav")?.querySelectorAll("[data-hub-tab]").forEach((btn) => {
      const tabId = btn.getAttribute("data-hub-tab");
      const hash = hubShellTabHash(tabId);
      if (hash) btn.dataset.tabHash = hash.slice(1);
    });
  }

  function syncHubTabForDiagnosticsShell() {
    if (diagnosticsPane !== "shell") return;
    const shellTab = diagnosticsShellHubTab(
      diagnosticsShellRouteSub(diagnosticsShellScope, activeTermId),
    );
    if (!shellTab) return;
    hubTab = shellTab;
    localStorage.setItem(HUB_TAB_KEY, shellTab);
    syncHubTabHighlight(shellTab);
  }

  function diagnosticsShellScopeFromSub(sub) {
    if (!sub) return null;
    if (sub === "security-shell" || sub.startsWith("security-shell/")) return "security";
    if (sub === "shell" || sub.startsWith("shell/")) return "network";
    return null;
  }

  function diagnosticsShellRouteSub(scope, sessionId) {
    const prefix = scope === "security" ? "security-shell" : "shell";
    return sessionId ? `${prefix}/${sessionId}` : prefix;
  }

  function termRouteSection() {
    const route = parseRouteHash();
    if (route.section === "dashboard" && route.tab === "terminal") return "dashboard";
    if (route.section === "tools" && route.tab === "terminal") return "dashboard";
    if (route.section === "tools" && route.tab === "custom-shell") return "tools";
    return "network";
  }

  function termCommandScope() {
    const route = parseRouteHash();
    if (route.section === "tools" && route.tab === "custom-shell") {
      const cat = route.sub || customShellCategory;
      return cat ? `custom:${cat}` : "custom:";
    }
    if (getActiveView() === "customShell" && customShellCategory) {
      return `custom:${customShellCategory}`;
    }
    if (route.section === "tools" && route.tab === "terminal") return "nord";
    if (route.section === "dashboard" && route.tab === "terminal") return "nord";
    const fromSub = diagnosticsShellScopeFromSub(route.sub || "");
    if (fromSub) return fromSub;
    if (route.section === "network"
      && (route.tab === "diagnostics" || route.tab === "networking-shell" || route.tab === "security-shell")
      && diagnosticsPane === "shell") {
      if (route.tab === "security-shell") return "security";
      if (route.tab === "networking-shell") return "network";
      return diagnosticsShellScope === "security" ? "security" : "network";
    }
    return "network";
  }

  function diagnosticsPaneFromSub(sub) {
    if (!sub) return "checks";
    if (sub === "packages") return "packages";
    if (sub === "shell" || sub.startsWith("shell/")) return "shell";
    if (sub === "security-shell" || sub.startsWith("security-shell/")) return "shell";
    return "checks";
  }

  function auditPaneFromSub(sub) {
    if (!sub || sub === "full" || sub === "overall") return "full";
    if (sub === "leak") return "leak";
    return "full";
  }

  function diagnosticsTermSessionFromSub(sub) {
    if (sub && sub.startsWith("shell/")) return sub.slice(6);
    if (sub && sub.startsWith("security-shell/")) return sub.slice(15);
    return null;
  }

  function syncDiagnosticsShellScope(scope, opts = {}) {
    const next = scope === "security" ? "security" : "network";
    diagnosticsShellScope = next;
    localStorage.setItem("nordctl_diag_shell_scope", next);
    $("diagnosticsShellScopeNav")?.querySelectorAll("[data-diagnostics-shell-scope]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-diagnostics-shell-scope") === next);
    });
    const titleEl = $("termPanelTitle");
    if (titleEl && termPanelMount !== "dashboard") {
      titleEl.textContent = next === "security" ? "Security shell" : "Networking shell";
    }
    if (!opts.skipHash && diagnosticsPane === "shell") {
      syncRouteHash("network", "diagnostics", !!opts.replaceHash, diagnosticsShellRouteSub(next, activeTermId));
    }
  }

  function termMountPanel(target) {
    const panel = $("terminalPanel");
    if (!panel) return;
    const host = target === "dashboard"
      ? $("termPanelMountDashboard")
      : (target === "custom" ? $("customShellPanelMount") : $("diagnosticsShellPanel"));
    if (host && panel.parentElement !== host) host.appendChild(panel);
    termPanelMount = target;
    const scopeNav = $("diagnosticsShellScopeNav");
    if (scopeNav) scopeNav.classList.toggle("hidden", target === "dashboard" || target === "custom");
    const titleEl = $("termPanelTitle");
    if (titleEl) {
      if (target === "dashboard") titleEl.textContent = "Nord shell";
      else if (target === "custom") {
        const scope = termCommandScope();
        const catLabel = quickCommandsSettingsDraft?.custom_categories
          ?.find((c) => scope === `custom:${c.id}`)?.label;
        titleEl.textContent = catLabel ? `${catLabel} shell` : "Custom shell";
      } else titleEl.textContent = termCommandScope() === "security" ? "Security shell" : "Networking shell";
    }
    syncTermCrossLink();
  }

  function termUiActive() {
    if (getActiveView() === "dashboard" && dashTab === "terminal") return true;
    if (getActiveView() === "terminal") return true;
    if (getActiveView() === "customShell" && toolsTab === "custom-shell") return true;
    return getActiveView() === "lab"
      && (hubTab === "diagnostics" || hubTab === "networking-shell" || hubTab === "security-shell")
      && diagnosticsPane === "shell";
  }

  function syncDiagnosticsHubPane() {
    localStorage.setItem(DIAGNOSTICS_TAB_KEY, "audit");
    $("auditSubnav")?.classList.add("hidden");
    $("overallAuditPanel")?.classList.add("hidden");
    $("auditLeakPanel")?.classList.add("hidden");
    $("auditDiagnosticsPanel")?.classList.remove("hidden");
    $("overallAuditPanel")?.classList.remove("active");
    $("auditLeakPanel")?.classList.remove("active");
    $("auditDiagnosticsPanel")?.classList.add("active");
  }

  function switchDiagnosticsPane(pane, opts = {}) {
    syncDiagnosticsHubPane();
    const id = pane === "shell" ? "shell" : (pane === "packages" ? "packages" : "checks");
    diagnosticsPane = id;
    localStorage.setItem(DIAG_PANE_KEY, id);
    $("diagnosticsSubnav")?.querySelectorAll("[data-diagnostics-pane]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-diagnostics-pane") === id);
    });
    $("diagnosticsChecksPanel")?.classList.toggle("hidden", id !== "checks");
    $("diagnosticsShellPanel")?.classList.toggle("hidden", id !== "shell");
    if (id === "shell") {
      if (opts.shellScope) syncDiagnosticsShellScope(opts.shellScope, { skipHash: true });
      termMountPanel("network");
      loadTerminal();
      termEnsureActiveLongPoll();
    } else {
      termPauseActiveLongPoll();
    }
    if (id === "packages") {
      navigateRoute("network", "network-packages", { skipHash: !!opts.skipHash, replaceHash: !!opts.replaceHash });
      return;
    }
    syncDiagnosticsSubnav();
    if (id === "shell") syncHubTabForDiagnosticsShell();
    if (!opts.skipHash) {
      let sub = null;
      if (id === "shell") sub = diagnosticsShellRouteSub(diagnosticsShellScope, activeTermId);
      else if (id === "packages") sub = "packages";
      syncRouteHash("network", "diagnostics", !!opts.replaceHash, sub);
    }
    syncPageIntro();
  }

  function syncLeakLabPane(mode) {
    const showLeak = mode === "leak" || mode === true;
    auditPane = showLeak ? "leak" : "full";
    localStorage.setItem(AUDIT_PANE_KEY, auditPane);
    localStorage.setItem(DIAGNOSTICS_TAB_KEY, showLeak ? "leak" : "overall");
    $("auditSubnav")?.classList.remove("hidden");
    $("auditSubnav")?.querySelectorAll("[data-audit-pane]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-audit-pane") === auditPane);
    });
    $("overallAuditPanel")?.classList.toggle("hidden", showLeak);
    $("auditLeakPanel")?.classList.toggle("hidden", !showLeak);
    $("auditDiagnosticsPanel")?.classList.add("hidden");
    $("overallAuditPanel")?.classList.toggle("active", !showLeak);
    $("auditLeakPanel")?.classList.toggle("active", showLeak);
    $("auditDiagnosticsPanel")?.classList.remove("active");
  }

  function switchAuditPane(pane, opts = {}) {
    const id = pane === "leak" ? "leak" : "full";
    if (id === "leak" && !opts.stayOnAuditTab) {
      switchHubTab("leak-tests", { skipHash: !!opts.skipHash, replaceHash: !!opts.replaceHash, fromHash: !!opts.fromHash });
      return;
    }
    syncLeakLabPane(id);
    if (id === "full") loadOverallAudit(false);
    else loadLab(false);
    syncAuditSubnav();
    if (!opts.skipHash) {
      syncRouteHash("network", "audit", !!opts.replaceHash, null);
    }
    syncPageIntro();
  }

  function initDiagnosticsSubnav() {
    $("diagnosticsSubnav")?.querySelectorAll("[data-diagnostics-pane]").forEach((btn) => {
      if (btn.dataset.diagBound) return;
      btn.dataset.diagBound = "1";
      btn.addEventListener("click", () => {
        switchDiagnosticsPane(btn.getAttribute("data-diagnostics-pane") || "checks");
      });
    });
  }

  function initAuditSubnav() {
    $("auditSubnav")?.querySelectorAll("[data-audit-pane]").forEach((btn) => {
      if (btn.dataset.auditBound) return;
      btn.dataset.auditBound = "1";
      btn.addEventListener("click", () => {
        switchAuditPane(btn.getAttribute("data-audit-pane") || "full");
      });
    });
    document.querySelectorAll("[data-audit-pane-jump]").forEach((btn) => {
      if (btn.dataset.auditJumpBound) return;
      btn.dataset.auditJumpBound = "1";
      btn.addEventListener("click", () => {
        switchAuditPane(btn.getAttribute("data-audit-pane-jump") || "leak");
      });
    });
    document.querySelectorAll("[data-diagnostics-pane-jump]").forEach((btn) => {
      if (btn.dataset.diagJumpBound) return;
      btn.dataset.diagJumpBound = "1";
      btn.addEventListener("click", () => {
        const pane = btn.getAttribute("data-diagnostics-pane-jump") || "packages";
        const shellScope = btn.getAttribute("data-diagnostics-shell-scope");
        switchDiagnosticsPane(pane, shellScope ? { shellScope } : undefined);
      });
    });
    $("diagnosticsShellScopeNav")?.querySelectorAll("[data-diagnostics-shell-scope]").forEach((btn) => {
      if (btn.dataset.shellScopeBound) return;
      btn.dataset.shellScopeBound = "1";
      btn.addEventListener("click", () => {
        const scope = btn.getAttribute("data-diagnostics-shell-scope") || "network";
        if (diagnosticsPane !== "shell") switchDiagnosticsPane("shell", { shellScope: scope, skipHash: true });
        else syncDiagnosticsShellScope(scope);
        loadTerminal(true);
      });
    });
  }

  function syncAuditSubnav() {
    const onAudit = getActiveView() === "lab" && hubTab === "audit";
    $("auditSubnav")?.classList.toggle("hidden", !onAudit);
    if (onAudit) {
      $("auditSubnav")?.querySelectorAll("[data-audit-pane]").forEach((b) => {
        b.classList.toggle("active", b.getAttribute("data-audit-pane") === auditPane);
      });
    }
  }

  function syncDiagnosticsSubnav() {
    const onDiag = getActiveView() === "lab"
      && (hubTab === "diagnostics" || hubTab === "networking-shell" || hubTab === "security-shell");
    $("diagnosticsSubnav")?.classList.toggle("hidden", !onDiag || hubTab !== "diagnostics");
  }

  function openNetworkTerminal(opts = {}) {
    const scope = opts.scope === "security" ? "security" : "network";
    const prefix = scope === "security" ? "security-shell" : "shell";
    const sub = opts.sub
      ? (String(opts.sub).startsWith("shell") || String(opts.sub).startsWith("security-shell")
        ? opts.sub
        : `${prefix}/${opts.sub}`)
      : prefix;
    const tab = scope === "security" ? "security-shell" : "networking-shell";
    const sess = opts.sub && !String(opts.sub).includes("/") ? opts.sub : null;
    navigateRoute("network", tab, { ...opts, sub: sess || sub.replace(/^(shell|security-shell)\/?/, "") || null });
  }

  function openNordTerminal(opts = {}) {
    if (opts.sub) pendingTermSessionId = opts.sub;
    navigateRoute("dashboard", "terminal", opts);
  }

  function termPreferredSessionId(scope) {
    const list = termSessionsForScope(scope);
    if (!list.length) return null;
    const saved = termLoadRegistry();
    let preferred = saved?.activeByScope?.[scope];
    if (preferred && list.some((s) => s.id === preferred)) return preferred;
    const alive = list.filter((s) => s.alive !== false);
    const pick = alive.length ? alive[alive.length - 1] : list[list.length - 1];
    return pick?.id || null;
  }

  function syncTermCrossLink() {
    const btn = $("btnTermCrossLink");
    if (!btn) return;
    if (!termUiActive()) {
      btn.classList.add("hidden");
      btn.hidden = true;
      return;
    }
    const onNord = termRouteSection() === "tools" || termRouteSection() === "dashboard";
    btn.hidden = false;
    btn.classList.remove("hidden");
    if (onNord) {
      const sid = termPreferredSessionId("network");
      btn.textContent = "Networking shell →";
      btn.title = sid
        ? `Open Networking → Networking shell (tab ${sid.slice(0, 8)}…)`
        : "Open Networking → Networking shell";
    } else {
      const sid = termPreferredSessionId("nord");
      btn.textContent = "Nord shell →";
      btn.title = sid
        ? `Open Nord Dashboard → Nord shell (tab ${sid.slice(0, 8)}…)`
        : "Open Nord Dashboard → Nord shell for NordVPN commands";
    }
  }

  function termJumpOtherTerminal() {
    const onNord = termRouteSection() === "tools" || termRouteSection() === "dashboard";
    if (onNord) {
      openNetworkTerminal({ scope: "network", sub: termPreferredSessionId("network") });
      return;
    }
    openNordTerminal({ sub: termPreferredSessionId("nord") });
  }

  function renderTermAccessNote(na) {
    const el = $("termAccessNote");
    if (!el) return;
    const nordScope = termCommandScope() === "nord";
    if (na?.lan_enabled) {
      el.innerHTML =
        "Interactive <strong>bash</strong> on this machine. "
        + `<strong class="msg warn">LAN access is ON</strong> — anyone who can open this dashboard can use this shell. `
        + `Switch to local-only in ${viewLink("advanced", "Network & Security → Services", "network-access")}.`;
      bindViewJumps(el);
    } else if (nordScope) {
      el.innerHTML =
        "Run nordvpn login here after top bar Wizard → Install NordVPN. Customize buttons in "
        + `<button type="button" class="btn sm jump-link" data-view-jump="settings/general/quick-commands">Settings → Quick commands</button>. `
        + "Local only (127.0.0.1).";
      bindViewJumps(el);
    } else if (String(termCommandScope()).startsWith("custom:")) {
      el.innerHTML =
        "Custom quick-command shell — edit buttons in "
        + `<button type="button" class="btn sm jump-link" data-view-jump="settings/general/quick-commands">Settings → Quick commands</button>. `
        + "Local only (127.0.0.1). Sudo prompts when needed.";
      bindViewJumps(el);
    } else {
      el.innerHTML =
        "Interactive bash on this machine — local only (127.0.0.1). Customize quick commands in "
        + `<button type="button" class="btn sm jump-link" data-view-jump="settings/general/quick-commands">Settings → Quick commands</button>. `
        + "Sudo prompts when needed. NordVPN login is on Nord Dashboard → Nord shell.";
      bindViewJumps(el);
    }
  }

  function decodeConfirmMessage(raw) {
    return String(raw || "").replace(/&#10;/g, "\n");
  }

  function initGlobalConfirm() {
    document.addEventListener("click", (e) => {
      const btn = e.target.closest("button");
      if (!btn || btn.disabled || btn.dataset.noConfirm === "1") return;
      /* Only confirm when explicitly marked — scans, refreshes, and navigation stay one-click. */
      if (btn.dataset.confirm !== "1" && !btn.dataset.confirmMessage) return;
      if (btn._skipConfirmOnce) {
        btn._skipConfirmOnce = false;
        return;
      }
      const custom = btn.dataset.confirmMessage;
      const label = (btn.getAttribute("title") || btn.textContent || "do this").trim().replace(/\s+/g, " ");
      const msg = custom ? decodeConfirmMessage(custom) : `Are you sure you want to ${label}?`;
      e.preventDefault();
      e.stopImmediatePropagation();
      if (confirm(msg)) {
        btn._skipConfirmOnce = true;
        btn.click();
      }
    }, true);
  }

  function markConfirm(btn, message) {
    if (!btn) return;
    btn.dataset.confirm = "1";
    if (message) btn.dataset.confirmMessage = message;
  }

  function setupCountryOptions(selected) {
    const sel = $("setupCountrySelect");
    if (!sel) return;
    const prev = selected || sel.value;
    sel.innerHTML = '<option value="">Pick your country…</option>';
    countries.forEach((c) => {
      const o = document.createElement("option");
      o.value = c;
      o.textContent = countryLabel(c);
      sel.appendChild(o);
    });
    if (prev) sel.value = prev;
  }

  async function saveSetupCountry() {
    const country = $("setupCountrySelect")?.value;
    const btn = $("btnSetupCountrySave");
    if (!country) {
      toast("Pick a country from the list", false);
      return;
    }
    if (btn) {
      btn.disabled = true;
      btn.textContent = "Saving…";
    }
    try {
      const res = await api("/api/action", {
        method: "POST",
        body: JSON.stringify({ action: "set_connect_country", country }),
        timeoutMs: 60000,
      });
      if (res.ok) {
        toast(res.note || "Country saved", true);
        hideNotice();
        lastState = { ...(lastState || {}), connect_country: country, doctor: res.doctor };
        if (res.doctor) renderDoctor(res.doctor);
        else {
          const d = await api("/api/doctor");
          renderDoctor(d);
        }
      } else {
        showNotice(res.error || "Could not save country", { ok: false, title: "Save country failed" });
      }
    } catch (e) {
      reportActionError("Save country failed", e, "Saving default country");
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.textContent = "Save country";
      }
    }
  }

  function formatFetchError(err, context) {
    const e = err?.name === "AbortError"
      ? `${context} timed out. Try again or restart nordctl serve.`
      : String(err || "Unknown error");
    if (e.includes("Failed to fetch") || e.includes("NetworkError")) {
      const cli = lastState?.cli?.service_restart || lastState?.cli?.bin || "~/.local/bin/nordctl";
      return [
        `${context} could not reach the nordctl server.`,
        "",
        "• Is nordctl serve still running? Check the terminal where you started it.",
        "• Hard-refresh this page (Ctrl+Shift+R).",
        `• Restart UI: ${cli} service restart`,
        `• Or start manually: ${lastState?.cli?.serve || cli + " serve"}`,
        lastState?.cli?.path_hint || "Add ~/.local/bin to PATH if commands are not found.",
      ].join("\n");
    }
    return e;
  }

  let suppressFetchErrorsUntil = 0;
  let stateFetchFailStreak = 0;

  function isFetchUnreachable(err) {
    const e = String(err?.message || err || "");
    return err?.name === "AbortError" || e.includes("Failed to fetch") || e.includes("NetworkError")
      || e.includes("invalid JSON") || e.includes("Empty reply");
  }

  function shouldSuppressFetchError() {
    return Date.now() < suppressFetchErrorsUntil;
  }

  function reportActionError(title, err, context, opts = {}) {
    const silent = opts.silent || shouldSuppressFetchError();
    const msg = formatFetchError(err, context || title);
    pushUiDiag({
      title,
      message: msg,
      source: context || title,
      hint: "Try Refresh, Reset UI cache (top right), or Ctrl+Shift+R",
    });
    if (silent) return;
    showNotice(msg, { ok: false, title, copyText: msg });
    toast(title + " failed", false);
  }

  function countryLabel(code) {
    return String(code || "").replace(/_/g, " ");
  }

  function populateCountryOptions(listEl, selectEl) {
    if (!listEl && !selectEl) return;
    const prev = selectEl?.value;
    if (listEl) listEl.innerHTML = "";
    if (selectEl) selectEl.innerHTML = '<option value="">Country…</option>';
    countries.forEach((c) => {
      if (listEl) {
        const o = document.createElement("option");
        o.value = c;
        o.label = countryLabel(c);
        listEl.appendChild(o);
      }
      if (selectEl) {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = countryLabel(c);
        selectEl.appendChild(o);
      }
    });
    if (selectEl && prev) selectEl.value = prev;
  }

  function bindCountryCityPair(countrySel, citySel, boundKey) {
    if (!countrySel || !citySel || countrySel.dataset[boundKey]) return;
    countrySel.dataset[boundKey] = "1";
    countrySel.addEventListener("change", () => loadCityOptions(countrySel, citySel));
  }

  function connectConnectTarget() {
    const city = $("connectCitySelect")?.value || "";
    if (city) return city;
    const country = $("connectCountrySelect")?.value || "";
    return country ? country.replace(/_/g, " ") : "";
  }

  function safeJsonStringify(value) {
    const seen = new WeakSet();
    return JSON.stringify(value, (_key, val) => {
      if (typeof val === "object" && val !== null) {
        if (seen.has(val)) return undefined;
        seen.add(val);
      }
      return val;
    });
  }

  async function api(path, opts = {}) {
    const timeoutMs = opts.timeoutMs;
    const { timeoutMs: _drop, ...fetchOpts } = opts;
    const controller = timeoutMs ? new AbortController() : null;
    const timer = controller ? setTimeout(() => controller.abort(), timeoutMs) : null;
    const headers = { ...(fetchOpts.headers || {}) };
    if (fetchOpts?.body && !headers["Content-Type"]) headers["Content-Type"] = "application/json";
    const token = sessionStorage.getItem(UI_TOKEN_KEY);
    if (token) headers["X-Nordctl-Token"] = token;
    try {
      const r = await fetch(path, {
        headers: Object.keys(headers).length ? headers : undefined,
        signal: controller?.signal,
        ...fetchOpts,
      });
      let data;
      try {
        data = await r.json();
      } catch (_) {
        throw new Error(`Server returned invalid JSON (HTTP ${r.status})`);
      }
      if (r.status === 401 && data?.auth_required) {
        showUiLogin(data.error || "Dashboard login required.");
      }
      if (!r.ok && data?.error == null) {
        data.error = data.error || `Request failed (HTTP ${r.status})`;
      }
      return data;
    } finally {
      if (timer) clearTimeout(timer);
    }
  }

  function notifyPermissionLabel() {
    if (typeof Notification === "undefined") return "Not supported in this browser";
    if (Notification.permission === "granted") return "Allowed";
    if (Notification.permission === "denied") return "Blocked — enable in browser site settings";
    return "Not asked yet — click Allow below";
  }

  function updateBellPermBadge() {
    const badge = $("bellPermBadge");
    if (!badge) return;
    const perm = typeof Notification !== "undefined" ? Notification.permission : "unsupported";
    badge.textContent = notifyPermissionLabel();
    badge.className = "badge " + (perm === "granted" ? "on" : perm === "denied" ? "off" : "");
  }

  function setBellBadge(count) {
    const el = $("bellBadge");
    if (!el) return;
    const n = Number(count) || 0;
    el.textContent = String(n);
    el.classList.toggle("hidden", n <= 0);
  }

  function toggleBellDropdown(show) {
    const dd = $("bellDropdown");
    const btn = $("btnAlertBell");
    if (!dd) return;
    const on = show ?? dd.classList.contains("hidden");
    dd.classList.toggle("hidden", !on);
    dd.hidden = !on;
    btn?.setAttribute("aria-expanded", on ? "true" : "false");
    btn?.classList.toggle("active", !!on);
    if (on) {
      updateBellPermBadge();
      positionBellDropdown();
    }
  }

  function positionBellDropdown() {
    const dd = $("bellDropdown");
    const btn = $("btnAlertBell");
    if (!dd || !btn || dd.classList.contains("hidden")) return;
    const r = btn.getBoundingClientRect();
    dd.style.top = `${Math.round(r.bottom + 8)}px`;
    dd.style.right = `${Math.round(window.innerWidth - r.right)}px`;
    dd.style.left = "auto";
  }

  function showUiLogin(msg) {
    const ov = $("uiLoginOverlay");
    if (!ov) return;
    ov.classList.remove("hidden");
    if ($("uiLoginError")) $("uiLoginError").textContent = msg || "";
  }

  function hideUiLogin() {
    $("uiLoginOverlay")?.classList.add("hidden");
    if ($("uiLoginError")) $("uiLoginError").textContent = "";
  }

  async function uiLoginSubmit() {
    const pwd = $("uiLoginPassword")?.value || "";
    const res = await api("/api/ui-auth/login", { method: "POST", body: JSON.stringify({ password: pwd }) });
    if (res.ok && res.token) {
      sessionStorage.setItem(UI_TOKEN_KEY, res.token);
      hideUiLogin();
      toast("Logged in", true);
      await loadState();
      return;
    }
    if ($("uiLoginError")) $("uiLoginError").textContent = res.error || "Login failed";
  }

  async function ensureUiAuth() {
    const st = await api("/api/ui-auth/status");
    if (!st.auth_required) {
      hideUiLogin();
      return true;
    }
    if (sessionStorage.getItem(UI_TOKEN_KEY)) {
      hideUiLogin();
      return true;
    }
    showUiLogin("Enter the dashboard password to continue.");
    return false;
  }

  async function requestBrowserNotify() {
    if (typeof Notification === "undefined") {
      toast("Browser notifications not supported", false);
      return Notification?.permission || "unsupported";
    }
    const p = Notification.permission === "default"
      ? await Notification.requestPermission()
      : Notification.permission;
    updateBellPermBadge();
    if ($("settingsNotifyPerm")) $("settingsNotifyPerm").textContent = notifyPermissionLabel();
    toast(`Notification permission: ${p}`, p === "granted");
    return p;
  }

  function renderBellHelp(lines) {
    const list = $("bellHelpList");
    if (!list) return;
    list.innerHTML = (lines || []).map((t) => `<li>${esc(t)}</li>`).join("");
  }

  async function initBellPanel() {
    try {
      const settings = await api("/api/settings");
      renderBellHelp(settings.bell_help || []);
    } catch (_) { /* ignore */ }
    updateBellPermBadge();
  }

  async function initBellPanel() {
    try {
      const settings = await api("/api/settings");
      renderBellHelp(settings.bell_help || []);
    } catch (_) { /* ignore */ }
    updateBellPermBadge();
  }

  const QUICK_COMMANDS_SCOPES = [
    { id: "network", label: "Networking shell" },
    { id: "security", label: "Security shell" },
    { id: "nord", label: "Nord shell (Dashboard)" },
    { id: "custom", label: "Custom categories" },
  ];

  function ensureQuickCommandsScopeBlock(scopeId) {
    if (!quickCommandsSettingsDraft) return null;
    quickCommandsSettingsDraft.scopes = quickCommandsSettingsDraft.scopes || {};
    if (!quickCommandsSettingsDraft.scopes[scopeId]) {
      quickCommandsSettingsDraft.scopes[scopeId] = { commands: [], using_defaults: true };
    }
    return quickCommandsSettingsDraft.scopes[scopeId];
  }

  function addQuickCommandToDraft(scopeId, catIndex = null) {
    if (!quickCommandsSettingsDraft) return;
    if (scopeId === "custom" || catIndex != null) {
      const cats = quickCommandsSettingsDraft.custom_categories || [];
      const cat = cats[Number(catIndex)];
      if (!cat) return;
      cat.commands = cat.commands || [];
      cat.commands.push({ label: "New command", cmd: "echo hello\n", enabled: true });
      return;
    }
    const block = ensureQuickCommandsScopeBlock(scopeId);
    if (!block) return;
    block.commands = block.commands || [];
    block.commands.push({ label: "New command", cmd: "echo hello\n", enabled: true });
    block.using_defaults = false;
  }

  function slugQuickCategoryLabel(label) {
    return String(label || "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 48) || "category";
  }

  function renderQuickCommandsScopeNav() {
    const nav = $("quickCommandsScopeNav");
    if (!nav || nav.dataset.rendered === "1") return;
    nav.innerHTML = QUICK_COMMANDS_SCOPES.map((s) =>
      `<button type="button" class="hub-subnav-btn${s.id === quickCommandsEditScope ? " active" : ""}" data-qc-scope="${esc(s.id)}">${esc(s.label)}</button>`,
    ).join("");
    nav.dataset.rendered = "1";
    nav.querySelectorAll("[data-qc-scope]").forEach((btn) => {
      btn.addEventListener("click", () => {
        collectQuickCommandsDraftFromDom();
        quickCommandsEditScope = btn.getAttribute("data-qc-scope") || "network";
        nav.querySelectorAll("[data-qc-scope]").forEach((b) => b.classList.toggle("active", b === btn));
        renderQuickCommandsSettingsEditor();
      });
    });
  }

  function qcCommandRowHtml(cmd, idx, scopeKey) {
    const on = cmd.enabled !== false;
    return `<div class="qc-command-row${on ? "" : " qc-command-row-off"}" data-qc-row="${idx}" data-qc-scope-key="${esc(scopeKey)}">
      <label class="qc-enable"><input type="checkbox" class="qc-enabled" ${on ? "checked" : ""} /><span>On</span></label>
      <label><span class="sr-only">Label</span><input type="text" class="qc-label" value="${esc(cmd.label || "")}" placeholder="Button label" maxlength="80" /></label>
      <label><span class="sr-only">Command</span><textarea class="qc-cmd" rows="2" placeholder="Shell command">${esc(String(cmd.cmd || "").replace(/\n$/, ""))}</textarea></label>
      <button type="button" class="btn sm qc-remove" title="Remove this command">Remove</button>
    </div>`;
  }

  function renderQuickCommandsSettingsEditor() {
    const root = $("quickCommandsSettingsRoot");
    const hint = $("quickCommandsSettingsHint");
    if (!root || !quickCommandsSettingsDraft) return;
    const scope = quickCommandsEditScope;
    if (scope === "custom") {
      const cats = quickCommandsSettingsDraft.custom_categories || [];
      root.innerHTML = cats.length
        ? cats.map((cat, ci) => {
          const rows = (cat.commands || []).map((c, ri) => qcCommandRowHtml(c, ri, `cat:${ci}`)).join("")
            || `<p class="help-text muted-inline">No commands — add one below.</p>`;
          return `<section class="qc-category-block" data-qc-cat-index="${ci}">
            <div class="qc-category-head">
              <input type="text" class="qc-cat-label" value="${esc(cat.label || "")}" placeholder="Category name (shown in Tools → Custom shell)" maxlength="80" />
              <input type="hidden" class="qc-cat-id" value="${esc(cat.id || "")}" />
              <button type="button" class="btn sm jump-link qc-open-shell" data-view-jump="tools/custom-shell/${esc(cat.id || "")}">Open shell</button>
              <button type="button" class="btn sm qc-cat-remove" title="Delete this category">Delete category</button>
            </div>
            <div class="qc-command-list">${rows}</div>
            <button type="button" class="btn sm qc-add-command" data-qc-cat-index="${ci}">Add command</button>
          </section>`;
        }).join("")
        : `<div class="page-empty"><strong>No custom categories</strong><p class="help-text">Press <strong>Add custom category</strong> below — each category gets its own shell under Tools → Custom shell.</p></div>`;
      if (hint) {
        hint.textContent = cats.length
          ? `${cats.length} custom categor${cats.length === 1 ? "y" : "ies"} — save, then open Tools → Custom shell to run them.`
          : "Custom categories are separate from Networking / Security / Nord shells.";
      }
    } else {
      const block = quickCommandsSettingsDraft.scopes?.[scope] || { commands: [], using_defaults: true };
      const rows = (block.commands || []).map((c, i) => qcCommandRowHtml(c, i, scope)).join("")
        || `<p class="help-text muted-inline">No commands in this list.</p>`;
      root.innerHTML = `<div class="settings-box">
        <p class="help-text settings-box-help">${block.using_defaults ? "Showing built-in defaults — edit and save to customize this list." : "Custom list saved in config.yaml — use Reset to restore built-in defaults."}</p>
        <div class="qc-command-list" data-qc-scope-list="${esc(scope)}">${rows}</div>
        <button type="button" class="btn sm qc-add-command" data-qc-scope="${esc(scope)}">Add command</button>
      </div>`;
      if (hint) {
        hint.textContent = scope === "nord"
          ? "These buttons appear on Nord Dashboard → Nord shell."
          : scope === "security"
            ? "These buttons appear on Security → Security shell (and Diagnostics shell when Security is selected)."
            : "These buttons appear on Networking → Networking shell (and Diagnostics shell when Networking is selected).";
      }
    }
    root.querySelectorAll(".qc-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        btn.closest(".qc-command-row")?.remove();
      });
    });
    root.querySelectorAll(".qc-add-command").forEach((btn) => {
      btn.addEventListener("click", () => {
        collectQuickCommandsDraftFromDom();
        const catIdx = btn.getAttribute("data-qc-cat-index");
        if (catIdx != null) addQuickCommandToDraft("custom", Number(catIdx));
        else addQuickCommandToDraft(btn.getAttribute("data-qc-scope") || quickCommandsEditScope);
        renderQuickCommandsSettingsEditor();
      });
    });
    root.querySelectorAll(".qc-cat-remove").forEach((btn) => {
      btn.addEventListener("click", () => {
        collectQuickCommandsDraftFromDom();
        const block = btn.closest(".qc-category-block");
        const idx = Number(block?.getAttribute("data-qc-cat-index"));
        if (!Number.isNaN(idx)) quickCommandsSettingsDraft.custom_categories.splice(idx, 1);
        renderQuickCommandsSettingsEditor();
      });
    });
    bindViewJumps(root);
  }

  function collectQuickCommandsDraftFromDom() {
    if (!quickCommandsSettingsDraft) return;
    const root = $("quickCommandsSettingsRoot");
    if (!root) return;
    if (quickCommandsEditScope === "custom") {
      const cats = [];
      root.querySelectorAll(".qc-category-block").forEach((block) => {
        const label = block.querySelector(".qc-cat-label")?.value?.trim() || "";
        let id = block.querySelector(".qc-cat-id")?.value?.trim() || slugQuickCategoryLabel(label);
        id = slugQuickCategoryLabel(id);
        const commands = [];
        block.querySelectorAll(".qc-command-row").forEach((row) => {
          const lbl = row.querySelector(".qc-label")?.value?.trim();
          const cmdRaw = row.querySelector(".qc-cmd")?.value?.trim();
          if (!lbl || !cmdRaw) return;
          commands.push({
            label: lbl,
            cmd: cmdRaw.endsWith("\n") ? cmdRaw : `${cmdRaw}\n`,
            enabled: !!row.querySelector(".qc-enabled")?.checked,
          });
        });
        if (label) cats.push({ id, label, commands });
      });
      quickCommandsSettingsDraft.custom_categories = cats;
      return;
    }
    const scope = quickCommandsEditScope;
    const list = root.querySelector(`[data-qc-scope-list="${scope}"]`) || root.querySelector(".qc-command-list");
    const commands = [];
    list?.querySelectorAll(".qc-command-row").forEach((row) => {
      const lbl = row.querySelector(".qc-label")?.value?.trim();
      const cmdRaw = row.querySelector(".qc-cmd")?.value?.trim();
      if (!lbl || !cmdRaw) return;
      commands.push({
        label: lbl,
        cmd: cmdRaw.endsWith("\n") ? cmdRaw : `${cmdRaw}\n`,
        enabled: !!row.querySelector(".qc-enabled")?.checked,
      });
    });
    quickCommandsSettingsDraft.scopes[scope] = {
      ...(quickCommandsSettingsDraft.scopes[scope] || {}),
      commands,
      using_defaults: false,
    };
  }

  async function loadQuickCommandsSettings(force = false) {
    try {
      const data = await apiCached("/api/terminal/quick-commands/settings", {}, force ? 0 : CACHE_TTL.tools);
      if (!data.ok) return;
      quickCommandsSettingsDraft = {
        scopes: data.scopes || {},
        custom_categories: (data.custom_categories || []).map((c) => ({ ...c, commands: [...(c.commands || [])] })),
      };
      for (const id of ["network", "security", "nord"]) ensureQuickCommandsScopeBlock(id);
      $("quickCommandsScopeNav") && delete $("quickCommandsScopeNav").dataset.rendered;
      renderQuickCommandsScopeNav();
      renderQuickCommandsSettingsEditor();
    } catch (e) {
      $("quickCommandsSettingsRoot") && ($("quickCommandsSettingsRoot").innerHTML = `<p class="help-text err">Could not load quick commands: ${esc(formatFetchError(e))}</p>`);
    }
  }

  function renderCustomShellCategoryNav(categories) {
    const nav = $("customShellCategoryNav");
    if (!nav) return;
    if (!categories.length) {
      nav.classList.add("hidden");
      nav.innerHTML = "";
      return;
    }
    nav.classList.remove("hidden");
    nav.innerHTML = categories.map((c) =>
      `<button type="button" class="hub-subnav-btn${c.id === customShellCategory ? " active" : ""}" data-custom-shell-cat="${esc(c.id)}">${esc(c.label || c.id)}</button>`,
    ).join("");
    nav.querySelectorAll("[data-custom-shell-cat]").forEach((btn) => {
      btn.addEventListener("click", () => {
        customShellCategory = btn.getAttribute("data-custom-shell-cat");
        localStorage.setItem("nordctl_custom_shell_cat", customShellCategory);
        syncRouteHash("tools", "custom-shell", false, customShellCategory);
        loadCustomShell();
      });
    });
  }

  async function loadCustomShell() {
    await loadQuickCommandsSettings(true);
    const cats = quickCommandsSettingsDraft?.custom_categories || [];
    const empty = $("customShellEmpty");
    const mount = $("customShellPanelMount");
    const badge = $("customShellBadge");
    if (badge) {
      badge.textContent = cats.length ? String(cats.length) : "Empty";
      badge.className = "badge " + (cats.length ? "on" : "off");
    }
    if (!cats.length) {
      empty?.classList.remove("hidden");
      mount?.classList.add("hidden");
      $("terminalPanel")?.classList.add("hidden");
      renderCustomShellCategoryNav([]);
      syncPageHow();
      return;
    }
    empty?.classList.add("hidden");
    mount?.classList.remove("hidden");
    $("terminalPanel")?.classList.remove("hidden");
    if (!customShellCategory || !cats.some((c) => c.id === customShellCategory)) {
      customShellCategory = cats[0].id;
      localStorage.setItem("nordctl_custom_shell_cat", customShellCategory);
      syncRouteHash("tools", "custom-shell", true, customShellCategory);
    }
    renderCustomShellCategoryNav(cats);
    await loadTerminal(true);
    syncPageHow();
  }

  function renderCustomPackagesCategoryNav(categories, data) {
    const nav = $("customPackagesCategoryNav");
    if (!nav) return;
    if (!categories.length) {
      nav.innerHTML = `<button type="button" class="hub-subnav-btn active" data-custom-packages-cat="miscellaneous">Miscellaneous</button>`;
      return;
    }
    nav.innerHTML = categories.map((c) => {
      const active = c.id === customPackagesCategory;
      const del = isCustomPackageCategoryDeletable(c)
        ? `<button type="button" class="btn xs danger custom-packages-cat-del" data-delete-custom-packages-cat="${esc(c.id)}" title="Delete this category and all packages in it">Delete</button>`
        : "";
      return `<span class="custom-packages-cat-item${active ? " active" : ""}">`
        + `<button type="button" class="hub-subnav-btn${active ? " active" : ""}" data-custom-packages-cat="${esc(c.id)}">${esc(c.label || c.id)} <span class="muted">(${c.total || 0})</span></button>`
        + del
        + `</span>`;
    }).join("");
    nav.querySelectorAll("[data-custom-packages-cat]").forEach((btn) => {
      btn.addEventListener("click", () => {
        customPackagesCategory = btn.getAttribute("data-custom-packages-cat");
        localStorage.setItem("nordctl_custom_packages_cat", customPackagesCategory);
        setPackageCategoryFilter("custom", customPackagesCategory);
        syncRouteHash("tools", "custom-packages", false, customPackagesCategory);
        if (toolsPayloadCache) {
          renderCustomPackagesCategoryNav(toolsPayloadCache?.groups?.custom?.categories || [], toolsPayloadCache);
          syncCustomPackagesCategoryDelete(toolsPayloadCache?.groups?.custom?.categories || []);
          renderHubToolCards(toolsPayloadCache, "custom", "customPackagesGrid", "customToolsHint");
        } else {
          loadCustomPackages(true);
        }
        syncPageHow();
      });
    });
    nav.querySelectorAll("[data-delete-custom-packages-cat]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        e.stopPropagation();
        const cid = btn.getAttribute("data-delete-custom-packages-cat");
        const cat = categories.find((c) => c.id === cid);
        if (!cat || !isCustomPackageCategoryDeletable(cat)) return;
        if (confirm(customPackageCategoryDeleteMessage(cat))) removePackageCategory(cid);
      });
    });
    syncCustomPackagesCategoryDelete(categories);
  }

  function customPackageCategoryDeleteMessage(cat) {
    const label = cat.label || cat.id;
    const n = cat.total || 0;
    const names = (cat.tools || []).map((t) => t.label || t.id).filter(Boolean);
    let pkgLine = "";
    if (n) {
      const list = names.slice(0, 8).map((name) => `• ${name}`).join("\n");
      const more = names.length > 8 ? `\n• …and ${names.length - 8} more` : "";
      pkgLine = `This permanently removes ${n} package entr${n === 1 ? "y" : "ies"} from config.yaml:\n\n${list}${more}\n\n`;
    } else {
      pkgLine = "This category has no packages — only the tab will be removed.\n\n";
    }
    return `Delete category “${label}”?\n\n${pkgLine}Installed apt packages are NOT uninstalled — only nordctl’s catalog entries are removed.\n\nThis cannot be undone.`;
  }

  function syncCustomPackagesCategoryDelete(categories) {
    const wrap = $("customPackagesCategoryActions");
    const btn = $("btnCustomPackagesCategoryDelete");
    if (!wrap || !btn) return;
    const cat = (categories || []).find((c) => c.id === customPackagesCategory);
    if (!cat || !isCustomPackageCategoryDeletable(cat)) {
      wrap.classList.add("hidden");
      delete btn.dataset.confirmMessage;
      delete btn.dataset.categoryId;
      return;
    }
    wrap.classList.remove("hidden");
    const n = cat.total || 0;
    btn.textContent = n
      ? `Delete “${cat.label || cat.id}” (${n} pkg)`
      : `Delete “${cat.label || cat.id}”`;
    btn.dataset.categoryId = cat.id;
    btn.dataset.confirmMessage = customPackageCategoryDeleteMessage(cat);
  }

  function populateCustomPackagesCategorySelect(data) {
    const sel = $("customPackagesToolCategory");
    const sections = data?.groups?.custom?.categories || [];
    if (!sel) return;
    sel.innerHTML = sections.map((s) =>
      `<option value="${esc(s.id)}">${esc(s.label)}</option>`,
    ).join("");
    const want = customPackagesCategory && sections.some((s) => s.id === customPackagesCategory)
      ? customPackagesCategory
      : (sections[0]?.id || "miscellaneous");
    sel.value = want;
  }

  async function loadCustomPackages(force = false) {
    const data = await loadHubTools(null, force);
    const group = data?.groups?.custom;
    const categories = group?.categories || [];
    const badge = $("customPackagesBadge");
    if (badge) {
      const total = group?.total || 0;
      const missing = group?.missing_count || 0;
      badge.textContent = total ? `${total} pkg` : "Empty";
      badge.className = "badge " + (total && !missing ? "on" : (total ? "off" : ""));
    }
    const prevCat = customPackagesCategory;
    if (!customPackagesCategory || !categories.some((c) => c.id === customPackagesCategory)) {
      customPackagesCategory = categories[0]?.id || "miscellaneous";
      localStorage.setItem("nordctl_custom_packages_cat", customPackagesCategory);
    }
    if (prevCat !== customPackagesCategory) {
      syncRouteHash("tools", "custom-packages", true, customPackagesCategory);
    }
    setPackageCategoryFilter("custom", customPackagesCategory);
    renderCustomPackagesCategoryNav(categories, data);
    syncCustomPackagesCategoryDelete(categories);
    populateCustomPackagesCategorySelect(data);
    if (data) renderHubToolCards(data, "custom", "customPackagesGrid", "customToolsHint");
    const hint = $("customPackagesHint");
    if (hint) {
      hint.textContent = categories.length
        ? `${categories.length} categor${categories.length === 1 ? "y" : "ies"} — packages install with the same apt UX as Networking and Security catalogs.`
        : "Add a category tab, then add apt packages below.";
    }
    syncPageHow();
    return data;
  }

  async function saveQuickCommandsSettings(resetScope = null) {
    collectQuickCommandsDraftFromDom();
    if (!quickCommandsSettingsDraft) await loadQuickCommandsSettings(true);
    collectQuickCommandsDraftFromDom();
    const body = {
      custom_categories: quickCommandsSettingsDraft.custom_categories || [],
      scopes: {},
    };
    for (const id of ["network", "security", "nord"]) {
      const block = quickCommandsSettingsDraft.scopes?.[id];
      if (resetScope === id) {
        body.scopes[id] = { reset_defaults: true };
      } else if (block && Array.isArray(block.commands)) {
        body.scopes[id] = { commands: block.commands };
      }
    }
    const res = await api("/api/terminal/quick-commands/settings", {
      method: "POST",
      body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(res.error || "Save failed");
    quickCommandsSettingsDraft = {
      scopes: res.scopes || {},
      custom_categories: res.custom_categories || [],
    };
    renderQuickCommandsSettingsEditor();
    if (termUiActive()) await termLoadQuickCommands(termCommandScope(), true);
    toast("Quick commands saved", true);
    return res;
  }

  async function loadSettingsPanel(force) {
    const profile = installProfile(lastState);
    initSettingsSubnav();
    const scopes = visibleSettingsScopes(profile);
    if (!scopes.includes(settingsScope)) {
      settingsScope = scopes[0];
      localStorage.setItem(SETTINGS_SCOPE_KEY, settingsScope);
    }
    const tabs = settingsTabsForScope(settingsScope, profile);
    if (!tabs.includes(settingsTab)) {
      settingsTab = defaultSettingsTab(settingsScope, profile);
      localStorage.setItem(SETTINGS_TAB_KEY, settingsTab);
    }
    renderSettingsTabNav(settingsScope, profile);
    const st = await apiCached("/api/settings", {}, force ? 0 : CACHE_TTL.security);
    if (!st.ok) return;
    const auth = st.ui_auth || {};
    const alerts = st.alerts || {};
    const svc = st.services || {};
    const cfg = st.config || {};
    const sd = cfg.smart_dns || {};
    const wifi = cfg.wifi || {};
    const wz = cfg.wifi_zones || {};
    const vd = cfg.vpn_defaults || {};
    const sp = cfg.service_prefs || {};
    const aa = cfg.alerts_advanced || {};
    const feats = cfg.features || {};
    if ($("settingsBadge")) {
      $("settingsBadge").textContent = auth.enabled ? "Password on" : "Open";
      $("settingsBadge").className = "badge " + (auth.enabled ? "on" : "");
    }
    if ($("uiAuthStatus")) {
      $("uiAuthStatus").textContent = auth.note || (auth.enabled ? "Password is set." : "No password — anyone with this URL can use the UI.");
    }
    if ($("settingsNotifyPerm")) $("settingsNotifyPerm").textContent = notifyPermissionLabel();
    if ($("settingsNotifyBadge")) {
      $("settingsNotifyBadge").textContent = alerts.browser_enabled ? "On" : "Off";
      $("settingsNotifyBadge").className = "badge " + (alerts.browser_enabled ? "on" : "off");
    }
    if ($("settingsBrowserAlerts")) $("settingsBrowserAlerts").checked = !!alerts.browser_enabled;
    if ($("settingsEmailAlerts")) $("settingsEmailAlerts").checked = !!alerts.email_enabled;
    if ($("settingsEmailTo")) $("settingsEmailTo").value = alerts.email_to || "";
    if ($("settingsSmtpHost")) $("settingsSmtpHost").value = alerts.smtp_host || "";
    if ($("settingsSmtpUser")) $("settingsSmtpUser").value = alerts.smtp_user || "";
    if ($("settingsSmtpPass")) {
      $("settingsSmtpPass").value = "";
      $("settingsSmtpPass").placeholder = alerts.smtp_password_set
        ? "•••••• (saved — leave blank to keep)"
        : "SMTP password (stored locally)";
    }
    const scanMail = alerts.scan_email || {};
    if ($("settingsScanEmailEnabled")) $("settingsScanEmailEnabled").checked = scanMail.enabled !== false;
    if ($("settingsScanEmailFindings")) $("settingsScanEmailFindings").checked = scanMail.email_on_findings !== false;
    if ($("settingsScanEmailFailure")) $("settingsScanEmailFailure").checked = scanMail.email_on_failure !== false;
    if ($("settingsScanEmailAlways")) $("settingsScanEmailAlways").checked = !!scanMail.email_always;
    if ($("settingsLynisMinScore")) $("settingsLynisMinScore").value = String(scanMail.lynis_min_score_alert ?? 65);
    if ($("settingsEmailHint")) {
      $("settingsEmailHint").textContent = alerts.email_configured
        ? "SMTP is configured — save to update recipient or rules."
        : "Enter your SMTP host and credentials below, then save. Use a dedicated app password if your provider requires it.";
    }
    const rules = alerts.rules || {};
    $("settingsNotifyRules") && ($("settingsNotifyRules").innerHTML = renderNotifyRules(rules, alerts.rule_descriptions));
    const watchOn = !!alerts.watch_running;
    const watchEnabled = alerts.watch_enabled !== false;
    $("settingsWatchStats") && ($("settingsWatchStats").innerHTML = [
      statCell("Background watch", watchOn ? "Running" : "Stopped", watchOn ? "on" : "off"),
      statCell("Configured", watchEnabled ? "Enabled" : "Disabled", watchEnabled ? "on" : "warn"),
      statCell("Check interval", `${alerts.watch_interval_seconds || 60}s`, ""),
    ].join(""));
    if ($("settingsAlertsPrivacyNote")) {
      $("settingsAlertsPrivacyNote").textContent = alerts.privacy_note || "";
    }
    try {
      const sec = await apiCached("/api/security/summary", {}, force ? 0 : CACHE_TTL.securitySummary);
      renderDisconnectWatchStats(sec?.disconnect_watch || {}, $("settingsDisconnectWatch"));
    } catch (_) { /* ignore */ }
    $("settingsSvcStats") && ($("settingsSvcStats").innerHTML = [
      statCell(
        "UI service",
        svc.ui_systemd ? "Running (systemd)" : (svc.ui_manual ? "Running (manual)" : "Stopped"),
        svc.ui_running ? "on" : "off"
      ),
      statCell("Autostart", svc.ui_enabled ? "Enabled" : "Disabled", svc.ui_enabled ? "on" : ""),
    ].join(""));
    renderBellHelp(st.bell_help || []);
    if (st.ui_prefs) applyUiPrefsFromConfig(st.ui_prefs);
    renderSettingsInterfacePanel(st.ui_prefs || uiPrefs);
    if (settingsTab === "quick-commands") await loadQuickCommandsSettings(!!force);
    if (st.locations) {
      if (lastState) lastState.locations = st.locations;
      renderLocationSettings(
        { locations: st.locations },
        { gridId: "settingsLocationsGrid", badgeId: "settingsLocationsBadge", hiddenId: "settingsLocationsHidden" },
      );
    }
    if (st.network_access) {
      renderNetworkAccess(st.network_access, {
        boxId: "settingsNetworkAccessBox",
        badgeId: null,
        applyBtnId: "btnSettingsNetAccessApply",
        customIpId: "settingsNetAccessCustomIp",
      });
    }
    if ($("settingsSmartDnsPrimary")) $("settingsSmartDnsPrimary").value = sd.primary || "";
    if ($("settingsSmartDnsSecondary")) $("settingsSmartDnsSecondary").value = sd.secondary || "";
    if ($("settingsWifiProfileCount")) {
      $("settingsWifiProfileCount").textContent = wifi.profile_count
        ? `${wifi.profile_count} profile(s): ${(wifi.profiles || []).slice(0, 3).join(", ")}${wifi.profile_count > 3 ? "…" : ""}`
        : "None — sync from WiFi hub";
    }
    if ($("settingsHomeIpLearn")) $("settingsHomeIpLearn").checked = wz.home_ip_learn !== false;
    if ($("settingsHomeIpWhenTrusted")) $("settingsHomeIpWhenTrusted").checked = wz.home_ip_when_trusted !== false;
    if ($("settingsZoneAutoApply")) $("settingsZoneAutoApply").checked = !!wz.auto_apply;
    if ($("settingsUntrustedPreset")) $("settingsUntrustedPreset").value = wz.untrusted_preset || "public-wifi";
    if ($("settingsWifiAutoSync")) $("settingsWifiAutoSync").checked = wifi.auto_sync_active !== false;
    if ($("settingsWifiHealDns")) $("settingsWifiHealDns").checked = wifi.heal_smart_dns !== false;
    if ($("settingsWifiProfileStats")) {
      $("settingsWifiProfileStats").innerHTML = [
        statCell("Device", wifi.device || "auto", wifi.device ? "on" : ""),
        statCell("Profiles", String(wifi.profile_count || 0), wifi.profile_count ? "on" : "off"),
        statCell("Zone watcher", wz.watch_enabled ? "On" : "Off", wz.watch_enabled ? "on" : "off"),
      ].join("");
    }
    if ($("settingsTrustedZonesList")) {
      const trusted = wz.trusted || [];
      $("settingsTrustedZonesList").innerHTML = trusted.length
        ? trusted.map((z) => `<div class="wifi-zone-row"><span><strong>${esc(z.ssid || z.name || "—")}</strong></span><span class="muted">${esc(z.preset || "—")}</span></div>`).join("")
        : "<p class=\"help-text muted-inline\">No trusted zones yet — add SSIDs under WiFi → Zones.</p>";
    }
    if ($("settingsLanCidr")) $("settingsLanCidr").value = vd.lan_allowlist_cidr || "";
    if ($("settingsVoipPorts")) $("settingsVoipPorts").value = (vd.voip_ports || []).join(", ");
    if ($("settingsAutoSnapshot")) $("settingsAutoSnapshot").checked = vd.auto_snapshot_before_preset !== false;
    if ($("settingsPublicIpUrl")) $("settingsPublicIpUrl").value = (cfg.probes || {}).public_ip_check_url || "";
    if ($("settingsNordvpnBin")) $("settingsNordvpnBin").value = vd.nordvpn_bin || "nordvpn";
    const hif = cfg.home_ip_fallback || {};
    if ($("settingsHomeIspFallbackEnabled")) $("settingsHomeIspFallbackEnabled").checked = !!hif.enabled;
    if ($("settingsHomeIspFallbackIp")) $("settingsHomeIspFallbackIp").value = hif.ip || "";
    if ($("settingsHomeIspStats")) {
      const homeChain = (lastState?.ip_info?.chain || []).find((x) => x.role === "home");
      const liveHome = homeChain?.ip || lastState?.ip_info?.external_ip || lastState?.ip_info?.home_ip || "—";
      $("settingsHomeIspStats").innerHTML = [
        statCell("Fallback", hif.enabled ? "On" : "Off", hif.enabled ? "on" : ""),
        statCell("Saved ISP", esc(hif.ip || "—"), hif.ip ? "on" : ""),
        statCell("Top bar Home now", esc(liveHome), homeChain?.source === "static_fallback" ? "warn" : ""),
      ].join("");
    }
    if ($("settingsNordAutostart")) $("settingsNordAutostart").checked = !!sp.nord_autostart;
    if ($("settingsTrayEnabled")) $("settingsTrayEnabled").checked = !!sp.tray_enabled;
    if ($("settingsTrayAutostart")) $("settingsTrayAutostart").checked = !!sp.tray_autostart;
    if ($("settingsWatchInterval")) $("settingsWatchInterval").value = String(aa.watch_interval || alerts.watch_interval_seconds || 60);
    if ($("settingsRateLimit")) $("settingsRateLimit").value = String(aa.rate_limit_minutes || 15);
    if ($("settingsHealthThreshold")) $("settingsHealthThreshold").value = String(aa.health_threshold || 50);
    if ($("settingsWizardStats")) {
      $("settingsWizardStats").innerHTML = [
        statCell("Legal", feats.legal_accepted ? "Accepted" : "Pending", feats.legal_accepted ? "on" : "warn"),
        statCell("Wizard", feats.setup_wizard_complete ? "Complete" : "Incomplete", feats.setup_wizard_complete ? "on" : "off"),
        statCell("Profile", cfg.install_profile || "auto", ""),
      ].join("");
    }
    renderSettingsSpeedTestPanel(cfg.speedtest || {});
    switchSettingsTab(settingsScope, settingsTab, { skipHash: true });
    updateSettingsChrome(settingsScope, profile);
  }

  async function saveSettingsConfigSection(section, payload, label) {
    const res = await doAction({ action: "settings_config_save", section, ...payload }, label || "Settings");
    if (res.ok) {
      invalidateApiCache("/api/settings");
      invalidateApiCache("/api/speedtest/providers");
      speedLabProvidersLoaded = false;
      await loadSettingsPanel(true);
    }
    return res;
  }

  let settingsSpeedMirrors = [];

  function renderSettingsSpeedMirrorRows() {
    const box = $("settingsSpeedMirrorsList");
    if (!box) return;
    if (!settingsSpeedMirrors.length) {
      box.innerHTML = '<p class="help-text muted-inline">No custom mirrors yet — add your own download URL (office, ISP, datacenter).</p>';
      return;
    }
    box.innerHTML = settingsSpeedMirrors.map((row, idx) => `
      <div class="settings-speed-mirror-row" data-mirror-idx="${idx}">
        <label class="settings-field"><span class="settings-field-label">Id</span><input type="text" data-mirror-field="id" value="${esc(row.id || "")}" placeholder="my-office" /></label>
        <label class="settings-field"><span class="settings-field-label">Label</span><input type="text" data-mirror-field="label" value="${esc(row.label || "")}" placeholder="My office (EU)" /></label>
        <label class="settings-field settings-field-wide"><span class="settings-field-label">Download URL</span><input type="url" data-mirror-field="url" value="${esc(row.url || "")}" placeholder="https://mirror.example/files/{mb}MB.bin" /></label>
        <label class="settings-field"><span class="settings-field-label">Region</span><input type="text" data-mirror-field="region" value="${esc(row.region || "custom")}" placeholder="eu-west" /></label>
        <button type="button" class="btn sm danger settings-mirror-remove" data-mirror-remove="${idx}" title="Remove mirror">Remove</button>
      </div>
    `).join("");
    box.querySelectorAll("[data-mirror-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const i = Number(btn.getAttribute("data-mirror-remove"));
        settingsSpeedMirrors = settingsSpeedMirrors.filter((_, j) => j !== i);
        renderSettingsSpeedMirrorRows();
      });
    });
  }

  function collectSettingsSpeedMirrors() {
    const box = $("settingsSpeedMirrorsList");
    if (!box) return [];
    return [...box.querySelectorAll(".settings-speed-mirror-row")].map((row) => ({
      id: row.querySelector('[data-mirror-field="id"]')?.value?.trim() || "",
      label: row.querySelector('[data-mirror-field="label"]')?.value?.trim() || "",
      url: row.querySelector('[data-mirror-field="url"]')?.value?.trim() || "",
      region: row.querySelector('[data-mirror-field="region"]')?.value?.trim() || "custom",
    })).filter((r) => r.id && r.url);
  }

  function renderSettingsSpeedTestPanel(st) {
    st = st || {};
    settingsSpeedMirrors = Array.isArray(st.custom_mirrors) ? st.custom_mirrors.map((m) => ({ ...m })) : [];
    const provSel = $("settingsSpeedDefaultProvider");
    const profSel = $("settingsSpeedDefaultProfile");
    const methSel = $("settingsSpeedDefaultMethod");
    if (provSel && st.builtin_providers) {
      const prev = provSel.value;
      const ids = Object.keys(st.builtin_providers);
      provSel.innerHTML = ids.map((id) =>
        `<option value="${esc(id)}">${esc(st.builtin_providers[id])}</option>`
      ).join("");
      const pick = st.default_provider && st.builtin_providers[st.default_provider] ? st.default_provider : prev;
      provSel.value = st.builtin_providers[pick] ? pick : "auto";
    }
    if (profSel && st.profiles) {
      profSel.innerHTML = Object.entries(st.profiles).map(([id, label]) =>
        `<option value="${esc(id)}">${esc(label)}</option>`
      ).join("");
      profSel.value = st.profiles[st.default_profile] ? st.default_profile : "standard";
    }
    if (methSel) methSel.value = st.default_method || "single";
    if ($("settingsSpeedWarmup")) $("settingsSpeedWarmup").checked = !!st.warmup;
    if ($("settingsSpeedSaveResults")) $("settingsSpeedSaveResults").checked = st.save_results !== false;
    renderSettingsSpeedMirrorRows();
  }

  function applySpeedLabDefaults(data) {
    if (!data?.defaults || speedLabProviderManual) return;
    const d = data.defaults;
    if ($("speedLabProfile") && data.profiles?.[d.default_profile]) {
      $("speedLabProfile").value = d.default_profile;
    }
    if ($("speedLabMethod")) $("speedLabMethod").value = d.default_method || "single";
    if ($("speedLabWarmup")) $("speedLabWarmup").checked = !!d.warmup;
    if (data.providers?.[d.default_provider]) {
      renderSpeedLabProviderOptions(data, { forcePick: d.default_provider });
    }
  }

  function setBusy(on) {
    busy = on;
    document.querySelectorAll(".btn, .nav-pill, .icon-btn").forEach((b) => { b.disabled = on; });
  }

  function toast(msg, ok = true, ms = 4500) {
    const el = $("toast");
    if (!el) return;
    el.textContent = msg;
    el.className = "toast " + (ok ? "ok" : "err");
    el.classList.remove("hidden");
    clearTimeout(toast._t);
    toast._t = setTimeout(() => el.classList.add("hidden"), ms);
  }

  let html2canvasLoadPromise = null;

  function loadHtml2Canvas() {
    if (window.html2canvas) return Promise.resolve(window.html2canvas);
    if (html2canvasLoadPromise) return html2canvasLoadPromise;
    html2canvasLoadPromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js";
      s.async = true;
      s.onload = () => {
        if (window.html2canvas) resolve(window.html2canvas);
        else reject(new Error("html2canvas unavailable"));
      };
      s.onerror = () => reject(new Error("Could not load snapshot library"));
      document.head.appendChild(s);
    });
    return html2canvasLoadPromise;
  }

  function downloadBlob(blob, filename) {
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.rel = "noopener";
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  }

  async function takeFullscreenSnapshot() {
    const app = document.querySelector(".app");
    if (!app) {
      toast("Snapshot target not found", false);
      return;
    }
    $("bellDropdown")?.classList.add("hidden");
    $("bellDropdown")?.setAttribute("hidden", "");
    const hadFullscreen = !!document.fullscreenElement;
    let enteredFullscreen = false;
    setBusy(true);
    try {
      if (!hadFullscreen && app.requestFullscreen) {
        await app.requestFullscreen();
        enteredFullscreen = true;
        await new Promise((r) => setTimeout(r, 220));
      }
      const html2canvas = await loadHtml2Canvas();
      const canvas = await html2canvas(app, {
        backgroundColor: null,
        scale: Math.min(2, window.devicePixelRatio || 1),
        useCORS: true,
        logging: false,
        ignoreElements: (node) => {
          if (!node?.classList) return false;
          return node.id === "toast"
            || node.classList.contains("toast")
            || node.classList.contains("modal-backdrop")
            || node.classList.contains("confirm-backdrop");
        },
      });
      const blob = await new Promise((resolve, reject) => {
        canvas.toBlob((b) => (b ? resolve(b) : reject(new Error("PNG export failed"))), "image/png", 0.92);
      });
      const stamp = new Date().toISOString().replace(/[:.]/g, "-").slice(0, 19);
      downloadBlob(blob, `nordctl-snapshot-${stamp}.png`);
      toast("Full screen snapshot saved");
      logActivity("ui_snapshot", "Dashboard PNG saved", true);
    } catch (e) {
      toast(String(e?.message || e || "Snapshot failed"), false);
      logActivity("ui_snapshot", String(e?.message || e || "Snapshot failed"), false);
    } finally {
      if (enteredFullscreen && document.fullscreenElement) {
        try { await document.exitFullscreen(); } catch (_) { /* ignore */ }
      }
      setBusy(false);
    }
  }

  let noticeCopyText = "";

  function hideNotice() {
    $("noticePanel")?.classList.add("hidden");
    hideNoticeSetup();
  }

  function hideNoticeSetup() {
    $("noticeSetup")?.classList.add("hidden");
    if ($("noticeSetup")) $("noticeSetup").innerHTML = "";
  }

  function showNotice(text, opts = {}) {
    const panel = $("noticePanel");
    const body = $("noticeBody");
    const title = $("noticeTitle");
    if (!panel || !body) {
      toast(String(text || "").slice(0, 160), opts.ok !== false);
      return;
    }
    const msg = String(text || "").trim();
    noticeCopyText = String(opts.copyText || msg).trim();
    if (title) title.textContent = opts.title || (opts.ok === false ? "Action needed" : "Notice");
    if (opts.setupHtml) {
      body.innerHTML = opts.messageHtml || "";
      const setup = $("noticeSetup");
      if (setup) {
        setup.innerHTML = opts.setupHtml;
        setup.classList.remove("hidden");
        bindViewJumps(setup);
        bindLocationFieldHandlers(setup);
      }
    } else {
      hideNoticeSetup();
      if (opts.html) {
        body.innerHTML = msg;
        bindViewJumps(body);
        bindOpenUrlButtons(body);
      } else {
        body.textContent = msg;
      }
    }
    panel.className = "notice-panel " + (opts.ok === false ? "err" : "ok");
    panel.classList.remove("hidden");
    $("noticeCopy")?.classList.toggle("hidden", !noticeCopyText);
  }

  function copyNoticeText() {
    if (!noticeCopyText) return;
    navigator.clipboard?.writeText(noticeCopyText).then(
      () => toast("Copied to clipboard", true),
      () => showNotice(noticeCopyText, { title: "Copy manually", copyText: noticeCopyText, ok: false })
    );
  }

  function initNoticePanel() {
    $("noticeClose")?.addEventListener("click", hideNotice);
    $("noticeDismiss")?.addEventListener("click", hideNotice);
    $("noticeCopy")?.addEventListener("click", copyNoticeText);
  }

  function showMsg(text, ok) {
    const el = $("actionMsg");
    if (!el) return;
    el.textContent = text || "";
    el.className = "msg" + (text ? (ok ? " ok" : " err") : "");
  }

  /* ── Theme ── */
  function applyTheme(theme) {
    document.documentElement.dataset.theme = theme;
    localStorage.setItem(THEME_KEY, theme);
    const btn = $("btnTheme");
    if (btn) btn.textContent = theme === "light" ? "☾" : "☀";
  }

  function initTheme() {
    applyTheme(localStorage.getItem(THEME_KEY) || "dark");
  }

  /* ── Activity log ── */
  function logActivity(type, message, ok = true, detail = "", technical = "") {
    api("/api/logs/append", {
      method: "POST",
      body: JSON.stringify({ type, message, ok, detail, technical }),
    }).then(() => {
      loadLogsQuiet();
    }).catch(() => {});
  }

  function logEntryExportText(e) {
    const parts = [
      `[${e.ts || ""}] ${(e.category || "system").toUpperCase()} — ${e.title || "Event"}`,
      `Status: ${e.ok && e.level !== "error" ? "OK" : "Problem"}`,
    ];
    if (e.detail) parts.push("", e.detail);
    if (e.technical) parts.push("", "--- output ---", e.technical);
    if (e.meta && Object.keys(e.meta).length) {
      parts.push("", "--- meta ---", JSON.stringify(e.meta, null, 2));
    }
    return parts.join("\n");
  }

  function downloadTextFile(filename, text) {
    const blob = new Blob([text], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  }

  async function sharePreset(p) {
    const id = p?.id;
    if (!id) return toast("Preset has no id", false);
    try {
      const res = await api(`/api/presets/export?id=${encodeURIComponent(id)}`);
      if (!res.ok) return toast(res.error || "Export failed", false);
      const content = res.content || "";
      const filename = res.filename || `${id}.yaml`;
      try {
        await navigator.clipboard.writeText(content);
        toast(`Copied “${p.label || id}” YAML — paste to share`, true);
      } catch (_) {
        showNotice("Copy the YAML below to share this preset.", {
          title: `Share: ${p.label || id}`,
          copyText: content,
          ok: true,
        });
      }
      downloadTextFile(filename, content);
    } catch (e) {
      toast(formatFetchError(e, "Share preset"), false);
    }
  }

  async function savePresetYamlToMyPresets(yaml, labelHint) {
    const text = String(yaml || "").trim();
    if (!text) return toast("Nothing to save", false);
    const res = await doAction({ action: "import_preset_yaml", yaml: text }, "Save to My presets");
    if (res.ok) {
      toast(res.note || `Saved “${res.label || labelHint || "preset"}” to My presets`, true);
      loadCommunityPresets();
      loadState(true);
    }
    return res;
  }

  async function savePresetToMyPresets(p) {
    const id = typeof p === "string" ? p : p?.id;
    if (!id) return toast("Preset has no id", false);
    if (p?.user) {
      toast(`“${p.label || id}” is already in My presets`, true);
      return { ok: true };
    }
    const res = await doAction({ action: "save_preset_to_my_presets", id }, "Save to My presets");
    if (res.ok) {
      toast(res.note || `Saved “${res.label || id}” to My presets`, true);
      loadCommunityPresets();
      loadState(true);
    }
    return res;
  }

  async function importSharedPreset(opts = {}) {
    const urlEl = $(opts.urlId || "presetImportUrl");
    const yamlEl = $(opts.yamlId || "presetImportYaml");
    const url = String(urlEl?.value || "").trim();
    const yaml = String(yamlEl?.value || "").trim();
    if (!url && !yaml) return toast("Paste YAML or a URL to a preset file", false);
    const body = url ? { action: "import_preset_yaml", url } : { action: "import_preset_yaml", yaml };
    const res = await doAction(body, "Import preset");
    if (res.ok) {
      if (urlEl) urlEl.value = "";
      if (yamlEl) yamlEl.value = "";
      loadCommunityPresets();
      loadState(true);
      toast(res.note || `Imported “${res.label || res.id}” — see My presets`, true);
      if (opts.jumpToPresets) navigateRoute("dashboard", "workflows", { sub: "my-presets" });
    }
    return res;
  }

  async function importPresetFromLocalFile(file) {
    if (!file) return;
    const name = String(file.name || "").toLowerCase();
    if (name && !(name.endsWith(".yaml") || name.endsWith(".yml"))) {
      toast("Pick a .yaml or .yml file", false);
      return;
    }
    try {
      const text = await file.text();
      const yamlEl = $("presetImportYaml");
      if (yamlEl && !String(yamlEl.value || "").trim()) yamlEl.value = text;
      return await importSharedPreset({ jumpToPresets: false });
    } catch (e) {
      toast(formatFetchError(e, "Import file"), false);
    }
  }

  function exportLogEntry(e) {
    if (!e) return;
    const slug = String(e.title || "log").replace(/[^\w]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 36) || "log";
    downloadTextFile(`nordctl-log-${slug}.txt`, logEntryExportText(e));
    toast("Log entry exported", true);
  }

  function exportAllLogEntries() {
    if (!cachedLogEntries.length) {
      toast("No log entries to export", false);
      return;
    }
    const stamp = new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-");
    const body = cachedLogEntries.map((e, i) => `=== Entry ${i + 1} ===\n${logEntryExportText(e)}`).join("\n\n");
    downloadTextFile(`nordctl-activity-log-${stamp}.txt`, body);
    toast(`Exported ${cachedLogEntries.length} entries`, true);
  }

  function logScanPreview(e) {
    const tech = String(e.technical || "");
    if (!tech.trim()) return "";
    const blob = `${e.title || ""} ${tech}`.toLowerCase();
    if (blob.includes("lynis")) {
      const score = tech.match(/hardening index\s*:\s*\[?\s*(\d+)/i);
      const sugg = tech.match(/suggestion[s]?\s*:\s*(\d+)/i);
      const bits = [];
      if (score) bits.push(`Hardening index: <strong>${esc(score[1])}</strong>`);
      if (sugg) bits.push(`Suggestions: <strong>${esc(sugg[1])}</strong>`);
      if (bits.length) return `<div class="log-scan-summary">${bits.join(" · ")}</div>`;
    }
    if (/rkhunter|chkrootkit|clamscan|rootkit/i.test(blob)) {
      const warnings = tech.match(/warning/gi);
      const infected = tech.match(/infected|found/i);
      if (warnings?.length) {
        return `<div class="log-scan-summary">${warnings.length} warning line(s) — expand output for full report.</div>`;
      }
      if (infected) return `<div class="log-scan-summary">Scan mentions findings — expand output for details.</div>`;
    }
    const lines = tech.split("\n").map((l) => l.trim()).filter(Boolean);
    if (!lines.length) return "";
    const preview = lines.slice(0, 5).join("\n");
    return `<pre class="log-output-preview mono">${esc(preview)}${lines.length > 5 ? "\n…" : ""}</pre>`;
  }

  function logTechnicalBlock(e, expanded) {
    const tech = String(e.technical || "").trim();
    if (!tech) return "";
    const open = expanded ? " open" : "";
    const label = (e.category === "scan" || /lynis|rkhunter|chkrootkit|clam|audit|scan/i.test(`${e.title} ${tech}`))
      ? "Full scan output"
      : "Technical output";
    return `<details class="log-tech"${open}><summary>${label} (${tech.split("\n").length} lines)</summary><pre class="mono log-tech-pre">${esc(tech)}</pre></details>`;
  }

  function renderMiniLog(entries) {
    const box = $("logList");
    if (!box) return;
    const slice = (entries || cachedLogEntries).slice(0, 5);
    if (!slice.length) {
      box.innerHTML = '<div class="log-empty">Actions will appear here</div>';
      return;
    }
    box.innerHTML = slice.map((e) => renderLogCard(e, true)).join("");
  }

  function renderLogCard(e, mini) {
    const icon = LOG_CATEGORY_META[e.category] || "•";
    const cls = e.ok && e.level !== "error" ? "ok" : "err";
    const ts = e.ts ? new Date(e.ts).toLocaleString() : "";
    const cat = esc(e.category || "system");
    const hasTech = !!(e.technical && String(e.technical).trim());
    const scanLike = e.category === "scan" || /lynis|rkhunter|chkrootkit|clamscan|audit/i.test(`${e.title} ${e.detail || ""}`);
    if (mini) {
      return `<div class="log-entry ${cls}"><time>${esc(ts)}</time><strong>${icon} ${esc(e.title)}</strong><span class="log-detail">${esc(e.detail || "")}</span></div>`;
    }
    const preview = hasTech ? logScanPreview(e) : "";
    const tech = hasTech ? logTechnicalBlock(e, scanLike) : "";
    const exportBtn = e.id
      ? `<button type="button" class="btn sm log-export-btn" data-log-export="${esc(e.id)}" title="Download this entry as a text file">Export</button>`
      : "";
    return `<article class="log-card ${cls}${scanLike ? " log-card-scan" : ""}" data-log-id="${esc(e.id || "")}">
      <div class="log-card-head">
        <span class="log-card-icon">${icon}</span>
        <div class="log-card-copy">
          <strong>${esc(e.title)}</strong>
          <time>${esc(ts)}</time>
        </div>
        <span class="badge log-cat-badge">${cat}</span>
        ${exportBtn}
      </div>
      <p class="log-card-detail">${esc(e.detail || "No extra detail.")}</p>${preview}${tech}</article>`;
  }

  function wireLogCardActions(listEl) {
    if (!listEl || listEl.dataset.logActionsBound) return;
    listEl.dataset.logActionsBound = "1";
    listEl.addEventListener("click", (ev) => {
      const btn = ev.target.closest("[data-log-export]");
      if (!btn) return;
      ev.preventDefault();
      ev.stopPropagation();
      const id = btn.getAttribute("data-log-export");
      const entry = cachedLogEntries.find((x) => String(x.id) === String(id));
      if (entry) exportLogEntry(entry);
    });
  }

  function updateLogBadge(entries) {
    const badge = $("logBadge");
    if (!badge) return;
    const errs = (entries || cachedLogEntries).filter((e) => !e.ok || e.level === "error").length;
    if (errs > 0) {
      badge.textContent = String(Math.min(errs, 9));
      badge.classList.remove("hidden");
    } else {
      badge.classList.add("hidden");
    }
  }

  function renderLogsFilters(categories) {
    const box = $("logsFilters");
    if (!box) return;
    const items = [{ id: "all", label: "All", icon: "📋" }, ...(categories || []).map((c) => ({ id: c.id, label: c.label, icon: c.icon }))];
    box.innerHTML = items.map((f) =>
      `<button type="button" class="btn sm logs-filter${logsFilter === f.id ? " active" : ""}" data-log-filter="${esc(f.id)}">${f.icon || ""} ${esc(f.label)}</button>`
    ).join("");
    box.querySelectorAll(".logs-filter").forEach((btn) => {
      btn.addEventListener("click", () => {
        logsFilter = btn.getAttribute("data-log-filter") || "all";
        loadLogs();
      });
    });
  }

  function renderLogs(data) {
    cachedLogEntries = data?.entries || [];
    renderMiniLog(cachedLogEntries);
    updateLogBadge(cachedLogEntries);
    const errN = cachedLogEntries.filter((e) => !e.ok || e.level === "error").length;
    $("logsIntro") && data?.intro && ($("logsIntro").textContent = data.intro);
    $("logsCountBadge") && ($("logsCountBadge").textContent = `${cachedLogEntries.length} shown`);
    const limit = getLogsDisplayLimit();
    $("logsShownHint") && ($("logsShownHint").textContent = `Showing last ${limit} (max ${LOGS_LIMIT_MAX})`);
    const limitInput = $("logsLimitInput");
    if (limitInput && document.activeElement !== limitInput) limitInput.value = String(limit);
    if ($("logsMetrics")) {
      const filterLabel = logsFilter === "all" ? "All" : logsFilter;
      const scanN = cachedLogEntries.filter((e) => e.category === "scan" || /lynis|rkhunter|scan/i.test(e.title || "")).length;
      $("logsMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Entries</div><div class="val">${cachedLogEntries.length}</div><div class="sub">Most recent first</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Problems</div><div class="val ${errN ? "warn" : "on"}">${errN}</div><div class="sub">Failed or error level</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Scans</div><div class="val">${scanN}</div><div class="sub">With expandable output</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Limit</div><div class="val">${limit}</div><div class="sub">Up to ${LOGS_LIMIT_MAX} entries</div></div>`,
      ].join("");
    }
    $("logsPath") && ($("logsPath").textContent = data?.path ? `Activity file: ${data.path}` : "");
    renderLogsFilters(data?.categories);
    const nord = showNordFeatures(lastState);
    $("connJournalSection")?.classList.toggle("hidden", !nord);
    const list = $("logsList");
    if (!list) return;
    if (!cachedLogEntries.length) {
      const empty = nord
        ? "Run a scan, install a package, connect VPN, or open Diagnostics → Shell."
        : "Run Lynis or rkhunter from Security → Packages, use Diagnostics → Shell, or change UFW rules.";
      list.innerHTML = `<div class="page-empty"><strong>No activity yet</strong>${esc(empty)}</div>`;
      return;
    }
    list.innerHTML = cachedLogEntries.map((e) => renderLogCard(e, false)).join("");
    wireLogCardActions(list);
    drawLogsActivityChart(cachedLogEntries);
  }

  async function loadLogsQuiet() {
    try {
      const cat = logsFilter === "all" ? "" : logsFilter;
      const limit = getLogsDisplayLimit();
      const url = `/api/logs?limit=${limit}${cat ? `&category=${encodeURIComponent(cat)}` : ""}`;
      const data = await api(url);
      renderLogs(data);
    } catch { /* ignore */ }
  }

  async function loadLogs() {
    const list = $("logsList");
    if (list) list.innerHTML = '<div class="page-empty"><strong>Loading…</strong></div>';
    await Promise.all([loadLogsQuiet(), loadConnJournal()]);
  }

  function stopLogsLive() {
    if (logsLiveTimer) {
      clearInterval(logsLiveTimer);
      logsLiveTimer = null;
    }
  }

  function startLogsLive() {
    stopLogsLive();
    if (!$("logsLive")?.checked) return;
    logsLiveTimer = setInterval(loadLogsQuiet, 10000);
  }

  const TERM_STORE_KEY = "nordctl_term_sessions";
  const termSessions = new Map();
  const termReservedLabels = new Set();
  let termQuickCommands = [];
  let pendingTermSessionId = null;
  let activeTermId = null;
  let termBgPollTimer = null;
  let termLongPollChain = false;
  let termLongPollActive = false;
  let termResizeObs = null;
  let termSudoActive = false;

  function termInferScope(label) {
    const l = String(label || "").trim();
    if (/^nordctl\b|^nordvpn\b/i.test(l)) return "nord";
    if (["nordctl status", "nordctl doctor", "nordctl leaklab", "nordvpn status", "nordvpn login", "nordvpn settings"].includes(l)) {
      return "nord";
    }
    return "network";
  }

  function termSessionScope(sess) {
    if (sess?.scope?.startsWith("custom:")) return sess.scope;
    if (sess?.scope === "nord") return "nord";
    if (sess?.scope === "security") return "security";
    if (sess?.scope === "network") return "network";
    return termInferScope(sess?.label);
  }

  function termSessionsForScope(scope) {
    const want = scope || termCommandScope();
    return [...termSessions.values()].filter((s) => termSessionScope(s) === want);
  }

  function termEnsureScopedActive(scope) {
    const list = termSessionsForScope(scope);
    const saved = termLoadRegistry();
    let preferred = pendingTermSessionId;
    if (preferred && (!termSessions.has(preferred) || termSessionScope(termSessions.get(preferred)) !== scope)) {
      preferred = null;
    }
    if (!preferred && saved?.activeByScope?.[scope] && list.some((s) => s.id === saved.activeByScope[scope])) {
      preferred = saved.activeByScope[scope];
    }
    if (!preferred && saved?.active && list.some((s) => s.id === saved.active)) {
      preferred = saved.active;
    }
    if (preferred && list.some((s) => s.id === preferred)) {
      activeTermId = preferred;
    } else if (!activeTermId || !list.some((s) => s.id === activeTermId)) {
      activeTermId = list[0]?.id || null;
    }
  }

  function applyTermScopeChrome(scope) {
    const hint = $("termHint");
    const tabsNav = $("termSessionTabs");
    if (scope === "nord") {
      if (hint) {
        hint.textContent = "NordVPN commands only — pick a tab, click the black area, then type. Ctrl+C interrupt · Ctrl+D exit · Paste with Ctrl+V";
      }
      if (tabsNav) tabsNav.setAttribute("aria-label", "Nord shell tabs");
    } else if (scope === "security") {
      if (hint) {
        hint.textContent = "Security shell — UFW, scans, and apt security tools. Sudo shows a password box when needed. Ctrl+C interrupt · Ctrl+D exit · Paste with Ctrl+V";
      }
      if (tabsNav) tabsNav.setAttribute("aria-label", "Security shell tabs");
    } else if (String(scope).startsWith("custom:")) {
      const catId = scope.slice(7);
      const cat = quickCommandsSettingsDraft?.custom_categories?.find((c) => c.id === catId);
      const name = cat?.label || "Custom";
      if (hint) {
        hint.textContent = `${name} shell — your custom quick commands. Edit in Settings → Quick commands. Sudo shows a password box when needed. Ctrl+C interrupt · Ctrl+D exit · Paste with Ctrl+V`;
      }
      if (tabsNav) tabsNav.setAttribute("aria-label", `${name} shell tabs`);
    } else {
      if (hint) {
        hint.textContent = "Networking shell — routes, WiFi, and apt networking tools. Sudo shows a password box when needed. Ctrl+C interrupt · Ctrl+D exit · Paste with Ctrl+V";
      }
      if (tabsNav) tabsNav.setAttribute("aria-label", "Networking shell tabs");
    }
  }

  function termDisplayNeedsSudoPassword(display) {
    const lines = String(display || "").split("\n");
    const last = (lines[lines.length - 1] || "").replace(/\r/g, "").trimEnd();
    const prev = (lines[lines.length - 2] || "").replace(/\r/g, "").trimEnd();
    if (/\[sudo\][^\n]*(?:password|authenticate)/i.test(last)) return true;
    if (/^\[sudo\]\s*password for [^:\n]+:\s*$/i.test(last)) return true;
    if (/^Password:?\s*$/i.test(last) && (/\[sudo\]/i.test(prev) || /\bsudo\b/i.test(prev))) return true;
    return false;
  }

  function termShellReady(display) {
    const lines = String(display || "").split("\n");
    let last = "";
    for (let i = lines.length - 1; i >= 0; i -= 1) {
      const line = (lines[i] || "").replace(/\r/g, "").trimEnd();
      if (line) {
        last = line;
        break;
      }
    }
    if (!last) return false;
    if (/\[sudo\]/i.test(last)) return false;
    if (/^password/i.test(last) && last.endsWith(":")) return false;
    return /[$#]\s*$/.test(last);
  }

  function termShowSudoPrompt(message, focusPass = true) {
    termSudoActive = true;
    $("termSudoPrompt")?.classList.remove("hidden");
    if ($("termSudoReason")) {
      $("termSudoReason").textContent = message || "Enter your sudo password below — characters stay hidden in the terminal output.";
    }
    if (focusPass) $("termSudoPass")?.focus();
    else termFocusInput();
  }

  function termSyncSudoPrompt(sess) {
    if (!sess || sess.id !== activeTermId) {
      termHideSudoPrompt();
      return;
    }
    if (termDisplayNeedsSudoPassword(sess.display)) {
      termShowSudoPrompt("Sudo is waiting for your password — type it below and press Send.", true);
      return;
    }
    if (sess.expectSudo && !termShellReady(sess.display)) {
      termShowSudoPrompt(
        "This command uses sudo — enter your password when prompted below, or click the black area once sudo finishes.",
        false
      );
      return;
    }
    sess.expectSudo = false;
    termHideSudoPrompt();
    termFocusInput();
  }

  function termRenderPostInstallBar(sess) {
    const bar = $("termPostInstallBar");
    if (!bar) return;
    termRehydratePackageInstallContext(sess);
    const backMeta = postInstallBackMeta(sess);
    const pi = sess?.postInstall;
    if (pi && sess.id === activeTermId && termShellReady(sess.display)) {
      const name = pi.label || pi.bin || "Package";
      const runCmd = String(pi.run_cmd || "").trim();
      const tryHint = pi.bin ? `${pi.bin} --help` : "";
      bar.classList.remove("hidden");
      bar.innerHTML = [
        `<p class="help-text"><strong>${esc(name)} installed.</strong> Shell is ready — click the black area to type, or try:</p>`,
        `<div class="actions">`,
        runCmd
          ? `<button type="button" class="btn sm primary" data-term-run-next="${esc(runCmd)}">${esc(pi.run_label || "Run installed tool")}</button>`
          : "",
        tryHint
          ? `<button type="button" class="btn sm" data-term-type-hint="${esc(tryHint)}">Type <code>${esc(tryHint)}</code></button>`
          : "",
        postInstallBackButtonHtml(backMeta),
        `<button type="button" class="btn sm" data-term-dismiss-post>Dismiss</button>`,
        `</div>`,
      ].filter(Boolean).join("");
      bar.querySelector("[data-term-run-next]")?.addEventListener("click", async () => {
        await termSendCommandToSession(sess, runCmd);
        sess.postInstall = null;
        termRenderPostInstallBar(sess);
        termFocusInput();
      });
      bar.querySelector("[data-term-type-hint]")?.addEventListener("click", async () => {
        const hint = bar.querySelector("[data-term-type-hint]")?.getAttribute("data-term-type-hint") || "";
        if (hint) await termSendCommandToSession(sess, hint);
        termFocusInput();
      });
      bar.querySelector("[data-term-dismiss-post]")?.addEventListener("click", () => {
        sess.postInstall = null;
        sess.afterPackageInstall = false;
        termRenderPostInstallBar(sess);
        termFocusInput();
      });
      wirePostInstallBackButton(bar, sess, backMeta);
      return;
    }
    if (sess?.afterPackageInstall && sess.id === activeTermId) {
      const done = termShellReady(sess.display);
      bar.classList.remove("hidden");
      bar.innerHTML = [
        done
          ? `<p class="help-text"><strong>Install finished.</strong> ${
            backMeta.wizardReturn
              ? "Return to the wizard to continue setup (or run nordvpn login next)."
              : backMeta.auditReturn
                ? "Return to the audit to re-run checks with the new tools."
                : "Return to packages to install more or check status."
          }</p>`
          : `<p class="help-text"><strong>Install running</strong> — watch progress above. Enter your sudo password when prompted.${
            backMeta.wizardReturn ? " Return to the wizard when done." : ""
          }</p>`,
        `<div class="actions term-post-install-actions">`,
        postInstallBackButtonHtml(backMeta, { primary: done }),
        `<button type="button" class="btn sm" data-term-dismiss-package-back>Dismiss</button>`,
        `</div>`,
      ].join("");
      wirePostInstallBackButton(bar, sess, backMeta);
      bar.querySelector("[data-term-dismiss-package-back]")?.addEventListener("click", () => {
        sess.afterPackageInstall = false;
        termRenderPostInstallBar(sess);
      });
      if (done && sess.id === activeTermId && termRouteSection() === "network") {
        scrollToPostInstallBar({ behavior: done ? "smooth" : "auto" });
      }
      return;
    }
    bar.classList.add("hidden");
    bar.innerHTML = "";
  }

  function termGetActive() {
    if (!activeTermId) return null;
    const sess = termSessions.get(activeTermId);
    if (!sess || termSessionScope(sess) !== termCommandScope()) return null;
    return sess;
  }

  function termSaveRegistry() {
    try {
      const saved = termLoadRegistry();
      const activeByScope = { ...(saved?.activeByScope || {}) };
      if (activeTermId && termSessions.has(activeTermId)) {
        activeByScope[termSessionScope(termSessions.get(activeTermId))] = activeTermId;
      }
      sessionStorage.setItem(TERM_STORE_KEY, JSON.stringify({
        active: activeTermId,
        activeByScope,
        sessions: [...termSessions.values()].map((s) => ({
          id: s.id,
          label: s.label,
          scope: s.scope || termSessionScope(s),
          cursorPos: s.cursorPos,
          display: (s.display || "").slice(-80000),
          alive: s.alive !== false,
          afterPackageInstall: !!s.afterPackageInstall,
          packageInstallReturnRoute: s.packageInstallReturnRoute || "",
          packageInstallHub: s.packageInstallHub || "",
        })),
      }));
    } catch (_) { /* ignore quota */ }
  }

  function termLoadRegistry() {
    try {
      const raw = sessionStorage.getItem(TERM_STORE_KEY);
      if (!raw) return null;
      return JSON.parse(raw);
    } catch (_) {
      return null;
    }
  }

  function termHideSudoPrompt() {
    termSudoActive = false;
    $("termSudoPrompt")?.classList.add("hidden");
    if ($("termSudoPass")) $("termSudoPass").value = "";
  }

  function termCheckSudoPrompt(sess) {
    termSyncSudoPrompt(sess);
  }

  async function termSubmitSudoPassword() {
    const pass = $("termSudoPass")?.value || "";
    if (!pass) {
      toast("Enter your sudo password", false);
      return;
    }
    const sess = termGetActive();
    if (sess) sess.expectSudo = false;
    termHideSudoPrompt();
    await termSendInput(`${pass}\n`);
    termFocusInput();
  }

  function stripAnsi(text) {
    return String(text || "")
      .replace(/\x1b\[[0-9;?]*[ -/]*[@-~]/g, "")
      .replace(/\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)/g, "")
      .replace(/\x1b[@-Z\\-_]/g, "")
      .replace(/\x1b./g, "");
  }

  function preprocessCursorAnsi(text) {
    let s = String(text || "");
    // EL erase line / erase to EOL → clear current line before redraw
    s = s.replace(/\x1b\[[012]?K/g, "\x02");
    // CHA: cursor to column 1 (1-based G) → treat as carriage return
    s = s.replace(/\x1b\[[0-9]*G/g, "\r");
    // CUP at column 1 on current row (common prompt redraw)
    s = s.replace(/\x1b\[1;1H/g, "\r\x02");
    return s;
  }

  function applyCarriageReturns(text) {
    let out = "";
    let line = "";
    const s = String(text || "");
    for (let i = 0; i < s.length; i += 1) {
      const ch = s[i];
      if (ch === "\x02") {
        line = "";
        continue;
      }
      if (ch === "\r") {
        if (s[i + 1] === "\n") {
          out += `${line}\n`;
          line = "";
          i += 1;
        } else {
          line = "";
        }
      } else if (ch === "\n") {
        out += `${line}\n`;
        line = "";
      } else if (ch !== "\x07") {
        line += ch;
      }
    }
    return out + line;
  }

  function dedupeTrailingPromptLine(text) {
    const lines = String(text || "").split("\n");
    if (!lines.length) return text;
    const last = lines[lines.length - 1];
    const promptRe = /u@[^\s:]+:[^\s]*[$#]\s*/g;
    const prompts = last.match(promptRe);
    if (!prompts || prompts.length < 2) return text;
    const tail = prompts[prompts.length - 1];
    const tailIdx = last.lastIndexOf(tail);
    const prefix = last.slice(0, tailIdx);
    if (!prefix.trim() || /^(?:u@[^\s:]+:[^\s]*[$#]\s*)+$/.test(prefix)) {
      lines[lines.length - 1] = tail;
    } else {
      lines[lines.length - 1] = prefix.replace(promptRe, "") + tail;
    }
    return lines.join("\n");
  }

  function sanitizeTerminalText(text) {
    let s = preprocessCursorAnsi(text);
    s = stripAnsi(s);
    s = s.replace(/\][0-9]+;[^\n]*/g, "");
    s = s.replace(/\x00/g, "");
    s = applyCarriageReturns(s);
    return dedupeTrailingPromptLine(s);
  }

  function termScanOutputComplete(out, cmd) {
    const t = String(out || "").toLowerCase();
    const c = String(cmd || "").toLowerCase();
    if (c.includes("lynis") && (/hardening index|lynis security scan details|audit finished|finished \(/.test(t))) return true;
    if (c.includes("rkhunter") && (/rkhunter done|one or more warnings|no warnings found/.test(t))) return true;
    if (c.includes("chkrootkit") && t.length > 400) return true;
    if (c.includes("clamscan") && (/scanning|infected files|found/.test(t) && t.length > 200)) return true;
    return false;
  }

  function termAppendChunkTo(sess, chunk) {
    if (!sess || !chunk) return;
    sess.display = (sess.display || "") + sanitizeTerminalText(chunk);
    if (sess.display.length > 300000) sess.display = sess.display.slice(-250000);
    if (sess.scanCommand && !sess.scanLogged && termScanOutputComplete(sess.display, sess.scanCommand.cmd)) {
      void maybeLogTerminalScan(sess);
    }
  }

  function termUpdateBadge() {
    const b = $("termBadge");
    if (!b) return;
    const scoped = termSessionsForScope(termCommandScope());
    const n = scoped.length;
    const active = termGetActive();
    if (!n) {
      b.textContent = "No shells";
      b.className = "badge off";
      return;
    }
    if (active?.alive === false) {
      b.textContent = "Ended";
      b.className = "badge off";
      return;
    }
    b.textContent = n === 1 ? "1 shell" : `${n} shells`;
    b.className = "badge on";
  }

  let termDeferRender = false;

  function termScreenEl() {
    return $("termScreen");
  }

  function termHasTextSelection() {
    const sel = window.getSelection();
    if (!sel || sel.isCollapsed) return false;
    const screen = termScreenEl();
    if (!screen) return false;
    const node = sel.anchorNode;
    return !!(node && screen.contains(node));
  }

  function termCopySelection() {
    const text = window.getSelection()?.toString() || "";
    if (!text.trim()) return false;
    navigator.clipboard?.writeText(text).then(
      () => toast("Copied selection", true),
      () => toast("Copy failed — try Copy output button", false),
    );
    return true;
  }

  function termSelectAllOutput() {
    const screen = termScreenEl();
    const sel = window.getSelection();
    if (!screen || !sel) return;
    const range = document.createRange();
    range.selectNodeContents(screen);
    sel.removeAllRanges();
    sel.addRange(range);
  }

  function termRenderActiveScreen() {
    if (termHasTextSelection()) {
      termDeferRender = true;
      return;
    }
    termDeferRender = false;
    const screen = termScreenEl();
    const sess = termGetActive();
    let display = "";
    if (sess) {
      display = sanitizeTerminalText(sess.display || "");
      if (display !== sess.display) sess.display = display;
    }
    const alive = sess?.alive !== false;
    if (screen) {
      screen.innerHTML = esc(display) + (alive ? '<span class="term-cursor-blink" aria-hidden="true">▋</span>' : "");
    }
    $("termCursor")?.remove();
    const vp = $("termViewport");
    if (vp) vp.scrollTop = vp.scrollHeight;
    termCheckSudoPrompt(sess);
    termRenderPostInstallBar(sess);
  }

  function termNextShellLabel(scope = termCommandScope()) {
    const used = new Set(termSessionsForScope(scope).map((s) => s.label));
    termReservedLabels.forEach((l) => used.add(l));
    let n = 1;
    while (used.has(`Shell ${n}`)) n += 1;
    const label = `Shell ${n}`;
    termReservedLabels.add(label);
    return label;
  }

  function termReleaseShellLabel(label) {
    if (label && /^Shell \d+$/i.test(label)) termReservedLabels.delete(label);
  }

  function termSyncRouteHash(replace) {
    if (!termUiActive()) return;
    const section = termRouteSection();
    if (section === "tools" && toolsTab === "custom-shell") {
      syncRouteHash("tools", "custom-shell", !!replace, customShellCategory || null);
      return;
    }
    if (section === "tools" || section === "dashboard") {
      syncRouteHash("dashboard", "terminal", !!replace, activeTermId || null);
      return;
    }
    syncRouteHash("network", "diagnostics", !!replace, diagnosticsShellRouteSub(termCommandScope(), activeTermId));
  }

  async function termFlushSession(sess, opts = {}) {
    if (!sess) return;
    try {
      const r = await api(
        `/api/terminal/poll?session=${encodeURIComponent(sess.id)}&cursor=${sess.cursorPos || 0}&wait=0`,
        { timeoutMs: 12000 }
      );
      if (r.ok && r.chunk) {
        termAppendChunkTo(sess, r.chunk);
        sess.cursorPos = r.cursor;
        sess.alive = r.alive !== false;
      } else if (!r.ok) {
        sess.alive = false;
      }
      if (opts.render && sess.id === activeTermId) termRenderActiveScreen();
    } catch (_) { /* ignore */ }
  }

  async function termSendCommandToSession(sess, cmd) {
    const payload = String(cmd || "");
    if (!payload) return;
    const data = payload.endsWith("\n") ? payload : `${payload}\n`;
    sess.expectSudo = /^\s*sudo\b/.test(data);
    if (sess.id === activeTermId) termSyncSudoPrompt(sess);
    await termSendInput(data, sess.id);
    await termFlushSession(sess, { render: false });
    if (sess.id === activeTermId) {
      await termPollOnce(sess.id, { wait: true });
      termRenderActiveScreen();
    }
  }

  function termRenderTabs() {
    const nav = $("termSessionTabs");
    if (!nav) return;
    const scope = termCommandScope();
    const scoped = termSessionsForScope(scope);
    if (!scoped.length) {
      const empty = scope === "nord"
        ? "No Nord shells — click <strong>New shell tab</strong> or a NordVPN command below."
        : "No shells — click <strong>New shell tab</strong> or run a quick command.";
      nav.innerHTML = `<span class="term-tabs-empty muted">${empty}</span>`;
      return;
    }
    nav.innerHTML = scoped.map((s) => {
      const alive = s.alive !== false;
      const cls = `term-session-tab${s.id === activeTermId ? " active" : ""}${alive ? "" : " ended"}`;
      return `<button type="button" class="${cls}" data-term-id="${esc(s.id)}" title="${esc(s.label)} — ${alive ? "running" : "ended"}">${esc(s.label)}${alive ? "" : " ✕"}</button>`;
    }).join("") + `<button type="button" class="btn sm term-session-add" id="btnTermAddTab" title="Open another bash shell in a new tab">+ New tab</button>`;
    nav.querySelectorAll("[data-term-id]").forEach((btn) => {
      btn.addEventListener("click", () => termSwitchTab(btn.getAttribute("data-term-id")));
    });
    $("btnTermAddTab")?.addEventListener("click", () => termConnect(true));
    applyButtonTitles(nav);
    syncTermCrossLink();
  }

  function termSwitchTab(sessionId, opts = {}) {
    const sess = termSessions.get(sessionId);
    if (!sess || termSessionScope(sess) !== termCommandScope()) return;
    activeTermId = sessionId;
    termRenderTabs();
    termRenderActiveScreen();
    termUpdateBadge();
    termSaveRegistry();
    termResizeViewport();
    termEnsureActiveLongPoll();
    termFocusInput();
    if (!opts.skipHash) termSyncRouteHash(false);
    syncTermCrossLink();
  }

  async function termSendInput(data, sessionId) {
    const sid = sessionId || activeTermId;
    const sess = sid ? termSessions.get(sid) : null;
    if (!sess || !data) return false;
    try {
      const r = await api("/api/terminal/input", {
        method: "POST",
        body: JSON.stringify({ session: sid, data }),
      });
      if (!r.ok) {
        if ((r.error || "").includes("not found")) {
          sess.alive = false;
          termUpdateBadge();
          termRenderTabs();
          return false;
        }
        toast(r.error || "Input failed", false);
        return false;
      }
      sess.alive = r.alive !== false;
      return true;
    } catch (_) {
      toast("Terminal input error", false);
      return false;
    }
  }

  async function termOpenSession(label, opts = {}) {
    const autoShellLabel = !String(label || "").trim();
    const cleanLabel = autoShellLabel ? termNextShellLabel() : String(label).trim();
    termSetBadge("Connecting…", null);
    try {
      const r = await api("/api/terminal/open", {
        method: "POST",
        body: JSON.stringify({ label: cleanLabel }),
      });
      if (!r.ok || !r.session) throw new Error(r.error || "Could not open terminal");
      const sess = {
        id: r.session,
        label: r.label || cleanLabel,
        scope: opts.scope || termCommandScope(),
        display: "",
        cursorPos: 0,
        alive: true,
      };
      termSessions.set(sess.id, sess);
      activeTermId = sess.id;
      termRenderTabs();
      termUpdateBadge();
      termSaveRegistry();
      termEnsureBackgroundPoll();
      termResizeViewport();
      termEnsureActiveLongPoll();
      termSyncRouteHash(false);
      await termFlushSession(sess, { render: true });
      logActivity("terminal", `Terminal opened — ${sess.label}`, true);
      if (opts.command) {
        await termSendCommandToSession(sess, opts.command);
      } else {
        termRenderActiveScreen();
      }
      return sess;
    } catch (e) {
      termSetBadge("Failed", false);
      reportActionError("Terminal connect failed", e, "Opening bash session");
      return null;
    } finally {
      if (autoShellLabel) termReleaseShellLabel(cleanLabel);
    }
  }

  async function ensureNordTerminalReady() {
    if (termUiActive() && (termRouteSection() === "tools" || termRouteSection() === "dashboard")) {
      await loadTerminal();
      await new Promise((r) => requestAnimationFrame(r));
      return;
    }
    openNordTerminal({ force: true });
    await loadTerminal();
    await new Promise((r) => requestAnimationFrame(r));
  }

  async function ensureNetworkTerminalReady(scope = "network") {
    const wantScope = scope === "security" ? "security" : "network";
    const wantTab = wantScope === "security" ? "security-shell" : "networking-shell";
    if (termUiActive() && termRouteSection() === "network" && termCommandScope() === wantScope) {
      await loadTerminal();
      await new Promise((r) => requestAnimationFrame(r));
      return;
    }
    await switchHubTab(wantTab);
    await loadTerminal();
    await new Promise((r) => requestAnimationFrame(r));
  }

  async function maybeLogTerminalScan(sess) {
    if (!sess?.scanCommand || sess.scanLogged) return;
    const out = String(sess.display || "").trim();
    if (!out) return;
    sess.scanLogged = true;
    try {
      await api("/api/logs/append", {
        method: "POST",
        body: JSON.stringify({
          type: "scan",
          message: sess.scanCommand.label || "Security scan",
          ok: !/\b(error|fatal|not found)\b/i.test(out.slice(-400)),
          detail: "Captured from Diagnostics → Shell when the session ended.",
          technical: out.slice(-8000),
        }),
      });
      loadLogsQuiet();
    } catch (_) { /* ignore */ }
  }

  function termCommandIsScan(cmd) {
    return /lynis|rkhunter|chkrootkit|clamscan|nmap|fail2ban|rootkit|audit system/i.test(String(cmd || ""));
  }

  async function termRunCommand(cmd, label, opts = {}) {
    const text = String(cmd || "");
    if (!text) return;
    const wantScope = opts.scope || (termUiActive() ? termCommandScope() : "network");
    if (wantScope === "nord") {
      if (!termUiActive() || (termRouteSection() !== "tools" && termRouteSection() !== "dashboard")) {
        await ensureNordTerminalReady();
      } else {
        await loadTerminal();
      }
    } else if (String(wantScope).startsWith("custom:")) {
      const catId = wantScope.slice(7);
      if (!termUiActive() || getActiveView() !== "customShell" || termCommandScope() !== wantScope) {
        customShellCategory = catId;
        localStorage.setItem("nordctl_custom_shell_cat", catId);
        await switchToolsTab("custom-shell", { skipHash: false, replaceHash: true, toolsSub: catId });
      } else {
        await loadTerminal();
      }
    } else if (!termUiActive() || termRouteSection() !== "network" || termCommandScope() !== wantScope) {
      await ensureNetworkTerminalReady(wantScope);
    } else {
      await loadTerminal();
    }
    const scope = opts.scope ? String(opts.scope) : termCommandScope();
    const shortLabel = String(label || "").trim() || text.trim().split("\n")[0].slice(0, 40) || "Command";
    const isSudo = /^\s*sudo\b/.test(text.trim());
    const isScan = termCommandIsScan(text);
    const existing = termSessionsForScope(scope).find((s) => s.label === shortLabel && s.alive !== false);
    if (existing) {
      existing.expectSudo = isSudo;
      if (isScan) {
        existing.scanCommand = { cmd: text, label: shortLabel };
        existing.scanLogged = false;
      }
      termSwitchTab(existing.id);
      await termSendCommandToSession(existing, text);
    } else {
      const sess = await termOpenSession(shortLabel, { command: text, scope });
      if (sess && isSudo) {
        sess.expectSudo = true;
        termSyncSudoPrompt(sess);
      }
      if (sess && isScan) {
        sess.scanCommand = { cmd: text, label: shortLabel };
        sess.scanLogged = false;
      }
    }
    termFocusInput();
    if ((scope === "network" || scope === "security") && (opts.scrollToTerminal || termCommandIsPackageChange(text))) {
      scrollToDiagnosticsTerminal();
    } else if (opts.scrollToTerminal && scope === "nord") {
      requestAnimationFrame(() => {
        ($("termPostInstallBar") || $("termViewport") || $("terminalPanel"))
          ?.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
    if (termCommandIsPackageChange(text)) {
      const active = termGetActive();
      if (active) {
        active.afterPackageInstall = true;
        active.packageInstallHub = sessionStorage.getItem("nordctl_install_return_hub") || packageApiHub(hubTab) || "network";
        active.packageInstallCategory = sessionStorage.getItem(INSTALL_RETURN_CAT_KEY) || customPackagesCategory || "";
        active.packageInstallReturnRoute = sessionStorage.getItem(INSTALL_RETURN_ROUTE_KEY)
          || installToolsPackagesRoute(active.packageInstallHub, active.packageInstallCategory);
        termRenderPostInstallBar(active);
        termSaveRegistry();
        if (scope === "network" || scope === "security") scrollToPostInstallBar({ behavior: "smooth" });
      }
    }
  }

  function termSetBadge(text, ok) {
    const b = $("termBadge");
    if (!b || text) {
      if (b) {
        b.textContent = text;
        b.className = "badge " + (ok === true ? "on" : ok === false ? "off" : "");
      }
      return;
    }
    termUpdateBadge();
  }

  let termResizeTimer = null;
  let termResizePending = null;

  async function termResizeViewportNow() {
    const sess = termGetActive();
    if (!sess) return;
    const vp = $("termViewport");
    if (!vp) return;
    const style = getComputedStyle(vp);
    const padX = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
    const padY = parseFloat(style.paddingTop) + parseFloat(style.paddingBottom);
    const charW = 8.2;
    const lineH = 16;
    const cols = Math.max(40, Math.floor((vp.clientWidth - padX) / charW));
    const rows = Math.max(8, Math.floor((vp.clientHeight - padY) / lineH));
    const key = `${sess.id}:${cols}x${rows}`;
    if (termResizePending === key) return;
    termResizePending = key;
    await api("/api/terminal/resize", {
      method: "POST",
      body: JSON.stringify({ session: sess.id, cols, rows }),
    });
  }

  function termResizeViewport() {
    clearTimeout(termResizeTimer);
    termResizeTimer = setTimeout(() => { termResizeViewportNow(); }, 120);
  }

  async function termPollOnce(sessionId, opts = {}) {
    const sess = termSessions.get(sessionId);
    if (!sess || sess.alive === false) return false;
    const onTerminal = termUiActive();
    const wait = opts.wait === true || (opts.wait !== false && sessionId === activeTermId && onTerminal && termLongPollActive);
    try {
      const r = await api(
        `/api/terminal/poll?session=${encodeURIComponent(sessionId)}&cursor=${sess.cursorPos || 0}&wait=${wait ? 1 : 0}`,
        { timeoutMs: wait ? 35000 : 12000 }
      );
      if (!r.ok) {
        sess.alive = false;
        if (sessionId === activeTermId) termUpdateBadge();
        return false;
      }
      if (r.chunk) {
        termAppendChunkTo(sess, r.chunk);
        sess.cursorPos = r.cursor;
        if (sessionId === activeTermId) termRenderActiveScreen();
      }
      if (!r.alive) {
        await maybeLogTerminalScan(sess);
        sess.alive = false;
        if (sessionId === activeTermId) termUpdateBadge();
        return false;
      }
      return true;
    } catch (_) {
      return sessionId === activeTermId;
    }
  }

  async function termLongPollLoop() {
    if (termLongPollChain) return;
    termLongPollChain = true;
    while (termLongPollActive && termUiActive() && activeTermId) {
      const ok = await termPollOnce(activeTermId, { wait: true });
      if (!ok) break;
    }
    termLongPollChain = false;
  }

  function termEnsureActiveLongPoll() {
    if (!termUiActive() || !activeTermId) {
      termLongPollActive = false;
      return;
    }
    termLongPollActive = true;
    if (!termLongPollChain) termLongPollLoop();
  }

  function termPauseActiveLongPoll() {
    termLongPollActive = false;
  }

  function termEnsureBackgroundPoll() {
    if (termBgPollTimer || !termSessions.size) return;
    termBgPollTimer = setInterval(async () => {
      if (!termSessions.size) {
        termStopBackgroundPoll();
        return;
      }
      for (const [id, sess] of termSessions) {
        if (sess.alive === false) continue;
        if (id === activeTermId && termLongPollActive && termUiActive()) continue;
        await termPollOnce(id, { wait: false });
      }
      termSaveRegistry();
    }, 800);
  }

  function termStopBackgroundPoll() {
    if (termBgPollTimer) {
      clearInterval(termBgPollTimer);
      termBgPollTimer = null;
    }
  }

  function stopTerminalPoll() {
    termPauseActiveLongPoll();
  }

  async function termCloseSession(sessionId) {
    const sid = sessionId || activeTermId;
    const sess = sid ? termSessions.get(sid) : null;
    if (!sess) return;
    await maybeLogTerminalScan(sess);
    try {
      await api("/api/terminal/close", {
        method: "POST",
        body: JSON.stringify({ session: sid }),
      });
    } catch (_) { /* ignore */ }
    termSessions.delete(sid);
    if (activeTermId === sid) {
      activeTermId = termSessions.size ? [...termSessions.keys()][0] : null;
      termHideSudoPrompt();
      termRenderActiveScreen();
    }
    if (!termSessions.size) termStopBackgroundPoll();
    termRenderTabs();
    termUpdateBadge();
    termSaveRegistry();
    termEnsureActiveLongPoll();
    termSyncRouteHash(true);
  }

  async function termConnect(forceNew) {
    const scope = termCommandScope();
    const scoped = termSessionsForScope(scope);
    if (forceNew) {
      await termOpenSession(termNextShellLabel(scope), { scope });
      termFocusInput();
      return;
    }
    termEnsureScopedActive(scope);
    if (scoped.length) {
      termRenderTabs();
      termRenderActiveScreen();
      termUpdateBadge();
      termEnsureBackgroundPoll();
      termEnsureActiveLongPoll();
      termFocusInput();
      return;
    }
    await termOpenSession(termNextShellLabel(scope), { scope });
    termFocusInput();
  }

  async function termSyncSessions() {
    try {
      const remote = await api("/api/terminal/sessions");
      const saved = termLoadRegistry();
      const remoteIds = new Set((remote.sessions || []).map((s) => s.id));
      if (saved?.sessions) {
        saved.sessions.forEach((s) => {
          if (!remoteIds.has(s.id)) return;
          if (termSessions.has(s.id)) return;
          termSessions.set(s.id, {
            id: s.id,
            label: s.label || "Shell",
            scope: (s.scope && (s.scope === "nord" || s.scope === "security" || s.scope === "network" || String(s.scope).startsWith("custom:")))
              ? s.scope
              : termInferScope(s.label),
            display: s.display || "",
            cursorPos: s.cursorPos || 0,
            alive: s.alive !== false,
            afterPackageInstall: !!s.afterPackageInstall,
            packageInstallReturnRoute: s.packageInstallReturnRoute || "",
            packageInstallHub: s.packageInstallHub || "",
          });
        });
      }
      (remote.sessions || []).forEach((s) => {
        if (termSessions.has(s.id)) {
          const loc = termSessions.get(s.id);
          loc.alive = s.alive !== false;
          if (s.label) loc.label = s.label;
          return;
        }
        termSessions.set(s.id, {
          id: s.id,
          label: s.label || "Shell",
          scope: termInferScope(s.label),
          display: "",
          cursorPos: 0,
          alive: s.alive !== false,
        });
      });
      [...termSessions.keys()].forEach((id) => {
        if (!remoteIds.has(id)) termSessions.delete(id);
      });
      if (saved?.activeByScope) {
        const scope = termCommandScope();
        if (saved.activeByScope[scope] && termSessions.has(saved.activeByScope[scope])) {
          activeTermId = saved.activeByScope[scope];
        }
      } else if (saved?.active && termSessions.has(saved.active)) {
        activeTermId = saved.active;
      }
      termEnsureScopedActive(termCommandScope());
      for (const sess of termSessions.values()) {
        if (sess.alive === false) continue;
        if ((sess.display || "").startsWith("# Local only")) {
          sess.display = "";
          sess.cursorPos = 0;
        }
        if (!(sess.display || "").length || (sess.display || "").length < 80) {
          await termFlushSession(sess);
        }
      }
      termRenderTabs();
      termRenderActiveScreen();
      termUpdateBadge();
      termEnsureBackgroundPoll();
      if (pendingTermSessionId && termSessions.has(pendingTermSessionId)) {
        const ps = termSessions.get(pendingTermSessionId);
        if (termSessionScope(ps) === termCommandScope()) {
          termSwitchTab(pendingTermSessionId, { skipHash: true });
          pendingTermSessionId = null;
          termSyncRouteHash(true);
        }
      } else if (pendingTermSessionId) {
        pendingTermSessionId = null;
      }
    } catch (_) { /* ignore */ }
  }

  function termKeyToData(e) {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key.toLowerCase() === "c") {
      if (termHasTextSelection()) {
        e.preventDefault();
        termCopySelection();
        return null;
      }
      if (!e.ctrlKey || e.altKey) return null;
      return "\x03";
    }
    if (mod && e.key.toLowerCase() === "a") {
      e.preventDefault();
      termSelectAllOutput();
      return null;
    }
    if (mod && e.key.toLowerCase() === "v") return null;
    if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "d") return "\x04";
    if (e.ctrlKey && !e.altKey && e.key.toLowerCase() === "l") return "\x0c";
    if (e.key === "Enter") return "\n";
    if (e.key === "Backspace") return "\x7f";
    if (e.key === "Tab") { e.preventDefault(); return "\t"; }
    if (e.key === "Escape") return "\x1b";
    const arrows = {
      ArrowUp: "\x1b[A",
      ArrowDown: "\x1b[B",
      ArrowRight: "\x1b[C",
      ArrowLeft: "\x1b[D",
    };
    if (arrows[e.key]) { e.preventDefault(); return arrows[e.key]; }
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) return e.key;
    return null;
  }

  function initTerminalInput() {
    const vp = $("termViewport");
    const inp = $("termInput");
    if (!vp || !inp || vp.dataset.termInit) return;
    vp.dataset.termInit = "1";

    const onKey = (e) => {
      if (!termGetActive()) {
        e.preventDefault();
        return;
      }
      if (termSudoActive && e.key === "Escape") {
        e.preventDefault();
        termHideSudoPrompt();
        termSendInput("\x03");
        return;
      }
      const data = termKeyToData(e);
      if (data == null) return;
      e.preventDefault();
      termSendInput(data);
    };

    inp.addEventListener("keydown", onKey);
    inp.addEventListener("paste", (e) => {
      if (!termGetActive()) {
        e.preventDefault();
        return;
      }
      e.preventDefault();
      const text = e.clipboardData?.getData("text") || "";
      if (text) termSendInput(text);
    });
    vp.addEventListener("mouseup", () => {
      window.setTimeout(() => {
        if (!termHasTextSelection()) termFocusInput();
      }, 0);
    });
    vp.addEventListener("dblclick", () => {
      window.setTimeout(() => {
        if (termHasTextSelection()) return;
        termFocusInput();
      }, 0);
    });
    if (!document.body.dataset.termSelectionInit) {
      document.body.dataset.termSelectionInit = "1";
      document.addEventListener("selectionchange", () => {
        if (termDeferRender && !termHasTextSelection()) termRenderActiveScreen();
      });
    }
    if (typeof ResizeObserver !== "undefined") {
      termResizeObs = new ResizeObserver(() => { termResizeViewport(); });
      termResizeObs.observe(vp);
    }
  }

  function termFocusInput() {
    $("termInput")?.focus();
  }

  function sortCommandsSudoLast(commands) {
    const plain = commands.filter((c) => !c.sudo);
    const elevated = commands.filter((c) => c.sudo);
    return [...plain, ...elevated];
  }

  function termQuickButtonHtml(commands, startIdx) {
    return commands.map((c, i) => {
      const idx = startIdx + i;
      const sudoTag = c.sudo ? '<span class="term-sudo-tag">sudo</span>' : "";
      const sudoHint = c.sudo ? " — opens a shell tab; password box appears if needed" : " — opens a shell tab";
      return `<button type="button" class="btn sm term-quick-btn${c.sudo ? " term-quick-sudo" : ""}" data-term-idx="${idx}" data-no-confirm="1" title="${esc(c.cmd.trim())}${sudoHint}">${esc(c.label)}${sudoTag}</button>`;
    }).join("");
  }

  function wireTermQuickButtons(root) {
    root?.querySelectorAll(".term-quick-btn").forEach((b) => {
      b.addEventListener("click", async () => {
        const c = termQuickCommands[Number(b.dataset.termIdx)];
        if (!c) return;
        b.disabled = true;
        try {
          await termRunCommand(c.cmd || "", c.label || "", { scope: termCommandScope() });
        } finally {
          b.disabled = false;
        }
      });
    });
  }

  function termMountTargetForScope(scope) {
    if (scope === "nord") return "dashboard";
    if (String(scope || "").startsWith("custom:")) return "custom";
    return "network";
  }

  async function termLoadQuickCommands(scope, force = false) {
    const box = $("termQuick");
    if (!box) return;
    const stdLabel = box.closest(".term-quick-toolbar-unified, .nettool-zone")?.querySelector(".nettool-zone-label");
    if (stdLabel) {
      if (scope === "nord") stdLabel.textContent = "NordVPN quick commands";
      else if (scope === "security") stdLabel.textContent = "Security quick commands";
      else if (String(scope).startsWith("custom:")) {
        const catId = scope.slice(7);
        const cat = quickCommandsSettingsDraft?.custom_categories?.find((c) => c.id === catId);
        stdLabel.textContent = cat?.label ? `${cat.label} quick commands` : "Custom quick commands";
      } else stdLabel.textContent = "Networking quick commands";
    }
    const fresh = force || scope === "network" || scope === "security" || scope === "nord" || String(scope).startsWith("custom:");
    try {
      const q = await apiCached(
        `/api/terminal/commands?scope=${encodeURIComponent(scope)}`,
        {},
        fresh ? 0 : CACHE_TTL.tools,
      );
      termQuickCommands = sortCommandsSudoLast(q.commands || []);
      box.innerHTML = termQuickCommands.length
        ? termQuickButtonHtml(termQuickCommands, 0)
        : `<span class="muted-inline nettool-zone-empty">No quick commands</span>`;
      wireTermQuickButtons(box);
    } catch (_) {
      box.innerHTML = `<span class="muted-inline nettool-zone-empty">Could not load quick commands</span>`;
    }
  }

  async function loadTerminal(force = false) {
    initTerminalInput();
    await termSyncSessions();
    const scope = termCommandScope();
    termMountPanel(termMountTargetForScope(scope));
    applyTermScopeChrome(scope);
    termEnsureScopedActive(scope);
    if (scope === "network" || scope === "security") {
      syncDiagnosticsShellScope(scope, { skipHash: true });
    }
    await termLoadQuickCommands(scope, force);
    renderTermAccessNote();
    const scoped = termSessionsForScope(scope);
    if (!scoped.length) {
      await termConnect(false);
    } else {
      termRenderTabs();
      termRenderActiveScreen();
      termEnsureBackgroundPoll();
      termEnsureActiveLongPoll();
    }
    termFocusInput();
    if (activeTermId && termUiActive()) termSyncRouteHash(true);
    applyButtonTitles($("terminalPanel"));
    syncPageHow();
    syncHubShellTabHashes();
  }

  function initLogPanel() {
    loadLogsQuiet();
  }

  /* ── Views ── */
  const VALID_VIEWS = new Set([
    "dashboard", "wifi", "doctors", "lab", "security", "control",
    "automate", "advanced", "logs", "terminal", "help", "editor", "settings", "customShell", "customPackages", "pcInfo",
  ]);
  const HUB_VIEWS = new Set(["security", "lab", "control", "advanced", "wifi", "doctors"]);
  const TOOLS_VIEWS = new Set(["logs", "automate", "editor", "terminal", "customShell", "customPackages", "pcInfo"]);
  const NETWORK_TOOLS_TABS = Object.fromEntries(
    Object.entries(TOOLS_TABS).filter(([id]) => id !== "settings")
  );
  let pendingPresetRetry = null;
  let tabLoadingDepth = 0;
  let tabLoadingMsgTimer = null;
  let tabLoadingMsgIndex = 0;
  const TAB_LOADING_TITLES = [
    "Routing your request",
    "Securing the wire",
    "Mapping the network",
    "Syncing with nordctl",
    "Preparing your dashboard",
  ];
  const TAB_LOADING_MESSAGES = [
    "Tunneling through Nordlynx…",
    "Negotiating WireGuard handshakes…",
    "Resolving DNS without leaks…",
    "Scanning WiFi channels & routes…",
    "Checking UFW and Meshnet peers…",
    "Loading apt package catalog…",
    "Running privacy audit probes…",
    "Encrypting local session state…",
    "Polling nordvpnd for status…",
    "Tracing packets across interfaces…",
    "Verifying kill-switch posture…",
    "Warming up diagnostics shell…",
  ];

  const LEGACY_ROUTE_HASH = {
    dashboard: "dashboard/connect",
    wifi: "network/wifi",
    lab: "network/audit",
    doctors: "network/doctors",
    security: "network/monitoring",
    control: "network/host-ufw",
    advanced: "network/map-internet",
    "map-internet": "network/map-internet",
    "map-local": "network/map-local",
    automate: "network/tools/auto-guide",
    logs: "network/tools/logs",
    terminal: "dashboard/terminal",
    settings: "settings/nord/password",
    editor: "network/tools/editor",
    help: "help",
  };

  const VIEW_ANCHOR_TO_ROUTE = {
    dashboard: {
      connect: "dashboard/connect", meshnet: "dashboard/meshnet", "connection-details": "dashboard/connection-details", workflows: "dashboard/workflows", "create-presets": "dashboard/create-presets", switches: "dashboard/switches", wizard: "dashboard/wizard",
      "nord-doctor": "dashboard/nord-doctor",
      "nord-services": "dashboard/nord-services",
      "optional-extras": "dashboard/optional-extras",
      "split-tunnel": "dashboard/split-tunnel",
      "nord-dns": "dashboard/nord-dns",
      terminal: "dashboard/terminal",
    },
    security: {
      overview: "network/monitoring",
      "net-dns": "network/network/dns",
      "net-ipv6": "network/network/ipv6",
    },
    lab: { leak: "network/leak-tests", overall: "network/audit", audit: "network/diagnostics" },
    doctors: {
      overview: "network/doctors/overview",
      nordvpn: "dashboard/nord-doctor",
      wifi: "network/doctors/wifi",
      privacy: "network/doctors/privacy",
      system: "network/doctors/system",
      net: "network/doctors/net",
      health: "network/doctors/overview",
    },
    wifi: {
      profiles: "network/wifi/profiles", zones: "network/wifi/zones",
      "smart-dns": "dashboard/nord-dns", scenarios: "dashboard/connect",
      nearby: "network/wifi/profiles", "wifi-doctor": "network/wifi/profiles",
    },
    advanced: {
      traffic: "network/traffic/internet",
      "traffic-live": "network/traffic/live",
      "traffic-speed": "network/traffic/speed",
      "spectrum-analyzer": "network/spectrum-analyzer",
      "bluetooth-spectrum": "network/bluetooth-spectrum",
      "traffic-internet": "network/traffic/internet",
      "traffic-local": "network/traffic/local",
      services: "network/services",
      "network-packages": "network/network-packages",
      "security-packages": "network/security-packages",
      listeners: "network/listeners",
      privileges: "network/privileges",
      setup: "network/security-packages",
      install: "network/network-packages",
      "network-tools": "network/network-packages",
      "network-access": "network/services",
      "security-tools": "network/security-packages",
    },
    automate: {
      guide: "network/tools/auto-guide", watcher: "network/tools/auto-watcher", schedules: "network/tools/schedules",
      rollback: "network/tools/rollback", reset: "network/tools/reset", snapshots: "network/tools/snapshots",
    },
    settings: {
      password: "settings/general/password", interface: "settings/general/interface", services: "settings/general/services",
      access: "settings/general/access", places: "settings/locations/places",
      "smart-dns": "settings/wifi/smart-dns", zones: "settings/wifi/zones", profiles: "settings/wifi/profiles",
      tunnel: "settings/vpn/tunnel", probes: "settings/vpn/probes", advanced: "settings/vpn/advanced",
      notifications: "settings/alerts/notifications", email: "settings/alerts/email",
      general: "settings/general/password", locations: "settings/locations/places", wifi: "settings/wifi/smart-dns",
      vpn: "settings/vpn/tunnel", alerts: "settings/alerts/notifications",
      nord: "settings/general/password", network: "settings/alerts/notifications",
    },
  };

  function resolveViewJump(raw) {
    const trimmed = String(raw || "").trim();
    if (!trimmed) return { section: "dashboard", tab: "connect" };
    if (trimmed.toLowerCase() === "help") return { section: "help", tab: null };
    if (trimmed.includes("/")) {
      const [section, tab, ...rest] = trimmed.split("/");
      if (section === "network" && tab === "profiles") {
        return { section: "dashboard", tab: "workflows", sub: rest[0] || "my-presets" };
      }
      if (section === "network" && tab === "sec-tools") {
        return { section: "network", tab: "security-packages", sub: null };
      }
      if (section === "network" && tab === "install-tools") {
        const sub = (rest[0] || "").toLowerCase();
        if (sub === "security") return { section: "network", tab: "security-packages", sub: null };
        return { section: "network", tab: "network-packages", sub: null };
      }
      if (section === "network" && tab === "setup") {
        return { section: "network", tab: "security-packages", sub: null };
      }
      if (section === "dashboard" && tab === "host-ufw") {
        return { section: "network", tab: "host-ufw", sub: rest[0] || null };
      }
      if (section === "network" && tab === "wifi") {
        const sub = rest[0] || null;
        if (sub === "scenarios") return { section: "dashboard", tab: "connect" };
        if (sub === "smart-dns") return { section: "dashboard", tab: "nord-dns" };
        return { section: "network", tab: "wifi", sub };
      }
      if (section === "network" && tab === "doctors") {
        const sub = rest[0] || null;
        if (sub === "nordvpn") return { section: "dashboard", tab: "nord-doctor" };
        return { section: "network", tab: "doctors", sub };
      }
      if (section === "network" && tab === "doctor") {
        return { section: "network", tab: "doctors", sub: "overview" };
      }
      if (section === "dashboard" && tab === "nord-doctor") {
        return { section: "dashboard", tab: "nord-doctor" };
      }
      if (section === "network" && tab === "wifi-nord-doctor") {
        return { section: "dashboard", tab: "nord-doctor" };
      }
      if (section === "network" && tab === "wifi-net-doctor") {
        return { section: "network", tab: "doctors", sub: "net" };
      }
      if (section === "network" && WIFI_LEGACY_HUB[tab]) {
        return { section: "network", tab: "wifi", sub: WIFI_LEGACY_HUB[tab] };
      }
      if (section === "network" && tab === "tools") {
        return { section: "tools", tab: rest[0] || "auto-guide", sub: null };
      }
      if (section === "tools" && tab && tab !== "settings") {
        return { section: "tools", tab, sub: rest[0] || null };
      }
      if (section === "tools" && tab === "settings") {
        if (!rest.length) return parseSettingsRouteParts([]);
        return parseSettingsRouteParts(rest);
      }
      if (section === "settings") {
        const parts = [tab, ...(rest || [])].filter(Boolean);
        return parseSettingsRouteParts(parts);
      }
      return { section: section || "dashboard", tab: tab || null, sub: rest[0] || null };
    }
    const [view, anchor] = trimmed.split("#");
    const anchorRoutes = VIEW_ANCHOR_TO_ROUTE[view];
    if (anchorRoutes) {
      const route = anchorRoutes[anchor || ""];
      if (route === "help") return { section: "help", tab: null };
      if (route) {
        const parts = route.split("/");
        return { section: parts[0], tab: parts[1] || null, sub: parts[2] || null };
      }
    }
    const mapped = LEGACY_ROUTE_HASH[view.toLowerCase()];
    if (mapped) {
      const parts = mapped.split("/");
      return { section: parts[0], tab: parts[1] || null, sub: parts[2] || null };
    }
    return { section: "dashboard", tab: "connect" };
  }

  function jumpRouteString(raw) {
    const route = resolveViewJump(raw);
    if (route.section === "settings") {
      const { scope, tab } = resolveSettingsRoute(route);
      return settingsRouteKey(scope, tab);
    }
    if (route.section === "tools" || (route.section === "network" && route.tab === "tools")) {
      const toolTab = route.section === "tools" ? (route.tab || "auto-guide") : (route.sub || "auto-guide");
      return buildRouteHash("tools", toolTab, null).slice(1);
    }
    if (route.section === "network") {
      return buildRouteHash(hubRoutePrefixForTab(route.tab), route.tab, route.sub).slice(1);
    }
    return buildRouteHash(route.section, route.tab, route.sub).slice(1);
  }

  function wifiRouteSub(sub) {
    return sub && sub !== "profiles" ? sub : null;
  }

  function trafficRouteSub(sub) {
    if (!sub || sub === "internet") return null;
    return sub;
  }

  function trafficHubPanelId(sub) {
    const id = TRAFFIC_HUB_TABS[sub] ? sub : "internet";
    if (id === "live") return "traffic-live";
    return id === "internet" ? "traffic-internet" : "traffic-local";
  }

  function networkRouteSub(sub) {
    return sub && NETWORK_HUB_TABS[sub] ? sub : null;
  }

  function doctorsRouteSub(sub) {
    if (!sub || sub === "overview") return null;
    if (sub === "health") return null;
    return sub;
  }

  function networkHubPanelId(sub) {
    const id = NETWORK_HUB_TABS[sub] ? sub : "dns";
    return `net-${id}`;
  }

  function hubRouteSub(tabId) {
    if (tabId === "wifi") return wifiRouteSub(wifiHubTab);
    if (tabId === "doctors") return doctorsRouteSub(doctorsHubTab);
    if (tabId === "network") return networkRouteSub(networkHubTab);
    if (tabId === "networking-shell" || tabId === "security-shell") {
      const scope = HUB_TABS[tabId]?.shellScope === "security" ? "security" : "network";
      const sid = sub && !String(sub).includes("/") ? sub : activeTermId;
      return diagnosticsShellRouteSub(scope, sid);
    }
    if (tabId === "diagnostics") {
      if (diagnosticsPane === "shell") return diagnosticsShellRouteSub(diagnosticsShellScope, activeTermId);
      if (diagnosticsPane === "packages") return "packages";
    }
    return null;
  }

  function categorySlug(name) {
    return String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || "general";
  }

  function categoryFromSlug(slug, categories) {
    const want = String(slug || "").toLowerCase();
    return (categories || []).find((c) => categorySlug(c) === want) || null;
  }

  function routeFromCanonicalPath(pathKey) {
    const parts = String(canonicalHubPath(pathKey) || "").split("/").filter(Boolean);
    if (!parts.length) return { section: "dashboard", tab: null, sub: null };
    if (parts[0] === "networking" || parts[0] === "security") {
      if (parts.length === 1) return { section: parts[0], tab: null, sub: null };
      return routeFromCanonicalPath(["network", ...parts.slice(1)].join("/"));
    }
    if (parts[0] === "tools") {
      if (parts.length === 1) return { section: "tools", tab: null, sub: null };
      return { section: "tools", tab: parts[1] || null, sub: parts[2] || null };
    }
    if (parts[0] === "settings") {
      return parseSettingsRouteParts(parts.slice(1));
    }
    if (parts[0] === "network" && parts[1] === "diagnostics" && parts[2] === "shell") {
      return { section: "network", tab: "networking-shell", sub: parts[3] || null };
    }
    if (parts[0] === "network" && parts[1] === "diagnostics" && parts[2] === "security-shell") {
      return { section: "network", tab: "security-shell", sub: parts[3] || null };
    }
    if (parts[0] === "network" && parts[1] === "diagnostics") {
      if (parts[2] === "packages") return { section: "network", tab: "network-packages", sub: null };
      if (parts[2] === "security-shell") return { section: "network", tab: "security-shell", sub: parts[3] || null };
      if (parts[2] === "shell") return { section: "network", tab: "networking-shell", sub: parts[3] || null };
      if (parts[2] && !parts[2].startsWith("shell") && !parts[2].startsWith("security-shell")) {
        return { section: "network", tab: "networking-shell", sub: null };
      }
      return { section: "network", tab: "networking-shell", sub: null };
    }
    if (parts[0] === "dashboard" && parts[1] === "workflows") {
      return { section: "dashboard", tab: "workflows", sub: parts[2] || null };
    }
    if (parts[0] === "dashboard" && parts[1] === "terminal") {
      return { section: "dashboard", tab: "terminal", sub: parts[2] || null };
    }
    return { section: parts[0], tab: parts[1] || null, sub: parts[2] || null };
  }

  /** Map legacy hash paths to canonical route objects — parse only, never rewrite the URL bar. */
  function normalizeLegacyHashRoute(raw, route) {
    const lower = String(raw || "").replace(/^#/, "").trim().toLowerCase();
    if (!lower) return route;
    const path = (key) => routeFromCanonicalPath(canonicalHubPath(key));

    if (lower === "network/sec-tools") return path("network/security-packages");
    if (lower === "network/install-tools/security") return path("network/security-packages");
    if (lower === "network/install-tools/custom") return path("tools/custom-packages");
    if (lower === "network/install-tools" || lower === "network/install-tools/network" || lower === "network/install-tools/networking") {
      return path("network/network-packages");
    }
    if (lower === "network/setup") return path("network/security-packages");
    if (lower === "network/diagnostics/packages") return path("network/network-packages");
    if (lower === "network/doctor") return path("network/doctors/overview");
    if (lower === "network/doctors/health") return path("network/doctors/overview");
    if (lower === "network/network/bandwidth") return path("network/traffic-live");
    if (lower === "network/network/speed" || lower === "network/traffic/speed") return path("network/traffic-speed");
    if (lower === "map-internet") return path("network/map-internet");
    if (lower === "map-local") return path("network/map-local");
    if (lower === "network/network/config") return path("network/diagnostics");
    if (lower === "network/network") return path("network/network/dns");
    if (lower === "network/wifi/nearby" || lower === "network/wifi/wifi-doctor") return path("network/wifi/profiles");
    if (lower === "network/wifi/scenarios" || lower === "network/wifi-scenarios") return path("dashboard/connect");
    if (lower === "network/wifi/smart-dns" || lower === "network/wifi-smart-dns") return path("dashboard/nord-dns");
    if (lower === "network/alerts/tiers") return path("dashboard/workflows/my-presets");
    if (lower === "network/alerts/disconnect" || lower === "network/alerts/roadmap" || lower === "network/alerts") {
      return path("settings/network/notifications");
    }
    if (lower.startsWith("network/alerts/")) return path("settings/network/notifications");
    if (lower === "network/doctors") return path("network/doctors");
    if (lower === "network/doctors/nordvpn") return path("dashboard/nord-doctor");
    if (lower === "network/wifi-nord-doctor" || lower === "network/wifi/nord-doctor") return path("dashboard/nord-doctor");
    if (lower === "network/wifi-net-doctor" || lower === "network/wifi/net-doctor") return path("network/doctors/net");
    if (lower === "network/audit/leak") return path("network/leak-tests");
    if (lower === "network/terminal") return path("network/diagnostics/shell");
    if (lower.startsWith("network/terminal/")) {
      return routeFromCanonicalPath(`network/diagnostics/shell/${raw.split("/").slice(2).join("/")}`);
    }
    if (lower === "dashboard/scenarios") return path("dashboard/workflows/workflows");
    if (lower === "dashboard/setup") return path("dashboard/wizard");
    if (lower === "dashboard/optional-extras") return path("dashboard/connect");
    if (lower === "dashboard/places") return path("dashboard/workflows/places");
    if (lower === "dashboard/home-lan") return path("dashboard/split-tunnel");
    if (lower === "network/nord-cli") return path("dashboard/terminal");
    if (lower === "dashboard/favorites") return path("dashboard/workflows/favorites");
    if (lower === "dashboard/presets") return path("dashboard/workflows/workflows");
    if (lower === "dashboard/meshnet") return path("dashboard/meshnet");
    if (lower === "dashboard/server-groups") return path("dashboard/connect");
    if (DASHBOARD_TABS_MOVED_TO_SWITCHES.has((route.tab || "").toLowerCase())) return path("dashboard/switches");
    if (lower === "dashboard/advanced" || lower === "dashboard/technology" || lower === "dashboard/nord-firewall" || lower === "dashboard/kill-switch") {
      return path("dashboard/switches");
    }
    if (lower.startsWith("dashboard/presets/")) {
      const cat = raw.split("/").slice(2).join("/");
      const dashTab = dashboardTabForPresetSub(cat);
      return dashTab ? path(`dashboard/${dashTab}`) : path("dashboard/workflows/places");
    }
    if (lower === "network/profiles") return path("dashboard/workflows/workflows");
    if (lower === "dashboard/host-ufw") return path("network/host-ufw");
    if (lower === "tools") return path("tools/auto-guide");
    if (lower.startsWith("tools/") && !lower.startsWith("tools/settings") && !lower.startsWith("tools/terminal")
        && !lower.startsWith("tools/editor/help")) {
      const rest = raw.split("/").slice(1).join("/");
      if (rest === "editor" || rest.startsWith("editor/")) {
        return rest === "editor" ? path("tools/editor") : routeFromCanonicalPath(`tools/${rest}`);
      }
      return routeFromCanonicalPath(`tools/${rest}`);
    }
    if (lower === "tools/settings") return path("settings");
    if (lower === "dashboard/terminal") return path("dashboard/terminal");
    if (lower.startsWith("dashboard/terminal/")) {
      return routeFromCanonicalPath(`dashboard/terminal/${raw.split("/").slice(2).join("/")}`);
    }
    if (lower === "tools/terminal") return path("dashboard/terminal");
    if (lower.startsWith("tools/terminal/")) {
      return routeFromCanonicalPath(`dashboard/terminal/${raw.split("/").slice(2).join("/")}`);
    }
    if (lower === "tools/editor/help" || lower.startsWith("tools/editor/help/")) {
      const sub = raw.split("/").slice(3).join("/") || null;
      return sub ? path(`help/${sub}`) : path("help");
    }
    if (lower.startsWith("tools/editor/")) return path("tools/editor");
    const legacyView = LEGACY_ROUTE_HASH[lower];
    if (legacyView) return routeFromCanonicalPath(legacyView);
    if (lower.startsWith("tools/settings/")) {
      const rest = raw.split("/").slice(2);
      if (rest[0] === "nord" || rest[0] === "network") {
        return rest[1]
          ? routeFromCanonicalPath(`settings/${rest[0]}/${rest[1]}`)
          : routeFromCanonicalPath(`settings/${rest[0]}/${defaultSettingsTab(rest[0], installProfile(lastState))}`);
      }
      const legacy = rest[0];
      if (legacy === "language") {
        const def = defaultSettingsRoute(lastState);
        return routeFromCanonicalPath(`settings/${def.scope}/${def.tab}`);
      }
      const scope = legacySettingsScope(legacy, installProfile(lastState));
      return scope ? routeFromCanonicalPath(`settings/${scope}/${legacy}`) : path("settings");
    }
    if (lower.startsWith("settings/language")) {
      const def = defaultSettingsRoute(lastState);
      return routeFromCanonicalPath(`settings/${def.scope}/${def.tab}`);
    }
    if (lower === "settings/password") return path("settings/general/password");
    if (lower === "settings/services") return path("settings/general/services");
    if (lower === "settings/notifications") return path("settings/alerts/notifications");
    if (lower === "settings/email") return path("settings/alerts/email");
    if (lower.startsWith("settings/nord/")) return path(lower.replace("settings/nord/", "settings/general/"));
    if (lower.startsWith("settings/network/")) return path(lower.replace("settings/network/", "settings/alerts/"));
    const parts = raw.split("/");
    if (parts.length >= 2 && parts[0] === "network" && WIFI_LEGACY_HUB[parts[1]]) {
      const sub = WIFI_LEGACY_HUB[parts[1]];
      return sub && sub !== "profiles" ? path(`network/wifi/${sub}`) : path("network/wifi");
    }
    if (route.section === "tools" && route.tab && route.tab !== "settings") {
      return routeFromCanonicalPath(`tools/${route.tab}`);
    }
    if (route.section === "network" && route.tab === "diagnostics" && route.sub === "packages") {
      return path("network/network-packages");
    }
    return route;
  }

  function parseRouteHash() {
    let raw = (location.hash || "").replace(/^#/, "").trim();
    if (!raw) return { section: "dashboard", tab: null, sub: null, routePrefix: null };
    let lower = raw.toLowerCase();
    if (lower === "help") return { section: "help", tab: null, sub: null, routePrefix: null };
    if (lower === "dashboard") return { section: "dashboard", tab: null, sub: null, routePrefix: null };
    if (lower === "networking") return { section: "networking", tab: null, sub: null, routePrefix: "networking" };
    if (lower === "security") return { section: "security", tab: null, sub: null, routePrefix: "security" };
    if (lower === "network") return { section: "network", tab: null, sub: null, routePrefix: null };
    if (lower === "settings") return { section: "settings", tab: null, sub: null, routePrefix: null };
    if (lower === "tools") return { section: "tools", tab: null, sub: null, routePrefix: null };
    let routePrefix = null;
    if (lower.startsWith("networking/")) {
      routePrefix = "networking";
      raw = `network/${raw.slice("networking/".length)}`;
    } else if (lower.startsWith("security/")) {
      routePrefix = "security";
      raw = `network/${raw.slice("security/".length)}`;
    }
    lower = raw.toLowerCase();
    if (!raw.includes("/")) {
      const mapped = LEGACY_ROUTE_HASH[lower];
      if (mapped) {
        const parts = mapped.split("/");
        return { section: parts[0], tab: parts[1] || null, sub: parts[2] || null };
      }
    }
    const parts = raw.split("/").map((p) => p.replace(/_/g, "-"));
    const section = parts[0] || "dashboard";
    if (section === "dashboard" && parts[1] === "host-ufw") {
      return { section: "network", tab: "host-ufw", sub: null };
    }
    if (section === "network" && parts[1] === "wifi") {
      if (parts[2] === "scenarios") return { section: "dashboard", tab: "connect", sub: null };
      if (parts[2] === "smart-dns") return { section: "dashboard", tab: "nord-dns", sub: null };
      return { section: "network", tab: "wifi", sub: parts[2] || null };
    }
    if (section === "network" && parts[1] === "doctors") {
      if (parts[2] === "nordvpn") return { section: "dashboard", tab: "nord-doctor", sub: null };
      return { section: "network", tab: "doctors", sub: parts[2] || null };
    }
    if (section === "network" && parts[1] === "doctor") {
      return { section: "network", tab: "doctors", sub: "overview" };
    }
    if (section === "network" && WIFI_LEGACY_HUB[parts[1]]) {
      return { section: "network", tab: "wifi", sub: WIFI_LEGACY_HUB[parts[1]] };
    }
    if (section === "help") {
      return { section: "help", tab: null, sub: parts[1] || null };
    }
    /* Whole hub tab ids with dashes (network-packages) must win over tab-sub splits (network + packages). */
    if (section === "network" && parts.length === 2 && HUB_TABS[parts[1]]) {
      return { section: "network", tab: parts[1], sub: null, routePrefix };
    }
    /* Compound hub routes: #network/diagnostics-traceroute → tab + tool sub-route (not dashboard tabs like split-tunnel). */
    if (parts.length === 2 && parts[1].includes("-") && section !== "dashboard") {
      const dash = parts[1].indexOf("-");
      const maybeTab = parts[1].slice(0, dash);
      const maybeSub = parts[1].slice(dash + 1);
      if (maybeTab && maybeSub && HUB_TABS[maybeTab]) {
        return { section, tab: maybeTab, sub: maybeSub };
      }
    }
    if (section === "tools" && parts[1] === "terminal") {
      return { section: "tools", tab: "terminal", sub: parts[2] || null };
    }
    if (section === "tools" && parts[1] && parts[1] !== "settings" && parts[1] !== "terminal" && parts[1] !== "editor") {
      return { section: "tools", tab: parts[1], sub: parts[2] || null };
    }
    if (section === "tools" && parts[1] === "settings") {
      return parseSettingsRouteParts(parts.slice(2));
    }
    if (section === "settings") {
      return parseSettingsRouteParts(parts.slice(1));
    }
    if (section === "network" && parts[1] === "traffic") {
      const sub = parts[2] || "internet";
      if (sub === "live") return { section: "network", tab: "traffic-live", sub: null };
      if (sub === "speed") return { section: "network", tab: "traffic-speed", sub: null };
      if (sub === "local") return { section: "network", tab: "map-local", sub: null };
      return { section: "network", tab: "map-internet", sub: null };
    }
    if (section === "network" && parts[1] === "audit") {
      if (parts[2] === "leak") return normalizeLegacyHashRoute(raw, { section: "network", tab: "leak-tests", sub: null });
      return normalizeLegacyHashRoute(raw, { section: "network", tab: "audit", sub: parts[2] || null });
    }
    if (section === "network" && parts[1] === "diagnostics") {
      if (parts[2] === "shell") {
        return { section: "network", tab: "networking-shell", sub: parts[3] || null };
      }
      if (parts[2] === "security-shell") {
        return { section: "network", tab: "security-shell", sub: parts[3] || null };
      }
      if (parts[2] === "packages") return { section: "network", tab: "network-packages", sub: null };
      if (parts[2] && !parts[2].startsWith("shell") && !parts[2].startsWith("security-shell")) {
        return { section: "network", tab: "networking-shell", sub: null };
      }
      return { section: "network", tab: "networking-shell", sub: null };
    }
    if (section === "network" && parts[1] === "profiles") {
      return { section: "dashboard", tab: "workflows", sub: "workflows" };
    }
    if (section === "network" && parts[1] === "setup") {
      return { section: "network", tab: "security-packages", sub: null };
    }
    if (section === "network" && LEGACY_HUB_TABS[parts[1]]) {
      const leg = LEGACY_HUB_TABS[parts[1]];
      return { section: "network", tab: leg.redirectTab, sub: leg.redirectSub };
    }
    if (section === "network" && parts[1] === "sec-tools") {
      return { section: "network", tab: "security-packages", sub: null };
    }
    if (section === "network" && parts[1] === "install-tools") {
      const sub = (parts[2] || "").toLowerCase();
      if (sub === "security") return { section: "network", tab: "security-packages", sub: null };
      return { section: "network", tab: "network-packages", sub: null };
    }
    if (section === "network" && parts[1] === "network" && NETWORK_LEGACY_SUB[parts[2]]) {
      const leg = NETWORK_LEGACY_SUB[parts[2]];
      return { section: "network", tab: leg.tab, sub: leg.sub };
    }
    if (section === "network" && parts[1] === "tools") {
      return { section: "tools", tab: parts[2] || "auto-guide", sub: null };
    }
    if (section === "tools" && parts[1] === "editor") {
      return { section: "tools", tab: "editor", sub: null };
    }
    return normalizeLegacyHashRoute(raw, {
      section,
      tab: parts[1] || null,
      sub: parts[2] || null,
    });
  }

  function currentRouteKey() {
    const route = parseRouteHash();
    if (route.section === "help") return route.sub ? `help/${route.sub}` : "help";
    if (route.section === "dashboard") {
      if (!route.tab) return "dashboard";
      const tab = normalizeDashboardTab(route.tab || dashTab || "connect");
      if (tab === "workflows" && route.sub) return `dashboard/workflows/${route.sub}`;
      if (tab === "terminal") return "dashboard/terminal";
      return `dashboard/${tab}`;
    }
    if (route.section === "networking" || route.section === "security") {
      return buildRouteHash(route.section, route.tab || HUB_PRIMARY_DEFAULT_TAB[route.section], route.sub).slice(1);
    }
    if (route.section === "network") {
      const tab = route.tab || hubTab || HUB_PRIMARY_DEFAULT_TAB[hubPrimaryTab] || "wifi";
      if (tab === "tools") {
        return buildRouteHash("tools", route.sub || toolsTab || "auto-guide", null).slice(1);
      }
      return buildRouteHash(hubPrimaryTab, tab, route.sub).slice(1);
    }
    if (route.section === "settings") {
      if (!route.tab && !route.sub) return "settings";
      const { scope, tab } = resolveSettingsRoute(route);
      return settingsRouteKey(scope, tab);
    }
    if (route.section === "tools") {
      return buildRouteHash("tools", route.tab || toolsTab || "auto-guide", null).slice(1);
    }
    return "dashboard";
  }

  function tabIntroForRouteKey(key) {
    return TAB_INTROS[key]
      || TAB_INTROS[key.replace(/^networking\//, "network/").replace(/^security\//, "network/")]
      || TAB_INTROS.dashboard;
  }

  function openHelpSection(helpId) {
    pendingHelpSection = helpId || "start";
    navigateRoute("help", null, { sub: pendingHelpSection });
  }

  function syncPageIntro() {
    const bar = $("pageIntroBar");
    const titleEl = $("pageIntroTitle");
    const textEl = $("pageIntroText");
    const btn = $("pageIntroHelpBtn");
    const route = parseRouteHash();
    if (bar && titleEl && textEl) {
      const hideIntro = route.section === "help"
        || route.section === "dashboard"
        || route.section === "settings"
        || uiPrefs.page_intro_visible === false;
      if (hideIntro) {
        bar.classList.add("page-intro-hidden");
      } else {
        bar.classList.remove("page-intro-hidden");
        const key = currentRouteKey();
        const intro = tabIntroForRouteKey(key);
        titleEl.textContent = intro.title;
        textEl.innerHTML = intro.text;
        if (btn) {
          btn.classList.remove("hidden");
          btn.onclick = () => openHelpSection(intro.help);
        }
      }
      const settingsHelp = $("settingsPageHelpBtn");
      if (settingsHelp) {
        if (route.section === "settings" || getActiveView() === "settings") {
          const intro = tabIntroForRouteKey(currentRouteKey());
          settingsHelp.classList.remove("hidden");
          settingsHelp.onclick = () => openHelpSection(intro.help);
        } else {
          settingsHelp.classList.add("hidden");
        }
      }
    }
    syncPageHow();
  }

  /** Canonical hash routes — always navigate with buildRouteHash(); legacy paths parse via normalizeLegacyHashRoute only. */
  function buildRouteHash(section, tab, sub) {
    if (section === "help") return sub ? `#help/${sub}` : "#help";
    if (section === "tools" || tab === "tools") {
      const toolTab = section === "tools" ? tab : sub;
      if (!toolTab || toolTab === "settings") return "#settings";
      if (toolTab === "custom-shell" && sub) return `#tools/custom-shell/${sub}`;
      if (toolTab === "custom-packages" && sub) return `#tools/custom-packages/${sub}`;
      return toolTab ? `#tools/${toolTab}` : "#tools/auto-guide";
    }
    if (!tab) {
      if (section === "dashboard") return "#dashboard";
      if (section === "networking") return "#networking";
      if (section === "security") return "#security";
      if (section === "network") return `#${hubPrimaryTab || "networking"}`;
      if (section === "settings") return "#settings";
      if (section === "tools") return "#tools/auto-guide";
    }
    if (section === "dashboard" && tab === "workflows" && sub) return `#dashboard/workflows/${sub}`;
    if (section === "dashboard" && tab === "terminal") {
      return sub ? `#dashboard/terminal/${sub}` : "#dashboard/terminal";
    }
    if (section === "tools" && tab === "terminal") {
      return sub ? `#dashboard/terminal/${sub}` : "#dashboard/terminal";
    }
    if (section === "settings") {
      if (!tab) {
        const def = defaultSettingsRoute(lastState);
        return `#settings/${def.scope}/${def.tab}`;
      }
      const scope = tab;
      const tabId = sub || defaultSettingsTab(scope, installProfile(lastState));
      return `#settings/${scope}/${tabId}`;
    }
    if (isHubRouteSection(section) || (section === "network" && tab)) {
      const hint = section === "networking" || section === "security" ? section : null;
      const p = hubRoutePrefixForTab(tab, hint);
      if (tab === "networking-shell" || tab === "security-shell") {
        const scope = HUB_TABS[tab]?.shellScope === "security" ? "security" : "network";
        const shellSub = sub && !String(sub).includes("/")
          ? diagnosticsShellRouteSub(scope, sub)
          : (sub || diagnosticsShellRouteSub(scope, activeTermId));
        return `#${p}/diagnostics/${shellSub}`;
      }
      if (tab === "diagnostics") {
        if (sub === "shell") return `#${p}/diagnostics/shell`;
        if (sub && sub.startsWith("shell/")) return `#${p}/diagnostics/${sub}`;
        if (sub === "security-shell") return `#${p}/diagnostics/security-shell`;
        if (sub && sub.startsWith("security-shell/")) return `#${p}/diagnostics/${sub}`;
        if (sub === "packages") return `#${p}/network-packages`;
        if (sub) return `#${p}/diagnostics/${sub}`;
        return `#${p}/diagnostics/shell`;
      }
      if (tab === "audit") return `#${p}/audit`;
      if (tab === "leak-tests") return `#${p}/leak-tests`;
      if (tab === "network-packages") return `#${p}/network-packages`;
      if (tab === "security-packages") return `#${p}/security-packages`;
      if (tab === "listeners") return `#${p}/listeners`;
      if (tab === "privileges") return `#${p}/privileges`;
      if (tab === "map-internet") return `#${p}/map-internet`;
      if (tab === "map-local") return `#${p}/map-local`;
      if (tab === "traffic-live") return `#${p}/traffic-live`;
      if (tab === "traffic-speed") return `#${p}/traffic-speed`;
      if (tab === "spectrum-analyzer") return `#${p}/spectrum-analyzer`;
      if (tab === "bluetooth-spectrum") return `#${p}/bluetooth-spectrum`;
      if (tab === "wifi") {
        const subId = sub && WIFI_HUB_TABS[sub] ? sub : (WIFI_LEGACY_SUB[sub] || wifiHubTab || "profiles");
        return wifiRouteSub(subId) ? `#${p}/wifi/${subId}` : `#${p}/wifi`;
      }
      if (tab === "doctors") {
        const subId = sub === "health" ? "overview" : (sub && DOCTORS_HUB_TABS[sub] ? sub : doctorsHubTab || "overview");
        return doctorsRouteSub(subId) ? `#${p}/doctors/${subId}` : `#${p}/doctors`;
      }
      if (tab === "network") {
        const subId = sub && NETWORK_HUB_TABS[sub] ? sub : networkHubTab || "dns";
        return networkRouteSub(subId) ? `#${p}/network/${subId}` : `#${p}/network/dns`;
      }
      if (tab === "traffic") {
        const subId = sub && TRAFFIC_HUB_TABS[sub] ? sub : trafficHubTab || "internet";
        if (subId === "local") return `#${p}/map-local`;
        if (subId === "live") return `#${p}/traffic-live`;
        return `#${p}/map-internet`;
      }
      if (sub) return `#${p}/${tab || "monitoring"}/${sub}`;
      if (section === "dashboard") return `#dashboard/${tab || "connect"}`;
      return `#${p}/${tab || (p === "security" ? "monitoring" : "wifi")}`;
    }
    if (section === "dashboard") return `#dashboard/${tab || "connect"}`;
    return "#dashboard";
  }

  function syncRouteHash(section, tab, replace, sub) {
    const target = buildRouteHash(section, tab, sub);
    if (location.hash === target) return;
    const url = `${location.pathname}${location.search}${target}`;
    if (replace) history.replaceState(null, "", url);
    else location.hash = target.slice(1);
  }

  function stopTabLoadingMessages() {
    if (tabLoadingMsgTimer) {
      clearInterval(tabLoadingMsgTimer);
      tabLoadingMsgTimer = null;
    }
  }

  function pickTabLoadingLine(pool, avoid) {
    if (!pool?.length) return "";
    if (pool.length === 1) return pool[0];
    let pick = pool[Math.floor(Math.random() * pool.length)];
    let guard = 0;
    while (pick === avoid && guard++ < 8) {
      pick = pool[Math.floor(Math.random() * pool.length)];
    }
    return pick;
  }

  function setTabLoadingMessage(title, msg, fade) {
    const titleEl = $("tabLoadingTitle");
    const msgEl = $("tabLoadingMsg");
    if (titleEl && title) titleEl.textContent = title;
    if (!msgEl || !msg) return;
    if (!fade) {
      msgEl.classList.remove("is-fading");
      msgEl.textContent = msg;
      return;
    }
    msgEl.classList.add("is-fading");
    setTimeout(() => {
      if (tabLoadingDepth <= 0) return;
      msgEl.textContent = msg;
      msgEl.classList.remove("is-fading");
    }, 180);
  }

  function startTabLoadingMessages() {
    stopTabLoadingMessages();
    tabLoadingMsgIndex = 0;
    setTabLoadingMessage(
      pickTabLoadingLine(TAB_LOADING_TITLES),
      pickTabLoadingLine(TAB_LOADING_MESSAGES),
      false,
    );
    tabLoadingMsgTimer = setInterval(() => {
      if (tabLoadingDepth <= 0) {
        stopTabLoadingMessages();
        return;
      }
      const msgEl = $("tabLoadingMsg");
      const prev = msgEl?.textContent || "";
      if (tabLoadingMsgIndex % 4 === 0) {
        setTabLoadingMessage(pickTabLoadingLine(TAB_LOADING_TITLES, $("tabLoadingTitle")?.textContent), null, false);
      }
      setTabLoadingMessage(null, pickTabLoadingLine(TAB_LOADING_MESSAGES, prev), true);
      tabLoadingMsgIndex += 1;
    }, 2400);
  }

  function showTabLoading(on) {
    const el = $("tabLoadingOverlay");
    if (!el) return;
    const wasBusy = tabLoadingDepth > 0;
    tabLoadingDepth += on ? 1 : -1;
    if (tabLoadingDepth < 0) tabLoadingDepth = 0;
    const busy = tabLoadingDepth > 0;
    el.classList.toggle("hidden", !busy);
    el.hidden = !busy;
    el.setAttribute("aria-busy", busy ? "true" : "false");
    if (busy && !wasBusy) startTabLoadingMessages();
    else if (!busy) stopTabLoadingMessages();
  }

  function resetTabLoading() {
    tabLoadingDepth = 0;
    stopTabLoadingMessages();
    const el = $("tabLoadingOverlay");
    if (el) {
      el.classList.add("hidden");
      el.hidden = true;
      el.setAttribute("aria-busy", "false");
    }
  }

  async function withTabLoading(task) {
    showTabLoading(true);
    try {
      return await task();
    } finally {
      showTabLoading(false);
    }
  }

  function viewFromHash() {
    const route = parseRouteHash();
    if (route.section === "help") return "help";
    if (route.section === "dashboard") {
      if (route.tab === "terminal") return "terminal";
      return "dashboard";
    }
    if (route.section === "settings") return "settings";
    if (route.section === "tools") {
      if (route.tab === "terminal") return "terminal";
      const cfg = NETWORK_TOOLS_TABS[route.tab || "logs"];
      return cfg?.view || "logs";
    }
    if (route.section === "network") {
      if (route.tab === "tools") {
        const cfg = NETWORK_TOOLS_TABS[route.sub || toolsTab || "auto-guide"];
        return cfg?.view || "logs";
      }
      const cfg = HUB_TABS[route.tab || "monitoring"];
      return cfg?.view || "security";
    }
    return "dashboard";
  }

  function resolveViewName(name) {
    if (!VALID_VIEWS.has(name)) return "dashboard";
    if (HUB_VIEWS.has(name) || TOOLS_VIEWS.has(name) || name === "help" || name === "dashboard") return name;
    const pill = document.querySelector(`.nav-pill[data-view="${name}"]`);
    if (pill?.classList.contains("hidden")) return "dashboard";
    return name;
  }

  function getActiveView() {
    const active = document.querySelector(".view.active");
    if (!active) return "dashboard";
    const id = active.id || "";
    if (id === "viewDashboard") return "dashboard";
    if (id === "viewHelp") return "help";
    return id.replace(/^view/, "").charAt(0).toLowerCase() + id.replace(/^view/, "").slice(1);
  }

  function syncViewHash(name, replace) {
    /* legacy — use syncRouteHash instead */
    if (name === "dashboard") syncRouteHash("dashboard", dashTab, replace);
    else if (name === "help") syncRouteHash("help", null, replace);
    else if (HUB_VIEWS.has(name)) syncRouteHash(hubPrimaryTab, hubTabIdForView(name), replace);
    else if (name === "settings") syncRouteHash("settings", settingsScope, replace, settingsTab);
    else if (TOOLS_VIEWS.has(name)) syncRouteHash("tools", toolsTabIdForView(name), replace);
  }

  function syncSettingsNavActive(on) {
    $("btnSettings")?.classList.toggle("active", !!on);
  }

  function finishRouteHash(section, tab, sub, fromHash, replaceHash) {
    syncRouteHash(section, tab, fromHash ? true : !!replaceHash, sub);
  }

  function hashRoutePrefixHint() {
    const raw = (location.hash || "").replace(/^#/, "").trim().toLowerCase();
    if (raw === "security" || raw.startsWith("security/")) return "security";
    if (raw === "networking" || raw.startsWith("networking/")) return "networking";
    return null;
  }

  function applyHubRoutePrefix(route) {
    const prefix = route?.routePrefix || hashRoutePrefixHint();
    if (!prefix || !HUB_PRIMARY_TABS[prefix]) return;
    hubPrimaryTab = prefix;
    localStorage.setItem(HUB_PRIMARY_KEY, hubPrimaryTab);
    syncHubPrimaryHighlight(hubPrimaryTab);
    syncHubTabsVisibility();
  }

  function applyRoute(fromHash, replaceHash) {
    let route = parseRouteHash();
    const scrollLanAfterLoad = fromHash && (location.hash || "").replace(/^#/, "").trim().toLowerCase() === "dashboard/home-lan";
    const nordBlocked = redirectNordBlockedRoute(route);
    if (nordBlocked) route = nordBlocked;
    if (route.section === "help") {
      if (route.sub) pendingHelpSection = route.sub;
      switchView("help", { fromHash: true, force: true });
      finishRouteHash("help", null, route.sub, fromHash, replaceHash);
      syncPageIntro();
      return;
    }
    if (route.section === "dashboard") {
      if (route.tab === "terminal") {
        openDashboardNordShell({ fromHash: true, sub: route.sub }).finally(() => {
          finishRouteHash("dashboard", "terminal", route.sub, fromHash, replaceHash);
          syncPageIntro();
        });
        return;
      }
      const tab = resolveDashboardTab(route.tab, dashTab);
      dashTab = tab;
      localStorage.setItem(DASH_TAB_KEY, dashTab);
      if (tab === "workflows" && route.sub && !WORKFLOW_SECTIONS.has(route.sub)) {
        pendingPresetCategory = route.sub;
      }
      switchView("dashboard", { fromHash: true, force: true });
      switchPageTabs("dashboard", tab, { skipHash: true });
      const dashLoads = [loadNordRoutingPanel?.()];
      if (tab === "terminal") {
        termMountPanel("dashboard");
        dashLoads.push(loadTerminal());
      } else if (tab === "switches") dashLoads.push(loadSwitchesPanel(true, true));
      if (tab === "connection-details") dashLoads.push(loadConnectionDetails());
      if (tab === "meshnet") dashLoads.push(loadMeshnetPage(true));
      if (tab === "create-presets") dashLoads.push(initPresetBuilderPage());
      if (tab === "connect") dashLoads.push(loadConnectExtras(true));
      if (tab === "wizard") {
        dashLoads.push(api("/api/doctor").then(renderDoctor).catch(() => {}));
        dashLoads.push(loadWizard(true).then((w) => {
          renderSetupWizardChecklist(w);
          updateWizardGateButtons();
          if (wizardUiMode === "hidden") showWizardPanel(true);
        }).catch(() => {}));
      } else if (tab === "nord-doctor") {
        dashLoads.push(loadNordDoctor(true));
      } else if (tab === "nord-services") {
        dashLoads.push(api("/api/service").then((s) => renderServicePanel(s?.services || s)).catch(() => {}));
      }
      Promise.all(dashLoads.map((p) => Promise.resolve(p).catch(() => {}))).finally(() => {
        if (tab === "workflows") applyWorkflowsSubRoute(route.sub);
        if (scrollLanAfterLoad) scrollToLanRangeOnly();
      });
      finishRouteHash("dashboard", tab, route.sub, fromHash, replaceHash);
      syncPageIntro();
      return;
    }
    if (route.section === "networking" || route.section === "security") {
      hubPrimaryTab = route.section;
      localStorage.setItem(HUB_PRIMARY_KEY, hubPrimaryTab);
      route = {
        section: "network",
        tab: route.tab || HUB_PRIMARY_DEFAULT_TAB[hubPrimaryTab],
        sub: route.sub,
      };
    }
    if (route.section === "network") {
      applyHubRoutePrefix(route);
      if (route.tab === "networking" || route.tab === "security") {
        const group = route.tab;
        hubPrimaryTab = group;
        localStorage.setItem(HUB_PRIMARY_KEY, group);
        const groupTab = route.sub && HUB_TABS[route.sub] && hubTabGroup(route.sub) === group
          ? route.sub
          : null;
        route = {
          section: "network",
          tab: groupTab || (hubTabsInGroup(group).includes(hubTab)
            ? hubTab
            : HUB_PRIMARY_DEFAULT_TAB[group]),
          sub: groupTab ? null : route.sub,
        };
      }
      const networkRoot = !route.tab;
      const tab = (route.tab && (HUB_TABS[route.tab] || route.tab === "tools"))
        ? route.tab
        : (networkRoot
          ? HUB_PRIMARY_DEFAULT_TAB[hubPrimaryTab || "networking"]
          : (hubTab && HUB_TABS[hubTab] ? hubTab : HUB_PRIMARY_DEFAULT_TAB[hubPrimaryTab || "networking"]));
      if (tab === "terminal" && route.sub) pendingTermSessionId = route.sub;
      const scope = nettoolScopeForHubTab(tab);
      if (scope && route.sub && tab !== "tools" && tab !== "diagnostics"
        && tab !== "networking-shell" && tab !== "security-shell") {
        pendingNettoolTool = { scope, toolId: route.sub.toLowerCase() };
      }
      if (tab === "diagnostics" && route.sub && diagnosticsPaneFromSub(route.sub) === "checks") {
        pendingNettoolTool = { scope: "adv", toolId: route.sub.toLowerCase() };
      }
      if ((tab === "networking-shell" || tab === "security-shell" || tab === "diagnostics") && route.sub) {
        const sessId = diagnosticsTermSessionFromSub(route.sub) || (route.sub.includes("/") ? null : route.sub);
        if (sessId) pendingTermSessionId = sessId;
        else if (fromHash && tab === "diagnostics") {
          diagnosticsPane = diagnosticsPaneFromSub(route.sub);
          localStorage.setItem(DIAG_PANE_KEY, diagnosticsPane);
        }
        const shellScope = tab === "security-shell" ? "security"
          : (tab === "networking-shell" ? "network" : diagnosticsShellScopeFromSub(route.sub));
        if (shellScope) syncDiagnosticsShellScope(shellScope, { skipHash: true });
      }
      if (tab === "audit" && route.sub && fromHash && route.sub !== "leak") {
        auditPane = auditPaneFromSub(route.sub);
        localStorage.setItem(AUDIT_PANE_KEY, auditPane);
        localStorage.setItem(DIAGNOSTICS_TAB_KEY, auditPane === "leak" ? "leak" : "overall");
      }
      switchHubTab(tab, { fromHash: true, skipHash: true, sub: route.sub });
      let canonSub = route.sub;
      if (tab === "wifi") canonSub = wifiRouteSub(wifiHubTab);
      else if (tab === "doctors") canonSub = doctorsRouteSub(doctorsHubTab);
      else if (tab === "network") canonSub = networkRouteSub(networkHubTab);
      else if (tab === "networking-shell" || tab === "security-shell") {
        canonSub = route.sub || activeTermId || null;
      }
      else if (tab === "diagnostics") {
        canonSub = diagnosticsPane === "shell"
          ? diagnosticsShellRouteSub(diagnosticsShellScope, activeTermId)
          : (diagnosticsPane === "packages" ? "packages" : (route.sub && !route.sub.startsWith("shell") && !route.sub.startsWith("security-shell") ? route.sub : null));
      }
      else if (tab === "audit" || tab === "leak-tests") {
        canonSub = null;
      }
      else if (tab === "tools") canonSub = route.sub || toolsTab || "auto-guide";
      if (tab === "tools") finishRouteHash("tools", canonSub, null, fromHash, replaceHash);
      else finishRouteHash(hubPrimaryTab, tab, canonSub, fromHash, replaceHash);
      syncPageIntro();
      return;
    }
    if (route.section === "settings") {
      syncSettingsFromHash();
      const { scope, tab } = resolveSettingsRoute(route);
      switchSettingsView(scope, tab, { fromHash: true, skipHash: true });
      finishRouteHash("settings", scope, tab, fromHash, replaceHash);
      syncPageIntro();
      return;
    }
    if (route.section === "tools") {
      if (route.tab === "terminal") {
        if (route.sub) pendingTermSessionId = route.sub;
        openDashboardNordShell({ fromHash: true, sub: route.sub }).finally(() => {
          finishRouteHash("dashboard", "terminal", route.sub, fromHash, replaceHash);
          syncPageIntro();
        });
        return;
      }
      const tab = route.tab && NETWORK_TOOLS_TABS[route.tab]
        ? route.tab
        : (NETWORK_TOOLS_TABS[toolsTab] ? toolsTab : "auto-guide");
      if (tab === "custom-shell" && route.sub) customShellCategory = route.sub;
      if (tab === "custom-packages" && route.sub) customPackagesCategory = route.sub;
      switchHubTab("tools", { fromHash: true, skipHash: true, sub: tab, toolsSub: route.sub || null });
      finishRouteHash("tools", tab, route.sub || null, fromHash, replaceHash);
      syncPageIntro();
      return;
    }
    syncPageIntro();
  }

  function navigateRoute(section, tab, opts = {}) {
    let hash;
    if (section === "settings") {
      const resolved = resolveSettingsRoute({ section: "settings", tab, sub: opts.sub ?? null });
      hash = buildRouteHash("settings", resolved.scope, resolved.tab);
    } else {
      hash = buildRouteHash(section, tab, opts.sub || null);
    }
    if (location.hash === hash) {
      applyRoute(true, false);
      if (section === "dashboard" && tab === "split-tunnel" && opts.scrollLan) scrollToLanRangeOnly();
      return;
    }
    location.hash = hash.slice(1);
  }

  function invalidateTabNavIfRev(navEl, revKey, currentRev, tabAttr) {
    if (!navEl) return;
    const stored = localStorage.getItem(revKey);
    if (stored !== String(currentRev)) {
      delete navEl.dataset.rendered;
      navEl.querySelectorAll(`[${tabAttr}]`).forEach((btn) => btn.remove());
      localStorage.setItem(revKey, String(currentRev));
    }
  }

  function buildFlatTabBtn(tabId, cfg, tabAttr, section) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "hub-subnav-btn";
    if (section === "dashboard") btn.classList.add("page-tab-btn");
    if (tabId === "editor") btn.classList.add("hub-subnav-last-resort");
    if (cfg.nordOnly) btn.dataset.nordOnly = "1";
    if (tabId === "optional-extras") btn.classList.add("hidden");
    btn.setAttribute(tabAttr, tabId);
    btn.dataset.tabHash = tabId === "settings"
      ? "settings/general/password"
      : (cfg.shellScope
        ? hubShellTabHash(tabId)?.slice(1)
        : (section === "tools"
          ? `tools/${tabId}`
          : (section === "dashboard" ? `dashboard/${tabId}` : `${hubRoutePrefixForTab(tabId)}/${tabId}`)));
    if (section === "network" && cfg.group) btn.dataset.hubGroup = cfg.group;
    btn.title = cfg.title || cfg.label || tabId;
    btn.textContent = cfg.label || tabId;
    return btn;
  }

  function renderFlatTabNav(navEl, tabsCfg, tabAttr, section) {
    if (!navEl) return;
    if (navEl.dataset.rendered) {
      const added = document.createDocumentFragment();
      navEl.querySelectorAll(`[${tabAttr}]`).forEach((btn) => {
        const tabId = btn.getAttribute(tabAttr);
        const cfg = tabsCfg[tabId];
        if (cfg) {
          btn.textContent = cfg.label || tabId;
          btn.title = cfg.title || cfg.label || tabId;
        }
        if (tabAttr === "data-tools-tab") {
          btn.classList.remove("hidden");
        }
      });
      Object.keys(tabsCfg).forEach((tabId) => {
        const cfg = tabsCfg[tabId];
        if (cfg?.topbarOnly) {
          navEl.querySelector(`[${tabAttr}="${tabId}"]`)?.remove();
          return;
        }
        let btn = navEl.querySelector(`[${tabAttr}="${tabId}"]`);
        if (!btn) {
          btn = buildFlatTabBtn(tabId, cfg, tabAttr, section);
          added.appendChild(btn);
        }
        navEl.appendChild(btn);
      });
      if (added.childNodes.length) navEl.appendChild(added);
      return;
    }
    navEl.dataset.rendered = "1";
    const frag = document.createDocumentFragment();
    Object.entries(tabsCfg).forEach(([tabId, cfg]) => {
      if (cfg?.topbarOnly) return;
      frag.appendChild(buildFlatTabBtn(tabId, cfg, tabAttr, section));
    });
    navEl.appendChild(frag);
  }

  function syncDashTabHighlight(tabId) {
    $("dashSubnav")?.querySelectorAll("[data-page-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-page-tab") === tabId);
    });
  }

  function syncHubPrimaryHighlight(groupId) {
    document.querySelectorAll(".nav-pill[data-hub-primary]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-hub-primary") === groupId);
    });
  }

  function syncToolsTabsVisibility(data) {
    $("toolsSubnav")?.querySelectorAll("[data-tools-tab]").forEach((btn) => {
      btn.classList.remove("hidden");
    });
  }

  function renderAutomateNordGates(data) {
    document.querySelectorAll("[data-nord-tools-panel]").forEach((el) => {
      el.classList.remove("hidden");
    });
    document.querySelectorAll("[data-nord-tools-fallback]").forEach((el) => {
      el.classList.add("hidden");
    });
    $("btnSnapshotRestore")?.classList.remove("hidden");
    $("btnSnapshotRestoreOnly")?.classList.remove("hidden");
  }

  function syncHubTabsVisibility() {
    $("hubSubnav")?.querySelectorAll("[data-hub-tab]").forEach((btn) => {
      const group = btn.dataset.hubGroup || hubTabGroup(btn.getAttribute("data-hub-tab"));
      btn.classList.toggle("hidden", group !== hubPrimaryTab);
    });
  }

  function syncHubPrimaryFromTab(tabId) {
    if (tabId === "tools") return;
    const group = hubTabGroup(tabId);
    if (!group || group === hubPrimaryTab) return;
    hubPrimaryTab = group;
    localStorage.setItem(HUB_PRIMARY_KEY, group);
    syncHubPrimaryHighlight(group);
    syncHubTabsVisibility();
  }

  function switchHubPrimaryTab(groupId, opts = {}) {
    if (!HUB_PRIMARY_TABS[groupId]) return;
    hubPrimaryTab = groupId;
    localStorage.setItem(HUB_PRIMARY_KEY, groupId);
    syncHubPrimaryHighlight(groupId);
    syncHubTabsVisibility();
    if (opts.syncOnly) return;
    const inGroup = hubTabsInGroup(groupId).includes(hubTab);
    const nextTab = inGroup && !opts.forceDefault
      ? hubTab
      : HUB_PRIMARY_DEFAULT_TAB[groupId];
    switchHubTab(nextTab, { skipHash: !!opts.skipHash, replaceHash: !!opts.replaceHash });
  }

  function initHubPrimarySubnav() {
    syncHubPrimaryHighlight(hubPrimaryTab);
    syncHubTabsVisibility();
  }

  function syncHubTabHighlight(tabId) {
    $("hubSubnav")?.querySelectorAll("[data-hub-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-hub-tab") === tabId);
    });
  }

  function syncToolsTabHighlight(tabId) {
    $("toolsSubnav")?.querySelectorAll("[data-tools-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tools-tab") === tabId);
    });
  }

  function switchHubTab(tabId, opts = {}) {
    const legacy = resolveLegacyHubRoute(tabId, opts.sub);
    if (legacy) return switchHubTab(legacy.tab, { ...opts, sub: legacy.sub ?? opts.sub });
    if (tabId === "traffic") tabId = "map-internet";
    if (tabId === "tools") {
      showTabLoading(true);
      const sub = opts.sub || (NETWORK_TOOLS_TABS[toolsTab] ? toolsTab : "auto-guide");
      const validSub = NETWORK_TOOLS_TABS[sub] ? sub : "auto-guide";
      switchToolsTab(validSub, { skipHash: true, fromHash: !!opts.fromHash });
      const done = () => { showTabLoading(false); };
      if (!opts.skipHash) syncRouteHash("tools", validSub, !!opts.replaceHash);
      syncPageIntro();
      return Promise.resolve().finally(done);
    }
    const cfg = HUB_TABS[tabId];
    if (!cfg) return Promise.resolve();
    if (cfg.shellScope) {
      hubTab = tabId;
      localStorage.setItem(HUB_TAB_KEY, hubTab);
      syncHubPrimaryFromTab(tabId);
      syncHubTabHighlight(tabId);
      const scope = cfg.shellScope;
      diagnosticsPane = "shell";
      localStorage.setItem(DIAG_PANE_KEY, "shell");
      const sessFromRoute = opts.sub && !opts.sub.includes("/") ? opts.sub : null;
      const sid = sessFromRoute || termPreferredSessionId(scope);
      if (sid) pendingTermSessionId = sid;
      showTabLoading(true);
      switchView("lab", { force: true, fromHash: !!opts.fromHash });
      switchDiagnosticsPane("shell", { skipHash: true, shellScope: scope });
      if (!opts.skipHash) {
        syncRouteHash(
          hubPrimaryTab,
          tabId,
          !!opts.replaceHash,
          sid || null,
        );
      }
      syncPageIntro();
      const done = () => { showTabLoading(false); syncHubShellTabHashes(); };
      return Promise.resolve(loadAuditDiagnostics()).finally(done);
    }
    hubTab = tabId;
    localStorage.setItem(HUB_TAB_KEY, hubTab);
    syncHubPrimaryFromTab(tabId);
    if (cfg.page && PAGE_TAB_VIEWS[cfg.view]) {
      localStorage.setItem(PAGE_TAB_VIEWS[cfg.view].key, cfg.page);
    }
    syncHubTabHighlight(tabId);
    if (tabId === "wifi") {
      const route = parseRouteHash();
      let sub = opts.fromHash
        ? (route.sub && (WIFI_HUB_TABS[route.sub] || WIFI_LEGACY_SUB[route.sub]) ? (WIFI_HUB_TABS[route.sub] ? route.sub : WIFI_LEGACY_SUB[route.sub]) : "profiles")
        : wifiHubTab;
      switchWifiHubTab(WIFI_HUB_TABS[sub] ? sub : (WIFI_LEGACY_SUB[sub] || "profiles"), { skipHash: true });
    }
    if (tabId === "doctors") {
      const route = parseRouteHash();
      if (route.sub === "nordvpn") {
        navigateRoute("dashboard", "nord-doctor", { force: true });
        return Promise.resolve();
      }
      let sub = opts.fromHash
        ? (route.sub === "health" ? "overview" : (route.sub && DOCTORS_HUB_TABS[route.sub] ? route.sub : "overview"))
        : doctorsHubTab;
      switchDoctorsHubTab(DOCTORS_HUB_TABS[sub] ? sub : "overview", { skipHash: true });
    }
    if (tabId === "map-internet" || tabId === "map-local" || tabId === "traffic-live" || tabId === "traffic-speed" || tabId === "spectrum-analyzer" || tabId === "bluetooth-spectrum") {
      const panel = tabId === "map-internet" ? "traffic-internet"
        : tabId === "map-local" ? "traffic-local"
          : tabId === "traffic-speed" ? "traffic-speed"
            : tabId === "spectrum-analyzer" ? "spectrum-analyzer"
            : tabId === "bluetooth-spectrum" ? "bluetooth-spectrum"
              : "traffic-live";
      localStorage.setItem("nordctl_adv_tab", panel);
      switchPageTabs("advanced", panel, { skipHash: true });
      if (tabId === "traffic-live") {
        loadBandwidthQuiet();
        startSecurityBw();
      } else {
        stopSecurityBw();
      }
      if (tabId === "traffic-speed") {
        syncSpeedLabContext();
        renderSpeedLabAll();
      }
      if (tabId === "spectrum-analyzer") {
        loadSpectrum(true);
        startSpectrumLive();
      } else {
        stopSpectrumLive();
      }
      if (tabId === "bluetooth-spectrum") {
        renderBtSpectrumBandSwitches(BT_SPECTRUM_DEFAULT_BANDS);
        loadBluetooth(true, { rescan: false });
        startBtSpectrumLive();
      } else {
        stopBtSpectrumLive();
      }
    }
    if (tabId === "network") {
      const route = parseRouteHash();
      const sub = opts.fromHash
        ? (route.sub && NETWORK_HUB_TABS[route.sub] ? route.sub : "dns")
        : networkHubTab;
      switchNetworkHubTab(NETWORK_HUB_TABS[sub] ? sub : "dns", { skipHash: true });
    }
    if (tabId === "audit") {
      const route = parseRouteHash();
      let pane = "full";
      if (opts.fromHash && route.tab === "audit" && route.sub) {
        pane = auditPaneFromSub(route.sub);
      }
      switchAuditPane(pane, { skipHash: true, fromHash: !!opts.fromHash, stayOnAuditTab: true });
    }
    if (tabId === "leak-tests") {
      switchPageTabs("lab", "leak", { skipHash: true });
      syncLeakLabPane("leak");
    }
    if (tabId === "network-packages" || tabId === "security-packages" || tabId === "listeners" || tabId === "privileges") {
      switchPageTabs("advanced", HUB_TABS[tabId].page, { skipHash: true });
    }
    if (tabId === "diagnostics") {
      const route = parseRouteHash();
      let pane = diagnosticsPane;
      if (opts.fromHash && route.sub) pane = diagnosticsPaneFromSub(route.sub);
      switchDiagnosticsPane(pane, { skipHash: true, fromHash: !!opts.fromHash });
    }
    showTabLoading(true);
    switchView(cfg.view, { force: true, fromHash: !!opts.fromHash });
    if (cfg.page && tabId !== "network" && tabId !== "doctors" && tabId !== "diagnostics"
        && tabId !== "map-internet" && tabId !== "map-local" && tabId !== "traffic-live"
        && tabId !== "traffic-speed" && tabId !== "spectrum-analyzer" && tabId !== "bluetooth-spectrum") {
      switchPageTabs(cfg.view, cfg.page, { skipHash: true });
    }
    const done = () => { showTabLoading(false); };
    const loads = [];
    if (cfg.view === "control") loads.push(loadFirewall());
    if (cfg.view === "advanced") loads.push(loadAdvanced());
    if (cfg.view === "lab") {
      if (tabId === "leak-tests") loads.push(loadLab());
      else if (tabId === "audit") loads.push(loadOverallAudit());
      else if (tabId === "diagnostics" || cfg.page === "audit") loads.push(loadAuditDiagnostics());
    }
    if (cfg.view === "doctors") loads.push(loadDoctorsHub());
    if (cfg.view === "security") loads.push(loadSecurity());
    if (cfg.view === "wifi") loads.push(loadWifiHub());
    const loadDone = Promise.all(loads.map((p) => Promise.resolve(p).catch(() => {}))).finally(done);
    if (!opts.skipHash) syncRouteHash(hubPrimaryTab, tabId, !!opts.replaceHash, hubRouteSub(tabId));
    syncPageIntro();
    return loadDone;
  }

  function switchToolsTab(tabId, opts = {}) {
    const cfg = NETWORK_TOOLS_TABS[tabId] || NETWORK_TOOLS_TABS.logs;
    const id = NETWORK_TOOLS_TABS[tabId] ? tabId : "auto-guide";
    toolsTab = id;
    localStorage.setItem(TOOLS_TAB_KEY, toolsTab);
    syncToolsTabHighlight(id);
    showTabLoading(true);
    if (id === "terminal") {
      navigateRoute("dashboard", "terminal", { sub: opts.sub, skipHash: opts.skipHash, replaceHash: opts.replaceHash });
      return Promise.resolve();
    }
    if (id === "custom-shell") {
      if (opts.toolsSub || opts.sub) {
        customShellCategory = opts.toolsSub || opts.sub;
        localStorage.setItem("nordctl_custom_shell_cat", customShellCategory);
      }
      switchView("customShell", { force: true, fromHash: !!opts.fromHash });
      const done = () => { showTabLoading(false); };
      const loadDone = loadCustomShell().finally(done);
      if (!opts.skipHash) syncRouteHash("tools", id, !!opts.replaceHash, customShellCategory);
      syncPageIntro();
      return loadDone;
    }
    if (id === "custom-packages") {
      if (opts.toolsSub || opts.sub) {
        customPackagesCategory = opts.toolsSub || opts.sub;
        localStorage.setItem("nordctl_custom_packages_cat", customPackagesCategory);
      }
      switchView("customPackages", { force: true, fromHash: !!opts.fromHash });
      const done = () => { showTabLoading(false); };
      const loadDone = loadCustomPackages(!!opts.force).finally(done);
      if (!opts.skipHash) syncRouteHash("tools", id, !!opts.replaceHash, customPackagesCategory);
      syncPageIntro();
      return loadDone;
    }
    if (id === "pc-info") {
      switchView("pcInfo", { force: true, fromHash: !!opts.fromHash });
      const done = () => { showTabLoading(false); };
      const loadDone = loadPcInfo(!!opts.force).finally(done);
      if (!opts.skipHash) syncRouteHash("tools", id, !!opts.replaceHash);
      syncPageIntro();
      return loadDone;
    }
    if (cfg.page) localStorage.setItem("nordctl_auto_tab", cfg.page);
    switchView(cfg.view, { force: true, fromHash: !!opts.fromHash });
    if (cfg.page) switchPageTabs(cfg.view, cfg.page, { skipHash: true });
    const done = () => { showTabLoading(false); };
    const loads = [];
    if (cfg.view === "automate") loads.push(loadAutomate());
    if (cfg.view === "logs") loads.push(loadLogs());
    const loadDone = Promise.all(loads.map((p) => Promise.resolve(p).catch(() => {}))).finally(done);
    if (!opts.skipHash) {
      syncRouteHash("tools", id, !!opts.replaceHash);
    }
    syncPageIntro();
    return loadDone;
  }

  function visibleSettingsScopes(profile) {
    return ["general", "locations", "wifi", "vpn", "alerts"];
  }

  function syncSettingsFromHash() {
    const route = parseRouteHash();
    if (route.section !== "settings") return null;
    const { scope, tab } = resolveSettingsRoute(route);
    settingsScope = scope;
    settingsTab = tab;
    localStorage.setItem(SETTINGS_SCOPE_KEY, scope);
    localStorage.setItem(SETTINGS_TAB_KEY, tab);
    return { scope, tab };
  }

  function settingsTabsForScope(scope, profile) {
    const mapped = LEGACY_SETTINGS_SCOPE[scope] || scope;
    return [...(SETTINGS_TABS_BY_SCOPE[mapped] || SETTINGS_TABS_BY_SCOPE.general)];
  }

  function legacySettingsScope(tabId, profile) {
    if (!tabId || tabId === "language") return null;
    if (LEGACY_SETTINGS_SCOPE[tabId]) return LEGACY_SETTINGS_SCOPE[tabId];
    for (const [scope, tabs] of Object.entries(SETTINGS_TABS_BY_SCOPE)) {
      if (tabs.includes(tabId)) return scope;
    }
    return null;
  }

  function defaultSettingsTab(scope, profile) {
    return settingsTabsForScope(scope, profile)[0] || "password";
  }

  function defaultSettingsRoute(data) {
    return { scope: "general", tab: "password" };
  }

  function isSettingsScope(id) {
    if (!id) return false;
    const mapped = LEGACY_SETTINGS_SCOPE[id] || id;
    return !!SETTINGS_TABS_BY_SCOPE[mapped];
  }

  function parseSettingsRouteParts(parts) {
    if (!parts.length) return { section: "settings", tab: null, sub: null };
    if (parts[0] === "nord" || parts[0] === "network") {
      return { section: "settings", tab: parts[1] || null, sub: parts[0] };
    }
    if (parts[0] === "language") return { section: "settings", tab: null, sub: null };
    const maybeScope = LEGACY_SETTINGS_SCOPE[parts[0]] || parts[0];
    if (SETTINGS_TABS_BY_SCOPE[maybeScope]) {
      return { section: "settings", tab: parts[1] || null, sub: maybeScope };
    }
    return { section: "settings", tab: parts[0] || null, sub: parts[1] || null };
  }

  function resolveSettingsRoute(route, profile) {
    profile = profile || installProfile(lastState);
    let scope = route.sub;
    let tab = route.tab;
    if (scope && LEGACY_SETTINGS_SCOPE[scope]) scope = LEGACY_SETTINGS_SCOPE[scope];
    if (scope && SETTINGS_TABS_BY_SCOPE[scope]) {
      const tabs = settingsTabsForScope(scope, profile);
      if (!tab || !tabs.includes(tab)) tab = defaultSettingsTab(scope, profile);
      return { scope, tab };
    }
    if (tab) {
      scope = legacySettingsScope(tab, profile);
      if (!scope) return defaultSettingsRoute(lastState);
      const tabs = settingsTabsForScope(scope, profile);
      if (!tabs.includes(tab)) tab = defaultSettingsTab(scope, profile);
      return { scope, tab };
    }
    return defaultSettingsRoute(lastState);
  }

  function settingsRouteKey(scope, tab) {
    return `settings/${scope}/${tab}`;
  }

  function renderSettingsTabNav(_scope, profile) {
    const tabNav = $("settingsSubnav");
    if (!tabNav) return;
    tabNav.innerHTML = "";
    let lastScope = null;
    visibleSettingsScopes(profile).forEach((scopeId) => {
      const scopeTabs = settingsTabsForScope(scopeId, profile);
      scopeTabs.forEach((id) => {
        if (lastScope && lastScope !== scopeId) {
          const sep = document.createElement("span");
          sep.className = "settings-nav-group-sep";
          sep.setAttribute("aria-hidden", "true");
          tabNav.appendChild(sep);
        }
        lastScope = scopeId;
        const cfg = SETTINGS_TAB_META[id];
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "hub-subnav-btn settings-tab-btn";
        btn.setAttribute("data-settings-tab", id);
        btn.setAttribute("data-settings-scope", scopeId);
        btn.dataset.tabHash = `settings/${scopeId}/${id}`;
        btn.title = cfg?.title || cfg?.label || id;
        btn.textContent = cfg?.label || id;
        btn.classList.toggle("active", id === settingsTab);
        btn.addEventListener("click", () => switchSettingsView(scopeId, id));
        tabNav.appendChild(btn);
      });
    });
  }

  function updateSettingsChrome(scope, profile) {
    profile = profile || installProfile(lastState);
    const meta = SETTINGS_SCOPE_META[scope] || SETTINGS_SCOPE_META.general;
    if ($("settingsTitle")) $("settingsTitle").textContent = meta.title;
    if ($("settingsIntro")) $("settingsIntro").textContent = meta.intro;
    $("settingsScopeNav")?.classList.add("hidden");
    $("settingsNavDivider")?.classList.add("hidden");
    $("settingsSubnav")?.classList.remove("settings-subnav-single");
    const btn = $("btnSettings");
    if (btn) btn.title = "Settings";
  }

  function applySettingsNav(profile) {
    profile = profile || installProfile(lastState);
    if (parseRouteHash().section === "settings") syncSettingsFromHash();
    const scopes = visibleSettingsScopes(profile);
    if (!scopes.includes(settingsScope)) {
      settingsScope = scopes[0];
      localStorage.setItem(SETTINGS_SCOPE_KEY, settingsScope);
    }
    const tabs = settingsTabsForScope(settingsScope, profile);
    if (!tabs.includes(settingsTab)) {
      settingsTab = defaultSettingsTab(settingsScope, profile);
      localStorage.setItem(SETTINGS_TAB_KEY, settingsTab);
    }
    initSettingsSubnav(true);
    updateSettingsChrome(settingsScope, profile);
    switchSettingsTab(settingsScope, settingsTab, { skipHash: true });
  }

  function switchSettingsView(scopeOrTab, tabId, opts = {}) {
    const profile = installProfile(lastState);
    let scope;
    let tab;
    if (tabId !== undefined) {
      if (isSettingsScope(scopeOrTab) || scopeOrTab === "nord" || scopeOrTab === "network") {
        scope = LEGACY_SETTINGS_SCOPE[scopeOrTab] || scopeOrTab;
        tab = tabId;
      } else {
        tab = tabId;
        scope = legacySettingsScope(tabId, profile) || settingsScope || "general";
      }
    } else {
      tab = scopeOrTab;
      scope = legacySettingsScope(tab, profile) || settingsScope || "general";
    }
    ({ scope, tab } = resolveSettingsRoute({ section: "settings", tab, sub: scope }, profile));
    settingsScope = scope;
    settingsTab = tab;
    localStorage.setItem(SETTINGS_SCOPE_KEY, scope);
    localStorage.setItem(SETTINGS_TAB_KEY, tab);
    renderSettingsTabNav(scope, profile);
    switchSettingsTab(scope, tab, { skipHash: true });
    showTabLoading(true);
    switchView("settings", { force: true, fromHash: !!opts.fromHash, skipSettingsLoad: true });
    Promise.resolve(loadSettingsPanel()).finally(() => showTabLoading(false));
    if (!opts.skipHash) syncRouteHash("settings", scope, !!opts.replaceHash, tab);
    syncPageIntro();
  }

  function switchSettingsTab(scope, tabId, opts = {}) {
    const profile = installProfile(lastState);
    const tabs = settingsTabsForScope(scope, profile);
    let id = tabs.includes(tabId) ? tabId : defaultSettingsTab(scope, profile);
    if (!document.querySelector(`[data-settings-panel="${id}"]`)) {
      const fallback = tabs.find((t) => document.querySelector(`[data-settings-panel="${t}"]`));
      if (fallback) id = fallback;
    }
    settingsScope = scope;
    settingsTab = id;
    localStorage.setItem(SETTINGS_SCOPE_KEY, scope);
    localStorage.setItem(SETTINGS_TAB_KEY, id);
    $("settingsSubnav")?.querySelectorAll("[data-settings-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-settings-tab") === id);
    });
    document.querySelectorAll("[data-settings-panel]").forEach((p) => {
      const panelId = p.getAttribute("data-settings-panel");
      p.classList.toggle("active", panelId === id);
    });
    updateSettingsChrome(scope, profile);
    if (!opts.skipHash && getActiveView() === "settings") {
      syncRouteHash("settings", scope, false, id);
    }
    syncPageIntro();
  }

  function initSettingsSubnav(force) {
    const profile = installProfile(lastState);
    const tabNav = $("settingsSubnav");
    if (!tabNav) return;
    if (!tabNav.dataset.rendered || force) {
      tabNav.dataset.rendered = "1";
      renderSettingsTabNav(settingsScope, profile);
    }
  }

  function switchPageTabs(viewName, tabId, opts = {}) {
    const cfg = PAGE_TAB_VIEWS[viewName];
    if (!cfg) return;
    const scope = document.querySelector(cfg.scope);
    if (!scope) return;
    let active = tabId || localStorage.getItem(cfg.key) || cfg.default;
    if (viewName === "dashboard" && active && !DASHBOARD_TABS[active]) active = cfg.default;
    if (!scope.querySelector(`[data-page-tab-panel="${dashboardPanelTab(active)}"]`)) active = cfg.default;
    localStorage.setItem(cfg.key, active);
    if (viewName === "dashboard") dashTab = active;
    if (viewName === "wifi") wifiTab = active;
    if (viewName === "dashboard") syncDashTabHighlight(active);
    else if (cfg.nav) {
      const nav = $(cfg.nav);
      nav?.querySelectorAll(".page-tab-btn").forEach((b) => {
        b.classList.toggle("active", b.dataset.pageTab === active);
      });
    }
    const panelTab = viewName === "dashboard" ? dashboardPanelTab(active) : active;
    scope.querySelectorAll("[data-page-tab-panel]").forEach((p) => {
      p.classList.toggle("active", p.dataset.pageTabPanel === panelTab);
    });
    if (viewName === "advanced") {
      if (active === "network-packages" || active === "security-packages") {
        void loadHubTools(active === "security-packages" ? "security" : "network", false);
      } else if (active === "listeners") {
        void loadListeners(false);
      }
    }
    if (viewName === "dashboard" && active === "workflows") {
      refreshLocationCountrySelects();
      if (lastState) renderWorkflowPresets(lastState);
    }
    if (viewName === "dashboard" && active === "wizard") {
      loadWizard(false).then((w) => {
        renderSetupWizardChecklist(w);
        updateWizardGateButtons();
        if (wizardUiMode === "hidden") showWizardPanel(true);
      }).catch(() => {});
      api("/api/doctor").then(renderDoctor).catch(() => {});
    }
    if (viewName === "dashboard" && active === "terminal") {
      termMountPanel("dashboard");
      loadTerminal();
    }
    if (viewName === "dashboard" && !opts.skipHash) {
      syncRouteHash("dashboard", active, !!opts.replaceHash, null);
    }
  }

  function openDashboardNordShell(opts = {}) {
    if (opts.sub) pendingTermSessionId = opts.sub;
    dashTab = "terminal";
    localStorage.setItem(DASH_TAB_KEY, dashTab);
    switchView("dashboard", { force: true, fromHash: !!opts.fromHash });
    switchPageTabs("dashboard", "terminal", { skipHash: true });
    termMountPanel("dashboard");
    return Promise.resolve(loadTerminal()).finally(() => syncDashTabHighlight("terminal"));
  }

  function initDashboardTabNav() {
    const nav = $("dashSubnav");
    nav?.querySelector('[data-page-tab="home-lan"]')?.remove();
    nav?.querySelector('[data-page-tab="setup"]')?.remove();
    invalidateTabNavIfRev(nav, DASH_SUBNAV_REV_KEY, DASH_SUBNAV_REV, "data-page-tab");
    renderFlatTabNav(nav, DASHBOARD_TABS, "data-page-tab", "dashboard");
    if (nav && !nav.dataset.dashNavBound) {
      nav.dataset.dashNavBound = "1";
      nav.addEventListener("click", (e) => {
        const btn = e.target.closest("[data-page-tab]");
        if (!btn || !nav.contains(btn)) return;
        const tab = btn.getAttribute("data-page-tab");
        if (tab) navigateRoute("dashboard", tab);
      });
    }
    syncDashTabHighlight(dashTab);
  }

  function initHubToolsTabNavs() {
    initDashboardTabNav();
    initHubPrimarySubnav();
    initWifiHubSubnav();
    initDoctorsHubSubnav();
    initNetworkHubSubnav();
    initTrafficHubSubnav();
    initDiagnosticsSubnav();
    initAuditSubnav();
    $("hubSubnav")?.querySelector('[data-hub-tab="nord-cli"]')?.remove();
    $("hubSubnav")?.querySelector('[data-hub-tab="tools"]')?.remove();
    $("hubSubnav")?.querySelector('[data-hub-tab="diagnostics"]')?.remove();
    const hubNav = $("hubSubnav");
    invalidateTabNavIfRev(hubNav, HUB_SUBNAV_REV_KEY, HUB_SUBNAV_REV, "data-hub-tab");
    renderFlatTabNav(hubNav, HUB_TABS, "data-hub-tab", "network");
    hubNav?.querySelector('[data-hub-tab="diagnostics"]')?.remove();
    invalidateTabNavIfRev($("toolsSubnav"), TOOLS_SUBNAV_REV_KEY, TOOLS_SUBNAV_REV, "data-tools-tab");
    renderFlatTabNav($("toolsSubnav"), NETWORK_TOOLS_TABS, "data-tools-tab", "tools");
    document.querySelectorAll("[data-hub-tab]").forEach((btn) => {
      if (btn.dataset.hubBound) return;
      btn.dataset.hubBound = "1";
      btn.addEventListener("click", () => switchHubTab(btn.getAttribute("data-hub-tab")));
    });
    document.querySelectorAll("[data-tools-tab]").forEach((btn) => {
      if (btn.dataset.toolsBound) return;
      btn.dataset.toolsBound = "1";
      btn.addEventListener("click", () => {
        const tabId = btn.getAttribute("data-tools-tab") || "logs";
        switchToolsTab(tabId);
      });
    });
    syncHubPrimaryHighlight(hubPrimaryTab);
    syncHubTabsVisibility();
    syncHubTabHighlight(hubTab);
    syncToolsTabHighlight(toolsTab);
  }

  const LAB_PAGE_HUB_TAB = {
    leak: "leak-tests",
    overall: "audit",
    audit: "diagnostics",
  };

  function hubTabIdForView(viewName) {
    if (viewName === "wifi") return "wifi";
    if (viewName === "doctors") return "doctors";
    if (TOOLS_VIEWS.has(viewName)) return "tools";
    const route = parseRouteHash();
    if (route.section === "network" && route.tab && HUB_TABS[route.tab]?.view === viewName) {
      return route.tab;
    }
    if (hubTab && HUB_TABS[hubTab]?.view === viewName) return hubTab;
    if (viewName === "lab") {
      if (hubTab === "diagnostics" || hubTab === "networking-shell" || hubTab === "security-shell") {
        return hubTab;
      }
      const page = localStorage.getItem(DIAGNOSTICS_TAB_KEY) || PAGE_TAB_VIEWS.lab.default;
      return LAB_PAGE_HUB_TAB[page] || "audit";
    }
    const pageCfg = PAGE_TAB_VIEWS[viewName];
    const page = pageCfg ? (localStorage.getItem(pageCfg.key) || pageCfg.default) : null;
    for (const [id, cfg] of Object.entries(HUB_TABS)) {
      if (cfg.view === viewName && cfg.page === page) return id;
    }
    if (viewName === "control") return "host-ufw";
    const hit = Object.entries(HUB_TABS).find(([, cfg]) => cfg.view === viewName);
    return hit ? hit[0] : hubTab;
  }

  function toolsTabIdForView(viewName) {
    if (viewName === "terminal") return "terminal";
    if (viewName === "logs") return "logs";
    if (viewName === "editor") return "editor";
    if (viewName === "pcInfo") return "pc-info";
    if (viewName === "automate") {
      const page = localStorage.getItem("nordctl_auto_tab") || "guide";
      const map = {
        guide: "auto-guide", watcher: "auto-watcher", schedules: "schedules",
        rollback: "rollback", reset: "reset", snapshots: "snapshots",
      };
      return map[page] || "auto-guide";
    }
    return toolsTab;
  }

  function switchDashTab(tabId) { switchPageTabs("dashboard", tabId); }
  function switchWifiTab(tabId) { switchPageTabs("wifi", tabId); }

  function filterPresetsList(presets, opts = {}) {
    let list = (presets || []).filter((p) => !p.hidden);
    if (opts.onlyUser) list = list.filter((p) => p.user);
    if (opts.onlyCategories?.length) {
      const only = new Set(opts.onlyCategories);
      list = list.filter((p) => only.has(presetCategory(p)));
    }
    if (opts.excludeCategories?.length) {
      const ex = new Set(opts.excludeCategories);
      list = list.filter((p) => !ex.has(presetCategory(p)));
    }
    return list;
  }

  function filterHiddenPresetsList(hiddenPresets, opts = {}) {
    let list = hiddenPresets || [];
    if (opts.onlyUser) list = list.filter((p) => p.user);
    if (opts.onlyCategories?.length) {
      const only = new Set(opts.onlyCategories);
      list = list.filter((p) => only.has(presetCategory(p)));
    }
    if (opts.excludeCategories?.length) {
      const ex = new Set(opts.excludeCategories);
      list = list.filter((p) => !ex.has(presetCategory(p)));
    }
    return list;
  }

  function presetCategory(p) {
    return p.category || "General";
  }

  function orderedPresetCategories(presets) {
    const seen = new Set();
    const out = [];
    PRESET_CATEGORY_ORDER.forEach((c) => {
      if (presets.some((p) => presetCategory(p) === c)) {
        seen.add(c);
        out.push(c);
      }
    });
    presets.forEach((p) => {
      const c = presetCategory(p);
      if (!seen.has(c)) {
        seen.add(c);
        out.push(c);
      }
    });
    return out;
  }

  function resolvePageTabForView(viewName) {
    const cfg = PAGE_TAB_VIEWS[viewName];
    if (!cfg) return undefined;
    const route = parseRouteHash();
    if (viewName === "dashboard") {
      if (route.section === "dashboard" && route.tab && DASHBOARD_TABS[route.tab]) return route.tab;
      return undefined;
    }
    if (viewName === "lab") {
      if (hubTab === "diagnostics") return "audit";
      if (route.section === "network" && route.tab === "diagnostics") return "audit";
    }
    if (viewName === "wifi" && route.section === "network" && route.tab === "wifi") {
      return route.sub && WIFI_HUB_TABS[route.sub] ? route.sub : cfg.default;
    }
    if (viewName === "doctors" && route.section === "network" && route.tab === "doctors") {
      const sub = route.sub === "health" ? "overview" : route.sub;
      return sub && DOCTORS_HUB_TABS[sub] ? sub : cfg.default;
    }
    if (viewName === "security" && route.section === "network" && route.tab === "network") {
      return networkHubPanelId(route.sub);
    }
    if (route.section === "network" && route.tab === "tools" && route.sub) {
      const t = NETWORK_TOOLS_TABS[route.sub];
      if (t?.view === viewName && t.page) return t.page;
    }
    if (route.section === "network" && route.tab) {
      const hub = HUB_TABS[route.tab];
      if (hub?.view === viewName && hub.page) return hub.page;
    }
    if (route.section === "tools" && route.tab) {
      const t = NETWORK_TOOLS_TABS[route.tab];
      if (t?.view === viewName && t.page) return t.page;
    }
    return undefined;
  }

  function updateSubnav(name) {
    const termSection = name === "terminal" ? termRouteSection() : null;
    const termFromTools = termSection === "tools";
    const toolsHub = isToolsHubActive(name) || termFromTools;
    const networkHub = (HUB_VIEWS.has(name) || (name === "terminal" && termSection === "network")) && !termFromTools;
    const onDashboard = name === "dashboard";
    $("dashSubnav")?.classList.toggle("hidden", !onDashboard);
    $("hubNavWrap")?.classList.toggle("hidden", !networkHub || onDashboard);
    $("hubSubnav")?.classList.toggle("hidden", !networkHub || onDashboard);
    $("toolsSubnav")?.classList.toggle("hidden", !toolsHub || onDashboard);
    syncSettingsNavActive(name === "settings");
    if (PAGE_TAB_VIEWS[name]) {
      switchPageTabs(name, resolvePageTabForView(name), { skipHash: true });
    }
    if (name === "dashboard") syncDashTabHighlight(dashTab);
    if (networkHub) {
      syncHubPrimaryFromTab(hubTabIdForView(name));
      syncHubTabsVisibility();
      syncHubPrimaryHighlight(hubPrimaryTab);
      syncHubTabHighlight(hubTabIdForView(name));
    }
    if (toolsHub) syncToolsTabHighlight(termFromTools ? "terminal" : toolsTabIdForView(name));
    syncSecuritySubnavs();
    syncTrafficSubnavs();
    syncAuditSubnav();
    syncDiagnosticsSubnav();
    if (name === "lab" && (hubTab === "diagnostics" || hubTab === "networking-shell" || hubTab === "security-shell")) syncDiagnosticsHubPane();
  }

  function syncTopNavForView(name) {
    document.querySelectorAll(".nav-pill").forEach((p) => p.classList.remove("active"));
    if (name === "dashboard") {
      document.querySelector('.nav-pill[data-view="dashboard"]')?.classList.add("active");
    } else if (HUB_VIEWS.has(name)) {
      if (name === "terminal" && termRouteSection() === "dashboard") {
        document.querySelector('.nav-pill[data-view="dashboard"]')?.classList.add("active");
      } else {
        document.querySelector(`.nav-pill[data-hub-primary="${hubPrimaryTab}"]`)?.classList.add("active");
      }
    } else if (isToolsHubActive(name) || (name === "terminal" && termRouteSection() === "tools")) {
      document.querySelector('.nav-pill[data-view="tools"]')?.classList.add("active");
    } else if (name === "settings") {
      syncSettingsNavActive(true);
    } else {
      document.querySelector(`.nav-pill[data-view="${name}"]`)?.classList.add("active");
    }
  }

  function switchView(name, opts = {}) {
    name = resolveViewName(name);
    if (name === getActiveView() && !opts.force) {
      if (!opts.fromHash) syncViewHash(name, !!opts.replaceHash);
      syncTopNavForView(name);
      updateSubnav(name);
      return;
    }
    document.querySelectorAll(".view").forEach((v) => v.classList.remove("active"));
    document.querySelectorAll(".nav-pill").forEach((p) => p.classList.remove("active"));
    const elId = "view" + name.charAt(0).toUpperCase() + name.slice(1);
    $(elId)?.classList.add("active");
    syncTopNavForView(name);
    updateSubnav(name);
    editor.active = name === "editor";
    if (name === "editor") initEditorView();
    if (name === "lab") {
      if (hubTab === "leak-tests") {
        syncLeakLabPane("leak");
        loadLab();
      } else if (hubTab === "audit") {
        if (auditPane === "leak") {
          syncLeakLabPane("leak");
          loadLab();
        } else {
          syncLeakLabPane("full");
          loadOverallAudit();
        }
      } else if (hubTab === "diagnostics" || hubTab === "networking-shell" || hubTab === "security-shell") loadAuditDiagnostics();
    }
    if (name === "doctors") loadDoctorsHub();
    if (name === "wifi") loadWifiHub();
    if (name === "security") loadSecurity();
    if (name === "dashboard") {
      loadNordRoutingPanel();
      const dashPage = localStorage.getItem(DASH_TAB_KEY) || defaultDashboardTab();
      if (dashPage === "connection-details") loadConnectionDetails();
    }
    if (name === "control") loadFirewall();
    if (name === "automate") loadAutomate();
    if (name === "advanced") loadAdvanced();
    if (name === "logs") { loadLogs(); startLogsLive(); }
    if (name === "customShell") loadCustomShell();
    if (name === "customPackages") loadCustomPackages();
    if (name === "pcInfo") loadPcInfo();
    if (name === "settings" && !opts.skipSettingsLoad) loadSettingsPanel();
    if (name === "terminal") loadTerminal();
    if (name === "help") loadHelpFull();
    if (name !== "advanced") stopTrafficLive();
    if (name !== "advanced" || trafficHubTab !== "live") stopSecurityBw();
    if (name !== "wifi") stopWifiLive();
    if (name !== "logs") stopLogsLive();
    if (termUiActive()) termEnsureActiveLongPoll();
    else termPauseActiveLongPoll();
  }

  function initPagePremiumChrome() {
    const skip = new Set([
      "live-bw-page", "sec-hero", "connect-home-card", "workflows-hub", "switches-hub",
      "preset-builder-hub", "connection-details-hub", "meshnet-hub", "smart-dns-hub", "wifi-hero",
      "doctor-report-panel", "ufw-panel", "automate-intro", "baseline-panel", "factory-panel",
      "settings-panel", "nord-doctor-hub", "setup-panel", "setup-banner",
    ]);
    document.querySelectorAll("section.panel.glass").forEach((panel) => {
      if ([...panel.classList].some((c) => skip.has(c))) return;
      if (panel.classList.contains("page-premium")) return;
      if (!panel.querySelector(":scope > h2, :scope > .hero-card-head")) return;
      panel.classList.add("page-premium");
    });
    document.querySelectorAll(".traffic-map-panel").forEach((p) => p.classList.add("page-premium", "traffic-premium"));
    document.querySelectorAll(".logs-panel, .service-panel").forEach((p) => p.classList.add("page-premium"));
  }

  function initViewRouting() {
    initHubToolsTabNavs();
    initPagePremiumChrome();
    window.addEventListener("hashchange", () => applyRoute(true));
    const hasHash = !!(location.hash || "").replace(/^#/, "").trim();
    applyRoute(true, !hasHash);
  }

  function stopTrafficLive() {
    if (trafficLiveTimer) {
      clearInterval(trafficLiveTimer);
      trafficLiveTimer = null;
    }
  }

  function startTrafficLive() {
    stopTrafficLive();
    const on = $("trafficLive")?.checked || $("trafficLiveLocal")?.checked;
    if (!on) return;
    trafficLiveTimer = setInterval(() => loadTraffic(true), 5000);
  }

  function statCell(label, value, cls) {
    return `<div class="stat-pair"><div class="lbl">${esc(label)}</div><div class="val ${cls || ""}">${value}</div></div>`;
  }

  function renderDoctor(doctor) {
    if (!doctor) return;
    const panel = $("setupPanel");
    const badge = $("setupBadge");
    const intro = $("setupIntro");
    const why = $("setupWhy");
    const banner = $("setupBanner");
    const ready = !!doctor.ready;
    const blocking = doctor.blocking_count || 0;
    const level = doctor.setup_level || (blocking > 0 ? "required" : "none");
    const dismissed = localStorage.getItem(SETUP_DISMISS_KEY) === "1";
    const optionalCount = (doctor.checks || []).filter(
      (c) => !c.ok && !REQUIRED_SETUP_IDS.has(c.id) && c.severity !== "error"
    ).length;

    $("btnInstallNord")?.classList.toggle("hidden", !!doctor.nord_installed);
    $("btnDismissSetup")?.classList.toggle("hidden", level === "required");

    if (level === "none") {
      panel?.classList.add("hidden");
      banner?.classList.add("hidden");
      return;
    }

    if (level === "optional" && dismissed) {
      panel?.classList.add("hidden");
      banner?.classList.remove("hidden");
      $("setupBannerText").textContent =
        `NordVPN is working. ${optionalCount} optional tip${optionalCount === 1 ? "" : "s"} (WiFi names, country, IPv6, sudo) — not required.`;
      if (badge) {
        badge.textContent = optionalCount ? `${optionalCount} optional` : "Ready";
        badge.className = optionalCount ? "setup-badge warn" : "setup-badge ok";
      }
      return;
    }

    panel?.classList.remove("hidden");
    banner?.classList.add("hidden");
    /* Do not auto-switch tabs or hash — user opens Setup via Nord Dashboard tab or banner. */

    panel?.classList.toggle("setup-ok", ready && level === "optional");
    panel?.classList.toggle("setup-warn", level === "required");

    $("btnSetupSwitchVpn")?.classList.add("hidden");
    if (level === "required") {
      if (badge) {
        badge.textContent = `${blocking} required`;
        badge.className = "setup-badge err";
      }
      if (why) {
        why.textContent =
          "Required setup — NordVPN is missing, not logged in, or the service is down. Fix the items marked ! below before presets will work reliably.";
      }
      intro.textContent = "Install and log in to NordVPN first. Optional WiFi/country tuning can wait.";
    } else {
      if (badge) {
        badge.textContent = optionalCount ? `${optionalCount} optional` : "Ready";
        badge.className = optionalCount ? "setup-badge warn" : "setup-badge ok";
      }
      if (why) {
        why.textContent =
          "NordVPN is already installed and logged in — that is why you might wonder why Setup appears. " +
          "These remaining items are optional tuning (Smart DNS WiFi names, default country, IPv6 hardening). " +
          "Dismiss this panel if basic VPN connect works for you.";
      }
      intro.textContent = optionalCount
        ? "Optional improvements — skip any you do not need."
        : "All systems go — pick a preset or connect.";
    }

    const checks = (doctor.checks || []).filter((c) => {
      if (level === "required") {
        return !c.ok && (REQUIRED_SETUP_IDS.has(c.id) || c.severity === "error");
      }
      return !c.ok && c.severity !== "error";
    });

    const box = $("setupChecks");
    if (!box) return;
    if (!checks.length && level === "optional") {
      box.innerHTML = '<p class="muted">No optional tips — you are good to go.</p>';
    } else {
      box.innerHTML = checks.map((c) => {
        const sev = c.ok ? "ok" : (c.severity === "info" ? "info" : (c.severity || "error"));
        const fixes = (c.fix || []).filter(Boolean).map((f) => `<li>${esc(f)}</li>`).join("");
        const countryPicker = c.id === "connect_country" && !c.ok
          ? `<div class="setup-country-picker field-row">
              <select id="setupCountrySelect" class="full-select" title="Your home country for presets"></select>
              <button type="button" class="btn sm primary" id="btnSetupCountrySave">Save country</button>
            </div>` : "";
        const editBtn = (!c.ok && c.id === "wifi_profiles")
          ? `<button type="button" class="btn sm check-edit" data-edit="config" title="Open Tools → Editor to edit config.yaml">Tools → Editor</button>` : "";
        const ipv6Btn = c.id === "ipv6" && !c.ok
          ? `<button type="button" class="btn sm check-edit" id="btnDisableIpv6Inline" data-confirm="1" title="Needs passwordless sudo or run command in terminal">Disable IPv6</button>` : "";
        return `<div class="check check-${sev}"><div class="check-head"><span class="check-icon">${c.ok ? "✓" : "!"}</span><span>${esc(c.summary)}</span>${editBtn}${ipv6Btn}</div>${fixes ? `<ul class="check-fix">${fixes}</ul>` : ""}${countryPicker}</div>`;
      }).join("");
    }
    setupCountryOptions(lastState?.connect_country || "");
    box.querySelectorAll(".check-edit[data-edit]").forEach((btn) => {
      btn.addEventListener("click", () => openEditor("config"));
    });
    $("btnSetupCountrySave")?.addEventListener("click", saveSetupCountry);
    $("btnDisableIpv6Inline")?.addEventListener("click", () => runDisableIpv6());
    $("btnDisableIpv6")?.classList.toggle("hidden", !checks.some((c) => c.id === "ipv6"));
    loadWizard(false).then((w) => renderSetupWizardChecklist(w)).catch(() => {});
  }

  function doctorCheckStatus(c) {
    if (c.ok) return { label: "OK", cls: "ok" };
    if (c.severity === "error") return { label: "Fix", cls: "bad" };
    return { label: "Tip", cls: "warn" };
  }

  function doctorCheckExplain(c) {
    const fixes = (c.fix || []).filter(Boolean);
    if (fixes.length) return fixes[0];
    return c.ok ? "No action needed." : "Review this item.";
  }

  let cachedDoctorData = null;

  const DOCTOR_GROUP_DOM = {
    wifi: { content: "doctorGroupContentWifi", badge: "doctorBadgeWifi" },
    privacy: { content: "doctorGroupContentPrivacy", badge: "doctorBadgePrivacy" },
    system: { content: "doctorGroupContentSystem", badge: "doctorBadgeSystem" },
  };

  function doctorCheckRowHtml(c) {
    const st = doctorCheckStatus(c);
    const fixes = (c.fix || []).filter(Boolean);
    return `<div class="doctor-check-row ${st.cls}">
      <div class="doctor-check-head">
        <span>${c.ok ? "✓" : "!"}</span>
        <span>${esc(c.summary)}</span>
        <span class="doctor-status">${st.label}</span>
      </div>
      <p class="doctor-check-detail">${esc(doctorCheckExplain(c))}</p>
      ${fixes.length > 1 ? `<ul class="doctor-check-fixes">${fixes.slice(1).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
    </div>`;
  }

  function renderDoctorOverview(doctor) {
    const summary = $("doctorReportSummary");
    const badge = $("doctorReportBadge");
    if (!summary) return;
    const checks = doctor?.checks || [];
    const passed = checks.filter((c) => c.ok).length;
    const tips = checks.filter((c) => !c.ok && c.severity !== "error").length;
    const blocking = doctor?.blocking_count || checks.filter((c) => !c.ok && c.severity === "error").length;
    if (badge) {
      badge.textContent = blocking ? `${blocking} to fix` : tips ? `${tips} tips` : "All OK";
      badge.className = "badge " + (blocking ? "off" : tips ? "warn" : "on");
    }
    summary.innerHTML = [
      "<p><strong>What the doctor did</strong> — read-only checks, nothing was changed:</p>",
      "<ul class=\"doctor-check-fixes\" style=\"margin:0.35rem 0 0 1rem\">",
      "<li>NordVPN CLI install, login, and nordvpnd service</li>",
      "<li>WiFi profile names and default country in config</li>",
      "<li>DNS, IPv6, resolv.conf, and internet connectivity</li>",
      "<li>NetworkManager / systemd-resolved availability</li>",
      "<li>Sudo privileges for fixes the UI can run</li>",
      "</ul>",
      `<div class="doctor-stats">`,
      `<span class="badge on">${passed} passed</span>`,
      tips ? `<span class="badge warn">${tips} optional tips</span>` : "",
      blocking ? `<span class="badge off">${blocking} must fix</span>` : "",
      `<span class="muted">Checked ${checks.length} items — use the tabs above for each area</span>`,
      `</div>`,
      blocking
        ? `<p class="help-text" style="margin-top:0.65rem">Fix items marked <strong>Fix</strong> first — presets may fail until NordVPN is installed, logged in, and running.</p>`
        : tips
          ? `<p class="help-text" style="margin-top:0.65rem">Optional tips improve Smart DNS and privacy — skip any you do not need.</p>`
          : `<p class="help-text" style="margin-top:0.65rem">Everything looks good for NordVPN and network health.</p>`,
    ].join("");
  }

  function renderDoctorGroupTab(tabId, doctor) {
    const dom = DOCTOR_GROUP_DOM[tabId];
    const idx = DOCTOR_TAB_GROUPS[tabId];
    if (!dom || idx === undefined) return;
    const g = DOCTOR_GROUPS[idx];
    const box = $(dom.content);
    const badge = $(dom.badge);
    if (!box || !g) return;
    const checks = doctor?.checks || [];
    const items = checks.filter((c) => g.ids.includes(c.id));
    const blocking = items.filter((c) => !c.ok && c.severity === "error").length;
    const tips = items.filter((c) => !c.ok && c.severity !== "error").length;
    if (badge) {
      badge.textContent = blocking ? `${blocking} to fix` : tips ? `${tips} tips` : items.length ? "All OK" : "—";
      badge.className = "badge " + (blocking ? "off" : tips ? "warn" : items.length ? "on" : "");
    }
    box.innerHTML = items.length
      ? items.map(doctorCheckRowHtml).join("")
      : "<p class=\"muted\">No checks in this group.</p>";
  }

  function renderFullDoctorReport(doctor) {
    cachedDoctorData = doctor;
    renderDoctorOverview(doctor);
    Object.keys(DOCTOR_TAB_GROUPS).forEach((tabId) => renderDoctorGroupTab(tabId, doctor));
    if (getActiveView() === "doctors") {
      const active = DOCTORS_HUB_TABS[doctorsHubTab] ? doctorsHubTab : "overview";
      switchPageTabs("doctors", active, { skipHash: true });
    }
  }

  async function loadDoctorReport(force) {
    const summary = $("doctorReportSummary");
    if (summary) summary.innerHTML = '<p class="muted">Loading health report…</p>';
    Object.values(DOCTOR_GROUP_DOM).forEach((dom) => {
      const box = $(dom.content);
      if (box) box.innerHTML = "";
      const badge = $(dom.badge);
      if (badge) { badge.textContent = "…"; badge.className = "badge"; }
    });
    if ($("doctorReportBadge")) {
      $("doctorReportBadge").textContent = "…";
      $("doctorReportBadge").className = "badge";
    }
    try {
      if (force) invalidateApiCache("/api/doctor");
      const d = await (force ? api("/api/doctor") : apiCached("/api/doctor", {}, CACHE_TTL.state));
      if (lastState) lastState.doctor = d;
      renderFullDoctorReport(d);
      return d;
    } catch (e) {
      if (summary) summary.innerHTML = `<p class="msg err">${esc(formatFetchError(e))}</p>`;
      reportActionError("Doctor report failed", e, "Loading health report");
      return null;
    }
  }

  function doctorReportStatsHtml(doctor) {
    const checks = doctor?.checks || [];
    const passed = checks.filter((c) => c.ok).length;
    const tips = checks.filter((c) => !c.ok && c.severity !== "error").length;
    const blocking = doctor?.blocking_count ?? checks.filter((c) => !c.ok && c.severity === "error").length;
    return [
      `<span class="badge on">${passed} passed</span>`,
      tips ? `<span class="badge warn">${tips} tip${tips === 1 ? "" : "s"}</span>` : "",
      blocking ? `<span class="badge off">${blocking} to fix</span>` : "",
      `<span class="muted">${checks.length} checks total</span>`,
    ].filter(Boolean).join("");
  }

  function renderLabDoctorResults(doctor) {
    const panel = $("labDoctorPanel");
    const box = $("labDoctorResults");
    const badge = $("labDoctorBadge");
    const summary = $("labDoctorSummary");
    if (!panel || !box || !doctor) return;
    const checks = doctor.checks || [];
    const blocking = doctor.blocking_count || 0;
    const tips = doctor.warning_count || checks.filter((c) => !c.ok && c.severity !== "error").length;
    const headline = blocking
      ? `${blocking} item${blocking === 1 ? "" : "s"} need fixing before presets work reliably.`
      : tips
        ? `All required checks passed — ${tips} optional tip${tips === 1 ? "" : "s"} below.`
        : "All checks passed.";
    panel.classList.remove("hidden");
    if (badge) {
      badge.textContent = blocking ? `${blocking} to fix` : tips ? `${tips} tips` : "All OK";
      badge.className = "badge " + (blocking ? "off" : tips ? "warn" : "on");
    }
    if (summary) {
      summary.innerHTML = [
        `<strong>${checks.length} checks completed.</strong> ${esc(headline)}`,
        ` NordVPN, WiFi/DNS, IPv6, connectivity, resolv.conf, and sudo privileges — read-only, nothing changed.`,
        `<span class="doctor-report-stats" style="display:flex;flex-wrap:wrap;gap:0.35rem;margin-top:0.45rem">${doctorReportStatsHtml(doctor)}</span>`,
      ].join("");
    }
    box.innerHTML = [
      checks.map(doctorCheckRowHtml).join("") || `<p class="muted">No checks returned.</p>`,
      `<div class="actions lab-doctor-actions">`,
      `<button type="button" class="btn sm jump-link" data-view-jump="network/doctors/overview">Open full doctor report</button>`,
      `</div>`,
    ].join("");
    bindViewJumps(panel);
  }

  function isLabLeakPageActive() {
    return getActiveView() === "lab" && (localStorage.getItem(DIAGNOSTICS_TAB_KEY) || "leak") === "leak";
  }

  async function runFullDoctor(opts = {}) {
    const panel = $("doctorReportPanel");
    const summary = $("doctorReportSummary");
    const onDoctors = opts.switchToLab || getActiveView() === "doctors";
    const onLabLeak = !onDoctors && isLabLeakPageActive();
    if (opts.switchToLab) navigateRoute("network", "doctors", { force: true, sub: "overview" });
    else if (onDoctors) switchPageTabs("doctors", "overview", { skipHash: true });
    if (onLabLeak) {
      $("labDoctorPanel")?.classList.remove("hidden");
      if ($("labDoctorResults")) $("labDoctorResults").innerHTML = `<p class="muted">Running health checks…</p>`;
      if ($("labDoctorBadge")) { $("labDoctorBadge").textContent = "…"; $("labDoctorBadge").className = "badge"; }
    }
    if (summary && onDoctors) summary.innerHTML = "<p class=\"muted\">Running health checks…</p>";
    if (onDoctors) {
      Object.values(DOCTOR_GROUP_DOM).forEach((dom) => {
        const box = $(dom.content);
        if (box) box.innerHTML = "";
      });
      if ($("doctorReportBadge")) {
        $("doctorReportBadge").textContent = "…";
        $("doctorReportBadge").className = "badge";
      }
    }
    try {
      const d = await api("/api/doctor");
      renderDoctor(d);
      renderFullDoctorReport(d);
      if (onLabLeak) renderLabDoctorResults(d);
      if (onDoctors) panel?.scrollIntoView({ behavior: "smooth", block: "start" });
      else if (onLabLeak) $("labDoctorPanel")?.scrollIntoView({ behavior: "smooth", block: "start" });
      const msg = `${d.checks?.length || 0} checks — ${d.blocking_count || 0} to fix, ${d.warning_count || 0} tips`;
      if (!onLabLeak) toast(msg, d.ok);
      logActivity("Doctor", msg, d.ok);
      return d;
    } catch (e) {
      if (summary && onDoctors) summary.innerHTML = `<p class="msg err">${esc(String(e))}</p>`;
      if (onLabLeak && $("labDoctorResults")) {
        $("labDoctorResults").innerHTML = `<p class="msg err">${esc(formatFetchError(e))}</p>`;
      }
      toast(formatFetchError(e), false);
      return null;
    }
  }

  async function runDisableIpv6() {
    showNotice("Disabling IPv6 system-wide…", { ok: true, title: "IPv6" });
    const res = await doAction({ action: "disable_ipv6" }, "Disable IPv6");
    if (res.ok) {
      showNotice("IPv6 disabled system-wide.", { ok: true, title: "IPv6 disabled" });
      const d = await api("/api/doctor");
      renderDoctor(d);
      return;
    }
    const manual = res.manual || "sudo sysctl -w net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1 net.ipv6.conf.lo.disable_ipv6=1";
    const body = [
      esc(res.error || "The web UI cannot enter your sudo password."),
      "",
      "<strong>What to do:</strong>",
      "1. Open " + viewLink("terminal", "Terminal") + " and paste this command:",
      `<pre class="mono notice-cmd">${esc(manual)}</pre>`,
      "2. Or install passwordless sudo: open " + viewLink("advanced", "Network & Security → Privileges", "privileges")
        + " and run the full privilege script shown there.",
    ].join("<br>");
    showNotice(body, {
      ok: false,
      title: "IPv6 — run in terminal",
      copyText: manual,
      html: true,
    });
  }

  function regionLabel(code) {
    return REGION_LABELS[code] || code;
  }

  function locationFieldSet(fieldId) {
    const f = (lastState?.locations?.fields || []).find((x) => x.id === fieldId);
    return !!f?.set;
  }

  function presetNeedsSetup(p) {
    return (p.requires || []).some((req) => !locationFieldSet(req));
  }

  function countryFromCityValue(cityValue) {
    const val = String(cityValue || "").trim();
    if (!val || !countries.length) return "";
    for (const c of countries) {
      const label = countryLabel(c);
      if (val.startsWith(`${label} `) || val.startsWith(`${c.replace(/_/g, " ")} `)) {
        return c;
      }
    }
    return "";
  }

  function resolveCityRowCountry(cSel, field) {
    const cityFieldId = cSel?.closest(".loc-city-row")?.querySelector(".loc-city")?.dataset.locField
      || field?.id;
    if (cSel?.value) return cSel.value;
    if (cityFieldId && pendingCityCountries[cityFieldId]) return pendingCityCountries[cityFieldId];
    const countryField = cSel?.dataset.countryField || field?.country_field || "connect_country";
    const linked = lastState?.[countryField]
      || (lastState?.locations?.fields || []).find((f) => f.id === countryField)?.value;
    if (linked) return String(linked).replace(/ /g, "_");
    if (field?.value) return countryFromCityValue(field.value);
    return "";
  }

  function applyCountrySelectValue(sel, countryCode) {
    if (!sel || !countryCode) return;
    const norm = String(countryCode).replace(/ /g, "_");
    if ([...sel.options].some((o) => o.value === norm)) {
      sel.value = norm;
      return;
    }
    const match = countries.find((c) => c === norm || countryLabel(c) === norm.replace(/_/g, " "));
    if (match) sel.value = match;
  }

  function placeFieldLabel(fieldId) {
    const f = (lastState?.locations?.fields || []).find((x) => x.id === fieldId);
    return f?.label || fieldId.replace(/_/g, " ");
  }

  function placeFieldSetupDest(fieldId) {
    return fieldId === "lan_allowlist_cidr" ? "Split tunnel" : "My places";
  }

  function scrollToLanRange() {
    const route = parseRouteHash();
    if (route.section !== "dashboard" || route.tab !== "split-tunnel") {
      navigateRoute("dashboard", "split-tunnel", { scrollLan: true });
      let tries = 0;
      const tick = () => {
        if (scrollToLanRangeOnly() || ++tries > 25) return;
        setTimeout(tick, 100);
      };
      setTimeout(tick, 50);
      return;
    }
    if (!scrollToLanRangeOnly()) {
      setTimeout(scrollToLanRangeOnly, 150);
    }
  }

  function syncHomeLanUi(data) {
    const fromField = (data?.locations?.fields || []).find((f) => f.id === "lan_allowlist_cidr");
    const cidr = String(data?.lan_allowlist_cidr || fromField?.value || "").trim();
    const input = $("lanAllowlistCidr");
    if (input && document.activeElement !== input) {
      input.value = cidr;
    }
  }

  function scrollToPlaceField(fieldId) {
    if (fieldId === "lan_allowlist_cidr") {
      scrollToLanRange();
      return;
    }
    const go = () => {
      const card = document.getElementById(`locCard_${CSS.escape(fieldId)}`) || document.getElementById(`locCard_${fieldId}`);
      if (!card) return false;
      card.scrollIntoView({ behavior: "smooth", block: "center" });
      card.classList.add("loc-highlight");
      setTimeout(() => card.classList.remove("loc-highlight"), 2800);
      const input = card.querySelector("input.loc-text, select.loc-country, select.loc-city:not([disabled])");
      input?.focus();
      return true;
    };
    const route = parseRouteHash();
    if (route.section !== "workflows" || route.tab !== "workflows") {
      navigateRoute("dashboard", "workflows", { sub: "places" });
      setTimeout(go, 450);
    } else if (!go()) {
      setTimeout(go, 200);
    }
  }

  function placeValueLabel(field) {
    if (field.type === "country") return "Country";
    if (field.type === "city") return "City";
    if (field.id === "custom_dns") return "DNS servers";
    if (field.id === "lan_allowlist_cidr") return "Subnet";
    if (field.id === "connect_server") return "Server name or ID";
    if (field.id === "mesh_peer") return "Peer hostname";
    return "Value";
  }

  function buildLocationInputHtml(fieldMeta, prefix, currentValue, opts = {}) {
    const id = fieldMeta.id;
    const type = fieldMeta.type || "text";
    const hasValue = !!String(currentValue || "").trim();
    const ph = (opts.omitPlaceholderIfSet && hasValue) ? "" : esc(fieldMeta.placeholder || "");
    if (type === "country") {
      return `<select class="full-select loc-country${hasValue ? " has-value" : ""}" data-loc-field="${esc(id)}" data-loc-prefix="${esc(prefix)}"><option value="">${ph || "Pick country…"}</option></select>`;
    }
    if (type === "city") {
      const countryField = fieldMeta.country_field || "connect_country";
      return `<div class="field-row loc-city-row">
        <select class="full-select loc-city-country" data-loc-prefix="${esc(prefix)}" data-country-field="${esc(countryField)}"><option value="">Country…</option></select>
        <select class="full-select loc-city${hasValue ? " has-value" : ""}" data-loc-field="${esc(id)}" data-loc-prefix="${esc(prefix)}" disabled><option value="">City…</option></select>
      </div>`;
    }
    return `<input type="text" class="full-select loc-text${hasValue ? " has-value" : ""}" data-loc-field="${esc(id)}" data-loc-prefix="${esc(prefix)}" placeholder="${ph}" value="${esc(currentValue || "")}" />`;
  }

  function fillLocationCountrySelects(root) {
    const emptyHint = nordInstalled(lastState)
      ? (countries.length ? null : "Loading countries… refresh or check NordVPN")
      : "Install NordVPN to load country list";

    (root || document).querySelectorAll(".loc-country").forEach((sel) => {
      const prev = sel.value;
      const ph = sel.dataset.placeholder || sel.querySelector("option")?.textContent || "Pick country…";
      sel.innerHTML = `<option value="">${esc(ph)}</option>`;
      if (emptyHint && !countries.length) {
        const o = document.createElement("option");
        o.value = "";
        o.textContent = emptyHint;
        o.disabled = true;
        sel.appendChild(o);
        return;
      }
      countries.forEach((c) => {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = countryLabel(c);
        sel.appendChild(o);
      });
      const fieldId = sel.dataset.locField;
      const cur = (lastState?.locations?.fields || []).find((f) => f.id === fieldId)?.value
        || lastState?.[fieldId]
        || (fieldId === "connect_country" ? lastState?.connect_country : "");
      if (cur) applyCountrySelectValue(sel, cur);
      else if (prev) applyCountrySelectValue(sel, prev);
    });

    (root || document).querySelectorAll(".loc-city-country").forEach((sel) => {
      const citySel = sel.closest(".loc-city-row")?.querySelector(".loc-city");
      const cityFieldId = citySel?.dataset.locField;
      const field = (lastState?.locations?.fields || []).find((f) => f.id === cityFieldId);
      const prev = resolveCityRowCountry(sel, field);
      sel.innerHTML = '<option value="">Country…</option>';
      if (emptyHint && !countries.length) {
        const o = document.createElement("option");
        o.value = "";
        o.textContent = emptyHint;
        o.disabled = true;
        sel.appendChild(o);
        return;
      }
      countries.forEach((c) => {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = countryLabel(c);
        sel.appendChild(o);
      });
      if (prev) {
        applyCountrySelectValue(sel, prev);
        if (cityFieldId) pendingCityCountries[cityFieldId] = sel.value;
      }
    });
  }

  function refreshLocationCountrySelects() {
    fillLocationCountrySelects($("locationSettingsGrid"));
    fillLocationCountrySelects($("noticeSetup"));
  }

  async function loadCityOptions(countrySel, citySel, opts = {}) {
    if (!citySel) return;
    const preserveCity = opts.preserveCity ? citySel.value : "";
    const country = countrySel?.value || countrySel?.dataset.pendingCountry || "";
    citySel.disabled = true;
    citySel.innerHTML = '<option value="">Loading cities…</option>';
    if (!country) {
      citySel.innerHTML = '<option value="">Pick country first…</option>';
      return;
    }
    try {
      const data = await api(`/api/locations/cities?country=${encodeURIComponent(country.replace(/_/g, " "))}`);
      citySel.innerHTML = '<option value="">Pick city…</option>';
      (data.cities || []).forEach((c) => {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = c;
        citySel.appendChild(o);
      });
      citySel.disabled = !(data.cities || []).length;
      if (preserveCity && [...citySel.options].some((o) => o.value === preserveCity)) {
        citySel.value = preserveCity;
      }
      if (countrySel && country) {
        applyCountrySelectValue(countrySel, country);
        countrySel.dataset.pendingCountry = countrySel.value;
        const cityFieldId = citySel.dataset.locField;
        if (cityFieldId && countrySel.value) pendingCityCountries[cityFieldId] = countrySel.value;
      }
      if (!data.ok && data.error) toast(data.error, false);
    } catch (e) {
      citySel.innerHTML = '<option value="">Could not load cities</option>';
      toast(String(e), false);
    }
  }

  async function restoreCityFieldRow(cSel, citySel, field) {
    if (!cSel || !citySel) return;
    const countryVal = resolveCityRowCountry(cSel, field);
    if (countryVal) {
      applyCountrySelectValue(cSel, countryVal);
      cSel.dataset.pendingCountry = cSel.value;
      if (field?.id && cSel.value) pendingCityCountries[field.id] = cSel.value;
    }
    const preserveCity = field?.value || citySel.value || "";
    await loadCityOptions(cSel, citySel, { preserveCity });
  }

  function bindLocationFieldHandlers(root) {
    fillLocationCountrySelects(root);
    (root || document).querySelectorAll(".loc-city-country").forEach((sel) => {
      if (sel.dataset.bound) return;
      sel.dataset.bound = "1";
      sel.addEventListener("change", () => {
        const citySel = sel.closest(".loc-city-row")?.querySelector(".loc-city");
        sel.dataset.pendingCountry = sel.value;
        const cityFieldId = citySel?.dataset.locField;
        if (cityFieldId) pendingCityCountries[cityFieldId] = sel.value;
        loadCityOptions(sel, citySel);
      });
    });
    (root || document).querySelectorAll("[data-loc-save]").forEach((btn) => {
      if (btn.dataset.bound) return;
      btn.dataset.bound = "1";
      btn.addEventListener("click", () => {
        const retry = btn.dataset.locRetry !== "0";
        saveLocationField(btn.dataset.locSave, btn.dataset.locPrefix || "card", retry);
      });
    });
  }

  async function readLocationFieldValue(fieldId, prefix) {
    const meta = (lastState?.locations?.fields || []).find((f) => f.id === fieldId) || { type: "text" };
    const root = prefix === "notice" ? $("noticeSetup") : (document.getElementById(`locCard_${fieldId}`) || document);
    if (meta.type === "country") {
      return root.querySelector(`select.loc-country[data-loc-field="${fieldId}"][data-loc-prefix="${prefix}"]`)?.value || "";
    }
    if (meta.type === "city") {
      const cSel = root.querySelector(".loc-city-country");
      const country = cSel?.value || cSel?.dataset.pendingCountry || pendingCityCountries[fieldId];
      if (!country) {
        toast("Pick a country first, then a city.", false);
        return "";
      }
      return root.querySelector(`select.loc-city[data-loc-field="${fieldId}"][data-loc-prefix="${prefix}"]`)?.value || "";
    }
    return root.querySelector(`input.loc-text[data-loc-field="${fieldId}"][data-loc-prefix="${prefix}"]`)?.value || "";
  }

  async function saveLocationField(fieldId, prefix, retryPreset = true) {
    const meta = (lastState?.locations?.fields || []).find((f) => f.id === fieldId)
      || { id: fieldId, type: "text", label: fieldId.replace(/_/g, " ") };
    const value = await readLocationFieldValue(fieldId, prefix);
    if (meta.type === "country" && !value) {
      toast(`Pick a country for ${meta.label} first.`, false);
      return { ok: false };
    }
    if (meta.type === "city" && !value) {
      toast("Pick a country, then a city.", false);
      return { ok: false };
    }
    if (meta.type === "text" && !String(value || "").trim()) {
      toast(`${meta.label} is optional — enter a value or ignore this card.`, false);
      return { ok: false };
    }
    const body = { action: "set_config_field", field: fieldId, value };
    if (retryPreset !== false && pendingPresetRetry) {
      body.retry_preset = pendingPresetRetry;
    }
    const res = await doAction(body, "Save place");
    if (res.ok) {
      hideNotice();
      pendingPresetRetry = null;
      toast(res.save_note || res.note || `${meta.label} saved — presets can use it now.`, true);
      if (getActiveView() === "settings") await loadSettingsPanel(true);
      else await loadState(true);
    }
    return res;
  }

  function showMissingFieldWizard(missing, presetId, presetLabel) {
    const meta = missing.field_meta || { id: missing.field, label: "Setting", type: "text" };
    pendingPresetRetry = presetId || null;
    const setupHtml = [
      `<p class="help-text">${esc(missing.preset_hint || "Save below — choose Save only or Save & run preset.")}</p>`,
      buildLocationInputHtml(meta, "notice", missing.current || ""),
      `<div class="actions" style="margin-top:0.55rem">`,
      `<button type="button" class="btn sm primary" data-loc-save="${esc(meta.id)}" data-loc-prefix="notice" data-loc-retry="1">Save &amp; run preset</button>`,
      ` <button type="button" class="btn sm" data-loc-save="${esc(meta.id)}" data-loc-prefix="notice" data-loc-retry="0">Save only</button>`,
      ` <button type="button" class="btn sm jump-link" data-view-jump="dashboard/workflows/places">My places</button>`,
      `</div>`,
    ].join("");
    showNotice("", {
      ok: false,
      title: presetLabel ? `Setup needed — ${presetLabel}` : "Setup needed",
      messageHtml: `<p>${esc(missing.message || "Pick a value to continue.")}</p>`,
      setupHtml,
      copyText: "",
    });
  }

  function renderLocationSettings(data, opts = {}) {
    const gridId = opts.gridId || "locationSettingsGrid";
    const badgeId = opts.badgeId || "locationSettingsBadge";
    const hiddenId = opts.hiddenId || "locationHiddenPanel";
    const grid = $(gridId);
    const badge = badgeId ? $(badgeId) : null;
    if (!grid) return;
    if (skipRenderWhileEditing(grid)) return;
    const fields = (data?.locations?.fields || []).filter((f) => f.show_in_places !== false);
    const hiddenFields = data?.locations?.hidden_fields || [];
    const unset = fields.filter((f) => !f.set).length;
    if (badge) {
      badge.textContent = unset ? `${unset} not set` : "All set";
      badge.className = "badge " + (unset ? "warn" : "on");
    }
    grid.innerHTML = fields.map((f) => {
      const meta = { id: f.id, type: f.type, placeholder: f.placeholder, country_field: f.country_field };
      const typeField = f.custom
        ? `<label class="wf-inline-field">Type
            <select class="loc-meta-type" data-place-id="${esc(f.id)}">
              <option value="country"${f.type === "country" ? " selected" : ""}>Country</option>
              <option value="city"${f.type === "city" ? " selected" : ""}>City</option>
              <option value="text"${f.type === "text" ? " selected" : ""}>Text</option>
            </select>
          </label>`
        : "";
      const savedDisplay = esc(String(f.value).replace(/_/g, " "));
      return `<div class="location-field-card ${f.set ? "set" : ""}" id="locCard_${esc(f.id)}">
        <div class="wf-card-head-row">
          <h4 class="loc-label-display">${esc(f.label)}${f.custom ? ' <span class="badge">Custom</span>' : ""}</h4>
        </div>
        <p class="help-text loc-hint-display">${esc(f.hint || "")}</p>
        <div class="loc-value-block">
          <span class="loc-value-label">${esc(placeValueLabel(f))}</span>
          ${buildLocationInputHtml(meta, f.id, f.value, { omitPlaceholderIfSet: true })}
          <div class="actions loc-value-actions">
            <button type="button" class="btn sm primary" data-loc-save="${esc(f.id)}" data-loc-prefix="${esc(f.id)}">Save</button>
          </div>
          ${f.set
            ? `<div class="loc-saved">Current: <strong>${savedDisplay}</strong></div>`
            : `<div class="loc-empty-hint muted">Not set — pick or type a value, then Save.</div>`}
        </div>
        <div class="wf-inline-edit hidden" data-place-edit-panel="${esc(f.id)}">
          <p class="help-text wf-rename-note">Renames the card title and hint only — change the ${esc(placeValueLabel(f).toLowerCase())} above, then Save.</p>
          <label class="wf-inline-field">Card title <input type="text" class="loc-meta-label" value="${esc(f.label)}" /></label>
          <label class="wf-inline-field">Hint <input type="text" class="loc-meta-hint" value="${esc(f.hint || "")}" /></label>
          ${typeField}
          <div class="actions">
            <button type="button" class="btn sm primary" data-place-save-meta="${esc(f.id)}">Save name</button>
            <button type="button" class="btn sm" data-place-cancel-meta="${esc(f.id)}">Cancel</button>
          </div>
        </div>
        <div class="wf-manage-actions">
          <p class="help-text wf-manage-help">Manage this place:</p>
          <div class="wf-manage-row">
            ${f.set && (f.type === "country" || f.type === "city" || f.id === "connect_country" || f.id === "connect_city")
              ? `<button type="button" class="btn sm" data-place-save-preset="${esc(f.id)}" title="Create a My presets workflow from this saved place">Save as preset</button>`
              : ""}
            <button type="button" class="btn sm" data-place-edit="${esc(f.id)}" title="Rename this card — does not change the saved value">Edit name</button>
            <button type="button" class="btn sm" data-place-hide="${esc(f.id)}" title="Hide this place from the list">Hide</button>
            ${f.set && !f.custom ? `<button type="button" class="btn sm" data-loc-clear="${esc(f.id)}" title="Clear saved value">Clear value</button>` : ""}
            ${f.custom ? `<button type="button" class="btn sm danger" data-loc-remove="${esc(f.id)}" title="Delete this custom place">Delete</button>` : ""}
          </div>
        </div>
      </div>`;
    }).join("");
    bindLocationFieldHandlers(grid);
    fields.filter((f) => f.type === "city").forEach((f) => {
      const row = grid.querySelector(`#locCard_${f.id} .loc-city-row`);
      if (!row) return;
      restoreCityFieldRow(row.querySelector(".loc-city-country"), row.querySelector(".loc-city"), f);
    });
    grid.querySelectorAll("[data-place-save-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-place-save-preset");
        const field = fields.find((f) => f.id === id);
        if (field) savePlaceAsPreset(field);
      });
    });
    grid.querySelectorAll("[data-place-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-place-edit");
        toggleInlineEdit(grid.querySelector(`[data-place-edit-panel="${id}"]`));
      });
    });
    grid.querySelectorAll("[data-place-cancel-meta]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-place-cancel-meta");
        grid.querySelector(`[data-place-edit-panel="${id}"]`)?.classList.add("hidden");
      });
    });
    grid.querySelectorAll("[data-place-save-meta]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-place-save-meta");
        const panel = grid.querySelector(`[data-place-edit-panel="${id}"]`);
        const label = panel?.querySelector(".loc-meta-label")?.value || "";
        const hint = panel?.querySelector(".loc-meta-hint")?.value || "";
        const type = panel?.querySelector(".loc-meta-type")?.value;
        const body = { action: "place_update", id, label, hint };
        if (type) body.type = type;
        const res = await doAction(body, "Update place");
        if (res.ok) await loadState(true);
      });
    });
    grid.querySelectorAll("[data-place-hide]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "place_hide", id: btn.getAttribute("data-place-hide") }, "Hide place")
          .then((r) => {
            if (r.ok) {
              loadState(true);
              if (getActiveView() === "settings") loadSettingsPanel(true);
            }
          });
      });
    });
    grid.querySelectorAll("[data-loc-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "custom_place_remove", id: btn.getAttribute("data-loc-remove") }, "Remove place")
          .then((r) => { if (r.ok) loadState(true); });
      });
    });
    grid.querySelectorAll("[data-loc-clear]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "location_clear", field: btn.getAttribute("data-loc-clear") }, "Clear place")
          .then((r) => { if (r.ok) loadState(true); });
      });
    });
    renderHiddenPanel(
      $(hiddenId),
      `Hidden places (${hiddenFields.length})`,
      hiddenFields.map((f) =>
        `<div class="wf-hidden-row"><span>${esc(f.label)}</span><div class="actions">
          <button type="button" class="btn sm" data-place-unhide="${esc(f.id)}">Show again</button>
          ${f.set && !f.custom ? `<button type="button" class="btn sm" data-loc-clear="${esc(f.id)}">Clear value</button>` : ""}
          ${f.custom ? `<button type="button" class="btn sm danger" data-loc-remove="${esc(f.id)}">Delete</button>` : ""}
        </div></div>`
      ).join("")
    );
    $(hiddenId)?.querySelectorAll("[data-place-unhide]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "place_unhide", id: btn.getAttribute("data-place-unhide") }, "Restore place")
          .then((r) => {
            if (r.ok) {
              loadState(true);
              if (getActiveView() === "settings") loadSettingsPanel(true);
            }
          });
      });
    });
    $(hiddenId)?.querySelectorAll("[data-loc-remove]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "custom_place_remove", id: btn.getAttribute("data-loc-remove") }, "Remove place")
          .then((r) => {
            if (r.ok) {
              loadState(true);
              if (getActiveView() === "settings") loadSettingsPanel(true);
            }
          });
      });
    });
    $(hiddenId)?.querySelectorAll("[data-loc-clear]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "location_clear", field: btn.getAttribute("data-loc-clear") }, "Clear place")
          .then((r) => {
            if (r.ok) {
              loadState(true);
              if (getActiveView() === "settings") loadSettingsPanel(true);
            }
          });
      });
    });
  }

  function invalidateScenarioCaches() {
    invalidateApiCache("/api/settings");
    invalidateApiCache("/api/wifi/hub");
    invalidateApiCache("/api/security");
    invalidateApiCache("/api/security/summary");
  }

  function buildPresetCard(p) {
    const card = document.createElement("div");
    const needs = presetNeedsSetup(p);
    card.className = "preset" + (needs ? " needs-setup" : " ready");
    if (needs) {
      card.title = "Needs a My places value before Apply — use Set up first or open My places.";
    }
    const statusBadge = needs
      ? `<span class="preset-status badge warn">Needs setup</span>`
      : `<span class="preset-status badge on">Ready</span>`;
    const req = (p.requires || []).length
      ? `<div class="req">Needs setup: ${(p.requires || []).map((r) => {
          const label = placeFieldLabel(r);
          const unset = !locationFieldSet(r);
          const dest = placeFieldSetupDest(r);
          return unset
            ? `<button type="button" class="btn sm preset-req-link" data-place-jump="${esc(r)}" title="Open ${esc(dest)} — ${esc(label)}">${esc(label)}</button>`
            : esc(label);
        }).reduce((html, part, i, arr) => html + (i ? ", " : "") + part, "")}${needs ? " — save the missing value first" : ""}</div>`
      : "";
    const stepsHint = (p.steps || []).length
      ? `<ul class="preset-steps">${(p.steps || []).slice(0, 4).map((s) => `<li>${esc(String(s.action || s).replace(/_/g, " "))}</li>`).join("")}${(p.steps || []).length > 4 ? `<li class="muted">+ ${(p.steps || []).length - 4} more step(s)</li>` : ""}</ul>`
      : "";
    const helpBlock = `<div class="preset-does"><strong>What it does</strong><p class="preset-summary-display">${esc(p.summary || "Runs a saved workflow.")}</p>${stepsHint}</div>`;
    card.innerHTML = `<div class="preset-head"><strong class="preset-label-display">${esc(p.label)}</strong>${statusBadge}</div>
      <div class="wf-inline-edit hidden preset-inline-edit">
        <p class="help-text wf-rename-note">Changes how this preset looks here — not My places values. Use <strong>My places</strong> to set countries, DNS, etc.</p>
        <label class="wf-inline-field">Display name <input type="text" class="preset-meta-label" value="${esc(p.label || "")}" /></label>
        <label class="wf-inline-field">What it does <input type="text" class="preset-meta-summary" value="${esc(p.summary || "")}" /></label>
        <label class="wf-inline-field">Category <input type="text" class="preset-meta-category" value="${esc(p.category || "General")}" /></label>
        <div class="actions">
          <button type="button" class="btn sm primary preset-save-meta">Save display</button>
          <button type="button" class="btn sm preset-cancel-meta">Cancel</button>
        </div>
      </div>
      ${helpBlock}${req}`;
    const actions = document.createElement("div");
    actions.className = "preset-actions";
    const actionsHelp = document.createElement("p");
    actionsHelp.className = "help-text preset-actions-help";
    actionsHelp.textContent = "Manage this preset:";
    actions.appendChild(actionsHelp);
    const actionsRow = document.createElement("div");
    actionsRow.className = "preset-actions-row";
    const editBtn = document.createElement("button");
    editBtn.type = "button";
    editBtn.className = "btn sm";
    editBtn.textContent = "Edit name";
    editBtn.title = "Change display name, What it does, and category on this card.";
    editBtn.addEventListener("click", () => toggleInlineEdit(card.querySelector(".preset-inline-edit")));
    actionsRow.appendChild(editBtn);
    if (p.user) {
      const editPresetBtn = document.createElement("button");
      editPresetBtn.type = "button";
      editPresetBtn.className = "btn sm primary";
      editPresetBtn.textContent = "Edit preset";
      editPresetBtn.title = "Open the full preset builder with every setting — same as Create preset.";
      editPresetBtn.addEventListener("click", () => editUserPresetInBuilder(p));
      actionsRow.appendChild(editPresetBtn);
      const yamlBtn = document.createElement("button");
      yamlBtn.type = "button";
      yamlBtn.className = "btn sm";
      yamlBtn.textContent = "Edit YAML";
      yamlBtn.title = "Open the preset file in Tools → Editor.";
      yamlBtn.addEventListener("click", async () => {
        navigateRoute("network", "tools", { sub: "editor" });
        await loadFileList();
        await openFile(p.file_id || `user/${p.id}.yaml`);
      });
      actionsRow.appendChild(yamlBtn);
    }
    const hideBtn = document.createElement("button");
    hideBtn.type = "button";
    hideBtn.className = "btn sm";
    hideBtn.textContent = "Hide";
    hideBtn.title = "Remove from My presets list without deleting the file.";
    hideBtn.addEventListener("click", () => {
      doAction({ action: "preset_hide", id: p.id }, "Hide preset").then((r) => {
        if (r.ok && !r.state) loadState(true);
      });
    });
    actionsRow.appendChild(hideBtn);
    card.querySelector(".preset-save-meta")?.addEventListener("click", async () => {
      const body = {
        action: "preset_update",
        id: p.id,
        file_id: p.file_id,
        user: p.user,
        label: card.querySelector(".preset-meta-label")?.value,
        summary: card.querySelector(".preset-meta-summary")?.value,
        category: card.querySelector(".preset-meta-category")?.value,
      };
      const res = await doAction(body, "Update preset");
      if (res.ok && !res.state) await loadState(true);
    });
    card.querySelector(".preset-cancel-meta")?.addEventListener("click", () => {
      card.querySelector(".preset-inline-edit")?.classList.add("hidden");
    });
    if (needs) {
      const reqId = (p.requires || []).find((r) => !locationFieldSet(r));
      const reqLabel = reqId ? placeFieldLabel(reqId) : "My places";
      const setupBtn = document.createElement("button");
      setupBtn.type = "button";
      setupBtn.className = "btn primary sm";
      setupBtn.textContent = reqId ? `Set up: ${reqLabel}` : "Set up first";
      setupBtn.title = reqId
        ? `Jump to ${placeFieldSetupDest(reqId)} — edit ${reqLabel}, Save, then apply this preset.`
        : "Opens a short wizard to save the missing value, then runs this preset.";
      setupBtn.addEventListener("click", () => {
        const missingId = (p.requires || []).find((r) => !locationFieldSet(r));
        if (missingId) {
          scrollToPlaceField(missingId);
          toast(`Edit ${placeFieldLabel(missingId)} on ${placeFieldSetupDest(missingId)}, press Save, then Apply this preset.`, true);
          return;
        }
        const missing = {
          field: reqId,
          message: `This preset needs your ${reqId.replace(/_/g, " ")}.`,
          preset_hint: "Save below — the preset runs right after.",
          field_meta: (lastState?.locations?.fields || []).find((f) => f.id === reqId) || { id: reqId, type: reqId.includes("city") ? "city" : (reqId.includes("country") ? "country" : "text") },
        };
        showMissingFieldWizard(missing, p.id, p.label);
      });
      const placesBtn = document.createElement("button");
      placesBtn.type = "button";
      placesBtn.className = "btn sm";
      const jumpDest = reqId ? placeFieldSetupDest(reqId) : "My places";
      placesBtn.textContent = `${jumpDest} ↑`;
      placesBtn.title = `Open ${jumpDest}`;
      placesBtn.addEventListener("click", () => scrollToPlaceField(reqId || "connect_country"));
      actionsRow.appendChild(setupBtn);
      actionsRow.appendChild(placesBtn);
    } else {
      const applyBtn = document.createElement("button");
      applyBtn.type = "button";
      applyBtn.className = "btn primary sm";
      applyBtn.textContent = "Run preset";
      applyBtn.title = p.summary || "Run this preset now.";
      markConfirm(applyBtn, `Apply “${p.label}”? This may change VPN, DNS, firewall, or WiFi settings.`);
      applyBtn.addEventListener("click", () => doAction({ action: "preset", preset: p.id }, p.label));
      actionsRow.appendChild(applyBtn);
      const previewBtn = document.createElement("button");
      previewBtn.type = "button";
      previewBtn.className = "btn sm";
      previewBtn.textContent = "Preview";
      previewBtn.title = "Dry run — show planned steps without applying.";
      previewBtn.addEventListener("click", () =>
        doAction({ action: "preset_dry_run", preset: p.id }, "Preview preset").then((r) => {
          if (r.ok && r.steps) {
            showNotice(
              (r.steps || []).map((s) => `${s.n}. ${s.text}`).join("\n"),
              { ok: true, title: `Dry run: ${r.label || p.label}` }
            );
          }
        })
      );
      actionsRow.appendChild(previewBtn);
    }
    const shareBtn = document.createElement("button");
    shareBtn.type = "button";
    shareBtn.className = "btn sm";
    shareBtn.textContent = "Share";
    shareBtn.title = "Copy preset YAML to clipboard and download a .yaml file to share.";
    shareBtn.addEventListener("click", () => sharePreset(p));
    actionsRow.appendChild(shareBtn);
    if (!p.user) {
      const saveBtn = document.createElement("button");
      saveBtn.type = "button";
      saveBtn.className = "btn sm primary";
      saveBtn.textContent = "Save to My presets";
      saveBtn.title = "Copy this preset into your My presets folder so you can edit and customize it.";
      saveBtn.addEventListener("click", () => savePresetToMyPresets(p));
      actionsRow.appendChild(saveBtn);
    }
    if (p.user) {
      const delBtn = document.createElement("button");
      delBtn.type = "button";
      delBtn.className = "btn sm danger";
      delBtn.textContent = "Delete";
      delBtn.title = "Permanently delete this preset file.";
      markConfirm(delBtn, `Delete preset “${p.label}”? This removes the YAML file permanently.`);
      delBtn.addEventListener("click", () => {
        doAction({ action: "preset_delete", id: p.id, file_id: p.file_id }, "Delete preset")
          .then((r) => { if (r.ok) loadState(true); });
      });
      actionsRow.appendChild(delBtn);
    }
    actions.appendChild(actionsRow);
    card.appendChild(actions);
    card.querySelectorAll("[data-place-jump]").forEach((btn) => {
      btn.addEventListener("click", (e) => {
        e.preventDefault();
        scrollToPlaceField(btn.getAttribute("data-place-jump"));
      });
    });
    return card;
  }

  function presetCategoryTooltip(cat, count, unset) {
    let tip = `${PRESET_CATEGORY_INTRO[cat] || cat} — ${count} preset${count === 1 ? "" : "s"}.`;
    if (unset) {
      tip += ` Orange outline: ${unset} preset${unset === 1 ? "" : "s"} here need a value saved under My places before Apply.`;
    }
    return tip;
  }

  function nordInstalled(data) {
    return !!(data?.nordvpn?.installed ?? data?.nordvpn_available ?? data?.available ?? data?.doctor?.nord_installed);
  }

  /** Full package — all Nord Dashboard panels and tools tabs are always available. */
  function showNordFeatures(data) {
    return true;
  }

  function applyNordUiVisibility(data) {
    document.querySelectorAll("[data-nord-feature]").forEach((el) => {
      el.classList.remove("hidden");
    });
    syncToolsTabsVisibility(data);
    renderAutomateNordGates(data);
  }

  function redirectNordBlockedRoute(route) {
    return null;
  }

  function installProfile(data) {
    return data?.usage?.install_profile || "full";
  }

  function isNordProfile(data) {
    return false;
  }

  function isNetworkProfile(data) {
    return false;
  }

  function isToolsOnly(data) {
    return false;
  }

  function shouldShowOptionalExtras(data) {
    return false;
  }

  function renderNordExtrasPanel(data) {
    $("dashSubnav")?.querySelector('[data-page-tab="optional-extras"]')?.classList.add("hidden");
    $("nordExtrasPanel")?.classList.add("hidden");
  }

  function updateMeshPageBadge(enabled) {
    const on = !!enabled;
    const badge = $("meshPageBadge");
    if (badge) {
      badge.textContent = on ? "On" : "Off";
      badge.className = "badge " + (on ? "on" : "off");
    }
  }

  function meshSettingOn(value) {
    return String(value || "").toLowerCase().includes("enabled") || String(value || "").toLowerCase() === "on";
  }

  function renderMeshnetPageNoNord() {
    updateMeshPageBadge(false);
    if ($("meshPageMetrics")) {
      $("meshPageMetrics").innerHTML = statCell("Meshnet", "Install NordVPN first", "off");
    }
    if ($("meshBox")) $("meshBox").innerHTML = "";
    if ($("meshToggleRow")) $("meshToggleRow").innerHTML = "";
    if ($("meshStatusHint")) {
      $("meshStatusHint").textContent = "Install and log in to NordVPN from the Wizard, then return here to enable Meshnet and link devices.";
    }
    if ($("meshPeerCount")) $("meshPeerCount").textContent = "";
    if ($("meshPeers")) {
      $("meshPeers").innerHTML = `<p class="help-text muted-inline">Meshnet appears after NordVPN is installed and logged in.</p>`;
    }
    if ($("meshSavedPeer")) $("meshSavedPeer").textContent = "";
  }

  function meshApiPeersList(apiPeers) {
    return (apiPeers || []).filter((p) => {
      const h = String(p.hostname || p.name || "").trim();
      return h && /\.nord$/i.test(h);
    });
  }

  function renderMeshPeersGrid(el, raw, opts = {}) {
    if (!el) return;
    const apiPeers = meshApiPeersList(opts.apiPeers);
    const { device, peers } = parseMeshPeers(raw);
    const peerRows = apiPeers.length
      ? apiPeers.map((p) => ({
          name: p.hostname || p.name,
          props: p,
        }))
      : peers;
    if (!peerRows.length && !device.length) {
      el.innerHTML = `<div class="mesh-empty glass">
        <p><strong>No peers yet</strong></p>
        <p class="help-text">Open the NordVPN app on another phone or PC → Meshnet → invite this device, or accept an incoming link. Peers show up here within a few seconds after linking.</p>
      </div>`;
      return;
    }
    let html = "";
    if (device.length) {
      const summary = device.slice(0, 5).map((d) => `${esc(d.k)}: ${esc(d.v)}`).join(" · ");
      html += `<div class="mesh-peer-card mesh-peer-local"><div class="peer-name">This device</div><div class="peer-meta">${summary}</div></div>`;
    }
    peerRows.forEach((p) => {
      const host = p.name || p.props?.hostname || p.props?.Hostname || "";
      const status = p.props?.status || p.props?.Status || "—";
      const os = p.props?.os || p.props?.OS || p.props?.Os || "";
      const ip = p.props?.ip || p.props?.["Meshnet IP"] || p.props?.["meshnet ip"] || "";
      const routing = p.props?.["allow routing"] || p.props?.["allows routing"] || "";
      const meta = [status, os, ip, routing ? `routing ${routing}` : ""].filter(Boolean).join(" · ");
      const detailKeys = Object.entries(p.props || {}).filter(([k]) => !/^(Status|OS|Os|hostname)$/i.test(k));
      const details = detailKeys.map(([k, v]) => `${esc(k)}: ${esc(v)}`).join("\n");
      html += `<div class="mesh-peer-card">
        <div class="peer-head">
          <div class="peer-name">${esc(host || "Peer")}</div>
          ${opts.interactive && host ? `<button type="button" class="btn sm primary" data-mesh-peer-connect="${esc(host)}" data-confirm="1" data-confirm-message="Route traffic through ${esc(host)}?">Route via peer</button>` : ""}
        </div>
        <div class="peer-meta">${esc(meta || "Linked device")}</div>
        ${details ? `<details><summary>More details</summary><pre class="mono mesh-peer-details">${details}</pre></details>` : ""}
      </div>`;
    });
    if (peers.length > 8) {
      html += `<details class="mesh-peer-card mesh-peer-raw"><summary>+${peers.length - 8} more — show raw list</summary><pre class="mono">${esc(raw)}</pre></details>`;
    }
    el.innerHTML = html;
    if (opts.interactive) {
      el.querySelectorAll("[data-mesh-peer-connect]").forEach((btn) => {
        btn.addEventListener("click", () => {
          const peer = btn.getAttribute("data-mesh-peer-connect");
          if (!peer) return;
          doAction({ action: "mesh_connect", peer }, "Meshnet peer").then((res) => {
            if (res.ok) loadMeshnetPage(true);
          });
        });
      });
    }
  }

  function renderMeshnetPage(state, mesh) {
    if (!$("meshnetHub")) return;
    const set = state?.settings || {};
    const sd = state?.smart_dns || {};
    const enabled = !!(mesh?.meshnet_enabled ?? String(set.Meshnet || "").includes("enabled"));
    updateMeshPageBadge(enabled);
    const peerCount = meshApiPeersList(mesh?.peers).length || mesh?.peer_count || parseMeshPeers(mesh?.raw || state?.mesh_peers_raw || "").peers.length;
    const meshIp = mesh?.mesh_ip || state?.mesh_ip || "—";
    const savedPeer = mesh?.configured_peer || state?.mesh_peer || "";
    const vpnOn = !!(mesh?.vpn_connected ?? state?.status?.connected);

    if ($("meshPageMetrics")) {
      $("meshPageMetrics").innerHTML = [
        statCell("Mesh IP", esc(meshIp), meshIp && meshIp !== "—" ? "on" : ""),
        statCell("Linked peers", String(peerCount), peerCount ? "on" : ""),
        statCell("VPN tunnel", vpnOn ? (mesh?.vpn_country || state?.status?.Country || "Connected") : "Off", vpnOn ? "on" : "off"),
        statCell("LAN discovery", meshSettingOn(mesh?.lan_discovery || set["LAN discovery"]) ? "On" : "Off", meshSettingOn(mesh?.lan_discovery || set["LAN discovery"]) ? "on" : "off"),
      ].join("");
    }

    if ($("meshBox")) {
      $("meshBox").innerHTML = [
        statCell("Routing", meshSettingOn(mesh?.routing || set.Routing) ? "On" : "Off", meshSettingOn(mesh?.routing || set.Routing) ? "on" : ""),
        statCell("WiFi", esc(sd.wifi_device || "—")),
        statCell("Smart DNS", sd.active ? "Active on WiFi" : "Off", sd.active ? "on" : "off"),
      ].join("");
    }

    const meshToggle = $("meshToggleRow");
    if (meshToggle) {
      meshToggle.innerHTML = nordToggleStatRow("Meshnet", enabled, "meshnet");
      bindNordToggleRows(meshToggle, true);
    }

    const hint = $("meshStatusHint");
    if (hint) {
      if (!enabled) {
        hint.textContent = "Meshnet is off — turn it on above to get a mesh IP and see linked devices. You can still use VPN without Meshnet.";
      } else if (!peerCount) {
        hint.textContent = "Meshnet is on but no peers are linked yet — invite another device from the NordVPN app.";
      } else if (vpnOn) {
        hint.textContent = "VPN and Meshnet can run together — use Local traffic to see mesh vs tunnel paths.";
      } else {
        hint.textContent = `${peerCount} linked device${peerCount === 1 ? "" : "s"} — route through a peer below or pick a preset that uses Meshnet.`;
      }
    }

    if ($("meshPeerCount")) {
      $("meshPeerCount").textContent = peerCount ? `${peerCount} peer${peerCount === 1 ? "" : "s"}` : "None linked";
    }

    renderMeshPeersGrid($("meshPeers"), mesh?.raw || state?.mesh_peers_raw || "", {
      apiPeers: mesh?.peers || [],
      interactive: true,
    });

    const savedEl = $("meshSavedPeer");
    if (savedEl) {
      savedEl.innerHTML = savedPeer
        ? `Default peer in My places: <code>${esc(savedPeer)}</code> — used by Meshnet presets.`
        : `No default peer saved — add <strong>Meshnet peer</strong> under My places for preset workflows.`;
    }
    const peerInput = $("meshPeerInput");
    if (peerInput && !peerInput.value && savedPeer) peerInput.placeholder = savedPeer;
  }

  async function loadMeshnetPage(force) {
    if (!nordInstalled(lastState)) {
      renderMeshnetPageNoNord();
      return;
    }
    try {
      await ensureSwitchesMeta(!!force);
      const mesh = await apiCached("/api/meshnet", {}, force ? 0 : CACHE_TTL.meshnet);
      renderMeshnetPage(lastState || {}, mesh || {});
    } catch (e) {
      toast(String(e), false);
    }
  }

  function initMeshnetPageActions() {
    const hub = $("meshnetHub");
    if (!hub || hub.dataset.meshBound) return;
    hub.dataset.meshBound = "1";
    $("btnMeshRefresh")?.addEventListener("click", () => loadMeshnetPage(true));
    $("btnMeshPeerConnect")?.addEventListener("click", () => {
      const peer = $("meshPeerInput")?.value?.trim();
      if (!peer) return toast("Enter a peer hostname (e.g. my-phone.nord)", false);
      doAction({ action: "mesh_connect", peer }, "Meshnet peer").then((res) => {
        if (res.ok) loadMeshnetPage(true);
      });
    });
  }

  async function enableNetworkHub() {
    const res = await doAction({ action: "enable_network_modules" }, "Enable Network & Security");
    if (res.ok) {
      toast("Network & Security hub enabled", true);
      await loadState(true);
      navigateRoute("network", "wifi", { force: true });
    }
  }

  async function installOnboardExtras(which) {
    if (dashTab !== "wizard") {
      $("onboardOverlay")?.classList.add("hidden");
    }
    if (which === "network" || which === "both") {
      navigateRoute("network", "network-packages", { force: true });
      await loadHubTools("network", true);
      await installAllHubTools("network");
    }
    if (which === "security" || which === "both") {
      if (which === "both") await new Promise((r) => setTimeout(r, 800));
      navigateRoute("network", "security-packages", { force: true });
      await loadHubTools("security", true);
      await installAllHubTools("security");
    }
  }

  function renderToolsWelcomeGrid() {
    const grid = $("toolsWelcomeGrid");
    if (!grid) return;
    grid.innerHTML = TOOLS_WELCOME_LINKS.map((item) =>
      `<button type="button" class="tools-welcome-card" data-view-jump="${esc(item.route)}"><strong>${esc(item.label)}</strong><span>${esc(item.desc)}</span></button>`
    ).join("") + `<div class="tools-welcome-extras actions" style="margin-top:0.65rem;grid-column:1/-1">
      <button type="button" class="btn sm primary" id="btnWelcomeInstallNetworking">Install all networking tools</button>
      <button type="button" class="btn sm" id="btnWelcomeInstallSecurity">Install all security tools</button>
      <button type="button" class="btn sm" id="btnWelcomeInstallAllExtras">Install networking + security</button>
    </div>`;
    bindViewJumps(grid);
    $("btnWelcomeInstallNetworking")?.addEventListener("click", () => installOnboardExtras("network"));
    $("btnWelcomeInstallSecurity")?.addEventListener("click", () => installOnboardExtras("security"));
    $("btnWelcomeInstallAllExtras")?.addEventListener("click", () => installOnboardExtras("both"));
  }

  function renderUsageMode(data) {
    $("toolsWelcomePanel")?.classList.add("hidden");
    if ($("toolsWelcomePanel")) $("toolsWelcomePanel").hidden = true;
    renderNordExtrasPanel(data);
    const badge = $("usageModeBadge");
    if (badge && data?.usage) {
      badge.textContent = data.usage.label || "Full hub";
      badge.className = "badge on";
    }
    $("btnSwitchVpnMode")?.classList.add("hidden");
  }

  function isNordSettingEnabled(value) {
    return String(value || "").toLowerCase().includes("enabled");
  }

  function renderTopbarVpnBadge(connected, { setupNeeded = false } = {}) {
    const el = $("vpnBadge");
    if (!el) return;
    let text = "VPN off";
    let tone = "off";
    let title = "NordVPN disconnected — open connection panel";
    if (setupNeeded) {
      text = "VPN setup";
      tone = "na";
      title = "Install NordVPN from Setup";
    } else if (connected) {
      text = "VPN on";
      tone = "on";
      title = "NordVPN connected — open connection panel";
    }
    el.textContent = text;
    el.className = `sys-chip sys-vpn jump-link ${tone}`;
    el.title = title;
  }

  function renderTopbarNordFw(data) {
    const el = $("topbarNordFw");
    if (!el) return;
    if (!data || !nordInstalled(data)) {
      el.textContent = "Nord FW n/a";
      el.className = "sys-chip sys-nord-fw jump-link na";
      el.title = "Install NordVPN to use Nord firewall";
      return;
    }
    const nord = data.firewall?.nord || {};
    const settings = data.settings || {};
    const on = nord.firewall != null ? !!nord.firewall : isNordSettingEnabled(settings.Firewall);
    el.textContent = on ? "Nord FW on" : "Nord FW off";
    el.className = `sys-chip sys-nord-fw jump-link ${on ? "on" : "off"}`;
    el.title = on
      ? "NordVPN firewall enabled — open Nord firewall switches"
      : "NordVPN firewall disabled — open Nord firewall switches";
  }

  function renderNoNordStatus(data) {
    const box = $("statusBox");
    if (!box) return;
    box.innerHTML = [
      statCell("NordVPN", "Not installed yet", "off"),
      `<div class="lbl span3">What to do</div><div class="val span3">Open ${viewLink("dashboard/wizard", "Wizard")} → <strong>Install NordVPN</strong>, then ${viewLink("dashboard/terminal", "Nord shell")} → <code>nordvpn login</code>. Network &amp; Security and Tools are already in the top menu.</div>`,
    ].join("");
    bindViewJumps(box);
    renderTopbarVpnBadge(false, { setupNeeded: true });
    renderTopbarNordFw(data);
    $("connPulse")?.classList.remove("on");
  }

  function setVpnControlsEnabled(enabled, hint) {
    ["btnConnect", "btnReconnect", "btnDisconnect"].forEach((id) => {
      const btn = $(id);
      if (!btn) return;
      btn.disabled = !enabled;
      if (hint) btn.title = hint;
    });
    const countrySel = $("connectCountrySelect");
    const citySel = $("connectCitySelect");
    if (countrySel) countrySel.disabled = !enabled;
    if (citySel && !enabled) citySel.disabled = true;
  }

  function renderMyPresets(data) {
    renderUserPresetsGrid(data, {
      grid: "myPresetsGrid",
      countBadge: "myPresetsCount",
      hiddenPanel: "myPresetsHiddenPanel",
      emptyMessage: "No presets yet. Open Create preset (wizard tab) or click Create preset above to build your first one.",
    });
    void loadPresetSuggestions();
  }

  function renderCreatePresetsList(data) {
    renderUserPresetsGrid(data, {
      grid: "presetBuilderResults",
      countBadge: "presetBuilderCount",
      hiddenPanel: "presetBuilderHiddenPanel",
      emptyMessage: "Your saved presets appear here and in My places → My presets after you create one.",
      sectionTitle: "Your presets",
    });
  }

  function renderUserPresetsGrid(data, opts) {
    renderPresets(data, {
      grid: opts.grid,
      countBadge: opts.countBadge,
      hiddenPanel: opts.hiddenPanel,
      onlyUser: true,
      flatList: true,
      emptyMessage: opts.emptyMessage,
      vpnRequired: false,
      sectionTitle: opts.sectionTitle,
    });
  }

  function renderWorkflowPresets(data) {
    renderMyPresets(data);
  }

  function renderPresets(data, opts = {}) {
    const grid = typeof opts.grid === "string" ? $(opts.grid) : (opts.grid || $("myPresetsGrid"));
    if (!grid) return;
    if (skipRenderWhileEditing(grid)) return;
    grid.innerHTML = "";
    const filterOpts = {};
    if (opts.onlyUser) filterOpts.onlyUser = true;
    if (opts.onlyCategories?.length) {
      filterOpts.onlyCategories = opts.onlyCategories;
    } else {
      filterOpts.excludeCategories = opts.excludeCategories?.length
        ? opts.excludeCategories
        : (grid.id === "myPresetsGrid" || grid.id === "presetBuilderResults" ? WORKFLOWS_EXCLUDED_PRESET_CATEGORIES : []);
    }
    const presets = filterPresetsList(data?.presets || [], filterOpts);
    const hiddenPresets = filterHiddenPresetsList(data?.hidden_presets || [], filterOpts);
    const panelCfg = presetPanelConfigForGrid(grid.id);
    const countEl = opts.countBadge === false ? null : $(opts.countBadge || panelCfg?.count || "presetCount");
    const totalCount = presets.length + hiddenPresets.length;
    if (countEl) {
      countEl.textContent = totalCount ? `(${presets.length} shown${hiddenPresets.length ? `, ${hiddenPresets.length} hidden` : ""})` : "";
    }
    if (opts.vpnRequired && !nordInstalled(data)) {
      grid.innerHTML = `<p class="help-text">Install NordVPN first — open ${viewLink("dashboard/wizard", "Wizard")} or ${viewLink("dashboard/terminal", "Nord shell")}.</p>`;
      bindViewJumps(grid);
      return;
    }
    if (!presets.length) {
      grid.innerHTML = `<p class="muted help-text">${opts.emptyMessage || "No presets loaded."}</p>`;
      if (opts.hiddenPanel !== false) {
        const hiddenPanelId = opts.hiddenPanel || "myPresetsHiddenPanel";
        renderHiddenPanel(
          $(hiddenPanelId),
          `Hidden presets (${hiddenPresets.length})`,
          hiddenPresets.map((p) =>
            `<div class="wf-hidden-row"><span><strong>${esc(p.label || p.id)}</strong></span>
            <div class="actions"><button type="button" class="btn sm" data-preset-unhide="${esc(p.id)}">Show again</button>
            <button type="button" class="btn sm danger" data-preset-delete="${esc(p.id)}" data-preset-file="${esc(p.file_id || "")}">Delete</button>
            </div></div>`
          ).join("")
        );
        bindPresetHiddenPanelActions(hiddenPanelId);
      }
      return;
    }
    if (opts.sectionTitle) {
      const head = document.createElement("h4");
      head.className = "my-presets-inline-title";
      head.textContent = opts.sectionTitle;
      grid.appendChild(head);
    }
    if (opts.flatList) {
      presets.forEach((p) => grid.appendChild(buildPresetCard(p)));
      applyButtonTitles(grid);
      if (opts.hiddenPanel === false) return;
      const hiddenPanelId = opts.hiddenPanel || "myPresetsHiddenPanel";
      renderHiddenPanel(
        $(hiddenPanelId),
        `Hidden presets (${hiddenPresets.length}) — click Show again to restore`,
        hiddenPresets.map((p) =>
          `<div class="wf-hidden-row"><span><strong>${esc(p.label || p.id)}</strong></span>
          <div class="actions"><button type="button" class="btn sm" data-preset-unhide="${esc(p.id)}">Show again</button>
          <button type="button" class="btn sm danger" data-preset-delete="${esc(p.id)}" data-preset-file="${esc(p.file_id || "")}">Delete</button>
          </div></div>`
        ).join("")
      );
      bindPresetHiddenPanelActions(hiddenPanelId);
      return;
    }
    const categories = orderedPresetCategories(presets);
    if (!categories.length) {
      grid.innerHTML = `<p class="muted">${opts.emptyMessage || "No presets loaded."}</p>`;
      return;
    }
    let scrollCatSlug = null;
    if (pendingPresetCategory && (grid.id === "myPresetsGrid" || grid.id === "presetBuilderResults")) {
      const fromHash = categoryFromSlug(pendingPresetCategory, categories);
      scrollCatSlug = fromHash ? categorySlug(fromHash) : pendingPresetCategory;
      pendingPresetCategory = null;
    }
    categories.forEach((cat) => {
      const catPresets = presets.filter((p) => presetCategory(p) === cat);
      if (!catPresets.length) return;
      const unset = catPresets.filter((p) => presetNeedsSetup(p)).length;
      const section = document.createElement("section");
      section.className = `preset-category-row${unset ? " has-unset" : ""}`;
      section.id = `preset-category-${categorySlug(cat)}`;
      const head = document.createElement("div");
      head.className = "preset-category-head";
      const showCatHead = categories.length > 1 || grid.id === "myPresetsGrid";
      if (showCatHead) {
        head.innerHTML = `<div class="preset-category-title-row">
            <h4 class="preset-cat">${esc(cat)}</h4>
            <span class="preset-cat-count muted">${catPresets.length} preset${catPresets.length === 1 ? "" : "s"}</span>
          </div>
          <p class="help-text preset-category-blurb">${esc(PRESET_CATEGORY_INTRO[cat] || "")}${unset ? ` <span class="tab-unset">${unset} need My places</span>` : ""}</p>`;
        section.appendChild(head);
      }
      const row = document.createElement("div");
      row.className = "presets";
      catPresets.forEach((p) => row.appendChild(buildPresetCard(p)));
      section.appendChild(row);
      grid.appendChild(section);
    });
    applyButtonTitles(grid);
    if (scrollCatSlug) {
      requestAnimationFrame(() => scrollToPresetCategory(scrollCatSlug));
    }
    if (opts.hiddenPanel === false) return;
    const hiddenPanelId = opts.hiddenPanel || panelCfg?.hidden || "presetHiddenPanel";
    renderHiddenPanel(
      $(hiddenPanelId),
      `Hidden presets (${hiddenPresets.length})`,
      hiddenPresets.map((p) =>
        `<div class="wf-hidden-row"><span><strong>${esc(p.label || p.id)}</strong> <span class="muted">${esc(p.category || "")}</span></span>
        <div class="actions"><button type="button" class="btn sm" data-preset-unhide="${esc(p.id)}">Show</button>
        ${p.user ? `<button type="button" class="btn sm danger" data-preset-delete="${esc(p.id)}" data-preset-file="${esc(p.file_id || "")}">Delete</button>` : ""}
        </div></div>`
      ).join("")
    );
    bindPresetHiddenPanelActions(hiddenPanelId);
  }

  function bindPresetHiddenPanelActions(hiddenPanelId) {
    $(hiddenPanelId)?.querySelectorAll("[data-preset-unhide]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "preset_unhide", id: btn.getAttribute("data-preset-unhide") }, "Restore preset")
          .then((r) => { if (r.ok && !r.state) loadState(true); });
      });
    });
    $(hiddenPanelId)?.querySelectorAll("[data-preset-delete]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction({ action: "preset_delete", id: btn.getAttribute("data-preset-delete"), file_id: btn.getAttribute("data-preset-file") }, "Delete preset")
          .then((r) => { if (r.ok) loadState(true); });
      });
    });
  }

  function renderDashboardPresetPanels(data) {
    Object.entries(DASHBOARD_PRESET_PANELS).forEach(([, panel]) => {
      renderPresets(data, {
        grid: panel.grid,
        countBadge: panel.count,
        hiddenPanel: panel.hidden,
        onlyCategories: [panel.category],
        emptyMessage: `No ${panel.category} presets loaded.`,
        vpnRequired: true,
      });
    });
  }

  function presetFactoryResetMessage(panelId, categoryLabel) {
    const name = panelId === "workflows"
      ? "general presets on Presets & places"
      : `${categoryLabel} presets on this tab`;
    return [
      `Reset ${name} to factory?`,
      "",
      "• Shows any hidden presets again",
      "• Clears renamed titles and summaries",
      "• Restores your custom preset files from first install",
      "• Removes custom presets you added after install",
      "",
      "Does not disconnect VPN or change live Nord settings — only this preset list.",
    ].join("\n");
  }

  function ensurePresetFactoryResetButton(panelId, anchorEl, categoryLabel) {
    if (!anchorEl || anchorEl.querySelector(`[data-preset-reset-panel="${panelId}"]`)) return;
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "btn sm preset-factory-reset";
    btn.dataset.presetResetPanel = panelId;
    btn.dataset.confirm = "1";
    btn.dataset.confirmMessage = presetFactoryResetMessage(panelId, categoryLabel);
    btn.textContent = "Reset to factory";
    btn.title = "Unhide presets, clear renames, restore custom preset files from install";
    anchorEl.appendChild(btn);
  }

  function initPresetPanelResets() {
    Object.entries(DASHBOARD_PRESET_PANELS).forEach(([panelId, panel]) => {
      const countEl = $(panel.count);
      if (!countEl) return;
      const head = countEl.closest(".hero-card-head, .dash-subhead-row");
      ensurePresetFactoryResetButton(panelId, head, panel.category);
    });
  }

  async function resetPresetsFactory(panelId) {
    const res = await doAction({ action: "preset_reset_factory", panel: panelId }, "Reset presets");
    if (res.ok) {
      toast(res.note || "Presets reset to factory", true);
      await loadState(true);
    }
    return res;
  }

  function parseMeshPeers(raw) {
    if (!raw || raw === "—") return { device: [], peers: [] };
    const device = [];
    const peers = [];
    let section = "";
    let current = null;
    raw.split("\n").forEach((line) => {
      const trimmed = line.trim();
      if (!trimmed) return;
      if (/^this device/i.test(trimmed)) { section = "device"; return; }
      if (/^local peers/i.test(trimmed)) { section = "peers"; return; }
      if (section === "peers" && /\.nord\b/i.test(trimmed) && !trimmed.includes(":")) {
        if (current) peers.push(current);
        current = { name: trimmed, props: {} };
        return;
      }
      const m = trimmed.match(/^([^:]+):\s*(.*)$/);
      if (m) {
        const k = m[1].trim();
        const v = m[2].trim();
        if (section === "device") device.push({ k, v });
        else if (current) current.props[k] = v;
      }
    });
    if (current) peers.push(current);
    return { device, peers };
  }

  function renderMeshPeers(raw) {
    renderMeshPeersGrid($("meshPeers"), raw, { interactive: true });
  }

  function renderQuickStart(data) {
    const box = $("quickStartCards");
    if (!box) return;
    const presets = data?.presets || [];
    const byId = {};
    presets.forEach((p) => { byId[p.id] = p; });
    box.innerHTML = QUICK_START.map((q) => {
      const p = byId[q.preset];
      const label = p?.label || q.label || q.preset;
      const desc = p?.summary || q.summary || "";
      return `<button type="button" class="quick-card" data-preset="${esc(q.preset)}" data-confirm="1" data-confirm-message="Apply “${esc(byId[q.preset]?.label || label)}”? This may change VPN, DNS, or firewall settings." title="${esc(desc)}">
        <span class="quick-card-icon">${q.icon}</span>
        <span><strong>${esc(label)}</strong><span>${esc(desc)}</span></span>
      </button>`;
    }).join("");
    box.querySelectorAll(".quick-card").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.dataset.preset;
        doAction({ action: "preset", preset: id }, byId[id]?.label || id);
      });
    });
  }

  function initViewJumps() {
    bindViewJumps(document);
  }

  function isNordDnsSettingOn(settings) {
    const raw = String(settings?.DNS ?? settings?.dns ?? "").trim();
    if (!raw) return false;
    const low = raw.toLowerCase();
    if (low === "disabled" || low === "off" || low === "no") return false;
    if (low === "enabled" || low === "on" || low === "yes") return true;
    return /\d/.test(raw);
  }

  function nordDnsDisplay(settings) {
    const raw = String(settings?.DNS ?? settings?.dns ?? "").trim();
    if (!raw) return "";
    const low = raw.toLowerCase();
    if (low === "enabled" || low === "on" || low === "yes") return "On";
    if (low === "disabled" || low === "off" || low === "no") return "Off";
    return raw;
  }

  function uniqDns(list) {
    const seen = new Set();
    return (list || []).filter((ip) => {
      const val = String(ip ?? "").trim();
      if (!val || seen.has(val)) return false;
      seen.add(val);
      return true;
    });
  }

  function renderTopbarDnsChip({ label, val, tone, title }) {
    return `<span class="topbar-dns${tone ? ` topbar-dns-${tone}` : ""}" title="${esc(title || "")}"><span class="topbar-dns-lbl">${esc(label)}</span><span class="topbar-dns-val">${esc(val)}</span></span>`;
  }

  function renderTopbarDnsBar(data) {
    const strip = $("topbarDnsBar");
    if (!strip) return;
    const connected = !!(data?.status?.connected ?? data?.nordvpn?.connected);
    const sd = data?.smart_dns || {};
    const settings = data?.settings || {};
    const liveDns = uniqDns(sd.dns_servers || []);
    const systemDns = uniqDns(sd.system_dns?.servers || []);
    const systemSrc = sd.system_dns?.source || sd.system_dns?.device || "";
    const smartActive = !!sd.active;
    const nordOn = connected && isNordDnsSettingOn(settings);
    const chips = [];

    if (connected) {
      if (nordOn) {
        chips.push({
          label: "Nord DNS",
          val: nordDnsDisplay(settings) || "On",
          tone: "nord",
          title: "NordVPN DNS is enabled while VPN is connected",
        });
      } else {
        chips.push({
          label: "Nord DNS",
          val: "Off",
          tone: "nord-off",
          title: "NordVPN DNS is disabled — using system resolver below",
        });
      }
    }

    if (smartActive && liveDns.length) {
      chips.push({
        label: "Smart DNS",
        val: liveDns.join(", "),
        tone: "smart",
        title: "Nord Smart DNS is active on this WiFi interface",
      });
    } else if (systemDns.length) {
      chips.push({
        label: systemSrc ? `DNS · ${systemSrc}` : "System DNS",
        val: systemDns.join(", "),
        tone: "system",
        title: `Resolver on ${systemSrc || "this device"} (router, ISP, or manual — from resolvectl)`,
      });
    } else if (liveDns.length) {
      chips.push({
        label: "DNS",
        val: liveDns.join(", "),
        tone: "live",
        title: "Current DNS servers on this device",
      });
    } else if (sd.primary || sd.secondary) {
      chips.push({
        label: "Smart DNS",
        val: uniqDns([sd.primary, sd.secondary].filter(Boolean)).join(", "),
        tone: "config",
        title: "Configured Smart DNS servers (not active on this link)",
      });
    }

    if (!chips.length) {
      strip.hidden = true;
      strip.innerHTML = "";
      strip.className = "topbar-dns-strip";
      return;
    }
    strip.hidden = false;
    strip.className = "topbar-dns-strip";
    strip.innerHTML = chips.map((chip) => renderTopbarDnsChip(chip)).join("");
  }

  function renderTopbarIpBar(data) {
    renderTopbarDnsBar(data);
    const bar = $("topbarIpBar");
    if (!bar) return;
    const info = data?.ip_info || {};
    let chain = Array.isArray(info.chain) ? info.chain.filter((x) => x && x.ip) : [];
    const routeChain = chain.filter((x) => x.role !== "mesh");
    const meshChain = chain.filter((x) => x.role === "mesh");
    if (!routeChain.length) {
      const fallback = info.external_ip || (info.connected ? null : info.routed_ip) || data?.smart_dns?.public_ip;
      if (fallback) routeChain.push({ role: "home", label: "Home", ip: fallback });
    }
    if (!routeChain.length && !meshChain.length) {
      bar.hidden = true;
      bar.innerHTML = "";
      return;
    }
    bar.hidden = false;
    const titleParts = [];
    if (routeChain.some((x) => x.role === "home" || x.role === "ext")) {
      titleParts.push("Home/Public = ISP address for this network (auto-learned or trusted zone)");
    }
    if (routeChain.some((x) => x.role === "vpn")) titleParts.push("VPN = Nord exit address");
    if (meshChain.length) titleParts.push("Mesh = Nord Meshnet address on this device");
    bar.title = info.note || titleParts.join(" · ") || "Public and Nord addresses for this device";
    const routeHtml = routeChain.map((item, idx) => {
      const sep = idx ? '<span class="topbar-ip-sep" aria-hidden="true">→</span>' : "";
      const vpnCls = item.role === "vpn" ? " topbar-ip-vpn" : "";
      return `${sep}<span class="topbar-ip-item${vpnCls}"><span class="topbar-ip-lbl">${esc(item.label || "IP")}</span><span class="topbar-ip-val">${esc(item.ip)}</span></span>`;
    }).join("");
    const meshHtml = meshChain.map((item) =>
      `<span class="topbar-ip-dot" aria-hidden="true">·</span><span class="topbar-ip-item topbar-ip-mesh"><span class="topbar-ip-lbl">${esc(item.label || "Mesh")}</span><span class="topbar-ip-val">${esc(item.ip)}</span></span>`,
    ).join("");
    bar.innerHTML = routeHtml + meshHtml;
  }

  function pctLevel(pct, warn = 80, hot = 92) {
    if (pct == null || Number.isNaN(Number(pct))) return "";
    if (Number(pct) >= hot) return "hot";
    if (Number(pct) >= warn) return "warn";
    return "ok";
  }

  function formatHostUptime(sec) {
    if (sec == null || !Number.isFinite(Number(sec))) return "Up —";
    const s = Math.max(0, Math.floor(Number(sec)));
    const d = Math.floor(s / 86400);
    const h = Math.floor((s % 86400) / 3600);
    const m = Math.floor((s % 3600) / 60);
    if (d > 0) return `Up ${d}d ${h}h`;
    if (h > 0) return `Up ${h}h ${m}m`;
    return `Up ${m}m`;
  }

  function applySysChip(el, baseClass, level, text, title) {
    if (!el) return;
    const txt = el.querySelector(".sys-chip-text");
    if (txt) txt.textContent = text;
    else el.textContent = text;
    if (title) el.title = title;
    el.className = level ? `${baseClass} ${level}` : baseClass;
  }

  function tempLevel(c) {
    if (c == null || Number.isNaN(c)) return "";
    if (c >= 90) return "hot";
    if (c >= 75) return "warn";
    return "ok";
  }

  function worstLevel(...levels) {
    const rank = { hot: 3, warn: 2, ok: 1 };
    return levels.reduce((best, lv) => ((rank[lv] || 0) > (rank[best] || 0) ? lv : best), "");
  }

  function topbarDiskClipped() {
    const strip = $("topbarSysStrip");
    const disk = $("topbarDisk");
    if (!strip || !disk || disk.hidden) return false;
    const sr = strip.getBoundingClientRect();
    const dr = disk.getBoundingClientRect();
    return dr.right > sr.right + 0.5 || strip.scrollWidth > strip.clientWidth + 2;
  }

  function syncTopbarChipFit() {
    const strip = $("topbarSysStrip");
    const uptime = $("topbarUptime");
    if (!strip) return;
    if (uptime) uptime.hidden = false;
    strip.classList.remove("topbar-sys-strip--fit");
    if (topbarDiskClipped()) strip.classList.add("topbar-sys-strip--fit");
    if (topbarDiskClipped() && uptime) uptime.hidden = true;
  }

  function initTopbarStackHeight() {
    const stack = $("topbarStack");
    if (!stack || stack.dataset.topbarHeightInit) return;
    stack.dataset.topbarHeightInit = "1";
    const sync = () => {
      const h = Math.ceil(stack.getBoundingClientRect().height);
      if (h > 0) document.documentElement.style.setProperty("--topbar-stack-h", `${h}px`);
      syncTopbarChipFit();
    };
    sync();
    if (typeof ResizeObserver !== "undefined") {
      const ro = new ResizeObserver(sync);
      ro.observe(stack);
      const strip = $("topbarSysStrip");
      if (strip) ro.observe(strip);
    } else {
      window.addEventListener("resize", sync);
    }
  }

  function renderTopbarSysStrip(data) {
    if (!data?.ok) return;
    const load = data.load || {};
    const mem = data.memory || {};
    const disk = data.disk || {};
    const ufw = data.ufw || {};
    const ui = data.ui_service || {};
    const cores = load.cores || 1;
    const load1 = Number(load["1m"] ?? 0);
    const cpuTemp = data.cpu_temp_c;
    const cpuLevel = worstLevel(
      pctLevel(load.pct ?? (cores ? (100 * load1) / cores : null), 75, 100),
      tempLevel(cpuTemp),
    );
    const cpuText = cpuTemp != null
      ? `CPU ${load1.toFixed(2)} · ${cpuTemp}°C`
      : `CPU ${load1.toFixed(2)}`;
    const cpuTitle = [
      `Load 1m ${load1} · 5m ${load["5m"]} · 15m ${load["15m"]} · ${cores} cores`,
      cpuTemp != null ? `${cpuTemp}°C` : null,
    ].filter(Boolean).join(" · ");
    applySysChip(
      $("topbarLoad"),
      "sys-chip sys-metric sys-load sys-chip-spark",
      cpuLevel,
      cpuText,
      cpuTitle,
    );
    const memPct = mem.used_pct;
    applySysChip(
      $("topbarMem"),
      "sys-chip sys-metric sys-mem sys-chip-spark",
      pctLevel(memPct, 78, 90),
      memPct != null ? `RAM ${memPct}%` : "RAM —",
      memPct != null
        ? `RAM ${Math.round((mem.used_kb || 0) / 1024 / 1024)} / ${Math.round((mem.total_kb || 0) / 1024 / 1024)} GiB`
        : "Memory usage",
    );
    const swap = data.swap || {};
    const swapPct = swap.used_pct;
    const swapEl = $("topbarSwap");
    if (swapEl) {
      if ((swap.total_kb || 0) > 0) {
        swapEl.hidden = false;
        applySysChip(
          swapEl,
          "sys-chip sys-metric sys-swap",
          pctLevel(swapPct, 50, 75),
          swapPct != null ? `Swap ${swapPct}%` : "Swap —",
          swapPct != null
            ? `Swap ${Math.round((swap.used_kb || 0) / 1024 / 1024)} / ${Math.round((swap.total_kb || 0) / 1024 / 1024)} GiB`
            : "Swap usage",
        );
      } else {
        swapEl.hidden = true;
      }
    }
    const diskPct = disk.used_pct;
    applySysChip(
      $("topbarDisk"),
      "sys-chip sys-metric sys-disk sys-chip-spark",
      pctLevel(diskPct, 82, 92),
      diskPct != null ? `Disk ${diskPct}%` : "Disk —",
      diskPct != null ? `${disk.free_gb} GiB free on ${disk.mount || "/"}` : "Root disk usage",
    );
    const ufwEl = $("topbarUfw");
    if (ufwEl) {
      ufwEl.textContent = ufw.label || (ufw.enabled ? "UFW on" : ufw.installed === false ? "UFW n/a" : "UFW off");
      ufwEl.className = `sys-chip sys-ufw jump-link ${ufw.installed === false ? "na" : ufw.enabled ? "on" : "off"}`;
      ufwEl.title = ufw.enabled
        ? `Linux UFW active${ufw.rule_count ? ` · ${ufw.rule_count} rules` : ""}`
        : "Linux UFW — open firewall editor";
    }
    applySysChip(
      $("topbarUptime"),
      "sys-chip sys-uptime",
      "",
      formatHostUptime(data.uptime_sec),
      data.uptime_sec != null ? `System uptime ${formatHostUptime(data.uptime_sec)}` : "System uptime",
    );
    const hostname = data.hostname || "";
    const clock = $("topbarClock");
    if (clock && hostname) clock.dataset.hostname = hostname;
    applySysChip(
      $("topbarUiSvc"),
      "sys-chip sys-ui",
      ui.active ? "on" : ui.active === false ? "off" : "",
      ui.label || (ui.active ? "UI on" : "UI off"),
      ui.active ? "nordctl web UI is running" : "nordctl web UI is not active",
    );
    recordSysHist(data);
    syncTopbarChipFit();
  }

  function tickTopbarClock() {
    const timeEl = $("topbarClockTime");
    const dayEl = $("topbarClockDay");
    const dateEl = $("topbarClockDate");
    const chip = $("topbarClock");
    if (!timeEl && !chip) return;
    const now = new Date();
    const time = formatLocaleTime(now, false);
    const day = formatLocaleWeekday(now);
    const date = now.toLocaleDateString([], { day: "numeric", month: "short" });
    if (timeEl) timeEl.textContent = time;
    else if (chip) chip.textContent = time;
    if (dayEl) dayEl.textContent = day;
    if (dateEl) dateEl.textContent = date;
    if (chip) {
      const host = chip.dataset.hostname || "";
      chip.title = [
        host,
        now.toLocaleString(undefined, {
          weekday: "long",
          day: "numeric",
          month: "long",
          year: "numeric",
          ...(uiPrefs.clock_format === "12h" ? {} : { hour12: false }),
        }),
      ].filter(Boolean).join(" · ");
    }
  }

  async function loadHostStatus(force) {
    try {
      const data = force
        ? await api("/api/host/status")
        : await apiCached("/api/host/status", {}, CACHE_TTL.host);
      renderTopbarSysStrip(data);
    } catch (_) {
      /* keep last chip values */
    }
  }

  function startTopbarSysTimers() {
    tickTopbarClock();
    setInterval(tickTopbarClock, 1000);
    void loadHostStatus(false);
    setInterval(() => loadHostStatus(false), 15000);
  }

  function renderConnectionCore(data) {
    renderTopbarIpBar(data);
    if (getActiveView() === "advanced" && (localStorage.getItem("nordctl_adv_tab") === "traffic-speed" || hubTab === "traffic-speed")) {
      syncSpeedLabContext(data);
    }
    const connected = !!(data?.status?.connected ?? data?.nordvpn?.connected);
    $("connPulse")?.classList.toggle("on", connected);
    $("viewDashboard")?.classList.toggle("vpn-connected", connected);
    renderTopbarVpnBadge(connected);
    renderTopbarNordFw(data);
    syncLiveBwRoute();
    renderUsageMode(data);

    if (!data?.ok) {
      $("statusBox").innerHTML = `<div class="val off span3">${esc(data?.error || "Unavailable")}</div>`;
      return;
    }

    if (!nordInstalled(data)) {
      renderNoNordStatus(data);
      setVpnControlsEnabled(false, "Install NordVPN from Setup first");
      return;
    }

    const st = data.status || {};
    const set = data.settings || {};
    const cells = connected
      ? [statCell("Server", esc(st.Server || "—")), statCell("IP", esc(st.IP || "—")), statCell("Country", esc(st.Country || "—"))]
      : [`<div class="lbl">Status</div><div class="val off span3">Disconnected</div>`];
    const meshOn = String(set.Meshnet || "").includes("enabled");
    cells.push(nordToggleStatRow("Meshnet", meshOn, "meshnet"));
    cells.push(statCell("Auto-connect", esc(set["Auto-connect"] || "—")));
    const fwOn = String(set.Firewall || "").toLowerCase().includes("enabled");
    cells.push(nordToggleStatRow("Firewall", fwOn, "firewall"));
    const sd = data.smart_dns || {};
    if (sd.active) {
      cells.push(`<div class="lbl">Smart DNS</div><div class="val on span3">${esc((sd.dns_servers || []).join(", "))}</div>`);
      if (sd.public_ip) cells.push(`<div class="lbl">Public IP</div><div class="val span3">${esc(sd.public_ip)}</div>`);
    }
    $("statusBox").innerHTML = cells.join("");
    bindNordToggleRows($("statusBox"));
    renderQuickStart(data);
    setVpnControlsEnabled(true);
    if (getActiveView() === "dashboard" && dashTab === "meshnet") {
      loadMeshnetPage(false);
    }
  }

  function renderDemoBanner(data) {
    const el = $("demoBanner");
    if (!el) return;
    const on = !!(data?.demo_mode || data?.usage?.demo_mode);
    el.classList.toggle("hidden", !on);
  }

  function referralPreviewForced() {
    try {
      return new URLSearchParams(window.location.search).get("referral_preview") === "1";
    } catch (_e) {
      return false;
    }
  }

  function renderReferralBanner(data) {
    const el = $("referralBanner");
    const link = $("referralBannerLink");
    const preview = $("referralBannerPreview");
    if (!el) return;
    const usage = data?.usage || {};
    const ref = usage.referral || {};
    const previewOn = referralPreviewForced();
    const url = String(ref.url || link?.getAttribute("href") || "").trim();
    const refEnabled = ref.enabled !== false;
    const enabled = !!url && (refEnabled || previewOn);
    const loggedIn = !!(data?.nordvpn?.logged_in ?? usage.logged_in);
    const demo = !!(data?.demo_mode || usage.demo_mode);
    const show = enabled && !demo && (previewOn || !loggedIn);
    el.classList.toggle("hidden", !show);
    if (link && url) link.href = url;
    if (preview) preview.classList.toggle("hidden", !previewOn);
  }

  function renderPresetVerification(verification) {
    const panel = $("presetVerifyPanel");
    if (!panel) return;
    if (!verification || !verification.checks?.length) {
      panel.classList.add("hidden");
      panel.innerHTML = "";
      return;
    }
    panel.classList.remove("hidden");
    const ok = verification.ok;
    const head = ok ? "Post-apply verification passed" : "Post-apply verification — review failures";
    panel.innerHTML = `<strong>${esc(head)}</strong> <span class="badge ${ok ? "on" : "warn"}">${esc(verification.summary || "")}</span>
      <ul>${(verification.checks || []).map((c) =>
        `<li class="${c.ok ? "verify-ok" : "verify-fail"}"><strong>${esc(c.name)}</strong>: ${esc(c.detail || "")}${c.hint ? ` <span class="muted">— ${esc(c.hint)}</span>` : ""}</li>`
      ).join("")}</ul>`;
  }

  async function loadCommunityPresets() {
    const grid = $("communityPresetsGrid");
    const badge = $("communityPresetsCount");
    if (!grid) return;
    try {
      const data = await api("/api/presets/community");
      const items = data.presets || [];
      if (badge) badge.textContent = String(items.length);
      grid.innerHTML = items.length
        ? items.map((p) =>
            `<div class="preset community-preset">
              <strong>${esc(p.label || p.id)}</strong>
              <p class="muted">${esc(p.summary || "")}</p>
              <div class="actions">
                ${p.user_copy ? `<span class="badge on">In My presets</span>` : ""}
                <button type="button" class="btn sm primary" data-community-save="${esc(p.id)}" ${p.user_copy ? "disabled" : ""} title="Copy into your My presets folder">Save to My presets</button>
                <button type="button" class="btn sm" data-community-share="${esc(p.id)}" title="Copy YAML to share">Share</button>
                <button type="button" class="btn sm" data-community-preview="${esc(p.id)}" ${p.installed ? "" : "disabled"} title="Preview applies only after import">Preview</button>
                <button type="button" class="btn sm" data-community-apply="${esc(p.id)}" ${p.installed ? "" : "disabled"}>Run</button>
              </div>
            </div>`
          ).join("")
        : `<p class="muted">No community presets found.</p>`;
      grid.querySelectorAll("[data-community-save]").forEach((btn) => {
        btn.addEventListener("click", () =>
          savePresetToMyPresets(btn.getAttribute("data-community-save"))
        );
      });
      grid.querySelectorAll("[data-community-share]").forEach((btn) => {
        btn.addEventListener("click", () =>
          sharePreset({ id: btn.getAttribute("data-community-share"), label: btn.closest(".community-preset")?.querySelector("strong")?.textContent })
        );
      });
      grid.querySelectorAll("[data-community-preview]").forEach((btn) => {
        btn.addEventListener("click", () =>
          doAction({ action: "preset_dry_run", preset: btn.getAttribute("data-community-preview") }, "Preview preset")
            .then((r) => {
              if (r.ok && r.steps) {
                showNotice(
                  (r.steps || []).map((s) => `${s.n}. ${s.text}`).join("\n"),
                  { ok: true, title: `Dry run: ${r.label || r.preset}` }
                );
              }
            })
        );
      });
      grid.querySelectorAll("[data-community-apply]").forEach((btn) => {
        btn.addEventListener("click", () =>
          doAction({ action: "preset", preset: btn.getAttribute("data-community-apply") }, "Community preset")
        );
      });
    } catch (e) {
      if (grid) grid.innerHTML = `<p class="muted">${esc(formatFetchError(e, "Community presets"))}</p>`;
    }
  }

  function renderState(data) {
    lastState = data;
    maybeAnnounceBaseline(data);
    renderDemoBanner(data);
    renderReferralBanner(data);
    renderConnectionCore(data);
    try {
      if (data?.features) {
        applyModuleNav(data.features);
        applySettingsNav(installProfile(data));
        applyNordUiVisibility(data);
        maybeShowSetupWizard(data.features);
      }
      if (data?.doctor) renderDoctor(data.doctor);
      countries = (Array.isArray(data?.countries) && data.countries.length) ? data.countries : countries;
      renderDashboardPresetPanels(data);
      renderMyPresets(data);
      renderCreatePresetsList(data);
      if (!data?.ok || !nordInstalled(data)) {
        renderBaselinePanel(data);
        renderAutomateGuide(data);
        applyButtonTitles();
        return;
      }
      populateCountryOptions(null, $("connectCountrySelect"));
      fillCountryDropdowns();
      renderSmartDnsHub(data);
      renderFirewallPanel(data);
      renderBaselinePanel(data);
      renderFactoryResetPanel(data);
      renderAutomatePanels(data);
      renderAutomateGuide(data);
      renderServicePanel(data?.services);
      renderPrivileges(data?.privileges);
      renderLocationSettings(data);
      syncHomeLanUi(data);
      if (!countries.length) loadNordRoutingPanel(true, false);
      applyButtonTitles();
    } catch (e) {
      console.error("renderState panels", e);
      applyButtonTitles();
    }
  }

  function renderBaselinePanel(data) {
    const bl = data?.baseline || {};
    mountBaselineSafetyNotice("baselineSafetyNotice", data);
    const comps = bl.components || [];
    const badge = $("baselineBadge");
    if (badge) {
      badge.textContent = bl.exists ? "Saved" : "Missing";
      badge.className = "badge " + (bl.exists ? "on" : "warn");
    }
    if ($("baselineMetrics")) {
      $("baselineMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Baseline</div><div class="val ${bl.exists ? "on" : "off"}">${bl.exists ? "Saved" : "Missing"}</div><div class="sub">Install snapshot</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Created</div><div class="val">${esc(String(bl.created || "—").slice(0, 10))}</div><div class="sub">First-run capture</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Components</div><div class="val">${comps.length || "—"}</div><div class="sub">Restored on rollback</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Scope</div><div class="val on">Full</div><div class="sub">Config, DNS, Nord, IPv6</div></div>`,
      ].join("");
    }
    const compGrid = $("baselineComponents");
    if (compGrid) {
      compGrid.innerHTML = comps.length
        ? comps.map((c) => `<article class="tools-component-card"><strong>${esc(String(c))}</strong><span class="tools-component-sub">Included in baseline</span></article>`).join("")
        : `<div class="page-empty"><strong>No baseline components listed</strong>Create a baseline with the button below or run <code>nordctl init</code>.</div>`;
    }
    const path = $("baselinePath");
    if (path) {
      path.textContent = bl.exists
        ? (bl.message || bl.path || "")
        : "No baseline yet — click Create baseline now or run nordctl init";
    }
  }

  function renderFirewallPanel(data) {
    const fw = data?.firewall || {};
    const nord = fw.nord || {};
    const fwBadge = $("nordFwBadge");
    if (fwBadge) {
      fwBadge.textContent = nord.firewall ? "On" : "Off";
      fwBadge.className = "badge " + (nord.firewall ? "on" : "off");
    }
    const markEl = $("nordFwMark");
    if (markEl) {
      const mark = nord.firewall_mark || "—";
      markEl.textContent = mark;
      markEl.className = "val" + (mark && mark !== "—" ? "" : " muted");
    }
    const killBadge = $("killSwitchBadge");
    if (killBadge) {
      killBadge.textContent = nord.killswitch ? "On" : "Off";
      killBadge.className = "badge " + (nord.killswitch ? "on" : "off");
    }
    const fwNotes = $("firewallNotes");
    if (fwNotes) {
      fwNotes.innerHTML = (fw.notes || [])
        .filter((n) => !n.includes("Control → UFW"))
        .filter((n) => !/kill switch/i.test(n) || /firewall/i.test(n))
        .map((n) => `<li>${esc(n)}</li>`)
        .join("");
    }
    const ksNotes = $("killSwitchNotes");
    if (ksNotes) {
      const notes = (fw.notes || []).filter((n) => !n.includes("Control → UFW"));
      const ksSpecific = notes.filter((n) => /kill switch/i.test(n));
      ksNotes.innerHTML = (ksSpecific.length ? ksSpecific : notes.slice(0, 2))
        .map((n) => `<li>${esc(n)}</li>`)
        .join("");
    }
  }

  function renderSmartDnsHub(data) {
    const sd = data?.smart_dns || {};
    const dns = data?.firewall?.dns || {};
    const nord = data?.firewall?.nord || {};
    const box = $("smartDnsBox");
    if (!box) return;
    const connected = !!(data?.firewall?.connected ?? data?.status?.connected ?? lastSwitchesData?.connected);
    const conn = lastSwitchesData?.connection || {};
    const country = conn.country && conn.country !== "—" ? conn.country : (data?.status?.Country || data?.status?.country || "");
    const nordSw = switchDefById("nord-dns");
    const smartSw = switchDefById("smart-dns-wifi");
    const nordCur = nordSw.current || { on: !!nord.nord_dns, display: nord.nord_dns ? "On" : "Off" };
    const smartCur = smartSw.current || {
      on: !!(dns.smart_active ?? sd.active),
      display: (dns.smart_active ?? sd.active) ? "On" : "Off",
    };
    const pubLabel = sd.public_ip_note ? "Home ISP (allowlist)" : "Public IP";
    const toggleCards = [
      nordDnsToggleCard(nordSw, nordCur, data),
      nordDnsToggleCard(smartSw, smartCur, data),
    ].join("");
    const infoRows = [
      statCell("VPN tunnel", connected ? (country ? `Connected · ${country}` : "Connected") : "Not connected", connected ? "on" : ""),
      statCell("WiFi DNS now", esc((dns.wifi_dns || sd.dns_servers || []).join(", ") || "—")),
      statCell(pubLabel, esc(sd.public_ip || "—")),
      statCell("Smart DNS IPs (config)", esc([sd.primary || dns.primary, sd.secondary || dns.secondary].filter(Boolean).join(", ") || "— set below")),
    ];
    if (sd.public_ip_routed && sd.public_ip_routed !== sd.public_ip) {
      infoRows.push(statCell("VPN exit IP", esc(sd.public_ip_routed), "warn"));
    }
    if (sd.public_ip_note) {
      infoRows.push(`<div class="lbl span3 help-text nord-dns-allowlist-note">${esc(sd.public_ip_note)}</div>`);
    }
    box.innerHTML = `${baselineSafetyNoticeHtml(data?.baseline || lastState?.baseline)}${localNetworkNoticeHtml({ scope: "wifi_dns" })}<div class="nord-dns-toggle-grid">${toggleCards}</div><div class="nord-dns-info-grid stat-grid">${infoRows.join("")}</div>`;
    bindViewJumps(box);
    bindNordToggleRows(box);
    window._lastPublicIp = sd.public_ip;
    const pri = $("dnsPrimary");
    const sec = $("dnsSecondary");
    if (pri && document.activeElement !== pri) pri.value = sd.primary || dns.primary || "";
    if (sec && document.activeElement !== sec) sec.value = sd.secondary || dns.secondary || "";
    const resolve = $("dnsResolve");
    if (resolve) {
      const snippet = dns.resolve_snippet || "";
      resolve.textContent = snippet || "";
      resolve.classList.toggle("hidden", !snippet);
    }
  }

  const FAV_COUNTRY_EMOJI = {
    United_States: "🇺🇸",
    United_Kingdom: "🇬🇧",
    Germany: "🇩🇪",
    France: "🇫🇷",
    Spain: "🇪🇸",
    Netherlands: "🇳🇱",
    Italy: "🇮🇹",
    Canada: "🇨🇦",
    Japan: "🇯🇵",
    Australia: "🇦🇺",
  };

  function favoriteEmoji(item) {
    if (item.kind === "city") {
      const country = String(item.value || "").split(/\s+/)[0] || "";
      const key = country.replace(/ /g, "_");
      return FAV_COUNTRY_EMOJI[key] || "🏙️";
    }
    return FAV_COUNTRY_EMOJI[item.value] || "🌐";
  }

  function favoriteConnectTarget(item) {
    if (item.kind === "country") return String(item.value || "").replace(/_/g, " ");
    return item.value;
  }

  function _safePresetId(s) {
    return String(s || "")
      .toLowerCase()
      .replace(/[^\w]+/g, "-")
      .replace(/^-+|-+$/g, "")
      .slice(0, 48) || "shared-preset";
  }

  function favoritePresetYaml(item, label, target) {
    const key = favoriteItemKey(item);
    const id = _safePresetId(`fav-${key}`);
    const safeLabel = String(label || "").trim() || (item.kind === "country" ? countryLabel(item.value) : String(item.value || "").trim()) || "Favorite";
    const summary = `Connect to ${safeLabel}`;
    const body = [
      `id: ${id}`,
      `label: ${safeLabel}`,
      `category: Favorites`,
      `summary: ${summary}`,
      `steps:`,
      `  - action: nordvpn_connect`,
      `    target: ${JSON.stringify(String(target || "").trim())}`,
      ``,
    ].join("\n");
    return { id, label: safeLabel, summary, content: body, filename: `${id}.yaml` };
  }

  async function shareFavoriteAsPreset(item, prof) {
    try {
      const label = favoriteDisplayLabel(item, prof);
      const target = favoriteConnectTarget(item);
      const preset = favoritePresetYaml(item, label, target);
      try {
        await navigator.clipboard.writeText(preset.content);
        toast(`Copied “${preset.label}” YAML — paste to share`, true);
      } catch (_) {
        showNotice("Copy the YAML below to share this favorite as a preset.", {
          title: `Share: ${preset.label}`,
          copyText: preset.content,
          ok: true,
        });
      }
      downloadTextFile(preset.filename, preset.content);
    } catch (e) {
      toast(formatFetchError(e, "Share favorite"), false);
    }
  }

  async function saveFavoriteToMyPresets(item, prof) {
    const label = favoriteDisplayLabel(item, prof);
    const target = favoriteConnectTarget(item);
    const preset = favoritePresetYaml(item, label, target);
    return savePresetYamlToMyPresets(preset.content, preset.label);
  }

  function placeFieldPresetYaml(field) {
    const fid = String(field.id || "").trim();
    const label = String(field.label || fid).trim();
    const id = _safePresetId(`place-${fid}`);
    if (field.type === "country" || fid === "connect_country") {
      return {
        label,
        content: [
          `id: ${id}`,
          `label: ${label}`,
          `category: My places`,
          `summary: Connect using ${label} saved in My places`,
          `requires:`,
          `  - connect_country`,
          `steps:`,
          `  - action: nordvpn_connect`,
          `    target: "{connect_country}"`,
          ``,
        ].join("\n"),
      };
    }
    if (field.type === "city" || fid === "connect_city") {
      return {
        label,
        content: [
          `id: ${id}`,
          `label: ${label}`,
          `category: My places`,
          `summary: Connect using ${label} saved in My places`,
          `requires:`,
          `  - connect_city`,
          `steps:`,
          `  - action: nordvpn_connect`,
          `    target: "{connect_city}"`,
          ``,
        ].join("\n"),
      };
    }
    return null;
  }

  async function savePlaceAsPreset(field) {
    if (!field?.set) return toast("Save the place value first, then Save as preset", false);
    const preset = placeFieldPresetYaml(field);
    if (!preset) return toast("This place cannot be saved as a preset yet", false);
    return savePresetYamlToMyPresets(preset.content, preset.label);
  }

  function favoriteItemKey(item) {
    let kind = item.kind || "country";
    const val = String(item.value || "").trim();
    if (kind === "country" && val.includes(" ")) kind = "city";
    return `${kind}:${val}`;
  }

  function favoriteDisplayLabel(item, prof) {
    const key = favoriteItemKey(item);
    const ov = prof?.favorite_overrides?.[key];
    if (ov?.label) return ov.label;
    if (item.kind === "country") return countryLabel(item.value);
    return item.value;
  }

  function renderFavorites(prof) {
    const fl = $("favList");
    const hiddenPanel = $("favHiddenPanel");
    if (!fl) return;
    if (skipRenderWhileEditing(fl)) return;
    const fav = prof?.favorites || {};
    const hiddenKeys = new Set(prof?.hidden_favorite_keys || []);
    const items = [];
    (fav.countries || []).forEach((c) => {
      items.push({ kind: "country", value: c, sub: "Country — one-tap connect" });
    });
    (fav.servers || []).forEach((s) => {
      items.push({ kind: "city", value: s, sub: "City server — one-tap connect" });
    });
    const visible = items.filter((item) => !hiddenKeys.has(favoriteItemKey(item)));
    const hiddenItems = prof?.hidden_favorites || [];
    if (!visible.length && !hiddenItems.length) {
      fl.innerHTML = '<p class="muted">No favorites yet — pick a country (and optional city) above, then click ★ Favorite.</p>';
      renderHiddenPanel(hiddenPanel, "", "");
      return;
    }
    if (!visible.length) {
      fl.innerHTML = '<p class="muted help-text">All favorites are hidden — expand Hidden below to show them again.</p>';
    } else {
      fl.innerHTML = visible.map((item) => {
        const label = favoriteDisplayLabel(item, prof);
        const target = favoriteConnectTarget(item);
        const fkey = favoriteItemKey(item);
        return `<div class="sec-profile-card fav-card" data-fav-key="${esc(fkey)}">
          <h3>${esc(favoriteEmoji(item))} <span class="fav-label-display">${esc(label)}</span></h3>
          <p>${esc(item.sub)}</p>
          <div class="wf-inline-edit hidden fav-inline-edit" data-fav-edit-panel="${esc(fkey)}">
            <p class="help-text wf-rename-note">Optional nickname on this card — does not change which server NordVPN connects to.</p>
            <label class="wf-inline-field">Display name <input type="text" class="fav-meta-label" value="${esc(label)}" /></label>
            <div class="actions">
              <button type="button" class="btn sm primary" data-fav-save-meta="${esc(item.kind)}" data-fav-value="${esc(item.value)}">Save name</button>
              <button type="button" class="btn sm" data-fav-cancel-meta="${esc(fkey)}">Cancel</button>
            </div>
          </div>
          <div class="wf-manage-actions">
            <p class="help-text wf-manage-help">Manage this favorite:</p>
            <div class="wf-manage-row">
              <button type="button" class="btn sm primary fav-connect" data-target="${esc(target)}" data-confirm="1" data-confirm-message="Connect to ${esc(label)}?">Connect</button>
              <button type="button" class="btn sm" data-fav-edit="${esc(fkey)}" title="Change display name on this card">Edit name</button>
              <button type="button" class="btn sm primary" data-fav-save-preset="${esc(fkey)}" title="Save as a preset in My presets">Save to My presets</button>
              <button type="button" class="btn sm" data-fav-share="${esc(fkey)}" title="Copy + download a preset YAML for this favorite">Share</button>
              <button type="button" class="btn sm" data-fav-hide="${esc(item.kind)}" data-fav-value="${esc(item.value)}" title="Hide from list without deleting">Hide</button>
              <button type="button" class="btn sm danger fav-delete" data-kind="${esc(item.kind)}" data-value="${esc(item.value)}" title="Permanently remove this favorite">Delete</button>
            </div>
          </div>
        </div>`;
      }).join("");
    }
    fl.querySelectorAll(".fav-connect").forEach((btn) => {
      btn.addEventListener("click", () => doAction({ action: "connect", target: btn.getAttribute("data-target") }, "Connect"));
    });
    fl.querySelectorAll("[data-fav-edit]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.getAttribute("data-fav-edit");
        toggleInlineEdit(fl.querySelector(`[data-fav-edit-panel="${key}"]`));
      });
    });
    fl.querySelectorAll("[data-fav-cancel-meta]").forEach((btn) => {
      btn.addEventListener("click", () => {
        fl.querySelector(`[data-fav-edit-panel="${btn.getAttribute("data-fav-cancel-meta")}"]`)?.classList.add("hidden");
      });
    });
    fl.querySelectorAll("[data-fav-save-meta]").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const kind = btn.getAttribute("data-fav-save-meta");
        const value = btn.getAttribute("data-fav-value");
        const panel = fl.querySelector(`[data-fav-edit-panel="${favoriteItemKey({ kind, value })}"]`);
        const label = panel?.querySelector(".fav-meta-label")?.value || "";
        const res = await doAction({ action: "favorite_update", kind, value, label }, "Update favorite");
        if (res.ok) await loadState(true);
      });
    });
    fl.querySelectorAll("[data-fav-save-preset]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.getAttribute("data-fav-save-preset") || "";
        const [kind, value] = key.split(":", 2);
        if (!kind || !value) return toast("Could not save favorite", false);
        saveFavoriteToMyPresets({ kind, value }, prof);
      });
    });
    fl.querySelectorAll("[data-fav-share]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const key = btn.getAttribute("data-fav-share") || "";
        const [kind, value] = key.split(":", 2);
        if (!kind || !value) return toast("Could not share favorite", false);
        shareFavoriteAsPreset({ kind, value }, prof);
      });
    });
    fl.querySelectorAll("[data-fav-hide]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction(
          { action: "favorite_hide", kind: btn.getAttribute("data-fav-hide"), value: btn.getAttribute("data-fav-value") },
          "Hide favorite"
        ).then((r) => { if (r.ok) loadState(true); });
      });
    });
    fl.querySelectorAll(".fav-delete").forEach((btn) => {
      markConfirm(btn, `Delete favorite “${btn.closest(".fav-card")?.querySelector(".fav-label-display")?.textContent || btn.getAttribute("data-value")}”? This cannot be undone.`);
      btn.addEventListener("click", () => {
        doAction(
          { action: "favorite_remove", kind: btn.getAttribute("data-kind"), value: btn.getAttribute("data-value") },
          "Delete favorite"
        ).then((r) => { if (r.ok) loadState(true); });
      });
    });
    applyButtonTitles(fl);
    renderHiddenPanel(
      hiddenPanel,
      `Hidden favorites (${hiddenItems.length})`,
      hiddenItems.map((item) => {
        const label = item.display || favoriteDisplayLabel(item, prof);
        return `<div class="wf-hidden-row"><span>${esc(favoriteEmoji(item))} ${esc(label)}</span><div class="actions">
          <button type="button" class="btn sm" data-fav-unhide="${esc(item.kind)}" data-fav-value="${esc(item.value)}">Show again</button>
          <button type="button" class="btn sm danger fav-hidden-delete" data-kind="${esc(item.kind)}" data-value="${esc(item.value)}">Delete</button>
        </div></div>`;
      }).join("")
    );
    hiddenPanel?.querySelectorAll("[data-fav-unhide]").forEach((btn) => {
      btn.addEventListener("click", () => {
        doAction(
          { action: "favorite_unhide", kind: btn.getAttribute("data-fav-unhide"), value: btn.getAttribute("data-fav-value") },
          "Restore favorite"
        ).then((r) => { if (r.ok) loadState(true); });
      });
    });
    hiddenPanel?.querySelectorAll(".fav-hidden-delete").forEach((btn) => {
      markConfirm(btn, `Delete favorite “${btn.getAttribute("data-value")}”? This cannot be undone.`);
      btn.addEventListener("click", () => {
        doAction(
          { action: "favorite_remove", kind: btn.getAttribute("data-kind"), value: btn.getAttribute("data-value") },
          "Delete favorite"
        ).then((r) => { if (r.ok) loadState(true); });
      });
    });
  }

  function renderAutomatePanels(data) {
    const zones = data?.zones || {};
    const zw = data?.zone_watch || {};
    const trusted = zones.is_trusted ? "Trusted" : "Untrusted";
    const trustedCls = zones.is_trusted ? "on" : "warn";
    if ($("zoneStatus")) {
      $("zoneStatus").innerHTML = [
        `<div class="tools-status-row"><span class="tools-status-lbl">SSID</span><strong>${esc(zones.ssid || "—")}</strong></div>`,
        `<div class="tools-status-row"><span class="tools-status-lbl">Zone</span><span class="badge ${trustedCls}">${trusted}</span></div>`,
        `<div class="tools-status-row"><span class="tools-status-lbl">Suggested preset</span><code>${esc(zones.suggested_preset || "—")}</code></div>`,
        `<div class="tools-status-row"><span class="tools-status-lbl">Auto-apply</span><span class="badge ${zones.auto_apply_enabled ? "on" : "off"}">${zones.auto_apply_enabled ? "On" : "Off"}</span></div>`,
      ].join("");
    }
    const watcherBadge = $("watcherBadge");
    if (watcherBadge) {
      watcherBadge.textContent = zw.running ? "Running" : (zw.enabled ? "Enabled" : "Stopped");
      watcherBadge.className = "badge " + (zw.running ? "on" : zw.enabled ? "warn" : "off");
    }
    if ($("watcherMetrics")) {
      $("watcherMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Watcher</div><div class="val ${zw.running ? "on" : "off"}">${zw.running ? "Running" : "Stopped"}</div><div class="sub">Background task</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Enabled</div><div class="val ${zw.enabled ? "on" : "off"}">${zw.enabled ? "Yes" : "No"}</div><div class="sub">In config</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Poll interval</div><div class="val">${esc(String(zw.interval_seconds || 30))}s</div><div class="sub">SSID check rate</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Auto-apply</div><div class="val ${zw.auto_apply ? "on" : "off"}">${zw.auto_apply ? "On" : "Off"}</div><div class="sub">Preset on zone change</div></div>`,
      ].join("");
    }
    const prof = data?.profiles || {};
    $("profileBox") && ($("profileBox").innerHTML = `<div class="tools-status-row"><span class="tools-status-lbl">Active profile</span><strong>${esc(prof.active || "default")}</strong></div>`);
    const ps = $("profileSelect");
    if (ps) {
      ps.innerHTML = "";
      (prof.names || ["default"]).forEach((n) => {
        const o = document.createElement("option");
        o.value = n; o.textContent = n;
        ps.appendChild(o);
      });
    }
    const snaps = data?.snapshots || [];
    const snapBadge = $("snapBadge");
    if (snapBadge) {
      snapBadge.textContent = snaps.length ? `${snaps.length} saved` : "Empty";
      snapBadge.className = "badge " + (snaps.length ? "on" : "off");
    }
    if ($("snapMetrics")) {
      const latest = snaps[0];
      const latestWhen = latest?.ts ? String(latest.ts).replace("T", " ").slice(0, 16) : "—";
      $("snapMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Saved</div><div class="val">${snaps.length}</div><div class="sub">Up to 10 kept</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Latest</div><div class="val">${esc(latest?.label || "—")}</div><div class="sub">${esc(latestWhen)}</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Scope</div><div class="val on">Nord only</div><div class="sub">CLI settings</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Auto-save</div><div class="val on">Presets</div><div class="sub">Before each run</div></div>`,
      ].join("");
    }
    $("snapshotList") && ($("snapshotList").innerHTML = snaps.length
      ? snaps.map((s, i) => {
        const when = s.ts ? esc(String(s.ts).replace("T", " ").slice(0, 19)) + " UTC" : esc(s.id || "");
        const label = s.label ? esc(s.label) : "manual";
        return `<article class="snapshot-card ${i === 0 ? "snapshot-card-latest" : ""}">
          <div class="snapshot-card-head"><strong>${esc(s.id || "")}</strong><span class="badge ${i === 0 ? "on" : "off"}">${i === 0 ? "Latest" : label}</span></div>
          <p class="snapshot-card-meta">${label} · ${when}</p>
        </article>`;
      }).join("")
      : `<div class="page-empty"><strong>No snapshots yet</strong>Run a preset (auto-save) or press <strong>Save snapshot</strong> in the hero.</div>`);
    renderFavorites(prof);
  }

  function favConnectTarget() {
    const city = $("favCitySelect")?.value || "";
    if (city) return city;
    const country = $("favCountrySelect")?.value || "";
    return country ? country.replace(/_/g, " ") : "";
  }

  function favFavoriteValue() {
    const city = $("favCitySelect")?.value || "";
    if (city) return city;
    return $("favCountrySelect")?.value || "";
  }

  function bindFavCountryCity() {
    bindCountryCityPair($("favCountrySelect"), $("favCitySelect"), "favBound");
  }

  function bindConnectCountryCity() {
    bindCountryCityPair($("connectCountrySelect"), $("connectCitySelect"), "connectBound");
  }

  async function loadAuditDiagnostics(force) {
    await loadLab(force);
    try {
      const tools = await apiCached("/api/nettools", {}, force ? 0 : CACHE_TTL.nettools);
      renderNetTools(tools, "adv");
      if (nettoolSelected.adv === "overview") {
        const advOut = $(NETTOOL_SCOPES.adv.output);
        const txt = advOut?.textContent || "";
        if (!txt.trim() || txt.startsWith("Select")) runNetTool("overview", "adv");
      }
    } catch (_) { /* ignore */ }
  }

  async function loadLab(force) {
    try {
      const ttl = force ? 0 : CACHE_TTL.lab;
      const [lab, audit] = await Promise.all([
        apiCached("/api/leaklab", {}, ttl),
        apiCached("/api/network-audit", {}, ttl),
      ]);
      renderLabResults(lab, audit);
      return { lab, audit };
    } catch (e) {
      reportActionError("Leak lab failed", e, "Running privacy checks");
      $("labScore") && ($("labScore").textContent = "—");
      $("labResults") && ($("labResults").innerHTML = '<p class="muted">Could not run tests — check the connection and try again.</p>');
      return null;
    }
  }

  const LEAK_TEST_META = {
    smart_dns_wifi: {
      about: "Compares WiFi interface DNS to your Smart DNS pair in nordctl config.",
      fixJump: "dashboard/nord-dns",
      fixLabel: "Open Nord DNS",
    },
    vpn_dns: {
      about: "When VPN is on, WiFi DNS should be Nord (103.86.x / 103.87.x), not your ISP.",
      fixJump: "dashboard/switches",
      fixLabel: "Fix Nord DNS",
    },
    public_ip: {
      about: "Shows which public IP this PC would use — home ISP for Smart DNS allowlist, not VPN exit.",
      fixJump: "dashboard/nord-dns",
      fixLabel: "Smart DNS setup",
    },
    resolv_conf: {
      about: "Checks /etc/resolv.conf for stub listeners or immutable flags that break DNS.",
      fixJump: "network/diagnostics",
      fixLabel: "Open Diagnostics",
    },
    route: {
      about: "Sample route to 1.1.1.1 — should use nordlynx tunnel interface when VPN is connected.",
      fixJump: "dashboard/split-tunnel",
      fixLabel: "Review split tunnel",
    },
    killswitch: {
      about: "Kill switch blocks all traffic when VPN is off — expected behavior, not a leak.",
      fixJump: "dashboard/switches",
      fixLabel: "Open Switches",
    },
  };

  function leakTestFixMeta(test) {
    const id = String(test?.id || "");
    return LEAK_TEST_META[id] || {
      about: "Privacy check on this machine.",
      fixJump: "network/diagnostics",
      fixLabel: "Open Diagnostics",
    };
  }

  function renderLeakLabSummary(lab) {
    const el = $("labSummary");
    if (!el || !lab) return;
    const fails = (lab.tests || []).filter((t) => !t.ok).length;
    if (lab.ok) {
      el.className = "leak-lab-summary ok";
      el.innerHTML = `<strong>All ${lab.total} checks passed.</strong> DNS and routing look consistent with your current VPN state. Re-run after connect/disconnect or router changes.`;
      return;
    }
    el.className = "leak-lab-summary warn";
    el.innerHTML = `<strong>${lab.score}/${lab.total} passed</strong> — ${fails} issue${fails === 1 ? "" : "s"} need attention. Read each card below and use the fix links.`;
  }

  function renderLeakLabContext(lab) {
    if (!lab) return;
    const connected = !!lab.connected;
    if ($("labVpnState")) {
      $("labVpnState").textContent = connected ? "On" : "Off";
      $("labVpnState").className = "val " + (connected ? "ok-text" : "muted-text");
    }
    if ($("labVpnIp")) $("labVpnIp").textContent = lab.vpn_ip || (connected ? "—" : "n/a");
    if ($("labHomeIp")) $("labHomeIp").textContent = lab.home_ip || lab.external_ip || "—";
    if ($("labKillSwitch")) {
      $("labKillSwitch").textContent = lab.killswitch ? "On" : "Off";
      $("labKillSwitch").className = "val " + (lab.killswitch ? "warn-text" : "ok-text");
    }
  }

  function renderLeakTestRow(test) {
    const meta = leakTestFixMeta(test);
    const ok = !!test.ok;
    const actions = [];
    if (!ok && meta.fixJump) {
      actions.push(`<button type="button" class="btn sm ${ok ? "" : "primary"} jump-link" data-view-jump="${esc(meta.fixJump)}">${esc(meta.fixLabel)}</button>`);
    }
    if (test.copy_value) {
      actions.push(`<button type="button" class="btn sm" data-copy-text="${esc(test.copy_value)}" title="Copy IP for Nord Account allowlist">Copy IP</button>`);
    }
    return `<article class="leak-test-row ${ok ? "ok" : "fail"}">
      <div class="leak-test-head">
        <span class="leak-test-icon" aria-hidden="true">${ok ? "✓" : "!"}</span>
        <div class="leak-test-title-wrap">
          <strong class="leak-test-title">${esc(test.name)}</strong>
          <span class="leak-test-status">${ok ? "Pass" : "Check"}</span>
        </div>
      </div>
      <p class="leak-test-about">${esc(meta.about)}</p>
      <p class="leak-test-detail"><strong>Result:</strong> ${esc(test.detail || "—")}</p>
      ${test.hint ? `<p class="help-text muted-inline leak-test-hint">${esc(test.hint)}</p>` : ""}
      ${actions.length ? `<div class="leak-test-actions">${actions.join("")}</div>` : ""}
    </article>`;
  }

  function renderLeakLabEmptyState() {
    $("labResults") && ($("labResults").innerHTML = "");
    $("labSummary") && ($("labSummary").className = "leak-lab-summary muted");
    $("labSummary") && ($("labSummary").innerHTML = "Press <strong>Run leak tests</strong> to scan DNS, routing, and public IP on this machine.");
    ["labVpnState", "labVpnIp", "labHomeIp", "labKillSwitch"].forEach((id) => {
      const el = $(id);
      if (el) el.textContent = "—";
    });
  }

  function renderLabResults(lab, audit) {
    const scoreEl = $("labScore");
    if (scoreEl && lab) {
      scoreEl.textContent = `${lab.score}/${lab.total}`;
      scoreEl.className = "badge " + (lab.ok ? "on" : (lab.score > 0 ? "warn" : "off"));
    }
    renderLeakLabContext(lab);
    if (lab?.tests?.length) {
      renderLeakLabSummary(lab);
      drawLeakLabCharts(lab);
      $("labResults") && ($("labResults").innerHTML = (lab.tests || []).map(renderLeakTestRow).join(""));
      bindViewJumps($("labResults"));
      $("labResults")?.querySelectorAll("[data-copy-text]").forEach((btn) => {
        if (btn.dataset.copyBound) return;
        btn.dataset.copyBound = "1";
        btn.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(btn.dataset.copyText || "");
            toast("Copied to clipboard", true);
          } catch (_) {
            toast("Copy failed", false);
          }
        });
      });
    } else if (!lab) {
      renderLeakLabEmptyState();
    } else {
      $("labResults") && ($("labResults").innerHTML = '<p class="muted">No tests returned.</p>');
    }
    $("auditResults") && ($("auditResults").innerHTML = (audit?.checks || []).map((c) =>
      `<div class="check check-${c.ok ? "ok" : "error"}">${esc(c.summary)}</div>`
    ).join(""));
    const auditBadge = $("auditBadge");
    if (auditBadge && audit) {
      const bad = (audit.checks || []).filter((c) => !c.ok).length;
      auditBadge.textContent = bad ? `${bad} issue(s)` : "OK";
      auditBadge.className = "badge " + (bad ? "warn" : "on");
    }
  }

  function auditCheckStatus(c) {
    if (c.ok) return { label: "OK", cls: "ok" };
    if (c.severity === "error") return { label: "Must fix", cls: "bad" };
    return { label: "Tip", cls: "warn" };
  }

  function auditJumpTarget(c) {
    if (c.ok) return null;
    if (c.jump) return c.jump;
    const id = String(c.id || "");
    const cat = String(c.category || "");
    if (id === "vpn_dns") return "dashboard/switches";
    if (id.includes("smart_dns")) return "dashboard/nord-dns";
    if (id.includes("resolv") || id === "dns_manager") return "network/diagnostics";
    if (id.includes("ipv6")) return "network/network/ipv6";
    if (id.includes("route")) return "network/leak-tests";
    if (cat === "connectivity" || cat === "dns") return "network/diagnostics";
    if (cat === "routing") return "dashboard/split-tunnel";
    return "network/diagnostics";
  }

  function auditJumpButtonLabel(c, jump) {
    if (c.jump_label) return c.jump_label;
    const j = String(jump || "");
    if (j.includes("dashboard/switches")) return "Fix Nord DNS (Switches)";
    if (j.includes("nord-dns")) return "Open Nord DNS";
    if (j.includes("split-tunnel")) return "Review split tunnel";
    if (j.includes("ipv6")) return "Open IPv6 settings";
    if (j.includes("doctors/net")) return "Open Net doctor";
    if (j.includes("leak-tests") || j.includes("audit/leak")) return "Run leak tests";
    if (j.includes("diagnostics")) return "Open Diagnostics";
    return "Go fix";
  }

  function auditCheckDetailHtml(c) {
    const d = String(c.detail || "").trim();
    if (!d) return "";
    const mono = /via |dev |PING |icmp_seq|\{|\}|\\n/.test(d) || d.length > 90;
    if (mono) return `<code class="audit-check-mono">${esc(d)}</code>`;
    return `<p class="muted-inline audit-check-detail">${esc(d)}</p>`;
  }

  function auditCheckRowHtml(c) {
    const st = auditCheckStatus(c);
    const fixes = (c.fix || []).filter(Boolean);
    const actions = [];
    const jump = auditJumpTarget(c);
    if (!c.ok && c.action) {
      actions.push(
        `<button type="button" class="btn sm primary audit-fix-btn" data-action="${esc(c.action)}" data-confirm="1">${esc(c.action_label || "Fix now")}</button>`
      );
    }
    if (!c.ok && jump) {
      const primary = c.severity === "error" && !c.action;
      actions.push(
        `<button type="button" class="btn sm ${primary ? "primary" : ""} jump-link audit-jump-btn" data-view-jump="${esc(jump)}">${esc(auditJumpButtonLabel(c, jump))}</button>`
      );
    }
    return `<div class="doctor-check-row audit-check-row ${st.cls}">
      <div class="doctor-check-head">
        <span class="doctor-check-icon" aria-hidden="true">${c.ok ? "✓" : "!"}</span>
        <span class="doctor-check-title">${esc(c.name || c.summary)}</span>
        <span class="doctor-status">${st.label}</span>
      </div>
      <p class="doctor-check-detail">${esc(c.explain || c.summary || "")}</p>
      ${auditCheckDetailHtml(c)}
      ${fixes.length ? `<ul class="doctor-check-fixes">${fixes.map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
      ${actions.length ? `<div class="doctor-check-actions">${actions.join("")}</div>` : ""}
    </div>`;
  }

  function bindOverallAuditActions(scope) {
    if (!scope) return;
    scope.querySelectorAll(".audit-fix-btn").forEach((btn) => {
      if (btn.dataset.auditBound) return;
      btn.dataset.auditBound = "1";
      btn.addEventListener("click", () => runOverallAuditFix(btn.dataset.action));
    });
    bindViewJumps(scope);
  }

  async function runOverallAuditFix(action) {
    const map = {
      disable_ipv6: { action: "disable_ipv6" },
      fix_resolv_immutable: { action: "fix_resolv_immutable" },
      fix_resolv_stub: { action: "fix_resolv_stub" },
      dns_apply_smart: { action: "dns_apply_smart" },
    };
    const body = map[action] || { action };
    const res = await doAction(body, action);
    if (res?.ok) {
      invalidateApiCache("/api/overall-audit");
      invalidateApiCache("/api/leaklab");
      invalidateApiCache("/api/network-audit");
      await loadOverallAudit(true);
    }
  }

  const AUDIT_EMAIL_KEY = "nordctl_audit_email_on_done";
  let lastOverallAuditData = null;

  function initAuditEmailPref() {
    const cb = $("auditEmailWhenDone");
    if (!cb || cb.dataset.bound) return;
    cb.dataset.bound = "1";
    cb.checked = localStorage.getItem(AUDIT_EMAIL_KEY) === "1";
    cb.addEventListener("change", () => {
      localStorage.setItem(AUDIT_EMAIL_KEY, cb.checked ? "1" : "0");
    });
  }

  function renderAuditToolInstallButton(t, toolsInfo) {
    if (!t.missing || !t.installable) return "";
    const cmd = t.install_cmd || "";
    const toolId = t.install_tool || t.id;
    if (toolsInfo?.can_install && toolId) {
      return `<button type="button" class="btn sm primary" data-audit-install-api="${esc(toolId)}" data-audit-install-label="${esc(t.label || t.id)}">Install</button>`;
    }
    if (toolsInfo?.can_install_terminal && cmd) {
      return `<button type="button" class="btn sm primary" data-audit-install-terminal="${esc(cmd)}" data-audit-install-label="${esc(t.label || t.id)}" title="Opens Shell and runs apt — enter your sudo password when asked">Install in terminal</button>`;
    }
    if (cmd) {
      return `<button type="button" class="btn sm" data-audit-copy-cmd="${esc(cmd)}" data-audit-install-label="${esc(t.label || t.id)}">Copy install command</button>`;
    }
    return "";
  }

  function wireAuditToolsActions(toolsInfo) {
    const root = $("auditToolsBox");
    root?.querySelectorAll("[data-audit-install-api]").forEach((b) => {
      b.addEventListener("click", () => installAuditTool(b.dataset.auditInstallApi, b.dataset.auditInstallLabel || b.textContent.trim(), toolsInfo));
    });
    root?.querySelectorAll("[data-audit-install-terminal]").forEach((b) => {
      b.addEventListener("click", () => installToolInTerminal(b.dataset.auditInstallTerminal, b.dataset.auditInstallLabel || "Install tool", { returnRoute: AUDIT_RETURN_ROUTE }));
    });
    root?.querySelectorAll("[data-audit-copy-cmd]").forEach((b) => {
      b.addEventListener("click", () => copyToolCommand(b.dataset.auditCopyCmd, b.dataset.auditInstallLabel));
    });
    $("auditToolsActions")?.querySelector("[data-audit-install-batch]")?.addEventListener("click", () => installAuditMissingTools(toolsInfo, { requiredOnly: true }));
    bindViewJumps($("auditToolsActions"));
  }

  function renderAuditTools(toolsInfo) {
    const list = $("auditToolsList");
    const badge = $("auditToolsBadge");
    const actions = $("auditToolsActions");
    if (!list) return;
    const tools = toolsInfo?.tools || [];
    if (!tools.length) {
      list.innerHTML = `<li class="muted">Tool list loads when the audit runs.</li>`;
      if (badge) badge.textContent = "—";
      if (actions) actions.innerHTML = "";
      return;
    }
    const missingReq = tools.filter((t) => t.required && t.missing);
    const missingOpt = tools.filter((t) => !t.required && t.missing);
    const missingInstallableReq = missingReq.filter((t) => t.installable);
    if (badge) {
      badge.textContent = missingReq.length
        ? `${missingReq.length} required missing`
        : missingOpt.length
          ? `${missingOpt.length} optional missing`
          : "Ready";
      badge.className = "badge " + (missingReq.length ? "off" : missingOpt.length ? "warn" : "on");
    }
    list.innerHTML = tools.map((t) => {
      const cls = t.missing ? (t.required ? "missing" : "optional-missing") : "ok";
      let status;
      if (!t.missing) status = "Installed";
      else if (t.installable) status = t.required ? "Missing — click Install" : "Missing — optional";
      else status = t.required ? "Missing — required" : "Missing — optional";
      const pkg = (t.packages || []).length ? `Package: ${esc((t.packages || []).join(", "))}` : "Usually pre-installed";
      const installBtn = renderAuditToolInstallButton(t, toolsInfo);
      return `<li class="${cls}"><strong>${esc(t.label || t.id)}</strong><span class="muted">${esc(status)} · ${esc(t.used_for || "")}</span><div class="muted">${pkg}</div>${installBtn ? `<div class="audit-tool-actions">${installBtn}</div>` : ""}</li>`;
    }).join("");
    if (actions) {
      const parts = [];
      if (missingInstallableReq.length) {
        const bulkLabel = toolsInfo?.can_install
          ? `Install ${missingInstallableReq.length} required tool${missingInstallableReq.length === 1 ? "" : "s"}`
          : toolsInfo?.can_install_terminal
            ? `Install ${missingInstallableReq.length} required in terminal`
            : `Copy install commands`;
        parts.push(`<button type="button" class="btn sm primary" data-audit-install-batch>${esc(bulkLabel)}</button>`);
      }
        parts.push(`<button type="button" class="btn sm jump-link" data-view-jump="network/network-packages" title="Browse networking apt packages">Networking packages</button>`);
      actions.innerHTML = parts.join("");
    }
    wireAuditToolsActions(toolsInfo);
  }

  async function installAuditTool(toolId, label, toolsInfo) {
    if (!toolId) return;
    await installOptionalTool(toolId, label || toolId, { returnRoute: AUDIT_RETURN_ROUTE, skipPackagesResult: true });
    invalidateApiCache("/api/overall-audit");
    await loadOverallAudit(true);
  }

  async function installAuditMissingTools(toolsInfo, opts = {}) {
    const tools = toolsInfo?.tools || [];
    const requiredOnly = opts.requiredOnly !== false;
    const missing = tools.filter((t) => t.missing && t.installable && (!requiredOnly || t.required));
    if (!missing.length) {
      toast("No installable missing tools", false);
      return;
    }
    const auditOpts = { returnRoute: AUDIT_RETURN_ROUTE };
    if (toolsInfo?.can_install) {
      const ids = missing.map((t) => t.install_tool || t.id).filter(Boolean);
      if (ids.length === 1) {
        await installAuditTool(ids[0], missing[0].label, toolsInfo);
        return;
      }
      if (!confirm(`Install ${ids.length} required package(s) for the audit?\n\nThis may take several minutes.`)) return;
      setBusy(true);
      try {
        const res = await api("/api/tools/install", { method: "POST", body: JSON.stringify({ tools: ids }) });
        toast(res.message || res.error || (res.ok ? "Installed" : "Failed"), res.ok || res.partial);
        if (res.tools) {
          toolsPayloadCache = res.tools;
          renderAllHubToolCards(toolsPayloadCache);
        }
        if (res.ok || res.partial) {
          await refreshAfterToolInstall(null, "network");
          invalidateApiCache("/api/overall-audit");
          await loadOverallAudit(true);
        } else if (res.manual && toolsInfo?.can_install_terminal) {
          await installToolInTerminal(res.retry_cmd || res.manual, "Install audit tools", auditOpts);
        } else if (res.manual) {
          copyToolCommand(res.manual, "Audit tools");
        }
        logActivity("install", `Audit tools: ${res.message || res.error || "done"}`, res.ok);
      } finally {
        setBusy(false);
      }
      return;
    }
    if (toolsInfo?.can_install_terminal) {
      const pkgs = [];
      missing.forEach((t) => (t.packages || []).forEach((p) => { if (p && !pkgs.includes(p)) pkgs.push(p); }));
      if (pkgs.length) {
        await installToolInTerminal(`sudo apt install -y ${pkgs.join(" ")}`, `Install ${missing.length} audit tool(s)`, auditOpts);
      }
      return;
    }
    const cmds = missing.map((t) => t.install_cmd).filter(Boolean).join("\n");
    if (cmds) copyToolCommand(cmds, "Audit tools");
    else toast("No install command available", false);
  }

  function renderAuditEmailPanel(emailInfo, hasResults) {
    initAuditEmailPref();
    const badge = $("auditEmailBadge");
    const hint = $("auditEmailHint");
    const sendBtn = $("btnAuditEmailSend");
    const setupBtn = $("btnAuditEmailSetup");
    const statusEl = $("auditEmailStatus");
    const email = emailInfo || {};
    const ready = !!email.ready;
    if (badge) {
      badge.textContent = ready ? "Ready" : email.configured ? "Needs enable" : "Not set up";
      badge.className = "badge " + (ready ? "on" : email.configured ? "warn" : "off");
    }
    if (hint) {
      hint.textContent = email.setup_hint
        || "Optional — send a plain-text summary to your own address via your SMTP (Settings → Email).";
    }
    if (sendBtn) {
      sendBtn.classList.toggle("hidden", !ready || !hasResults);
      sendBtn.disabled = !ready || !hasResults;
    }
    if (setupBtn) {
      setupBtn.classList.toggle("hidden", ready);
    }
    if (statusEl) {
      statusEl.classList.toggle("hidden", !hasResults);
      if (hasResults && !ready) {
        statusEl.textContent = "Email is not configured yet — set up SMTP to receive audit reports.";
      } else if (hasResults && ready) {
        statusEl.textContent = `Reports go to ${email.to || "your saved address"}.`;
      }
    }
    bindViewJumps($("auditEmailBox"));
  }

  async function sendAuditEmailReport(data) {
    const audit = data || lastOverallAuditData;
    if (!audit) {
      toast("Run the audit first", false);
      return null;
    }
    showMsg("Sending audit report…", true);
    try {
      const res = await api("/api/overall-audit/email", { method: "POST", body: "{}" });
      const msg = res.note || res.error || (res.ok ? "Report sent" : "Email failed");
      toast(msg, !!res.ok);
      logActivity("audit email", msg.slice(0, 120), !!res.ok);
      if (!res.ok && !res.skipped) {
        showNotice(
          [res.error || "Could not send email.", res.email?.setup_hint || "Open Settings → Email to configure SMTP."].filter(Boolean).join("\n\n"),
          { ok: false, title: "Audit email", copyText: res.error || msg }
        );
      }
      return res;
    } catch (e) {
      reportActionError("Audit email failed", e, "Send audit report");
      return null;
    }
  }

  async function maybeEmailAuditReport(data) {
    const email = data?.email || {};
    if (email.ready) {
      return sendAuditEmailReport(data);
    }
    showNotice(
      [
        "You asked to email the audit report, but SMTP is not set up yet.",
        "",
        `Open ${viewLink("settings", "Settings → Email", "network/email")} and enter your mail provider’s SMTP host, recipient address, and app password, then enable email alerts.`,
        "",
        "After saving, run the audit again or use Send report now.",
      ].join("<br>"),
      { ok: false, title: "Set up email first", html: true }
    );
    return null;
  }

  function renderOverallAudit(data) {
    const badge = $("overallAuditBadge");
    const summary = $("overallAuditSummary");
    const stats = $("overallAuditStats");
    const box = $("overallAuditCategories");
    if (!box) return;
    if (!data) {
      if (badge) badge.textContent = "—";
      if (summary) summary.textContent = "Could not run audit — check the connection and try again.";
      box.innerHTML = "";
      renderAuditTools(null);
      renderAuditEmailPanel(null, false);
      return;
    }
    lastOverallAuditData = data;
    renderAuditTools(data.tools);
    renderAuditEmailPanel(data.email, true);
    const passed = data.passed ?? 0;
    const total = data.total ?? 0;
    const issues = data.issue_count ?? 0;
    const blocking = data.blocking_count ?? 0;
    if (badge) {
      badge.textContent = blocking ? `${blocking} fix` : issues ? `${issues} tip${issues === 1 ? "" : "s"}` : "All OK";
      badge.className = "badge " + (blocking ? "off" : issues ? "warn" : "on");
    }
    if (summary) {
      summary.innerHTML = [
        `<p><strong>${esc(data.headline || data.summary || "Audit complete")}</strong></p>`,
        data.connected
          ? `<p class="help-text" style="margin:0.35rem 0 0">VPN connected${data.vpn_ip ? ` — exit ${esc(data.vpn_ip)}` : ""}. Leak lab score: ${esc(data.leak_score || "—")}.</p>`
          : `<p class="help-text" style="margin:0.35rem 0 0">VPN off${data.home_ip ? ` — home ISP ${esc(data.home_ip)}` : ""}. Leak lab score: ${esc(data.leak_score || "—")}.</p>`,
        blocking
          ? `<p class="help-text" style="margin:0.45rem 0 0">Red items need attention — use the <strong>Fix now</strong> or labeled button on each card below.</p>`
          : issues
            ? `<p class="help-text" style="margin:0.45rem 0 0">Optional tips improve privacy — skip any you do not need.</p>`
            : `<p class="help-text" style="margin:0.45rem 0 0">Everything looks healthy for DNS, routing, and basic privacy on this PC.</p>`,
      ].join("");
    }
    if (stats) {
      stats.classList.remove("hidden");
      stats.innerHTML = [
        `<span class="badge on">${passed}/${total} passed</span>`,
        data.warning_count ? `<span class="badge warn">${data.warning_count} tips</span>` : "",
        blocking ? `<span class="badge off">${blocking} must fix</span>` : "",
      ].join("");
    }
    const categories = data.categories || [];
    box.innerHTML = categories.map((cat) =>
      `<section class="audit-category">
        <div class="audit-category-head">
          <h3>${esc(cat.label)}</h3>
          <span class="badge ${cat.passed === cat.total ? "on" : "warn"}">${cat.passed}/${cat.total}</span>
        </div>
        <div class="audit-category-grid">${(cat.items || []).map(auditCheckRowHtml).join("")}</div>
      </section>`
    ).join("") || `<p class="muted">No checks returned.</p>`;
    bindOverallAuditActions(box);
    bindViewJumps($("overallAuditPanel"));
    drawAuditCategoryChart(data);
  }

  async function loadOverallAudit(force) {
    const box = $("overallAuditCategories");
    const summary = $("overallAuditSummary");
    initAuditEmailPref();
    if (force && summary) summary.textContent = "Running privacy audit…";
    try {
      const data = await apiCached("/api/overall-audit", {}, force ? 0 : CACHE_TTL.overallAudit);
      renderOverallAudit(data);
      return data;
    } catch (e) {
      reportActionError("Audit failed", e, "Running overall audit");
      renderOverallAudit(null);
      return null;
    }
  }

  async function runOverallAudit() {
    const btn = $("btnRunOverallAudit");
    const summary = $("overallAuditSummary");
    if (btn) {
      btn.disabled = true;
      btn.classList.add("running");
    }
    if (summary) summary.textContent = "Running privacy audit — DNS, routing, resolv.conf, public IP…";
    showMsg("Running full audit…", true);
    try {
      invalidateApiCache("/api/overall-audit");
      invalidateApiCache("/api/leaklab");
      invalidateApiCache("/api/network-audit");
      const data = await loadOverallAudit(true);
      if (data) {
        const msg = data.ok
          ? `Audit: all ${data.total} checks passed`
          : `Audit: ${data.passed}/${data.total} passed — ${data.issue_count} item${data.issue_count === 1 ? "" : "s"} to review`;
        toast(msg, !!data.ok);
        logActivity("audit", msg, !!data.ok);
        if (data.tools && !data.tools.ready) {
          toast(`Install required tools for full accuracy (${(data.tools.missing_required || []).join(", ")})`, false);
        }
        if ($("auditEmailWhenDone")?.checked) {
          await maybeEmailAuditReport(data);
        }
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.classList.remove("running");
      }
    }
  }

  async function runLeakLab() {
    const btn = $("btnRunLab");
    const scoreEl = $("labScore");
    const resultsEl = $("labResults");
    if (btn) {
      btn.disabled = true;
      btn.classList.add("running");
    }
    if (scoreEl) {
      scoreEl.textContent = "Running…";
      scoreEl.className = "badge";
    }
    if (resultsEl) {
      resultsEl.innerHTML = '<p class="muted lab-running">Running leak tests — Smart DNS, VPN DNS, public IP, resolv.conf, routing…</p>';
    }
    showMsg("Running leak tests…", true);
    try {
      invalidateApiCache("/api/leaklab");
      invalidateApiCache("/api/network-audit");
      const out = await loadLab(true);
      if (out?.lab) {
        const { lab } = out;
        const fails = (lab.tests || []).filter((t) => !t.ok).length;
        const msg = fails
          ? `Leak lab: ${lab.score}/${lab.total} passed — ${fails} issue${fails === 1 ? "" : "s"}`
          : `Leak lab: all ${lab.total} checks passed`;
        toast(msg, !!lab.ok);
        logActivity("lab", msg, !!lab.ok);
      }
    } finally {
      if (btn) {
        btn.disabled = false;
        btn.classList.remove("running");
      }
    }
  }

  function fmtTrafficMbps(v) {
    return `${(v == null ? 0 : Number(v)).toFixed(2)} Mbps`;
  }

  function trafficDotClass(up, active) {
    if (up === false) return "down";
    if (active === false) return "idle";
    return "";
  }

  function trafficAddrCell(ip, port, host, device) {
    let html = "";
    if (device) html += `<span class="host">${esc(device)}</span> `;
    if (ip) html += esc(ip);
    if (port) html += `:${port}`;
    if (host && host !== device) html += `<div class="muted">${esc(host)}</div>`;
    return html || "—";
  }

  function paintTrafficConnTable(tbody, rows, emptyMsg) {
    if (!tbody) return;
    if (!rows?.length) {
      tbody.innerHTML = `<tr class="empty-row"><td colspan="7">${esc(emptyMsg)}</td></tr>`;
      return;
    }
    tbody.innerHTML = rows.map((r) => {
      const dirCls = r.direction === "outbound" ? "dir-out" : r.direction === "inbound" ? "dir-in" : "dir-listen";
      const dirLabel = r.direction === "listening" ? "LISTEN" : String(r.direction || "").toUpperCase();
      return `<tr>
        <td class="${dirCls}">${dirLabel}</td>
        <td>${trafficAddrCell(r.local_ip, r.local_port, r.local_host, r.local_device)}</td>
        <td>${trafficAddrCell(r.remote_ip, r.remote_port, r.remote_host, r.remote_device)}</td>
        <td>${esc(r.service || "—")}</td>
        <td class="proc">${esc(r.process || "—")}${r.pid ? ` <span class="muted">pid ${r.pid}</span>` : ""}</td>
        <td class="muted">${esc(r.user || "")}</td>
        <td class="muted proc">${esc(r.cmdline || "")}</td>
      </tr>`;
    }).join("");
  }

  function paintTrafficConnectPath(el, path) {
    if (!el) return;
    el.innerHTML = (path || []).map((step, i) => {
      const arrow = i > 0
        ? `<div class="traffic-connect-arrow">↓ via ${esc(step.via || "—")}</div>`
        : "";
      const meta = [step.ip, step.speed, step.detail].filter(Boolean).join(" · ");
      return `${arrow}<div class="traffic-connect-row${step.up === false ? " down" : ""}">
        <div class="name"><span class="traffic-status-dot ${trafficDotClass(step.up)}"></span>${esc(step.name)}</div>
        ${i === 0 && step.via ? `<div class="via">${esc(step.via)}</div>` : ""}
        ${meta ? `<div class="meta">${esc(meta)}</div>` : ""}
      </div>`;
    }).join("");
  }

  function paintTrafficConnectLinks(el, links) {
    if (!el) return;
    el.innerHTML = (links || []).map((link) => {
      const meta = [link.ip, link.detail].filter(Boolean).join(" · ");
      return `<div class="traffic-connect-row${link.up === false ? " down" : ""}">
        <div class="name"><span class="traffic-status-dot ${trafficDotClass(link.up)}"></span>${esc(link.name)}</div>
        <div class="via">via ${esc(link.via || "—")}</div>
        ${meta ? `<div class="meta">${esc(meta)}</div>` : ""}
      </div>`;
    }).join("");
  }

  function renderTrafficInternet(data) {
    const s = data.summary || {};
    const c = data.counts || {};
    const age = data.ts ? formatLocaleTime(data.ts * 1000, true) : "—";
    const set = (id, text) => { const el = $(id); if (el) el.textContent = text; };
    set("trafficStatWan", `${fmtTrafficMbps(s.wan_down_mbps)} / ${fmtTrafficMbps(s.wan_up_mbps)}`);
    set("trafficStatOut", String(c.internet_outbound ?? 0));
    set("trafficStatIn", String(c.internet_inbound ?? 0));
    set("trafficStatListen", String(c.internet_listening ?? 0));
    set("trafficStatVpn", s.vpn_connected ? (s.external_country || "on") : "off");
    set("trafficInternetAge", `updated ${age}`);
    const badge = $("trafficInternetBadge");
    if (badge) {
      badge.textContent = `${c.internet_outbound ?? 0} out · ${c.internet_inbound ?? 0} in`;
      badge.className = "badge on";
    }
    const grid = $("trafficSummaryGrid");
    if (grid) {
      const cards = [
        { lbl: "Public IP", val: s.external_ip || "—", big: true },
        { lbl: "Mesh IP", val: s.mesh_ip || data.meshnet?.host || "—" },
        { lbl: "Country", val: s.external_country || "—" },
        { lbl: "WAN speed", val: `${fmtTrafficMbps(s.wan_down_mbps)} / ${fmtTrafficMbps(s.wan_up_mbps)}` },
      ];
      grid.innerHTML = cards.map((card) => `
        <div class="traffic-summary-card">
          <div class="lbl">${esc(card.lbl)}</div>
          <div class="val${card.big ? " big" : ""}">${esc(card.val)}</div>
        </div>`).join("");
    }
    const feedGrid = $("trafficFeedGrid");
    if (feedGrid) {
      const feeds = data.outbound_feeds || [];
      feedGrid.innerHTML = feeds.length
        ? feeds.map((f) => {
          const cls = f.active ? "ok" : (f.service_up ? "idle" : "down");
          const state = f.active ? "sending" : (f.service_up ? "idle" : "offline");
          return `<div class="traffic-feed-card ${cls}">
            <div class="lbl">${esc(f.name)}</div>
            <div class="val">${esc(state)}</div>
            <div class="sub">via ${esc(f.via || "—")}</div>
            <div class="sub">→ ${esc(f.dest || "—")}</div>
            <div class="sub">${esc(f.detail || "")}</div>
          </div>`;
        }).join("")
        : '<div class="traffic-feed-card"><div class="val">No feeds detected</div></div>';
    }
    paintTrafficConnTable($("trafficOutboundBody"), data.internet_outbound, "No outbound internet sessions");
    paintTrafficConnTable($("trafficInboundBody"), data.internet_inbound, "No inbound internet sessions");
    paintTrafficConnTable($("trafficListenBody"), data.internet_listening, "No WAN listen sockets");
  }

  function renderTrafficLocal(data) {
    const s = data.summary || {};
    const c = data.counts || {};
    const age = data.ts ? formatLocaleTime(data.ts * 1000, true) : "—";
    const set = (id, text) => { const el = $(id); if (el) el.textContent = text; };
    set("trafficStatLan", `${fmtTrafficMbps(s.lan_down_mbps)} / ${fmtTrafficMbps(s.lan_up_mbps)}`);
    set("trafficStatMesh", `${fmtTrafficMbps(s.mesh_down_mbps)} / ${fmtTrafficMbps(s.mesh_up_mbps)}`);
    const meshUp = data.meshnet?.up;
    set("trafficStatMeshUp", meshUp ? `UP · ${data.meshnet?.host || ""}` : "DOWN");
    $("trafficStatMeshWrap")?.classList.toggle("ok", !!meshUp);
    $("trafficStatMeshWrap")?.classList.toggle("down", !meshUp);
    set("trafficStatLocal", String(c.local_sessions ?? 0));
    set("trafficStatSvc", `${s.services_up ?? 0} / ${s.services_total ?? 0} up`);
    set("trafficLocalAge", `updated ${age}`);
    const badge = $("trafficLocalBadge");
    if (badge) {
      badge.textContent = `${c.local_sessions ?? 0} LAN`;
      badge.className = "badge on";
    }
    paintTrafficConnectPath($("trafficConnectPath"), data.connect_path);
    paintTrafficConnectLinks($("trafficConnectLinks"), data.network_links);
    paintTrafficConnTable($("trafficLocalSessions"), data.local_connections, "No active LAN TCP sessions");
    paintTrafficConnTable($("trafficLocalListening"), data.local_listening, "No LAN listen sockets");
  }

  function renderTrafficMap(data) {
    if (!data?.ok) {
      $("trafficInternetErr")?.classList.remove("hidden");
      $("trafficLocalErr")?.classList.remove("hidden");
      const msg = data?.error || "Could not read connections";
      $("trafficInternetBadge") && ($("trafficInternetBadge").textContent = "—");
      $("trafficLocalBadge") && ($("trafficLocalBadge").textContent = "—");
      return;
    }
    $("trafficInternetErr")?.classList.add("hidden");
    $("trafficLocalErr")?.classList.add("hidden");
    renderTrafficInternet(data);
    renderTrafficLocal(data);
    pushTrafficMapHistory(data);
    drawTrafficMapCharts();
  }

  async function loadTraffic(quiet) {
    try {
      const data = await api("/api/traffic");
      renderTrafficMap(data);
      if (!quiet) {
        const c = data.counts || {};
        logActivity(
          "traffic",
          `Traffic map — ${c.internet_outbound || 0} internet out, ${c.local_sessions || 0} LAN`,
          data.ok,
          "",
        );
      }
    } catch (e) {
      renderTrafficMap({ ok: false, error: String(e) });
    }
  }

  function highlightNetOutput(text) {
    const lines = String(text || "").split("\n");
    return lines.map((line) => {
      const low = line.toLowerCase();
      if (low.includes("nordlynx") || low.includes("nordtun") || low.includes("via vpn")) {
        return `<span class="vpn-mark">${esc(line)}</span>`;
      }
      return esc(line);
    }).join("\n");
  }

  function nettoolMeta(scopeKey, toolId) {
    const id = String(toolId || nettoolSelected[scopeKey] || "").toLowerCase();
    return (nettoolsLastPayload?.tools || []).find((t) => t.id === id) || null;
  }

  function nettoolUsesTerminal(meta) {
    return !!(meta?.needs_root && meta?.terminal_cmd);
  }

  function nettoolBuildTerminalCmd(meta, target = "") {
    let cmd = String(meta?.terminal_cmd || "").trim();
    if (!cmd) return "";
    if (meta?.needs_target && target) {
      cmd = cmd.replace(/\{target\}/g, target);
    }
    return cmd;
  }

  function nettoolOutputNeedsSudo(text) {
    const s = String(text || "").toLowerCase();
    return /need to be root|must be root|you need root|permission denied|operation not permitted|access denied|not permitted|requires root/.test(s);
  }

  function renderNetToolOutput(result, scopeKey = "lab", metaOverride = null) {
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    const out = $(scope.output);
    const badge = $(scope.badge);
    if (!out) return;
    const toolId = result?.tool || nettoolSelected[scopeKey];
    const meta = metaOverride || nettoolMeta(scopeKey, toolId);
    const header = [
      result?.label || result?.tool || "Tool",
      result?.target ? `→ ${result.target}` : "",
      result?.summary || "",
      result?.via_vpn ? "· via VPN tunnel" : "",
    ].filter(Boolean).join(" ");
    const body = result?.output || result?.error || "No output";
    const termCmd = nettoolBuildTerminalCmd(meta, result?.target || "");
    const showTerminalBtn = termCmd && (!result?.ok || nettoolOutputNeedsSudo(body));
    let actions = "";
    if (showTerminalBtn) {
      actions = `<div class="nettool-output-actions actions" style="margin-bottom:0.5rem"><button type="button" class="btn sm primary" data-nettool-terminal="${esc(meta?.id || toolId || "")}">Run with sudo in Terminal</button></div>`;
    }
    out.innerHTML = actions + esc(header) + "\n\n" + highlightNetOutput(body);
    out.querySelector("[data-nettool-terminal]")?.addEventListener("click", () => {
      if (meta) runNetToolViaTerminal(meta, scopeKey);
    });
    if (badge) {
      badge.textContent = result?.ok ? "OK" : "FAIL";
      badge.className = "badge " + (result?.ok ? "on" : "off");
    }
  }

  async function runNetToolViaTerminal(meta, scopeKey = "adv") {
    if (!meta) return;
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    const target = scope.target ? String($(scope.target)?.value || "").trim() : "";
    if (meta.needs_target && !target) {
      toast("Enter a target host or IP in the box below first.", false);
      if (scope.target && $(scope.target)) $(scope.target).focus();
      return;
    }
    const cmd = nettoolBuildTerminalCmd(meta, target);
    if (!cmd) return;
    const out = $(scope.output);
    if (out) {
      out.textContent = "Opening Diagnostics → Shell — enter your sudo password in the box when it appears…";
    }
    if (scope.badge && $(scope.badge)) {
      $(scope.badge).textContent = "Terminal";
      $(scope.badge).className = "badge";
    }
    toast("Opening Shell — sudo commands show a password box when needed.", true);
    await termRunCommand(cmd, meta.label || meta.id);
  }

  let nettoolsLastPayload = null;
  let pendingNettoolTool = null;

  const NETTOOL_HUB_TABS = {
    adv: "diagnostics",
    network: "network",
  };

  function nettoolScopeForHubTab(hubTabId) {
    if (hubTabId === "diagnostics") return "adv";
    if (hubTabId === "network") return "network";
    return null;
  }

  function syncNettoolRouteHash(scopeKey, replace) {
    const hubTabId = NETTOOL_HUB_TABS[scopeKey];
    if (!hubTabId) return;
    const tool = nettoolSelected[scopeKey];
    const sub = tool && tool !== "overview" ? tool : null;
    syncRouteHash("network", hubTabId, !!replace, sub);
  }

  function nettoolButtonHtml(tools, selected) {
    return tools.map((t) => {
      const missing = t.install_id && t.package_installed === false;
      const missingTag = missing ? ' <span class="tool-missing-tag">needs install</span>' : "";
      const sudoTag = t.needs_root ? '<span class="term-sudo-tag">sudo</span>' : "";
      const cls = [
        "btn sm nettool-btn",
        selected === t.id ? "active" : "",
        missing ? "tool-needs-pkg" : "",
        t.needs_root ? "term-quick-sudo" : "",
      ].filter(Boolean).join(" ");
      return `<button type="button" class="${cls}" data-tool="${esc(t.id)}" title="${esc(t.hint || t.label)}">${esc(t.label)}${missingTag}${sudoTag}</button>`;
    }).join("");
  }

  function syncNettoolButtonActive(scopeKey, toolId) {
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    $(scope.buttons)?.querySelectorAll(".nettool-btn").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-tool") === toolId);
    });
  }

  function wireNettoolButtons(container, tools, scopeKey) {
    if (!container) return;
    container.querySelectorAll(".nettool-btn").forEach((btn) => {
      btn.addEventListener("click", () => {
        const toolId = btn.getAttribute("data-tool") || "overview";
        nettoolSelected[scopeKey] = toolId;
        syncNettoolButtonActive(scopeKey, toolId);
        const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
        const meta = tools.find((t) => t.id === toolId);
        renderNettoolHelp(meta, scopeKey);
        syncNettoolRouteHash(scopeKey, false);
        if (meta?.install_id && meta.package_installed === false) {
          toast(`Install ${meta.install_id} from Networking packages, then run again.`, false);
          return;
        }
        if (nettoolUsesTerminal(meta)) {
          runNetToolViaTerminal(meta, scopeKey);
          return;
        }
        const targetEl = scope.target ? $(scope.target) : null;
        const hasTarget = (targetEl?.value || "").trim();
        if (!meta?.needs_target || hasTarget) runNetTool(toolId, scopeKey);
      });
    });
  }

  function selectNettool(toolId, scopeKey, opts = {}) {
    const tools = nettoolsLastPayload?.tools || [];
    const id = String(toolId || "").toLowerCase();
    const meta = tools.find((t) => t.id === id);
    if (!meta) return false;
    nettoolSelected[scopeKey] = id;
    syncNettoolButtonActive(scopeKey, id);
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    renderNettoolHelp(meta, scopeKey);
    if (!opts.skipHash) syncNettoolRouteHash(scopeKey, false);
    return true;
  }

  function applyPendingNettool(scopeKey) {
    if (!pendingNettoolTool || pendingNettoolTool.scope !== scopeKey) return;
    const { toolId } = pendingNettoolTool;
    pendingNettoolTool = null;
    if (selectNettool(toolId, scopeKey, { skipHash: true })) {
      syncNettoolRouteHash(scopeKey, true);
      const meta = nettoolMeta(scopeKey, toolId);
      if (nettoolUsesTerminal(meta)) runNetToolViaTerminal(meta, scopeKey);
    }
  }

  function renderNettoolHelp(meta, scopeKey = "adv") {
    const scope = NETTOOL_SCOPES[scopeKey];
    const box = scope?.help ? $(scope.help) : null;
    if (!box) return;
    if (!meta) {
      box.innerHTML = scopeKey === "network"
        ? `<strong class="nettool-help-title">Pick a view above</strong><p class="nettool-help-detail">Read-only snapshots of routes, DNS, interfaces, and active connections on this machine.</p>`
        : `<strong class="nettool-help-title">Pick a tool above</strong><p class="nettool-help-detail">Each button runs a read-only check on this PC. Click a tool to see what it does, then press <strong>Run</strong> or pick a quick target below.</p>`;
      return;
    }
    const needsTarget = !!meta.needs_target;
    const missing = meta.install_id && meta.package_installed === false;
    const targetEl = scope.target ? $(scope.target) : null;
    const hasTarget = !!(targetEl?.value || "").trim();
    const metaParts = [
      needsTarget ? "Needs a target host or IP in the box below" : "No target needed — runs immediately",
      meta.needs_root && meta.terminal_cmd
        ? "Opens Shell — sudo password box appears when needed"
        : (meta.needs_root ? "May show partial output without sudo — try again in Shell if needed" : ""),
      meta.example ? meta.example : (meta.hint || ""),
    ].filter(Boolean);
    const runHint = needsTarget && !hasTarget
      ? "Enter a target (or click a quick target chip below), then press Run."
      : "Click the tool again or press Run to execute.";
    const targetsIntro = scopeKey === "adv" ? $("advNettoolTargetsIntro") : null;
    if (targetsIntro) {
      targetsIntro.textContent = needsTarget
        ? `Quick targets for ${meta.label} — click a chip to run against that host, or type your own target above.`
        : `${meta.label} does not need a target — click Run or the tool button to execute.`;
    }
    box.innerHTML = [
      `<strong class="nettool-help-title">${esc(meta.label || meta.id)}</strong>`,
      `<p class="nettool-help-detail">${esc(meta.detail || meta.hint || "Runs a read-only network check.")}</p>`,
      meta.example && meta.detail ? `<p class="nettool-help-example muted-inline">${esc(meta.example)}</p>` : "",
      `<p class="nettool-help-meta muted-inline">${esc(metaParts.join(" · "))}</p>`,
      `<p class="nettool-help-meta muted-inline">${esc(runHint)}</p>`,
      missing ? `<p class="nettool-help-warn">Package <strong>${esc(meta.install_id)}</strong> is not installed — use Networking packages below or the install button above.</p>` : "",
    ].filter(Boolean).join("");
  }

  function renderNetTools(data, scopeKey = "lab") {
    nettoolsLastPayload = data;
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    const grid = $(scope.buttons);
    const targets = scope.targets ? $(scope.targets) : null;
    const deps = scopeKey === "adv" ? $("advNettoolDeps") : null;
    if (!grid || !data) return;
    let tools = data.tools || [];
    if (scopeKey === "network") {
      tools = tools.filter((t) => NETWORK_SETUP_TOOLS.has(t.id));
    }
    const selected = nettoolSelected[scopeKey] || "overview";
    const ordered = [...tools.filter((t) => !t.needs_root), ...tools.filter((t) => t.needs_root)];
    grid.innerHTML = ordered.length
      ? nettoolButtonHtml(ordered, selected)
      : `<span class="muted-inline nettool-zone-empty">No tools in this view</span>`;
    wireNettoolButtons(grid, tools, scopeKey);
    if (deps && scopeKey === "adv") {
      const missingIds = [...new Set(tools.filter((t) => t.install_id && t.package_installed === false).map((t) => t.install_id))];
      if (missingIds.length) {
        deps.innerHTML = `<p class="help-text"><strong>${missingIds.length} package(s) missing</strong> for diagnostics above — install from Networking packages below or click:</p><div class="actions">${missingIds.map((id) =>
          `<button type="button" class="btn sm primary" data-install-tool="${esc(id)}" data-confirm-message="Install ${esc(id)} for network diagnostics?">Install ${esc(id)}</button>`
        ).join("")}</div>`;
        deps.querySelectorAll("[data-install-tool]").forEach((b) => {
          b.addEventListener("click", () => {
            const id = b.dataset.installTool;
            const cache = toolsPayloadCache;
            const row = cache?.tools?.find((t) => t.id === id);
            if (cache?.can_install) installOptionalTool(id, row?.label || id);
            else if (cache?.can_install_terminal && row?.install_cmd) installToolInTerminal(row.install_cmd, row.label || id);
            else if (row?.install_cmd) copyToolCommand(row.install_cmd, row.label || id);
          });
        });
      } else {
        deps.innerHTML = `<p class="help-text muted-inline">All packages for network diagnostics are installed.</p>`;
      }
    }
    if (targets) {
      targets.innerHTML = (data.default_targets || []).map((t) =>
        `<button type="button" class="nettool-target" data-target="${esc(t)}">${esc(t)}</button>`
      ).join("");
      targets.querySelectorAll(".nettool-target").forEach((btn) => {
        btn.addEventListener("click", () => {
          const inp = scope.target ? $(scope.target) : null;
          const targetVal = btn.getAttribute("data-target") || "";
          if (inp) inp.value = targetVal;
          const meta = tools.find((t) => t.id === nettoolSelected[scopeKey]);
          renderNettoolHelp(meta, scopeKey);
          btn.title = meta
            ? `Run ${meta.label} against ${targetVal}`
            : targetVal;
          runNetTool(nettoolSelected[scopeKey], scopeKey);
        });
      });
    }
    const selectedMeta = tools.find((t) => t.id === (nettoolSelected[scopeKey] || selected));
    renderNettoolHelp(selectedMeta, scopeKey);
    applyPendingNettool(scopeKey);
    if (scopeKey === "adv" && data.overview && nettoolSelected.adv === "overview") {
      renderNetToolOutput(data.overview, "adv");
    }
    if (scopeKey === "network" && grid.dataset.loaded !== "1") {
      grid.dataset.loaded = "1";
      if (nettoolSelected.network === "overview") runNetTool("overview", "network");
    }
  }

  function networkSetupQuickButtonHtml(commands, startIdx) {
    return commands.map((c, i) => {
      const idx = startIdx + i;
      const sudoTag = c.sudo ? '<span class="term-sudo-tag">sudo</span>' : "";
      const sudoHint = c.sudo ? " — opens Shell; password box when needed" : "";
      return `<button type="button" class="btn sm netsetup-quick-btn${c.sudo ? " term-quick-sudo" : ""}" data-setup-idx="${idx}" data-no-confirm="1" title="${esc((c.cmd || "").trim())}${sudoHint}">${esc(c.label)}${sudoTag}</button>`;
    }).join("");
  }

  function wireNetworkSetupQuickButtons(root) {
    root?.querySelectorAll(".netsetup-quick-btn").forEach((b) => {
      b.addEventListener("click", async () => {
        const c = networkSetupQuickCommands[Number(b.dataset.setupIdx)];
        if (!c) return;
        if (c.sudo) {
          await termRunCommand(c.cmd || "", c.label || "", { scope: "network" });
          return;
        }
        const out = $("networkSetupOutput");
        const help = $("networkSetupHelp");
        if (out) out.textContent = `Running ${c.label || "command"}…`;
        if (help) {
          const titleEl = help.querySelector(".nettool-help-title");
          const detailEl = help.querySelector(".nettool-help-detail");
          if (titleEl) titleEl.textContent = c.label || "Quick command";
          if (detailEl) detailEl.textContent = "Output appears below and in Tools → Activity log.";
        }
        b.disabled = true;
        try {
          const timeout = /lynis|rkhunter|chkrootkit|clamscan/i.test(c.cmd || "") ? 3600 : 600;
          const r = await api("/api/terminal/run-once", {
            method: "POST",
            body: JSON.stringify({ cmd: c.cmd, label: c.label, timeout }),
          });
          if (out) out.textContent = r.output || r.error || "(no output)";
          loadLogsQuiet();
          toast(r.ok ? `${c.label} finished` : `${c.label} failed`, r.ok);
        } catch (e) {
          if (out) out.textContent = formatFetchError(e);
          toast(formatFetchError(e), false);
        } finally {
          b.disabled = false;
        }
      });
    });
  }

  async function loadNetworkSetupQuickCommands(force = false) {
    const box = $("networkSetupQuick");
    if (!box) return;
    try {
      const q = await apiCached("/api/terminal/commands?scope=network", {}, force ? 0 : CACHE_TTL.tools);
      networkSetupQuickCommands = sortCommandsSudoLast(q.commands || []);
      box.innerHTML = networkSetupQuickCommands.length
        ? networkSetupQuickButtonHtml(networkSetupQuickCommands, 0)
        : `<span class="muted-inline nettool-zone-empty">No quick commands</span>`;
      wireNetworkSetupQuickButtons(box);
    } catch (_) { /* ignore */ }
  }

  async function runNetTool(tool, scopeKey = "lab") {
    const scope = NETTOOL_SCOPES[scopeKey] || NETTOOL_SCOPES.adv;
    const selected = tool || nettoolSelected[scopeKey] || "overview";
    nettoolSelected[scopeKey] = selected;
    const meta = nettoolMeta(scopeKey, selected);
    if (nettoolUsesTerminal(meta)) {
      return runNetToolViaTerminal(meta, scopeKey);
    }
    const target = scope.target ? String($(scope.target)?.value || "").trim() : "";
    const out = $(scope.output);
    if (out) out.textContent = selected === "traceroute" || selected === "iperf3" ? "Running… (may take up to 45s)" : "Running…";
    const timeoutMs = (selected === "traceroute" || selected === "iperf3" || selected === "nmap") ? 65000 : 25000;
    try {
      const result = await api("/api/nettools/run", {
        method: "POST",
        body: JSON.stringify({ tool: selected, target }),
        timeoutMs,
      });
      renderNetToolOutput(result, scopeKey, meta);
      logActivity("nettools", `${result.label || selected}${target ? " " + target : ""}`, result.ok);
    } catch (e) {
      const msg = String(e?.name === "AbortError" ? "Timed out — try again or pick a closer target." : e);
      renderNetToolOutput({ ok: false, label: selected, tool: selected, error: msg }, scopeKey, meta);
    }
  }

  function renderServicePanel(svc) {
    if (!svc) return;
    const ui = svc.ui || {};
    const nord = svc.nordvpnd || {};
    const uiOn = ui.active || ui.manual_running;
    $("svcUiBadge") && ($("svcUiBadge").textContent = ui.active ? "Running" : (ui.manual_running ? "Manual" : "Stopped"));
    $("svcUiBadge")?.classList.toggle("on", !!uiOn);
    $("svcPageBadge") && ($("svcPageBadge").textContent = uiOn ? "UI running" : "UI stopped");
    $("svcPageBadge")?.classList.toggle("on", !!uiOn);
    $("setupSvcBadge") && ($("setupSvcBadge").textContent = nord.active ? "nordvpnd on" : "nordvpnd off");
    $("setupSvcBadge")?.classList.toggle("on", !!nord.active);
    $("svcNordBadge") && ($("svcNordBadge").textContent = nord.active ? "Active" : (nord.status_text || "—"));
    $("svcNordBadge")?.classList.toggle("on", !!nord.active);
    const trayOn = svc.tray_autostart && svc.tray_enabled;
    $("svcTrayBadge") && ($("svcTrayBadge").textContent = trayOn ? "Autostart" : "Off");
    $("svcTrayBadge")?.classList.toggle("on", trayOn);
    const na = svc.network_access || {};
    const dashCell = na.lan_enabled && (na.urls?.lan || []).length
      ? statCell(
          "Dashboard (LAN)",
          `<div class="panel-nav-actions" style="margin:0">${(na.urls.lan || []).map((u) => openUrlBtn(u, u)).join("")}</div>`,
          "warn"
        )
      : statCell("Dashboard", openUrlBtn(ui.url || na.urls?.this_browser, ui.url || na.urls?.this_browser || "Open dashboard"));
    $("svcUiStats") && ($("svcUiStats").innerHTML = [
      statCell("Status", ui.active ? "systemd active" : (ui.manual_running ? "manual process" : ui.status_text || "—"), uiOn ? "on" : "off"),
      statCell("At login", ui.enabled_at_login ? "enabled" : "disabled"),
      statCell("Unit file", ui.installed ? "installed" : "not installed"),
      dashCell,
    ].join(""));
    $("svcNordStats") && ($("svcNordStats").innerHTML = [
      statCell("Status", nord.status_text || "—", nord.active ? "on" : "off"),
      statCell("At boot", nord.enabled_at_boot ? "enabled" : nord.enabled_text || "—"),
    ].join(""));
    $("svcTrayStats") && ($("svcTrayStats").innerHTML = [
      statCell("Tray", svc.tray_enabled ? "enabled in config" : "not enabled"),
      statCell("Autostart", svc.tray_autostart ? "yes" : "no"),
    ].join(""));
    const hints = [];
    if (ui.manual_running && ui.active) hints.push("Both systemd and a manual nordctl serve are running — stop one to avoid port conflicts.");
    else if (ui.manual_running) hints.push(`Manual serve running (PIDs: ${(ui.manual_pids || []).join(", ")}) — install service to survive logout.`);
    if (!ui.installed) hints.push("Install service writes ~/.config/systemd/user/nordctl-ui.service");
    if (na.lan_enabled) hints.push("LAN access is enabled — phones and other PCs on your network can open this dashboard.");
    $("svcUiHint") && ($("svcUiHint").textContent = hints.join(" "));
    renderNetworkAccess(na);
    renderTermAccessNote(na);
    bindOpenUrlButtons($("svcUiStats"));
  }

  function renderNetworkAccess(na, opts = {}) {
    const boxId = opts.boxId || "networkAccessBox";
    const badgeId = opts.badgeId || "netAccessBadge";
    const applyBtnId = opts.applyBtnId || "btnNetAccessApply";
    const customIpId = opts.customIpId || "netAccessCustomIp";
    const box = $(boxId);
    const badge = badgeId ? $(badgeId) : null;
    if (!box || !na?.ok) return;
    if (badge) {
      badge.textContent = na.loopback_only ? "This PC only" : "LAN enabled";
      badge.className = "badge " + (na.loopback_only ? "on" : "warn");
    }
    const modes = [
      { id: "local", label: "This computer only", hint: "Safest — listens on 127.0.0.1. Other devices cannot connect." },
      { id: "lan", label: "Home LAN (192.168.x, 10.x, …)", hint: "Reachable from phones, tablets, and other PCs on the same WiFi or wired network." },
      { id: "custom", label: "One LAN address", hint: "Bind to a single network interface IP only." },
    ];
    let html = "";
    if (na.loopback_only) {
      html += `<p class="help-text">Currently <strong>local only</strong> — use this dashboard URL on this PC:</p>`;
      html += `<div class="panel-nav-actions">${openUrlBtn(na.urls?.this_browser, na.urls?.this_browser || "Open dashboard")}</div>`;
    } else {
      html += `<p class="help-text"><strong>LAN share is ON.</strong> Open the dashboard from another device:</p>`;
      html += `<div class="panel-nav-actions">${(na.urls?.lan || []).map((u) => openUrlBtn(u, u)).join("") || '<span class="muted">No LAN IPs detected</span>'}</div>`;
    }
    (na.warnings || []).forEach((w) => { html += `<p class="msg warn net-access-warn">${esc(w)}</p>`; });
    html += '<div class="net-access-modes">';
    modes.forEach((m) => {
      const on = na.mode === m.id;
      html += `<label class="net-access-mode${on ? " active" : ""}"><input type="radio" name="netAccessMode" value="${esc(m.id)}"${on ? " checked" : ""} /> <strong>${esc(m.label)}</strong><span class="muted">${esc(m.hint)}</span></label>`;
    });
    html += "</div>";
    if ((na.lan_ips || []).length) {
      html += `<select id="${esc(customIpId)}" class="full-select${na.mode === "custom" ? "" : " hidden"}">`;
      (na.lan_ips || []).forEach((row) => {
        html += `<option value="${esc(row.ip)}"${na.bind === row.ip ? " selected" : ""}>${esc(row.iface)} — ${esc(row.ip)} (${esc(row.subnet_hint)})</option>`;
      });
      html += "</select>";
    } else if (na.mode === "custom") {
      html += `<p class="msg warn">No private LAN IPs found. Connect to WiFi or Ethernet first, or use Home LAN mode.</p>`;
    }
    html += `<div class="actions"><button type="button" class="btn sm primary" id="${esc(applyBtnId)}" data-confirm="1">Apply &amp; restart UI</button></div>`;
    html += `<p class="help-text muted-inline">Listening on <code>${esc(na.bind)}:${na.port}</code>. After apply, the page may reload — use the LAN URL from another device if you enabled LAN.</p>`;
    box.innerHTML = html;
    bindOpenUrlButtons(box);
    box.querySelectorAll('input[name="netAccessMode"]').forEach((r) => {
      r.addEventListener("change", () => {
        $(customIpId)?.classList.toggle("hidden", r.value !== "custom");
        box.querySelectorAll(".net-access-mode").forEach((lbl) => {
          lbl.classList.toggle("active", lbl.querySelector("input")?.checked);
        });
      });
    });
    $(applyBtnId)?.addEventListener("click", (ev) => applyNetworkAccess(ev, { customIpId }));
  }

  async function applyNetworkAccess(ev, opts = {}) {
    const customIpId = opts.customIpId || "netAccessCustomIp";
    const mode = boxRadioValue("netAccessMode") || "local";
    const bind = mode === "custom" ? ($(customIpId)?.value || "") : null;
    if (mode === "custom" && !bind) {
      toast("Pick a LAN IP from the dropdown", false);
      return;
    }
    if (mode === "lan") {
      const ok = confirm(
        "Enable LAN access?\n\nAny device on your home network (192.168.x, 10.x, …) will be able to open this dashboard and use the Terminal tab (full shell).\n\nOnly continue on a network you trust."
      );
      if (!ok) return;
    }
    showNotice("Saving network access and restarting the UI…", { ok: true, title: "Network access" });
    const res = await doAction(
      { action: "set_server_access", mode, bind, restart: true },
      "Network access"
    );
    if (res.ok) {
      const steps = (res.steps || res.next_steps || []).filter(Boolean);
      const body = [
        esc(res.human || "Network access updated."),
        steps.length ? `<br><br><strong>Next:</strong><br>${steps.map((s) => esc(s)).join("<br>")}` : "",
        !res.loopback_only && (res.urls?.lan || []).length
          ? `<br><br>From another device, open:<br>${(res.urls.lan || []).map((u) => openUrlBtn(u, u)).join("<br>")}`
          : "",
      ].join("");
      showNotice(body, { ok: true, title: "Network access saved", html: true });
    }
  }

  function boxRadioValue(name) {
    const el = document.querySelector(`input[name="${name}"]:checked`);
    return el ? el.value : "";
  }

  function sudoBashScript(scriptPath) {
    const p = String(scriptPath || "").trim();
    if (!p) return "";
    if (/^sudo\s+bash\s+/i.test(p)) return p;
    return `sudo bash ${p}`;
  }

  function renderListeners(data) {
    const err = $("listenersErr");
    const body = $("listenersBody");
    const badge = $("listenersBadge");
    const hint = $("listenersHint");
    if (!body) return;
    if (!data?.ok) {
      err?.classList.remove("hidden");
      if (err) err.textContent = data?.error || "Could not read listeners";
      if (badge) { badge.textContent = "—"; badge.className = "badge off"; }
      body.innerHTML = `<tr class="empty-row"><td colspan="4">Could not read listeners</td></tr>`;
      return;
    }
    err?.classList.add("hidden");
    const sum = data.summary || {};
    const set = (id, text) => { const el = $(id); if (el) el.textContent = text; };
    set("listenersMetricTotal", String(sum.total ?? 0));
    set("listenersMetricNamed", String(sum.named ?? 0));
    set("listenersMetricLan", String(sum.lan_exposed ?? 0));
    if (badge) {
      badge.textContent = `${sum.total ?? 0} open`;
      badge.className = "badge " + ((sum.lan_exposed ?? 0) > 0 ? "warn" : "on");
    }
    if (hint) hint.innerHTML = data.hint || data.message || "";
    const rows = data.listeners || [];
    if (!rows.length) {
      body.innerHTML = `<tr class="empty-row"><td colspan="4">No TCP listeners found</td></tr>`;
      return;
    }
    body.innerHTML = rows.map((row) => {
      const scope = row.scope === "localhost"
        ? '<span class="badge ok">localhost</span>'
        : '<span class="badge warn">LAN</span>';
      const proc = row.process
        ? `<span class="proc">${esc(row.process)}</span>`
        : '<span class="muted">—</span>';
      return `<tr><td>${esc(row.proto || "tcp")}</td><td class="host">${esc(row.addr || "")}</td><td>${scope}</td><td>${proc}</td></tr>`;
    }).join("");
  }

  async function loadListeners(force) {
    try {
      const data = await apiCached("/api/listeners", {}, force ? 0 : CACHE_TTL.listeners);
      renderListeners(data);
      if (force) {
        logActivity("listeners", `Listeners — ${data.summary?.total ?? 0} TCP sockets`, data.ok, data.error || "");
      }
      return data;
    } catch (e) {
      renderListeners({ ok: false, error: String(e) });
      return null;
    }
  }

  function renderPrivileges(priv) {
    const box = $("privilegeBox");
    if (!box || !priv) return;
    const ok = !!priv.ui_privileges_ok;
    if ($("privBadge")) {
      $("privBadge").textContent = ok ? "Ready" : "Setup needed";
      $("privBadge").className = "badge " + (ok ? "on" : "off");
    }
    if ($("privMetricSudo")) $("privMetricSudo").textContent = priv.sudo_installed ? "Yes" : "No";
    if ($("privMetricUi")) $("privMetricUi").textContent = ok ? "OK" : "Missing";
    if ($("privMetricPwless")) $("privMetricPwless").textContent = priv.passwordless_sudo ? "Yes" : "No";
    const nord = priv.nordctl_privileges || {};
    const flags = [
      ["sudo", priv.sudo_installed ? "installed" : "missing"],
      ["Nordctl UI fixes", priv.ui_privileges_ok ? "yes" : (nord.sudoers_installed ? "partial" : "no")],
      ["Full passwordless sudo", priv.passwordless_sudo ? "yes" : "no"],
      ["nordvpn group", priv.nordvpn_group ? "member" : "not member"],
    ];
    let html = '<div class="stat-grid">';
    flags.forEach(([k, v]) => {
      const good = v === "yes" || v === "member" || v === "installed";
      const warn = v === "partial";
      html += statCell(k, v, good ? "on" : warn ? "warn" : "off");
    });
    html += "</div>";
    if (nord.sudoers_installed) {
      html += '<div class="stat-grid" style="margin-top:0.5rem">';
      html += statCell("UFW (passwordless)", nord.ufw_passwordless ? "yes" : "no", nord.ufw_passwordless ? "on" : "off");
      html += statCell("IPv6 fix", nord.ipv6_passwordless ? "yes" : (nord.ipv6_rules_installed ? "rules only" : "no"), nord.ipv6_passwordless ? "on" : "off");
      html += statCell("resolv chattr", nord.resolv_passwordless ? "yes" : (nord.resolv_rules_installed ? "rules only" : "no"), nord.resolv_passwordless ? "on" : "off");
      html += "</div>";
    }
    (priv.notes || []).forEach((n) => { html += `<p class="help-text">${esc(n)}</p>`; });
    if (priv.manual_sudo_hint && !priv.ui_privileges_ok) {
      html += `<p class="help-text mono">${esc(priv.manual_sudo_hint)}</p>`;
    }
    const scripts = priv.install_scripts || {};
    if (scripts.privileges && !priv.ui_privileges_ok) {
      html += `<p class="help-text">Install nordctl UI fixes:<br><code>sudo bash ${esc(scripts.privileges)}</code></p>`;
    }
    if (scripts.ufw) {
      html += `<p class="help-text muted-inline">UFW-only setup: Network & Security → Linux UFW — <code>sudo bash ${esc(scripts.ufw)}</code></p>`;
    }
    box.innerHTML = html;
  }

  async function loadPrivileges(force) {
    try {
      invalidateApiCache("/api/state");
      invalidateApiCache("/api/state/quick");
      invalidateApiCache("/api/state/app");
      invalidateApiCache("/api/state/nord");
      invalidateApiCache("/api/state/network");
      invalidateApiCache("/api/security");
      invalidateApiCache("/api/security/summary");
      const st = await fetchSplitState(true);
      if (st?.privileges) {
        lastState = { ...(lastState || {}), privileges: st.privileges };
        renderPrivileges(st.privileges);
      }
      return st?.privileges;
    } catch (e) {
      reportActionError("Privileges check failed", e, "Re-checking sudo");
      return null;
    }
  }

  async function waitForUiOnline(maxMs = 25000) {
    const start = Date.now();
    while (Date.now() - start < maxMs) {
      try {
        const r = await fetch("/api/state", { cache: "no-store" });
        if (r.ok) return true;
      } catch (_) { /* server down during restart */ }
      await new Promise((resolve) => setTimeout(resolve, 800));
    }
    return false;
  }

  async function serviceAction(target, op) {
    const body = target === "ui"
      ? { action: "service_ui", op }
      : { action: "service_nordvpnd", op };
    if (target === "ui" && op === "restart") {
      suppressFetchErrorsUntil = Date.now() + 45000;
    }
    const res = await doAction(body, `Service ${target} ${op}`);
    if (!res.ok && res.manual) toast(res.manual, false);
    if (target === "ui" && op === "restart" && (res.ok || res.reconnecting) && (res.scheduled || res.reconnecting)) {
      toast(res.note || "Restarting UI…", true);
      const back = await waitForUiOnline();
      if (back) {
        toast("UI is back online", true);
        refreshAll(true);
      } else {
        toast("Still restarting — refresh the page in a few seconds", false);
      }
    }
    return res;
  }

  let securityBwTimer = null;
  let secStatusUrl = "";
  const liveBwHistory = { rx: [], tx: [] };
  const LIVE_BW_HISTORY_MAX = 48;
  let liveBwPeakBps = 0;
  let liveBwChartBound = false;

  const HEALTH_HIST_KEY = "nordctl_health_hist";
  const SYS_HIST_MAX = 36;
  const TRAFFIC_HIST_MAX = 48;
  const WIFI_SIG_HIST_MAX = 48;
  const sysHist = { cpu: [], ram: [], disk: [] };
  const trafficWanHist = { down: [], up: [] };
  const trafficLanHist = { lan: [], mesh: [] };
  const trafficSessHist = { local: [] };
  const wifiSignalHist = [];

  function chartsApi() {
    return window.NordctlCharts;
  }

  function scoreChartColor(score) {
    const s = Number(score) || 0;
    if (s >= 80) return "#4ade80";
    if (s >= 60) return "#fbbf24";
    return "#f87171";
  }

  function getHealthHist() {
    try {
      const raw = JSON.parse(localStorage.getItem(HEALTH_HIST_KEY) || "[]");
      return Array.isArray(raw) ? raw : [];
    } catch (_) {
      return [];
    }
  }

  function recordHealthScore(score) {
    const s = Number(score);
    if (!Number.isFinite(s)) return;
    const hist = getHealthHist().filter((r) => Date.now() - (r.t || 0) < 30 * 86400000);
    hist.push({ t: Date.now(), score: s });
    while (hist.length > 60) hist.shift();
    localStorage.setItem(HEALTH_HIST_KEY, JSON.stringify(hist));
  }

  function drawSecHealthCharts(health) {
    const C = chartsApi();
    if (!C) return;
    const checks = health?.checks || [];
    const pass = checks.filter((c) => c.ok).length;
    const fail = checks.length - pass;
    C.drawDonut($("secHealthDonut"), [
      { label: "Pass", value: pass, color: "#4ade80" },
      { label: "Review", value: fail, color: "#fbbf24" },
    ], {
      centerText: String(health?.score ?? "—"),
      centerSub: health?.grade || "score",
      height: 140,
    });
    const hist = getHealthHist();
    C.drawMultiLine($("secHealthTrend"), [{
      values: hist.map((r) => r.score),
      color: scoreChartColor(health?.score),
    }], { height: 140, minMax: 100, fmtY: (v) => `${Math.round(v)}` });
    const fill = $("secScoreRingFill");
    if (fill) C.setSvgRing(fill, health?.score ?? 0, { color: scoreChartColor(health?.score) });
  }

  function drawLeakLabCharts(lab) {
    const C = chartsApi();
    if (!C || !lab) return;
    const pass = Number(lab.score) || 0;
    const total = Number(lab.total) || 1;
    const fail = Math.max(0, total - pass);
    C.drawDonut($("labScoreDonut"), [
      { label: "Pass", value: pass, color: "#4ade80" },
      { label: "Fail", value: fail, color: "#f87171" },
    ], { centerText: `${pass}/${total}`, centerSub: "passed", height: 140 });
    C.renderHBarList($("labTestBars"), (lab.tests || []).map((t) => ({
      label: t.name,
      value: t.ok ? 1 : 0.35,
      display: t.ok ? "Pass" : "Check",
      color: t.ok ? "#4ade80" : "#f87171",
    })), { empty: "Run leak tests to see per-test bars." });
  }

  function drawAuditCategoryChart(data) {
    const C = chartsApi();
    if (!C || !data?.categories?.length) {
      C?.drawBars($("overallAuditChart"), [], { height: 180 });
      return;
    }
    const colors = ["#22d3ee", "#818cf8", "#c084fc", "#fbbf24", "#4ade80", "#fb7185"];
    C.drawBars($("overallAuditChart"), data.categories.map((cat, i) => ({
      label: String(cat.label || "Cat").slice(0, 8),
      value: cat.total ? (cat.passed / cat.total) * 100 : 0,
      color: colors[i % colors.length],
    })), { height: 180, showValues: true });
  }

  function pushTrafficMapHistory(data) {
    const C = chartsApi();
    if (!C || !data?.ok) return;
    const s = data.summary || {};
    const c = data.counts || {};
    C.pushBuffer(trafficWanHist.down, Number(s.wan_down_mbps) || 0, TRAFFIC_HIST_MAX);
    C.pushBuffer(trafficWanHist.up, Number(s.wan_up_mbps) || 0, TRAFFIC_HIST_MAX);
    C.pushBuffer(trafficLanHist.lan, Number(s.lan_down_mbps) || 0, TRAFFIC_HIST_MAX);
    C.pushBuffer(trafficLanHist.mesh, Number(s.mesh_down_mbps) || 0, TRAFFIC_HIST_MAX);
    C.pushBuffer(trafficSessHist.local, Number(c.local_sessions) || 0, TRAFFIC_HIST_MAX);
  }

  function drawTrafficMapCharts() {
    const C = chartsApi();
    if (!C) return;
    C.drawMultiLine($("trafficWanChart"), [
      { values: trafficWanHist.down, color: "#22d3ee" },
      { values: trafficWanHist.up, color: "#c084fc" },
    ], { height: 120, maxPoints: TRAFFIC_HIST_MAX });
    C.drawMultiLine($("trafficLanChart"), [
      { values: trafficLanHist.lan, color: "#4ade80" },
      { values: trafficLanHist.mesh, color: "#818cf8" },
    ], { height: 120, maxPoints: TRAFFIC_HIST_MAX });
    C.drawMultiLine($("trafficSessionChart"), [
      { values: trafficSessHist.local, color: "#fbbf24" },
    ], { height: 120, maxPoints: TRAFFIC_HIST_MAX, minMax: 1 });
  }

  function pushWifiSignalSample(sig) {
    const C = chartsApi();
    if (!C) return;
    const n = Number(sig);
    if (!Number.isFinite(n)) return;
    C.pushBuffer(wifiSignalHist, n, WIFI_SIG_HIST_MAX);
  }

  function drawWifiCharts(nearby) {
    const C = chartsApi();
    if (!C) return;
    C.drawMultiLine($("wifiSignalChart"), [{
      values: wifiSignalHist,
      color: "#4ade80",
    }], { height: 100, maxPoints: WIFI_SIG_HIST_MAX, minMax: 100 });
    const nets = (nearby || []).slice(0, 8);
    C.renderHBarList($("wifiNearbyBars"), nets.map((n) => ({
      label: n.ssid || "—",
      value: Number(n.signal) || 0,
      display: `${n.signal || 0}%`,
      color: n.in_use ? "#5eead4" : "#64748b",
    })), { empty: "Rescan to chart nearby networks." });
  }

  function recordSysHist(data) {
    const C = chartsApi();
    if (!C || !data?.ok) return;
    const cores = data.load?.cores || 1;
    const cpuPct = data.load?.pct ?? (cores ? (100 * Number(data.load?.["1m"] || 0)) / cores : 0);
    C.pushBuffer(sysHist.cpu, cpuPct, SYS_HIST_MAX);
    C.pushBuffer(sysHist.ram, Number(data.memory?.used_pct) || 0, SYS_HIST_MAX);
    C.pushBuffer(sysHist.disk, Number(data.disk?.used_pct) || 0, SYS_HIST_MAX);
    drawTopbarSparklines();
  }

  function drawTopbarSparklines() {
    const C = chartsApi();
    if (!C) return;
    C.drawSparkline($("sparkCpu"), sysHist.cpu, "#22d3ee", { height: 18, fill: "rgba(34,211,238,0.12)" });
    C.drawSparkline($("sparkRam"), sysHist.ram, "#c084fc", { height: 18, fill: "rgba(192,132,252,0.12)" });
    C.drawSparkline($("sparkDisk"), sysHist.disk, "#fbbf24", { height: 18, fill: "rgba(251,191,36,0.12)" });
  }

  function drawConnJournalChart(entries) {
    const C = chartsApi();
    if (!C) return;
    const buckets = C.bucketByDay(entries || [], 7);
    C.drawBars($("connJournalChart"), buckets.map((b) => ({
      label: b.label,
      value: b.value,
      color: b.fail ? "#f87171" : "#4ade80",
    })), { height: 120 });
  }

  function drawLogsActivityChart(entries) {
    const C = chartsApi();
    if (!C) return;
    const buckets = C.bucketLogsByHour(entries || [], 24);
    C.drawMultiLine($("logsActivityChart"), [{
      values: buckets,
      color: "#818cf8",
    }], { height: 100, maxPoints: 24, minMax: 1 });
  }

  function drawDnsAssistantChart(findings) {
    const C = chartsApi();
    if (!C) return;
    const list = findings || [];
    const detected = list.filter((f) => f.detected).length;
    const active = list.filter((f) => f.active).length;
    const clear = Math.max(0, list.length - detected);
    C.drawDonut($("secDnsChart"), [
      { label: "Clear", value: clear, color: "#4ade80" },
      { label: "Detected", value: Math.max(0, detected - active), color: "#64748b" },
      { label: "Conflict", value: active, color: "#fbbf24" },
    ], { centerText: String(active), centerSub: active ? "conflicts" : "clear", height: 120 });
  }

  function drawCaptureProtocolChart(summary) {
    const C = chartsApi();
    const panel = $("secCaptureChartPanel");
    if (!C || !panel) return;
    const segs = C.parseProtocolCounts(summary || []);
    if (!segs.length) {
      panel.classList.add("hidden");
      return;
    }
    panel.classList.remove("hidden");
    C.drawDonut($("secCaptureChart"), segs, {
      centerText: String(summary.length),
      centerSub: "packets",
      height: 140,
    });
  }

  const SPECTRUM_BANDS_KEY = "nordctl_spectrum_bands";
  const SPECTRUM_WIFI_CH5 = [36, 40, 44, 48, 52, 56, 60, 64, 100, 104, 108, 112, 116, 120, 124, 128, 132, 136, 140, 144, 149, 153, 157, 161, 165];
  let spectrumData = null;
  let spectrumLiveTimer = null;
  let spectrumChartBound = false;
  let spectrumZoomBound = false;
  let spectrumBandsEnabled = {};
  let spectrumView = { mhzMin: null, mhzMax: null };
  let spectrumPan = { active: false, startX: 0, startMin: 0, startMax: 0 };
  let spectrumFocusKey = null;
  let spectrumSsidUiBound = false;

  function resetSpectrumView() {
    spectrumView = { mhzMin: null, mhzMax: null };
    spectrumFocusKey = null;
  }

  function spectrumNetKey(n) {
    return `${n?.ssid || ""}|${n?.mhz ?? ""}|${n?.bssid || ""}|${n?.channel ?? ""}`;
  }

  function spectrumNetColorIndex(n, scan) {
    const list = scan || spectrumData?.scan || [];
    const idx = list.findIndex((x) => spectrumNetKey(x) === spectrumNetKey(n));
    return idx >= 0 ? idx : 0;
  }

  function spectrumNetColor(n, scan) {
    return rfBellColor(spectrumNetColorIndex(n, scan));
  }

  function spectrumFindNet(key) {
    return (spectrumData?.scan || []).find((n) => spectrumNetKey(n) === key) || null;
  }

  function spectrumCenterOnNetwork(net) {
    if (!net || net.mhz == null) return;
    if (net.band_id) {
      spectrumBandsEnabled[net.band_id] = true;
      saveSpectrumBandPrefs();
      renderSpectrumBandSwitches(spectrumData?.all_bands || spectrumData?.bands);
    }
    const span = net.band_id === "2g" ? 58 : net.band_id === "6g" ? 160 : 130;
    const mid = Number(net.mhz);
    let vMin = mid - span / 2;
    let vMax = mid + span / 2;
    const bins = filteredSpectrumBins(spectrumData || {});
    const full = spectrumAutoFitRange(bins, spectrumData?.scan || []) || { min: vMin - 40, max: vMax + 40 };
    if (vMin < full.min) {
      vMax += full.min - vMin;
      vMin = full.min;
    }
    if (vMax > full.max) {
      vMin -= vMax - full.max;
      vMax = full.max;
    }
    if (vMax - vMin < 40) {
      const c = (vMin + vMax) / 2;
      vMin = c - 50;
      vMax = c + 50;
    }
    spectrumView = { mhzMin: vMin, mhzMax: vMax };
    spectrumFocusKey = spectrumNetKey(net);
    renderSpectrumCharts();
    renderSpectrumSsidButtons();
    renderSpectrumScanTable();
  }

  function spectrumFullRange(bins) {
    if (!bins.length) return { min: 0, max: 1 };
    return { min: bins[0].mhz, max: bins[bins.length - 1].mhz };
  }

  function spectrumFilteredScan(scan) {
    return (scan || []).filter((n) => {
      if (!n.band_id) return true;
      return spectrumBandsEnabled[n.band_id] !== false;
    });
  }

  function spectrumHiddenScan(scan) {
    return (scan || []).filter((n) => n.band_id && spectrumBandsEnabled[n.band_id] === false);
  }

  function spectrumEnabledBands() {
    const bands = spectrumData?.all_bands || spectrumData?.bands || [];
    return bands.filter((b) => spectrumBandsEnabled[b.id] !== false);
  }

  function spectrumBandIdForMhz(mhz, bands) {
    for (const b of bands || []) {
      if (mhz >= b.mhz_min && mhz < b.mhz_max) return b.id;
    }
    return null;
  }

  function spectrumWifiChannelCatalog(bands) {
    const rows = [];
    for (let ch = 1; ch <= 13; ch++) {
      rows.push({ channel: ch, mhz: 2407 + ch * 5, band_id: "2g" });
    }
    rows.push({ channel: 14, mhz: 2484, band_id: "2g" });
    for (const ch of SPECTRUM_WIFI_CH5) {
      const mhz = 5000 + ch * 5;
      const band_id = spectrumBandIdForMhz(mhz, bands) || "5g_unii1";
      rows.push({ channel: ch, mhz, band_id });
    }
    for (let ch = 1; ch <= 233; ch += 4) {
      const mhz = 5950 + ch * 5;
      const band_id = spectrumBandIdForMhz(mhz, bands);
      if (band_id === "6g") rows.push({ channel: ch, mhz, band_id });
    }
    return rows;
  }

  function spectrumChannelTicks(mhzMin, mhzMax, bands, scan) {
    const seen = new Set();
    const ticks = [];
    const add = (channel, mhz, band_id) => {
      if (channel == null || mhz == null) return;
      if (band_id && spectrumBandsEnabled[band_id] === false) return;
      if (mhz < mhzMin - 4 || mhz > mhzMax + 4) return;
      const key = `${channel}@${mhz}`;
      if (seen.has(key)) return;
      seen.add(key);
      ticks.push({ channel, mhz, band_id });
    };
    for (const t of spectrumWifiChannelCatalog(bands)) add(t.channel, t.mhz, t.band_id);
    for (const n of scan || []) add(n.channel, n.mhz, n.band_id);
    return ticks.sort((a, b) => a.mhz - b.mhz);
  }

  function spectrumEmptyMessage(scan) {
    const hidden = spectrumHiddenScan(scan);
    if (hidden.length) {
      const hints = hidden.map((n) => {
        const band = spectrumBandLabel(n.band_id, spectrumData?.all_bands);
        return `<strong>${esc(n.ssid)}</strong> is on ${esc(band)} (ch ${esc(String(n.channel || "?"))}) — enable that band above`;
      });
      return `No networks on the bands you have selected. ${hints.join(" · ")}`;
    }
    const sel = spectrumEnabledBands().map((b) => b.short || b.label).join(", ");
    return `No WiFi networks on ${esc(sel || "selected bands")} in this scan — try <strong>Rescan WiFi</strong>.`;
  }

  /** Default MHz window — wide enough for bell curves and labels when few channels scan. */
  function spectrumAutoFitRange(allBins, scan) {
    const nets = spectrumFilteredScan(scan);
    const binMhz = (allBins || []).map((b) => b.mhz).filter((v) => Number.isFinite(v));
    const netMhz = nets.map((n) => n.mhz).filter((v) => Number.isFinite(v));
    let values = [...new Set([...binMhz, ...netMhz])];
    if (!values.length) {
      const enabled = spectrumEnabledBands();
      if (enabled.length) {
        const min = Math.min(...enabled.map((b) => b.mhz_min));
        const max = Math.max(...enabled.map((b) => b.mhz_max));
        return { min: min - 16, max: max + 16 };
      }
      return null;
    }
    let min = Math.min(...values);
    let max = Math.max(...values);
    const rawSpan = max - min;
    const has5g = values.some((v) => v >= 4900);
    const has2g = values.some((v) => v < 3000);
    let minSpan = has5g && !has2g ? 130 : has2g && !has5g ? 50 : 150;
    if (rawSpan < 8) {
      const mid = (min + max) / 2;
      min = mid - minSpan / 2;
      max = mid + minSpan / 2;
    } else if (rawSpan < minSpan) {
      const mid = (min + max) / 2;
      min = mid - minSpan / 2;
      max = mid + minSpan / 2;
    }
    const edgePad = 32;
    return { min: min - edgePad, max: max + edgePad };
  }

  function spectrumVisibleRange(bins, scan) {
    const fit = spectrumAutoFitRange(bins, scan);
    const full = fit || spectrumFullRange(bins);
    const userZoomed = spectrumView.mhzMin != null || spectrumView.mhzMax != null;
    let vmin = userZoomed ? spectrumView.mhzMin : full.min;
    let vmax = userZoomed ? spectrumView.mhzMax : full.max;
    if (vmin == null || vmax == null) {
      vmin = full.min;
      vmax = full.max;
    }
    if (vmax - vmin < 50) {
      const mid = (vmin + vmax) / 2;
      vmin = mid - 65;
      vmax = mid + 65;
    }
    if (userZoomed) {
      vmin = Math.max(full.min, vmin);
      vmax = Math.min(full.max, vmax);
    }
    return { min: vmin, max: vmax, full };
  }

  function ensureSpectrumViewFits(scan, bins) {
    const nets = spectrumFilteredScan(scan);
    if (!nets.length) return;
    if (spectrumView.mhzMin == null && spectrumView.mhzMax == null) return;
    const { min, max } = spectrumVisibleRange(bins, scan);
    const anyVisible = nets.some((n) => n.mhz >= min - 25 && n.mhz <= max + 25);
    if (!anyVisible) resetSpectrumView();
  }

  function binsInSpectrumView(bins, scan) {
    if (!bins.length) return bins;
    const { min, max } = spectrumVisibleRange(bins, scan);
    return bins.filter((b) => b.mhz >= min - 5 && b.mhz <= max + 5);
  }

  function truncateSpectrumLabel(text, maxLen) {
    const s = String(text || "").trim();
    if (s.length <= maxLen) return s;
    return `${s.slice(0, maxLen - 1)}…`;
  }

  const RF_BELL_COLORS = [
    "#c084fc", "#38bdf8", "#6366f1", "#fb923c", "#ef4444",
    "#4ade80", "#facc15", "#f472b6", "#2dd4bf", "#a78bfa",
  ];

  function rfBellColor(idx) {
    return RF_BELL_COLORS[idx % RF_BELL_COLORS.length];
  }

  function rfPctToDbm(pct) {
    const p = Math.max(0, Math.min(100, Number(pct) || 0));
    return Math.round(-90 + p * 0.6);
  }

  function rfDbmToY(dbm, dbmFloor, dbmTop, pad, plotH) {
    const t = (dbm - dbmFloor) / Math.max(1, dbmTop - dbmFloor);
    return pad.t + plotH - Math.max(0, Math.min(1, t)) * plotH;
  }

  function rfMhzToX(mhz, xMin, xMax, pad, plotW) {
    return pad.l + ((mhz - xMin) / Math.max(1, xMax - xMin)) * plotW;
  }

  function rfGaussianDbm(peakDbm, centerMhz, sigmaMhz, mhz, floorDbm) {
    const diff = mhz - centerMhz;
    const amp = peakDbm - floorDbm;
    return floorDbm + amp * Math.exp(-(diff * diff) / (2 * sigmaMhz * sigmaMhz));
  }

  function drawRfBellSpectrum(canvas, cfg) {
    const emptyEl = cfg.emptyEl;
    const series = cfg.series || [];
    const xMin = cfg.xMin;
    const xMax = cfg.xMax;
    const dbmFloor = cfg.dbmFloor ?? -92;
    const pad = cfg.pad || { l: 44, r: 14, t: 24, b: 34 };
    const cssH = cfg.cssH ?? 280;
    const xTicks = cfg.xTicks || [];
    const xTickLabel = cfg.xTickLabel || ((t) => String(t));
    const linkMhz = cfg.linkMhz ?? null;

    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || canvas.parentElement?.clientWidth || 700;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    if (xMax <= xMin) {
      if (emptyEl) emptyEl.classList.remove("hidden");
      return;
    }

    const plotW = cssW - pad.l - pad.r;
    const plotH = cssH - pad.t - pad.b;

    ctx.fillStyle = "#060606";
    ctx.fillRect(0, 0, cssW, cssH);

    ctx.strokeStyle = "rgba(130,130,145,0.4)";
    ctx.lineWidth = 1;
    ctx.strokeRect(pad.l + 0.5, pad.t + 0.5, plotW - 1, plotH - 1);

    let dbmTop = cfg.dbmTop ?? -30;
    if (series.length) {
      const peakDbm = Math.max(...series.map((s) => s.dbm ?? dbmFloor));
      dbmTop = Math.min(-28, Math.ceil((peakDbm + 6) / 5) * 5);
      if (emptyEl) emptyEl.classList.add("hidden");
    } else if (emptyEl) {
      emptyEl.classList.remove("hidden");
    }

    for (let dbm = dbmTop; dbm >= dbmFloor; dbm -= 10) {
      const y = rfDbmToY(dbm, dbmFloor, dbmTop, pad, plotH);
      ctx.strokeStyle = dbm % 20 === 0 ? "rgba(130,130,145,0.22)" : "rgba(130,130,145,0.1)";
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + plotW, y);
      ctx.stroke();
      ctx.fillStyle = "rgba(180,180,195,0.75)";
      ctx.font = "10px ui-monospace, monospace";
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(String(dbm), pad.l - 6, y);
    }

    const active = series
      .filter((s) => s.mhz != null && s.mhz >= xMin - 20 && s.mhz <= xMax + 20)
      .slice()
      .sort((a, b) => (a.dbm ?? dbmFloor) - (b.dbm ?? dbmFloor));

    if (active.length) active.forEach((s) => {
      const color = s.color || "#5eead4";
      const sigma = s.sigma || 8;
      const mhzStart = Math.max(xMin, s.mhz - sigma * 3.4);
      const mhzEnd = Math.min(xMax, s.mhz + sigma * 3.4);
      const steps = 72;
      const baseY = rfDbmToY(dbmFloor, dbmFloor, dbmTop, pad, plotH);

      ctx.beginPath();
      let first = true;
      for (let i = 0; i <= steps; i++) {
        const mhz = mhzStart + (i / steps) * (mhzEnd - mhzStart);
        const dbm = rfGaussianDbm(s.dbm ?? dbmFloor, s.mhz, sigma, mhz, dbmFloor);
        const x = rfMhzToX(mhz, xMin, xMax, pad, plotW);
        const y = rfDbmToY(dbm, dbmFloor, dbmTop, pad, plotH);
        if (first) {
          ctx.moveTo(x, baseY);
          ctx.lineTo(x, y);
          first = false;
        } else {
          ctx.lineTo(x, y);
        }
      }
      ctx.lineTo(rfMhzToX(mhzEnd, xMin, xMax, pad, plotW), baseY);
      ctx.closePath();
      ctx.fillStyle = color;
      ctx.globalAlpha = 0.52;
      ctx.fill();

      ctx.globalAlpha = 0.98;
      ctx.strokeStyle = color;
      ctx.lineWidth = s.inUse ? 2.4 : 1.8;
      ctx.beginPath();
      first = true;
      for (let i = 0; i <= steps; i++) {
        const mhz = mhzStart + (i / steps) * (mhzEnd - mhzStart);
        const dbm = rfGaussianDbm(s.dbm ?? dbmFloor, s.mhz, sigma, mhz, dbmFloor);
        const x = rfMhzToX(mhz, xMin, xMax, pad, plotW);
        const y = rfDbmToY(dbm, dbmFloor, dbmTop, pad, plotH);
        if (first) { ctx.moveTo(x, y); first = false; }
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
      ctx.globalAlpha = 1;
    });

    if (active.length) active.forEach((s) => {
      const x = rfMhzToX(s.mhz, xMin, xMax, pad, plotW);
      const y = rfDbmToY(s.dbm ?? dbmFloor, dbmFloor, dbmTop, pad, plotH);
      const label = truncateSpectrumLabel(s.label || "—", 20);
      ctx.font = `700 ${s.inUse ? 12 : 11}px ui-sans-serif, system-ui, sans-serif`;
      ctx.textAlign = "center";
      ctx.textBaseline = "bottom";
      ctx.fillStyle = s.color || "#fff";
      const lx = Math.max(pad.l + 36, Math.min(pad.l + plotW - 36, x));
      ctx.fillText(label, lx, Math.max(pad.t + 12, y - 8));
    });

    if (linkMhz != null && linkMhz >= xMin && linkMhz <= xMax) {
      const lx = rfMhzToX(linkMhz, xMin, xMax, pad, plotW);
      ctx.strokeStyle = "rgba(255,255,255,0.45)";
      ctx.lineWidth = 1;
      ctx.setLineDash([5, 4]);
      ctx.beginPath();
      ctx.moveTo(lx, pad.t);
      ctx.lineTo(lx, pad.t + plotH);
      ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.fillStyle = "rgba(180,180,195,0.65)";
    ctx.font = "10px ui-monospace, monospace";
    ctx.textAlign = "center";
    ctx.textBaseline = "alphabetic";
    const tickStep = xTicks.length > 22 ? Math.ceil(xTicks.length / 18) : 1;
    xTicks.forEach((t, i) => {
      if (i % tickStep !== 0 && i !== xTicks.length - 1) return;
      if (t.mhz < xMin - 0.5 || t.mhz > xMax + 0.5) return;
      const x = rfMhzToX(t.mhz, xMin, xMax, pad, plotW);
      ctx.strokeStyle = "rgba(130,130,145,0.35)";
      ctx.beginPath();
      ctx.moveTo(x, pad.t + plotH);
      ctx.lineTo(x, pad.t + plotH + 4);
      ctx.stroke();
      ctx.fillStyle = "rgba(180,180,195,0.75)";
      ctx.fillText(xTickLabel(t), x, cssH - 8);
      if (t.mhz != null && xTicks.length <= 14) {
        ctx.fillStyle = "rgba(140,140,155,0.55)";
        ctx.font = "9px ui-monospace, monospace";
        ctx.fillText(`${Math.round(t.mhz)}`, x, cssH - 20);
        ctx.font = "10px ui-monospace, monospace";
        ctx.fillStyle = "rgba(180,180,195,0.75)";
      }
    });

    ctx.textAlign = "left";
    ctx.textBaseline = "alphabetic";
  }

  function spectrumZoomBy(factor, focalFrac) {
    const bins = filteredSpectrumBins(spectrumData || {});
    const scan = filteredSpectrumScan(spectrumData || {});
    if (bins.length < 1 && !(scan || []).length) return;
    const full = spectrumAutoFitRange(bins, scan) || spectrumFullRange(bins);
    let vMin = spectrumView.mhzMin ?? full.min;
    let vMax = spectrumView.mhzMax ?? full.max;
    const span = vMax - vMin;
    const focal = vMin + (focalFrac ?? 0.5) * span;
    const newSpan = Math.max(25, Math.min(full.max - full.min, span * factor));
    let newMin = focal - (focalFrac ?? 0.5) * newSpan;
    let newMax = newMin + newSpan;
    if (newMin < full.min) {
      newMin = full.min;
      newMax = full.min + newSpan;
    }
    if (newMax > full.max) {
      newMax = full.max;
      newMin = full.max - newSpan;
    }
    if (newMax - newMin >= full.max - full.min - 2) {
      resetSpectrumView();
    } else {
      spectrumView = { mhzMin: newMin, mhzMax: newMax };
    }
    renderSpectrumCharts();
  }

  function bindSpectrumZoom() {
    if (spectrumZoomBound) return;
    const canvas = $("spectrumCanvas");
    if (!canvas) return;
    spectrumZoomBound = true;
    const padL = 36;
    const padR = 12;

    canvas.addEventListener("wheel", (e) => {
      e.preventDefault();
      if (!spectrumData?.ok) return;
      const bins = filteredSpectrumBins(spectrumData);
      const scan = filteredSpectrumScan(spectrumData);
      if (bins.length < 1 && !(scan || []).length) return;
      const rect = canvas.getBoundingClientRect();
      const plotW = rect.width - padL - padR;
      const mouseX = e.clientX - rect.left - padL;
      const frac = plotW > 0 ? Math.max(0, Math.min(1, mouseX / plotW)) : 0.5;
      spectrumZoomBy(e.deltaY < 0 ? 0.78 : 1.28, frac);
    }, { passive: false });

    canvas.addEventListener("pointerdown", (e) => {
      if (!spectrumData?.ok || e.button !== 0) return;
      const bins = filteredSpectrumBins(spectrumData);
      const scan = filteredSpectrumScan(spectrumData);
      if (bins.length < 1 && !(scan || []).length) return;
      const { min, max } = spectrumVisibleRange(bins, scan);
      spectrumPan = { active: true, startX: e.clientX, startMin: min, startMax: max, pointerId: e.pointerId };
      canvas.classList.add("spectrum-panning");
      canvas.setPointerCapture(e.pointerId);
    });

    canvas.addEventListener("pointermove", (e) => {
      if (!spectrumPan.active || e.pointerId !== spectrumPan.pointerId) return;
      const bins = filteredSpectrumBins(spectrumData);
      const scan = filteredSpectrumScan(spectrumData);
      const full = spectrumAutoFitRange(bins, scan) || spectrumFullRange(bins);
      const rect = canvas.getBoundingClientRect();
      const plotW = rect.width - padL - padR;
      const span = spectrumPan.startMax - spectrumPan.startMin;
      const deltaMhz = (-(e.clientX - spectrumPan.startX) / Math.max(plotW, 1)) * span;
      let newMin = spectrumPan.startMin + deltaMhz;
      let newMax = spectrumPan.startMax + deltaMhz;
      if (newMin < full.min) {
        newMax += full.min - newMin;
        newMin = full.min;
      }
      if (newMax > full.max) {
        newMin -= newMax - full.max;
        newMax = full.max;
      }
      if (newMax - newMin >= full.max - full.min - 2) {
        resetSpectrumView();
      } else {
        spectrumView = { mhzMin: newMin, mhzMax: newMax };
      }
      renderSpectrumCharts();
    });

    const endPan = (e) => {
      if (!spectrumPan.active || e.pointerId !== spectrumPan.pointerId) return;
      spectrumPan.active = false;
      canvas.classList.remove("spectrum-panning");
      try { canvas.releasePointerCapture(e.pointerId); } catch (_) { /* ignore */ }
    };
    canvas.addEventListener("pointerup", endPan);
    canvas.addEventListener("pointercancel", endPan);
  }

  function loadSpectrumBandPrefs(bands) {
    try {
      const saved = JSON.parse(localStorage.getItem(SPECTRUM_BANDS_KEY) || "{}");
      if (saved && typeof saved === "object") spectrumBandsEnabled = saved;
    } catch (_) { spectrumBandsEnabled = {}; }
    (bands || []).forEach((b) => {
      if (spectrumBandsEnabled[b.id] === undefined) spectrumBandsEnabled[b.id] = true;
    });
  }

  function saveSpectrumBandPrefs() {
    localStorage.setItem(SPECTRUM_BANDS_KEY, JSON.stringify(spectrumBandsEnabled));
  }

  function spectrumBandColor(bandId, bands) {
    const b = (bands || []).find((x) => x.id === bandId);
    return b?.color || "#5eead4";
  }

  function spectrumBandLabel(bandId, bands) {
    const b = (bands || []).find((x) => x.id === bandId);
    return b?.short || b?.label || bandId || "—";
  }

  function renderSpectrumBandSwitches(bands) {
    const box = $("spectrumBandSwitches");
    if (!box) return;
    loadSpectrumBandPrefs(bands);
    box.innerHTML = (bands || []).map((b) => {
      const on = spectrumBandsEnabled[b.id] !== false;
      return `<label class="spectrum-band-switch${on ? " on" : ""}" style="--band-color:${esc(b.color)}">
        <input type="checkbox" class="spectrum-band-cb" data-band="${esc(b.id)}" ${on ? "checked" : ""} />
        <span class="spectrum-band-dot" aria-hidden="true"></span>
        <span class="spectrum-band-text">
          <strong>${esc(b.label)}</strong>
          <span class="spectrum-band-range">${b.mhz_min}–${b.mhz_max} MHz</span>
        </span>
      </label>`;
    }).join("");
    box.querySelectorAll(".spectrum-band-cb").forEach((cb) => {
      cb.addEventListener("change", () => {
        spectrumBandsEnabled[cb.dataset.band] = cb.checked;
        saveSpectrumBandPrefs();
        resetSpectrumView();
        cb.closest(".spectrum-band-switch")?.classList.toggle("on", cb.checked);
        renderSpectrumCharts();
        renderSpectrumSsidButtons();
        renderSpectrumScanTable();
      });
    });
  }

  function filteredSpectrumBins(data) {
    const bins = data?.bins || [];
    return bins.filter((b) => {
      const id = b.band_id;
      if (!id) return true;
      return spectrumBandsEnabled[id] !== false;
    });
  }

  function filteredSpectrumScan(data) {
    return (data?.scan || []).filter((n) => {
      if (!n.band_id) return true;
      return spectrumBandsEnabled[n.band_id] !== false;
    });
  }

  function bindSpectrumChartResize() {
    if (spectrumChartBound) return;
    spectrumChartBound = true;
    window.addEventListener("resize", () => renderSpectrumCharts(), { passive: true });
  }

  function drawSpectrumMain(allBins, bands, link, scan) {
    const canvas = $("spectrumCanvas");
    const empty = $("spectrumEmpty");
    bindSpectrumChartResize();
    bindSpectrumZoom();

    const view = spectrumVisibleRange(allBins || [], scan || []);
    const mhzMin = view.min;
    const mhzMax = view.max;

    if (mhzMax <= mhzMin && !spectrumFilteredScan(scan).length) {
      drawRfBellSpectrum(canvas, { emptyEl: empty, series: [], xMin: 0, xMax: 1 });
      return;
    }

    const centerEl = $("spectrumAxisCenter");
    if (centerEl) {
      const zoomed = spectrumView.mhzMin != null || spectrumView.mhzMax != null;
      centerEl.textContent = zoomed
        ? `${Math.round(mhzMin)} – ${Math.round(mhzMax)} MHz (zoomed)`
        : `${Math.round(mhzMin)} – ${Math.round(mhzMax)} MHz`;
    }

    const allScan = spectrumData?.scan || scan || [];
    const nets = spectrumFilteredScan(scan).filter((n) => {
      if (n.mhz == null || n.mhz < mhzMin - 30 || n.mhz > mhzMax + 30) return false;
      return true;
    });

    const series = nets.map((n) => {
      const key = spectrumNetKey(n);
      const focused = spectrumFocusKey === key;
      return {
        mhz: n.mhz,
        dbm: n.signal_dbm != null ? n.signal_dbm : rfPctToDbm(n.signal_pct),
        label: n.ssid || "(hidden)",
        color: spectrumNetColor(n, allScan),
        sigma: n.band_id === "2g" ? 11 : 9,
        inUse: !!n.in_use || focused,
      };
    });

    const bandsMeta = spectrumData?.all_bands || bands || [];
    const xTicks = spectrumChannelTicks(mhzMin, mhzMax, bandsMeta, spectrumData?.scan || scan || []);

    if (empty) {
      if (!series.length) {
        empty.innerHTML = spectrumEmptyMessage(spectrumData?.scan || scan || []);
        empty.classList.remove("hidden");
      } else {
        empty.classList.add("hidden");
      }
    }

    drawRfBellSpectrum(canvas, {
      emptyEl: empty,
      series,
      xMin: mhzMin,
      xMax: mhzMax,
      linkMhz: link?.mhz ?? null,
      xTicks,
      xTickLabel: (t) => (t.channel != null ? `ch ${t.channel}` : `${Math.round(t.mhz)}`),
      cssH: 280,
      pad: { l: 44, r: 14, t: 24, b: 42 },
    });
  }

  function spectrumSsidButtonHtml(n, scan, compact) {
    const key = spectrumNetKey(n);
    const band = spectrumBandLabel(n.band_id, spectrumData?.all_bands);
    const bandOff = n.band_id && spectrumBandsEnabled[n.band_id] === false;
    const active = spectrumFocusKey === key;
    const color = spectrumNetColor(n, scan);
    const ch = n.channel != null ? `ch ${n.channel}` : `${Math.round(n.mhz)} MHz`;
    const label = compact
      ? `${band} · ${ch}`
      : `${truncateSpectrumLabel(n.ssid || "(hidden)", 18)} · ${band} · ${ch}`;
    return `<button type="button" class="spectrum-ssid-btn${active ? " active" : ""}${bandOff ? " band-off" : ""}${n.in_use ? " in-use" : ""}"
      data-spectrum-focus="${esc(encodeURIComponent(key))}" style="--ssid-color:${esc(color)}"
      title="${esc(n.ssid || "(hidden)")} · ${esc(String(n.mhz))} MHz · ${esc(String(n.signal_dbm))} dBm${bandOff ? " · band filter off" : ""}">
      ${n.in_use ? '<span class="spectrum-ssid-star" aria-hidden="true">★</span>' : ""}
      <span class="spectrum-ssid-btn-label">${esc(label)}</span>
      <span class="spectrum-ssid-signal">${esc(String(n.signal_dbm))} dBm</span>
    </button>`;
  }

  function renderSpectrumSsidButtons() {
    const box = $("spectrumSsidButtons");
    if (!box) return;
    if (!spectrumData?.ok) {
      box.innerHTML = '<span class="muted-inline">No scan data — rescan WiFi.</span>';
      return;
    }
    const scan = (spectrumData.scan || []).slice().sort((a, b) => (b.signal_pct || 0) - (a.signal_pct || 0));
    if (!scan.length) {
      box.innerHTML = '<span class="muted-inline">No networks detected — click <strong>Rescan WiFi</strong>.</span>';
      return;
    }
    const bySsid = new Map();
    scan.forEach((n) => {
      const ssid = n.ssid || "(hidden)";
      if (!bySsid.has(ssid)) bySsid.set(ssid, []);
      bySsid.get(ssid).push(n);
    });
    box.innerHTML = [...bySsid.entries()].map(([ssid, nets]) => {
      if (nets.length === 1) return spectrumSsidButtonHtml(nets[0], scan, false);
      return `<div class="spectrum-ssid-group">
        <span class="spectrum-ssid-group-name" title="${esc(ssid)}">${esc(truncateSpectrumLabel(ssid, 22))}</span>
        <div class="spectrum-ssid-group-btns">${nets.map((n) => spectrumSsidButtonHtml(n, scan, true)).join("")}</div>
      </div>`;
    }).join("");
  }

  function bindSpectrumSsidUi() {
    if (spectrumSsidUiBound) return;
    spectrumSsidUiBound = true;
    $("spectrumSsidButtons")?.addEventListener("click", (e) => {
      const btn = e.target.closest("[data-spectrum-focus]");
      if (!btn) return;
      const key = decodeURIComponent(btn.dataset.spectrumFocus || "");
      const net = spectrumFindNet(key);
      if (net) spectrumCenterOnNetwork(net);
    });
    $("spectrumScanBody")?.addEventListener("click", (e) => {
      const row = e.target.closest("tr[data-spectrum-focus]");
      if (!row) return;
      const key = decodeURIComponent(row.dataset.spectrumFocus || "");
      const net = spectrumFindNet(key);
      if (net) spectrumCenterOnNetwork(net);
    });
  }

  function renderSpectrumCharts() {
    if (!spectrumData?.ok) return;
    const bins = filteredSpectrumBins(spectrumData);
    const scan = filteredSpectrumScan(spectrumData);
    drawSpectrumMain(bins, spectrumData.all_bands || spectrumData.bands, spectrumData.link, scan);
  }

  function renderSpectrumScanTable() {
    const body = $("spectrumScanBody");
    if (!body || !spectrumData) return;
    const rows = (spectrumData.scan || []).slice().sort((a, b) => (b.signal_pct || 0) - (a.signal_pct || 0));
    body.innerHTML = rows.length
      ? rows.map((n) => {
        const bandOff = n.band_id && spectrumBandsEnabled[n.band_id] === false;
        const key = encodeURIComponent(spectrumNetKey(n));
        const focused = spectrumFocusKey === spectrumNetKey(n);
        return `<tr class="spectrum-scan-row${n.in_use ? " spectrum-row-active" : ""}${bandOff ? " spectrum-row-band-off" : ""}${focused ? " spectrum-row-focused" : ""}" data-spectrum-focus="${esc(key)}" tabindex="0" role="button" title="Click to centre on chart">
          <td>${n.in_use ? "★" : ""}</td>
          <td><span class="spectrum-scan-ssid-dot" style="background:${esc(spectrumNetColor(n, rows))}"></span>${esc(n.ssid)}${bandOff ? ' <span class="muted-inline">(band off)</span>' : ""}</td>
          <td class="mono">${esc(String(n.mhz))}</td>
          <td>${esc(String(n.channel || "—"))}</td>
          <td><span class="spectrum-band-tag" style="background:${esc(spectrumBandColor(n.band_id, spectrumData.all_bands))}22;color:${esc(spectrumBandColor(n.band_id, spectrumData.all_bands))}">${esc(spectrumBandLabel(n.band_id, spectrumData.all_bands))}</span></td>
          <td>${esc(String(n.signal_pct))}% <span class="muted-inline">(${esc(String(n.signal_dbm))} dBm)</span></td>
          <td>${esc(n.security)}</td>
        </tr>`;
      }).join("")
      : `<tr><td colspan="7" class="muted">No networks detected — click Rescan WiFi.</td></tr>`;
  }

  function renderSpectrumMetrics(data) {
    const box = $("spectrumMetrics");
    if (!box || !data?.ok) return;
    const link = data.link || {};
    const peakDbm = Math.max(-100, ...(data.scan || []).map((n) => n.signal_dbm ?? rfPctToDbm(n.signal_pct)), -100);
    const busy = (data.scan || []).filter((n) => (n.signal_dbm ?? rfPctToDbm(n.signal_pct)) > -75).length;
    box.innerHTML = [
      `<div class="spectrum-metric"><div class="lbl">Peak signal</div><div class="val">${peakDbm} dBm</div><div class="sub">Strongest SSID in scan</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Strong networks</div><div class="val">${busy}</div><div class="sub">Above −75 dBm</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Your link</div><div class="val">${link.signal_dbm != null ? `${link.signal_dbm} dBm` : "—"}</div><div class="sub">${esc(link.ssid || "Not connected")}</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Adapter</div><div class="val mono">${esc(data.device || "—")}</div><div class="sub">${esc(data.phy || "")}</div></div>`,
    ].join("");
  }

  function renderSpectrum(data) {
    spectrumData = data;
    if (!data?.ok) {
      $("spectrumDevice") && ($("spectrumDevice").textContent = "—");
      $("spectrumConnected") && ($("spectrumConnected").textContent = data?.error || "Unavailable");
      $("spectrumNetCount") && ($("spectrumNetCount").textContent = "—");
      $("spectrumChanCount") && ($("spectrumChanCount").textContent = "—");
      $("spectrumScanBody") && ($("spectrumScanBody").innerHTML = `<tr><td colspan="7">${esc(data?.hint || data?.error || "No WiFi adapter")}</td></tr>`);
      $("spectrumEmpty")?.classList.remove("hidden");
      return;
    }
    renderSpectrumBandSwitches(data.all_bands || data.bands);
    $("spectrumDevice") && ($("spectrumDevice").textContent = data.device || "—");
    const link = data.link || {};
    $("spectrumConnected") && ($("spectrumConnected").textContent = link.ssid
      ? `${link.ssid} · ch ${link.channel || "?"} · ${link.mhz || "?"} MHz`
      : "Not connected");
    $("spectrumNetCount") && ($("spectrumNetCount").textContent = String(data.network_count || 0));
    $("spectrumChanCount") && ($("spectrumChanCount").textContent = String(data.channel_count || 0));
    $("spectrumAge") && ($("spectrumAge").textContent = `Updated ${formatLocaleTime(Date.now(), true)}`);
    renderSpectrumMetrics(data);
    if (data?.ok) {
      ensureSpectrumViewFits(data.scan, filteredSpectrumBins(data));
    }
    bindSpectrumSsidUi();
    renderSpectrumCharts();
    renderSpectrumSsidButtons();
    renderSpectrumScanTable();
  }

  async function loadSpectrum(force) {
    try {
      const data = await api("/api/spectrum", force ? { cache: "no-store" } : {});
      renderSpectrum(data);
      return data;
    } catch (e) {
      renderSpectrum({ ok: false, error: formatFetchError(e, "Spectrum scan") });
      return null;
    }
  }

  function stopSpectrumLive() {
    if (spectrumLiveTimer) {
      clearInterval(spectrumLiveTimer);
      spectrumLiveTimer = null;
    }
  }

  function startSpectrumLive() {
    stopSpectrumLive();
    if ($("spectrumLive") && !$("spectrumLive").checked) return;
    spectrumLiveTimer = setInterval(() => loadSpectrum(true), 4000);
  }

  const BT_SPECTRUM_BANDS_KEY = "nordctl_bt_spectrum_bands";
  const BT_SPECTRUM_DEFAULT_BANDS = [
    { id: "ble_low", label: "BLE low", short: "BLE-L", mhz_min: 2402, mhz_max: 2420, color: "#38bdf8" },
    { id: "ble_mid", label: "BLE mid", short: "BLE-M", mhz_min: 2422, mhz_max: 2460, color: "#818cf8" },
    { id: "ble_high", label: "BLE high", short: "BLE-H", mhz_min: 2462, mhz_max: 2480, color: "#c084fc" },
    { id: "classic", label: "BT Classic", short: "Classic", mhz_min: 2402, mhz_max: 2480, color: "#2dd4bf" },
  ];
  let btSpectrumData = null;
  let btSpectrumLiveTimer = null;
  let btSpectrumChartBound = false;
  let btSpectrumBandsEnabled = {};

  function loadBtSpectrumBandPrefs(bands) {
    try {
      const saved = JSON.parse(localStorage.getItem(BT_SPECTRUM_BANDS_KEY) || "{}");
      if (saved && typeof saved === "object") btSpectrumBandsEnabled = saved;
    } catch (_) { btSpectrumBandsEnabled = {}; }
    (bands || []).forEach((b) => {
      if (btSpectrumBandsEnabled[b.id] === undefined) btSpectrumBandsEnabled[b.id] = true;
    });
  }

  function saveBtSpectrumBandPrefs() {
    localStorage.setItem(BT_SPECTRUM_BANDS_KEY, JSON.stringify(btSpectrumBandsEnabled));
  }

  function btSpectrumBandColor(bandId, bands) {
    const b = (bands || []).find((x) => x.id === bandId);
    return b?.color || "#5eead4";
  }

  function btSpectrumBandLabel(bandId, bands) {
    const b = (bands || []).find((x) => x.id === bandId);
    return b?.short || b?.label || bandId || "—";
  }

  function renderBtSpectrumBandSwitches(bands) {
    const box = $("btSpectrumBandSwitches");
    if (!box) return;
    loadBtSpectrumBandPrefs(bands);
    box.innerHTML = (bands || []).map((b) => {
      const on = btSpectrumBandsEnabled[b.id] !== false;
      return `<label class="spectrum-band-switch${on ? " on" : ""}" style="--band-color:${esc(b.color)}">
        <input type="checkbox" class="bt-spectrum-band-cb" data-band="${esc(b.id)}" ${on ? "checked" : ""} />
        <span class="spectrum-band-dot" aria-hidden="true"></span>
        <span class="spectrum-band-text">
          <strong>${esc(b.label)}</strong>
          <span class="spectrum-band-range">${b.mhz_min}–${b.mhz_max} MHz</span>
        </span>
      </label>`;
    }).join("");
    box.querySelectorAll(".bt-spectrum-band-cb").forEach((cb) => {
      cb.addEventListener("change", () => {
        btSpectrumBandsEnabled[cb.dataset.band] = cb.checked;
        saveBtSpectrumBandPrefs();
        cb.closest(".spectrum-band-switch")?.classList.toggle("on", cb.checked);
        renderBtSpectrumCharts();
        renderBtSpectrumTables();
      });
    });
  }

  function filteredBtSpectrumBins(data) {
    return (data?.bins || []).filter((b) => {
      const id = b.band_id;
      if (!id) return true;
      return btSpectrumBandsEnabled[id] !== false;
    });
  }

  function filteredBtSpectrumDevices(data) {
    return (data?.devices || []).filter((d) => {
      if (!d.band_id) return true;
      return btSpectrumBandsEnabled[d.band_id] !== false;
    });
  }

  function bindBtSpectrumChartResize() {
    if (btSpectrumChartBound) return;
    btSpectrumChartBound = true;
    window.addEventListener("resize", () => renderBtSpectrumCharts(), { passive: true });
  }

  function drawBtSpectrumMain(bins, bands, devices) {
    const canvas = $("btSpectrumCanvas");
    const empty = $("btSpectrumEmpty");
    bindBtSpectrumChartResize();

    if (!bins.length) {
      if (empty) empty.classList.remove("hidden");
      return;
    }

    const mhzMin = bins[0].mhz;
    const mhzMax = bins[bins.length - 1].mhz;
    const centerEl = $("btSpectrumAxisCenter");
    if (centerEl) centerEl.textContent = `${Math.round(mhzMin)} – ${Math.round(mhzMax)} MHz · BLE`;

    const devs = (devices || []).filter((d) => (d.rssi != null || (d.signal_pct || 0) > 0) && d.mhz != null);
    const series = devs.map((d, i) => ({
      mhz: d.mhz,
      dbm: d.rssi != null ? d.rssi : rfPctToDbm(d.signal_pct),
      label: d.name || "(unknown)",
      color: rfBellColor(i),
      sigma: 3.2,
      inUse: !!d.connected,
    }));

    const xTicks = bins.map((b) => ({ mhz: b.mhz, channel: b.channel }));

    drawRfBellSpectrum(canvas, {
      emptyEl: empty,
      series,
      xMin: mhzMin,
      xMax: mhzMax,
      xTicks,
      xTickLabel: (t) => String(t.channel ?? ""),
      cssH: 280,
    });
  }

  function renderBtSpectrumCharts() {
    if (!btSpectrumData) return;
    const bins = filteredBtSpectrumBins(btSpectrumData);
    const devices = filteredBtSpectrumDevices(btSpectrumData);
    const bands = btSpectrumData.all_bands || btSpectrumData.bands;
    drawBtSpectrumMain(bins, bands, devices);
    const legend = $("btSpectrumLegend");
    if (legend) {
      const devs = devices.slice().sort((a, b) => (b.rssi ?? -100) - (a.rssi ?? -100));
      legend.innerHTML = devs.length
        ? devs.map((d, i) =>
          `<span class="spectrum-legend-item" style="--c:${esc(rfBellColor(i))}">${esc(truncateSpectrumLabel(d.name || "(unknown)", 14))}</span>`
        ).join("")
        : (bands || []).filter((b) => btSpectrumBandsEnabled[b.id] !== false).map((b) =>
          `<span class="spectrum-legend-item" style="--c:${esc(b.color)}">${esc(b.short || b.label)}</span>`
        ).join("");
    }
  }

  function btDeviceSecurityLabel(dev) {
    if (dev.legacy_pairing) return "Legacy pairing";
    if (dev.connected && !dev.trusted) return "Connected · not trusted";
    if (dev.paired && dev.trusted) return "Paired · trusted";
    if (dev.paired) return "Paired";
    return "Nearby";
  }

  function renderBtSecurityPanel(data) {
    const box = $("btSecurityPanel");
    if (!box) return;
    const items = data?.security || [];
    if (!data?.ok) {
      box.innerHTML = `<div class="bt-security-item info"><span class="bt-sec-level">Info</span><div><strong>${esc(data?.error || "Bluetooth unavailable")}</strong>${esc(data?.hint || "")}</div></div>`;
      return;
    }
    box.innerHTML = items.length
      ? items.map((f) => `<div class="bt-security-item ${esc(f.level || "info")}">
          <span class="bt-sec-level">${esc(f.level || "info")}</span>
          <div><strong>${esc(f.title)}</strong>${esc(f.detail)}</div>
        </div>`).join("")
      : "";
  }

  function renderBtSpectrumMetrics(data) {
    const box = $("btSpectrumMetrics");
    if (!box || !data?.ok) return;
    const peak = Math.max(0, ...(data.devices || []).map((d) => d.signal_pct || 0), 0);
    const busy = (data.bins || []).filter((b) => (b.signal_pct || 0) > 20).length;
    const adapter = data.adapter || {};
    box.innerHTML = [
      `<div class="spectrum-metric"><div class="lbl">Peak RSSI</div><div class="val">${peak}%</div><div class="sub">Strongest neighbor</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Active channels</div><div class="val">${busy}</div><div class="sub">BLE ch with signal</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Discoverable</div><div class="val">${adapter.discoverable ? "Yes" : "No"}</div><div class="sub">${adapter.discoverable ? "Visible to others" : "Not broadcasting"}</div></div>`,
      `<div class="spectrum-metric"><div class="lbl">Paired</div><div class="val">${data.paired_count || 0}</div><div class="sub">${data.nearby_count || 0} unknown nearby</div></div>`,
    ].join("");
  }

  function renderBtSpectrumTables() {
    const connBody = $("btConnectedBody");
    const devBody = $("btDeviceBody");
    if (!btSpectrumData) return;
    const bands = btSpectrumData.all_bands || btSpectrumData.bands;
    const connected = filteredBtSpectrumDevices(btSpectrumData).filter((d) => d.connected);
    if (connBody) {
      connBody.innerHTML = connected.length
        ? connected.map((d) => `<tr class="bt-row-connected">
            <td>${esc(d.name)}</td>
            <td class="mono">${esc(d.mac)}</td>
            <td>${esc(d.appearance || "—")}</td>
            <td>${d.rssi != null ? `${esc(String(d.rssi))} dBm` : "—"}</td>
            <td>${d.paired ? "Yes" : "No"}</td>
            <td>${d.trusted ? "Yes" : "No"}</td>
            <td>${esc(btDeviceSecurityLabel(d))}</td>
          </tr>`).join("")
        : `<tr><td colspan="7" class="muted">No active Bluetooth connections.</td></tr>`;
    }
    if (devBody) {
      const rows = filteredBtSpectrumDevices(btSpectrumData).sort((a, b) => (b.signal_pct || 0) - (a.signal_pct || 0));
      devBody.innerHTML = rows.length
        ? rows.map((d) => `<tr class="${d.connected ? "bt-row-connected" : ""}${d.paired ? " bt-row-paired" : ""}">
            <td>${d.connected ? "★" : d.paired ? "◆" : ""}</td>
            <td>${esc(d.name)}</td>
            <td class="mono">${esc(String(d.mhz))}</td>
            <td>${esc(String(d.ble_channel ?? "—"))}</td>
            <td><span class="spectrum-band-tag" style="background:${esc(btSpectrumBandColor(d.band_id, bands))}22;color:${esc(btSpectrumBandColor(d.band_id, bands))}">${esc(btSpectrumBandLabel(d.band_id, bands))}</span></td>
            <td>${d.rssi != null ? `${esc(String(d.rssi))} dBm` : "—"} <span class="muted-inline">(${esc(String(d.signal_pct || 0))}%)</span></td>
            <td>${esc(btDeviceSecurityLabel(d))}</td>
          </tr>`).join("")
        : `<tr><td colspan="7" class="muted">No devices found — click Scan nearby.</td></tr>`;
    }
  }

  function renderBluetoothSpectrum(data) {
    btSpectrumData = data;
    const bands = data?.all_bands || data?.bands || BT_SPECTRUM_DEFAULT_BANDS;
    renderBtSpectrumBandSwitches(bands);
    const pulse = $("btSpectrumPulse");
    if (pulse) pulse.classList.toggle("hidden", !data?.ok || !data?.adapter?.powered);

    if (!data?.ok) {
      $("btSpectrumAdapter") && ($("btSpectrumAdapter").textContent = "—");
      $("btSpectrumPower") && ($("btSpectrumPower").textContent = "—");
      $("btSpectrumNearbyCount") && ($("btSpectrumNearbyCount").textContent = "—");
      $("btSpectrumConnectedCount") && ($("btSpectrumConnectedCount").textContent = "—");
      renderBtSecurityPanel(data);
      $("btConnectedBody") && ($("btConnectedBody").innerHTML = `<tr><td colspan="7">${esc(data?.hint || data?.error || "Unavailable")}</td></tr>`);
      $("btDeviceBody") && ($("btDeviceBody").innerHTML = `<tr><td colspan="7">${esc(data?.hint || data?.error || "")}</td></tr>`);
      renderBtSpectrumCharts();
      return;
    }
    const adapter = data.adapter || {};
    $("btSpectrumAdapter") && ($("btSpectrumAdapter").textContent = adapter.name || adapter.mac || "—");
    $("btSpectrumPower") && ($("btSpectrumPower").textContent = adapter.powered ? (adapter.discovering ? "On · scanning" : "On") : "Off");
    $("btSpectrumNearbyCount") && ($("btSpectrumNearbyCount").textContent = String(data.device_count || 0));
    $("btSpectrumConnectedCount") && ($("btSpectrumConnectedCount").textContent = String(data.connected_count || 0));
    $("btSpectrumAge") && ($("btSpectrumAge").textContent = `Updated ${formatLocaleTime(Date.now(), true)}`);
    renderBtSecurityPanel(data);
    renderBtSpectrumMetrics(data);
    renderBtSpectrumCharts();
    renderBtSpectrumTables();
  }

  async function loadBluetooth(force, opts = {}) {
    const rescan = !!opts.rescan;
    const url = rescan ? "/api/bluetooth?rescan=1" : "/api/bluetooth";
    try {
      const data = await api(url, force ? { cache: "no-store" } : {});
      renderBluetoothSpectrum(data);
      return data;
    } catch (e) {
      renderBluetoothSpectrum({ ok: false, error: formatFetchError(e, "Bluetooth scan") });
      return null;
    }
  }

  function stopBtSpectrumLive() {
    if (btSpectrumLiveTimer) {
      clearInterval(btSpectrumLiveTimer);
      btSpectrumLiveTimer = null;
    }
  }

  function startBtSpectrumLive() {
    stopBtSpectrumLive();
    if ($("btSpectrumLive") && !$("btSpectrumLive").checked) return;
    btSpectrumLiveTimer = setInterval(() => loadBluetooth(true, { rescan: true }), 8000);
  }


  const SPEED_HISTORY_KEY = "nordctl_speed_history";
  const SPEED_HISTORY_MAX = 200;
  let speedHistoryCache = [];
  let speedHistoryLoaded = false;
  let speedLabGaugeMaxMbps = 100;
  let speedLabChartBound = false;
  let speedLabRunning = false;
  let speedLabProvidersLoaded = false;
  let speedLabProviderManual = localStorage.getItem("nordctl_speed_provider_manual") === "1";
  let speedLabProvidersCache = null;

  function renderSpeedLabProviderOptions(data, opts = {}) {
    const sel = $("speedLabProvider");
    const hint = $("speedLabProviderHint");
    if (!sel || !data?.providers) return;
    const prev = sel.value;
    const order = [
      "auto", "cloudflare",
      "linode_newark", "linode_atlanta", "linode_dallas", "linode_fremont",
      "linode_frankfurt", "linode", "linode_singapore", "linode_tokyo", "linode_sydney",
      "hetzner", "ovh", "tele2", "thinkbroadband", "fast", "speedtest_net",
    ];
    const ids = order.filter((id) => data.providers[id]);
    Object.keys(data.providers).forEach((id) => {
      if (!ids.includes(id)) ids.push(id);
    });
    sel.innerHTML = ids.map((id) =>
      `<option value="${esc(id)}">${esc(data.providers[id])}</option>`
    ).join("");
    let pick = "auto";
    if (opts.forcePick && data.providers[opts.forcePick]) {
      pick = opts.forcePick;
    } else if (speedLabProviderManual && prev && data.providers[prev]) {
      pick = prev;
    } else if (data.defaults?.default_provider && data.providers[data.defaults.default_provider]) {
      pick = data.defaults.default_provider;
    } else if (data.recommended && data.providers[data.recommended]) {
      pick = data.recommended;
    } else if (prev && data.providers[prev]) {
      pick = prev;
    }
    if (opts.forceAuto) pick = data.recommended || "auto";
    sel.value = data.providers[pick] ? pick : "auto";
    if (hint) {
      if (data.recommended_reason && !speedLabProviderManual) {
        hint.textContent = data.recommended_reason;
      } else if (data.geo?.country_code) {
        const geoBits = [data.geo.country_code, data.geo.colo, data.geo.city].filter(Boolean);
        hint.textContent = geoBits.length ? `Your IP region: ${geoBits.join(" · ")}` : "";
      } else {
        hint.textContent = "";
      }
    }
  }

  async function loadSpeedLabProviders(force = false) {
    if (speedLabProvidersLoaded && !force && speedLabProvidersCache) {
      renderSpeedLabProviderOptions(speedLabProvidersCache);
      return speedLabProvidersCache;
    }
    try {
      const data = await api("/api/speedtest/providers");
      if (data?.ok) {
        speedLabProvidersCache = data;
        speedLabProvidersLoaded = true;
        renderSpeedLabProviderOptions(data);
        applySpeedLabDefaults(data);
        return data;
      }
    } catch (_) { /* ignore */ }
    return speedLabProvidersCache;
  }

  function getSpeedHistory() {
    return speedHistoryCache.slice();
  }

  function setSpeedHistory(list) {
    speedHistoryCache = Array.isArray(list) ? list.slice(0, SPEED_HISTORY_MAX) : [];
  }

  async function loadSpeedHistoryFromServer(force) {
    if (speedHistoryLoaded && !force) return getSpeedHistory();
    try {
      const data = await api("/api/speedtest/history?limit=100");
      if (data?.ok && Array.isArray(data.entries)) {
        setSpeedHistory(data.entries);
        speedHistoryLoaded = true;
        const hint = $("speedLabSaveHint");
        if (hint && data.path) {
          hint.innerHTML = `Results on disk: <code>${esc(data.path)}</code> · exports in <code>~/.config/nordctl/exports/</code>`;
        }
        return getSpeedHistory();
      }
    } catch (_) { /* fall through */ }
    try {
      const raw = JSON.parse(localStorage.getItem(SPEED_HISTORY_KEY) || "[]");
      if (Array.isArray(raw) && raw.length) {
        setSpeedHistory(raw);
        localStorage.removeItem(SPEED_HISTORY_KEY);
      }
    } catch (_) { /* ignore */ }
    speedHistoryLoaded = true;
    return getSpeedHistory();
  }

  function speedLabDnsFromData(data) {
    const connected = !!(data?.status?.connected ?? data?.nordvpn?.connected);
    const sd = data?.smart_dns || {};
    const settings = data?.settings || {};
    const liveDns = (sd.dns_servers || []).filter(Boolean);
    let label = "DNS";
    let val = "";
    if (connected) {
      const nordDns = settings.DNS ?? settings.dns;
      if (nordDns !== undefined && nordDns !== null && String(nordDns).trim()) {
        label = "Nord DNS";
        val = String(nordDns).trim();
      }
    }
    if (!val && liveDns.length) {
      val = liveDns.join(", ");
      label = sd.active ? "Smart DNS" : "DNS";
    }
    if (!val && (sd.primary || sd.secondary)) {
      val = [sd.primary, sd.secondary].filter(Boolean).join(", ");
      label = "Smart DNS";
    }
    return { label, val };
  }

  function syncSpeedLabContext(data) {
    data = data || lastState || window.__nordctlPreboot || {};
    const connected = !!(data?.status?.connected ?? data?.nordvpn?.connected);
    const routeEl = $("speedLabRouteVal");
    const routeWrap = $("speedLabRoute");
    if (routeEl) {
      if (connected) {
        const country = data?.status?.country || data?.nordvpn?.country || "";
        const server = data?.status?.Server || data?.status?.server || "";
        routeEl.textContent = country ? `VPN · ${country}` : "VPN connected";
        if (server) routeEl.textContent += ` · ${server}`;
      } else {
        routeEl.textContent = "Direct (no VPN)";
      }
    }
    routeWrap?.classList.toggle("vpn", connected);
    const dns = speedLabDnsFromData(data);
    const dnsVal = $("speedLabDnsVal");
    const dnsLbl = $("speedLabDns")?.querySelector(".lbl");
    if (dnsVal) dnsVal.textContent = dns.val || "—";
    if (dnsLbl) dnsLbl.textContent = dns.label || "DNS";
  }

  function setSpeedLabGauge(mbps, { testing = false } = {}) {
    const gauge = $("speedLabGauge");
    const fill = $("speedLabGaugeFill");
    const valEl = $("speedLabGaugeVal");
    const hint = $("speedLabGaugeHint");
    const prog = $("speedLabProgress");
    const progBar = $("speedLabProgressBar");
    if (!gauge || !fill) return;
    gauge.classList.toggle("testing", !!testing);
    prog?.classList.toggle("hidden", !testing);
    const circ = 326.7;
    if (testing) {
      if (valEl) valEl.textContent = "…";
      if (hint) hint.textContent = "Downloading test file…";
      fill.style.strokeDashoffset = String(circ * 0.75);
      if (progBar) progBar.style.width = "35%";
      return;
    }
    const mb = Number(mbps);
    if (!Number.isFinite(mb) || mb <= 0) {
      if (valEl) valEl.textContent = "—";
      fill.style.strokeDashoffset = String(circ);
      if (progBar) progBar.style.width = "0%";
      return;
    }
    if (mb > speedLabGaugeMaxMbps * 0.9) speedLabGaugeMaxMbps = Math.ceil(mb * 1.25 / 10) * 10;
    const pct = Math.min(1, mb / speedLabGaugeMaxMbps);
    fill.style.strokeDashoffset = String(circ * (1 - pct));
    if (valEl) valEl.textContent = mb.toFixed(1);
    if (hint) hint.textContent = `Scale to ${speedLabGaugeMaxMbps} Mbps`;
    if (progBar) progBar.style.width = `${Math.round(pct * 100)}%`;
    gauge.dataset.mbps = String(mb);
  }

  function fmtSpeedWhen(ts) {
    if (typeof ts === "string" && ts.includes("T")) {
      try {
        return new Date(ts).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
      } catch (_) { /* fall through */ }
    }
    try {
      const n = Number(ts);
      return new Date(n > 1e12 ? n : n * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
    } catch (_) {
      return "—";
    }
  }

  function speedHistoryStats(history) {
    const vpn = history.filter((h) => h.vpn);
    const direct = history.filter((h) => !h.vpn);
    const avg = (arr) => (arr.length ? arr.reduce((s, x) => s + (x.mbps || 0), 0) / arr.length : 0);
    const best = history.length ? Math.max(...history.map((h) => h.mbps || 0)) : 0;
    const latest = history[0];
    return { vpn, direct, vpnAvg: avg(vpn), directAvg: avg(direct), best, latest };
  }

  function renderSpeedLabMetrics(history) {
    const stats = speedHistoryStats(history);
    const latestEl = $("speedLabLatest");
    const latestSub = $("speedLabLatestSub");
    const bestEl = $("speedLabBest");
    const bestSub = $("speedLabBestSub");
    if (latestEl) latestEl.textContent = stats.latest ? `${stats.latest.mbps.toFixed(1)} Mbps` : "—";
    if (latestSub) {
      latestSub.textContent = stats.latest
        ? `${stats.latest.vpn ? "VPN" : "Direct"} · ${fmtSpeedWhen(stats.latest.ts)}`
        : "No runs yet";
    }
    if (bestEl) bestEl.textContent = stats.best > 0 ? `${stats.best.toFixed(1)} Mbps` : "—";
    if (bestSub) bestSub.textContent = stats.best > 0 ? "All saved runs" : "—";
    $("speedLabVpnAvg") && ($("speedLabVpnAvg").textContent = stats.vpn.length ? `${stats.vpnAvg.toFixed(1)} Mbps` : "—");
    $("speedLabVpnCount") && ($("speedLabVpnCount").textContent = `${stats.vpn.length} run${stats.vpn.length === 1 ? "" : "s"}`);
    $("speedLabDirectAvg") && ($("speedLabDirectAvg").textContent = stats.direct.length ? `${stats.directAvg.toFixed(1)} Mbps` : "—");
    $("speedLabDirectCount") && ($("speedLabDirectCount").textContent = `${stats.direct.length} run${stats.direct.length === 1 ? "" : "s"}`);
    $("btnSpeedLabExportJson") && ($("btnSpeedLabExportJson").disabled = !history.length);
    $("btnSpeedLabExportCsv") && ($("btnSpeedLabExportCsv").disabled = !history.length);
  }

  function drawSpeedLabChart(history) {
    const canvas = $("speedLabChart");
    const empty = $("speedLabChartEmpty");
    if (!canvas) return;
    if (!speedLabChartBound) {
      speedLabChartBound = true;
      window.addEventListener("resize", () => drawSpeedLabChart(getSpeedHistory()), { passive: true });
    }
    const rows = [...history].reverse().slice(-20);
    if (empty) empty.classList.toggle("hidden", rows.length > 0);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || canvas.parentElement?.clientWidth || 600;
    const cssH = 160;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);
    if (!rows.length) return;

    const pad = { l: 36, r: 12, t: 14, b: 28 };
    const plotW = cssW - pad.l - pad.r;
    const plotH = cssH - pad.t - pad.b;
    const maxVal = Math.max(5, ...rows.map((r) => r.mbps || 0)) * 1.12;
    const barW = Math.max(8, Math.min(28, plotW / rows.length - 6));
    const gap = (plotW - barW * rows.length) / Math.max(1, rows.length + 1);

    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    for (let i = 0; i <= 4; i++) {
      const y = pad.t + (plotH * i) / 4;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + plotW, y);
      ctx.stroke();
      if (i === 0) {
        ctx.fillStyle = "rgba(255,255,255,0.35)";
        ctx.font = "10px ui-monospace, monospace";
        ctx.fillText(`${maxVal.toFixed(0)} Mbps`, 4, y + 10);
      }
    }

    rows.forEach((row, i) => {
      const mb = row.mbps || 0;
      const h = (mb / maxVal) * plotH;
      const x = pad.l + gap + i * (barW + gap);
      const y = pad.t + plotH - h;
      const grad = ctx.createLinearGradient(0, y, 0, pad.t + plotH);
      if (row.vpn) {
        grad.addColorStop(0, "#4ade80");
        grad.addColorStop(1, "rgba(74, 222, 128, 0.35)");
      } else {
        grad.addColorStop(0, "#67e8f9");
        grad.addColorStop(1, "rgba(103, 232, 249, 0.3)");
      }
      ctx.fillStyle = grad;
      ctx.fillRect(x, y, barW, h);
    });

    ctx.strokeStyle = "rgba(129, 140, 248, 0.55)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    rows.forEach((row, i) => {
      const mb = row.mbps || 0;
      const h = (mb / maxVal) * plotH;
      const x = pad.l + gap + i * (barW + gap) + barW / 2;
      const y = pad.t + plotH - h;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    });
    ctx.stroke();
  }

  function renderSpeedLabHistoryList(history) {
    const box = $("speedLabHistory");
    const count = $("speedLabHistoryCount");
    if (count) count.textContent = `${history.length} stored`;
    if (!box) return;
    if (!history.length) {
      box.innerHTML = `<p class="muted">No saved results — runs are stored in this browser only.</p>`;
      return;
    }
    box.innerHTML = history.map((row) => {
      const routeCls = row.vpn ? "vpn" : "direct";
      const meta = [
        `<strong>${esc(row.profile_label || row.profile || "standard")}</strong>`,
        esc(row.provider_label || row.provider || "auto"),
        esc(row.method || "single"),
        row.warmup ? "warm-up" : null,
        row.bytes ? `${Math.round(row.bytes / 1024)} KB` : null,
        row.seconds ? `${row.seconds}s` : null,
      ].filter(Boolean).join(" · ");
      return `<article class="speed-lab-run ${routeCls}">
        <div class="speed-lab-run-mbps">${Number(row.mbps || 0).toFixed(1)}</div>
        <div class="speed-lab-run-meta">${esc(fmtSpeedWhen(row.ts_iso || row.ts))}<br>${meta}<br>DNS: ${esc(row.dns || "—")}</div>
        <span class="speed-lab-run-badge ${routeCls}">${row.vpn ? "VPN" : "Direct"}</span>
      </article>`;
    }).join("");
  }

  function refreshSpeedLabUi() {
    const history = getSpeedHistory();
    renderSpeedLabMetrics(history);
    drawSpeedLabChart(history);
    renderSpeedLabHistoryList(history);
  }

  async function renderSpeedLabAll() {
    await loadSpeedLabProviders(false);
    await loadSpeedHistoryFromServer(false);
    refreshSpeedLabUi();
    syncSpeedLabContext();
  }

  function appendSpeedResult(res, ctx) {
    const entry = res.saved || {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      ts: Date.now(),
      ts_iso: new Date().toISOString(),
      mbps: Number(res.mbps) || 0,
      bytes: res.bytes,
      seconds: res.seconds,
      profile: res.profile,
      profile_label: res.profile_label,
      method: res.method,
      provider: res.provider,
      provider_label: res.provider_label,
      warmup: !!res.warmup,
      vpn: !!ctx.vpn,
      route: ctx.route,
      dns: ctx.dns,
      dns_label: ctx.dns_label,
      runs: Array.isArray(res.runs) ? res.runs.map((r) => ({ ...r })) : [],
      url: res.url,
      human: res.human,
    };
    const history = getSpeedHistory();
    history.unshift(entry);
    setSpeedHistory(history);
    refreshSpeedLabUi();
    setSpeedLabGauge(entry.mbps);
    return entry;
  }

  async function runSpeedLabTest() {
    if (speedLabRunning) return;
    const btn = $("btnSpeedLabRun");
    const status = $("speedLabStatus");
    speedLabRunning = true;
    if (btn) btn.disabled = true;
    if (status) {
      status.textContent = "Running";
      status.classList.add("running");
    }
    setSpeedLabGauge(0, { testing: true });
    syncSpeedLabContext();
    const body = {
      profile: $("speedLabProfile")?.value || "standard",
      method: $("speedLabMethod")?.value || "single",
      provider: $("speedLabProvider")?.value || "auto",
      warmup: !!$("speedLabWarmup")?.checked,
    };
    const saveDefault = speedLabProvidersCache?.defaults?.save_results !== false;
    const timeoutMs = body.provider === "speedtest_net" ? 150000
      : body.profile === "max" ? 120000
        : body.method !== "single" ? 150000 : 90000;
    const data = lastState || window.__nordctlPreboot || {};
    const connected = !!(data?.status?.connected ?? data?.nordvpn?.connected);
    const dnsInfo = speedLabDnsFromData(data);
    const ctx = {
      vpn: connected,
      route: connected ? liveBwRouteLabel() : "Direct",
      dns: dnsInfo.val,
      dns_label: dnsInfo.label,
    };
    try {
      const res = await api("/api/speedtest", {
        method: "POST",
        body: JSON.stringify({ ...body, save: saveDefault, meta: ctx }),
        timeoutMs,
      });
      if (res.ok) {
        appendSpeedResult(res, ctx);
        const savedNote = res.saved_path ? ` Saved to disk.` : "";
        toast((res.human || `${res.mbps} Mbps`) + savedNote, true);
        logActivity("Speed test", (res.human || `${res.mbps} Mbps`).slice(0, 120), true);
      } else {
        setSpeedLabGauge(0);
        showNotice(
          (res.error || "Speed test failed.") + (res.manual ? `\n\n${res.manual}` : ""),
          { ok: false, title: "Speed test failed", copyText: res.error || "failed" }
        );
        logActivity("Speed test", (res.error || "failed").slice(0, 120), false);
      }
    } catch (e) {
      setSpeedLabGauge(0);
      const err = e.name === "AbortError" ? "Speed test timed out" : String(e);
      showNotice(
        esc(err) + "<br><br>Check your connection or try a smaller file size.",
        { ok: false, title: "Speed test error", copyText: err, html: true }
      );
      logActivity("Speed test", err.slice(0, 120), false);
    } finally {
      speedLabRunning = false;
      if (btn) btn.disabled = false;
      if (status) {
        status.textContent = "Ready";
        status.classList.remove("running");
      }
      $("speedLabProgress")?.classList.add("hidden");
    }
  }

  async function clearSpeedHistory() {
    try {
      await api("/api/speedtest/clear", { method: "POST", body: "{}" });
    } catch (_) { /* ignore */ }
    localStorage.removeItem(SPEED_HISTORY_KEY);
    setSpeedHistory([]);
    speedHistoryLoaded = true;
    setSpeedLabGauge(0);
    refreshSpeedLabUi();
    toast("Speed test history cleared from disk", true);
  }

  function downloadSpeedExport(data, fmt) {
    if (!data?.ok || !data.content) {
      toast(data?.error || "Export failed", false);
      return;
    }
    const mime = fmt === "csv" ? "text/csv" : "application/json";
    const blob = new Blob([data.content], { type: mime });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = data.filename || `nordctl-speed-tests.${fmt}`;
    a.click();
    URL.revokeObjectURL(a.href);
    const pathNote = data.path ? ` Also saved: ${data.path}` : "";
    toast(`Exported ${data.count || 0} runs (${fmt.toUpperCase()}).${pathNote}`, true);
  }

  async function exportSpeedHistory(fmt) {
    try {
      const data = await api(`/api/speedtest/export?format=${encodeURIComponent(fmt)}&limit=200`);
      downloadSpeedExport(data, fmt);
    } catch (e) {
      toast(formatFetchError(e), false);
    }
  }

  function fmtBpsShort(bps) {
    const n = Number(bps) || 0;
    if (n < 1024) return `${n.toFixed(0)} B/s`;
    if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB/s`;
    return `${(n / (1024 * 1024)).toFixed(2)} MB/s`;
  }

  function liveBwRouteLabel() {
    const st = lastState || {};
    const connected = !!(st?.status?.connected ?? st?.nordvpn?.connected);
    if (connected) {
      const country = st?.status?.country || st?.nordvpn?.country || "";
      const tech = st?.status?.technology || st?.nordvpn?.technology || "";
      const bits = [country, tech].filter(Boolean);
      return bits.length ? `VPN · ${bits.join(" · ")}` : "VPN connected";
    }
    return "Direct (no VPN tunnel)";
  }

  function syncLiveBwRoute() {
    const el = $("liveBwRouteVal");
    if (!el) return;
    const connected = !!(lastState?.status?.connected ?? lastState?.nordvpn?.connected);
    el.textContent = liveBwRouteLabel();
    el.classList.toggle("on", connected);
    el.classList.toggle("off", !connected);
  }

  function pushLiveBwHistory(rxBps, txBps) {
    liveBwHistory.rx.push(Math.max(0, rxBps || 0));
    liveBwHistory.tx.push(Math.max(0, txBps || 0));
    if (liveBwHistory.rx.length > LIVE_BW_HISTORY_MAX) liveBwHistory.rx.shift();
    if (liveBwHistory.tx.length > LIVE_BW_HISTORY_MAX) liveBwHistory.tx.shift();
    const combined = (rxBps || 0) + (txBps || 0);
    if (combined > liveBwPeakBps) liveBwPeakBps = combined;
    drawLiveBwChart();
  }

  function bindLiveBwChartResize() {
    if (liveBwChartBound) return;
    liveBwChartBound = true;
    window.addEventListener("resize", () => drawLiveBwChart(), { passive: true });
  }

  function drawLiveBwChart() {
    const canvas = $("liveBwChart");
    const empty = $("liveBwChartEmpty");
    if (!canvas) return;
    bindLiveBwChartResize();
    const rx = liveBwHistory.rx;
    const tx = liveBwHistory.tx;
    if (empty) empty.classList.toggle("hidden", rx.length >= 2);
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    const dpr = window.devicePixelRatio || 1;
    const cssW = canvas.clientWidth || canvas.parentElement?.clientWidth || 600;
    const cssH = 140;
    canvas.width = Math.floor(cssW * dpr);
    canvas.height = Math.floor(cssH * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, cssW, cssH);

    const pad = { l: 8, r: 8, t: 10, b: 22 };
    const plotW = cssW - pad.l - pad.r;
    const plotH = cssH - pad.t - pad.b;

    const all = rx.concat(tx);
    const maxVal = Math.max(1024, ...all, liveBwPeakBps * 0.15);
    const gridLines = 4;
    ctx.strokeStyle = "rgba(255,255,255,0.06)";
    ctx.lineWidth = 1;
    ctx.fillStyle = "rgba(255,255,255,0.35)";
    ctx.font = "10px ui-monospace, monospace";
    for (let i = 0; i <= gridLines; i++) {
      const y = pad.t + (plotH * i) / gridLines;
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + plotW, y);
      ctx.stroke();
      if (i === 0) {
        ctx.fillText(fmtBpsShort(maxVal), pad.l + 2, y + 10);
      }
    }

    const drawLine = (series, color) => {
      if (series.length < 2) return;
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.beginPath();
      series.forEach((v, i) => {
        const x = pad.l + (plotW * i) / (LIVE_BW_HISTORY_MAX - 1);
        const y = pad.t + plotH - (Math.min(v, maxVal) / maxVal) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      });
      ctx.stroke();
      const last = series[series.length - 1];
      const lx = pad.l + (plotW * (series.length - 1)) / (LIVE_BW_HISTORY_MAX - 1);
      const ly = pad.t + plotH - (Math.min(last, maxVal) / maxVal) * plotH;
      ctx.fillStyle = color;
      ctx.beginPath();
      ctx.arc(lx, ly, 3.5, 0, Math.PI * 2);
      ctx.fill();
    };

    drawLine(rx, "#22d3ee");
    drawLine(tx, "#c084fc");
  }

  function stopSecurityBw() {
    if (securityBwTimer) {
      clearInterval(securityBwTimer);
      securityBwTimer = null;
    }
  }

  function startSecurityBw() {
    stopSecurityBw();
    syncLiveBwRoute();
    loadBandwidthQuiet();
    securityBwTimer = setInterval(() => loadBandwidthQuiet(), 4000);
  }

  async function loadBandwidthQuiet() {
    try {
      const bw = await api("/api/bandwidth");
      renderBandwidth(bw);
    } catch (_) { /* ignore */ }
  }

  function renderBandwidth(bw) {
    const box = $("secBandwidth");
    const badge = $("secBwBadge");
    if (!box) return;
    syncLiveBwRoute();
    const updated = $("liveBwUpdated");
    if (updated) updated.textContent = `Updated ${formatLocaleTime(Date.now(), true)}`;

    if (!bw?.ok || !(bw.interfaces || []).length) {
      box.innerHTML = `<div class="live-bw-iface"><p class="muted">${esc(bw?.hint || "No active traffic detected — idle interfaces are hidden.")}</p></div>`;
      if (badge) badge.textContent = "Idle";
      $("liveBwRxTotal") && ($("liveBwRxTotal").textContent = "—");
      $("liveBwTxTotal") && ($("liveBwTxTotal").textContent = "—");
      $("liveBwPeak") && ($("liveBwPeak").textContent = liveBwPeakBps ? fmtBpsShort(liveBwPeakBps) : "—");
      $("liveBwIfaceCount") && ($("liveBwIfaceCount").textContent = "0");
      return;
    }

    const ifaces = bw.interfaces || [];
    const primary = bw.primary || ifaces[0];
    const totalRx = ifaces.reduce((s, i) => s + (i.rx_bps || 0), 0);
    const totalTx = ifaces.reduce((s, i) => s + (i.tx_bps || 0), 0);
    const rxShow = primary?.rx_bps ?? totalRx;
    const txShow = primary?.tx_bps ?? totalTx;

    if ($("liveBwRxTotal")) $("liveBwRxTotal").textContent = primary?.rx_human || fmtBpsShort(rxShow);
    if ($("liveBwTxTotal")) $("liveBwTxTotal").textContent = primary?.tx_human || fmtBpsShort(txShow);
    if ($("liveBwRxSub")) $("liveBwRxSub").textContent = primary ? `${primary.iface}${primary.vpn ? " · VPN" : ""}` : "All interfaces";
    if ($("liveBwTxSub")) $("liveBwTxSub").textContent = primary ? `${primary.iface}${primary.vpn ? " · VPN" : ""}` : "All interfaces";
    if ($("liveBwPeak")) $("liveBwPeak").textContent = fmtBpsShort(liveBwPeakBps || rxShow + txShow);
    if ($("liveBwIfaceCount")) $("liveBwIfaceCount").textContent = String(ifaces.length);

    pushLiveBwHistory(rxShow, txShow);

    if (badge) badge.textContent = primary ? `${primary.rx_human} ↓` : fmtBpsShort(totalRx);

    const maxRate = Math.max(1, ...ifaces.map((i) => Math.max(i.rx_bps || 0, i.tx_bps || 0)));
    box.innerHTML = ifaces.map((iface) => {
      const rxPct = Math.min(100, ((iface.rx_bps || 0) / maxRate) * 100);
      const txPct = Math.min(100, ((iface.tx_bps || 0) / maxRate) * 100);
      const vpnCls = iface.vpn ? " live-bw-iface vpn" : " live-bw-iface";
      const tag = iface.vpn ? `<span class="live-bw-iface-tag">VPN</span>` : "";
      return `<div class="${vpnCls.trim()}">
        <div class="live-bw-iface-head">
          <span class="live-bw-iface-name">${esc(iface.iface)}</span>
          ${tag}
        </div>
        <div class="live-bw-iface-row">
          <span class="dir">↓</span>
          <div class="live-bw-iface-bar down"><span style="width:${rxPct.toFixed(1)}%"></span></div>
          <span class="live-bw-iface-rate">${esc(iface.rx_human)}</span>
        </div>
        <div class="live-bw-iface-row">
          <span class="dir">↑</span>
          <div class="live-bw-iface-bar up"><span style="width:${txPct.toFixed(1)}%"></span></div>
          <span class="live-bw-iface-rate">${esc(iface.tx_human)}</span>
        </div>
      </div>`;
    }).join("");
  }

  function renderLocationScenarios(data) {
    const profBox = $("connectLocationProfiles");
    if (!profBox) return;
    const profiles = Array.isArray(data) ? data : (data?.scenarios || data?.location_profiles || []);
    profBox.innerHTML = profiles.length
      ? profiles.map((p) =>
      `<button type="button" class="wifi-scenario-btn sec-location-btn" data-profile="${esc(p.id)}" data-confirm="1" data-confirm-message="Apply “${esc(p.label)}”? This may change VPN or DNS settings." title="${esc(p.hint || "")}"><strong>${esc(p.emoji || "")} ${esc(p.label)}</strong><span>${esc(p.hint || "")}</span></button>`
    ).join("")
      : `<p class="help-text muted-inline">No location scenarios available.</p>`;
    profBox.querySelectorAll(".sec-location-btn").forEach((btn) => {
      btn.addEventListener("click", () => doAction(
        { action: "location_apply", profile: btn.dataset.profile },
        btn.querySelector("strong")?.textContent || "Scenario",
      ).then(() => refreshLocationScenarios(true)));
    });
  }

  function refreshLocationScenariosFromAction(res) {
    invalidateScenarioCaches();
    if (res.location_scenarios) {
      renderLocationScenarios(res.location_scenarios);
    } else {
      refreshLocationScenarios(true);
    }
  }

  async function refreshLocationScenarios(force) {
    try {
      const ttl = force ? 0 : CACHE_TTL.securitySummary;
      const summary = await apiCached("/api/security/summary", {}, ttl);
      if (summary?.ok) {
        renderLocationScenarios({
          scenarios: summary.location_profiles,
          hidden_scenarios: summary.hidden_scenarios,
        });
      }
    } catch (e) {
      toast(String(e), false);
    }
  }

  async function addCustomPlace() {
    const label = prompt("Place name (e.g. Office VPN country):");
    if (!label) return;
    const type = (prompt("Type: country, city, or text?", "country") || "country").trim().toLowerCase();
    const res = await doAction({ action: "custom_place_add", label, type }, "Add place");
    if (res.ok) {
      await loadState(true);
      if (getActiveView() === "settings") await loadSettingsPanel(true);
    }
  }

  async function addPresetFromDashboard(template = "blank") {
    const name = prompt("Workflow name (e.g. my-stream):", template === "copy-example" ? "my-smart-dns" : "my-workflow");
    if (!name) return;
    const res = await api("/api/files/create", { method: "POST", body: JSON.stringify({ name, template }) });
    if (!res.ok) return toast(res.error, false);
    toast("Workflow created — opening editor", true);
    navigateRoute("network", "tools", { sub: "editor" });
    await loadFileList();
    await openFile(res.id);
  }

  let presetBuilderSchema = null;
  let presetBuilderPreviewTimer = null;
  let presetCurrentCapture = null;
  let lastCreatedPreset = null;
  let presetBuilderEdit = null;
  let presetBuilderFolded = false;

  const PB_TOGGLE_FIELDS = [
    "meshnet", "lan_discovery", "routing", "killswitch", "firewall",
    "threat_protection", "analytics", "virtual_location", "autoconnect",
    "notify", "tray", "arp_ignore", "post_quantum", "obfuscate",
  ];
  const PB_EXTRA_FIELDS = [
    "split_tunnel_lan", "split_tunnel_voip", "split_tunnel_subnets",
    "smart_dns_wifi", "meshnet_peer", "restore_defaults", "restore_dns_wifi",
  ];

  function slugifyPresetName(name) {
    return String(name || "")
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/^-|-$/g, "") || "my-preset";
  }

  function fillSelect(el, options, { valueKey = "value", labelKey = "label" } = {}) {
    if (!el) return;
    el.innerHTML = (options || [])
      .map((o) => `<option value="${esc(o[valueKey] ?? "")}">${esc(o[labelKey] ?? o[valueKey] ?? "")}</option>`)
      .join("");
  }

  function suggestPresetSummaryLabel(spec) {
    const label = String(spec?.label || "").trim();
    if (!label) return "";
    const mode = String(spec?.connection_mode || "vpn").trim();
    const modeHints = {
      smart_dns: "Smart DNS on WiFi — no VPN tunnel",
      vpn: "Connect via VPN",
      meshnet_only: "Meshnet routing without full VPN",
      disconnect: "Disconnect VPN",
      settings_only: "Change Nord settings without connecting",
    };
    const group = String(spec?.server_group || "").trim();
    if (group) {
      const groupLabel = group.replace(/_/g, " ");
      return `${label} — ${groupLabel}`;
    }
    return `${label} — ${modeHints[mode] || "Custom Nord workflow"}`;
  }

  function maybeAutoFillPresetSummary() {
    const summaryEl = $("pbSummary");
    if (!summaryEl || summaryEl.dataset.userEdited === "1") return;
    const suggested = suggestPresetSummaryLabel(readPresetBuilderSpec());
    if (suggested) summaryEl.value = suggested;
  }

  function readPresetBuilderSpec() {
    const tri = (id) => {
      const el = $(id);
      if (!el || el.disabled) return "";
      return String(el.value || "").trim();
    };
    const extraInc = (id) => tri(`pbExtra-${id}`) === "yes";
    return {
      label: tri("pbLabel"),
      filename: tri("pbFilename") || slugifyPresetName(tri("pbLabel")),
      summary: tri("pbSummary"),
      category: presetBuilderEdit?.category || "Custom",
      connection_mode: tri("pbConnectionMode") || "vpn",
      server_group: tri("pbServerGroup"),
      country_source: tri("pbCountrySource") || "config",
      country: tri("pbCountry"),
      city_source: tri("pbCitySource") || "none",
      city: tri("pbCity"),
      technology: tri("pbTechnology"),
      protocol: tri("pbProtocol"),
      nord_dns: tri("pbNordDns"),
      fwmark: tri("pbFwmark"),
      mesh_peer_value: tri("pbMeshPeerValue"),
      meshnet: tri("pbToggle-meshnet"),
      lan_discovery: tri("pbToggle-lan_discovery"),
      routing: tri("pbToggle-routing"),
      killswitch: tri("pbToggle-killswitch"),
      firewall: tri("pbToggle-firewall"),
      threat_protection: tri("pbToggle-threat_protection"),
      analytics: tri("pbToggle-analytics"),
      virtual_location: tri("pbToggle-virtual_location"),
      autoconnect: tri("pbToggle-autoconnect"),
      notify: tri("pbToggle-notify"),
      tray: tri("pbToggle-tray"),
      arp_ignore: tri("pbToggle-arp_ignore"),
      post_quantum: tri("pbToggle-post_quantum"),
      obfuscate: tri("pbToggle-obfuscate"),
      split_tunnel_lan: extraInc("split_tunnel_lan"),
      split_tunnel_voip: extraInc("split_tunnel_voip"),
      split_tunnel_subnets: extraInc("split_tunnel_subnets"),
      smart_dns_wifi: extraInc("smart_dns_wifi"),
      restore_dns_wifi: extraInc("restore_dns_wifi"),
      meshnet_peer: extraInc("meshnet_peer"),
      restore_defaults: extraInc("restore_defaults"),
    };
  }

  function applyPresetBuilderHelp(schema) {
    const help = schema?.field_help || {};
    document.querySelectorAll("[data-pb-help]").forEach((el) => {
      const key = el.dataset.pbHelp;
      el.textContent = help[key] || "";
    });
    const intro = $("presetBuilderCompatIntro");
    if (intro) intro.textContent = schema?.compat_intro || "";
  }

  function applyPresetBuilderCompatHints(fields = {}) {
    document.querySelectorAll("[data-pb-compat]").forEach((el) => {
      const fid = el.dataset.pbCompat;
      const f = fields[fid] || {};
      const reason = f.reason || "";
      if (f.state === "disabled" && reason) {
        el.textContent = reason;
        el.classList.remove("hidden");
      } else if (f.state === "forced" && reason) {
        el.textContent = `Auto: ${reason}`;
        el.classList.remove("hidden");
      } else {
        el.textContent = "";
        el.classList.add("hidden");
      }
    });
    document.querySelectorAll(".pb-field[data-pb-field]").forEach((row) => {
      const fid = row.dataset.pbField;
      const f = fields[fid] || { state: "enabled" };
      row.classList.toggle("disabled", f.state === "disabled");
      row.classList.toggle("forced", f.state === "forced");
    });
  }

  function syncPresetBuilderMeshPeerRow() {
    const row = $("pbMeshPeerRow");
    const inc = triVal("pbExtra-meshnet_peer") === "yes";
    if (row) row.classList.toggle("hidden", !inc);
    const input = $("pbMeshPeerValue");
    const hints = presetBuilderSchema?.config_hints || {};
    if (input && !input.value && hints.mesh_peer) input.value = hints.mesh_peer;
    const hint = $("pbMeshPeerHint");
    if (hint) {
      hint.textContent = inc
        ? "Saved to My places when you save the preset. List peers on Nord Dashboard → Meshnet or run nordvpn meshnet peer list."
        : "";
    }
  }

  function triVal(id) {
    const el = $(id);
    return el && !el.disabled ? String(el.value || "").trim() : "";
  }

  function applyPresetBuilderFieldStates(fields = {}) {
    const setDisabled = (sel, disabled, reason) => {
      const el = typeof sel === "string" ? $(sel) : sel;
      if (!el) return;
      el.disabled = disabled;
      const wrap = el.closest(".pb-field") || el.closest("label") || el.closest(".pb-location-row")
        || el.closest("label[data-toggle-id]");
      if (wrap) {
        wrap.classList.toggle("disabled", disabled);
        wrap.title = disabled ? (reason || "Not available for this combination") : "";
      }
    };
    const field = (id) => fields[id] || { state: "enabled" };

    const pbCountryRow = document.querySelector(".pb-inline-country");
    const pbCityRow = document.querySelector(".pb-inline-city");
    const countrySrc = $("pbCountrySource")?.value;
    const citySrc = $("pbCitySource")?.value;
    if (pbCountryRow) pbCountryRow.classList.toggle("hidden", countrySrc !== "inline");
    if (pbCityRow) pbCityRow.classList.toggle("hidden", citySrc !== "inline");

    [
      ["pbServerGroup", "server_group"],
      ["pbCountrySource", "country_source"],
      ["pbCitySource", "city_source"],
      ["pbCountry", "country"],
      ["pbCity", "city"],
      ["pbTechnology", "technology"],
      ["pbProtocol", "protocol"],
      ["pbNordDns", "nord_dns"],
      ["pbFwmark", "fwmark"],
      ["pbConnectionMode", "connection_mode"],
      ["pbMeshPeerValue", "mesh_peer_value"],
    ].forEach(([elId, fid]) => {
      const f = field(fid);
      setDisabled(elId, f.state === "disabled", f.reason);
      if (f.state === "forced" && f.forced != null && $(elId)) {
        $(elId).value = f.forced;
      }
    });

    document.querySelectorAll(".pb-location-row").forEach((row) => {
      const disabled = field("country_source").state === "disabled" && field("city_source").state === "disabled";
      row.classList.toggle("disabled", disabled);
    });

    const protoWrap = $("pbProtocolWrap");
    if (protoWrap) {
      protoWrap.classList.toggle("hidden", field("protocol").state === "disabled");
      protoWrap.classList.toggle("disabled", field("protocol").state === "disabled");
    }

    document.querySelectorAll("#pbToggleGrid label[data-toggle-id]").forEach((lbl) => {
      const fid = lbl.dataset.toggleId;
      const f = field(fid);
      const sel = lbl.querySelector("select");
      lbl.classList.toggle("disabled", f.state === "disabled");
      lbl.classList.toggle("forced", f.state === "forced");
      if (sel) {
        sel.disabled = f.state === "disabled";
        if (f.state === "forced" && f.forced != null) sel.value = f.forced;
      }
    });

    document.querySelectorAll("#pbExtrasGrid label[data-extra-id]").forEach((lbl) => {
      const fid = lbl.dataset.extraId;
      const f = field(fid);
      const sel = lbl.querySelector("select");
      lbl.classList.toggle("disabled", f.state === "disabled");
      lbl.classList.toggle("forced", f.state === "forced");
      if (sel) {
        sel.disabled = f.state === "disabled";
        if (f.state === "forced" && f.forced != null) {
          sel.value = f.forced === true || f.forced === "on" || f.forced === "yes" ? "yes" : "";
        }
      }
    });

    applyPresetBuilderCompatHints(fields);
    syncPresetBuilderMeshPeerRow();
  }

  function renderPresetBuilderWarnings(warnings = []) {
    const box = $("presetBuilderWarnings");
    if (!box) return;
    if (!warnings.length) {
      box.classList.add("hidden");
      box.innerHTML = "";
      return;
    }
    box.classList.remove("hidden");
    box.innerHTML = `<strong>Notes</strong><ul>${warnings.map((w) => `<li>${esc(w)}</li>`).join("")}</ul>`;
  }

  function renderPresetBuilderPreview(preview) {
    const box = $("presetBuilderPreview");
    if (!box) return;
    if (!preview?.steps?.length) {
      box.classList.add("hidden");
      box.innerHTML = "";
      return;
    }
    box.classList.remove("hidden");
    box.innerHTML = `<strong>Steps (${preview.steps.length})</strong><ol>${preview.steps.map((s) => `<li>${esc(s.text)}</li>`).join("")}</ol>`;
  }

  function showPresetBuilderSavedBanner(result, { updated = false } = {}) {
    const banner = $("presetBuilderSavedBanner");
    if (!banner) return;
    const label = result?.label || result?.document?.label || "Preset";
    const presetId = result?.document?.id || String(result?.file_id || "").replace(/^user\//, "").replace(/\.yaml$/, "");
    const fileId = result?.file_id || result?.id || "";
    const fav = presetConnectFavoriteTarget(result?.spec, result?.document);
    const verb = updated ? "updated" : "saved";
    banner.classList.remove("hidden");
    banner.innerHTML = `<p><strong>“${esc(label)}” ${verb}.</strong> It is in <strong>My presets</strong> below. Saving does not run it — use <strong>Run preset</strong> when ready.</p>
      <div class="panel-nav-actions">
        <button type="button" class="btn sm primary" data-pb-saved-jump="my-presets">Open My presets</button>
        <button type="button" class="btn sm" data-pb-saved-share="${esc(presetId)}" ${presetId ? "" : "disabled"}>Share YAML</button>
        ${fav ? `<button type="button" class="btn sm" data-pb-saved-fav-kind="${esc(fav.kind)}" data-pb-saved-fav-value="${esc(fav.value)}">Add to favorites</button>` : ""}
        <button type="button" class="btn sm danger" data-pb-saved-delete="${esc(presetId)}" data-pb-saved-file="${esc(fileId)}" ${presetId ? "" : "disabled"}>Delete preset</button>
        <button type="button" class="btn sm" data-pb-saved-new>New preset</button>
      </div>`;
    bindPresetBuilderSavedBanner(banner, { presetId, fileId, label, fav });
    bindViewJumps(banner);
  }

  function presetConnectFavoriteTarget(spec, doc) {
    const s = spec || {};
    if (s.city_source === "inline" && s.city) return { kind: "city", value: s.city };
    if (s.country_source === "inline" && s.country) return { kind: "country", value: s.country };
    const steps = doc?.steps || [];
    for (const step of steps) {
      if (!step || typeof step !== "object") continue;
      const action = String(step.action || "");
      const target = String(step.target || "").trim();
      if (action === "nordvpn_connect" && target && !target.startsWith("{")) {
        if (target.includes(" ")) return { kind: "city", value: target };
        return { kind: "country", value: target.replace(/ /g, "_") };
      }
    }
    return null;
  }

  function bindPresetBuilderSavedBanner(banner, meta) {
    banner.querySelector("[data-pb-saved-jump]")?.addEventListener("click", () => {
      navigateRoute("dashboard", "workflows", { sub: "my-presets" });
    });
    banner.querySelector("[data-pb-saved-share]")?.addEventListener("click", () => {
      if (!meta.presetId) return;
      sharePreset({ id: meta.presetId, label: meta.label });
    });
    banner.querySelector("[data-pb-saved-fav-kind]")?.addEventListener("click", (e) => {
      const btn = e.currentTarget;
      const kind = btn.getAttribute("data-pb-saved-fav-kind");
      const value = btn.getAttribute("data-pb-saved-fav-value");
      if (!kind || !value) return;
      doAction({
        action: "favorite_add",
        kind,
        value: kind === "country" ? value.replace(/ /g, "_") : value,
      }, "Add favorite").then((r) => {
        if (r.ok) {
          toast(`Added “${meta.label}” connect target to favorites`, true);
          loadState(true);
        }
      });
    });
    banner.querySelector("[data-pb-saved-delete]")?.addEventListener("click", () => {
      if (!meta.presetId) return;
      if (!confirm(`Delete preset “${meta.label}”? This removes the YAML file permanently.`)) return;
      doAction({ action: "preset_delete", id: meta.presetId, file_id: meta.fileId }, "Delete preset")
        .then((r) => {
          if (r.ok) {
            banner.classList.add("hidden");
            banner.innerHTML = "";
            lastCreatedPreset = null;
            loadState(true);
          }
        });
    });
    banner.querySelector("[data-pb-saved-new]")?.addEventListener("click", () => {
      banner.classList.add("hidden");
      clearPresetBuilderEditMode();
      openPresetBuilder();
    });
  }

  function setPresetBuilderEditMode(editing) {
    const title = $("presetBuilderTitle");
    const btn = $("btnPresetBuilderCreate");
    const fn = $("pbFilename");
    if (editing && presetBuilderEdit) {
      if (title) title.textContent = `Edit preset — ${presetBuilderEdit.label || presetBuilderEdit.preset_id || "Custom"}`;
      if (btn) btn.textContent = "Save changes";
      if (fn) {
        fn.disabled = true;
        fn.title = "File name stays the same when editing an existing preset.";
      }
    } else {
      if (title) title.textContent = "New preset";
      if (btn) btn.textContent = "Save preset";
      if (fn) {
        fn.disabled = false;
        fn.title = "";
      }
    }
  }

  function clearPresetBuilderEditMode() {
    presetBuilderEdit = null;
    setPresetBuilderEditMode(false);
  }

  function presetBuilderFilenameFromPreset(p) {
    const fileId = String(p?.file_id || "").trim();
    if (fileId) return fileId.replace(/^user\//, "").replace(/\.yaml$/i, "");
    const pid = String(p?.id || "").trim();
    return pid ? slugifyPresetName(pid.replace(/_/g, "-")) : "";
  }

  async function resolvePresetBuilderSpec(p) {
    if (p?.builder_spec && typeof p.builder_spec === "object") {
      return { ...p.builder_spec };
    }
    const presetId = p?.id || String(p?.file_id || "").replace(/^user\//, "").replace(/\.yaml$/i, "");
    if (!presetId) return null;
    const fromPreset = await api(`/api/presets/builder/from-preset?id=${encodeURIComponent(presetId)}`).catch(() => null);
    if (fromPreset?.ok && fromPreset.spec) return { ...fromPreset.spec };
    return null;
  }

  async function openPresetBuilderForEdit(p) {
    if (!p?.user) return toast("Only your custom presets can be edited in the builder", false);
    const spec = await resolvePresetBuilderSpec(p);
    if (!spec) return toast("Could not load preset for editing", false);
    spec.filename = presetBuilderFilenameFromPreset(p) || spec.filename || slugifyPresetName(spec.label || p.label);
    presetBuilderEdit = {
      file_id: p.file_id || `user/${p.id}.yaml`,
      preset_id: p.id,
      label: p.label || spec.label,
      category: p.category || spec.category || "Custom",
    };
    await openPresetBuilder(spec);
    setPresetBuilderEditMode(true);
  }

  async function editUserPresetInBuilder(p) {
    if (!p?.user) return;
    if (getActiveView() === "create-presets") {
      await openPresetBuilderForEdit(p);
      return;
    }
    pendingPresetEditId = p.id;
    navigateRoute("dashboard", "create-presets");
  }

  function updatePresetBuilderFoldButtons() {
    const expanded = !presetBuilderFolded;
    ["btnTogglePresetBuilder", "btnTogglePresetBuilderHead"].forEach((id) => {
      const btn = $(id);
      if (!btn) return;
      btn.textContent = expanded ? "Fold ↑" : "Unfold ↓";
      btn.setAttribute("aria-expanded", expanded ? "true" : "false");
    });
  }

  function togglePresetBuilderFold(forceExpand) {
    const box = $("presetBuilderOverlay");
    if (!box) return;
    if (forceExpand === true) presetBuilderFolded = false;
    else if (forceExpand === false) presetBuilderFolded = true;
    else presetBuilderFolded = !presetBuilderFolded;
    box.classList.toggle("collapsed", presetBuilderFolded);
    updatePresetBuilderFoldButtons();
  }

  async function ensurePresetBuilderCountries() {
    if (!countries.length) {
      try {
        const data = await api("/api/state/nord");
        if (Array.isArray(data?.countries) && data.countries.length) countries = data.countries;
      } catch (_) { /* filled below if still empty */ }
    }
    await populatePresetBuilderCountries();
  }

  async function ensurePresetBuilderReady(prefillSpec = null) {
    if (!presetBuilderSchema?.ok) {
      presetBuilderSchema = await api("/api/presets/builder/schema").catch(() => null);
      if (!presetBuilderSchema?.ok) {
        toast(presetBuilderSchema?.error || "Could not load preset builder", false);
        return false;
      }
    }
    const schema = presetBuilderSchema;
    fillSelect($("pbConnectionMode"), schema.connection_modes);
    fillSelect($("pbServerGroup"), schema.server_groups);
    fillSelect($("pbCountrySource"), schema.location_sources);
    fillSelect($("pbCitySource"), schema.location_sources);
    fillSelect($("pbTechnology"), schema.technologies);
    fillSelect($("pbProtocol"), schema.protocols);
    fillSelect($("pbNordDns"), schema.dns_modes);
    renderPresetBuilderToggleGrid(schema);
    renderPresetBuilderExtrasGrid(schema);
    applyPresetBuilderHelp(schema);
    const defs = prefillSpec || schema.defaults || {};
    fillPresetBuilderFromSpec(defs, { fromCapture: Boolean(prefillSpec) });
    const hints = schema.config_hints || {};
    if (!prefillSpec?.mesh_peer_value && hints.mesh_peer && $("pbMeshPeerValue")) {
      $("pbMeshPeerValue").value = hints.mesh_peer;
    }
    populatePresetBuilderMeshPeerList(lastState?.mesh_peers_raw);
    await ensurePresetBuilderCountries();
    if (prefillSpec?.country && $("pbCountry")) $("pbCountry").value = prefillSpec.country;
    if (prefillSpec?.city && prefillSpec?.country) {
      await populatePresetBuilderCities(prefillSpec.country);
      if ($("pbCity")) $("pbCity").value = prefillSpec.city;
    }
    document.querySelector(".pb-inline-country")?.classList.toggle("hidden", $("pbCountrySource")?.value !== "inline");
    document.querySelector(".pb-inline-city")?.classList.toggle("hidden", $("pbCitySource")?.value !== "inline");
    await refreshPresetBuilderCompatibility();
    return true;
  }

  async function refreshPresetBuilderCompatibility() {
    const spec = readPresetBuilderSpec();
    const res = await api("/api/presets/builder/preview", { method: "POST", body: JSON.stringify({ spec }) });
    if (!res.ok) return;
    applyPresetBuilderFieldStates(res.fields || {});
    renderPresetBuilderWarnings(res.warnings || []);
    return res;
  }

  function schedulePresetBuilderPreview() {
    clearTimeout(presetBuilderPreviewTimer);
    presetBuilderPreviewTimer = setTimeout(async () => {
      const res = await refreshPresetBuilderCompatibility();
      if (res?.breakdown) renderPresetBuilderPreview(res.breakdown);
    }, 220);
  }

  async function populatePresetBuilderCountries() {
    const sel = $("pbCountry");
    if (!sel) return;
    if (!countries.length) {
      sel.innerHTML = `<option value="">Loading countries…</option>`;
      return;
    }
    const prev = sel.value;
    sel.innerHTML = `<option value="">Country…</option>` + countries.map((c) =>
      `<option value="${esc(c)}">${esc(countryLabel(c))}</option>`
    ).join("");
    if (prev) sel.value = prev;
  }

  async function populatePresetBuilderCities(country) {
    const sel = $("pbCity");
    if (!sel) return;
    if (!country) {
      sel.innerHTML = `<option value="">City…</option>`;
      sel.disabled = true;
      return;
    }
    sel.disabled = false;
    sel.innerHTML = `<option value="">Loading…</option>`;
    const data = await api(`/api/locations/cities?country=${encodeURIComponent(country.replace(/_/g, " "))}`);
    const cities = data.cities || [];
    sel.innerHTML = `<option value="">City (optional)…</option>` + cities.map((c) =>
      `<option value="${esc(c)}">${esc(c.replace(/_/g, " "))}</option>`
    ).join("");
  }

  function renderPresetBuilderToggleGrid(schema) {
    const grid = $("pbToggleGrid");
    if (!grid) return;
    const triOpts = [
      { value: "default", label: "Default (unchanged)" },
      { value: "on", label: "On" },
      { value: "off", label: "Off" },
    ];
    grid.innerHTML = (schema.toggles || []).map((t) =>
      `<label data-toggle-id="${esc(t.id)}"><span>${esc(t.label)}</span>
        <select id="pbToggle-${esc(t.id)}" data-toggle-id="${esc(t.id)}">${triOpts.map((o) =>
          `<option value="${esc(o.value)}">${esc(o.label)}</option>`
        ).join("")}</select>
        <p class="pb-toggle-help">${esc(t.help || "")}</p>
        <p class="pb-field-compat hidden" data-pb-compat="${esc(t.id)}"></p>
      </label>`
    ).join("");
    grid.querySelectorAll("select").forEach((sel) => {
      sel.addEventListener("change", schedulePresetBuilderPreview);
    });
  }

  function renderPresetBuilderExtrasGrid(schema) {
    const grid = $("pbExtrasGrid");
    if (!grid) return;
    const incOpts = schema.include_options || [
      { value: "", label: "Don't include" },
      { value: "yes", label: "Include in preset" },
    ];
    grid.innerHTML = (schema.extras || []).map((t) =>
      `<label data-extra-id="${esc(t.id)}"><span>${esc(t.label)}</span>
        <select id="pbExtra-${esc(t.id)}" data-extra-id="${esc(t.id)}">${incOpts.map((o) =>
          `<option value="${esc(o.value)}">${esc(o.label)}</option>`
        ).join("")}</select>
        <p class="pb-toggle-help">${esc(t.help || "")}</p>
        <p class="pb-field-compat hidden" data-pb-compat="${esc(t.id)}"></p>
      </label>`
    ).join("");
    grid.querySelectorAll("select").forEach((sel) => {
      sel.addEventListener("change", () => {
        syncPresetBuilderMeshPeerRow();
        schedulePresetBuilderPreview();
      });
    });
  }

  function populatePresetBuilderMeshPeerList(raw) {
    const list = $("pbMeshPeerList");
    if (!list) return;
    list.innerHTML = "";
    String(raw || "").split(/\n/).forEach((line) => {
      const m = line.match(/([a-z0-9][a-z0-9.-]*\.nord)/i) || line.match(/Hostname:\s*(\S+)/i);
      if (m && m[1]) {
        const opt = document.createElement("option");
        opt.value = m[1];
        list.appendChild(opt);
      }
    });
  }

  async function openPresetBuilder(prefillSpec = null) {
    const overlay = $("presetBuilderOverlay");
    if (!overlay) return;
    togglePresetBuilderFold(true);
    const ok = await ensurePresetBuilderReady(prefillSpec);
    if (!ok) return;
    if (presetBuilderEdit) setPresetBuilderEditMode(true);
    overlay.scrollIntoView({ block: "start", behavior: "smooth" });
    $("pbLabel")?.focus();
  }

  function fillPresetBuilderFromSpec(spec, { fromCapture = false } = {}) {
    const set = (id, val) => {
      const el = $(id);
      if (el) el.value = val ?? "";
    };
    set("pbLabel", spec.label || "");
    set("pbFilename", spec.filename || slugifyPresetName(spec.label || ""));
    set("pbSummary", spec.summary || "");
    set("pbConnectionMode", spec.connection_mode || "vpn");
    set("pbServerGroup", spec.server_group || "");
    set("pbCountrySource", spec.country_source || "config");
    set("pbCitySource", spec.city_source || "none");
    set("pbCountry", spec.country || "");
    set("pbCity", spec.city || "");
    set("pbTechnology", spec.technology || "");
    set("pbProtocol", spec.protocol || "");
    set("pbNordDns", spec.nord_dns || "");
    set("pbFwmark", spec.fwmark || "");
    set("pbMeshPeerValue", spec.mesh_peer_value || "");
    PB_TOGGLE_FIELDS.forEach((fid) => {
      const el = $(`pbToggle-${fid}`);
      if (!el) return;
      const val = spec[fid];
      el.value = val === "on" || val === "off" ? val : (fromCapture ? "default" : (el.value || "default"));
    });
    PB_EXTRA_FIELDS.forEach((fid) => {
      const el = $(`pbExtra-${fid}`);
      if (!el) return;
      el.value = spec[fid] ? "yes" : "";
    });
    const fn = $("pbFilename");
    if (fn) fn.dataset.userEdited = spec.filename ? "1" : "";
    const summaryEl = $("pbSummary");
    if (summaryEl) {
      summaryEl.dataset.userEdited = String(spec.summary || "").trim() ? "1" : "";
      if (!summaryEl.dataset.userEdited) maybeAutoFillPresetSummary();
    }
    syncPresetBuilderMeshPeerRow();
  }

  function renderPresetCurrentCapture(data) {
    presetCurrentCapture = data?.ok && data.available !== false ? data : null;
    const badge = $("presetCurrentStatus");
    const list = $("presetCurrentSummary");
    const btn = $("btnPresetFromCurrent");
    if (!list) return;
    if (!data?.ok || data.available === false) {
      if (badge) badge.textContent = "Unavailable";
      list.innerHTML = `<li class="muted-inline">${esc(data?.error || data?.message || "Install NordVPN to capture live settings.")}</li>`;
      if (btn) btn.disabled = true;
      return;
    }
    if (badge) badge.textContent = data.connected ? "VPN on" : (data.smart_dns_active ? "Smart DNS" : "Ready");
    const lines = data.summary_lines || [];
    list.innerHTML = lines.length
      ? lines.map((line) => `<li>${esc(line)}</li>`).join("")
      : `<li class="muted-inline">Live Nord settings loaded.</li>`;
    if (btn) btn.disabled = false;
  }

  async function loadPresetCurrentCapture() {
    const list = $("presetCurrentSummary");
    if (list) list.innerHTML = `<li class="muted-inline">Loading current setup…</li>`;
    const data = await api("/api/presets/builder/from-current").catch(() => ({ ok: false, error: "Could not read live settings" }));
    renderPresetCurrentCapture(data);
    return data;
  }

  async function openPresetBuilderFromCurrent() {
    const data = presetCurrentCapture?.ok && presetCurrentCapture.available !== false
      ? presetCurrentCapture
      : await loadPresetCurrentCapture();
    if (!data?.ok || data.available === false) return toast(data?.error || "Could not capture current setup", false);
    await openPresetBuilder(data.spec || {});
    if ((data.warnings || []).length) renderPresetBuilderWarnings(data.warnings);
  }

  function closePresetBuilder() {
    if (!presetBuilderSchema?.ok) return;
    clearPresetBuilderEditMode();
    const schema = presetBuilderSchema;
    const defs = schema.defaults || {};
    fillPresetBuilderFromSpec(defs);
    $("presetBuilderPreview")?.classList.add("hidden");
    $("presetBuilderWarnings")?.classList.add("hidden");
    const warn = $("presetBuilderWarnings");
    if (warn) warn.innerHTML = "";
  }

  async function createPresetFromBuilder() {
    const spec = readPresetBuilderSpec();
    if (!spec.label?.trim()) return toast("Give the preset a name", false);
    if (!spec.summary?.trim()) spec.summary = suggestPresetSummaryLabel(spec);
    if (!spec.summary?.trim()) return toast("Add a short “What it does” line for the preset card", false);
    if (spec.meshnet_peer && !spec.mesh_peer_value && !(presetBuilderSchema?.config_hints?.mesh_peer)) {
      return toast("Enter a Meshnet peer hostname (e.g. my-phone.nord)", false);
    }
    const editing = Boolean(presetBuilderEdit?.file_id);
    const name = spec.filename || slugifyPresetName(spec.label);
    const res = editing
      ? await api("/api/presets/builder/update", {
          method: "POST",
          body: JSON.stringify({ file_id: presetBuilderEdit.file_id, spec }),
        })
      : await api("/api/presets/builder/create", {
          method: "POST",
          body: JSON.stringify({ name, spec }),
        });
    if (!res.ok) return toast(res.error || (editing ? "Could not update preset" : "Could not save preset"), false);
    lastCreatedPreset = {
      label: spec.label,
      file_id: res.id,
      document: res.document,
      spec,
    };
    toast(editing ? `Preset “${spec.label}” updated` : `Preset “${spec.label}” saved — run it from My presets when ready`, true);
    showPresetBuilderSavedBanner(lastCreatedPreset, { updated: editing });
    clearPresetBuilderEditMode();
    togglePresetBuilderFold(false);
    closePresetBuilder();
    await loadState(true);
  }

  function initPresetBuilderEvents() {
    $("btnOpenPresetBuilder")?.addEventListener("click", () => {
      clearPresetBuilderEditMode();
      openPresetBuilder();
    });
    $("btnTogglePresetBuilder")?.addEventListener("click", () => togglePresetBuilderFold());
    $("btnTogglePresetBuilderHead")?.addEventListener("click", () => togglePresetBuilderFold());
    $("btnPresetFromCurrent")?.addEventListener("click", () => openPresetBuilderFromCurrent());
    $("btnPresetFromCurrentRefresh")?.addEventListener("click", () => loadPresetCurrentCapture());
    $("btnPresetBuilderCancel")?.addEventListener("click", closePresetBuilder);
    $("btnPresetBuilderCreate")?.addEventListener("click", createPresetFromBuilder);
    $("btnPresetBuilderPreview")?.addEventListener("click", async () => {
      const res = await refreshPresetBuilderCompatibility();
      if (res?.breakdown) renderPresetBuilderPreview(res.breakdown);
    });
    $("pbLabel")?.addEventListener("input", (e) => {
      const fn = $("pbFilename");
      if (fn && !fn.dataset.userEdited) fn.value = slugifyPresetName(e.target.value);
      maybeAutoFillPresetSummary();
      schedulePresetBuilderPreview();
    });
    $("pbFilename")?.addEventListener("input", (e) => {
      e.target.dataset.userEdited = e.target.value ? "1" : "";
    });
    $("pbSummary")?.addEventListener("input", (e) => {
      e.target.dataset.userEdited = e.target.value.trim() ? "1" : "";
    });
    [
      "pbConnectionMode", "pbServerGroup", "pbCountrySource", "pbCitySource",
      "pbCountry", "pbCity", "pbTechnology", "pbProtocol", "pbNordDns", "pbFwmark",
      "pbSummary", "pbMeshPeerValue",
    ].forEach((id) => {
      $(id)?.addEventListener("change", () => {
        if (id === "pbConnectionMode" || id === "pbServerGroup") maybeAutoFillPresetSummary();
        schedulePresetBuilderPreview();
      });
      $(id)?.addEventListener("input", schedulePresetBuilderPreview);
    });
    $("pbCountry")?.addEventListener("change", (e) => populatePresetBuilderCities(e.target.value));
    $("pbCountrySource")?.addEventListener("change", async () => {
      if ($("pbCountrySource")?.value === "inline") await ensurePresetBuilderCountries();
      document.querySelector(".pb-inline-country")?.classList.toggle("hidden", $("pbCountrySource")?.value !== "inline");
      schedulePresetBuilderPreview();
    });
    $("pbCitySource")?.addEventListener("change", () => {
      document.querySelector(".pb-inline-city")?.classList.toggle("hidden", $("pbCitySource")?.value !== "inline");
      schedulePresetBuilderPreview();
    });
    // Builder is inline; Esc should not hide/reset it.
  }

  async function initPresetBuilderPage() {
    bindViewJumps($("createPresetsHub"));
    if (lastState) renderCreatePresetsList(lastState);
    populatePresetBuilderMeshPeerList(lastState?.mesh_peers_raw);
    await loadPresetCurrentCapture();
    await ensurePresetBuilderReady();
    updatePresetBuilderFoldButtons();
    if (pendingPresetEditId && lastState) {
      const pid = pendingPresetEditId;
      pendingPresetEditId = null;
      const preset = [...(lastState.presets || []), ...(lastState.hidden_presets || [])]
        .find((p) => p.id === pid);
      if (preset?.user) await openPresetBuilderForEdit(preset);
    }
    if (pendingPresetBuilderSpec) {
      const spec = pendingPresetBuilderSpec;
      pendingPresetBuilderSpec = null;
      await openPresetBuilder(spec);
      setPresetBuilderEditMode(false);
    }
  }

  const NORD_DOC_GROUPS = [
    { title: "Install & daemon", ids: ["nordvpn_cli", "nordvpnd", "nord_version"] },
    { title: "Account", ids: ["nordvpn_login", "connect_country", "nordvpn_group"] },
    { title: "VPN session", ids: ["nord_vpn_connected", "nord_technology", "nord_autoconnect"] },
    { title: "Features", ids: ["nord_meshnet", "nord_dns_setting", "nord_threat_protection", "nordctl_smart_dns"] },
    { title: "Travel safety", ids: ["nord_firewall", "nord_killswitch"] },
  ];

  function nordDoctorCheckRowHtml(c) {
    const st = doctorCheckStatus(c);
    const fixes = (c.fix || []).filter(Boolean);
    const fixBtn = c.action && !c.ok
      ? `<div class="doctor-check-actions"><button type="button" class="btn sm primary wifi-doc-fix" data-action="${esc(c.action)}" data-prefix="nord" data-confirm="1">Fix now</button></div>`
      : "";
    return `<div class="doctor-check-row ${st.cls}">
      <div class="doctor-check-head">
        <span class="doctor-check-icon" aria-hidden="true">${c.ok ? "✓" : "!"}</span>
        <span class="doctor-check-title">${esc(c.summary)}</span>
        <span class="doctor-status">${st.label}</span>
      </div>
      <p class="doctor-check-detail">${esc(doctorCheckExplain(c))}</p>
      ${fixes.length > 1 ? `<ul class="doctor-check-fixes">${fixes.slice(1).map((f) => `<li>${esc(f)}</li>`).join("")}</ul>` : ""}
      ${fixBtn}
    </div>`;
  }

  function renderNordDoctorPanel(doc) {
    const badge = $("nordDocBadge");
    const summary = $("nordDocSummary");
    const stats = $("nordDocStats");
    const checksBox = $("nordDocChecks");
    if (!doc || !checksBox) return;
    const checks = doc.checks || [];
    const all = doc.all_checks || [];
    const passed = checks.filter((c) => c.ok).length;
    const tips = doc.warning_count || checks.filter((c) => !c.ok && c.severity !== "error").length;
    const block = doc.blocking_count || checks.filter((c) => !c.ok && c.severity === "error").length;
    if (badge) {
      badge.textContent = block ? `${block} to fix` : tips ? `${tips} tips` : checks.length ? "All OK" : "—";
      badge.className = "badge " + (block ? "off" : tips ? "warn" : checks.length ? "on" : "");
    }
    if (summary) {
      summary.innerHTML = [
        `<p><strong>${esc(doc.title || "NordVPN doctor")}</strong> — ${esc(doc.hint || "Daemon, account, and travel-safe Nord settings.")}</p>`,
        block
          ? `<p class="help-text" style="margin:0.45rem 0 0">Fix items marked <strong>Fix</strong> first — presets and connect may fail until NordVPN is installed, logged in, and running.</p>`
          : tips
            ? `<p class="help-text" style="margin:0.45rem 0 0">Optional tips improve security on public WiFi — enable firewall and kill switch when you travel.</p><div class="panel-nav-actions inline-jump-actions" style="margin:0.35rem 0 0"><button type="button" class="btn sm jump-link" data-view-jump="dashboard/switches">Open Switches</button></div>`
            : `<p class="help-text" style="margin:0.45rem 0 0">Everything looks good for NordVPN on this machine.</p>`,
        `<div class="doctor-stats">`,
        `<span class="badge on">${passed} passed</span>`,
        tips ? `<span class="badge warn">${tips} tips</span>` : "",
        block ? `<span class="badge off">${block} must fix</span>` : "",
        `<span class="muted">Showing ${checks.length} of ${all.length || checks.length} checks</span>`,
        `</div>`,
      ].join("");
      bindViewJumps(summary);
    }
    if (stats) {
      stats.innerHTML = [
        statCell("Checks passed", String(passed), passed === checks.length && checks.length ? "on" : ""),
        statCell("Tips", String(tips), tips ? "warn" : "on"),
        statCell("Must fix", String(block), block ? "off" : "on"),
        statCell("Status", block ? "Needs work" : tips ? "Mostly OK" : "Healthy", block ? "off" : tips ? "warn" : "on"),
      ].join("");
    }
    const byId = Object.fromEntries(checks.map((c) => [c.id, c]));
    const grouped = NORD_DOC_GROUPS.map((g) => ({
      ...g,
      items: g.ids.map((id) => byId[id]).filter(Boolean),
    })).filter((g) => g.items.length);
    const used = new Set(grouped.flatMap((g) => g.items.map((c) => c.id)));
    const extra = checks.filter((c) => !used.has(c.id));
    if (extra.length) grouped.push({ title: "Other", items: extra });
    checksBox.innerHTML = grouped.map((g) =>
      `<section class="nord-doc-group">
        <h3 class="nord-doc-group-title">${esc(g.title)}</h3>
        <div class="nord-doc-grid grid-4">${g.items.map(nordDoctorCheckRowHtml).join("")}</div>
      </section>`
    ).join("") || `<p class="muted">No checks to show — enable items under Customize visible checks.</p>`;
    checksBox.querySelectorAll(".wifi-doc-fix").forEach((btn) => {
      btn.addEventListener("click", () => runNordDoctorFix(btn.dataset.action));
    });
    applyButtonTitles(checksBox);
  }

  function renderNordDoctorVisibility(doc) {
    const box = $("nordDocVisibility");
    if (!box || !doc) return;
    const hidden = new Set(doc.hidden || []);
    const all = doc.all_checks || [];
    if (!all.length) {
      box.innerHTML = "";
      return;
    }
    box.innerHTML = `<p class="help-text">Toggle checks shown in the cards above:</p><div class="doctor-visibility-grid nord-doc-vis-grid">${
      all.map((c) =>
        `<label class="nord-doc-vis-chip doctor-vis-item"><input type="checkbox" data-nord-doc-id="${esc(c.id)}" ${hidden.has(c.id) ? "" : "checked"} /><span>${esc(c.label)}</span></label>`
      ).join("")
    }</div>`;
    box.querySelectorAll("input[data-nord-doc-id]").forEach((inp) => {
      inp.addEventListener("change", saveNordDoctorVisibility);
    });
  }

  async function saveNordDoctorVisibility() {
    const box = $("nordDocVisibility");
    if (!box) return;
    const hidden = [];
    box.querySelectorAll("input[data-nord-doc-id]").forEach((inp) => {
      if (!inp.checked) hidden.push(inp.getAttribute("data-nord-doc-id"));
    });
    const res = await doAction({ action: "nord_doctor_prefs", hidden }, "Doctor visibility");
    if (res.ok && res.doctor) {
      renderNordDoctorPanel(res.doctor);
      renderNordDoctorVisibility(res.doctor);
    }
  }

  async function runNordDoctorFix(action) {
    const map = {
      nord_firewall_on: { action: "nord_firewall", value: "on" },
      nord_killswitch_on: { action: "nord_killswitch", value: "on" },
    };
    const body = map[action] || { action };
    const res = await doAction(body, action);
    if (res.ok) await loadNordDoctor(true);
  }

  async function loadScenarios(force) {
    await refreshLocationScenarios(force);
  }

  function renderConnectScenarios(data) {
    const grid = $("connectScenarioGrid");
    if (!grid || !data?.ok) return;
    grid.innerHTML = (data.scenarios || []).map((s) =>
      `<button type="button" class="wifi-scenario-btn" data-preset="${esc(s.id)}" data-confirm="1" title="${esc(s.hint || "")}"><strong>${esc(s.emoji || "")} ${esc(s.label)}</strong><span>${esc(s.hint || "")}</span></button>`
    ).join("");
    grid.querySelectorAll(".wifi-scenario-btn").forEach((b) => {
      b.addEventListener("click", () => doAction({ action: "preset", preset: b.dataset.preset }, b.querySelector("strong")?.textContent || "Preset"));
    });
  }

  async function loadConnectExtras(force) {
    try {
      const wifiTtl = force ? 0 : CACHE_TTL.wifi;
      const secTtl = force ? 0 : CACHE_TTL.securitySummary;
      const [wifi, summary] = await Promise.all([
        apiCached("/api/wifi/hub", {}, wifiTtl),
        apiCached("/api/security/summary", {}, secTtl),
      ]);
      renderConnectScenarios(wifi);
      if (summary?.ok) {
        renderLocationScenarios({
          scenarios: summary.location_profiles,
          hidden_scenarios: summary.hidden_scenarios,
        });
      }
    } catch (e) {
      toast(String(e), false);
    }
  }

  function renderDnsAssistantPanel(rep) {
    const findings = rep?.findings || [];
    const tips = rep?.tips || [];
    const detected = findings.filter((f) => f.detected).length;
    const active = findings.filter((f) => f.active).length;
    const clear = active === 0;
    if ($("secDnsBadge")) {
      $("secDnsBadge").textContent = active ? `${active} active` : "Clear";
      $("secDnsBadge").className = "badge " + (clear ? "on" : "warn");
    }
    if ($("secDnsMetrics")) {
      $("secDnsMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Services scanned</div><div class="val">${findings.length}</div><div class="sub">Pi-hole, Unbound, resolved</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Detected</div><div class="val">${detected}</div><div class="sub">Installed or running</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Active conflicts</div><div class="val ${active ? "warn" : "on"}">${active}</div><div class="sub">May affect Nord DNS</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Status</div><div class="val ${clear ? "on" : "warn"}">${clear ? "Clear" : "Review"}</div><div class="sub">${tips.length} tip(s)</div></div>`,
      ].join("");
    }
    const dns = $("secDnsAssistant");
    if (dns) {
      dns.innerHTML = findings.length
        ? findings.map((f) => {
          const status = f.active ? "Active" : (f.detected ? "Detected" : "Not found");
          const cls = f.active ? "warn" : (f.detected ? "on" : "off");
          return `<article class="dns-finding-card ${f.active ? "dns-finding-active" : ""}">
            <div class="dns-finding-head">
              <strong>${esc(f.name)}</strong>
              <span class="badge ${cls}">${esc(status)}</span>
            </div>
            <p class="dns-finding-detail">${esc(f.detail || "—")}</p>
          </article>`;
        }).join("")
        : `<div class="page-empty"><strong>No DNS services scanned</strong>Refresh security summary to rebuild this report.</div>`;
    }
    const tipsBox = $("secDnsTipsBox");
    const tipsEl = $("secDnsTips");
    if (tipsBox && tipsEl) {
      tipsBox.classList.toggle("hidden", !tips.length);
      tipsEl.innerHTML = tips.map((t) => `<li>${esc(t)}</li>`).join("");
    }
    drawDnsAssistantChart(findings);
  }

  function renderSecurityHub(data) {
    if (!data?.ok) return;
    const h = data.health || {};
    const ring = $("secScoreRing");
    if ($("secHealthScore")) $("secHealthScore").textContent = h.score ?? "—";
    const grade = $("secHealthGrade");
    if (grade) {
      grade.textContent = h.grade || "—";
      grade.className = "badge " + (h.color || "off");
    }
    if (ring) {
      ring.classList.remove("warn", "off");
      if (h.color === "warn") ring.classList.add("warn");
      if (h.color === "off") ring.classList.add("off");
    }
    recordHealthScore(h.score);
    drawSecHealthCharts(h);
    if ($("secHealthSummary")) $("secHealthSummary").textContent = h.summary || "";
    const checkList = h.checks || [];
    const passN = checkList.filter((c) => c.ok).length;
    const failN = checkList.length - passN;
    if ($("secHealthMetrics")) {
      $("secHealthMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Health score</div><div class="val">${esc(String(h.score ?? "—"))}</div><div class="sub">Combined checks</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Grade</div><div class="val">${esc(h.grade || "—")}</div><div class="sub">A–F scale</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Passing</div><div class="val on">${passN}</div><div class="sub">Of ${checkList.length} checks</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Needs review</div><div class="val ${failN ? "warn" : "on"}">${failN}</div><div class="sub">Open linked tabs to fix</div></div>`,
      ].join("");
    }
    const checks = $("secHealthChecks");
    if (checks) {
      checks.innerHTML = checkList.map((c) => {
        const route = healthFixRoute(c.fix);
        const fix = route && !c.ok
          ? `<div class="doctor-check-actions"><button type="button" class="btn sm sec-health-fix jump-link" data-view-jump="${esc(route)}" title="${esc(c.fix)}">Inspect</button></div>`
          : "";
        return `<li class="doctor-check-card sec-health-card ${c.ok ? "ok" : "bad"}">
          <div class="doctor-check-head"><strong>${esc(c.name)}</strong><span class="badge ${c.ok ? "on" : "warn"}">${c.ok ? "OK" : "Review"}</span></div>
          <p class="doctor-check-detail">${esc(c.detail)}</p>${fix}</li>`;
      }).join("") || `<li class="page-empty"><strong>No health checks yet</strong>Refresh or open leak tests to populate this view.</li>`;
      bindViewJumps(checks);
    }

    renderDnsAssistantPanel(data.dns_assistant || {});

    const v6 = $("secIpv6Lan");
    const v6Notice = $("secIpv6LocalNotice");
    if (v6Notice) v6Notice.innerHTML = localNetworkNoticeHtml({ scope: "ipv6" });
    if (v6) {
      const rep = data.ipv6_lan || {};
      v6.innerHTML = (rep.modes || []).map((m) =>
        `<p>${m.active ? "●" : "○"} <strong>${esc(m.label)}</strong> — ${esc(m.hint || "")}</p>`
      ).join("") + (rep.recommendation ? `<p class="help-text">${esc(rep.recommendation)}</p>` : "");
      const activeMode = (rep.modes || []).find((m) => m.active);
      $("secIpv6Badge") && ($("secIpv6Badge").textContent = activeMode?.label || "—");
    }

    const dw = data.disconnect_watch || {};
    renderDisconnectWatchStats(dw, $("settingsDisconnectWatch"));

    const links = $("secQuickLinks");
    if (links) {
      links.innerHTML = `<div class="panel-nav-actions" style="margin:0">${(data.quick_links || []).map((l) =>
        openUrlBtn(l.url, l.label)
      ).join("")}</div>`;
      bindOpenUrlButtons(links);
    }

    const mesh = data.meshnet || {};
    if ($("secMeshnet")) {
      $("secMeshnet").innerHTML = [
        `<p>Meshnet: <strong>${mesh.enabled ? "On" : "Off"}</strong></p>`,
        `<p>Mesh IP: <strong>${esc(mesh.mesh_ip || "—")}</strong> · Peers: ${mesh.peer_count || 0}</p>`,
        mesh.peers?.length ? `<ul class="sec-check-list">${mesh.peers.map((p) => `<li>${esc(typeof p === "string" ? p : (p.name || p.hostname || JSON.stringify(p)))}</li>`).join("")}</ul>` : "",
      ].join("");
    }

    const sched = data.schedules_summary || {};
    if ($("secSchedules")) {
      $("secSchedules").innerHTML = [
        `<p><strong>${sched.count || 0}</strong> schedule(s) · <strong>${sched.enabled || 0}</strong> enabled</p>`,
        `<p class="muted">${esc(sched.hint || "")}</p>`,
      ].join("");
    }

    const sp = data.status_page || {};
    secStatusUrl = sp.url || "";
    const spBox = $("secStatusPage");
    if (spBox) {
      spBox.innerHTML = [
        statCell("Status page", sp.enabled ? "Enabled" : "Disabled", sp.enabled ? "on" : "off"),
        statCell("LAN note", sp.lan_note ? "See Help" : "—", ""),
      ].join("");
    }

    const ha = data.homeassistant || {};
    if ($("secHaYaml")) $("secHaYaml").textContent = ha.yaml_snippet || "—";
  }

  let wifiLiveTimer = null;

  function stopWifiLive() {
    if (wifiLiveTimer) {
      clearInterval(wifiLiveTimer);
      wifiLiveTimer = null;
    }
  }

  function startWifiLive() {
    stopWifiLive();
    wifiLiveTimer = setInterval(() => loadWifiHub(true, true), 15000);
  }

  function renderDoctorPanel(doc, badgeId, listId, prefix) {
    const badge = $(badgeId);
    const list = $(listId);
    if (!doc || !list) return;
    const warn = doc.warning_count || 0;
    const block = doc.blocking_count || 0;
    const total = (doc.checks || []).length;
    const okN = (doc.checks || []).filter((c) => c.ok).length;
    if (badge) {
      badge.textContent = block ? `${block} fix` : warn ? `${warn} tip` : "OK";
      badge.className = "badge " + (block ? "off" : warn ? "warn" : "on");
    }
    if (listId === "netDocChecks" && $("netDocMetrics")) {
      $("netDocMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Checks</div><div class="val">${total}</div><div class="sub">Network path</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Passing</div><div class="val on">${okN}</div><div class="sub">No action needed</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Warnings</div><div class="val ${warn ? "warn" : "on"}">${warn}</div><div class="sub">Review recommended</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Blocking</div><div class="val ${block ? "off" : "on"}">${block}</div><div class="sub">Fix before presets</div></div>`,
      ].join("");
    }
    const cardMode = listId === "netDocChecks" || list.classList.contains("doctor-check-grid");
    list.innerHTML = (doc.checks || []).map((c) => {
      const fixBtn = c.action && !c.ok
        ? `<div class="doctor-check-actions"><button type="button" class="btn sm wifi-doc-fix" data-action="${esc(c.action)}" data-prefix="${prefix}" data-confirm="1">Fix</button></div>`
        : "";
      const hint = (c.fix || []).length ? `<div class="check-detail">${esc(c.fix[0])}</div>` : "";
      if (cardMode) {
        return `<li class="doctor-check-card ${c.ok ? "ok" : "bad"}">
          <div class="doctor-check-head"><strong>${esc(c.summary)}</strong><span class="badge ${c.ok ? "on" : (c.severity === "error" ? "off" : "warn")}">${c.ok ? "OK" : "Fix"}</span></div>
          ${hint}${fixBtn}</li>`;
      }
      return `<li class="${c.ok ? "ok" : "bad"}"><strong>${esc(c.summary)}</strong>${fixBtn.replace(/<div class="doctor-check-actions">|<\/div>/g, "")}${hint}</li>`;
    }).join("") || `<li class="page-empty"><strong>No checks returned</strong>Re-run checks to refresh this panel.</li>`;
    list.querySelectorAll(".wifi-doc-fix").forEach((btn) => {
      btn.addEventListener("click", () => runWifiDoctorFix(btn.dataset.action, btn.dataset.prefix));
    });
  }

  async function runWifiDoctorFix(action, prefix) {
    const map = {
      wifi_sync_profiles: { action: "wifi_sync_profiles" },
      wifi_remove_stale_profiles: { action: "wifi_remove_stale_profiles" },
      wifi_heal_smart_dns: { action: "dns_apply_smart" },
      dns_apply_smart: { action: "dns_apply_smart" },
      disable_ipv6: { action: "disable_ipv6" },
      nord_firewall_on: { action: "nord_firewall", value: "on" },
      nord_killswitch_on: { action: "nord_killswitch", value: "on" },
    };
    const body = map[action] || { action };
    await doAction(body, action);
    loadWifiHub(true);
  }

  function renderWifiHub(data) {
    if (!data?.ok) return;
    const wifiNotice = $("wifiLocalNetworkNotice");
    if (wifiNotice) wifiNotice.innerHTML = localNetworkNoticeHtml({ scope: "wifi_dns" });
    mountBaselineSafetyNotice("wifiBaselineNotice", data);
    const conn = data.connection || {};
    const sig = (data.nearby || []).find((n) => n.in_use);
    const signalEl = $("wifiSignalBadge");
    if (signalEl) {
      signalEl.textContent = sig ? `${sig.signal}%` : conn.connected ? "ON" : "—";
      signalEl.classList.toggle("weak", sig && sig.signal < 40);
      signalEl.classList.toggle("off", !conn.connected);
    }
    if (sig?.signal != null) pushWifiSignalSample(sig.signal);
    const badge = $("wifiConnBadge");
    if (badge) {
      badge.textContent = conn.connected ? "Connected" : "Offline";
      badge.className = "badge " + (conn.connected ? "on" : "off");
    }
    $("wifiConnSummary") && ($("wifiConnSummary").textContent =
      conn.connected
        ? `On ${conn.ssid || "WiFi"} via profile “${conn.active_profile || "?"}”. Device ${conn.device || "—"}.`
        : "Connect to WiFi in system settings, then sync profiles for Smart DNS.");
    $("wifiConnStats") && ($("wifiConnStats").innerHTML = [
      statCell("SSID", esc(conn.ssid || "—")),
      statCell("Profile", esc(conn.active_profile || "—")),
      statCell("Live DNS", esc((conn.live_dns || []).join(", ") || "—")),
      statCell(conn.public_ip_note ? "Home ISP (allowlist)" : "Public IP", esc(conn.public_ip || "—")),
      ...(conn.public_ip_routed && conn.public_ip_routed !== conn.public_ip
        ? [statCell("VPN exit IP", esc(conn.public_ip_routed), "warn")]
        : []),
      ...(conn.public_ip_note
        ? [`<div class="lbl span3 help-text" style="margin:0;padding:0 0 0.15rem">${esc(conn.public_ip_note)}</div>`]
        : []),
    ].join(""));

    const drift = conn.smart_dns_drift || {};
    const dnsStatus = $("wifiDnsStatus");
    if (dnsStatus) {
      dnsStatus.innerHTML = [
        statCell("Expected", esc([conn.primary, conn.secondary].filter(Boolean).join(", ") || "—")),
        statCell("Live DNS", esc((conn.live_dns || []).join(", ") || "—")),
        statCell("Drift", drift.drift ? "Yes ⚠" : "No", drift.drift ? "warn" : "on"),
        statCell("Detail", esc(drift.detail || "Profiles match") || "—"),
      ].join("");
    }

    const sh = data.self_heal || {};
    const zw = data.zone_watch || {};
    $("wifiHealToggles") && ($("wifiHealToggles").innerHTML = [
      `<label><input type="checkbox" id="wifiHealSync" ${sh.auto_sync_active ? "checked" : ""} /> Auto-sync active profile to config</label>`,
      `<label><input type="checkbox" id="wifiHealDns" ${sh.heal_smart_dns ? "checked" : ""} /> Re-apply Smart DNS when drift detected</label>`,
    ].join(""));
    $("wifiWatchStats") && ($("wifiWatchStats").innerHTML = [
      statCell("Zone watcher", zw.running ? "Running" : "Stopped", zw.running ? "on" : "off"),
      statCell("Auto-apply zones", zw.auto_apply ? "Yes" : "No", zw.auto_apply ? "on" : ""),
    ].join(""));

    const table = $("wifiProfileTable");
    if (table) {
      const rows = data.profiles || [];
      const inConfig = rows.filter((r) => r.in_config).length;
      $("wifiProfileSummary") && ($("wifiProfileSummary").textContent =
        `${inConfig} of ${rows.length} profile(s) tracked in config — only tracked profiles get Smart DNS, zones, and self-heal.`);
      const stale = rows.filter((r) => r.in_config && !r.exists_in_nm);
      const staleBanner = stale.length
        ? `<div class="wifi-stale-banner"><span>${stale.length} profile(s) in config not found in NetworkManager: <strong>${esc(stale.map((r) => r.name).join(", "))}</strong></span><button type="button" class="btn sm danger" id="btnWifiRemoveStale" data-confirm="1" data-confirm-message="Remove WiFi profile names from config that no longer exist in NetworkManager?">Remove stale</button></div>`
        : "";
      table.innerHTML = [
        staleBanner,
        `<div class="wifi-prof-row head"><span>Profile</span><span>DNS</span><span>SSID</span><span>In config</span><span>Actions</span></div>`,
        ...rows.map((r) => {
          const cls = `wifi-prof-row${r.active ? " active" : ""}`;
          const dns = (r.dns_servers || []).join(", ") || (r.ignore_auto_dns ? "locked" : "auto");
          const cfgCell = r.in_config
            ? `<span class="wifi-config-yes">Yes</span>`
            : `<span class="wifi-config-no">No</span>`;
          const configBtn = r.in_config
            ? `<button type="button" class="btn sm wifi-prof-remove" data-name="${esc(r.name)}" data-confirm="1" data-confirm-message="Remove “${esc(r.name)}” from nordctl config? (Does not delete the WiFi profile from your system.)">Remove from config</button>`
            : `<button type="button" class="btn sm primary wifi-prof-add" data-name="${esc(r.name)}" data-confirm="1" title="Track this profile in config.yaml for Smart DNS and zones">Add to config</button>`;
          const connectBtn = r.exists_in_nm && !r.active
            ? `<button type="button" class="btn sm wifi-prof-connect" data-name="${esc(r.name)}" data-confirm="1" data-confirm-message="Connect using saved profile “${esc(r.name)}”?">Connect</button>`
            : "";
          const deleteBtn = r.exists_in_nm
            ? `<button type="button" class="btn sm danger wifi-prof-delete" data-name="${esc(r.name)}" data-confirm="1" data-confirm-message="Delete WiFi profile “${esc(r.name)}” from NetworkManager? This removes the saved network, not just nordctl config.">Delete profile</button>`
            : "";
          const actions = `<span class="wifi-prof-actions">${connectBtn}${configBtn}${deleteBtn}</span>`;
          return `<div class="${cls}"><span>${esc(r.name)}${r.active ? " ★" : ""}</span><span>${esc(dns)}</span><span>${esc(r.ssid || "—")}</span><span>${cfgCell}</span><span>${actions}</span></div>`;
        }),
      ].join("");
      table.querySelectorAll(".wifi-prof-add").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "wifi_profile_toggle", name: b.dataset.name, add: true }, "Add profile").then(() => loadWifiHub(true)));
      });
      table.querySelectorAll(".wifi-prof-remove").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "wifi_profile_toggle", name: b.dataset.name, add: false }, "Remove profile").then(() => loadWifiHub(true)));
      });
      table.querySelectorAll(".wifi-prof-connect").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "wifi_connect", profile: b.dataset.name }, "Connect WiFi").then(() => loadWifiHub(true)));
      });
      table.querySelectorAll(".wifi-prof-delete").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "wifi_delete_profile", name: b.dataset.name }, "Delete profile").then(() => loadWifiHub(true)));
      });
      $("btnWifiRemoveStale")?.addEventListener("click", () => doAction({ action: "wifi_remove_stale_profiles" }, "Remove stale profiles").then(() => loadWifiHub(true)));
    }

    const zc = data.zones_config || {};
    const zones = $("wifiZonesList");
    if (zones) {
      const trusted = zc.trusted || [];
      zones.innerHTML = trusted.length
        ? trusted.map((z) =>
            `<div class="wifi-zone-row"><span><strong>${esc(z.ssid)}</strong> → <code>${esc(z.preset)}</code></span><button type="button" class="btn sm wifi-zone-rm" data-ssid="${esc(z.ssid)}" data-confirm="1">Remove</button></div>`
          ).join("")
        : `<p class="muted">No trusted zones — add your home SSID above.</p>`;
      zones.querySelectorAll(".wifi-zone-rm").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "wifi_zone_remove", ssid: b.dataset.ssid }, "Zone").then(() => loadWifiHub(true)));
      });
    }
    const autoCb = $("wifiZoneAutoApply");
    if (autoCb) autoCb.checked = !!zc.auto_apply;
    const unt = $("wifiUntrustedPreset");
    if (unt) unt.value = zc.untrusted_preset || "public-wifi";
    const ssidIn = $("wifiZoneSsid");
    if (ssidIn && !ssidIn.value && data.zones?.ssid) ssidIn.placeholder = data.zones.ssid;

    const near = $("wifiNearbyList");
    if (near) {
      near.innerHTML = (data.nearby || []).length
        ? (data.nearby || []).map((n) =>
            `<div class="wifi-nearby-row${n.in_use ? " in-use" : ""}"><span>${n.in_use ? "★ " : ""}${esc(n.ssid)}</span><span>${n.signal}% · ${esc(n.security)}</span>${n.in_use || n.ssid === "(hidden)" ? "" : `<button type="button" class="btn sm wifi-nearby-connect" data-ssid="${esc(n.ssid)}" data-confirm="1">Connect</button>`}</div>`
          ).join("")
        : `<p class="muted">No scan results — click Rescan networks.</p>`;
      near.querySelectorAll(".wifi-nearby-connect").forEach((b) => {
        b.addEventListener("click", () => {
          const ssid = b.dataset.ssid || "";
          const pwd = window.prompt(`Password for “${ssid}” (leave empty for open WiFi):`, "") ?? null;
          if (pwd === null) return;
          doAction({ action: "wifi_connect", ssid, password: pwd }, "Connect WiFi").then(() => loadWifiHub(true));
        });
      });
    }

    const docs = data.doctors || {};
    renderDoctorPanel(docs.wifi, "wifiDocBadge", "wifiDocChecks", "wifi");
    drawWifiCharts(data.nearby || []);
  }

  async function loadNordDoctor(force) {
    showNordDoctorLoading();
    try {
      const data = await apiCached("/api/wifi/hub", {}, force ? 0 : CACHE_TTL.wifi);
      const doc = data.doctors?.nord;
      renderNordDoctorPanel(doc);
      renderNordDoctorVisibility(doc);
    } catch (e) {
      toast(String(e), false);
      showNordDoctorLoading();
      $("nordDocChecks") && ($("nordDocChecks").innerHTML = `<div class="val off span3">${esc(formatFetchError(e, "Nord doctor"))}</div>`);
    }
  }

  function showNordDoctorLoading() {
    const badge = $("nordDocBadge");
    if (badge) {
      badge.textContent = "…";
      badge.className = "badge";
    }
    $("nordDocSummary") && ($("nordDocSummary").innerHTML = "<p class=\"help-text\"><strong>Doctor checking — please wait…</strong></p>");
    $("nordDocStats") && ($("nordDocStats").innerHTML = "");
    $("nordDocChecks") && ($("nordDocChecks").innerHTML = "<div class=\"val span3 muted\" style=\"padding:1.25rem 0;text-align:center\">Running NordVPN health checks…</div>");
  }

  const CONN_ROLE_META = {
    device: { icon: "🖥", label: "Device", cls: "conn-role-device" },
    wifi: { icon: "📶", label: "Wi‑Fi", cls: "conn-role-wifi" },
    gateway: { icon: "↔", label: "Gateway", cls: "conn-role-gateway" },
    isp: { icon: "🌐", label: "ISP", cls: "conn-role-isp" },
    vpn: { icon: "🛡", label: "VPN", cls: "conn-role-vpn" },
    mesh: { icon: "🔗", label: "Mesh", cls: "conn-role-mesh" },
  };

  function connDetailField(label, val) {
    if (val == null || val === "" || (Array.isArray(val) && !val.length)) return "";
    const text = Array.isArray(val) ? val.join(", ") : String(val);
    return `<div class="conn-hop-field"><dt>${esc(label)}</dt><dd>${esc(text)}</dd></div>`;
  }

  function connDetailPrimaryIp(hop) {
    if (hop.ipv4) return Array.isArray(hop.ipv4) ? hop.ipv4[0] : hop.ipv4;
    if (hop.vpn?.exit_ip) return hop.vpn.exit_ip;
    return "";
  }

  function renderConnectionDetails(data) {
    const pathBox = $("connDetailPath");
    const ifBox = $("connDetailIfaces");
    const notesBox = $("connDetailNotes");
    const extraBox = $("connDetailExtra");
    const metricsBox = $("connDetailMetrics");
    const generatedEl = $("connDetailGenerated");
    const badge = $("connDetailBadge");
    if (!pathBox) return;
    if (!data?.ok) {
      if (metricsBox) metricsBox.innerHTML = "";
      pathBox.innerHTML = `<div class="page-empty"><strong>Connection details unavailable</strong>${esc(data?.error || "Try refresh.")}</div>`;
      return;
    }
    const vpn = data.vpn || {};
    const home = data.home || {};
    const hops = data.path || [];
    if (badge) {
      badge.textContent = vpn.active ? (vpn.provider_label || "VPN on") : "No VPN";
      badge.className = "badge " + (vpn.active ? "on" : "off");
    }
    if (generatedEl) {
      const ts = data.generated_at ? new Date(data.generated_at) : null;
      generatedEl.textContent = ts && !Number.isNaN(ts.getTime())
        ? `Updated ${ts.toLocaleString()}`
        : "";
    }
    if (metricsBox) {
      const exitVal = vpn.exit_ip || data.routed_public_ip || "—";
      const homeVal = home.show === false ? "Hidden" : (home.ip || "—");
      const homeSub = home.is_trusted_network ? "Trusted LAN" : (home.source || "Baseline");
      metricsBox.innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">VPN</div><div class="val ${vpn.active ? "on" : "off"}">${esc(vpn.active ? (vpn.provider_label || "Connected") : "Off")}</div><div class="sub">${vpn.active ? "Active tunnel" : "No tunnel"}</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Exit IP</div><div class="val">${esc(exitVal)}</div><div class="sub">Routed public</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Home ISP</div><div class="val">${esc(homeVal)}</div><div class="sub">${esc(homeSub)}</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Path hops</div><div class="val">${esc(String(hops.length || 0))}</div><div class="sub">Device → exit</div></div>`,
      ].join("");
    }
    pathBox.innerHTML = hops.map((hop, idx) => {
      const meta = CONN_ROLE_META[hop.role] || { icon: "•", label: hop.role || "Hop", cls: "conn-role-hop" };
      const primaryIp = connDetailPrimaryIp(hop);
      const fields = [];
      if (hop.interface) fields.push(connDetailField("Interface", hop.interface));
      if (hop.mac) fields.push(connDetailField("MAC", hop.mac));
      if (hop.ipv4) fields.push(connDetailField("IPv4", hop.ipv4));
      if (hop.ssid) fields.push(connDetailField("SSID", hop.ssid));
      if (hop.bssid) fields.push(connDetailField("BSSID", hop.bssid));
      if (hop.signal != null) fields.push(connDetailField("Signal", `${hop.signal}%`));
      if (hop.security) fields.push(connDetailField("Security", hop.security));
      if (hop.trusted_zone != null) fields.push(connDetailField("Trusted zone", hop.trusted_zone ? "Yes" : "No"));
      if (hop.source) fields.push(connDetailField("Source", hop.source));
      if (hop.detail) fields.push(connDetailField("Detail", hop.detail));
      if (hop.note) fields.push(connDetailField("Note", hop.note));
      if (hop.vpn) {
        const v = hop.vpn;
        fields.push(connDetailField("Provider", v.provider));
        fields.push(connDetailField("Detection", v.detection));
        fields.push(connDetailField("Interface", v.interface));
        fields.push(connDetailField("Tunnel local IP", v.local_ip));
        fields.push(connDetailField("Exit / public IP", v.exit_ip));
        fields.push(connDetailField("Default route via", v.default_route_device));
        if (v.nord_status) {
          Object.entries(v.nord_status).forEach(([k, val]) => fields.push(connDetailField(k, val)));
        }
        if (v.nord_settings) {
          Object.entries(v.nord_settings).forEach(([k, val]) => fields.push(connDetailField(k, val)));
        }
        if (Array.isArray(v.tunnels) && v.tunnels.length) {
          fields.push(connDetailField(
            "Tunnel interfaces",
            v.tunnels.map((t) => `${t.device} (${t.kind}) ${t.ipv4 || ""} ${t.mac || ""}`.trim()),
          ));
        }
      }
      const step = idx + 1;
      return `<article class="conn-hop ${meta.cls}" style="--conn-hop-i:${step}"><div class="conn-hop-marker" aria-hidden="true"><span class="conn-hop-icon">${meta.icon}</span><span class="conn-hop-step">${step}</span></div><div class="conn-hop-body"><div class="conn-hop-head"><span class="conn-hop-role">${esc(meta.label)}</span><div class="conn-hop-title">${esc(hop.label || "Hop")}${primaryIp ? `<code class="conn-hop-ip">${esc(primaryIp)}</code>` : ""}</div></div>${fields.length ? `<dl class="conn-hop-grid">${fields.join("")}</dl>` : ""}</div></article>`;
    }).join("") || "<div class=\"page-empty\"><strong>No path data</strong>Refresh to rebuild the connection snapshot.</div>";

    if (notesBox) {
      const notes = data.notes || [];
      notesBox.innerHTML = notes.length
        ? notes.map((n) => `<p class="help-text">${esc(n)}</p>`).join("")
        : "";
    }

    const ifaces = data.interfaces || [];
    if (ifBox) {
      ifBox.innerHTML = ifaces.length
        ? `<div class="conn-iface-table-wrap"><table class="help-table conn-iface-table"><thead><tr><th>Interface</th><th>State</th><th>MAC</th><th>IPv4</th><th>IPv6</th></tr></thead><tbody>${
          ifaces.map((i) => `<tr><td><strong>${esc(i.name)}</strong></td><td><span class="conn-iface-state ${esc(i.state === "up" ? "on" : "off")}">${esc(i.state)}</span></td><td>${esc(i.mac || "—")}</td><td>${esc((i.ipv4 || []).join(", ") || "—")}</td><td>${esc((i.ipv6 || []).slice(0, 2).join(", ") || "—")}</td></tr>`).join("")
        }</tbody></table></div>`
        : "<div class=\"page-empty\"><strong>No interfaces reported</strong></div>";
    }

    if (extraBox) {
      const routes = (data.routes || []).join("\n");
      const dns = data.dns || {};
      extraBox.innerHTML = [
        "<h4>Default route</h4>",
        `<pre class="code-block">${esc(JSON.stringify(data.default_route || {}, null, 2))}</pre>`,
        '<div class="conn-detail-routes-block">',
        "<h4>Routing table</h4>",
        `<pre class="code-block">${esc(routes || "—")}</pre>`,
        "</div>",
        "<h4>DNS (active WiFi)</h4>",
        `<pre class="code-block">${esc((dns.servers || []).join("\n") || "—")}</pre>`,
        dns.resolvectl ? `<details><summary>resolvectl status</summary><pre class="code-block">${esc(dns.resolvectl)}</pre></details>` : "",
        "<h4>Top bar IP snapshot</h4>",
        `<pre class="code-block">${esc(JSON.stringify(data.ip_info || {}, null, 2))}</pre>`,
      ].join("");
    }
    renderNetworkRoutes(data);
  }

  function renderNetworkRoutes(data) {
    const routesBox = $("networkOverviewRoutes");
    if (!routesBox || !data) return;
    const routes = (data.routes || []).join("\n");
    routesBox.textContent = routes || "—";
  }

  async function loadNetworkRoutes(force) {
    try {
      const data = await apiCached("/api/connection-details", {}, force ? 0 : CACHE_TTL.connectionDetails);
      renderNetworkRoutes(data);
    } catch {
      const routesBox = $("networkOverviewRoutes");
      if (routesBox) routesBox.textContent = "Could not load routing table.";
    }
  }

  async function loadConnectionDetails(force) {
    const pathBox = $("connDetailPath");
    const metricsBox = $("connDetailMetrics");
    if (metricsBox) metricsBox.innerHTML = "";
    if (pathBox) pathBox.innerHTML = "<div class=\"page-empty\"><strong>Loading connection path…</strong>Probing interfaces, routes, and VPN state.</div>";
    try {
      const data = await apiCached("/api/connection-details", {}, force ? 0 : CACHE_TTL.connectionDetails);
      renderConnectionDetails(data);
    } catch (e) {
      if (pathBox) pathBox.innerHTML = `<div class="val off span3">${esc(formatFetchError(e, "Connection details"))}</div>`;
      toast(String(e), false);
    }
  }

  const PC_INFO_INTROS = {
    system: "Identity of this machine in Linux — hostname, distro, kernel, boot time, and who is logged in. Useful when you need to know exactly which box you are managing.",
    cpu: "The brain of your PC. Core count, cache, current speed, load averages, and temperature tell you how busy and how healthy the processor is right now.",
    memory: "Working RAM and swap space. Bars show live usage; module details reveal exact DIMM type (DDR4/DDR5), speed, and slot layout when SMBIOS is available.",
    storage: "Every physical drive with model, bus, partitions, and usage. Root filesystem bar shows how full your main disk is.",
    firmware: "SMBIOS/DMI data burned into the motherboard — manufacturer, model, BIOS version, and serial numbers for support and warranty.",
    buses: "PCI and USB inventories list expansion cards and plugged-in devices. Collapsed by default when the list is long.",
    gpu: "Graphics and sound hardware — discrete GPUs via PCI, built-in DRM cards, and ALSA audio devices.",
    power: "Laptop battery health and ACPI power source, plus hardware sensor chips reporting temperature and fan speed.",
    security: "Firmware security features (EFI, TPM, Secure Boot vars) and NUMA topology for multi-socket / multi-die systems.",
  };

  function pcInfoIntro(text) {
    if (!text) return "";
    return '<p class="pc-info-section-intro">' + esc(text) + "</p>";
  }

  function pcInfoKv(label, value, opts = {}) {
    const v = value == null || value === "" ? "—" : String(value);
    const cls = opts.mono ? "v mono-sm" : "v";
    const tip = opts.tip ? ' title="' + esc(opts.tip) + '"' : "";
    return '<div class="pc-info-kv"' + tip + '><span class="k">' + esc(label) + '</span><span class="' + cls + '">' + esc(v) + "</span></div>";
  }

  function pcInfoSection(icon, title, bodyHtml) {
    return '<section class="pc-info-section"><header class="pc-info-section-head"><h3><span class="pc-info-section-icon" aria-hidden="true">' + icon + "</span> " + esc(title) + '</h3></header><div class="pc-info-section-body">' + bodyHtml + "</div></section>";
  }

  function pcInfoTable(headers, rows) {
    if (!rows.length) return '<p class="help-text muted-inline">No data available on this system.</p>';
    const head = headers.map((h) => "<th>" + esc(h) + "</th>").join("");
    const body = rows.map((row) => "<tr>" + row.map((c) => "<td>" + c + "</td>").join("") + "</tr>").join("");
    return '<div class="pc-info-table-wrap"><table class="pc-info-table"><thead><tr>' + head + "</tr></thead><tbody>" + body + "</tbody></table></div>";
  }

  function pcInfoDetails(summary, bodyHtml, count) {
    if (!bodyHtml || !String(bodyHtml).trim()) return "";
    const cnt = count != null ? ' <span class="pc-info-details-count">(' + esc(String(count)) + ")</span>" : "";
    return '<details class="pc-info-details"><summary><span class="pc-info-details-chevron" aria-hidden="true">▸</span> ' + esc(summary) + cnt + '</summary><div class="pc-info-details-body">' + bodyHtml + "</div></details>";
  }

  function pcInfoUsageBar(pct, label, opts = {}) {
    if (pct == null || Number.isNaN(Number(pct))) return "";
    const p = Math.max(0, Math.min(100, Number(pct)));
    const tone = opts.tone || (p >= 92 ? "crit" : (p >= 78 ? "warn" : ""));
    const sub = opts.sub ? '<span class="pc-info-bar-sub">' + esc(opts.sub) + "</span>" : "";
    return '<div class="pc-info-bar-row" title="' + esc(label || "") + '"><div class="pc-info-bar-head"><span>' + esc(label) + "</span><strong>" + p + "%</strong>" + sub + '</div><div class="pc-info-bar-track"><div class="pc-info-bar-fill ' + tone + '" style="width:' + p + '%"></div></div></div>';
  }

  function pcInfoLoadChart(load1, load5, load15, cores) {
    const loads = [
      { label: "1 min", val: load1 },
      { label: "5 min", val: load5 },
      { label: "15 min", val: load15 },
    ];
    const c = Math.max(1, Number(cores) || 1);
    const bars = loads.map((l) => {
      const raw = Number(l.val);
      if (Number.isNaN(raw)) return "";
      const pct = Math.min(100, Math.round((raw / c) * 100));
      const tone = pct >= 100 ? "crit" : (pct >= 75 ? "warn" : "");
      return '<div class="pc-info-load-col"><span class="pc-info-load-lbl">' + esc(l.label) + '</span><div class="pc-info-load-track"><div class="pc-info-load-fill ' + tone + '" style="height:' + pct + '%"></div></div><span class="pc-info-load-val">' + esc(raw.toFixed(2)) + "</span></div>";
    }).join("");
    return '<div class="pc-info-load-chart" title="Load average per CPU thread — 100% means all ' + c + ' threads fully busy"><div class="pc-info-load-cols">' + bars + '</div><p class="help-text muted-inline pc-info-load-hint">Load ÷ ' + c + " logical CPUs · 100% = fully saturated</p></div>";
  }

  function pcInfoFsLabel(p) {
    if (!p || !p.fstype) return "—";
    return p.fsver ? (p.fstype + " " + p.fsver) : p.fstype;
  }

  function pcInfoSectorLabel(disk) {
    if (!disk.physical_sector_bytes || !disk.logical_sector_bytes) return "—";
    return disk.physical_sector_bytes + " B phys · " + disk.logical_sector_bytes + " B log";
  }

  function pcInfoDiskCard(disk) {
    const parts = disk.partitions || [];
    const partRows = parts.map((p) => [
      esc(p.name),
      esc(p.size_human || "—"),
      esc(p.parttype_label || p.parttype || "—"),
      esc(pcInfoFsLabel(p)),
      esc(p.mountpoint || "—"),
      esc(p.label || p.partlabel || "—"),
      '<code class="mono-sm">' + esc(p.uuid || p.partuuid || "—") + "</code>",
    ]);
    const smart = disk.smart || {};
    const trimLabel = disk.trim_supported
      ? ("Yes (max " + _bytes_human_js(disk.discard_max_bytes) + ")")
      : "No";
    const sched = (disk.scheduler || "").replace(/\[|\]/g, "") || "—";
    const bus = [disk.transport, disk.subsystems].filter(Boolean).join(" · ") || "—";
    let smartBlock = "";
    if (smart.model || smart.serial) {
      smartBlock = '<h4 class="pc-info-subhead">SMART / identity</h4><div class="pc-info-spec-grid">'
        + pcInfoKv("SMART model", smart.model, { tip: "Self-Monitoring, Analysis and Reporting Technology — drive health data" })
        + pcInfoKv("SMART serial", smart.serial)
        + pcInfoKv("SMART firmware", smart.firmware)
        + pcInfoKv("Rotation", smart.rotation, { tip: "0 = SSD/NVMe, 7200/5400 = spinning rust RPM" })
        + pcInfoKv("Capacity", smart.capacity)
        + "</div>";
    }
    const partTable = parts.length
      ? pcInfoTable(["Part", "Size", "Type", "Filesystem", "Mount", "Label", "UUID"], partRows)
      : '<p class="help-text muted-inline">No partitions detected.</p>';
    return '<article class="pc-info-disk-card"><header class="pc-info-disk-head"><div><strong class="pc-info-disk-title">' + esc(disk.identity || disk.path) + '</strong><span class="pc-info-disk-role">' + esc(disk.role || "Storage") + '</span></div><span class="pc-info-disk-size">' + esc(disk.size_human || "—") + '</span></header><div class="pc-info-spec-grid">'
      + pcInfoKv("Device", disk.path, { tip: "Kernel block device path" })
      + pcInfoKv("What it is", disk.media, { tip: "NVMe SSD, SATA disk, USB stick, etc." })
      + pcInfoKv("Model", disk.model)
      + pcInfoKv("Vendor", disk.vendor)
      + pcInfoKv("Serial", disk.serial)
      + pcInfoKv("Firmware / rev", disk.firmware || disk.revision)
      + pcInfoKv("Bus / transport", bus)
      + pcInfoKv("WWN", disk.wwn, { mono: true, tip: "World Wide Name — unique SCSI/SAS identifier" })
      + pcInfoKv("HCTL (SCSI)", disk.hctl, { tip: "Host:Channel:Target:LUN for SCSI enumeration" })
      + pcInfoKv("Partition table", disk.partition_table, { tip: "GPT or MBR — how partitions are laid out" })
      + pcInfoKv("Sector size", pcInfoSectorLabel(disk))
      + pcInfoKv("I/O scheduler", sched, { tip: "Kernel algorithm for ordering disk requests" })
      + pcInfoKv("TRIM / discard", trimLabel, { tip: "SSD wear-levelling hint — lets the drive know which blocks are free" })
      + pcInfoKv("Removable", disk.removable ? "Yes" : "No")
      + pcInfoKv("State", disk.state)
      + "</div>" + smartBlock + '<h4 class="pc-info-subhead">Partitions on this disk (' + parts.length + ")</h4>" + partTable + "</article>";
  }

  function pcInfoModuleCards(modules) {
    if (!modules.length) return "";
    return '<div class="pc-info-module-grid">' + modules.map((m) => {
      const title = esc(m.slot || m.bank || "DIMM");
      const type = esc(m.memory_type || m.type_detail || "—");
      const speed = esc(m.configured_speed || m.speed || "—");
      return '<article class="pc-info-module-card"><header><strong>' + title + '</strong><span>' + esc(m.size || "—") + '</span></header><div class="pc-info-spec-grid">'
        + pcInfoKv("Type", type, { tip: "DDR generation from SMBIOS" })
        + pcInfoKv("Speed", speed)
        + pcInfoKv("Form", m.form_factor)
        + pcInfoKv("Maker", m.manufacturer)
        + pcInfoKv("Part #", m.part_number, { mono: true })
        + pcInfoKv("Serial", m.serial, { mono: true })
        + "</div></article>";
    }).join("") + "</div>";
  }

  function _bytes_human_js(n) {
    if (n == null) return "—";
    const x = Number(n);
    if (Number.isNaN(x)) return "—";
    for (const [lim, unit] of [[1024 ** 4, "TiB"], [1024 ** 3, "GiB"], [1024 ** 2, "MiB"], [1024, "KiB"]]) {
      if (x >= lim) return (x / lim).toFixed(1) + " " + unit;
    }
    return x + " B";
  }

  function _kb_human_js(kb) {
    if (kb == null) return "—";
    const n = Number(kb);
    if (Number.isNaN(n)) return "—";
    if (n >= 1024 * 1024) return (n / 1024 / 1024).toFixed(1) + " GiB";
    if (n >= 1024) return (n / 1024).toFixed(1) + " MiB";
    return n + " KiB";
  }

  function renderPcInfo(data) {
    const box = $("pcInfoSections");
    const metrics = $("pcInfoHeroMetrics");
    const badge = $("pcInfoBadge");
    const generated = $("pcInfoGenerated");
    if (!box) return;
    if (!data?.ok) {
      if (metrics) metrics.innerHTML = "";
      box.innerHTML = '<div class="page-empty"><strong>PC info unavailable</strong><p class="help-text">' + esc(data?.error || "Try refresh.") + "</p></div>";
      return;
    }
    const sys = data.system || {};
    const cpu = data.cpu || {};
    const mem = data.memory || {};
    const storage = data.storage || {};
    const fw = data.firmware || {};
    const gpu = data.gpu || {};
    const power = data.power || {};
    const runtime = data.runtime || {};
    const sec = data.security_firmware || {};

    if (badge) {
      badge.textContent = sys.hostname || "This PC";
      badge.className = "badge on";
    }
    if (generated) {
      const ts = data.generated_at ? new Date(data.generated_at) : null;
      generated.textContent = ts && !Number.isNaN(ts.getTime())
        ? "Inventory generated " + ts.toLocaleString()
        : "";
    }
    if (metrics) {
      const cpuTemp = (cpu.thermals || [])[0]?.temp_c;
      const tempSub = cpuTemp != null ? (cpuTemp + "°C") : "—";
      const memType = mem.module_summary?.type || (mem.modules_note ? "SMBIOS locked" : "—");
      const memSpeed = mem.module_summary?.speed ? (" · " + mem.module_summary.speed) : "";
      const cpuShort = ((cpu.model || "—").split("@")[0].trim().slice(0, 28));
      metrics.innerHTML = [
        '<div class="page-metric page-metric-a"><div class="lbl">⚡ Processor</div><div class="val">' + esc(cpuShort) + '</div><div class="sub">' + esc(String(cpu.cores_logical || "?")) + " threads · " + esc(tempSub) + "</div></div>",
        '<div class="page-metric page-metric-b"><div class="lbl">🧠 Memory</div><div class="val">' + esc(mem.total_human || "—") + '</div><div class="sub">' + esc(memType) + esc(memSpeed) + "</div></div>",
        '<div class="page-metric page-metric-c"><div class="lbl">💾 Storage</div><div class="val">' + esc(storage.total_capacity_human || "—") + '</div><div class="sub">' + esc(String(storage.disk_count || 0)) + " drives · " + esc(String(storage.partition_count || 0)) + " parts</div></div>",
        '<div class="page-metric page-metric-d"><div class="lbl">⏱ Uptime</div><div class="val">' + esc(sys.uptime_human || "—") + '</div><div class="sub">' + esc(sys.distro?.name || sys.kernel || "Linux") + "</div></div>",
      ].join("");
    }

    const sections = [];
    const archLabel = (sys.architecture || "—") + " (" + (sys.bitness || "—") + ")";
    const users = (runtime.logged_in_users || []).join(", ") || runtime.user;
    let sysExtra = "";
    if (sys.cmdline) {
      sysExtra = pcInfoDetails("Kernel command line (full)", '<code class="pc-info-code-block">' + esc(sys.cmdline) + "</code>", null);
    }
    sections.push(pcInfoSection("🖥", "System & OS",
      pcInfoIntro(PC_INFO_INTROS.system)
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("Hostname", sys.hostname, { tip: "Short name on the network" })
      + pcInfoKv("FQDN", sys.fqdn, { tip: "Fully qualified domain name" })
      + pcInfoKv("Distribution", sys.distro?.name, { tip: "Linux distro and version" })
      + pcInfoKv("Kernel", sys.kernel, { tip: "Running Linux kernel release" })
      + pcInfoKv("Architecture", archLabel)
      + pcInfoKv("Platform", sys.platform)
      + pcInfoKv("Boot time", sys.boot_time)
      + pcInfoKv("Uptime", sys.uptime_human)
      + pcInfoKv("Timezone", sys.timezone)
      + pcInfoKv("Machine ID", sys.machine_id, { mono: true, tip: "Unique ID in /etc/machine-id" })
      + pcInfoKv("Logged-in user", users)
      + pcInfoKv("Processes", runtime.process_count, { tip: "Running processes right now" })
      + "</div>" + sysExtra));

    const freq = cpu.frequency_mhz || {};
    const lscpu = cpu.lscpu || {};
    const cacheRows = (cpu.cache_sysfs || []).map((c) => [
      esc(("L" + (c.level || "?") + " " + (c.type || "")).trim()),
      esc(c.size || "—"),
      esc(c.ways ? (c.ways + "-way") : "—"),
      esc(c.line_size ? (c.line_size + " B line") : "—"),
    ]);
    const thermals = (cpu.thermals || []).map((t) => {
      const lv = t.temp_c >= 90 ? "hot" : (t.temp_c >= 75 ? "warn" : "");
      return '<span class="pc-info-thermal-chip ' + lv + '"><span>' + esc(t.zone) + '</span> <strong>' + esc(String(t.temp_c)) + "°C</strong></span>";
    }).join("");
    const l1 = (lscpu["l1d cache"] && lscpu["l1i cache"]) ? (lscpu["l1d cache"] + " / " + lscpu["l1i cache"]) : (lscpu["l1d cache"] || lscpu["l1i cache"] || "—");
    const l23 = (lscpu["l2 cache"] && lscpu["l3 cache"]) ? (lscpu["l2 cache"] + " / " + lscpu["l3 cache"]) : (lscpu["l2 cache"] || lscpu["l3 cache"] || "—");
    const mhzRange = [freq.min_mhz, freq.max_mhz].filter((x) => x != null).join(" – ") || "—";
    const loadStr = [cpu.load_1m, cpu.load_5m, cpu.load_15m].map((x) => (x != null && x.toFixed) ? x.toFixed(2) : x).join(" / ");
    const familyStep = [cpu.family, cpu.stepping].filter(Boolean).join(" / ") || "—";
    let cpuExtra = pcInfoLoadChart(cpu.load_1m, cpu.load_5m, cpu.load_15m, cpu.cores_logical);
    if (cacheRows.length) cpuExtra += '<h4 class="pc-info-subhead">CPU cache (sysfs)</h4>' + pcInfoTable(["Cache", "Size", "Associativity", "Line"], cacheRows);
    if (thermals) cpuExtra += '<h4 class="pc-info-subhead">Thermal zones</h4><div class="pc-info-thermal-row">' + thermals + "</div>";
    const flags = cpu.flags_sample || [];
    if (flags.length) {
      const flagHtml = flags.map((f) => '<span class="pc-info-flag">' + esc(f) + "</span>").join("")
        + (cpu.flags_count > flags.length ? '<span class="pc-info-flag">+' + (cpu.flags_count - flags.length) + " more</span>" : "");
      cpuExtra += pcInfoDetails("All CPU feature flags", '<div class="pc-info-flag-cloud">' + flagHtml + "</div>", cpu.flags_count);
    }
    sections.push(pcInfoSection("⚡", "Processor",
      pcInfoIntro(PC_INFO_INTROS.cpu)
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("Model", cpu.model)
      + pcInfoKv("Vendor", cpu.vendor)
      + pcInfoKv("Physical cores", cpu.cores_physical, { tip: "Actual CPU cores in the silicon" })
      + pcInfoKv("Logical CPUs", cpu.cores_logical, { tip: "Threads visible to the OS (includes hyperthreading)" })
      + pcInfoKv("Sockets", cpu.sockets)
      + pcInfoKv("Threads / core", cpu.threads_per_core)
      + pcInfoKv("Family / stepping", familyStep)
      + pcInfoKv("Microcode", cpu.microcode, { tip: "CPU microcode patch level" })
      + pcInfoKv("Address sizes", cpu.address_sizes || lscpu["address sizes"])
      + pcInfoKv("Byte order", cpu.byte_order || lscpu["byte order"])
      + pcInfoKv("L1d / L1i cache", l1)
      + pcInfoKv("L2 / L3 cache", l23)
      + pcInfoKv("Current MHz", freq.current_mhz)
      + pcInfoKv("Min / max MHz", mhzRange)
      + pcInfoKv("Load (1 / 5 / 15 m)", loadStr, { tip: "Unix load average — processes waiting for CPU time" })
      + pcInfoKv("Virtualization", cpu.virtualization)
      + pcInfoKv("Hypervisor", cpu.hypervisor_vendor || lscpu["hypervisor vendor"] || "—")
      + pcInfoKv("BogoMIPS", cpu.bogomips, { tip: "Rough kernel benchmark per core (not comparable across CPUs)" })
      + "</div>" + cpuExtra));

    const memSummary = mem.module_summary || {};
    const modules = mem.modules || [];
    const modCount = memSummary.module_count != null ? memSummary.module_count : (modules.length || "—");
    const memUsedStr = mem.used_pct != null
      ? ((mem.used_human || "—") + " (" + mem.used_pct + "%)")
      : (mem.used_human || "—");
    const swapUsedStr = mem.swap_used_pct != null
      ? (_kb_human_js(mem.swap_used_kb) + " (" + mem.swap_used_pct + "%)")
      : "—";
    let memBody = pcInfoIntro(PC_INFO_INTROS.memory)
      + '<div class="pc-info-bar-grid">'
      + pcInfoUsageBar(mem.used_pct, "RAM used", { sub: mem.used_human })
      + pcInfoUsageBar(mem.swap_used_pct, "Swap used", { sub: _kb_human_js(mem.swap_used_kb) })
      + "</div>"
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("Total RAM", mem.total_human)
      + pcInfoKv("Used", memUsedStr)
      + pcInfoKv("Available", _kb_human_js(mem.available_kb), { tip: "Memory available for new apps without swapping" })
      + pcInfoKv("Memory type", memSummary.type || "—", { tip: "DDR generation from SMBIOS when available" })
      + pcInfoKv("RAM speed", memSummary.speed || "—")
      + pcInfoKv("Form factor", memSummary.form_factor || "—", { tip: "DIMM, SODIMM, etc." })
      + pcInfoKv("Installed modules", modCount)
      + pcInfoKv("Swap total", _kb_human_js(mem.swap_total_kb), { tip: "Disk space used when RAM is full" })
      + pcInfoKv("Swap used", swapUsedStr)
      + "</div>";
    if (mem.modules_note) memBody += '<p class="help-text muted-inline">' + esc(mem.modules_note) + "</p>";
    if (modules.length) {
      const src = mem.modules_source ? (" · " + mem.modules_source) : "";
      memBody += '<h4 class="pc-info-subhead">Physical memory modules <span class="muted-inline">' + esc(src) + "</span></h4>" + pcInfoModuleCards(modules);
    }
    const memDetails = mem.details || [];
    if (memDetails.length) {
      const rows = memDetails.map((d) => [esc(d.key), esc(d.human || d.kb)]);
      memBody += pcInfoDetails("/proc/meminfo highlights", pcInfoTable(["Metric", "Value"], rows), memDetails.length);
    }
    sections.push(pcInfoSection("🧠", "Memory & swap", memBody));

    const physicalDisks = storage.physical_disks || [];
    const diskCards = physicalDisks.map((d) => pcInfoDiskCard(d)).join("");
    const rootUsage = storage.root_usage;
    let storageBody = pcInfoIntro(PC_INFO_INTROS.storage)
      + (rootUsage ? pcInfoUsageBar(rootUsage.used_pct, "Root filesystem (/)", { sub: rootUsage.used_human + " / " + rootUsage.total_human }) : "")
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("Physical drives", storage.disk_count)
      + pcInfoKv("Partitions total", storage.partition_count)
      + pcInfoKv("Combined capacity", storage.total_capacity_human)
      + "</div>"
      + '<div class="pc-info-disk-grid">' + (diskCards || '<p class="help-text muted-inline">No block devices found.</p>') + "</div>";
    const mountRows = (storage.mounts || []).filter((m) => m.usage).slice(0, 24).map((m) => [
      esc(m.mount),
      esc(m.fstype),
      esc(m.usage?.used_human || "—"),
      esc(m.usage?.total_human || "—"),
      esc(m.usage?.used_pct != null ? (m.usage.used_pct + "%") : "—"),
      "<code>" + esc(m.device) + "</code>",
    ]);
    if (mountRows.length) {
      storageBody += pcInfoDetails("Live mount usage", pcInfoTable(["Mount", "FS", "Used", "Size", "%", "Device"], mountRows), mountRows.length);
    }
    sections.push(pcInfoSection("💾", "Storage — individual disks", storageBody));

    const boardName = [fw.board_vendor, fw.board_name].filter(Boolean).join(" ") || "—";
    sections.push(pcInfoSection("🏭", "Firmware & board (DMI)",
      pcInfoIntro(PC_INFO_INTROS.firmware)
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("System vendor", fw.system_vendor)
      + pcInfoKv("Product", fw.system_product, { tip: "Model name from manufacturer" })
      + pcInfoKv("Version", fw.system_version)
      + pcInfoKv("Serial", fw.system_serial)
      + pcInfoKv("UUID", fw.system_uuid, { mono: true })
      + pcInfoKv("Board", boardName)
      + pcInfoKv("Board version", fw.board_version)
      + pcInfoKv("BIOS vendor", fw.bios_vendor)
      + pcInfoKv("BIOS version", fw.bios_version)
      + pcInfoKv("BIOS date", fw.bios_date)
      + pcInfoKv("Chassis", fw.chassis_type_label || fw.chassis_type, { tip: "Laptop, desktop tower, mini PC, etc." })
      + "</div>"));

    const pciRows = (data.pci || []).map((p) => [esc(p.slot), esc(p.description)]);
    const usbRows = (data.usb || []).map((u) => [
      esc(u.bus + ":" + u.device),
      esc(u.id),
      esc(u.description),
    ]);
    let busBody = pcInfoIntro(PC_INFO_INTROS.buses);
    if (pciRows.length > 8) {
      busBody += pcInfoDetails("PCI devices", pcInfoTable(["Slot", "Device"], pciRows), pciRows.length);
    } else if (pciRows.length) {
      busBody += '<h4 class="pc-info-subhead">PCI devices (' + pciRows.length + ")</h4>" + pcInfoTable(["Slot", "Device"], pciRows);
    } else {
      busBody += '<p class="help-text muted-inline">No PCI devices reported.</p>';
    }
    if (usbRows.length > 10) {
      busBody += pcInfoDetails("USB devices", pcInfoTable(["Bus:Dev", "ID", "Description"], usbRows), usbRows.length);
    } else if (usbRows.length) {
      busBody += '<h4 class="pc-info-subhead">USB devices (' + usbRows.length + ")</h4>" + pcInfoTable(["Bus:Dev", "ID", "Description"], usbRows);
    } else {
      busBody += '<p class="help-text muted-inline">No USB devices reported.</p>';
    }
    sections.push(pcInfoSection("🔌", "Expansion buses", busBody));

    const gpuPci = (gpu.pci || []).map((p) => [esc(p.slot), esc(p.description)]);
    const drmCards = gpu.drm_cards || [];
    const audioRows = (data.audio || []).map((a) => [esc(a.index), esc(a.id), esc(a.name)]);
    let avBody = pcInfoIntro(PC_INFO_INTROS.gpu);
    avBody += gpuPci.length
      ? pcInfoTable(["Slot", "GPU"], gpuPci)
      : '<p class="help-text muted-inline">No discrete GPU reported via PCI.</p>';
    if (drmCards.length) {
      avBody += '<h4 class="pc-info-subhead">DRM display cards</h4><div class="pc-info-spec-grid">'
        + drmCards.map((c) => pcInfoKv(c.id, c.vendor_pci || c.status, { tip: "Direct Rendering Manager — kernel graphics device" })).join("")
        + "</div>";
    }
    avBody += '<h4 class="pc-info-subhead">Sound cards</h4>';
    avBody += audioRows.length
      ? pcInfoTable(["#", "ID", "Name"], audioRows)
      : '<p class="help-text muted-inline">No ALSA cards in /proc/asound/cards.</p>';
    sections.push(pcInfoSection("🎮", "Graphics & audio", avBody));

    const bats = power.batteries || [];
    let powerBody = pcInfoIntro(PC_INFO_INTROS.power)
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("AC power", power.ac_online === true ? "Online" : (power.ac_online === false ? "On battery" : "—"), { tip: "Whether wall power is connected" })
      + "</div>";
    if (bats.length) {
      powerBody += bats.map((b) => {
        const charge = b.capacity_pct != null ? (b.capacity_pct + "%") : "—";
        const volts = b.voltage_v != null ? (b.voltage_v + " V") : "—";
        const watts = b.power_w != null ? (b.power_w + " W") : "—";
        return '<article class="pc-info-battery-card"><div class="pc-info-spec-grid">'
          + pcInfoUsageBar(b.capacity_pct, "Battery · " + (b.name || "pack"), { sub: b.status })
          + pcInfoKv("Manufacturer", b.manufacturer)
          + pcInfoKv("Model", b.model)
          + pcInfoKv("Technology", b.technology)
          + pcInfoKv("Cycles", b.cycle_count, { tip: "Charge cycles — higher means more wear" })
          + pcInfoKv("Charge", charge)
          + pcInfoKv("Voltage", volts)
          + pcInfoKv("Power", watts)
          + "</div></article>";
      }).join("");
    } else {
      powerBody += '<p class="help-text muted-inline">No battery detected (desktop or ACPI data unavailable).</p>';
    }
    const hwmon = data.sensors?.hwmon || [];
    if (hwmon.length) {
      const chips = hwmon.map((chip) => {
        const temps = (chip.temps || []).map((t) => t.label + ": " + t.temp_c + "°C").join(" · ");
        const fans = (chip.fans || []).map((f) => f.label + ": " + f.rpm + " RPM").join(" · ");
        return pcInfoKv(chip.chip, [temps, fans].filter(Boolean).join(" | ") || "—");
      }).join("");
      powerBody += '<h4 class="pc-info-subhead">Hardware monitors</h4><div class="pc-info-spec-grid">' + chips + "</div>";
    }
    sections.push(pcInfoSection("🔋", "Power & sensors", powerBody));

    const numaRows = (data.numa || []).map((n) => [
      esc(n.node),
      esc(n.cpus),
      esc(_kb_human_js(n.mem_total_kb)),
      esc(_kb_human_js(n.mem_free_kb)),
    ]);
    let secBody = pcInfoIntro(PC_INFO_INTROS.security)
      + '<div class="pc-info-spec-grid">'
      + pcInfoKv("EFI firmware", sec.efi_present ? "Present" : "Not detected", { tip: "UEFI firmware — required for Secure Boot" })
      + pcInfoKv("Secure Boot vars", sec.secure_boot_vars ? "EFI vars present" : "—")
      + pcInfoKv("AppArmor", sec.apparmor ? "Available" : "—")
      + pcInfoKv("SELinux", sec.selinux ?? "—")
      + pcInfoKv("TPM", (sec.tpm_devices || []).join(", ") || "—", { tip: "Trusted Platform Module for disk encryption keys" })
      + "</div>";
    if (numaRows.length) {
      secBody += pcInfoDetails("NUMA nodes", pcInfoTable(["Node", "CPUs", "Mem total", "Mem free"], numaRows), numaRows.length);
    }
    sections.push(pcInfoSection("🛡", "Security firmware & topology", secBody));

    box.innerHTML = sections.join("");
  }

  async function loadPcInfo(force) {
    const box = $("pcInfoSections");
    if (box && !box.querySelector(".pc-info-section")) {
      box.innerHTML = '<div class="page-empty"><strong>Scanning hardware…</strong><p class="help-text">Reading CPU, memory, disks, firmware, PCI, USB, and sensors.</p></div>';
    }
    try {
      const path = force ? "/api/pc-info?force=1" : "/api/pc-info";
      const data = await apiCached(path, {}, force ? 0 : 30_000);
      renderPcInfo(data);
    } catch (e) {
      if (box) box.innerHTML = '<div class="page-empty"><strong>Could not load PC info</strong><p class="help-text">' + esc(formatFetchError(e, "PC info")) + "</p></div>";
      toast(String(e), false);
    }
  }
  async function loadDoctorsHub(quiet, force) {
    const sub = doctorsHubTab || "overview";
    if (sub === "nordvpn") {
      navigateRoute("dashboard", "nord-doctor", { force: true });
      return;
    }
    if (sub === "overview" || DOCTOR_TAB_GROUPS[sub] !== undefined) {
      try {
        await loadDoctorReport(force);
      } catch (e) {
        if (!quiet) toast(String(e), false);
      }
      return;
    }
    try {
      const data = await apiCached("/api/wifi/hub", {}, force ? 0 : CACHE_TTL.wifi);
      renderDoctorPanel(data.doctors?.network, "netDocBadge", "netDocChecks", "net");
    } catch (e) {
      if (!quiet) toast(String(e), false);
    }
  }

  async function loadWifiHub(quiet, force) {
    try {
      const data = await apiCached("/api/wifi/hub", {}, force ? 0 : CACHE_TTL.wifi);
      renderWifiHub(data);
      if (!quiet) startWifiLive();
    } catch (e) {
      if (!quiet) toast(String(e), false);
    }
  }

  async function loadSecurity(force) {
    try {
      const sumTtl = force ? 0 : CACHE_TTL.securitySummary;
      const fullTtl = force ? 0 : CACHE_TTL.security;
      const summary = await apiCached("/api/security/summary", {}, sumTtl);
      renderSecurityHub(summary);
      const fullPromise = apiCached("/api/security", {}, fullTtl)
        .then((data) => {
          renderSecurityHub(data);
        })
        .catch(() => {});
      loadNetworkRoutes(force);
      await fullPromise;
    } catch (e) {
      toast(String(e), false);
    }
  }

  const VIEW_MODULE_MAP = {
    dashboard: "dashboard",
    security: "security",
    tools: ["logs", "automate", "editor"],
    wifi: "wifi",
    doctors: "lab",
    lab: "lab",
    security: "security",
    control: "control",
    automate: "automate",
    advanced: ["map-internet", "map-local", "traffic-live", "traffic-speed", "spectrum-analyzer", "bluetooth-spectrum", "services"],
    logs: "logs",
    settings: "settings",
    terminal: "terminal",
    editor: "editor",
    help: "help",
  };

  function applyModuleNav(feats) {
    document.querySelectorAll(".nav-pill[data-view]").forEach((pill) => {
      if (!pill.classList.contains("nav-pill-sub")) pill.classList.remove("hidden");
    });
  }

  let wizardData = null;
  /** hidden | gate | steps — prevents renderState from flashing back to the gate mid-wizard */
  let wizardUiMode = "hidden";
  /** When true, only steps that are not already configured appear in the flow. */
  let wizardShortMode = false;

  const WIZARD_STEPS_CLIENT = [
    { id: "welcome", title: "Welcome", summary: "What this wizard will help you configure.", skippable: false },
    { id: "legal", title: "Legal", summary: "Accept LEGAL.md once — required to use nordctl.", skippable: false },
    { id: "nordvpn", title: "NordVPN", summary: "Official NordVPN client — install and log in for Connect and presets.", skippable: true },
    { id: "services", title: "Services", summary: "Start nordvpnd and optional UI autostart so Connect works after reboot.", skippable: true },
    { id: "privileges", title: "Sudo & privileges", summary: "One-time sudo setup so the UI can manage UFW, WiFi DNS, and IPv6.", skippable: true },
    { id: "country", title: "Home country", summary: "Default country for presets and quick connect.", skippable: true },
    { id: "wifi", title: "WiFi profiles", summary: "Sync your active WiFi into config for Smart DNS and home IP.", skippable: true },
    { id: "home_isp", title: "Home ISP & trusted WiFi", summary: "Trusted home WiFi and ISP address for the top bar (travel-safe).", skippable: true },
    { id: "smart_dns", title: "Smart DNS on WiFi", summary: "Apply Nord Smart DNS to saved WiFi profiles when VPN is off.", skippable: true },
    { id: "ipv6", title: "IPv6 hardening", summary: "Optional — disable IPv6 to reduce VPN bypass leaks.", skippable: true },
    { id: "ufw", title: "Host firewall (UFW)", summary: "Quick check that Linux UFW is available.", skippable: true },
    { id: "alerts", title: "Alerts & notifications", summary: "Browser notifications and VPN disconnect watcher.", skippable: true },
    { id: "email", title: "Email alerts", summary: "Optional SMTP — mail goes only to your address.", skippable: true },
    { id: "ui_access", title: "Dashboard access", summary: "Password if you open the UI on your LAN.", skippable: true },
    { id: "baseline", title: "Install baseline", summary: "Rollback snapshot saved on first run — undo preset mistakes safely.", skippable: true },
    { id: "first_connect", title: "First connect", summary: "Connect VPN or apply a starter preset so you see it working.", skippable: true },
    { id: "packages", title: "Optional apt tools", summary: "Networking and security scanners (lynis, nmap, …).", skippable: true },
    { id: "ui_health", title: "Dashboard UI", summary: "Verify CSS and static files so every page renders correctly.", skippable: true },
    { id: "finish", title: "All set", summary: "Review checklist and open the dashboard.", skippable: false },
  ];

  function wizardFallbackPayload(stepId) {
    const id = stepId || "welcome";
    return {
      ok: true,
      complete: false,
      current_step: id,
      steps: WIZARD_STEPS_CLIENT.map((s) => ({ ...s, state: s.id === id ? "current" : "todo", auto_done: false })),
      checklist: [],
      context: {},
      doctor: lastState?.doctor || {},
      legal_accepted: false,
      api_fallback: true,
    };
  }

  async function enrichWizardEmailContext() {
    if (wizardData?.context?.email?.to || wizardData?.context?.email?.configured) return;
    try {
      const st = await api("/api/settings");
      const a = st?.alerts || {};
      if (!a.email_to && !a.smtp_host && !a.email_enabled) return;
      wizardData.context = {
        ...(wizardData.context || {}),
        email: {
          enabled: !!a.email_enabled,
          to: a.email_to || "",
          smtp_host: a.smtp_host || "",
          smtp_user: a.smtp_user || "",
          password_set: !!a.smtp_password_set,
          configured: !!a.email_configured,
        },
      };
    } catch (_) { /* settings optional */ }
  }

  async function loadWizard(force) {
    const raw = await api("/api/setup-wizard");
    if (raw?.ok && Array.isArray(raw.steps) && raw.steps.length) {
      wizardData = raw;
      await enrichWizardEmailContext();
      updateWizardGateButtons();
      return wizardData;
    }
    const step = wizardData?.current_step || "welcome";
    wizardData = wizardFallbackPayload(step);
    if (raw?.error && !raw?.ok) {
      wizardData.api_error = raw.error;
    }
    await enrichWizardEmailContext();
    updateWizardGateButtons();
    return wizardData;
  }

  function wizardStepMeta(stepId) {
    const fromApi = (wizardData?.steps || []).find((s) => s.id === stepId);
    if (fromApi) return fromApi;
    return WIZARD_STEPS_CLIENT.find((s) => s.id === stepId) || null;
  }

  function wizardAllSteps() {
    return (wizardData?.steps?.length ? wizardData.steps : WIZARD_STEPS_CLIENT);
  }

  function wizardStepNeedsSetup(s) {
    if (!s) return false;
    if (s.id === "finish") return true;
    if (s.id === "welcome") return false;
    if (s.id === "legal") return s.state !== "done" || !wizardData?.legal_accepted;
    const checklist = wizardData?.checklist || [];
    if (checklist.some((c) => !c.ok && (c.wizard_step || c.id) === s.id)) return true;
    return s.state !== "done";
  }

  function wizardFirstIncompleteStep(steps) {
    const checklist = wizardData?.checklist || [];
    for (const c of checklist) {
      if (!c.ok && c.wizard_step) return c.wizard_step;
    }
    const list = steps || wizardData?.steps || WIZARD_STEPS_CLIENT;
    const skip = new Set(["welcome", "finish"]);
    for (const s of list) {
      if (skip.has(s.id)) continue;
      if (s.state !== "done") return s.id;
    }
    return "finish";
  }

  function wizardPendingSetupCount(steps) {
    return (steps || wizardAllSteps()).filter((s) => {
      if (s.id === "welcome") return false;
      return wizardStepNeedsSetup(s);
    }).length;
  }

  function wizardActiveSteps() {
    const all = wizardAllSteps();
    if (!wizardShortMode) return all;
    const pending = all.filter(wizardStepNeedsSetup);
    if (!pending.length) {
      const fin = all.find((s) => s.id === "finish");
      return fin ? [fin] : all.slice(-1);
    }
    if (!pending.some((s) => s.id === "finish")) {
      const fin = all.find((s) => s.id === "finish");
      if (fin) pending.push(fin);
    }
    return pending;
  }

  function wizardNextInFlow(fromId) {
    const active = wizardActiveSteps();
    const idx = active.findIndex((s) => s.id === fromId);
    if (idx >= 0 && idx + 1 < active.length) return active[idx + 1].id;
    return "finish";
  }

  function wizardPrevInFlow(fromId) {
    const active = wizardActiveSteps();
    const idx = active.findIndex((s) => s.id === fromId);
    return idx > 0 ? active[idx - 1].id : null;
  }

  function updateWizardGateButtons() {
    const pending = wizardPendingSetupCount();
    const shortBtn = $("btnWizardStartShort");
    if (shortBtn) {
      shortBtn.textContent = pending ? `Quick setup (${pending} left)` : "Quick setup";
    }
    const resumeBtn = $("btnResumeSetupWizard");
    if (resumeBtn) resumeBtn.classList.add("hidden");
    const topBtn = $("btnTopbarWizard");
    if (topBtn) {
      topBtn.title = pending
        ? `Setup wizard — ${pending} checklist item${pending === 1 ? "" : "s"} open`
        : "Open the setup wizard";
    }
  }

  function applyWizardActionResult(res) {
    if (!res?.wizard) return;
    wizardData = res.wizard;
    renderSetupWizardChecklist(res.wizard);
    updateWizardGateButtons();
    if (wizardUiMode === "steps") {
      renderWizardStep(wizardData.current_step || "welcome");
    }
  }

  async function showSetupWizardGate() {
    try {
      ensureWizardPage();
      await loadWizard(true);
      if (wizardData?.complete && !wizardData?.api_fallback) {
        const res = await doAction({ action: "setup_wizard_reopen" }, "Reopen wizard");
        if (res.wizard) wizardData = res.wizard;
        else await loadWizard(true);
      }
      const pending = wizardPendingSetupCount();
      const lead = $("wizardGateLead");
      if (lead) {
        lead.innerHTML = pending
          ? `Choose how to run setup: <strong>Quick setup</strong> opens only the ${pending} step${pending === 1 ? "" : "s"} still missing from the checklist below. <strong>All wizard steps</strong> walks every page from the start (you can still skip optional ones).`
          : "Choose how to run setup: <strong>Quick setup</strong> checks the checklist for anything left. <strong>All wizard steps</strong> walks every page from the start.";
      }
      $("onboardReturning")?.classList.toggle("hidden", !wizardData?.returning_user);
      updateWizardGateButtons();
      showWizardPanel(true);
    } catch (e) {
      toast(formatFetchError(e, "Setup wizard"), false);
    }
  }

  function wizardProgressClass(s) {
    const cur = wizardData?.current_step || "welcome";
    const isCurrent = s.id === cur;
    return isCurrent ? "current" : (s.state === "done" ? "done" : (s.state === "skipped" ? "skipped" : "todo"));
  }

  async function wizardGotoStep(stepId) {
    if (!stepId || stepId === wizardData?.current_step) return;
    showWizardPanel(false);
    if (wizardData?.api_fallback) {
      wizardData.current_step = stepId;
      renderWizardStep(stepId);
      return;
    }
    const res = await doAction({ action: "setup_wizard_goto", step: stepId }, "Open step");
    if (res.wizard) wizardData = res.wizard;
    renderWizardStep(stepId);
  }

  function renderWizardProgress() {
    const bar = $("wizardProgress");
    if (!bar) return;
    const steps = wizardActiveSteps();
    let jumpableCount = 0;
    bar.innerHTML = steps.map((s) => {
      const cls = wizardProgressClass(s);
      const isCurrent = cls === "current";
      const jumpable = !isCurrent && cls !== "done";
      if (jumpable) jumpableCount += 1;
      const title = `${s.title}${jumpable ? " — click to open" : ""}`;
      return `<span class="wizard-progress-dot ${cls}${jumpable ? " jumpable" : ""}"${jumpable ? ` data-wizard-jump="${esc(s.id)}" role="button" tabindex="0"` : ""} title="${esc(title)}"></span>`;
    }).join("");
    bar.querySelectorAll("[data-wizard-jump]").forEach((dot) => {
      dot.addEventListener("click", () => wizardGotoStep(dot.getAttribute("data-wizard-jump")));
      dot.addEventListener("keydown", (e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          wizardGotoStep(dot.getAttribute("data-wizard-jump"));
        }
      });
    });
    const hint = $("wizardProgressHint");
    if (hint) {
      hint.textContent = wizardShortMode
        ? "Quick setup — grey dots are steps still to do"
        : "Click a grey dot to jump to an incomplete step";
      hint.classList.toggle("hidden", jumpableCount < 2);
    }
    const cur = wizardData?.current_step || "welcome";
    const idx = Math.max(0, steps.findIndex((s) => s.id === cur)) + 1;
    if ($("wizardStepBadge")) {
      $("wizardStepBadge").textContent = wizardShortMode
        ? `${idx} / ${steps.length} · quick`
        : `${idx} / ${steps.length}`;
    }
    const modeBadge = $("wizardModeBadge");
    if (modeBadge) {
      const pending = wizardPendingSetupCount();
      if (wizardShortMode) {
        modeBadge.textContent = pending ? `Quick · ${pending} left` : "Quick setup";
        modeBadge.classList.remove("hidden");
      } else {
        modeBadge.classList.add("hidden");
      }
    }
  }

  function wizardStatusRow(ok, text) {
    return `<div class="wizard-status-row ${ok ? "ok" : "warn"}"><span>${ok ? "✓" : "!"}</span><span>${esc(text)}</span></div>`;
  }

  function renderWizardStep(stepId) {
    const host = $("wizardStepHost");
    const sid = stepId || wizardData?.current_step || "welcome";
    const meta = wizardStepMeta(sid);
    if (!host || !meta) {
      if (host) {
        host.innerHTML = `<p class="help-text">Could not load setup wizard step. Hard-refresh the page (Ctrl+Shift+R) and restart <code>nordctl serve</code>.</p>`;
      }
      return;
    }
    if ($("wizardStepTitle")) $("wizardStepTitle").textContent = meta.title;
    const doc = wizardData?.doctor || lastState?.doctor || {};
    const priv = doc.privileges || {};
    const ctx = wizardData?.context || {};
    let html = "";
    if (wizardData?.api_fallback || wizardData?.api_error) {
      html += `<p class="help-text warn-inline">Setup wizard API unavailable (${esc(wizardData.api_error || "restart nordctl serve")}). Showing offline steps — some buttons need a server restart.</p>`;
    }
    if (wizardShortMode && sid !== "finish") {
      const pending = wizardPendingSetupCount();
      html += `<p class="help-text wizard-short-lead"><strong>Quick setup</strong> — ${pending ? `only ${pending} step${pending === 1 ? "" : "s"} still need attention` : "nothing left to configure"}. Already-set steps are skipped.</p>`;
    }
    html += `<p class="help-text">${esc(meta.summary || "")}</p>`;
    if (sid === "welcome") {
      const serve = ctx.cli_serve || lastState?.cli?.serve || "nordctl serve";
      html += `<ul class="steps"><li>NordVPN install, login &amp; nordvpnd</li><li>Sudo, home country, WiFi &amp; Smart DNS</li><li>Alerts, email, UFW &amp; IPv6</li><li>First VPN connect or preset</li></ul>`;
      html += `<p class="help-text muted-inline">Start the UI anytime: <code>${esc(serve)}</code> — then open the URL shown in the terminal.</p>`;
      html += `<p class="help-text muted-inline">Each optional step has <strong>Skip for now</strong>. Reopen anytime from the top <strong>Wizard</strong> button.</p>`;
    } else if (sid === "legal") {
      html += `<label class="onboard-legal"><input type="checkbox" id="wizardLegal" ${wizardData?.legal_accepted ? "checked disabled" : ""} /> I accept <strong>LEGAL.md</strong> — I am responsible for compliance with law and NordVPN / streaming terms.</label>`;
    } else if (sid === "nordvpn") {
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!doc.nord_installed, doc.nord_installed ? "NordVPN CLI installed" : "NordVPN not installed yet")}
        ${wizardStatusRow(!!doc.logged_in, doc.logged_in ? "Logged in to NordVPN" : "Not logged in — use Nord shell → nordvpn login")}
      </div>
      <p class="help-text muted-inline">Install uses the <strong>Nord shell</strong> when sudo needs your password — enter it in the box that appears below the terminal.</p>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardInstallNord">Install NordVPN</button>
        <button type="button" class="btn sm" id="btnWizardNordPreview">Preview install</button>
        <button type="button" class="btn sm" id="btnWizardNordLogin">Login in Nord shell</button>
        <button type="button" class="btn sm jump-link" data-view-jump="dashboard/terminal">Open Nord shell</button>
        <button type="button" class="btn sm" id="btnWizardNordRecheck">Re-check</button></div>`;
      html += `<pre class="mono wizard-code hidden" id="wizardInstallLog"></pre>`;
    } else if (sid === "services") {
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!doc.nord_installed, doc.nord_installed ? "NordVPN CLI installed" : "Install NordVPN first (previous step)")}
        ${wizardStatusRow(!!ctx.nordvpnd_active, ctx.nordvpnd_active ? "nordvpnd is running" : "nordvpnd not running — Connect needs this")}
        ${wizardStatusRow(!!ctx.ui_service_installed, ctx.ui_service_installed ? "nordctl UI service installed" : "UI service optional — use nordctl serve manually")}
      </div>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardStartNordvpnd">Start nordvpnd</button>
        <button type="button" class="btn sm" id="btnWizardInstallUiSvc">Install UI autostart</button>
        <button type="button" class="btn sm" id="btnWizardSvcRecheck">Re-check</button></div>`;
    } else if (sid === "privileges") {
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!priv.ui_privileges_ok, priv.ui_privileges_ok ? "UI privileges OK" : "UI needs one-time sudo setup")}
      </div>`;
      (priv.notes || []).slice(0, 3).forEach((n) => { html += `<p class="help-text">${esc(n)}</p>`; });
      if (priv.manual_sudo_hint) {
        html += `<div class="wizard-code" id="wizardPrivCmd">${esc(priv.manual_sudo_hint)}</div>`;
        html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardCopyPriv">Copy command</button>
          <button type="button" class="btn sm jump-link" data-view-jump="network/privileges">Open Privileges tab</button></div>`;
      }
    } else if (sid === "country") {
      html += `<p class="help-text">Presets and quick connect use this as your home country.</p>
        <div class="field-row"><select id="wizardCountrySelect" class="full-select" title="Home country"></select>
        <button type="button" class="btn sm primary" id="btnWizardCountrySave">Save country</button></div>`;
    } else if (sid === "wifi") {
      html += `<p class="help-text">Adds your current WiFi to <code>wifi.profiles</code> for Smart DNS and the Home IP chip.</p>
        <div class="actions"><button type="button" class="btn sm primary" id="btnWizardWifiSync">Sync active WiFi</button>
        <button type="button" class="btn sm jump-link" data-view-jump="network/wifi/profiles">WiFi profiles</button></div>`;
    } else if (sid === "home_isp") {
      const ssid = ctx.zones?.ssid || "—";
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!ctx.zones?.is_trusted, ctx.zones?.is_trusted ? `Trusted zone: ${esc(ssid)}` : `SSID ${esc(ssid)} not in trusted zones yet`)}
        ${wizardStatusRow(!!ctx.home_ip_cached, ctx.home_ip_cached ? `Home ISP learned: ${esc(ctx.home_ip_cached)}` : "Home ISP not learned yet")}
      </div>`;
      html += `<p class="help-text">On home WiFi, disconnect VPN once to auto-learn your ISP into <code>home_ip_cache.json</code>, or add this SSID as trusted below.</p>`;
      html += `<div class="field-row"><input type="text" id="wizardTrustSsid" class="full-select" placeholder="Home WiFi name (SSID)" value="${esc(ctx.zones?.ssid || "")}" />
        <button type="button" class="btn sm primary" id="btnWizardTrustSsid">Add trusted WiFi</button></div>`;
      html += `<div class="actions"><button type="button" class="btn sm" id="btnWizardLearnHome" data-confirm="1">Disconnect VPN (learn home IP)</button>
        <button type="button" class="btn sm jump-link" data-view-jump="network/wifi/zones">WiFi zones</button></div>`;
    } else if (sid === "smart_dns") {
      const sd = ctx.smart_dns || {};
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!ctx.smart_dns_active, ctx.smart_dns_active ? "Smart DNS active on current network" : "Smart DNS not active on this WiFi yet")}
      </div>`;
      html += `<p class="help-text">Applies Nord Smart DNS IPs to this computer's Wi‑Fi profiles in config (NetworkManager) — not your router or Nord account page alone. VPN should be off.</p>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardApplySmartDns">Apply Smart DNS to profiles</button>
        <button type="button" class="btn sm jump-link" data-view-jump="dashboard/nord-dns">Nord DNS tab</button></div>`;
      if (sd.dns_servers?.length) {
        html += `<p class="help-text muted-inline">Configured: ${sd.dns_servers.map((d) => esc(d)).join(", ")}</p>`;
      }
    } else if (sid === "ipv6") {
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!ctx.ipv6_ok, ctx.ipv6_ok ? "IPv6 check OK" : "IPv6 may bypass VPN — consider disabling")}
      </div>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardDisableIpv6" data-confirm="1">Disable IPv6</button>
        <button type="button" class="btn sm" id="btnWizardIpv6Recheck">Re-check</button></div>`;
    } else if (sid === "ufw") {
      const ufw = ctx.ufw || {};
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(ufw.installed !== false, ufw.installed === false ? "UFW not installed" : "UFW installed")}
        ${wizardStatusRow(!!ctx.ufw_active, ctx.ufw_active ? "UFW active" : "UFW inactive")}
      </div>`;
      html += `<p class="help-text">${esc(ufw.summary || "Linux host firewall — separate from Nord firewall.")}</p>`;
      html += `<div class="actions"><button type="button" class="btn sm primary jump-link" data-view-jump="network/host-ufw">Open Linux UFW</button></div>`;
    } else if (sid === "alerts") {
      html += `<label class="traffic-live"><input type="checkbox" id="wizardBrowserAlerts" ${ctx.alerts?.browser_enabled !== false ? "checked" : ""} /> Browser notifications (VPN drop, DNS drift, health)</label>
        <label class="traffic-live"><input type="checkbox" id="wizardAlertWatch" ${ctx.alerts?.watch_enabled !== false ? "checked" : ""} /> Background VPN disconnect watcher</label>
        <div class="actions"><button type="button" class="btn sm" id="btnWizardNotifyPerm">Allow browser notifications</button>
        <button type="button" class="btn sm" id="btnWizardAlertTest">Send test alert</button></div>`;
    } else if (sid === "email") {
      const em = ctx.email || {};
      const alerts = ctx.alerts || {};
      const emailTo = em.to || alerts.email_to || "";
      const emailOn = !!(em.enabled ?? alerts.email_enabled);
      if (em.configured || emailTo) {
        html += `<div class="wizard-status-grid">
          ${wizardStatusRow(!!em.configured, em.configured ? `Email alerts configured · ${esc(emailTo)}` : (emailTo ? `Recipient saved · ${esc(emailTo)}` : "Email not fully configured yet"))}
          ${em.smtp_host ? wizardStatusRow(true, `SMTP host · ${esc(em.smtp_host)}`) : ""}
          ${em.smtp_user ? wizardStatusRow(true, `SMTP user · ${esc(em.smtp_user)}`) : ""}
        </div>`;
      }
      html += `<p class="help-text">Optional — SMTP credentials stay on this PC. Mail only goes to your address.</p>
        <label class="traffic-live"><input type="checkbox" id="wizardEmailEn" ${emailOn ? "checked" : ""} /> Enable email alerts</label>
        <div class="field-row"><input type="email" id="wizardEmailTo" placeholder="you@example.com" class="full-select" value="${esc(emailTo)}" /></div>
        <div class="field-row"><input type="text" id="wizardSmtpHost" placeholder="smtp.example.com" class="full-select" value="${esc(em.smtp_host || "")}" /></div>
        <div class="field-row"><input type="text" id="wizardSmtpUser" placeholder="SMTP username" class="full-select" value="${esc(em.smtp_user || "")}" />
        <input type="password" id="wizardSmtpPass" placeholder="${em.password_set ? "•••••• (saved — leave blank to keep)" : "SMTP password / app password"}" autocomplete="new-password" /></div>`;
    } else if (sid === "ui_access") {
      const bind = wizardData?.ui_bind || "127.0.0.1";
      const lan = bind !== "127.0.0.1" && bind !== "localhost";
      html += `<p class="help-text">UI listens on <code>${esc(bind)}:${esc(String(wizardData?.ui_port || 8765))}</code>${lan ? " — other devices on your network can open this page." : " — localhost only."}</p>`;
      if (lan) {
        html += `<label class="traffic-live"><input type="checkbox" id="wizardLabPwEn" /> Set a dashboard password (recommended on LAN)</label>
          <div class="field-row"><input type="password" id="wizardLabPw" placeholder="Password (min 4 characters)" autocomplete="new-password" />
          <input type="password" id="wizardLabPw2" placeholder="Confirm password" autocomplete="new-password" /></div>`;
      } else {
        html += `<p class="help-text muted-inline">Password not required on localhost. Change bind under Settings → Services if you need LAN access.</p>`;
      }
    } else if (sid === "baseline") {
      const bl = ctx.baseline || {};
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!bl.exists, bl.exists ? "Install baseline saved" : "No baseline yet")}
      </div>`;
      html += `<p class="help-text">${esc(bl.message || "Rollback snapshot for undoing nordctl changes.")}</p>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardBaselineEnsure">Create baseline now</button>
        <button type="button" class="btn sm jump-link" data-view-jump="network/tools/rollback">Open Rollback</button></div>`;
    } else if (sid === "first_connect") {
      const cc = wizardData?.connect_country || lastState?.connect_country || "";
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(!!doc.logged_in, doc.logged_in ? "Logged in to NordVPN" : "Log in first (NordVPN step)")}
        ${wizardStatusRow(!!ctx.vpn_connected, ctx.vpn_connected ? `VPN connected${ctx.vpn_country ? " · " + ctx.vpn_country : ""}` : "Not connected yet")}
      </div>`;
      html += `<div class="actions"><button type="button" class="btn sm primary" id="btnWizardConnect" ${!cc ? "disabled title=\"Save home country first\"" : ""}>Connect${cc ? " · " + esc(countryLabel(cc)) : ""}</button>
        <button type="button" class="btn sm" id="btnWizardPresetStreaming">Apply streaming preset</button>
        <button type="button" class="btn sm jump-link" data-view-jump="dashboard/connect">Open Connect</button></div>`;
    } else if (sid === "packages") {
      html += `<p class="help-text">Install apt tools for scans and diagnostics — needs sudo. Skip if you install packages later from Network &amp; Security.</p>
        <div class="actions"><button type="button" class="btn sm" id="btnWizardPkgNet">Networking tools</button>
        <button type="button" class="btn sm" id="btnWizardPkgSec">Security tools</button>
        <button type="button" class="btn sm primary" id="btnWizardPkgAll">Install both</button></div>`;
    } else if (sid === "ui_health") {
      const uh = wizardData?.ui_health || {};
      const ok = !!uh.ok;
      html += `<div class="wizard-status-grid">
        ${wizardStatusRow(ok, ok ? "UI stylesheet and static files look complete" : "UI assets incomplete — pages may look unstyled")}
        ${wizardStatusRow(!uh.missing_files?.length, uh.missing_files?.length ? `Missing files: ${esc(uh.missing_files.join(", "))}` : "index.html, app.css, app.js present")}
        ${wizardStatusRow(!(uh.missing_css || []).length, (uh.missing_css || []).length ? `Missing CSS: ${esc((uh.missing_css || []).slice(0, 6).join(", "))}${(uh.missing_css || []).length > 6 ? "…" : ""}` : "Core page styles present")}
      </div>`;
      html += `<p class="help-text">Hard-refresh the dashboard (<kbd>Ctrl</kbd>+<kbd>Shift</kbd>+<kbd>R</kbd>) or click <strong>Reset UI cache</strong> after updates. CSS size: ${esc(String(Math.round((uh.css_bytes || 0) / 1024)))} KB.</p>`;
      if (!ok && uh.repair_hint) {
        html += `<p class="help-text warn-text">${esc(uh.repair_hint)}</p>`;
      }
      html += `<div class="actions">
        <button type="button" class="btn sm primary" id="btnWizardUiRecheck">Re-check UI assets</button>
        <button type="button" class="btn sm" id="btnWizardUiCache">Reset UI cache</button>
        <button type="button" class="btn sm" id="btnWizardUiRestart">Restart nordctl</button>
      </div>`;
    } else if (sid === "finish") {
      html += `<div class="wizard-checklist">${(wizardData?.checklist || []).map((c) =>
        `<label><input type="checkbox" disabled ${c.ok ? "checked" : ""} /> ${esc(c.label)}</label>`).join("")}</div>`;
      html += `<p class="help-text">Open <strong>Connect</strong> for your first preset, or explore <strong>Network &amp; Security</strong> and <strong>Tools</strong>.</p>`;
    }
    host.innerHTML = html;
    bindViewJumps(host);
    renderWizardProgress();
    const skippable = !!meta.skippable;
    $("wizardSkip")?.classList.toggle("hidden", !skippable || sid === "finish");
    const prevStep = wizardShortMode ? wizardPrevInFlow(sid) : (sid === "welcome" ? null : true);
    $("wizardBack")?.classList.toggle("hidden", !prevStep || sid === "welcome");
    if ($("wizardNext")) {
      $("wizardNext").textContent = sid === "finish" ? "Finish setup" : "Continue";
    }
    if (sid === "country") {
      const sel = $("wizardCountrySelect");
      if (sel) {
        sel.innerHTML = '<option value="">Country…</option>';
        countries.forEach((c) => {
          const o = document.createElement("option");
          o.value = c;
          o.textContent = countryLabel(c);
          sel.appendChild(o);
        });
        if (wizardData?.connect_country) sel.value = wizardData.connect_country;
      }
    }
    host.querySelector("#btnWizardInstallNord")?.addEventListener("click", () => runWizardInstall(false));
    host.querySelector("#btnWizardNordPreview")?.addEventListener("click", () => runWizardInstall(true));
    host.querySelector("#btnWizardNordLogin")?.addEventListener("click", () => runWizardNordLoginInShell());
    host.querySelector("#btnWizardNordRecheck")?.addEventListener("click", () => refreshWizardDoctor());
    host.querySelector("#btnWizardCopyPriv")?.addEventListener("click", () => {
      const t = $("wizardPrivCmd")?.textContent || priv.manual_sudo_hint || "";
      navigator.clipboard?.writeText(t).then(() => toast("Copied to clipboard", true)).catch(() => toast("Copy failed", false));
    });
    host.querySelector("#btnWizardCountrySave")?.addEventListener("click", saveWizardCountry);
    host.querySelector("#btnWizardWifiSync")?.addEventListener("click", () => doAction({ action: "wifi_sync_profiles" }, "Sync WiFi").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardStartNordvpnd")?.addEventListener("click", () => doAction({ action: "service_nordvpnd", op: "start" }, "Start nordvpnd").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardInstallUiSvc")?.addEventListener("click", () => doAction({ action: "service_ui", op: "install" }, "UI service").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardSvcRecheck")?.addEventListener("click", () => refreshWizardContext());
    host.querySelector("#btnWizardTrustSsid")?.addEventListener("click", () => {
      const ssid = $("wizardTrustSsid")?.value?.trim();
      if (!ssid) { toast("Enter your home WiFi name", false); return; }
      doAction({ action: "wifi_zone_add", ssid, preset: "streaming-smartdns" }, "Trusted WiFi").then(() => refreshWizardContext());
    });
    host.querySelector("#btnWizardLearnHome")?.addEventListener("click", () => doAction({ action: "disconnect" }, "Disconnect VPN").then(() => {
      toast("VPN off — browse briefly on home WiFi to learn ISP, then reconnect", true);
      refreshWizardContext();
    }));
    host.querySelector("#btnWizardApplySmartDns")?.addEventListener("click", () => doAction({ action: "dns_apply_smart" }, "Smart DNS").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardDisableIpv6")?.addEventListener("click", () => runDisableIpv6().then(() => refreshWizardContext()));
    host.querySelector("#btnWizardIpv6Recheck")?.addEventListener("click", () => refreshWizardContext());
    host.querySelector("#btnWizardBaselineEnsure")?.addEventListener("click", () => doAction({ action: "baseline_ensure" }, "Baseline").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardConnect")?.addEventListener("click", () => {
      const cc = wizardData?.connect_country || lastState?.connect_country;
      if (!cc) return;
      doAction({ action: "connect", target: cc }, "Connect VPN").then(() => refreshWizardContext());
    });
    host.querySelector("#btnWizardPresetStreaming")?.addEventListener("click", () => doAction({ action: "preset", preset: "streaming-smartdns" }, "Preset").then(() => refreshWizardContext()));
    host.querySelector("#btnWizardNotifyPerm")?.addEventListener("click", () => {
      if (typeof Notification === "undefined") { toast("Browser notifications not supported", false); return; }
      Notification.requestPermission().then((p) => toast(p === "granted" ? "Notifications allowed" : "Permission denied", p === "granted"));
    });
    host.querySelector("#btnWizardAlertTest")?.addEventListener("click", () => saveWizardAlerts(true).then(() => doAction({ action: "alerts_test" }, "Test alert")));
    host.querySelector("#btnWizardPkgNet")?.addEventListener("click", () => installOnboardExtras("network"));
    host.querySelector("#btnWizardPkgSec")?.addEventListener("click", () => installOnboardExtras("security"));
    host.querySelector("#btnWizardPkgAll")?.addEventListener("click", () => installOnboardExtras("both"));
    host.querySelector("#btnWizardUiRecheck")?.addEventListener("click", () => refreshWizardContext());
    host.querySelector("#btnWizardUiCache")?.addEventListener("click", () => {
      resetNordctlBrowserUiState();
      refreshWizardContext();
    });
    host.querySelector("#btnWizardUiRestart")?.addEventListener("click", () => serviceAction("ui", "restart"));
  }

  async function refreshWizardContext() {
    wizardData = await api("/api/setup-wizard");
    await enrichWizardEmailContext();
    if (wizardData?.doctor && lastState) lastState.doctor = { ...lastState.doctor, ...wizardData.doctor };
    renderWizardStep(wizardData?.current_step || "welcome");
    renderSetupWizardChecklist(wizardData);
  }

  async function refreshWizardDoctor() {
    await refreshWizardContext();
  }

  function nordInstallShouldUseTerminal(res) {
    if (!res || res.already_installed) return false;
    if (res.ok && !res.dry_run && res.can_api_install !== false) return false;
    return !!(res.use_terminal || res.needs_password || res.shell_script);
  }

  async function runWizardNordLoginInShell() {
    sessionStorage.setItem(INSTALL_RETURN_ROUTE_KEY, WIZARD_RETURN_ROUTE);
    await termRunCommand("nordvpn login\n", "nordvpn login", { scope: "nord", scrollToTerminal: true });
    toast("Nord shell — complete login in the terminal", true);
  }

  async function runWizardNordInstallInTerminal(res) {
    const script = String(res?.shell_script || res?.plan?.shell_script || "").trim();
    if (!script) {
      toast("No install script for this distro — see Preview install", false);
      return false;
    }
    sessionStorage.setItem(INSTALL_RETURN_ROUTE_KEY, WIZARD_RETURN_ROUTE);
    const log = $("wizardInstallLog");
    log?.classList.remove("hidden");
    if (log) {
      log.textContent = "Opening Nord shell…\nEnter your sudo password when the box appears below the terminal.";
    }
    await termRunCommand(script, "Install NordVPN", { scope: "nord", scrollToTerminal: true });
    toast("Nord shell — enter sudo password when prompted", true);
    return true;
  }

  async function runWizardInstall(dryRun) {
    const log = $("wizardInstallLog");
    log?.classList.remove("hidden");
    if (log) log.textContent = dryRun ? "Preview…" : "Installing…";
    try {
      const res = await api("/api/install-nordvpn", { method: "POST", body: JSON.stringify({ dry_run: !!dryRun }) });
      if (!dryRun && nordInstallShouldUseTerminal(res)) {
        await runWizardNordInstallInTerminal(res);
        return;
      }
      const lines = [];
      if (res.error) lines.push("ERROR: " + res.error);
      if (res.already_installed) lines.push("NordVPN is already installed.");
      (res.logs || []).forEach((l) => {
        lines.push((l.ok ? "OK" : "FAIL") + ": " + l.cmd);
        if (l.output) lines.push(l.output);
      });
      (res.fix || []).forEach((s) => lines.push("→ " + s));
      (res.next_steps || []).forEach((s) => lines.push("→ " + s));
      if (dryRun && res.shell_script) {
        lines.push("", "# Would run in Nord shell:", res.shell_script.trim());
      }
      if (log) log.textContent = lines.join("\n") || (res.ok ? "Done" : "Failed");
      toast(res.ok ? (dryRun ? "Preview ready" : "Install OK") : (res.error || "Failed"), res.ok);
      await refreshWizardDoctor();
    } catch (e) {
      if (log) log.textContent = String(e);
    }
  }

  async function saveWizardCountry() {
    const country = $("wizardCountrySelect")?.value;
    if (!country) { toast("Pick a country", false); return; }
    const res = await doAction({ action: "set_connect_country", country }, "Save country");
    if (res.ok) {
      toast("Country saved", true);
      wizardData.connect_country = country;
      await refreshWizardDoctor();
    }
  }

  async function saveWizardAlerts(testOnly) {
    const browser = !!$("wizardBrowserAlerts")?.checked;
    const watch = !!$("wizardAlertWatch")?.checked;
    if (!testOnly) {
      await doAction({ action: "alerts_save", browser_enabled: browser }, "Alerts");
      await doAction({ action: "alerts_watch", enable: watch }, "Alert watch");
    }
    const emailEn = !!$("wizardEmailEn")?.checked;
    const to = $("wizardEmailTo")?.value?.trim();
    if (emailEn || to) {
      await doAction({
        action: "alerts_save",
        email: {
          enabled: emailEn,
          to: to || undefined,
          smtp_host: $("wizardSmtpHost")?.value?.trim() || undefined,
          smtp_user: $("wizardSmtpUser")?.value?.trim() || undefined,
          smtp_password: $("wizardSmtpPass")?.value || undefined,
        },
      }, "Email settings");
    }
  }

  async function saveWizardUiPassword() {
    if (!$("wizardLabPwEn")?.checked) return true;
    const pw = $("wizardLabPw")?.value || "";
    const pw2 = $("wizardLabPw2")?.value || "";
    if (pw.length < 4) { toast("Password must be at least 4 characters", false); return false; }
    if (pw !== pw2) { toast("Passwords do not match", false); return false; }
    const res = await doAction({ action: "ui_password_set", password: pw }, "Dashboard password");
    if (res.ok && res.token) sessionStorage.setItem(UI_TOKEN_KEY, res.token);
    return !!res.ok;
  }

  function ensureWizardPage() {
    if (getActiveView() !== "dashboard" || dashTab !== "wizard") {
      dashTab = "wizard";
      localStorage.setItem(DASH_TAB_KEY, "wizard");
      switchView("dashboard", { force: true, skipHash: true });
      switchPageTabs("dashboard", "wizard", { skipHash: true });
      syncRouteHash("dashboard", "wizard", false, null);
    }
  }

  function showWizardPanel(showGate) {
    wizardUiMode = showGate ? "gate" : "steps";
    $("wizardHub")?.classList.toggle("wizard-running", !showGate);
    $("wizardHubStage")?.classList.toggle("wizard-running", !showGate);
    $("wizardGate")?.classList.toggle("hidden", !showGate);
    $("setupWizard")?.classList.toggle("hidden", showGate);
    $("onboardOverlay")?.classList.add("hidden");
  }

  function closeWizardSteps() {
    wizardUiMode = "gate";
    $("wizardHub")?.classList.remove("wizard-running");
    $("wizardHubStage")?.classList.remove("wizard-running");
    $("wizardGate")?.classList.remove("hidden");
    $("setupWizard")?.classList.add("hidden");
  }

  function leaveWizardPage() {
    wizardUiMode = "hidden";
    closeWizardSteps();
    if (dashTab === "wizard") navigateRoute("dashboard", "connect", { force: true });
  }

  function closeSetupWizard() {
    leaveWizardPage();
  }

  async function openSetupWizardAt(stepId, opts = {}) {
    try {
      ensureWizardPage();
      await loadWizard(true);
      if (wizardData?.complete && !wizardData?.api_fallback) {
        const reopenStep = stepId || null;
        const action = reopenStep ? "setup_wizard_reopen" : "setup_wizard_restart";
        const res = await doAction(
          reopenStep ? { action, step: reopenStep } : { action },
          reopenStep ? "Open step" : "Restart wizard",
        );
        if (res.wizard) wizardData = res.wizard;
        else await loadWizard(true);
      }
      const steps = wizardData?.steps || WIZARD_STEPS_CLIENT;
      const pending = wizardPendingSetupCount(steps);
      if (opts.short === true) wizardShortMode = true;
      else if (opts.short === false) wizardShortMode = false;
      else wizardShortMode = !stepId && pending > 0;
      showWizardPanel(false);
      const doneCount = steps.filter((s) => s.state === "done").length;
      let target = stepId;
      if (!target) {
        target = wizardShortMode ? wizardFirstIncompleteStep(steps) : (wizardData?.current_step || "welcome");
      } else if (wizardShortMode && target === "welcome") {
        target = wizardFirstIncompleteStep(steps);
      } else if (!wizardShortMode && target === "welcome" && doneCount >= 3) {
        const next = wizardFirstIncompleteStep(steps);
        if (next && next !== "welcome") target = next;
      }
      if (target && target !== wizardData?.current_step) {
        if (wizardData?.api_fallback) {
          wizardData.current_step = target;
        } else {
          const res = await doAction({ action: "setup_wizard_goto", step: target }, "Open step");
          if (res.wizard) wizardData = res.wizard;
          else if (!res.ok) {
            toast(res.error || "Could not open wizard step", false);
            return;
          }
        }
      }
      renderWizardStep(wizardData?.current_step || target || "welcome");
    } catch (e) {
      toast(formatFetchError(e, "Setup wizard"), false);
    }
  }

  async function openSetupWizard(fromGate, short) {
    if (!short) {
      const res = await doAction({ action: "setup_wizard_restart" }, "Restart wizard");
      if (res.wizard) wizardData = res.wizard;
      else await loadWizard(true);
    }
    await openSetupWizardAt(fromGate ? "welcome" : null, { short: !!short });
  }

  function renderSetupWizardChecklist(data) {
    const panel = $("setupWizardChecklist");
    const body = $("setupWizardChecklistBody");
    if (!panel || !body) return;
    const list = data?.checklist || wizardData?.checklist || [];
    if (!list.length) {
      panel.classList.add("hidden");
      return;
    }
    const open = list.some((c) => !c.ok);
    panel.classList.toggle("hidden", !open && !!data?.complete);
    body.innerHTML = list.map((c) =>
      `<div class="wizard-checklist-row${c.ok ? " ok" : ""}">
        <label><input type="checkbox" disabled ${c.ok ? "checked" : ""} /> ${esc(c.label)}</label>
        ${c.ok ? "" : `<button type="button" class="btn xs sm wizard-fix-btn" data-wizard-fix="${esc(c.wizard_step || c.id)}">Fix now</button>`}
      </div>`
    ).join("");
    body.querySelectorAll("[data-wizard-fix]").forEach((btn) => {
      btn.addEventListener("click", () => {
        ensureWizardPage();
        openSetupWizardAt(btn.getAttribute("data-wizard-fix"), { short: true });
      });
    });
  }

  async function maybeShowSetupWizard(feats) {
    if (wizardUiMode === "steps" || wizardUiMode === "gate") return;
    await loadWizard(false);
    updateWizardGateButtons();
    if (wizardData?.complete || feats?.setup_wizard_complete) return;
    if (wizardData?.returning_user) {
      $("onboardReturning")?.classList.remove("hidden");
    } else {
      $("onboardReturning")?.classList.add("hidden");
    }
  }

  async function continueOnboardingCurrent() {
    const res = await doAction({ action: "setup_wizard_dismiss" }, "Continue");
    if (res.ok) {
      closeSetupWizard();
      toast("Welcome back — dashboard is ready.", true);
      await loadState(true);
    }
  }

  async function dismissSetupWizardGate() {
    const res = await doAction({ action: "setup_wizard_dismiss" }, "Skip wizard");
    if (res.ok) {
      closeSetupWizard();
      toast("Skipped — open Wizard anytime from the top bar.", true);
      await loadState(true);
    }
  }

  async function wizardGoBack() {
    const cur = wizardData?.current_step || "welcome";
    const prev = wizardShortMode ? wizardPrevInFlow(cur) : null;
    if (wizardData?.api_fallback) {
      if (wizardShortMode) {
        if (!prev) return;
        wizardData.current_step = prev;
        renderWizardStep(prev);
        return;
      }
      const steps = WIZARD_STEPS_CLIENT;
      const idx = steps.findIndex((s) => s.id === cur);
      const p = idx > 0 ? steps[idx - 1].id : null;
      if (!p) return;
      wizardData.current_step = p;
      renderWizardStep(p);
      return;
    }
    const backId = wizardShortMode ? prev : (() => {
      const steps = wizardData?.steps || [];
      const idx = steps.findIndex((s) => s.id === cur);
      return idx > 0 ? steps[idx - 1].id : null;
    })();
    if (!backId) return;
    const res = await doAction({ action: "setup_wizard_goto", step: backId }, "Back");
    if (res.wizard) wizardData = res.wizard;
    renderWizardStep(backId);
  }

  async function wizardGoNext(skip) {
    const cur = wizardData?.current_step || "welcome";
    if (wizardData?.api_fallback) {
      const nxt = wizardShortMode ? wizardNextInFlow(cur) : (() => {
        const steps = WIZARD_STEPS_CLIENT;
        const idx = steps.findIndex((s) => s.id === cur);
        return idx >= 0 && idx + 1 < steps.length ? steps[idx + 1].id : "finish";
      })();
      if (cur === "legal" && !skip && !wizardData?.legal_accepted && !$("wizardLegal")?.checked) {
        toast("Accept LEGAL.md to continue", false);
        return;
      }
      if (cur === "finish" && !skip) {
        toast("Restart nordctl serve from the project folder, then hard-refresh — wizard save needs the updated server.", false);
        return;
      }
      wizardData.current_step = nxt;
      renderWizardStep(nxt);
      return;
    }
    if (cur === "legal" && !skip) {
      if (!wizardData?.legal_accepted && !$("wizardLegal")?.checked) {
        toast("Accept LEGAL.md to continue", false);
        return;
      }
    }
    if (cur === "alerts" && !skip) await saveWizardAlerts(false);
    if (cur === "email" && !skip) await saveWizardAlerts(false);
    if (cur === "ui_access" && !skip) {
      const ok = await saveWizardUiPassword();
      if (!ok && $("wizardLabPwEn")?.checked) return;
    }
    if (cur === "finish" && !skip) {
      const res = await doAction({ action: "setup_wizard_complete", legal_accepted: true }, "Finish setup");
      if (res.ok) {
        closeSetupWizard();
        helpFullLoaded = false;
        toast("Setup complete — welcome to nordctl.", true);
        await loadState(true);
      }
      return;
    }
    const res = await doAction({
      action: "setup_wizard_advance",
      step: cur,
      skip: !!skip,
      legal_accepted: cur === "legal" && !skip,
    }, skip ? "Skip step" : "Continue");
    if (!res.ok) { toast(res.error || "Could not continue", false); return; }
    wizardData = res.wizard || wizardData;
    let nxt = wizardData?.current_step || "finish";
    if (wizardShortMode) {
      nxt = wizardNextInFlow(cur);
      if (nxt !== wizardData.current_step) {
        const g = await doAction({ action: "setup_wizard_goto", step: nxt }, "Open step");
        if (g.wizard) wizardData = g.wizard;
      }
    }
    renderWizardStep(wizardData?.current_step || nxt);
  }

  function renderDisconnectWatchStats(dw, box) {
    if (!box) return;
    box.innerHTML = [
      statCell("Alerts enabled", dw.enabled ? "Yes" : "No", dw.enabled ? "on" : "off"),
      statCell("Monitor running", dw.running ? "Yes" : "No", dw.running ? "on" : "off"),
      statCell("notify-send", dw.notify_send ? "Available" : "Missing", dw.notify_send ? "on" : "warn"),
      statCell("Poll interval", `${dw.interval_seconds || 30}s`, ""),
    ].join("");
  }

  async function loadPresetSuggestions(force) {
    const box = $("myPresetSuggestions");
    if (!box) return;
    try {
      const recs = await apiCached("/api/recommendations", {}, force ? 0 : CACHE_TTL.state);
      const items = recs.recommendations || [];
      if (!items.length) {
        box.classList.add("hidden");
        box.innerHTML = "";
        return;
      }
      box.classList.remove("hidden");
      box.innerHTML = [
        `<p class="help-text"><strong>Suggested for you</strong> — from doctor and WiFi zone checks (computed locally):</p>`,
        `<div class="sec-profile-grid">`,
        items.map((r) =>
          `<button type="button" class="wifi-scenario-btn sec-rec-btn" data-preset="${esc(r.preset)}" data-confirm="1" data-confirm-message="Apply preset “${esc(r.preset)}”? ${esc(r.reason)}"><strong>${esc(r.preset)}</strong><span>${esc(r.reason)}</span></button>`
        ).join(""),
        `</div>`,
      ].join("");
      box.querySelectorAll(".sec-rec-btn").forEach((b) => {
        b.addEventListener("click", () => doAction({ action: "preset", preset: b.dataset.preset }, "Preset"));
      });
    } catch (_) {
      box.classList.add("hidden");
    }
  }

  async function loadConnJournal(force) {
    const box = $("connJournal");
    if (!box) return;
    try {
      const journal = await apiCached(`/api/journal?limit=${getLogsDisplayLimit()}`, {}, force ? 0 : CACHE_TTL.state);
      const entries = journal.entries || [];
      if ($("connJournalBadge")) {
        $("connJournalBadge").textContent = entries.length ? String(entries.length) : "Empty";
        $("connJournalBadge").className = "badge " + (entries.length ? "on" : "off");
      }
      box.innerHTML = entries.length
        ? entries.map((e) => {
          const mark = e.ok ? "ok" : "err";
          const label = e.label || e.preset || e.title || "Preset";
          const ver = e.verification?.summary ? ` · ${e.verification.summary}` : "";
          const ts = e.ts ? new Date(e.ts).toLocaleString() : "";
          return `<article class="log-journal-card ${mark}">
            <div class="log-journal-head"><strong>${esc(label)}</strong><span class="badge ${e.ok ? "on" : "off"}">${e.ok ? "OK" : "Issue"}</span></div>
            <p class="log-journal-meta">${esc(ts)}${esc(ver)}</p>
          </article>`;
        }).join("")
        : `<div class="page-empty"><strong>No preset runs yet</strong>Run a preset from My presets to populate the journal.</div>`;
      drawConnJournalChart(entries);
    } catch (_) {
      box.innerHTML = `<div class="page-empty"><strong>Could not load journal</strong>Try Refresh or check file permissions.</div>`;
    }
  }

  async function loadAlertsPanel() {
    /* Alerts hub removed — see My presets, Activity log, Settings → Browser alerts */
  }

  async function pollBrowserAlerts() {
    if (!lastState?.features?.modules?.alerts && lastState?.features?.modules?.alerts !== undefined) return;
    try {
      const pending = await api("/api/alerts/pending?clear=0");
      setBellBadge(pending.count || 0);
      const data = await api("/api/alerts/pending?clear=1");
      (data.alerts || []).forEach((a) => {
        if (typeof Notification !== "undefined" && Notification.permission === "granted") {
          new Notification(a.title, { body: a.body, tag: a.rule_id });
        }
        toast(`${a.title}: ${a.body}`.slice(0, 120), a.severity !== "warn");
      });
      if (!(data.alerts || []).length) setBellBadge(pending.count || 0);
    } catch (_) { /* ignore */ }
  }

  async function refreshBellRecent() {
    try {
      const data = await api("/api/alerts/pending?clear=0");
      setBellBadge(data.count || 0);
      const box = $("bellRecent");
      if (!box) return;
      box.innerHTML = (data.alerts || []).slice(-6).reverse().map((a) =>
        `<div class="bell-recent-item"><strong>${esc(a.title)}</strong><span>${esc(a.body)}</span></div>`
      ).join("") || "<p class=\"muted\">No pending alerts — try Send test alert.</p>";
    } catch (_) { /* ignore */ }
  }

  async function loadAdvanced(force) {
    await loadTraffic(true);
    startTrafficLive();
    const advPage = localStorage.getItem("nordctl_adv_tab") || "traffic-internet";
    if (advPage === "traffic-live" || hubTab === "traffic-live") {
      loadBandwidthQuiet();
      startSecurityBw();
    } else {
      stopSecurityBw();
    }
    if (advPage === "traffic-speed" || hubTab === "traffic-speed") {
      syncSpeedLabContext();
      renderSpeedLabAll();
    }
    if (advPage === "spectrum-analyzer" || hubTab === "spectrum-analyzer") {
      await loadSpectrum(!!force);
      startSpectrumLive();
    } else {
      stopSpectrumLive();
    }
    if (advPage === "bluetooth-spectrum" || hubTab === "bluetooth-spectrum") {
      await loadBluetooth(!!force, { rescan: false });
      startBtSpectrumLive();
    } else {
      stopBtSpectrumLive();
    }
    if (lastState?.services) renderServicePanel(lastState.services);
    else api("/api/service").then((s) => renderServicePanel(s));
    if (advPage === "listeners" || hubTab === "listeners") await loadListeners(!!force);
    if (advPage === "privileges" || hubTab === "privileges" || force) await loadPrivileges(true);
    else if (lastState?.privileges) renderPrivileges(lastState.privileges);
    if (packageHubPageActive("network-packages")) loadHubTools("network", !!force);
    else if (packageHubPageActive("security-packages")) loadHubTools("security", !!force);
    else if (force) loadHubTools(null, true);
  }

  let helpFullLoaded = false;
  let helpCatalogVersion = 0;
  let helpSections = [];

  async function loadHelpFull(force) {
    if (!helpSections.length || force) {
      const data = await apiCached("/api/help", {}, force ? 0 : CACHE_TTL.help);
      helpSections = data.sections || [];
      helpCatalogVersion = data.version || 0;
      helpFullLoaded = false;
    }
    const cachedVer = parseInt(localStorage.getItem(HELP_CACHE_KEY) || "0", 10);
    const cacheHit = helpFullLoaded && !force && cachedVer === helpCatalogVersion;
    if (!cacheHit) {
      helpFullLoaded = true;
      localStorage.setItem(HELP_CACHE_KEY, String(helpCatalogVersion));
      const nav = $("helpFullNav");
      const body = $("helpFullBody");
      if (!nav || !body) return;
      nav.innerHTML = "";
      helpSections.forEach((s, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.dataset.helpId = s.id;
        b.textContent = s.title.replace(/&amp;/g, "&");
        b.classList.toggle("active", i === 0);
        b.addEventListener("click", () => showHelpFullSection(s.id));
        nav.appendChild(b);
      });
    }
    if (pendingHelpSection) {
      showHelpFullSection(pendingHelpSection);
      pendingHelpSection = null;
    } else if (!cacheHit && helpSections[0]) {
      showHelpFullSection(helpSections[0].id);
    }
    syncPageHow();
  }

  function showHelpFullSection(id) {
    const sec = helpSections.find((s) => s.id === id);
    const body = $("helpFullBody");
    if (!sec || !body) return;
    body.innerHTML = `<h2>${esc(sec.title.replace(/&amp;/g, "&"))}</h2>${sec.html}`;
    bindHelpDocButtons(body);
    $("helpFullNav")?.querySelectorAll("button").forEach((b) => {
      b.classList.toggle("active", b.dataset.helpId === id);
    });
    body.scrollTop = 0;
    if (getActiveView() === "help") syncRouteHash("help", null, false, id);
    syncPageHow();
  }

  async function loadSwitchesPanel(quiet, force) {
    const panel = $("switchesPanel");
    if (!panel) return;
    try {
      const data = force
        ? await api("/api/switches")
        : await apiCached("/api/switches", {}, CACHE_TTL.state);
      lastSwitchesData = data;
      renderSwitchesPanel(data);
    } catch (e) {
      if (!quiet) panel.innerHTML = `<p class="msg err">${esc(formatFetchError(e))}</p>`;
    }
  }

  function switchRowIsOn(sw, cur) {
    if (sw.type === "connect" || sw.type === "action") return false;
    if (cur?.on === true) return true;
    if (sw.type === "choice" && cur?.value) return true;
    return false;
  }

  function switchStatusBadge(cur) {
    const on = cur?.on;
    const disp = cur?.display || "Unknown";
    if (on === true) return `<span class="badge on switch-status-badge">On</span>`;
    if (on === false) return `<span class="badge off switch-status-badge">Off</span>`;
    return `<span class="badge switch-status-badge">${esc(disp)}</span>`;
  }

  function switchConfirmLines(sw, newVal, ctx, opts = {}) {
    const connected = ctx?.connected;
    const curOn = opts.currentOn !== undefined ? !!opts.currentOn : (sw.current?.on === true);
    if (sw.type === "connect") {
      const lines = [`Connect via ${sw.label}?`];
      if (sw.warn_enable) lines.push("", sw.warn_enable);
      if (sw.connect_warning) lines.push("", sw.connect_warning);
      else if (connected) lines.push("", "VPN is connected — this will reconnect you.");
      return lines.join("\n");
    }
    if (sw.type === "action") {
      const lines = [`Run ${sw.label}?`];
      if (sw.warn_change) lines.push("", sw.warn_change);
      return lines.join("\n");
    }
    if (sw.type === "value") {
      const lines = [`Set ${sw.label} to ${newVal}?`];
      if (sw.warn_change) lines.push("", sw.warn_change);
      if (connected) lines.push("", "VPN is connected — changing fwmark may affect routing.");
      return lines.join("\n");
    }
    const lines = sw.type === "toggle" && (newVal === "on" || newVal === "off")
      ? [newVal === "on" ? `Turn on ${sw.label}?` : `Turn off ${sw.label}?`]
      : [`Set ${sw.label} to ${newVal.toUpperCase()}?`];
    const warn = newVal === "on" ? sw.warn_enable : (newVal === "off" ? sw.warn_disable : sw.warn_change);
    if (warn) lines.push("", warn);
    if (newVal === "off" && sw.disconnect_warning_off) lines.push("", sw.disconnect_warning_off);
    if (newVal !== "on" && newVal !== "off" && sw.warn_change) lines.push("", sw.warn_change);
    if (sw.change_warning && (sw.type === "choice" || newVal !== (curOn ? "off" : "on"))) {
      lines.push("", sw.change_warning);
    }
    if (newVal === "on" && sw.requires_vpn_disconnect && connected) {
      lines.push("", "VPN is connected. Confirming will disconnect the VPN, then apply Smart DNS on your WiFi profiles.");
    }
    if (switchAffectsLocalNetwork(sw) && (newVal === "on" || newVal === "off")) {
      lines.push("", LOCAL_NETWORK_SCOPES.wifi_dns);
    }
    if ((switchAffectsLocalNetwork(sw) || sw.virtual === "split_tunnel_lan") && (newVal === "on" || newVal === "off")) {
      lines.push("", "Install baseline (Tools → Rollback) lets you revert config, Wi‑Fi DNS, and Nord settings to first-run state.");
    }
    return lines.join("\n");
  }

  const NORD_TOGGLE_DEFAULTS = {
    "nord-dns": {
      id: "nord-dns",
      label: "Nord DNS (while VPN connected)",
      type: "toggle",
      explain: "Uses Nord’s DNS servers while the VPN tunnel is connected — not the same as “VPN connected” in the top bar.",
    },
    "smart-dns-wifi": {
      id: "smart-dns-wifi",
      label: "Smart DNS on WiFi",
      type: "toggle",
      affects_local_network: true,
      explain: "Applies Nord streaming DNS to this computer's saved Wi‑Fi profiles (NetworkManager). Does not change your router or TV — only this PC's Wi‑Fi connections.",
    },
    meshnet: { id: "meshnet", label: "Meshnet", type: "toggle" },
    firewall: { id: "firewall", label: "Nord firewall", type: "toggle" },
    killswitch: { id: "killswitch", label: "Kill switch", type: "toggle" },
  };

  function switchDefById(id) {
    const sections = lastSwitchesData?.sections || [];
    const hit = sections.flatMap((s) => s.switches || []).find((x) => x.id === id);
    return hit || NORD_TOGGLE_DEFAULTS[id] || { id, label: id, type: "toggle" };
  }

  function nordDnsToggleStatusLine(sw, cur, data) {
    const id = String(sw?.id || "");
    const connected = !!(data?.firewall?.connected ?? data?.status?.connected ?? lastSwitchesData?.connected);
    const on = cur?.on === true || !!(id === "nord-dns" && data?.firewall?.nord?.nord_dns);
    const disp = cur?.display || (on ? "On" : "Off");
    if (id === "nord-dns") {
      if (on && connected) {
        return `<p class="nord-dns-toggle-status ok">Status: <strong>${esc(disp)}</strong> · Nord DNS active on the VPN tunnel</p>`;
      }
      if (!on && connected) {
        return `<p class="nord-dns-toggle-status warn">Status: <strong>Off</strong> · VPN is connected but Nord DNS is not — turn on below to use Nord’s DNS (103.86.x)</p>`;
      }
      if (on && !connected) {
        return `<p class="nord-dns-toggle-status">Status: <strong>On</strong> · will apply when you connect VPN</p>`;
      }
      return `<p class="nord-dns-toggle-status muted">Status: <strong>Off</strong> · VPN is not connected</p>`;
    }
    if (id === "smart-dns-wifi") {
      if (connected && !on) {
        return `<p class="nord-dns-toggle-status warn">Status: <strong>Off</strong> · VPN is connected — turn on below to disconnect and apply Smart DNS on WiFi</p>`;
      }
      if (on) {
        return `<p class="nord-dns-toggle-status ok">Status: <strong>On</strong> · streaming DNS is active on this PC's Wi‑Fi profiles</p>`;
      }
      const sd = data?.smart_dns || {};
      const pri = sd.primary || data?.firewall?.dns?.primary;
      if (pri) {
        return `<p class="nord-dns-toggle-status muted">Status: <strong>Off</strong> · IPs saved in config — turn on when VPN is off</p>`;
      }
      return `<p class="nord-dns-toggle-status muted">Status: <strong>Off</strong> · enter Smart DNS IPs below, save, then turn on</p>`;
    }
    return "";
  }

  function nordDnsToggleCard(sw, cur, data) {
    const id = String(sw?.id || "");
    const on = switchIsChecked(sw, cur);
    const toggle = renderSwitchToggleControl(sw, cur);
    const badge = switchStatusBadge(cur);
    const statusLine = nordDnsToggleStatusLine(sw, cur, data);
    const blocked = !!(sw?.blocked || (sw?.toggle_blocked_on && !on));
    const cardClass = [
      "nord-dns-toggle-card glass",
      on ? "is-on" : "",
      blocked ? "is-blocked" : "",
    ].filter(Boolean).join(" ");
    const shortLabel = id === "nord-dns" ? "Nord DNS" : (id === "smart-dns-wifi" ? "Smart DNS on WiFi" : (sw?.label || id));
    const blockHint = sw?.toggle_blocked_off
      ? `<p class="nord-dns-toggle-status muted">${esc(sw.blocked_reason_off || sw.blocked_reason || "")}</p>`
      : (sw?.blocked && sw?.blocked_reason
        ? `<p class="nord-dns-toggle-status warn">${esc(sw.blocked_reason)}</p>`
        : "");
    return `<article class="${cardClass}" data-nord-toggle-row="${esc(id)}" data-current-on="${on ? "1" : "0"}">
      <div class="nord-dns-toggle-head">
        <h4 class="nord-dns-toggle-title">${esc(shortLabel)}</h4>
        ${badge}
      </div>
      <p class="help-text nord-dns-toggle-desc">${esc(sw?.explain || "")}</p>
      ${statusLine}
      ${blockHint}
      <div class="nord-dns-toggle-control">${toggle}</div>
    </article>`;
  }

  function nordToggleStatRow(label, on, switchId) {
    const sw = switchDefById(switchId);
    const cur = sw.current || { on: !!on, display: on ? "On" : "Off" };
    const toggle = renderSwitchToggleControl(sw, cur);
    const onNow = switchIsChecked(sw, cur);
    return `<div class="stat-pair stat-pair-toggle" data-nord-toggle-row="${esc(switchId)}" data-current-on="${onNow ? "1" : "0"}">
      <div class="lbl">${esc(label)}</div>
      <div class="val toggle-val">${toggle}</div>
    </div>`;
  }

  function bindNordToggleRows(container, interactive) {
    if (!container) return;
    const canUse = interactive !== false && nordInstalled(lastState);
    container.querySelectorAll("[data-nord-toggle-row]").forEach((row) => {
      const id = row.getAttribute("data-nord-toggle-row");
      const sw = switchDefById(id);
      const toggle = row.querySelector("[data-switch-toggle]");
      if (!toggle || toggle.dataset.bound) return;
      toggle.dataset.bound = "1";
      if (!canUse) {
        toggle.disabled = true;
        row.classList.add("is-blocked");
        return;
      }
      toggle.addEventListener("change", async () => {
        const want = toggle.checked ? "on" : "off";
        const wasOn = row.getAttribute("data-current-on") === "1";
        if (want === "on" && sw.toggle_blocked_on) {
          toggle.checked = false;
          toast(sw.blocked_reason || "Cannot turn on right now.", false);
          return;
        }
        if (want === "off" && sw.toggle_blocked_off) {
          toggle.checked = true;
          toast(sw.blocked_reason_off || sw.blocked_reason || "Cannot turn off right now.", false);
          return;
        }
        const ok = await applyNordSwitch(sw, want, { currentOn: wasOn });
        if (!ok) toggle.checked = !toggle.checked;
      });
    });
    applyButtonTitles(container);
  }

  async function ensureSwitchesMeta(force) {
    if (lastSwitchesData?.ok && !force) return lastSwitchesData;
    try {
      lastSwitchesData = force
        ? await api("/api/switches")
        : await apiCached("/api/switches", {}, CACHE_TTL.state);
    } catch (_) {
      /* optional — inline toggles still work with defaults */
    }
    return lastSwitchesData;
  }

  async function applyNordSwitch(sw, value, opts = {}) {
    if (sw.blocked) {
      toast(sw.blocked_reason || "This switch cannot be changed right now.", false);
      return false;
    }
    if (value === "on" && sw.toggle_blocked_on) {
      toast(sw.blocked_reason || "Cannot turn this on with your current VPN setup.", false);
      return false;
    }
    if (value === "off" && sw.toggle_blocked_off) {
      toast(sw.blocked_reason_off || sw.blocked_reason || "Cannot turn this off right now.", false);
      return false;
    }
    const msg = switchConfirmLines(sw, value, lastSwitchesData || {}, opts);
    if (!confirm(msg)) return false;
    const res = await doAction({ action: "nord_switch", id: sw.id, value }, sw.label);
    if (res.ok) {
      toast(res.note || "Switch updated", true);
      await loadState(true);
      await loadSwitchesPanel(true, true);
    } else {
      const stepErr = (res.steps || []).find((s) => s && s.ok === false);
      toast(res.error || res.hint || stepErr?.output || res.note || "Switch failed", false);
    }
    return res.ok;
  }

  function switchIsChecked(cur) {
    return cur?.on === true;
  }

  function renderSwitchConnectControl(sw) {
    if (sw.active) {
      return `<button type="button" class="btn sm primary switch-connect-btn" disabled title="${esc(sw.blocked_reason || "Active connection")}">Active</button>`;
    }
    return `<button type="button" class="btn sm primary switch-connect-btn" data-switch-connect="1">Connect</button>`;
  }

  function renderSwitchActionControl(sw) {
    return `<button type="button" class="btn sm switch-action-btn" data-switch-action="1">${esc(sw.action_label || "Run")}</button>`;
  }

  function renderSwitchValueControl(sw, cur) {
    const val = esc(cur?.value || cur?.display || "");
    const ph = esc(sw.placeholder || "0xe1f1");
    return `<div class="switch-value-row">
      <input type="text" class="switch-value-input mono" data-switch-value="1" value="${val}" placeholder="${ph}" spellcheck="false" autocomplete="off" />
      <button type="button" class="btn sm primary switch-value-apply" data-switch-value-apply="1">Apply</button>
    </div>`;
  }

  function renderSwitchReadonlyControl() {
    return `<p class="switch-readonly-note muted">Read-only on this CLI</p>`;
  }

  function renderSwitchToggleControl(sw, cur) {
    const on = switchIsChecked(cur);
    const blocked = !!sw.blocked;
    return `<label class="switch-toggle-wrap${blocked ? " is-blocked" : ""}" title="${esc(blocked ? (sw.blocked_reason || "Not available") : `Toggle ${sw.label}`)}">
      <span class="switch-toggle-label off">Off</span>
      <input type="checkbox" class="switch-toggle" data-switch-toggle="1" ${on ? "checked" : ""}${blocked ? " disabled" : ""} />
      <span class="switch-toggle-label on">On</span>
    </label>`;
  }

  function renderSwitchChoiceControl(sw, cur) {
    const curVal = (cur.value || "").toUpperCase();
    const blocked = !!sw.blocked;
    return `<div class="switch-choice-row">${(sw.choices || []).map((c) =>
      `<button type="button" class="btn sm switch-choice${curVal === c.value ? " active primary" : ""}" data-switch-choice="${esc(c.value)}"${blocked ? ` disabled title="${esc(sw.blocked_reason || "Not available")}"` : ""}>${esc(c.label)}</button>`
    ).join("")}</div>`;
  }

  function bindSwitchRow(el, sw, interactive = true) {
    if (!interactive) {
      el.querySelectorAll("button, input").forEach((n) => { n.disabled = true; });
      return;
    }
    if (sw.blocked) {
      el.querySelectorAll("button:not([disabled]), input:not([disabled])").forEach((n) => { n.disabled = true; });
    }
    if (sw.type === "choice") {
      if (sw.blocked) return;
      el.querySelectorAll("[data-switch-choice]").forEach((btn) => {
        btn.addEventListener("click", async () => {
          const val = btn.getAttribute("data-switch-choice");
          if (btn.classList.contains("active")) return;
          await applyNordSwitch(sw, val);
        });
      });
      return;
    }
    if (sw.type === "connect") {
      if (sw.blocked) return;
      el.querySelector("[data-switch-connect]")?.addEventListener("click", () => applyNordSwitch(sw, "connect"));
      return;
    }
    if (sw.type === "action") {
      el.querySelector("[data-switch-action]")?.addEventListener("click", () => applyNordSwitch(sw, "run"));
      return;
    }
    if (sw.type === "value") {
      const input = el.querySelector("[data-switch-value]");
      el.querySelector("[data-switch-value-apply]")?.addEventListener("click", async () => {
        const val = (input?.value || "").trim();
        if (!val) {
          toast("Enter a firewall mark value", false);
          return;
        }
        await applyNordSwitch(sw, val);
      });
      input?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") el.querySelector("[data-switch-value-apply]")?.click();
      });
      return;
    }
    if (sw.type === "readonly") return;
    const toggle = el.querySelector("[data-switch-toggle]");
    if (toggle) {
      toggle.addEventListener("change", async () => {
        const want = toggle.checked ? "on" : "off";
        if (want === "on" && sw.toggle_blocked_on) {
          toggle.checked = false;
          toast(sw.blocked_reason || "Cannot turn on with current VPN setup.", false);
          return;
        }
        const ok = await applyNordSwitch(sw, want);
        if (!ok) toggle.checked = !toggle.checked;
      });
    }
  }

  function renderSwitchesSessionBanner(data) {
    const box = $("switchesSessionBanner");
    if (!box) return;
    if (!data?.ok || !data.available) {
      box.classList.add("hidden");
      box.innerHTML = "";
      return;
    }
    const conn = data.connection || {};
    box.classList.remove("hidden");
    if (data.connected) {
      const tech = data.technology ? String(data.technology).replace(/_/g, " ") : null;
      const specialty = data.active_server_group_label || null;
      const sessionBits = [
        conn.country && conn.country !== "—" ? `Country: <strong>${esc(conn.country)}</strong>` : "",
        conn.server && conn.server !== "—" ? `Server: <strong>${esc(conn.server)}</strong>` : "",
        specialty ? `Mode: <strong>${esc(specialty)}</strong>` : "",
        tech && !specialty ? `Protocol: <strong>${esc(tech)}</strong>` : "",
      ].filter(Boolean).join(" · ");
      box.className = "switches-session-banner glass switches-session-connected";
      box.innerHTML = `<strong class="switches-session-title">You are connected — only some switches are safe to use</strong>
        <p class="switches-session-body">${sessionBits || "VPN tunnel is active."} While connected, nordctl reads your live session and <strong>disables switches that clash</strong> (grey cards with “Unavailable”). Switches that stay enabled may still <strong>reconnect or disconnect</strong> you — always read the yellow warning and confirm dialog.</p>
        <ul class="compact-help-list switches-session-list">
          <li><strong>Grey / Unavailable</strong> — cannot use until you disconnect or change something else first.</li>
          <li><strong>Active</strong> (server groups) — you are already on that specialty server.</li>
          <li><strong>Yellow “If you change”</strong> — will likely reconnect the VPN.</li>
          <li><strong>Need an exact combo?</strong> Disconnect, or open <strong>Create preset</strong> to save and run the full workflow in one go.</li>
        </ul>`;
    } else {
      box.className = "switches-session-banner glass switches-session-disconnected";
      box.innerHTML = `<strong class="switches-session-title">VPN is off — all switches are available</strong>
        <p class="switches-session-body">Changes here update Nord settings for your <strong>next</strong> connect. They do not start the VPN by themselves (use <strong>Connect</strong> or a preset). If you want country + Meshnet + firewall + ports + Smart DNS applied together every time, use <strong>Create preset</strong> instead of flipping switches one by one.</p>`;
    }
    bindViewJumps(box);
  }

  function renderSwitchesPanel(data) {
    const panel = $("switchesPanel");
    const badge = $("switchesConnBadge");
    const summary = $("switchesConnSummary");
    if (!panel) return;
    const sections = data?.sections || [];
    if (!data?.ok) {
      const err = data?.error === "not found"
        ? "Switches API not found — restart nordctl serve to load the latest server."
        : (data?.error || "Could not load switches.");
      panel.innerHTML = `<p class="msg err">${esc(err)}</p>`;
      if (badge) { badge.textContent = "—"; badge.className = "badge off"; }
      if (summary) summary.textContent = "";
      renderSwitchesSessionBanner(null);
      return;
    }
    const conn = data.connection || {};
    renderSwitchesSessionBanner(data);
    if (badge) {
      if (!data.available) {
        badge.textContent = "No CLI";
        badge.className = "badge off";
      } else {
        badge.textContent = data.connected ? "VPN on" : "VPN off";
        badge.className = "badge " + (data.connected ? "on" : "off");
      }
    }
    if (summary) {
      if (!data.available) {
        summary.textContent = data.message || "Install NordVPN from Setup to read and apply live settings.";
      } else if (data.connected) {
        const parts = [
          `Session: ${conn.country || "—"}`,
          conn.server && conn.server !== "—" ? conn.server : null,
          conn.ip && conn.ip !== "—" ? conn.ip : null,
          data.active_server_group_label ? data.active_server_group_label : (data.technology ? data.technology.replace(/_/g, " ") : null),
        ].filter(Boolean);
        summary.textContent = `${parts.join(" · ")} — grey cards are blocked for this session; others ask for confirmation before changing.`;
      } else {
        summary.textContent = "No active VPN tunnel — switches update Nord for the next connect. For multi-step setups, prefer Create preset over changing many switches manually.";
      }
    }
    if (!sections.length) {
      panel.innerHTML = `<p class="muted">No switches loaded.</p>`;
      return;
    }
    const banner = !data.available
      ? `<p class="msg warn switches-banner">${esc(data.message || "NordVPN CLI not available — toggles are preview only until you install and log in from Setup.")}</p>`
      : "";
    const allSwitches = sections.flatMap((sec) =>
      (sec.switches || []).map((sw) => ({ ...sw, section: sw.section || sec.title }))
    );
    panel.innerHTML = banner + `<div class="switch-grid-4 grid-4">${allSwitches.map((sw) => {
      const cur = sw.current || {};
      const rowOn = switchRowIsOn(sw, cur);
      const warns = [
        sw.blocked && sw.blocked_reason ? `<p class="switch-warn switch-warn-blocked"><strong>Unavailable:</strong> ${esc(sw.blocked_reason)}</p>` : "",
        sw.toggle_blocked_on && sw.blocked_reason && !sw.blocked ? `<p class="switch-warn switch-warn-blocked"><strong>Cannot turn ON:</strong> ${esc(sw.blocked_reason)}</p>` : "",
        sw.connect_warning ? `<p class="switch-warn"><strong>If you connect:</strong> ${esc(sw.connect_warning)}</p>` : "",
        sw.change_warning ? `<p class="switch-warn"><strong>If you change:</strong> ${esc(sw.change_warning)}</p>` : "",
        sw.warn_enable ? `<p class="switch-warn switch-warn-enable"><strong>If you turn ON:</strong> ${esc(sw.warn_enable)}</p>` : "",
        sw.warn_disable ? `<p class="switch-warn switch-warn-disable"><strong>If you turn OFF:</strong> ${esc(sw.warn_disable)}</p>` : "",
        sw.disconnect_warning_off ? `<p class="switch-warn switch-warn-disconnect"><strong>Disconnect:</strong> ${esc(sw.disconnect_warning_off)}</p>` : "",
        sw.warn_change ? `<p class="switch-warn"><strong>Note:</strong> ${esc(sw.warn_change)}</p>` : "",
      ].filter(Boolean).join("");
      let control = "";
      if (sw.type === "choice") {
        control = renderSwitchChoiceControl(sw, cur);
      } else if (sw.type === "connect") {
        control = renderSwitchConnectControl(sw);
      } else if (sw.type === "action") {
        control = renderSwitchActionControl(sw);
      } else if (sw.type === "value") {
        control = renderSwitchValueControl(sw, cur);
      } else if (sw.type === "readonly") {
        control = renderSwitchReadonlyControl();
      } else {
        control = renderSwitchToggleControl(sw, cur);
      }
      const helper = sw.helper_jump
        ? `<div class="switch-helper panel-nav-actions inline-jump-actions"><button type="button" class="btn sm jump-link" data-view-jump="${esc(sw.helper_jump)}">${esc(sw.helper_label || "Open")}</button></div>`
        : "";
      const cat = sw.section ? `<span class="switch-row-cat">${esc(sw.section)}</span>` : "";
      const rowClass = [
        "switch-row glass",
        rowOn || sw.active ? " is-on" : "",
        sw.blocked ? " is-blocked" : "",
        sw.active ? " is-active" : "",
      ].join("");
      return `<article class="${rowClass.trim()}" data-switch-id="${esc(sw.id)}">
        ${cat}
        <div class="switch-row-head">
          <h4>${esc(sw.label)}</h4>
          ${switchStatusBadge(cur)}
        </div>
        <p class="switch-current muted">Currently: <strong>${esc(cur.display || "Unknown")}</strong></p>
        <p class="help-text switch-explain">${esc(sw.explain || "")}</p>
        ${helper}
        ${warns}
        ${control}
      </article>`;
    }).join("")}</div>`;
    panel.querySelectorAll(".switch-row").forEach((el) => {
      const id = el.getAttribute("data-switch-id");
      const sw = (sections.flatMap((s) => s.switches || [])).find((x) => x.id === id);
      if (sw) bindSwitchRow(el, sw, data.available !== false);
    });
    bindViewJumps(panel);
    applyButtonTitles(panel);
  }

  function allowlistSourceLabel(entry) {
    if (entry?.from_voip_config) return "voip_ports preset";
    if (entry?.partial_voip_config) return "preset + custom";
    return "Nord allowlist";
  }

  function renderAllowlistPanel(al) {
    const box = $("allowlistBox");
    if (!box) return;
    const subnets = al?.subnets || [];
    const details = al?.port_details || [];
    const voipCfg = (al?.voip_ports_config || []).join(", ") || "—";
    let html = "";

    html += `<div class="allowlist-section">`;
    html += `<h4 class="allowlist-section-title">Subnets (${subnets.length})</h4>`;
    if (!subnets.length) {
      html += `<p class="help-text muted-inline">No subnets allowlisted in NordVPN yet. Save a Home LAN range and press <strong>Apply to Nord</strong>, or use <strong>Add subnet</strong> below.</p>`;
    } else {
      html += `<ul class="allowlist-subnet-list compact-help-list">`;
      subnets.forEach((cidr) => {
        html += `<li><code>${esc(cidr)}</code> — devices on this network range can bypass the VPN tunnel (printers, NAS, LAN servers).</li>`;
      });
      html += `</ul>`;
    }
    html += `</div>`;

    html += `<div class="allowlist-section">`;
    html += `<h4 class="allowlist-section-title">Port rules (${details.length})</h4>`;
    html += `<p class="help-text allowlist-port-lead">Each rule lets matching traffic skip the VPN tunnel. One line from NordVPN may cover <strong>both TCP and UDP</strong> (shown as <code>UDP|TCP</code>). These persist until removed — often added by the <strong>VoIP / messaging friendly</strong> preset (<code>voip_ports</code> in config: ${esc(voipCfg)}).</p>`;
    if (!details.length) {
      html += `<p class="help-text muted-inline">No port rules on NordVPN. Use <strong>Add port</strong> below or run a preset with VoIP allowlist.</p>`;
    } else {
      html += `<div class="allowlist-port-table-wrap"><table class="allowlist-port-table"><thead><tr><th>NordVPN rule</th><th>What it does</th><th>Likely source</th></tr></thead><tbody>`;
      details.forEach((entry) => {
        const proto = entry.protocols ? `<span class="allowlist-proto">${esc(entry.protocols)}</span>` : "";
        html += `<tr><td><code>${esc(entry.raw)}</code>${proto ? `<div class="allowlist-proto-line">${proto}</div>` : ""}</td>`;
        html += `<td>${esc(entry.summary || "Bypasses VPN for this port.")}</td>`;
        html += `<td><span class="badge ${entry.from_voip_config ? "on" : ""}">${esc(allowlistSourceLabel(entry))}</span></td></tr>`;
      });
      html += `</tbody></table></div>`;
      html += `<p class="help-text muted-inline allowlist-remove-hint">To remove: <code>nordvpn allowlist remove port 80</code> (repeat per rule). Subnets: <code>nordvpn allowlist remove subnet 192.168.0.0/16</code>.</p>`;
    }
    html += `</div>`;

    box.innerHTML = html;
  }

  async function loadNordRoutingPanel(quiet, force) {
    try {
      const ttl = force ? 0 : CACHE_TTL.routing;
      const al = await apiCached("/api/allowlist", {}, ttl);
      syncHomeLanUi({ ...(lastState || {}), lan_allowlist_cidr: al.lan_cidr ?? lastState?.lan_allowlist_cidr });
      renderAllowlistPanel(al);
      const subN = al.subnet_count ?? (al.subnets || []).length;
      const portN = al.port_count ?? (al.ports || []).length;
      if ($("splitMetricSubnets")) $("splitMetricSubnets").textContent = String(subN);
      if ($("splitMetricPorts")) $("splitMetricPorts").textContent = String(portN);
      if ($("splitMetricPortsSub")) {
        $("splitMetricPortsSub").textContent = portN
          ? `${portN} rule${portN === 1 ? "" : "s"} in NordVPN`
          : "None on NordVPN";
      }
      if ($("splitAllowlistIntroText")) {
        $("splitAllowlistIntroText").textContent = al.metric_note
          || "Counts rules stored in NordVPN — not empty form fields.";
      }
      if ($("splitMetricLan")) $("splitMetricLan").textContent = esc(al.lan_cidr || lastState?.lan_allowlist_cidr || "—");
      if ($("splitTunnelBadge")) $("splitTunnelBadge").textContent = subN + portN ? `${subN + portN} rules` : "Empty";
      fillCountryDropdowns();
      bindFavCountryCity();
      bindConnectCountryCity();
      const fs = $("favCountrySelect");
      if (fs && countries.length) {
        fs.innerHTML = '<option value="">Country…</option>';
        countries.forEach((c) => {
          const o = document.createElement("option");
          o.value = c;
          o.textContent = countryLabel(c);
          fs.appendChild(o);
        });
      }
    } catch (e) {
      if (!quiet) toast(String(e), false);
    }
  }

  async function loadFirewall(force) {
    await loadUfw(!!force);
  }

  async function ufwAction(body, okMsg) {
    setBusy(true);
    showMsg("Running…", true);
    try {
      const res = await api("/api/ufw", { method: "POST", body: JSON.stringify(body) });
      if (res.state) renderUfwEditor(res.state);
      else await loadUfw();
      const msg = res.message || res.error || res.manual || (res.ok ? okMsg || "Done" : "Failed");
      showMsg(msg, res.ok);
      toast(msg.slice(0, 120), res.ok);
      if (res.manual && !res.ok) {
        showNotice(
          (res.error || "This action needs sudo.") + "\n\nRun in terminal:\n" + res.manual,
          { ok: false, title: "UFW — manual step", copyText: res.manual }
        );
      }
      logActivity("UFW", msg.slice(0, 120), res.ok);
      return res;
    } catch (err) {
      showMsg(String(err), false);
      return { ok: false };
    } finally {
      setBusy(false);
    }
  }

  function renderUfwEditor(data) {
    const st = data?.status || {};
    const notice = $("ufwLocalNetworkNotice");
    if (notice) notice.innerHTML = localNetworkNoticeHtml({ scope: "ufw" });
    const badge = $("ufwHeroBadge");
    if (badge) {
      if (!st.installed && st.available === false) {
        badge.textContent = "N/A";
        badge.className = "badge off";
      } else if (st.enabled) {
        badge.textContent = "ON";
        badge.className = "badge on";
      } else {
        badge.textContent = "OFF";
        badge.className = "badge warn";
      }
    }
    const warn = $("ufwManageWarn");
    if (warn) {
      if (st.note && !st.can_manage) {
        warn.textContent = st.note;
        warn.classList.remove("hidden");
      } else {
        warn.classList.add("hidden");
      }
    }
    const stats = $("ufwStats");
    if (stats) {
      stats.innerHTML = [
        statCell("Status", st.enabled ? "active" : (st.installed ? "inactive" : "not installed"), st.enabled ? "on" : "off"),
        statCell("Default in", esc(st.default_in || "—")),
        statCell("Default out", esc(st.default_out || "—")),
        statCell("Rules", esc(String(st.rule_count ?? 0))),
      ].join("");
    }
    $("ufwRulesCount") && ($("ufwRulesCount").textContent = `${st.rule_count ?? 0} active`);
    const presets = $("ufwPresets");
    if (presets) {
      presets.innerHTML = (data.presets || []).map((p) =>
        `<button type="button" class="btn sm ufw-preset${p.exists ? " exists" : ""}" data-ufw-preset="${esc(p.id)}" data-confirm-message="Are you sure you want to add the ${esc(p.label)} UFW preset rule?&#10;&#10;${esc(p.detail)}" title="${esc(p.detail)}">${esc(p.label)}</button>`
      ).join("");
      presets.querySelectorAll("[data-ufw-preset]").forEach((b) => {
        b.addEventListener("click", () => ufwAction({ action: "preset", preset: b.dataset.ufwPreset }, "Preset added"));
      });
    }
    const list = $("ufwRulesList");
    if (!list) return;
    const rules = st.rules || [];
    if (!rules.length) {
      list.innerHTML = '<p class="muted">No numbered rules yet.</p>';
      return;
    }
    list.innerHTML = rules.map((r) => {
      const num = r.number;
      const del = num != null && st.can_manage
        ? `<button type="button" class="btn sm danger" data-ufw-del="${num}" data-confirm-message="Are you sure you want to remove UFW rule #${num}?">Remove</button>`
        : "";
      return `<div class="ufw-rule-row"><span class="mono ufw-rule-num">#${esc(num ?? "—")}</span><span class="ufw-rule-line">${esc(r.line || "")}${r.comment ? ` <span class="muted">(${esc(r.comment)})</span>` : ""}</span>${del}</div>`;
    }).join("");
    list.querySelectorAll("[data-ufw-del]").forEach((b) => {
      b.addEventListener("click", () => ufwAction({ action: "delete", number: parseInt(b.dataset.ufwDel, 10) }, "Rule removed"));
    });
  }

  async function loadUfw(force) {
    try {
      const data = await apiCached("/api/ufw", {}, force ? 0 : CACHE_TTL.ufw);
      renderUfwEditor(data);
    } catch (_) {
      $("ufwRulesList") && ($("ufwRulesList").innerHTML = '<p class="muted">Could not load UFW state.</p>');
    }
  }

  let toolsPayloadCache = null;

  async function refreshAfterToolInstall(toolId, hub) {
    invalidateApiCache("/api/tools");
    invalidateApiCache("/api/nettools");
    invalidateApiCache("/api/terminal/commands");
    toolsPayloadCache = null;
    helpFullLoaded = false;
    invalidateApiCache("/api/help");
    await loadHubTools(hub || null, true);
    if (hub === "security" || toolId === "ufw" || toolId === "tcpdump" || toolId === "libnotify") {
      await loadSecurity();
    }
    try {
      const nt = await api("/api/nettools");
      if (document.querySelector("#viewLab.view.active") || document.querySelector("#auditDiagnosticsPanel")?.closest(".view.active")) {
        renderNetTools(nt, "adv");
      }
    } catch (_) { /* ignore */ }
    if (toolId === "ufw") await loadUfw();
    if (toolId === "network-manager") await loadWifiHub(true);
    if (document.querySelector("#viewHelp.view.active")) loadHelpFull(true);
    if (termUiActive() && (termCommandScope() === "network" || termCommandScope() === "security")) {
      await termLoadQuickCommands(termCommandScope(), true);
    }
    applyButtonTitles();
  }

  function hubMissingInstallCmd(hub, data) {
    const group = data?.groups?.[hub];
    const missing = (group?.tools || []).filter((t) => !t.installed);
    const pkgs = [];
    missing.forEach((t) => (t.packages || []).forEach((p) => {
      if (p && !pkgs.includes(p)) pkgs.push(p);
    }));
    return pkgs.length ? `sudo apt install -y ${pkgs.join(" ")}` : "";
  }

  function copyToolCommand(cmd, label) {
    const text = String(cmd || "").trim();
    if (!text) return;
    navigator.clipboard?.writeText(text).then(() => toast(`Copied command for ${label || "tool"}`, true));
  }

  async function installToolInTerminal(installCmd, label, opts = {}) {
    const cmd = String(installCmd || "").trim();
    if (!cmd) return;
    const hub = opts.hub || packageApiHub(hubTab) || (getActiveView() === "customPackages" ? "custom" : "network");
    const category = opts.category || customPackagesCategory;
    setInstallReturnContext({ hub, returnRoute: opts.returnRoute || "", category });
    const scope = installTermScope(hub, category);
    toast("Opening Shell — enter your sudo password when asked", true);
    await termRunCommand(cmd, label || "Install package", {
      scrollToTerminal: hub !== "custom",
      scope,
    });
  }

  async function uninstallToolInTerminal(tool, label, opts = {}) {
    const pkgs = (tool?.packages || []).filter(Boolean);
    if (!pkgs.length) return;
    const cmd = `sudo apt remove -y ${pkgs.join(" ")}`;
    const hub = opts.hub || packageApiHub(hubTab) || (getActiveView() === "customPackages" ? "custom" : "network");
    const category = opts.category || customPackagesCategory;
    setInstallReturnContext({ hub, category });
    const scope = installTermScope(hub, category);
    toast("Opening Shell — enter your sudo password when asked", true);
    await termRunCommand(cmd, label || "Uninstall package", {
      scrollToTerminal: hub !== "custom",
      scope,
    });
  }

  async function installBatchSelected(hub) {
    const data = toolsPayloadCache || {};
    const group = data?.groups?.[hub];
    const ids = selectedInstallToolIds(hub).filter((id) => {
      const row = (group?.tools || []).find((t) => t.id === id);
      return row && !row.installed;
    });
    if (!ids.length) {
      toast("Select at least one package that is not installed", false);
      return;
    }
    if (data?.can_install_terminal && !data?.can_install) {
      const pkgs = [];
      ids.forEach((id) => {
        const row = (group?.tools || []).find((t) => t.id === id);
        (row?.packages || []).forEach((p) => { if (p && !pkgs.includes(p)) pkgs.push(p); });
      });
      if (pkgs.length) await installToolInTerminal(`sudo apt install -y ${pkgs.join(" ")}`, `Install ${ids.length} packages`, { hub, category: customPackagesCategory });
      return;
    }
    if (!data?.can_install) {
      const cmds = ids.map((id) => (group?.tools || []).find((t) => t.id === id)?.install_cmd).filter(Boolean).join("\n");
      if (cmds) copyToolCommand(cmds, `${ids.length} packages`);
      return;
    }
    if (!confirm(`Install ${ids.length} selected package(s) in one apt run?\n\nThis may take several minutes.`)) return;
    setBusy(true);
    try {
      const res = await api("/api/tools/install", { method: "POST", body: JSON.stringify({ tools: ids }) });
      toast(res.message || res.error || (res.ok ? "Installed" : "Failed"), res.ok || res.partial);
      if (res.tools) {
        toolsPayloadCache = res.tools;
        renderAllHubToolCards(toolsPayloadCache);
      }
      installToolsSelected[hub].clear();
      renderInstallToolsResult(res, hub, "install");
      if (res.ok || res.partial) await refreshAfterToolInstall(null, hub);
      else if (res.manual && data?.can_install_terminal) await installToolInTerminal(res.retry_cmd || res.manual, "Batch install", { hub, category: customPackagesCategory });
      logActivity("install", `Batch install (${hub}): ${res.message || res.error || "done"}`, res.ok);
    } finally {
      setBusy(false);
    }
  }

  async function uninstallBatchSelected(hub) {
    const data = toolsPayloadCache || {};
    const group = data?.groups?.[hub];
    const ids = selectedInstallToolIds(hub).filter((id) => {
      const row = (group?.tools || []).find((t) => t.id === id);
      return row && row.installed && !row.custom;
    });
    if (!ids.length) {
      toast("Select at least one installed package", false);
      return;
    }
    const labels = ids.map((id) => (group?.tools || []).find((t) => t.id === id)?.label || id).join(", ");
    if (!confirm(`Uninstall ${ids.length} selected package(s)?\n\n${labels}\n\nnordctl features that need them may stop working.`)) return;
    if (data?.can_install_terminal && !data?.can_install) {
      const pkgs = [];
      ids.forEach((id) => {
        const row = (group?.tools || []).find((t) => t.id === id);
        (row?.packages || []).forEach((p) => { if (p && !pkgs.includes(p)) pkgs.push(p); });
      });
      if (pkgs.length) await installToolInTerminal(`sudo apt remove -y ${pkgs.join(" ")}`, `Remove ${ids.length} packages`);
      return;
    }
    if (!data?.can_install) {
      toast("Copy uninstall commands from each card or set up Privileges", false);
      return;
    }
    setBusy(true);
    try {
      const res = await api("/api/tools/uninstall", { method: "POST", body: JSON.stringify({ tools: ids }) });
      toast(res.message || res.error || (res.ok ? "Removed" : "Failed"), res.ok || res.partial);
      if (res.tools) {
        toolsPayloadCache = res.tools;
        renderAllHubToolCards(toolsPayloadCache);
      }
      installToolsSelected[hub].clear();
      renderInstallToolsResult(res, hub, "uninstall");
      if (res.ok || res.partial) await refreshAfterToolInstall(null, hub);
      logActivity("install", `Batch uninstall (${hub}): ${res.message || res.error || "done"}`, res.ok);
    } finally {
      setBusy(false);
    }
  }

  async function installOptionalTool(toolId, label, opts = {}) {
    if (opts.returnRoute || opts.hub) {
      setInstallReturnContext({
        returnRoute: opts.returnRoute || "",
        hub: opts.hub,
        category: opts.category || customPackagesCategory,
      });
    }
    setBusy(true);
    try {
      const res = await api("/api/tools/install", { method: "POST", body: JSON.stringify({ tool: toolId }) });
      toast(res.message || res.error || (res.ok ? "Installed" : "Failed"), res.ok);
      if (res.ok || res.partial) {
        toolsPayloadCache = res.tools || toolsPayloadCache;
        const row = (res.tools?.tools || []).find((t) => t.id === toolId);
        const hub = res.hub || row?.hub || "network";
        renderAllHubToolCards(toolsPayloadCache);
        if (!opts.skipPackagesResult) renderInstallToolsResult(res, hub, "install");
        await refreshAfterToolInstall(toolId, hub);
      } else if (res.manual && toolsPayloadCache?.can_install_terminal) {
        const row = toolsPayloadCache?.tools?.find((t) => t.id === toolId);
        const rowHub = res.hub || opts.hub || row?.hub || packageApiHub(hubTab);
        await installToolInTerminal(res.manual, label, {
          returnRoute: opts.returnRoute || "",
          hub: rowHub,
          category: opts.category || row?.category || customPackagesCategory,
        });
      } else if (res.manual) {
        copyToolCommand(res.manual, label);
      } else {
        await loadHubTools(null, true);
      }
      logActivity("install", `${label}: ${res.message || res.error || "done"}`, res.ok);
    } finally {
      setBusy(false);
    }
  }

  async function installAllHubTools(hub) {
    const data = toolsPayloadCache || {};
    const group = data?.groups?.[hub];
    const missing = (group?.tools || []).filter((t) => !t.installed);
    if (!missing.length) {
      toast("All tools in this tab are already installed", true);
      return;
    }
    if (data?.can_install_terminal && !data?.can_install) {
      const cmd = hubMissingInstallCmd(hub, data);
      if (cmd) await installToolInTerminal(cmd, `Install ${group?.title || hub}`, { hub, category: customPackagesCategory });
      return;
    }
    if (!data?.can_install) {
      const cmds = hubMissingInstallCmd(hub, data) || missing.map((t) => t.install_cmd).filter(Boolean).join("\n");
      if (cmds) copyToolCommand(cmds, group?.title || hub);
      else toast("No install command available", false);
      return;
    }
    setBusy(true);
    try {
      const res = await api("/api/tools/install", { method: "POST", body: JSON.stringify({ hub, all: true }) });
      toast(res.message || res.error || (res.ok ? "Installed" : "Failed"), res.ok || res.partial);
      if (res.ok || res.partial) {
        toolsPayloadCache = res.tools || toolsPayloadCache;
        renderAllHubToolCards(toolsPayloadCache);
        renderInstallToolsResult(res, res.hub || hub, "install");
        await refreshAfterToolInstall(null, res.hub || hub);
      } else if (res.manual && data?.can_install_terminal) {
        await installToolInTerminal(res.manual.replace(/^sudo apt install -y\s*/, "sudo apt install -y ") || hubMissingInstallCmd(hub, data), group?.title || hub, { hub, category: customPackagesCategory });
      } else if (res.manual) {
        copyToolCommand(res.manual, group?.title || hub);
      } else {
        await loadHubTools(null, true);
      }
      logActivity("install", `${group?.title || hub} bulk: ${res.message || res.error || "done"}`, res.ok);
    } finally {
      setBusy(false);
    }
  }

  async function uninstallOptionalTool(toolId, label, opts = {}) {
    if (!toolId) return;
    const data = toolsPayloadCache || {};
    const row = data?.tools?.find((t) => t.id === toolId);
    if (opts.custom || row?.custom) {
      setBusy(true);
      try {
        const res = await api("/api/tools/uninstall", { method: "POST", body: JSON.stringify({ tool: toolId }) });
        const msg = res.error || (res.ok ? "Removed from list" : "Failed");
        toast(msg, res.ok);
        if (res.ok) {
          toolsPayloadCache = res.tools || toolsPayloadCache;
          renderAllHubToolCards(toolsPayloadCache);
        }
        logActivity("install", `${label}: ${msg}`, res.ok);
      } finally {
        setBusy(false);
      }
      return;
    }
    if (data?.can_install_terminal && !data?.can_install && row) {
      await uninstallToolInTerminal(row, label, { hub: row?.hub || packageApiHub(hubTab) });
      return;
    }
    if (!data?.can_install && row?.packages?.length) {
      copyToolCommand(`sudo apt remove -y ${row.packages.join(" ")}`, label);
      return;
    }
    setBusy(true);
    try {
      const res = await api("/api/tools/uninstall", { method: "POST", body: JSON.stringify({ tool: toolId }) });
      const msg = res.message || res.error || (res.ok ? "Uninstalled" : "Failed");
      toast(msg, res.ok);
      if (res.ok) {
        toolsPayloadCache = res.tools || toolsPayloadCache;
        renderAllHubToolCards(toolsPayloadCache);
        await refreshAfterToolInstall(toolId, res.hub);
      } else if (res.manual) {
        copyToolCommand(res.manual, label);
      }
      logActivity("install", `${label}: ${msg}`, res.ok);
    } finally {
      setBusy(false);
    }
  }

  function customToolsForHub(data, pageHub) {
    return (data?.groups?.custom?.tools || []).filter((t) => (t.hub || "network") === pageHub);
  }

  function updatePackageHubHeader(data, pageHub) {
    const g = data?.groups?.[pageHub] || {};
    const missing = g.missing_count || 0;
    const total = g.total || 0;
    const prefix = pageHub === "security" ? "securityPackages" : "networkPackages";
    const badge = $(`${prefix}Badge`);
    if (badge) {
      badge.textContent = missing ? `${missing} of ${total} missing` : (total ? `All ${total} installed` : "—");
      badge.className = "badge " + (missing ? "warn" : "on");
    }
    const summary = $(`${prefix}Summary`);
    if (summary && g.summary) summary.textContent = g.summary;
    const hint = $(`${prefix}Hint`);
    const onPackagePage = pageHub === "security"
      ? packageHubPageActive("security-packages")
      : packageHubPageActive("network-packages");
    if (hint && onPackagePage) hint.textContent = data?.install_hint || "";
    const optNoteId = pageHub === "security" ? "securityPackagesOptionalNote" : "networkPackagesOptionalNote";
    const optNote = $(optNoteId);
    if (optNote && onPackagePage && data?.optional_note) optNote.textContent = data.optional_note;
  }

  function syncWifiHubTabHighlight(tabId) {
    $("wifiHubSubnav")?.querySelectorAll("[data-wifi-hub-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-wifi-hub-tab") === tabId);
    });
  }

  function syncSecuritySubnavs() {
    const onSec = getActiveView() === "security";
    $("networkHubSubnav")?.classList.toggle("hidden", !onSec || hubTab !== "network");
    if (onSec && hubTab === "network") syncNetworkHubTabHighlight(networkHubTab);
  }

  function syncNetworkHubTabHighlight(tabId) {
    $("networkHubSubnav")?.querySelectorAll("[data-network-hub-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-network-hub-tab") === tabId);
    });
  }

  function switchNetworkHubTab(tabId, opts = {}) {
    const id = NETWORK_HUB_TABS[tabId] ? tabId : "dns";
    networkHubTab = id;
    localStorage.setItem("nordctl_network_hub_tab", id);
    syncNetworkHubTabHighlight(id);
    syncSecuritySubnavs();
    switchPageTabs("security", networkHubPanelId(id), { skipHash: true });
    if (!opts.skipHash && getActiveView() === "security") {
      syncRouteHash("network", "network", false, networkRouteSub(id));
    }
    syncPageIntro();
  }

  function initNetworkHubSubnav() {
    const nav = $("networkHubSubnav");
    if (!nav || nav.dataset.rendered) return;
    nav.dataset.rendered = "1";
    Object.entries(NETWORK_HUB_TABS).forEach(([id, cfg]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hub-subnav-btn";
      btn.setAttribute("data-network-hub-tab", id);
      btn.textContent = cfg.label;
      btn.title = cfg.title;
      btn.addEventListener("click", () => switchNetworkHubTab(id));
      nav.appendChild(btn);
    });
    syncNetworkHubTabHighlight(networkHubTab);
  }

  function syncTrafficHubTabHighlight(tabId) {
    $("trafficHubSubnav")?.querySelectorAll("[data-traffic-hub-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-traffic-hub-tab") === tabId);
    });
  }

  function syncTrafficSubnavs() {
    $("trafficHubSubnav")?.classList.add("hidden");
  }

  function switchTrafficHubTab(tabId, opts = {}) {
    const id = TRAFFIC_HUB_TABS[tabId] ? tabId : "internet";
    trafficHubTab = id;
    localStorage.setItem("nordctl_traffic_hub_tab", id);
    localStorage.setItem("nordctl_adv_tab", trafficHubPanelId(id));
    syncTrafficHubTabHighlight(id);
    switchPageTabs("advanced", trafficHubPanelId(id), { skipHash: true });
    if (id === "live") {
      loadBandwidthQuiet();
      startSecurityBw();
    } else {
      stopSecurityBw();
    }
    if (!opts.skipHash && getActiveView() === "advanced") {
      syncRouteHash("network", "traffic", false, trafficRouteSub(id));
    }
    syncPageIntro();
  }

  function initTrafficHubSubnav() {
    const nav = $("trafficHubSubnav");
    if (!nav || nav.dataset.rendered) return;
    nav.dataset.rendered = "1";
    Object.entries(TRAFFIC_HUB_TABS).forEach(([id, cfg]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hub-subnav-btn";
      btn.setAttribute("data-traffic-hub-tab", id);
      btn.textContent = cfg.label;
      btn.title = cfg.title;
      btn.addEventListener("click", () => switchTrafficHubTab(id));
      nav.appendChild(btn);
    });
    syncTrafficHubTabHighlight(trafficHubTab);
  }

  function syncDoctorsHubTabHighlight(tabId) {
    $("doctorsHubSubnav")?.querySelectorAll("[data-doctors-hub-tab]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-doctors-hub-tab") === tabId);
    });
  }

  function switchDoctorsHubTab(tabId, opts = {}) {
    let id = tabId === "health" ? "overview" : (DOCTORS_HUB_TABS[tabId] ? tabId : "overview");
    if (id === "nordvpn") id = "overview";
    doctorsHubTab = id;
    localStorage.setItem("nordctl_doctors_hub_tab", id);
    syncDoctorsHubTabHighlight(id);
    switchPageTabs("doctors", id, { skipHash: true });
    if (id === "net") loadDoctorsHub(true, false);
    else if (id === "overview" || DOCTOR_TAB_GROUPS[id] !== undefined) loadDoctorReport();
    if (!opts.skipHash && getActiveView() === "doctors") {
      syncRouteHash("network", "doctors", false, doctorsRouteSub(id));
    }
    syncPageIntro();
  }

  function initDoctorsHubSubnav() {
    const nav = $("doctorsHubSubnav");
    if (!nav || nav.dataset.rendered) return;
    nav.dataset.rendered = "1";
    Object.entries(DOCTORS_HUB_TABS).forEach(([id, cfg]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hub-subnav-btn";
      btn.setAttribute("data-doctors-hub-tab", id);
      btn.textContent = cfg.label;
      btn.title = cfg.title;
      btn.addEventListener("click", () => switchDoctorsHubTab(id));
      nav.appendChild(btn);
    });
    syncDoctorsHubTabHighlight(doctorsHubTab);
  }

  function switchWifiHubTab(tabId, opts = {}) {
    const mapped = WIFI_LEGACY_SUB[tabId] || tabId;
    const id = WIFI_HUB_TABS[mapped] ? mapped : "profiles";
    wifiHubTab = id;
    wifiTab = id;
    localStorage.setItem("nordctl_wifi_hub_tab", id);
    localStorage.setItem(WIFI_TAB_KEY, id);
    syncWifiHubTabHighlight(id);
    switchPageTabs("wifi", id, { skipHash: true });
    if (!opts.skipHash && getActiveView() === "wifi") {
      syncRouteHash("network", "wifi", false, wifiRouteSub(id));
    }
    syncPageIntro();
  }

  function initWifiHubSubnav() {
    const nav = $("wifiHubSubnav");
    if (!nav || nav.dataset.rendered) return;
    nav.dataset.rendered = "1";
    Object.entries(WIFI_HUB_TABS).forEach(([id, cfg]) => {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "hub-subnav-btn";
      btn.setAttribute("data-wifi-hub-tab", id);
      btn.textContent = cfg.label;
      btn.title = cfg.title;
      btn.addEventListener("click", () => switchWifiHubTab(id));
      nav.appendChild(btn);
    });
    syncWifiHubTabHighlight(wifiHubTab);
  }

  function updateInstallToolsHeader(data) {
    updatePackageHubHeader(data, "network");
    updatePackageHubHeader(data, "security");
  }

  function setInstallToolsFilter(hub, filterId) {
    if (!["network", "security", "custom"].includes(hub)) return;
    installToolsFilter[hub] = filterId;
    localStorage.setItem(`${INSTALL_TOOLS_FILTER_KEY}_${hub}`, filterId);
    installToolsSelected[hub].clear();
    if (toolsPayloadCache) {
      renderHubToolCards(toolsPayloadCache, hub, installToolsGridId(hub), installToolsHintId(hub));
    }
  }

  function filterInstallToolsRows(rows, hub) {
    const f = installToolsFilter[hub] || "all";
    if (f === "missing") return rows.filter((t) => !t.installed);
    if (f === "installed") return rows.filter((t) => t.installed);
    return rows;
  }

  function selectedInstallToolIds(hub) {
    return [...(installToolsSelected[hub] || new Set())];
  }

  function toggleInstallToolSelect(hub, toolId, checked) {
    if (!installToolsSelected[hub]) installToolsSelected[hub] = new Set();
    if (checked) installToolsSelected[hub].add(toolId);
    else installToolsSelected[hub].delete(toolId);
  }

  function selectVisibleInstallTools(hub, rows, mode) {
    if (!installToolsSelected[hub]) installToolsSelected[hub] = new Set();
    rows.forEach((t) => {
      if (mode === "missing" && !t.installed) installToolsSelected[hub].add(t.id);
      else if (mode === "installed" && t.installed && (!t.custom || hub === "custom")) installToolsSelected[hub].add(t.id);
      else if (mode === "all") installToolsSelected[hub].add(t.id);
    });
  }

  function renderToolWhereHint(t) {
    const rw = t.run_where || {};
    if (!rw.label) return "";
    const jump = rw.route
      ? ` <button type="button" class="btn sm jump-link tool-where-jump" data-view-jump="${esc(rw.route)}">Open →</button>`
      : "";
    return `<p class="tool-where-hint"><strong>Run from:</strong> ${esc(rw.label)}${jump}</p>`;
  }

  function renderInstallToolsResult(res, hub, mode) {
    const boxId = INSTALL_TOOLS_RESULT_BOXES[hub];
    const box = boxId ? $(boxId) : null;
    if (!box) return;
    if (!res) {
      box.classList.add("hidden");
      box.innerHTML = "";
      return;
    }
    const installed = res.installed || [];
    const removed = res.removed || [];
    const failed = res.failed || [];
    const ok = res.ok && !res.partial;
    const partial = !!res.partial;
    const cls = ok ? "ok" : (partial ? "warn" : "err");
    const title = mode === "uninstall"
      ? (ok ? "Uninstall complete" : (partial ? "Uninstall partly complete" : "Uninstall failed"))
      : (ok ? "Install complete" : (partial ? "Install partly complete" : "Install failed"));
    const lines = [];
    if (res.message) lines.push(`<p class="install-result-lead">${esc(res.message)}</p>`);
    if (res.fixes_applied?.length) {
      lines.push(`<p class="help-text muted-inline">Auto-fix applied: ${esc(res.fixes_applied.join(", "))}</p>`);
    }
    const successRows = mode === "uninstall" ? removed : installed;
    if (successRows.length) {
      lines.push(`<ul class="install-result-list">${successRows.map((t) => {
        const rw = t.run_where || {};
        const jump = rw.route && mode !== "uninstall"
          ? ` — <button type="button" class="btn sm jump-link" data-view-jump="${esc(rw.route)}">${esc(rw.label || "Open")}</button>`
          : (rw.label && mode !== "uninstall" ? ` — ${esc(rw.label)}` : "");
        const runScope = hub === "custom"
          ? ` data-run-scope="${esc(customPackageTermScope((rw.route || "").split("/").pop() || customPackagesCategory))}"`
          : "";
        const run = t.run_label && mode !== "uninstall"
          ? ` <button type="button" class="btn sm term-run-tool" data-run-cmd="${esc(t.run_cmd || "")}" data-run-label="${esc(t.run_label)}"${runScope}>${esc(t.run_label)}</button>`
          : "";
        return `<li><strong>${esc(t.label)}</strong>${jump}${run}</li>`;
      }).join("")}</ul>`);
    }
    if (failed.length) {
      lines.push(`<p class="install-result-fail"><strong>Still missing or failed:</strong> ${esc(failed.map((t) => t.label).join(", "))}</p>`);
    }
    if (res.hints?.length) {
      lines.push(`<ul class="compact-help-list">${res.hints.map((h) => `<li>${esc(h)}</li>`).join("")}</ul>`);
    }
    if (res.retry_cmd && !ok) {
      lines.push(`<div class="actions"><button type="button" class="btn sm primary" data-install-retry-cmd="${esc(res.retry_cmd)}">Retry in Shell</button>`);
      lines.push(`<button type="button" class="btn sm" data-copy-install-cmd="${esc(res.retry_cmd)}" data-copy-label="Retry install">Copy fix command</button></div>`);
    } else if (res.manual && !ok && toolsPayloadCache?.can_install_terminal) {
      lines.push(`<div class="actions"><button type="button" class="btn sm primary" data-install-retry-cmd="${esc(res.manual)}">Run in Shell</button></div>`);
    }
    if (res.output && !ok) {
      lines.push(`<pre class="mono install-result-output">${esc(String(res.output).slice(-2500))}</pre>`);
    }
    if (mode === "install") {
      lines.push(
        `<div class="actions install-result-footer"><button type="button" class="btn sm primary jump-link" data-view-jump="${esc(installToolsPackagesRoute(hub, customPackagesCategory))}">Back to packages</button></div>`
      );
    }
    box.className = `install-tools-result glass install-result-${cls}`;
    box.innerHTML = `<div class="install-result-head"><strong>${esc(title)}</strong><button type="button" class="btn sm" data-dismiss-install-result>Dismiss</button></div>${lines.join("")}`;
    box.querySelector("[data-dismiss-install-result]")?.addEventListener("click", () => renderInstallToolsResult(null, hub, mode));
    box.querySelectorAll(".term-run-tool").forEach((b) => {
      b.addEventListener("click", () => termRunCommand(
        b.dataset.runCmd || "",
        b.dataset.runLabel || b.textContent.trim(),
        {
          scope: termRunScopeFromButton(b, hub, null),
          scrollToTerminal: hub !== "custom",
        },
      ));
    });
    box.querySelectorAll("[data-install-retry-cmd]").forEach((b) => {
      b.addEventListener("click", () => installToolInTerminal(b.dataset.installRetryCmd, "Fix apt install", { hub, category: customPackagesCategory }));
    });
    box.querySelectorAll("[data-copy-install-cmd]").forEach((b) => {
      b.addEventListener("click", () => copyToolCommand(b.dataset.copyInstallCmd, b.dataset.copyLabel));
    });
    bindViewJumps(box);
  }

  function renderInstallToolsToolbar(hub, group, data) {
    const el = $(INSTALL_TOOLS_TOOLBARS[hub]);
    if (!el) return;
    const missing = group?.missing_count || 0;
    const installed = group?.installed_count || 0;
    const total = group?.total || 0;
    const filter = installToolsFilter[hub] || "all";
    const selected = selectedInstallToolIds(hub);
    const selMissing = selected.filter((id) => !(group?.tools || []).find((t) => t.id === id)?.installed);
    const selInstalled = selected.filter((id) => (group?.tools || []).find((t) => t.id === id)?.installed);
    const filterBtns = INSTALL_TOOLS_FILTER_OPTS.map((o) =>
      `<button type="button" class="btn sm install-filter-btn${filter === o.id ? " primary" : ""}" data-install-filter="${esc(hub)}" data-filter-id="${esc(o.id)}">${esc(o.label)}</button>`
    ).join("");
    let bulkLabel = "Install all missing";
    if (missing) {
      if (!data?.can_install && data?.can_install_terminal) bulkLabel = "Install all in Shell";
      else if (!data?.can_install) bulkLabel = "Copy all commands";
    } else bulkLabel = "All installed";
    el.innerHTML = [
      `<div class="install-tools-toolbar-inner">`,
      `<div class="install-tools-toolbar-row">`,
      `<span class="install-tab-stat muted">${esc(installed)}/${esc(total)} installed · ${esc(missing)} missing</span>`,
      `<div class="install-filter-group" role="group" aria-label="Show">${filterBtns}</div>`,
      `</div>`,
      `<div class="install-tools-toolbar-row install-tools-batch-row">`,
      `<span class="muted-inline install-sel-count">${selected.length ? `${selected.length} selected` : "Select packages below"}</span>`,
      `<div class="actions">`,
      `<button type="button" class="btn sm" data-select-visible="${esc(hub)}" data-select-mode="missing" title="Select all not-installed packages visible in the list">Select missing</button>`,
      `<button type="button" class="btn sm" data-select-visible="${esc(hub)}" data-select-mode="installed" title="Select installed packages for batch uninstall">Select installed</button>`,
      `<button type="button" class="btn sm" data-clear-selection="${esc(hub)}">Clear</button>`,
      `<button type="button" class="btn sm primary" data-batch-install="${esc(hub)}"${selMissing.length ? "" : " disabled"} title="Install checked packages in one apt run">Install selected (${selMissing.length})</button>`,
      `<button type="button" class="btn sm" data-batch-uninstall="${esc(hub)}"${selInstalled.length ? "" : " disabled"} title="Remove checked packages">Uninstall selected (${selInstalled.length})</button>`,
      `<button type="button" class="btn sm" data-install-all-hub="${esc(hub)}"${missing ? "" : " disabled"} title="Install every missing package in this tab">${esc(bulkLabel)}${missing ? ` (${missing})` : ""}</button>`,
      `</div>`,
      `</div>`,
      `</div>`,
    ].join("");
    el.querySelectorAll("[data-install-filter]").forEach((b) => {
      b.addEventListener("click", () => setInstallToolsFilter(b.dataset.installFilter, b.dataset.filterId));
    });
    el.querySelectorAll("[data-select-visible]").forEach((b) => {
      b.addEventListener("click", () => {
        const visible = filterInstallToolsRows(group?.tools || [], hub);
        selectVisibleInstallTools(hub, visible, b.dataset.selectMode);
        renderHubToolCards(data, hub, installToolsGridId(hub), installToolsHintId(hub));
      });
    });
    el.querySelector(`[data-clear-selection="${hub}"]`)?.addEventListener("click", () => {
      installToolsSelected[hub].clear();
      renderHubToolCards(data, hub, installToolsGridId(hub), installToolsHintId(hub));
    });
    el.querySelector(`[data-batch-install="${hub}"]`)?.addEventListener("click", () => installBatchSelected(hub));
    el.querySelector(`[data-batch-uninstall="${hub}"]`)?.addEventListener("click", () => uninstallBatchSelected(hub));
    el.querySelector("[data-install-all-hub]")?.addEventListener("click", () => installAllHubTools(hub));
  }

  function renderToolInstallButton(t, data) {
    if (t.installed) return "";
    const cmd = t.install_cmd || "";
    if (data?.can_install) {
      return `<button type="button" class="btn sm primary" data-install-tool-api="${esc(t.id)}" data-confirm-message="Install ${esc(t.label)}?&#10;&#10;Used for: ${esc(t.used_by || t.description)}&#10;&#10;Command: ${esc(t.install_cmd)}&#10;&#10;This may take a few minutes.">Install</button>`;
    }
    if (data?.can_install_terminal) {
      return `<button type="button" class="btn sm primary" data-install-tool-terminal="${esc(cmd)}" data-install-label="${esc(t.label)}" title="Opens Terminal and runs apt — enter your sudo password when asked">Install in terminal</button>`;
    }
    return `<button type="button" class="btn sm" data-copy-install-cmd="${esc(cmd)}" data-copy-label="${esc(t.label)}" title="Copy apt command to clipboard">Copy install command</button>`;
  }

  function renderToolRemoveButton(t, data) {
    if (!t.custom && !t.installed) return "";
    const removeLabel = t.custom ? "Remove" : (data?.can_install ? "Uninstall" : "Uninstall in terminal");
    const removeMsg = t.custom
      ? `Remove ${t.label} from your custom list? (Does not uninstall the apt package.)`
      : `Uninstall ${t.label} from the system?&#10;&#10;Command: sudo apt remove -y ${(t.packages || []).join(" ")}&#10;&#10;nordctl may show it as missing again.`;
    if (t.custom) {
      return `<button type="button" class="btn sm" data-uninstall-tool="${esc(t.id)}" data-custom-tool="1" data-confirm-message="${esc(removeMsg)}">${removeLabel}</button>`;
    }
    if (data?.can_install) {
      return `<button type="button" class="btn sm" data-uninstall-tool="${esc(t.id)}" data-confirm-message="${esc(removeMsg)}">${removeLabel}</button>`;
    }
    if (data?.can_install_terminal) {
      return `<button type="button" class="btn sm" data-uninstall-tool-terminal="${esc(t.id)}" data-confirm-message="${esc(removeMsg)}">${removeLabel}</button>`;
    }
    return `<button type="button" class="btn sm" data-copy-remove-tool="${esc(t.id)}">${removeLabel.replace(" in terminal", "")} command</button>`;
  }

  function customPackageTermScope(category) {
    return `custom:${category || customPackagesCategory || "miscellaneous"}`;
  }

  function termRunScopeFromButton(btn, hub, tool) {
    if (btn?.dataset?.runScope) return btn.dataset.runScope;
    if (hub === "custom") return customPackageTermScope(tool?.category);
    return hub;
  }

  function renderToolRunButtons(t, hub) {
    if (!t.installed) return "";
    const runScope = hub === "custom"
      ? ` data-run-scope="${esc(customPackageTermScope(t.category))}"`
      : "";
    const parts = [];
    if (t.run_cmd) {
      parts.push(
        `<button type="button" class="btn sm primary term-run-tool" data-run-cmd="${esc(t.run_cmd)}" data-run-label="${esc(t.run_label || t.label || "Tool")}" title="${esc(t.run_cmd)}"${runScope}>${esc(t.run_label || "Run program")}</button>`,
      );
    }
    if (t.help_cmd && t.help_cmd !== t.run_cmd) {
      parts.push(
        `<button type="button" class="btn sm term-run-tool" data-run-cmd="${esc(t.help_cmd)}" data-run-label="${esc(t.help_label || "Run help")}" title="${esc(t.help_cmd)}"${runScope}>${esc(t.help_label || "Run help")}</button>`,
      );
    }
    return parts.join(" ");
  }

  const BUILTIN_PACKAGE_CATEGORY_IDS = new Set(["recommended", "my-packages"]);
  const BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS = new Set(["miscellaneous"]);

  function isCustomPackageCategoryDeletable(cat) {
    if (!cat?.id) return false;
    if (typeof cat.deletable === "boolean") return cat.deletable;
    return !BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS.has(String(cat.id));
  }

  function packageCategoryNavLabel(sec) {
    const total = sec.total || 0;
    const missing = sec.missing_count || 0;
    const miss = missing ? ` · ${missing} missing` : "";
    return `${esc(sec.label)} <span class="muted">(${total}${miss})</span>`;
  }

  function packageCategorySectionHead(sec, localCount) {
    return `${esc(sec.label)} <span class="muted">(${localCount})</span>`;
  }

  function packageCategoryEmptyMessage(hub, catFilter, sections) {
    const sec = sections.find((s) => s.id === catFilter);
    const catLabel = sec?.label || catFilter;
    if (installToolsFilter[hub] === "missing") return "All packages in this category are already installed — switch <strong>Show</strong> to All or Installed.";
    if (installToolsFilter[hub] === "installed") return "No installed packages match this filter — switch <strong>Show</strong> to All or Missing.";
    if (hub === "custom") {
      return `No packages in <strong>${esc(catLabel)}</strong> yet — add one with the form below.`;
    }
    return "No packages in this category.";
  }

  function packageCategoryToolsForDisplay(sec, hub) {
    if (!sec) return [];
    return (sec.tools || []).map((t) => ({ ...t, _pkgHub: hub }));
  }

  function renderPackageCategoryNav(hub, group, data) {
    if (hub === "custom") return;
    const nav = $(hub === "security" ? "securityPackageCategoryNav" : "networkPackageCategoryNav");
    if (!nav) return;
    const sections = group?.categories || [];
    const active = resolvePackageCategoryFilter(hub, sections);
    const btns = [
      `<button type="button" class="btn sm package-cat-btn${active === "all" ? " primary" : ""}" data-package-cat="${esc(hub)}" data-cat-id="all">All</button>`,
    ];
    sections.forEach((sec) => {
      btns.push(
        `<button type="button" class="btn sm package-cat-btn${active === sec.id ? " primary" : ""}" data-package-cat="${esc(hub)}" data-cat-id="${esc(sec.id)}">${packageCategoryNavLabel(sec)}</button>`
      );
    });
    nav.innerHTML = btns.join("");
    nav.querySelectorAll("[data-package-cat]").forEach((btn) => {
      btn.addEventListener("click", () => {
        setPackageCategoryFilter(btn.dataset.packageCat, btn.dataset.catId);
        renderHubToolCards(
          data,
          hub,
          hub === "network" ? "networkToolsGrid" : "secToolsGrid",
          hub === "network" ? "networkToolsHint" : "secToolsHint",
        );
        if (btn.dataset.catId && btn.dataset.catId !== "all") {
          document.getElementById(`pkg-cat-${hub}-${btn.dataset.catId}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      });
    });
  }

  function installToolsGridId(hub) {
    if (hub === "security") return "secToolsGrid";
    if (hub === "custom") return "customPackagesGrid";
    return "networkToolsGrid";
  }

  function installToolsHintId(hub) {
    if (hub === "security") return "secToolsHint";
    if (hub === "custom") return "customToolsHint";
    return "networkToolsHint";
  }

  function customPackagesPageActive() {
    return getActiveView() === "customPackages" && toolsTab === "custom-packages";
  }

  function renderOptionalToolCard(t, data, hub, categories) {
    const cardHub = t._pkgHub || hub;
    const installBtn = renderToolInstallButton(t, data);
    const statusBadge = t.installed
      ? `<span class="badge on" title="Ready to use">Installed</span>`
      : `<span class="badge off" title="Not installed yet">Not installed</span>`;
    const runBtns = renderToolRunButtons(t, cardHub);
    const removeBtn = renderToolRemoveButton(t, data);
    const whereHint = t.installed ? renderToolWhereHint(t) : "";
    const batchHub = cardHub === "network" || cardHub === "security" || cardHub === "custom";
    const checked = batchHub && installToolsSelected[cardHub]?.has(t.id) ? " checked" : "";
    const pick = batchHub
      ? `<label class="tool-pick"><input type="checkbox" class="tool-pick-cb" data-tool-pick="${esc(cardHub)}" data-tool-id="${esc(t.id)}"${checked} /><span class="tool-pick-label">Select</span></label>`
      : "";
    const customBadge = t.custom ? '<span class="badge">Custom</span>' : "";
    let moveCat = "";
    if (t.custom && categories?.length) {
      const opts = categories.map((c) =>
        `<option value="${esc(c.id)}"${c.id === t.category ? " selected" : ""}>${esc(c.label)}</option>`
      ).join("");
      moveCat = `<label class="tool-cat-move">Move to category: <select data-move-tool-cat="${esc(t.id)}" data-move-hub="${esc(cardHub)}">${opts}</select></label>`;
    }
    return `<div class="optional-tool-card ${t.installed ? "installed" : "missing"}" data-tool-id="${esc(t.id)}">${pick}<div class="optional-tool-card-body"><h4>${esc(t.label)} ${customBadge}</h4>${statusBadge}<p class="tool-used-by"><strong>Used for:</strong> ${esc(t.used_by || "—")}</p><p class="muted">${esc(t.description)}</p>${whereHint}${moveCat}<p class="mono muted tool-cmd">${esc(t.install_cmd)}</p><div class="actions">${installBtn}${runBtns ? ` ${runBtns}` : ""}${removeBtn ? ` ${removeBtn}` : ""}</div></div></div>`;
  }

  function bindOptionalToolGrid(grid, data, hub, group) {
    grid.querySelectorAll(".tool-pick-cb").forEach((cb) => {
      cb.addEventListener("change", () => {
        toggleInstallToolSelect(cb.dataset.toolPick, cb.dataset.toolId, cb.checked);
        renderInstallToolsToolbar(hub, group, data);
      });
    });
    grid.querySelectorAll("[data-install-tool-api]").forEach((b) => {
      b.addEventListener("click", () => {
        const card = b.closest(".optional-tool-card");
        const toolId = card?.dataset?.toolId;
        const tool = toolId ? (data?.tools || []).find((t) => t.id === toolId) : null;
        const lbl = card?.querySelector("h4")?.textContent || b.dataset.installToolApi;
        installOptionalTool(b.dataset.installToolApi, lbl, {
          hub,
          category: tool?.category || customPackagesCategory,
        });
      });
    });
    grid.querySelectorAll("[data-install-tool-terminal]").forEach((b) => {
      b.addEventListener("click", () => {
        const card = b.closest(".optional-tool-card");
        const toolId = card?.dataset?.toolId;
        const tool = toolId ? (data?.tools || []).find((t) => t.id === toolId) : null;
        installToolInTerminal(b.dataset.installToolTerminal, b.dataset.installLabel || b.textContent.trim(), {
          hub,
          category: tool?.category || customPackagesCategory,
        });
      });
    });
    grid.querySelectorAll("[data-copy-install-cmd]").forEach((b) => {
      b.addEventListener("click", () => copyToolCommand(b.dataset.copyInstallCmd, b.dataset.copyLabel));
    });
    grid.querySelectorAll(".term-run-tool").forEach((b) => {
      const card = b.closest(".optional-tool-card");
      const toolId = card?.dataset?.toolId;
      const tool = toolId ? (data?.tools || []).find((t) => t.id === toolId) : null;
      b.addEventListener("click", () => termRunCommand(
        b.dataset.runCmd || "",
        b.dataset.runLabel || b.textContent.trim(),
        {
          scope: termRunScopeFromButton(b, hub, tool),
          scrollToTerminal: hub !== "custom",
        },
      ));
    });
    grid.querySelectorAll("[data-uninstall-tool]").forEach((b) => {
      b.addEventListener("click", () => {
        const card = b.closest(".optional-tool-card");
        const lbl = card?.querySelector("h4")?.textContent || b.dataset.uninstallTool;
        uninstallOptionalTool(b.dataset.uninstallTool, lbl, { custom: !!b.dataset.customTool });
      });
    });
    grid.querySelectorAll("[data-uninstall-tool-terminal]").forEach((b) => {
      b.addEventListener("click", () => {
        const row = data?.tools?.find((t) => t.id === b.dataset.uninstallToolTerminal);
        const lbl = row?.label || b.dataset.uninstallToolTerminal;
        uninstallOptionalTool(b.dataset.uninstallToolTerminal, lbl);
      });
    });
    grid.querySelectorAll("[data-copy-remove-tool]").forEach((b) => {
      b.addEventListener("click", () => {
        const row = data?.tools?.find((t) => t.id === b.dataset.copyRemoveTool);
        if (row?.packages?.length) copyToolCommand(`sudo apt remove -y ${row.packages.join(" ")}`, row.label);
      });
    });
    grid.querySelectorAll("[data-move-tool-cat]").forEach((sel) => {
      sel.addEventListener("change", () => moveCustomToolCategory(sel.dataset.moveToolCat, sel.value, sel.dataset.moveHub));
    });
    bindViewJumps(grid);
  }

  function packageHubPageActive(pageId) {
    const advPage = localStorage.getItem("nordctl_adv_tab") || "";
    return hubTab === pageId || advPage === pageId;
  }

  function renderHubToolCards(data, hub, gridId, hintId) {
    const group = data?.groups?.[hub];
    renderInstallToolsToolbar(hub, group, data);
    renderPackageCategoryNav(hub, group, data);
    const hint = hintId ? $(hintId) : null;
    const grid = $(gridId);
    const onPackageTab = hub === "custom"
      ? customPackagesPageActive()
      : (hub === "security"
        ? packageHubPageActive("security-packages")
        : packageHubPageActive("network-packages"));
    if (hint && onPackageTab) hint.textContent = data?.install_hint || "";
    const optNoteId = hub === "security" ? "securityPackagesOptionalNote" : "networkPackagesOptionalNote";
    const optNote = $(optNoteId);
    if (optNote && onPackageTab && data?.optional_note) optNote.textContent = data.optional_note;
    if (!grid) return;
    const categories = group?.categories?.length
      ? group.categories
      : (group?.tools?.length
        ? [{
            id: "recommended",
            label: "Recommended packages",
            tools: group.tools,
            total: group.tools.length,
            missing_count: group.missing_count || 0,
          }]
        : []);
    const catFilter = resolvePackageCategoryFilter(hub, categories);
    const sections = catFilter === "all"
      ? categories
      : categories.filter((s) => s.id === catFilter);
    let html = "";
    sections.forEach((sec) => {
      let rows = packageCategoryToolsForDisplay(sec, hub);
      rows = filterInstallToolsRows(rows, hub);
      if (!rows.length && catFilter !== "all") {
        html += `<section class="package-category-section" id="pkg-cat-${esc(hub)}-${esc(sec.id)}">`;
        html += `<h3 class="package-category-head">${packageCategorySectionHead(sec, 0)}</h3>`;
        html += `<p class="muted package-category-empty">${packageCategoryEmptyMessage(hub, catFilter, categories)}</p>`;
        html += "</section>";
        return;
      }
      if (!rows.length && catFilter === "all") return;
      html += `<section class="package-category-section" id="pkg-cat-${esc(hub)}-${esc(sec.id)}">`;
      html += `<h3 class="package-category-head">${packageCategorySectionHead(sec, rows.length)}</h3>`;
      html += `<div class="optional-tools-grid package-category-grid">${rows.map((t) => renderOptionalToolCard(t, data, t._pkgHub || hub, categories)).join("")}</div>`;
      html += "</section>";
    });
    if (!html) {
      html = `<p class="muted">${catFilter !== "all"
        ? packageCategoryEmptyMessage(hub, catFilter, categories)
        : (installToolsFilter[hub] === "missing"
          ? "All packages in this view are installed."
          : (installToolsFilter[hub] === "installed"
            ? "No installed packages match this filter."
            : "No packages in this category."))}</p>`;
    }
    grid.innerHTML = html;
    bindOptionalToolGrid(grid, data, hub, group);
  }

  async function moveCustomToolCategory(toolId, category, hub) {
    if (!toolId || !category) return;
    setBusy(true);
    try {
      const res = await api("/api/tools/custom", {
        method: "POST",
        body: JSON.stringify({ action: "move", tool: toolId, category }),
      });
      toast(res.note || res.error || (res.ok ? "Package moved" : "Move failed"), res.ok);
      if (res.ok) {
        toolsPayloadCache = res.tools || null;
        renderAllHubToolCards(toolsPayloadCache);
        setPackageCategoryFilter(hub, category);
      }
    } finally {
      setBusy(false);
    }
  }

  async function removePackageCategory(categoryId) {
    const cid = (categoryId || "").trim();
    if (!cid) return;
    setBusy(true);
    try {
      const res = await api("/api/tools/categories", {
        method: "POST",
        body: JSON.stringify({ action: "remove", id: cid }),
      });
      toast(res.note || res.error || (res.ok ? "Category deleted" : "Delete failed"), res.ok);
      if (res.ok) {
        toolsPayloadCache = res.tools || null;
        const cats = toolsPayloadCache?.groups?.custom?.categories || [];
        customPackagesCategory = cats[0]?.id || "miscellaneous";
        localStorage.setItem("nordctl_custom_packages_cat", customPackagesCategory);
        setPackageCategoryFilter("custom", customPackagesCategory);
        renderAllHubToolCards(toolsPayloadCache);
        await loadCustomPackages(true);
      }
    } finally {
      setBusy(false);
    }
  }

  async function addPackageCategory(label) {
    label = (label || "").trim();
    if (!label) {
      toast("Enter a category name", false);
      return;
    }
    setBusy(true);
    try {
      const res = await api("/api/tools/categories", {
        method: "POST",
        body: JSON.stringify({ label }),
      });
      toast(res.note || res.error || (res.ok ? "Category created" : "Failed"), res.ok);
      if (res.ok) {
        toolsPayloadCache = res.tools || null;
        if (res.category?.id) {
          customPackagesCategory = res.category.id;
          localStorage.setItem("nordctl_custom_packages_cat", customPackagesCategory);
          setPackageCategoryFilter("custom", res.category.id);
        }
        renderAllHubToolCards(toolsPayloadCache);
        await loadCustomPackages(true);
        if ($("customPackagesCategoryNew")) $("customPackagesCategoryNew").value = "";
      }
    } finally {
      setBusy(false);
    }
  }

  async function addCustomPackageFromForm() {
    const label = ($("customPackagesToolLabel")?.value || "").trim();
    const pkg = ($("customPackagesToolPackage")?.value || "").trim();
    const usedBy = ($("customPackagesToolUsedBy")?.value || "").trim();
    if (!label || !pkg) {
      toast("Label and apt package are required", false);
      return;
    }
    setBusy(true);
    try {
      let category = $("customPackagesToolCategory")?.value || customPackagesCategory || "miscellaneous";
      const newCat = ($("customPackagesCategoryNew")?.value || "").trim();
      if (newCat) {
        const catRes = await api("/api/tools/categories", {
          method: "POST",
          body: JSON.stringify({ label: newCat }),
        });
        if (!catRes.ok) {
          toast(catRes.error || "Could not create category", false);
          return;
        }
        category = catRes.category?.id || category;
        toolsPayloadCache = catRes.tools || toolsPayloadCache;
        customPackagesCategory = category;
        localStorage.setItem("nordctl_custom_packages_cat", category);
      }
      const res = await api("/api/tools/custom", {
        method: "POST",
        body: JSON.stringify({
          label,
          packages: pkg,
          used_by: usedBy || undefined,
          category,
        }),
      });
      toast(res.error || (res.ok ? "Package added" : "Failed"), res.ok);
      if (res.ok) {
        toolsPayloadCache = res.tools || null;
        setPackageCategoryFilter("custom", category);
        await loadCustomPackages(true);
        if ($("customPackagesToolLabel")) $("customPackagesToolLabel").value = "";
        if ($("customPackagesToolPackage")) $("customPackagesToolPackage").value = "";
        if ($("customPackagesToolUsedBy")) $("customPackagesToolUsedBy").value = "";
        if ($("customPackagesCategoryNew")) $("customPackagesCategoryNew").value = "";
      }
    } finally {
      setBusy(false);
    }
  }

  async function removeCustomTool(toolId) {
    await uninstallOptionalTool(toolId, toolId, { custom: true });
  }

  function renderAllHubToolCards(data) {
    if (!data) return;
    updateInstallToolsHeader(data);
    renderHubToolCards(data, "network", "networkToolsGrid", "networkToolsHint");
    renderHubToolCards(data, "security", "secToolsGrid", "secToolsHint");
    if (customPackagesPageActive()) {
      populateCustomPackagesCategorySelect(data);
      renderHubToolCards(data, "custom", "customPackagesGrid", "customToolsHint");
    }
  }

  async function loadHubTools(hubFilter, force) {
    try {
      if (!force && toolsPayloadCache) {
        renderAllHubToolCards(toolsPayloadCache);
        return toolsPayloadCache;
      }
      const data = await apiCached("/api/tools", {}, force ? 0 : CACHE_TTL.tools);
      toolsPayloadCache = data;
      renderAllHubToolCards(data);
      return data;
    } catch (e) {
      reportActionError("Tools list unavailable", e, "Loading installable tools");
      $("networkToolsGrid") && ($("networkToolsGrid").innerHTML = '<p class="muted">Could not load networking tools list.</p>');
      $("secToolsGrid") && ($("secToolsGrid").innerHTML = '<p class="muted">Could not load security tools list.</p>');
      return null;
    }
  }

  function renderAutomateGuide(data) {
    const grid = $("automateGuideGrid");
    if (!grid) return;
    const lead = $("automateGuideLead");
    const badge = $("automateGuideBadge");
    const actions = $("automateGuideActions");
    const bl = data?.baseline || {};
    const schedN = (data?.schedules || []).length;
    const snapN = (data?.snapshots || []).length;
    if (lead) {
      lead.textContent = bl.exists
        ? "History, undo, and automation. Your first-run install baseline is saved — use Rollback to revert config, Wi‑Fi DNS, and Nord settings."
        : "History, undo, and automation. Create an install baseline on Rollback before heavy changes.";
    }
    if (badge) {
      badge.textContent = "Full hub";
      badge.className = "badge on";
    }
    if ($("automateGuideMetrics")) {
      $("automateGuideMetrics").innerHTML = [
        `<div class="page-metric page-metric-a"><div class="lbl">Tools</div><div class="val">7</div><div class="sub">Log, editor, undo, auto</div></div>`,
        `<div class="page-metric page-metric-b"><div class="lbl">Baseline</div><div class="val ${bl.exists ? "on" : "warn"}">${bl.exists ? "Ready" : "Missing"}</div><div class="sub">Install rollback</div></div>`,
        `<div class="page-metric page-metric-c"><div class="lbl">Snapshots</div><div class="val">${snapN}</div><div class="sub">Nord undo points</div></div>`,
        `<div class="page-metric page-metric-d"><div class="lbl">Schedules</div><div class="val">${schedN}</div><div class="sub">Daily preset jobs</div></div>`,
      ].join("");
    }
    const cards = [
      { route: "tools/logs", label: "Activity log", desc: "Every action nordctl recorded on this PC", icon: "📋" },
      { route: "tools/editor", label: "Config editor", desc: "Edit config.yaml and preset files", icon: "✎" },
      { route: "tools/rollback", label: "Rollback", desc: "Restore install baseline if config goes wrong", icon: "⏪" },
      { route: "tools/schedules", label: "Schedules", desc: "Run presets at set times", icon: "🕐" },
      { route: "tools/auto-watcher", label: "Zone watcher", desc: "Auto-apply WiFi zone presets", icon: "📡" },
      { route: "tools/snapshots", label: "Nord snapshots", desc: "Quick undo after a preset", icon: "💾" },
      { route: "tools/reset", label: "Factory reset", desc: "Full undo of nordctl changes (keeps NordVPN installed)", icon: "⚠️" },
      { route: "tools/custom-shell", label: "Custom shell", desc: "Your custom quick-command categories", icon: "🛠" },
      { route: "tools/custom-packages", label: "Custom packages", desc: "Your apt packages by category", icon: "📦" },
    ];
    grid.innerHTML = cards.map((c) =>
      `<button type="button" class="tools-welcome-card tools-tool-card" data-view-jump="${esc(c.route)}"><span class="tools-card-icon" aria-hidden="true">${c.icon}</span><strong>${esc(c.label)}</strong><span>${esc(c.desc)}</span></button>`
    ).join("");
    bindViewJumps(grid);
    if (actions) {
      actions.innerHTML = `<button type="button" class="btn sm primary jump-link" data-view-jump="tools/logs">Open activity log</button>
           <button type="button" class="btn sm jump-link" data-view-jump="dashboard/connect">Nord Dashboard → Connect</button>
           <button type="button" class="btn sm jump-link" data-view-jump="network/wifi/zones">WiFi zones</button>`;
      bindViewJumps(actions);
    }
  }

  function renderSchedulesPanel(items) {
    const list = items || [];
    const enabledN = list.filter((s) => s.enabled !== false).length;
    if ($("schedMetricCount")) $("schedMetricCount").textContent = String(list.length);
    if ($("schedMetricEnabled")) {
      $("schedMetricEnabled").textContent = String(enabledN);
      $("schedMetricEnabled").className = "val" + (enabledN ? " on" : "");
    }
    if ($("schedMetricSystemd")) {
      $("schedMetricSystemd").textContent = list.length ? `${list.length} unit${list.length === 1 ? "" : "s"}` : "None";
    }
    if ($("schedMetricNext")) {
      const next = list.find((s) => s.enabled !== false) || list[0];
      $("schedMetricNext").textContent = next ? esc(next.preset) : "—";
    }
    if ($("schedBadge")) {
      $("schedBadge").textContent = list.length ? String(list.length) : "Empty";
      $("schedBadge").className = "badge " + (list.length ? "on" : "off");
    }
    $("scheduleList") && ($("scheduleList").innerHTML = list.map((s) => {
      const on = s.enabled !== false;
      return `<article class="schedule-card ${on ? "schedule-card-on" : "schedule-card-off"}">
        <div class="schedule-card-head"><strong>${esc(s.preset)}</strong><span class="badge ${on ? "on" : "off"}">${esc(s.time)}</span></div>
        <p class="schedule-card-meta">${esc(s.days || "Mon..Sun")} · <code>${esc(s.id)}</code></p>
      </article>`;
    }).join("") || `<div class="page-empty"><strong>No schedules yet</strong>Add a preset id and daily time above, then write systemd units.</div>`);
  }

  async function loadAutomate() {
    const sched = await api("/api/schedules");
    const items = sched.schedules || [];
    renderSchedulesPanel(items);
    if (lastState) renderAutomatePanels(lastState);
    renderAutomateGuide({ ...(lastState || {}), schedules: items });
    renderAutomateNordGates(lastState || {});
    const bl = lastState?.baseline || await api("/api/baseline");
    renderBaselinePanel({ baseline: bl });
    renderFactoryResetPanel({ baseline: bl });
    await loadSettingsPanel();
    applyButtonTitles();
  }

  function fillCountryDropdowns() {
    let loadConnectCities = false;
    ["favCountrySelect", "connectCountrySelect"].forEach((id) => {
      const sel = $(id);
      if (!sel) return;
      const prev = sel.value;
      sel.innerHTML = '<option value="">Pick country…</option>';
      countries.forEach((c) => {
        const o = document.createElement("option");
        o.value = c;
        o.textContent = countryLabel(c);
        sel.appendChild(o);
      });
      if (prev) sel.value = prev;
      else if (id === "connectCountrySelect" && lastState?.connect_country) {
        sel.value = String(lastState.connect_country).replace(/ /g, "_");
        loadConnectCities = true;
      }
    });
    bindFavCountryCity();
    bindConnectCountryCity();
    if (loadConnectCities) loadCityOptions($("connectCountrySelect"), $("connectCitySelect"));
    void populatePresetBuilderCountries();
  }

  async function refreshActiveViewPanels(force) {
    const view = getActiveView();
    const route = parseRouteHash();
    const tasks = [];
    if (view === "lab") {
      const page = localStorage.getItem(DIAGNOSTICS_TAB_KEY) || "leak";
      tasks.push(page === "audit" ? loadAuditDiagnostics(!!force) : loadLab(!!force));
    }
    if (view === "doctors") tasks.push(loadDoctorsHub(true, !!force));
    if (view === "security") tasks.push(loadSecurity(!!force));
    if (view === "wifi") tasks.push(loadWifiHub(true, !!force));
    if (view === "control") tasks.push(loadFirewall(!!force));
    if (view === "advanced") tasks.push(loadAdvanced(!!force));
    if (view === "terminal") tasks.push(loadTerminal(!!force));
    if (view === "editor") {
      tasks.push((async () => {
        await loadFileList();
        if (editor.id) await openFile(editor.id);
      })());
    }
    if (view === "settings") tasks.push(loadSettingsPanel(!!force));
    if (view === "automate") tasks.push(loadAutomate());
    if (view === "logs") tasks.push(loadLogs());
    if (view === "pcInfo") tasks.push(loadPcInfo(!!force));
    if (view === "help") tasks.push(loadHelpFull(!!force));
    if (view === "dashboard") {
      tasks.push(loadNordRoutingPanel(true, !!force));
      if (route.tab === "connection-details" || dashTab === "connection-details") tasks.push(loadConnectionDetails(!!force));
      if (route.tab === "switches" || dashTab === "switches") tasks.push(loadSwitchesPanel(true, !!force));
      if (route.tab === "connect" || dashTab === "connect") tasks.push(loadConnectExtras(!!force));
      if (route.tab === "meshnet" || dashTab === "meshnet") tasks.push(loadMeshnetPage(!!force));
    }
    if (route.section === "dashboard") {
      const dashRouteTab = route.tab || dashTab;
      if (dashRouteTab === "wizard") {
        tasks.push(api("/api/doctor").then(renderDoctor).catch(() => {}));
        tasks.push(loadWizard(!!force).then((w) => {
          renderSetupWizardChecklist(w);
          updateWizardGateButtons();
        }).catch(() => {}));
      } else if (dashRouteTab === "nord-doctor") {
        tasks.push(loadNordDoctor(!!force));
      } else if (dashRouteTab === "nord-services") {
        tasks.push(api("/api/service").then((s) => renderServicePanel(s?.services || s)).catch(() => {}));
      }
    }
    if (route.section === "settings") tasks.push(loadSettingsPanel(!!force));
    if (route.section === "network" && route.tab === "host-ufw") tasks.push(loadFirewall(!!force));
    await Promise.all(tasks.map((p) => Promise.resolve(p).catch(() => {})));
  }

  function mergeStateParts(...parts) {
    return Object.assign({ ok: true }, ...parts.filter(Boolean));
  }

  async function fetchSplitState(force) {
    const ttl = force ? 0 : CACHE_TTL.state;
    const netTtl = force ? 0 : CACHE_TTL.network;
    const fetchPart = (path, partTtl) => (partTtl ? apiCached(path, {}, partTtl) : api(path));
    const [app, nord, network] = await Promise.all([
      fetchPart("/api/state/app", ttl),
      fetchPart("/api/state/nord", ttl),
      fetchPart("/api/state/network", netTtl),
    ]);
    return mergeStateParts(app, nord, network);
  }

  async function loadState(opts = {}) {
    const box = $("statusBox");
    if (box && /^(Loading…|Connecting…|Fetching VPN status…)$/i.test(box.textContent.trim())) {
      box.innerHTML = `<div class="val span3 muted">Fetching VPN status…</div>`;
    }
    let quickDone = false;

    const fetchFullState = async () => {
      const data = await fetchSplitState(!!opts.force);
      await ensureSwitchesMeta(!!opts.force);
      renderState(data);
      return data;
    };

    if (!opts.force && !opts.skipQuick) {
      try {
        const pre = window.__nordctlPreboot;
        const preFresh = pre?.ok && pre._ts && (Date.now() - pre._ts < 15000);
        const quick = preFresh
          ? pre
          : await apiCached("/api/state/quick", {}, CACHE_TTL.stateQuick);
        if (quick?.ok) {
          quickDone = true;
          renderConnectionCore({ ...(lastState || {}), ...quick, presets: quick.presets || lastState?.presets || [] });
          renderDashboardPresetPanels(quick);
          renderQuickStart(quick);
        }
      } catch (_) { /* full state below */ }
    }
    const silent = !!(opts.silent || opts.background);
    try {
      if (quickDone && !opts.force) {
        resetTabLoading();
        await fetchFullState().catch((e) => {
          if (silent) return;
          if (!quickDone) {
            $("statusBox") && ($("statusBox").innerHTML = `<div class="val off span3">${esc(formatFetchError(e, "Loading dashboard"))}</div>`);
            reportActionError("Dashboard unavailable", e, "Loading status");
          }
        });
      } else {
        await fetchFullState();
      }
      stateFetchFailStreak = 0;
    } catch (e) {
      stateFetchFailStreak += 1;
      const loud = !silent && !quickDone;
      const backgroundLoud = silent && stateFetchFailStreak >= 3;
      if (loud || backgroundLoud) {
        $("statusBox") && ($("statusBox").innerHTML = `<div class="val off span3">${esc(formatFetchError(e, "Loading dashboard"))}</div>`);
        reportActionError("Dashboard unavailable", e, "Loading status", { silent: shouldSuppressFetchError() });
      }
    } finally {
      resetTabLoading();
    }
  }

  function bootDashboard() {
    resetTabLoading();
    const watchdog = setTimeout(() => {
      const box = $("statusBox");
      if (!box) return;
      const t = box.textContent.trim();
      if (/^(Loading…|Connecting…|Fetching VPN status…)$/i.test(t)) {
        box.innerHTML = `<div class="val off span3">Still loading — click <strong>Refresh</strong> or wait a few seconds. If this persists, restart: <code>nordctl service restart</code></div>`;
      }
    }, 25000);
    void loadState().catch(() => resetTabLoading()).finally(() => clearTimeout(watchdog));
  }

  let dashboardBootStarted = false;
  function startDashboardBoot() {
    if (dashboardBootStarted) return;
    dashboardBootStarted = true;
    void ensureUiAuth()
      .then((ok) => { if (ok) bootDashboard(); else resetTabLoading(); })
      .catch(() => resetTabLoading());
  }

  initUiDiag();
  initTopbarStackHeight();
  initPageHowUi();
  try { initViewRouting(); } catch (e) {
    console.error("initViewRouting", e);
    pushUiDiag({
      title: "Page routing failed",
      message: String(e?.message || e),
      source: "initViewRouting",
      hint: "Click Reset UI cache (top right) or Ctrl+Shift+R",
    });
  }
  void bootstrapPageHowPrefs();

  // Don't wait for ~400 lines of event bindings — app.js is large and boot was stuck at the end.
  startDashboardBoot();

  async function refreshAll() {
    if (busy) return;
    const btn = $("refreshBtn");
    btn?.classList.add("refreshing");
    setBusy(true);
    showTabLoading(true);
    try {
      invalidateApiCache();
      toolsPayloadCache = null;
      await loadState({ force: true, skipQuick: true });
      await loadHostStatus(true);
      await refreshActiveViewPanels(true);
      await pollBrowserAlerts();
      toast("Refreshed", true);
      logActivity("ui", "Manual refresh", true);
    } catch (e) {
      reportActionError("Refresh failed", e, "Refreshing");
    } finally {
      btn?.classList.remove("refreshing");
      setBusy(false);
      showTabLoading(false);
    }
  }

  async function doAction(body, label) {
    if (busy) return { ok: false, error: "Busy" };
    setBusy(true);
    showMsg("Running…", true);
    try {
      const res = await api("/api/action", {
        method: "POST",
        body: JSON.stringify(body),
        timeoutMs: 120000,
      });
      if (res.state) {
        renderState(res.state);
      } else if (res.wizard) {
        applyWizardActionResult(res);
      } else if (String(body.action || "").startsWith("setup_wizard_")) {
        /* keep wizard open — avoid full reload that dismisses the overlay */
      } else if (res.doctor || res.locations || res.connect_country !== undefined) {
        lastState = {
          ...(lastState || {}),
          ...(res.doctor ? { doctor: res.doctor } : {}),
          ...(res.locations ? { locations: res.locations } : {}),
          ...(res.connect_country !== undefined ? { connect_country: res.connect_country } : {}),
        };
        if (res.doctor) renderDoctor(res.doctor);
        if (res.locations) renderLocationSettings(lastState);
        if (res.connect_country !== undefined) fillCountryDropdowns();
      } else {
        await loadState();
      }
      const msg = res.note || res.human || res.result?.output || (res.ok ? "Done" : res.error || res.hint || "Failed");
      showMsg(msg, res.ok);
      if (!res.ok && res.missing_field) {
        showMissingFieldWizard(res.missing_field, body.preset || res.preset, res.preset_label || label);
      } else if (!res.ok && (res.manual || res.hint)) {
        showNotice(
          [res.error, res.manual, res.hint].filter(Boolean).join("\n\n"),
          { ok: false, title: label || body.action || "Action needed", copyText: res.manual || res.error || msg }
        );
      } else if (res.verification) {
        renderPresetVerification(res.verification);
      }
      logActivity(label || body.action || "action", msg.slice(0, 120), res.ok);
      return res;
    } catch (e) {
      if (body.action === "service_ui" && body.op === "restart" && isFetchUnreachable(e)) {
        suppressFetchErrorsUntil = Date.now() + 45000;
        showMsg("Restarting UI — reconnecting…", true);
        logActivity("service_ui", "restart (connection dropped)", true);
        return { ok: true, scheduled: true, reconnecting: true, note: "Restarting UI…" };
      }
      reportActionError(label || body.action || "Action failed", e, label || "Request");
      showMsg(formatFetchError(e, label || "Action"), false);
      logActivity("error", String(e), false);
      return { ok: false, error: String(e) };
    } finally {
      setBusy(false);
    }
  }

  async function runInstall(dryRun) {
    const log = $("installLog");
    log?.classList.remove("hidden");
    if (log) log.textContent = dryRun ? "Preview…" : "Installing…";
    setBusy(true);
    try {
      const res = await api("/api/install-nordvpn", { method: "POST", body: JSON.stringify({ dry_run: !!dryRun }) });
      if (!dryRun && nordInstallShouldUseTerminal(res)) {
        setBusy(false);
        await runWizardNordInstallInTerminal(res);
        return;
      }
      const lines = [];
      if (res.error) lines.push("ERROR: " + res.error);
      if (res.already_installed) lines.push("NordVPN is already installed.");
      (res.logs || []).forEach((l) => {
        lines.push((l.ok ? "OK" : "FAIL") + ": " + l.cmd);
        if (l.output) lines.push(l.output);
      });
      (res.fix || []).forEach((s) => lines.push("→ " + s));
      (res.next_steps || []).forEach((s) => lines.push("→ " + s));
      if (dryRun && res.shell_script) {
        lines.push("", "# Would run in Nord shell:", res.shell_script.trim());
      }
      if (log) log.textContent = lines.join("\n") || (res.ok ? "Done" : "Failed");
      logActivity("install", dryRun ? "Preview" : (res.ok ? "NordVPN installed" : res.error), res.ok);
      toast(res.ok ? "Install OK" : (res.error || "Failed"), res.ok);
      await loadState();
    } finally { setBusy(false); }
  }

  /* ── Editor ── */
  function setEditorDirty(on) {
    $("editorDirty")?.classList.toggle("hidden", !on);
  }

  function updateGutter(errLine) {
    const ta = $("editorText");
    const gutter = $("editorGutter");
    if (!ta || !gutter) return;
    const lines = ta.value.split("\n").length || 1;
    gutter.innerHTML = Array.from({ length: lines }, (_, i) => {
      const n = i + 1;
      return n === errLine ? `<span class="err-line">${n}</span>` : String(n);
    }).join("\n");
    gutter.scrollTop = ta.scrollTop;
  }

  function showYamlError(line) {
    const bar = $("yamlErrorLine");
    const pill = $("yamlPill");
    if (line && bar) {
      bar.classList.remove("hidden");
      bar.style.top = `${0.75 + (line - 1) * 1.55}rem`;
      pill?.classList.remove("hidden", "ok");
      pill?.classList.add("err");
      if (pill) pill.textContent = `Line ${line}`;
    } else {
      bar?.classList.add("hidden");
      pill?.classList.add("hidden");
    }
    editor.errorLine = line;
    updateGutter(line);
  }

  function scheduleLint() {
    clearTimeout(editor.lintTimer);
    editor.lintTimer = setTimeout(runLiveLint, 400);
  }

  async function runLiveLint() {
    const content = $("editorText")?.value;
    if (content === undefined) return;
    const res = await api("/api/files/validate", {
      method: "POST",
      body: JSON.stringify({ id: editor.id, content }),
    });
    const pill = $("yamlPill");
    if (res.ok) {
      showYamlError(null);
      pill?.classList.remove("hidden", "err");
      pill?.classList.add("ok");
      if (pill) pill.textContent = "YAML OK";
      $("editorStatus").textContent = "Valid";
      $("editorStatus").className = "ok";
    } else {
      const line = res.yaml_line || null;
      showYamlError(line);
      $("editorStatus").textContent = res.yaml_error || res.error || "Invalid";
      $("editorStatus").className = "err";
    }
    if (editor.id !== "config" && !editor.id.startsWith("user/")) return;
  }

  async function initEditorView() {
    await loadFileList();
    if (!editor.savedContent) await openFile("config");
  }

  async function loadFileList() {
    const data = await api("/api/files");
    const box = $("editorFileList");
    if (!box) return;
    box.innerHTML = "";
    (data.groups || []).forEach((g) => {
      const h = document.createElement("div");
      h.className = "file-group-label";
      h.textContent = g.name;
      box.appendChild(h);
      (g.files || []).forEach((f) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "file-item" + (f.id === editor.id ? " active" : "") + (f.readonly ? " readonly" : "");
        btn.innerHTML = `<span>${esc(f.label)}</span>${f.readonly ? "<em>ro</em>" : ""}`;
        btn.addEventListener("click", () => switchFile(f.id));
        box.appendChild(btn);
      });
    });
  }

  async function switchFile(fid) {
    const ta = $("editorText");
    if (ta && ta.value !== editor.savedContent && !confirm("Unsaved changes — switch anyway?")) return;
    await openFile(fid);
  }

  async function openFile(fid) {
    const data = await api("/api/files/read?id=" + encodeURIComponent(fid));
    if (!data.ok) { toast(data.error || "Load failed", false); return; }
    editor.id = fid;
    editor.savedContent = data.content || "";
    editor.readonly = !!data.readonly;
    const ta = $("editorText");
    ta.value = editor.savedContent;
    ta.readOnly = editor.readonly;
    $("editorPath").textContent = data.path || fid;
    $("editorMeta").textContent = `${data.size || 0} B · ${data.readonly ? "read-only" : "editable"}`;
    $("editorSave").disabled = editor.readonly;
    $("editorDeletePreset")?.classList.toggle("hidden", !fid.startsWith("user/") || editor.readonly);
    $("editorRestoreBaseline")?.classList.toggle("hidden", editor.readonly);
    setEditorDirty(false);
    updateGutter(data.yaml_line);
    showYamlError(data.yaml_valid === false ? data.yaml_line : null);
    await loadFileList();
    scheduleLint();
  }

  async function saveEditor() {
    if (editor.readonly) return;
    const content = $("editorText").value;
    const res = await api("/api/files/write", { method: "POST", body: JSON.stringify({ id: editor.id, content }) });
    if (!res.ok) { toast(res.error || "Save failed", false); logActivity("save", res.error, false); return; }
    editor.savedContent = content;
    setEditorDirty(false);
    toast("Saved");
    logActivity("save", editor.id, true);
    scheduleLint();
    if (editor.id === "config") await loadState();
  }

  async function newPreset() {
    const name = prompt("Preset name (e.g. my-stream):", "my-preset");
    if (!name) return;
    const res = await api("/api/files/create", { method: "POST", body: JSON.stringify({ name }) });
    if (!res.ok) return toast(res.error, false);
    toast("Created");
    await loadFileList();
    await openFile(res.id);
  }

  async function restoreInstallBaseline(label) {
    const res = await doAction({ action: "editor_restore_baseline", all: true }, label || "Baseline restore");
    if (res.ok) {
      await loadState(true);
      await loadScenarios(true);
      if (getActiveView() === "editor") {
        await loadFileList();
        if (editor.id) await openFile(editor.id);
      }
    }
    return res;
  }

  /* ── Bindings ── */
  const LEGACY_VIEW_NAV = {
    lab: ["network", "leak-tests"],
    advanced: ["network", "map-internet"],
    control: ["network", "host-ufw"],
    logs: ["network", "tools", "logs"],
    editor: ["network", "tools", "editor"],
    automate: ["network", "tools", "auto-guide"],
  };

  $("btnSettings")?.addEventListener("click", () => {
    const d = defaultSettingsRoute(lastState);
    switchSettingsView(d.scope, d.tab);
  });

  document.querySelectorAll(".nav-pill").forEach((p) => {
    p.addEventListener("click", () => {
      const v = p.getAttribute("data-view");
      if (v === "networking") switchHubPrimaryTab("networking");
      else if (v === "security") switchHubPrimaryTab("security");
      else if (v === "tools") navigateRoute("tools", toolsTab || "auto-guide");
      else if (v === "dashboard") navigateRoute("dashboard", null);
      else if (v === "help") navigateRoute("help");
      else {
        const leg = LEGACY_VIEW_NAV[v];
        if (leg) {
          if (leg[0] === "network" && leg[1] === "tools") navigateRoute("tools", leg[2]);
          else navigateRoute(leg[0], leg[1]);
        } else switchView(v);
      }
    });
  });
  $("btnTheme")?.addEventListener("click", () => {
    const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
    applyTheme(next);
    logActivity("ui", `Theme: ${next}`, true);
  });

  $("btnLogToggle")?.addEventListener("click", () => navigateRoute("tools", "logs"));
  $("btnUiSnapshot")?.addEventListener("click", () => takeFullscreenSnapshot());
  $("btnTermConnect")?.addEventListener("click", () => termConnect(true));
  $("btnTermReconnect")?.addEventListener("click", () => termConnect(true));
  $("btnTermCloseTab")?.addEventListener("click", () => {
    if (activeTermId) termCloseSession(activeTermId);
  });
  $("btnTermCopy")?.addEventListener("click", () => {
    const sess = termGetActive();
    navigator.clipboard?.writeText(sess?.display || "").then(() => toast("Copied terminal output", true));
  });
  $("btnTermClear")?.addEventListener("click", () => {
    const sess = termGetActive();
    if (sess) {
      sess.display = "";
      termRenderActiveScreen();
      termSaveRegistry();
    }
  });
  $("btnTermCrossLink")?.addEventListener("click", () => termJumpOtherTerminal());
  $("btnTermSudoSend")?.addEventListener("click", () => termSubmitSudoPassword());
  $("btnTermSudoCancel")?.addEventListener("click", () => {
    const sess = termGetActive();
    if (sess) sess.expectSudo = false;
    termHideSudoPrompt();
    termSendInput("\x03");
  });
  $("termSudoPass")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      termSubmitSudoPassword();
    }
  });
  $("btnLogsRefresh")?.addEventListener("click", loadLogs);
  $("btnLogsClear")?.addEventListener("click", () => {
    api("/api/logs/clear", { method: "POST" }).then(() => { loadLogs(); toast("Log cleared", true); });
  });
  $("btnLogsExportAll")?.addEventListener("click", exportAllLogEntries);
  $("btnLogsCopy")?.addEventListener("click", () => {
    const text = cachedLogEntries.map((e) => logEntryExportText(e)).join("\n\n---\n\n");
    navigator.clipboard?.writeText(text || "No log entries").then(() => toast("Log copied to clipboard", true));
  });
  $("logsLimitInput")?.addEventListener("change", (e) => {
    setLogsDisplayLimit(e.target.value);
    loadLogs();
  });
  $("logsLimitInput")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      setLogsDisplayLimit(e.target.value);
      loadLogs();
    }
  });
  $("logsLive")?.addEventListener("change", (e) => {
    if (e.target.checked) startLogsLive();
    else stopLogsLive();
  });

  $("refreshBtn")?.addEventListener("click", refreshAll);
  window.addEventListener("resize", positionBellDropdown);
  $("btnReconnect")?.addEventListener("click", () => doAction({ action: "reconnect" }, "Reconnect"));
  $("btnDisconnect")?.addEventListener("click", () => doAction({ action: "disconnect" }, "Disconnect"));
  $("btnConnect")?.addEventListener("click", () => {
    const target = connectConnectTarget();
    if (!target) return toast("Pick a country first", false);
    doAction({ action: "connect", target }, "Connect");
  });
  $("btnInstallNord")?.addEventListener("click", () => runInstall(false));
  $("btnDryRun")?.addEventListener("click", () => runInstall(true));
  $("btnEditConfig")?.addEventListener("click", () => openEditor("config"));
  $("btnDisableIpv6")?.addEventListener("click", runDisableIpv6);
  $("btnRunDoctorSetup")?.addEventListener("click", () => runFullDoctor({ switchToLab: true }));
  $("btnDismissSetup")?.addEventListener("click", () => {
    localStorage.setItem(SETUP_DISMISS_KEY, "1");
    if (lastState?.doctor) renderDoctor(lastState.doctor);
    toast("Optional setup hidden — use “Show tips” to reopen");
  });
  $("btnOpenSetup")?.addEventListener("click", openSetupTips);

  async function openEditor(fid) {
    const fileId = fid || "config";
    switchToolsTab("editor", { skipHash: true });
    syncRouteHash("tools", "editor", true, null);
    await initEditorView();
    await openFile(fileId);
  }

  function openSetupTips() {
    localStorage.removeItem(SETUP_DISMISS_KEY);
    navigateRoute("dashboard", "wizard");
    if (lastState?.doctor) renderDoctor(lastState.doctor);
    else api("/api/doctor").then(renderDoctor);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  $("btnCopyIp")?.addEventListener("click", () => {
    const ip = window._lastPublicIp;
    if (ip) navigator.clipboard?.writeText(ip).then(() => toast("Copied " + ip));
  });
  $("btnNordAccount")?.addEventListener("click", () => window.open("https://my.nordaccount.com/dashboard/nordvpn/", "_blank"));
  $("btnDnsSave")?.addEventListener("click", () => doAction({
    action: "dns_save",
    primary: $("dnsPrimary")?.value,
    secondary: $("dnsSecondary")?.value,
  }, "Save DNS"));

  $("btnSvcUiInstall")?.addEventListener("click", () => serviceAction("ui", "install"));
  $("btnSvcUiStart")?.addEventListener("click", () => serviceAction("ui", "start"));
  $("btnSvcUiStop")?.addEventListener("click", () => serviceAction("ui", "stop"));
  $("btnSvcUiRestart")?.addEventListener("click", () => serviceAction("ui", "restart"));
  $("btnSvcUiEnable")?.addEventListener("click", () => serviceAction("ui", "enable"));
  $("btnSvcUiDisable")?.addEventListener("click", () => serviceAction("ui", "disable"));
  $("btnSvcUiUninstall")?.addEventListener("click", () => {
    serviceAction("ui", "uninstall");
  });
  $("btnSvcNordStart")?.addEventListener("click", () => serviceAction("nord", "start"));
  $("btnSvcNordStop")?.addEventListener("click", () => serviceAction("nord", "stop"));
  $("btnSvcNordRestart")?.addEventListener("click", () => serviceAction("nord", "restart"));
  $("btnSvcNordEnable")?.addEventListener("click", () => serviceAction("nord", "enable"));
  $("btnSvcNordDisable")?.addEventListener("click", () => serviceAction("nord", "disable"));
  $("btnAdvNettoolRun")?.addEventListener("click", () => {
    const meta = (nettoolsLastPayload?.tools || []).find((t) => t.id === nettoolSelected.adv);
    renderNettoolHelp(meta, "adv");
    runNetTool(undefined, "adv");
  });
  $("advNettoolTarget")?.addEventListener("keydown", (e) => {
    if (e.key === "Enter") runNetTool(undefined, "adv");
  });

  $("btnRunLab")?.addEventListener("click", () => runLeakLab());
  $("btnRunOverallAudit")?.addEventListener("click", () => runOverallAudit());
  $("btnAuditEmailSend")?.addEventListener("click", () => sendAuditEmailReport());
  initAuditEmailPref();
  $("btnLabToAdvanced")?.addEventListener("click", () => navigateRoute("network", "diagnostics"));
  $("btnAlertsOpenSource")?.addEventListener("click", () => window.open("/OPEN_SOURCE.md", "_blank"));
  $("btnTrafficRefresh")?.addEventListener("click", () => loadTraffic());
  $("btnTrafficLocalRefresh")?.addEventListener("click", () => loadTraffic());
  $("btnSpectrumRefresh")?.addEventListener("click", () => loadSpectrum(true));
  $("btnSpectrumZoomIn")?.addEventListener("click", () => spectrumZoomBy(0.72, 0.5));
  $("btnSpectrumZoomOut")?.addEventListener("click", () => spectrumZoomBy(1.35, 0.5));
  $("btnSpectrumZoomReset")?.addEventListener("click", () => {
    resetSpectrumView();
    renderSpectrumCharts();
    renderSpectrumSsidButtons();
    renderSpectrumScanTable();
  });
  $("btnSpectrumRescan")?.addEventListener("click", () =>
    doAction({ action: "wifi_rescan" }, "Rescan WiFi").then(() => loadSpectrum(true)));
  $("spectrumLive")?.addEventListener("change", () => {
    if ($("spectrumLive")?.checked) startSpectrumLive();
    else stopSpectrumLive();
  });
  $("btnSpectrumAllOn")?.addEventListener("click", () => {
    (spectrumData?.all_bands || spectrumData?.bands || []).forEach((b) => { spectrumBandsEnabled[b.id] = true; });
    saveSpectrumBandPrefs();
    resetSpectrumView();
    renderSpectrumBandSwitches(spectrumData?.all_bands || spectrumData?.bands);
    renderSpectrumCharts();
    renderSpectrumSsidButtons();
    renderSpectrumScanTable();
  });
  $("btnSpectrumAllOff")?.addEventListener("click", () => {
    (spectrumData?.all_bands || spectrumData?.bands || []).forEach((b) => { spectrumBandsEnabled[b.id] = false; });
    saveSpectrumBandPrefs();
    resetSpectrumView();
    renderSpectrumBandSwitches(spectrumData?.all_bands || spectrumData?.bands);
    renderSpectrumCharts();
    renderSpectrumSsidButtons();
    renderSpectrumScanTable();
  });
  $("btnBtSpectrumRefresh")?.addEventListener("click", () => loadBluetooth(true, { rescan: false }));
  $("btnBtSpectrumScan")?.addEventListener("click", () =>
    doAction({ action: "bluetooth_scan", duration: 6 }, "Bluetooth scan").then(() => loadBluetooth(true, { rescan: false })));
  $("btSpectrumLive")?.addEventListener("change", () => {
    if ($("btSpectrumLive")?.checked) startBtSpectrumLive();
    else stopBtSpectrumLive();
  });
  $("btnBtSpectrumAllOn")?.addEventListener("click", () => {
    (btSpectrumData?.all_bands || btSpectrumData?.bands || []).forEach((b) => { btSpectrumBandsEnabled[b.id] = true; });
    saveBtSpectrumBandPrefs();
    renderBtSpectrumBandSwitches(btSpectrumData?.all_bands || btSpectrumData?.bands);
    renderBtSpectrumCharts();
    renderBtSpectrumTables();
  });
  $("btnBtSpectrumAllOff")?.addEventListener("click", () => {
    (btSpectrumData?.all_bands || btSpectrumData?.bands || []).forEach((b) => { btSpectrumBandsEnabled[b.id] = false; });
    saveBtSpectrumBandPrefs();
    renderBtSpectrumBandSwitches(btSpectrumData?.all_bands || btSpectrumData?.bands);
    renderBtSpectrumCharts();
    renderBtSpectrumTables();
  });
  $("trafficLive")?.addEventListener("change", (e) => {
    const local = $("trafficLiveLocal");
    if (local) local.checked = e.target.checked;
    if (e.target.checked) startTrafficLive();
    else stopTrafficLive();
  });
  $("trafficLiveLocal")?.addEventListener("change", (e) => {
    const main = $("trafficLive");
    if (main) main.checked = e.target.checked;
    if (e.target.checked) startTrafficLive();
    else stopTrafficLive();
  });
  $("btnRunDoctor")?.addEventListener("click", () => runFullDoctor());
  $("btnAdvDoctor")?.addEventListener("click", () => runFullDoctor({ switchToLab: true }));
  $("btnDisableIpv6Adv")?.addEventListener("click", runDisableIpv6);
  $("btnFixImmutable")?.addEventListener("click", () => doAction({ action: "fix_resolv_immutable" }, "Fix resolv"));
  $("btnExportBundle")?.addEventListener("click", () => api("/api/support-bundle", { method: "POST", body: "{}" }).then((r) => toast(r.path || r.error, r.ok)));
  $("btnExportBundleAnon")?.addEventListener("click", () =>
    api("/api/support-bundle", { method: "POST", body: JSON.stringify({ anonymized: true }) }).then((r) => toast(r.note || r.path || r.error, r.ok))
  );

  $("btnSpeedLabRun")?.addEventListener("click", () => runSpeedLabTest());
  $("speedLabProvider")?.addEventListener("change", () => {
    const sel = $("speedLabProvider");
    if (sel?.value === "auto") {
      speedLabProviderManual = false;
      localStorage.removeItem("nordctl_speed_provider_manual");
      if (speedLabProvidersCache) renderSpeedLabProviderOptions(speedLabProvidersCache);
      return;
    }
    speedLabProviderManual = true;
    localStorage.setItem("nordctl_speed_provider_manual", "1");
    const hint = $("speedLabProviderHint");
    if (hint) hint.textContent = "Manual mirror selected — pick Auto to use IP-based selection again.";
  });
  $("btnSpeedLabClear")?.addEventListener("click", () => clearSpeedHistory());
  $("btnSpeedLabExportJson")?.addEventListener("click", () => exportSpeedHistory("json"));
  $("btnSpeedLabExportCsv")?.addEventListener("click", () => exportSpeedHistory("csv"));
  $("btnSecWatchOn")?.addEventListener("click", () => doAction({ action: "disconnect_watch", enable: true }, "Disconnect alerts").then(() => {
    loadSecurity();
    loadSettingsPanel(true);
  }));
  $("btnSecWatchOff")?.addEventListener("click", () => doAction({ action: "disconnect_watch", enable: false }, "Disconnect alerts").then(() => {
    loadSecurity();
    loadSettingsPanel(true);
  }));
  $("btnSecDisableIpv6")?.addEventListener("click", runDisableIpv6);
  $("btnSecCapture")?.addEventListener("click", async () => {
    const sec = parseInt($("secCaptureSec")?.value, 10) || 10;
    const out = $("secCaptureOut");
    if (out) out.textContent = "Capturing…";
    const res = await doAction({ action: "packet_capture", seconds: sec }, "Packet capture");
    if (out) {
      const lines = (res.summary || []).join("\n") || res.plain || res.error || res.manual || "Done";
      out.textContent = lines;
    }
    drawCaptureProtocolChart(res.summary || []);
  });
  $("btnSecStatusOn")?.addEventListener("click", () => doAction({ action: "status_page", enable: true }, "Status page").then(() => loadSecurity()));
  $("btnSecStatusOff")?.addEventListener("click", () => doAction({ action: "status_page", enable: false }, "Status page").then(() => loadSecurity()));
  $("btnSecCopyStatusUrl")?.addEventListener("click", () => {
    if (!secStatusUrl) { toast("Enable status page first", false); return; }
    navigator.clipboard?.writeText(secStatusUrl).then(() => toast("Status URL copied", true)).catch(() => toast(secStatusUrl, true));
  });
  $("btnSecExportConfig")?.addEventListener("click", () => doAction({ action: "export_config" }, "Export config").then((r) => toast(r.path || r.error, r.ok)));
  $("btnSecExportLogs")?.addEventListener("click", () => doAction({ action: "export_logs" }, "Export logs").then((r) => toast(r.path || r.error, r.ok)));
  $("btnSecExportBundleAnon")?.addEventListener("click", () =>
    api("/api/support-bundle", { method: "POST", body: JSON.stringify({ anonymized: true }) }).then((r) => toast(r.note || r.path || r.error, r.ok))
  );
  $("btnSecCopyHa")?.addEventListener("click", () => {
    const txt = $("secHaYaml")?.textContent || "";
    if (!txt.trim() || txt === "—") { toast("No HA snippet loaded", false); return; }
    navigator.clipboard?.writeText(txt).then(() => toast("HA YAML copied", true)).catch(() => toast("Copy failed", false));
  });

  $("btnWifiRefresh")?.addEventListener("click", () => loadWifiHub());
  $("btnNordDocRefresh")?.addEventListener("click", () => loadNordDoctor(true));
  $("btnNetDocRefresh")?.addEventListener("click", () => loadDoctorsHub(true, true));
  $("btnConnDetailRefresh")?.addEventListener("click", () => loadConnectionDetails(true));
  $("btnPcInfoRefresh")?.addEventListener("click", () => loadPcInfo(true));
  $("btnWifiRescan")?.addEventListener("click", () => doAction({ action: "wifi_rescan" }, "Rescan").then(() => loadWifiHub(true)));
  $("btnWifiSync")?.addEventListener("click", () => doAction({ action: "wifi_sync_profiles" }, "Sync").then(() => loadWifiHub(true)));
  $("btnWifiConnectSsid")?.addEventListener("click", () => {
    const ssid = ($("wifiConnectSsid")?.value || "").trim();
    const password = $("wifiConnectPassword")?.value || "";
    if (!ssid) {
      toast("Enter an SSID to connect.", false);
      $("wifiConnectSsid")?.focus();
      return;
    }
    doAction({ action: "wifi_connect", ssid, password }, "Connect WiFi").then(() => loadWifiHub(true));
  });
  $("btnWifiHeal")?.addEventListener("click", () => doAction({ action: "wifi_heal" }, "Self-heal").then(() => loadWifiHub(true)));
  $("btnWifiEditConfig")?.addEventListener("click", () => openEditor("config"));
  $("btnWifiDnsSave")?.addEventListener("click", () => doAction({
    action: "dns_save",
    primary: $("wifiDnsPrimary")?.value,
    secondary: $("wifiDnsSecondary")?.value,
  }, "Save DNS"));
  $("btnWifiApplySmart")?.addEventListener("click", () => doAction({ action: "dns_apply_smart" }, "Smart DNS").then(() => loadWifiHub(true)));
  $("btnWifiRestoreDns")?.addEventListener("click", () => doAction({ action: "dns_restore" }, "Restore DNS").then(() => loadWifiHub(true)));
  $("btnWifiWatchOn")?.addEventListener("click", () => doAction({ action: "wifi_zone_watch", enable: true }, "Zone watch").then(() => loadWifiHub(true)));
  $("btnWifiWatchOff")?.addEventListener("click", () => doAction({ action: "wifi_zone_watch", enable: false }, "Zone watch").then(() => loadWifiHub(true)));
  $("btnWatcherEnable")?.addEventListener("click", () => doAction({ action: "wifi_zone_watch", enable: true }, "Zone watch").then(() => refresh()));
  $("btnWatcherDisable")?.addEventListener("click", () => doAction({ action: "wifi_zone_watch", enable: false }, "Zone watch").then(() => refresh()));
  $("btnWifiZoneApply")?.addEventListener("click", () => doAction({ action: "zone_auto" }, "Zone preset").then(() => loadWifiHub(true)));
  $("btnWifiZoneAdd")?.addEventListener("click", () => {
    const ssid = ($("wifiZoneSsid")?.value || "").trim();
    if (!ssid) { toast("Enter SSID", false); return; }
    doAction({ action: "wifi_zone_add", ssid, preset: $("wifiZonePreset")?.value }, "Zone").then(() => loadWifiHub(true));
  });
  $("btnWifiZonesSave")?.addEventListener("click", () => {
    doAction({
      action: "wifi_zones_save",
      auto_apply: !!$("wifiZoneAutoApply")?.checked,
      untrusted_preset: $("wifiUntrustedPreset")?.value,
    }, "Zones").then(() => loadWifiHub(true));
  });
  document.addEventListener("change", (e) => {
    if (e.target?.id === "wifiHealSync" || e.target?.id === "wifiHealDns") {
      doAction({
        action: "wifi_self_heal",
        auto_sync_active: !!$("wifiHealSync")?.checked,
        heal_smart_dns: !!$("wifiHealDns")?.checked,
      }, "Self-heal options");
    }
  });

  $("btnAddSubnet")?.addEventListener("click", () => doAction({ action: "allowlist_add_subnet", cidr: $("allowSubnet")?.value }, "Add subnet"));
  $("btnAddPort")?.addEventListener("click", () => doAction({ action: "allowlist_add_port", port: parseInt($("allowPort")?.value, 10) }, "Add port"));
  $("btnApplyLan")?.addEventListener("click", () => doAction({ action: "allowlist_apply_lan" }, "LAN allowlist"));
  $("btnSaveLanCidr")?.addEventListener("click", async () => {
    const value = String($("lanAllowlistCidr")?.value || "").trim();
    if (!value) return toast("Enter a CIDR (e.g. 192.168.0.0/16)", false);
    const res = await doAction({ action: "set_config_field", field: "lan_allowlist_cidr", value }, "Home LAN range");
    if (res.ok) syncHomeLanUi(res.state || lastState);
  });
  $("btnAddFavCountry")?.addEventListener("click", () => {
    const value = favFavoriteValue();
    if (!value) return toast("Pick a country first (and optional city)", false);
    const kind = ($("favCitySelect")?.value || value.includes(" ")) ? "city" : "country";
    doAction({ action: "favorite_add", kind, value: kind === "country" ? value.replace(/ /g, "_") : value }, "Favorite")
      .then((r) => { if (r.ok) loadState(true); });
  });
  $("btnConnectFav")?.addEventListener("click", () => {
    const target = favConnectTarget();
    if (!target) return toast("Pick a country first", false);
    doAction({ action: "connect", target }, "Connect");
  });
  $("btnAddCustomPlace")?.addEventListener("click", addCustomPlace);
  $("btnAddPreset")?.addEventListener("click", () => addPresetFromDashboard("blank"));
  $("btnAddPresetExample")?.addEventListener("click", () => addPresetFromDashboard("copy-example"));
  $("btnCommunityImport")?.addEventListener("click", async () => {
    const url = String($("communityImportUrl")?.value || "").trim();
    if (!url) return toast("Paste a raw URL to a preset YAML file", false);
    const res = await doAction({ action: "import_preset_yaml", url }, "Import preset");
    if (res.ok) {
      $("communityImportUrl").value = "";
      loadCommunityPresets();
      loadState(true);
    }
  });
  $("btnPresetImport")?.addEventListener("click", () => importSharedPreset({ jumpToPresets: false }));
  $("btnPresetImportFilePick")?.addEventListener("click", () => $("presetImportFile")?.click());
  $("presetImportFile")?.addEventListener("change", (e) => {
    const f = e.target?.files?.[0];
    importPresetFromLocalFile(f);
  });
  $("btnPresetImportClear")?.addEventListener("click", () => {
    const yamlEl = $("presetImportYaml");
    const urlEl = $("presetImportUrl");
    const fileEl = $("presetImportFile");
    if (yamlEl) yamlEl.value = "";
    if (urlEl) urlEl.value = "";
    if (fileEl) fileEl.value = "";
  });
  $("btnCommunityRefresh")?.addEventListener("click", () => loadCommunityPresets());
  loadCommunityPresets();
  $("btnPlacesBaselineRestore")?.addEventListener("click", () => restoreInstallBaseline("Install baseline"));

  $("btnZoneApply")?.addEventListener("click", () => doAction({ action: "zone_auto" }, "Zone preset"));
  $("btnSwitchProfile")?.addEventListener("click", () => doAction({ action: "profile_switch", name: $("profileSelect")?.value }, "Profile"));
  $("btnAddSchedule")?.addEventListener("click", () => doAction({ action: "schedule_add", preset: $("schedPreset")?.value, time: $("schedTime")?.value || "18:00" }, "Schedule"));
  $("btnWriteSystemd")?.addEventListener("click", () => api("/api/schedules/write", { method: "POST" }).then((r) => toast(r.enable_hint || "Written", r.ok)));
  $("btnSnapshotSave")?.addEventListener("click", () => doAction({ action: "snapshot" }, "Snapshot"));
  $("btnSnapshotRestore")?.addEventListener("click", () => doAction({ action: "snapshot", restore: true }, "Nord snapshot"));
  $("btnSnapshotRestoreOnly")?.addEventListener("click", () => doAction({ action: "snapshot", restore: true }, "Nord snapshot"));
  $("btnBaselineRestore")?.addEventListener("click", () => {
    doAction({ action: "baseline_restore" }, "Baseline restore");
  });
  $("btnBaselineEnsure")?.addEventListener("click", () => doAction({ action: "baseline_ensure" }, "Baseline"));
  $("btnFactoryReset")?.addEventListener("click", async () => {
    const res = await doAction({ action: "factory_reset" }, "Factory reset");
    if (res.ok) {
      toast("Factory reset complete — refreshing…", true);
      setTimeout(() => window.location.reload(), 1200);
    }
  });

  $("editorSave")?.addEventListener("click", saveEditor);
  $("editorRevert")?.addEventListener("click", () => {
    $("editorText").value = editor.savedContent;
    setEditorDirty(false);
    scheduleLint();
  });
  $("editorRestoreBaseline")?.addEventListener("click", async () => {
    const res = await doAction({ action: "editor_restore_baseline", id: editor.id }, "Restore from install");
    if (res.ok) {
      await openFile(editor.id);
      if (editor.id === "config") await loadState(true);
      else await loadState(true);
    }
  });
  $("editorRestoreAllBaseline")?.addEventListener("click", () => restoreInstallBaseline("Restore all files"));
  $("editorDeletePreset")?.addEventListener("click", async () => {
    if (!editor.id?.startsWith("user/")) return;
    const res = await doAction({ action: "preset_delete", file_id: editor.id }, "Delete preset");
    if (res.ok) {
      await loadFileList();
      await openFile("config");
      await loadState(true);
    }
  });
  $("editorNewPreset")?.addEventListener("click", newPreset);
  $("editorText")?.addEventListener("input", () => {
    setEditorDirty($("editorText").value !== editor.savedContent);
    updateGutter(editor.errorLine);
    scheduleLint();
  });
  $("editorText")?.addEventListener("scroll", () => {
    $("editorGutter").scrollTop = $("editorText").scrollTop;
  });

  document.addEventListener("keydown", (e) => {
    if (!editor.active) return;
    if ((e.ctrlKey || e.metaKey) && e.key === "s") { e.preventDefault(); saveEditor(); }
  });

  window.nordctlOpenEditor = (fid) => openEditor(fid || "config");

  $("btnUfwEnable")?.addEventListener("click", () => ufwAction({ action: "enable" }, "UFW enabled"));
  $("btnUfwDisable")?.addEventListener("click", () => ufwAction({ action: "disable" }, "UFW disabled"));
  $("btnUfwReload")?.addEventListener("click", () => ufwAction({ action: "reload" }, "UFW reloaded"));
  $("btnUfwRefresh")?.addEventListener("click", () => loadUfw(true));
  $("btnListenersRefresh")?.addEventListener("click", async () => {
    const btn = $("btnListenersRefresh");
    if (btn) btn.disabled = true;
    try {
      await loadListeners(true);
      toast("Listeners refreshed", true);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
  $("btnPrivRefresh")?.addEventListener("click", async () => {
    const btn = $("btnPrivRefresh");
    if (btn) btn.disabled = true;
    try {
      await loadPrivileges(true);
      toast("Privileges re-checked", true);
    } finally {
      if (btn) btn.disabled = false;
    }
  });
  $("btnUfwSudoSetup")?.addEventListener("click", async () => {
    const data = await api("/api/ufw");
    const ufwPath = data?.status?.install_script || lastState?.privileges?.install_scripts?.ufw;
    const script = sudoBashScript(ufwPath);
    const full = sudoBashScript(lastState?.privileges?.install_scripts?.privileges);
    const body = [
      "Run once in a terminal (as your user — enter your password when asked):",
      "",
      script || "(Refresh the page — install path could not be resolved)",
      full ? "" : "",
      full ? "Or install UFW + IPv6 + resolv fixes together:" : "",
      full || "",
      "",
      "Then restart the UI:",
      lastState?.cli?.service_restart || "~/.local/bin/nordctl service restart",
      "",
      "Click ↻ Refresh on Network & Security → Linux UFW after restart.",
    ].filter(Boolean).join("\n");
    showNotice(body, { ok: true, title: "UFW sudo setup", copyText: full || script || undefined });
  });
  $("btnUfwAdd")?.addEventListener("click", () => {
    ufwAction({
      action: "allow",
      port: $("ufwAddPort")?.value,
      proto: $("ufwAddProto")?.value || "tcp",
      from: $("ufwAddFrom")?.value,
      comment: $("ufwAddComment")?.value,
    }, "Rule added");
  });

  initNoticePanel();
  initGlobalConfirm();
  initPresetPanelResets();
  initPresetBuilderEvents();
  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-preset-reset-panel]");
    if (!btn || btn.disabled) return;
    resetPresetsFactory(btn.getAttribute("data-preset-reset-panel"));
  });
  initViewJumps();
  initTheme();
  initLogPanel();
  initBellPanel();
  startTopbarSysTimers();
  toggleBellDropdown(false);
  applyButtonTitles();
  initMeshnetPageActions();
  setInterval(() => loadState({ force: true, silent: true }), 15000);
  setInterval(pollBrowserAlerts, 30000);

  $("btnAlertBell")?.addEventListener("click", (e) => {
    e.stopPropagation();
    toggleBellDropdown();
    refreshBellRecent();
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest(".bell-wrap")) toggleBellDropdown(false);
  });
  $("btnBellEnableNotify")?.addEventListener("click", () => requestBrowserNotify());
  $("btnSettingsEnableNotify")?.addEventListener("click", () => requestBrowserNotify());
  $("btnBellTest")?.addEventListener("click", () => doAction({ action: "alerts_test" }, "Test alert").then(refreshBellRecent));
  $("btnBellOpenSettings")?.addEventListener("click", () => {
    toggleBellDropdown(false);
    navigateRoute("settings", "network", { sub: "notifications" });
  });
  $("btnUiLogin")?.addEventListener("click", uiLoginSubmit);
  $("uiLoginPassword")?.addEventListener("keydown", (e) => { if (e.key === "Enter") uiLoginSubmit(); });
  $("btnUiPasswordSave")?.addEventListener("click", async () => {
    const res = await doAction({
      action: "ui_password_set",
      current: $("settingsUiPasswordCurrent")?.value,
      password: $("settingsUiPasswordNew")?.value,
    }, "Dashboard password");
    if (res.ok) {
      if (res.token) sessionStorage.setItem(UI_TOKEN_KEY, res.token);
      toast(res.note || "Password saved", true);
      $("settingsUiPasswordCurrent").value = "";
      $("settingsUiPasswordNew").value = "";
      loadSettingsPanel();
    }
  });
  $("btnUiPasswordClear")?.addEventListener("click", async () => {
    const res = await doAction({ action: "ui_password_clear", current: $("settingsUiPasswordCurrent")?.value }, "Remove password");
    if (res.ok) {
      sessionStorage.removeItem(UI_TOKEN_KEY);
      toast(res.note || "Password removed", true);
      loadSettingsPanel();
    }
  });
  $("btnSettingsInterfaceSave")?.addEventListener("click", async () => {
    const showGuides = !!$("settingsPageGuidesShow")?.checked;
    const res = await doAction({
      action: "ui_prefs_save",
      page_guides_visible_default: showGuides,
      page_intro_visible: !!$("settingsPageIntroVisible")?.checked,
      clock_format: $("settingsClock12")?.checked ? "12h" : "24h",
    }, "Interface settings");
    if (res.ok) {
      localStorage.removeItem(PAGE_HOW_USER_SET_KEY);
      applyUiPrefsFromConfig(res);
      renderSettingsInterfacePanel(res);
      loadSettingsPanel(true);
    }
  });
  $("btnQuickCommandsSave")?.addEventListener("click", async () => {
    try {
      await saveQuickCommandsSettings();
      await loadQuickCommandsSettings(true);
    } catch (e) {
      reportActionError("Quick commands save failed", e, "Saving shell buttons");
    }
  });
  $("btnQuickCommandsResetScope")?.addEventListener("click", async () => {
    if (quickCommandsEditScope === "custom") {
      toast("Delete custom categories with Delete category, or remove their commands.", false);
      return;
    }
    try {
      await saveQuickCommandsSettings(quickCommandsEditScope);
      await loadQuickCommandsSettings(true);
    } catch (e) {
      reportActionError("Quick commands reset failed", e, "Resetting shell buttons");
    }
  });
  $("btnQuickCommandsAddCommand")?.addEventListener("click", () => {
    if (!quickCommandsSettingsDraft) {
      void loadQuickCommandsSettings(true).then(() => $("btnQuickCommandsAddCommand")?.click());
      return;
    }
    collectQuickCommandsDraftFromDom();
    if (quickCommandsEditScope === "custom") {
      const cats = quickCommandsSettingsDraft.custom_categories || [];
      if (!cats.length) {
        toast("Add a custom category first, or switch to Networking / Security / Nord shell.", false);
        return;
      }
      addQuickCommandToDraft("custom", cats.length - 1);
    } else {
      addQuickCommandToDraft(quickCommandsEditScope);
    }
    renderQuickCommandsSettingsEditor();
  });
  $("btnQuickCommandsAddCategory")?.addEventListener("click", () => {
    if (!quickCommandsSettingsDraft) {
      void loadQuickCommandsSettings(true).then(() => $("btnQuickCommandsAddCategory")?.click());
      return;
    }
    collectQuickCommandsDraftFromDom();
    quickCommandsEditScope = "custom";
    quickCommandsSettingsDraft.custom_categories = quickCommandsSettingsDraft.custom_categories || [];
    quickCommandsSettingsDraft.custom_categories.push({
      id: `category-${Date.now().toString(36)}`,
      label: "New category",
      commands: [{ label: "Example", cmd: "echo hello\n", enabled: true }],
    });
    const nav = $("quickCommandsScopeNav");
    nav?.querySelectorAll("[data-qc-scope]").forEach((b) => {
      b.classList.toggle("active", b.getAttribute("data-qc-scope") === "custom");
    });
    renderQuickCommandsSettingsEditor();
  });
  $("btnSettingsResetUiCache")?.addEventListener("click", resetNordctlBrowserUiState);
  $("btnSettingsNotifySave")?.addEventListener("click", async () => {
    await doAction({
      action: "alerts_save",
      browser_enabled: !!$("settingsBrowserAlerts")?.checked,
      rules: {
        security_audit: !!$("setRuleAudit")?.checked,
        health_score_low: !!$("setRuleHealth")?.checked,
        vpn_disconnect: !!$("setRuleVpnDisc")?.checked,
        smart_dns_drift: !!$("setRuleDnsDrift")?.checked,
        wifi_untrusted: !!$("setRuleUntrusted")?.checked,
      },
    }, "Browser alerts");
    loadSettingsPanel();
  });
  $("btnSettingsEmailSave")?.addEventListener("click", async () => {
    await doAction({
      action: "alerts_save",
      email: {
        enabled: !!$("settingsEmailAlerts")?.checked,
        to: $("settingsEmailTo")?.value,
        smtp_host: $("settingsSmtpHost")?.value,
        smtp_user: $("settingsSmtpUser")?.value,
        smtp_password: $("settingsSmtpPass")?.value,
      },
      scan_email: {
        enabled: !!$("settingsScanEmailEnabled")?.checked,
        email_on_findings: !!$("settingsScanEmailFindings")?.checked,
        email_on_failure: !!$("settingsScanEmailFailure")?.checked,
        email_always: !!$("settingsScanEmailAlways")?.checked,
        lynis_min_score_alert: parseInt($("settingsLynisMinScore")?.value || "65", 10) || 65,
      },
    }, "Email settings");
    if ($("settingsSmtpPass")) $("settingsSmtpPass").value = "";
    loadSettingsPanel();
  });
  $("btnSettingsNotifyTest")?.addEventListener("click", () => doAction({ action: "alerts_test" }, "Test alert"));
  $("btnSettingsPrivacyExport")?.addEventListener("click", () => doAction({ action: "privacy_export" }, "Privacy export").then((r) => toast(r.path || r.error, r.ok)));
  $("btnSettingsAlertsWatchOn")?.addEventListener("click", () => doAction({ action: "alerts_watch", enable: true }, "Alert watch").then(loadSettingsPanel));
  $("btnSettingsAlertsWatchOff")?.addEventListener("click", () => doAction({ action: "alerts_watch", enable: false }, "Alert watch").then(loadSettingsPanel));
  $("btnSettingsSvcStart")?.addEventListener("click", () => serviceAction("ui", "start").then(loadSettingsPanel));
  $("btnSettingsSvcStop")?.addEventListener("click", () => serviceAction("ui", "stop").then(loadSettingsPanel));
  $("btnSettingsSvcRestart")?.addEventListener("click", () => serviceAction("ui", "restart").then(loadSettingsPanel));
  $("btnSettingsSpeedSave")?.addEventListener("click", () => saveSettingsConfigSection("speedtest", {
    default_provider: $("settingsSpeedDefaultProvider")?.value || "auto",
    default_profile: $("settingsSpeedDefaultProfile")?.value || "standard",
    default_method: $("settingsSpeedDefaultMethod")?.value || "single",
    warmup: !!$("settingsSpeedWarmup")?.checked,
    save_results: !!$("settingsSpeedSaveResults")?.checked,
    custom_mirrors: collectSettingsSpeedMirrors(),
  }, "Speed test settings"));
  $("btnSettingsSpeedMirrorAdd")?.addEventListener("click", () => {
    settingsSpeedMirrors.push({ id: "", label: "", url: "", region: "custom" });
    renderSettingsSpeedMirrorRows();
  });
  $("btnSettingsSmartDnsSave")?.addEventListener("click", () => saveSettingsConfigSection("smart_dns", {
    primary: $("settingsSmartDnsPrimary")?.value,
    secondary: $("settingsSmartDnsSecondary")?.value,
  }, "Smart DNS"));
  $("btnSettingsApplySmartDns")?.addEventListener("click", () => doAction({ action: "dns_apply_smart" }, "Apply Smart DNS").then(loadSettingsPanel));
  $("btnSettingsZonesSave")?.addEventListener("click", () => saveSettingsConfigSection("wifi_zones", {
    home_ip_learn: !!$("settingsHomeIpLearn")?.checked,
    home_ip_when_trusted: !!$("settingsHomeIpWhenTrusted")?.checked,
    auto_apply: !!$("settingsZoneAutoApply")?.checked,
    untrusted_preset: $("settingsUntrustedPreset")?.value,
  }, "WiFi zones"));
  $("btnSettingsWifiSave")?.addEventListener("click", () => saveSettingsConfigSection("wifi", {
    auto_sync_active: !!$("settingsWifiAutoSync")?.checked,
    heal_smart_dns: !!$("settingsWifiHealDns")?.checked,
  }, "WiFi options"));
  $("btnSettingsWifiSync")?.addEventListener("click", () => doAction({ action: "wifi_sync_profiles" }, "Sync WiFi").then(loadSettingsPanel));
  $("btnSettingsVpnDefaultsSave")?.addEventListener("click", () => saveSettingsConfigSection("vpn_defaults", {
    lan_allowlist_cidr: $("settingsLanCidr")?.value,
    voip_ports: $("settingsVoipPorts")?.value,
    auto_snapshot_before_preset: !!$("settingsAutoSnapshot")?.checked,
  }, "VPN defaults"));
  $("btnSettingsProbesSave")?.addEventListener("click", () => saveSettingsConfigSection("probes", {
    public_ip_check_url: $("settingsPublicIpUrl")?.value,
  }, "Probe URL"));
  $("btnSettingsHomeIspSave")?.addEventListener("click", () => saveSettingsConfigSection("home_ip_fallback", {
    enabled: !!$("settingsHomeIspFallbackEnabled")?.checked,
    ip: $("settingsHomeIspFallbackIp")?.value,
  }, "Home ISP fallback"));
  $("btnSettingsNordBinSave")?.addEventListener("click", () => saveSettingsConfigSection("vpn_defaults", {
    nordvpn_bin: $("settingsNordvpnBin")?.value,
  }, "Nord binary"));
  $("btnSettingsServicePrefsSave")?.addEventListener("click", () => saveSettingsConfigSection("service_prefs", {
    nord_autostart: !!$("settingsNordAutostart")?.checked,
    tray_enabled: !!$("settingsTrayEnabled")?.checked,
    tray_autostart: !!$("settingsTrayAutostart")?.checked,
  }, "Service preferences"));
  $("btnSettingsAlertsAdvancedSave")?.addEventListener("click", () => saveSettingsConfigSection("alerts_advanced", {
    watch_interval: Number($("settingsWatchInterval")?.value || 60),
    rate_limit_minutes: Number($("settingsRateLimit")?.value || 15),
    health_threshold: Number($("settingsHealthThreshold")?.value || 50),
  }, "Alert timing"));
  $("btnSettingsRunWizard")?.addEventListener("click", () => showSetupWizardGate());
  $("btnSettingsDisableIpv6")?.addEventListener("click", runDisableIpv6);
  $("btnSettingsAddPlace")?.addEventListener("click", addCustomPlace);
  $("btnCustomPackagesToolAdd")?.addEventListener("click", () => addCustomPackageFromForm());
  $("btnCustomPackagesCategoryAdd")?.addEventListener("click", () => addPackageCategory($("customPackagesCategoryNew")?.value));
  $("btnCustomPackagesCategoryDelete")?.addEventListener("click", () => {
    removePackageCategory($("btnCustomPackagesCategoryDelete")?.dataset.categoryId);
  });

  $("btnWizardStart")?.addEventListener("click", () => openSetupWizard(true, false));
  $("btnWizardStartShort")?.addEventListener("click", () => openSetupWizard(true, true));
  $("btnTopbarWizard")?.addEventListener("click", () => showSetupWizardGate());
  $("btnWizardDismiss")?.addEventListener("click", () => dismissSetupWizardGate());
  $("btnOnboardContinue")?.addEventListener("click", () => continueOnboardingCurrent());
  $("btnWizardClose")?.addEventListener("click", () => closeWizardSteps());
  $("btnWizardClosePage")?.addEventListener("click", () => leaveWizardPage());
  $("wizardBack")?.addEventListener("click", () => wizardGoBack());
  $("wizardSkip")?.addEventListener("click", () => wizardGoNext(true));
  $("wizardNext")?.addEventListener("click", () => wizardGoNext(false));
  async function switchToVpnMode() {
    const res = await doAction({ action: "set_usage_mode", mode: "vpn" }, "Switch to VPN mode");
    if (res.ok) {
      toast("Switched to VPN mode — presets and Connect tab are fully enabled", true);
      await loadState();
    }
  }
  $("btnSwitchVpnMode")?.addEventListener("click", switchToVpnMode);
  $("btnSetupSwitchVpn")?.addEventListener("click", switchToVpnMode);
  $("btnSettingsEmailTest")?.addEventListener("click", () => doAction({ action: "alerts_test" }, "Test alert"));
})();
