"""Optional system packages for nordctl features (apt install from the UI)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from nordctl.config import load_config, save_config
from nordctl.privileges import passwordless_sudo, sudo_available

# hub: "network" (Advanced tab) or "security" (Security tab)
TOOL_CATALOG: list[dict[str, Any]] = [
    # ── Top 10 networking (Advanced hub) ──
    {
        "id": "curl",
        "label": "curl",
        "packages": ["curl"],
        "bins": ["curl"],
        "hub": "network",
        "description": "Public IP lookup, speed test, and HTTP checks in Network diagnostics.",
        "used_by": "Public IP · Speed test",
    },
    {
        "id": "dnsutils",
        "label": "dig / DNS tools",
        "packages": ["dnsutils"],
        "bins": ["dig"],
        "hub": "network",
        "description": "DNS lookup tool in Advanced → Network diagnostics.",
        "used_by": "DNS lookup",
    },
    {
        "id": "mtr",
        "label": "mtr & traceroute",
        "packages": ["mtr-tiny", "traceroute"],
        "bins": ["mtr", "traceroute", "tracepath"],
        "hub": "network",
        "description": "Hop-by-hop path tests to any host or IP.",
        "used_by": "Traceroute",
    },
    {
        "id": "iputils-ping",
        "label": "ping",
        "packages": ["iputils-ping"],
        "bins": ["ping"],
        "hub": "network",
        "description": "ICMP reachability — Overview and Ping diagnostic.",
        "used_by": "Ping · Overview",
    },
    {
        "id": "net-tools",
        "label": "netstat (legacy)",
        "packages": ["net-tools"],
        "bins": ["netstat"],
        "hub": "network",
        "description": "Fallback when modern ss is unavailable — connections & listening ports.",
        "used_by": "Connections · Listening ports",
    },
    {
        "id": "nmap",
        "label": "nmap",
        "packages": ["nmap"],
        "bins": ["nmap"],
        "hub": "network",
        "description": "Safe local port scan — see open ports on your LAN (read-only quick scan).",
        "used_by": "Port scan",
    },
    {
        "id": "iperf3",
        "label": "iperf3",
        "packages": ["iperf3"],
        "bins": ["iperf3"],
        "hub": "network",
        "description": "Throughput benchmark to an iperf3 server (manual target in diagnostics).",
        "used_by": "Bandwidth test",
    },
    {
        "id": "whois",
        "label": "whois",
        "packages": ["whois"],
        "bins": ["whois"],
        "hub": "network",
        "description": "Domain registration lookup for a hostname.",
        "used_by": "WHOIS lookup",
    },
    {
        "id": "netcat",
        "label": "netcat (nc)",
        "packages": ["netcat-openbsd"],
        "bins": ["nc", "nc.openbsd"],
        "hub": "network",
        "description": "Quick TCP connectivity probe to a host:port.",
        "used_by": "Port probe",
    },
    {
        "id": "network-manager",
        "label": "NetworkManager",
        "packages": ["network-manager"],
        "bins": ["nmcli"],
        "hub": "network",
        "description": "WiFi profiles, Smart DNS, zones, and self-healing on the WiFi tab.",
        "used_by": "WiFi hub",
    },
    {
        "id": "iproute2",
        "label": "iproute2 (ip / ss)",
        "packages": ["iproute2"],
        "bins": ["ip", "ss"],
        "hub": "network",
        "description": "Modern routing table, interface, and socket listing — core of Audit diagnostics.",
        "used_by": "Routes · Connections · Listening",
    },
    {
        "id": "nftables-net",
        "label": "nftables",
        "packages": ["nftables"],
        "bins": ["nft"],
        "hub": "network",
        "description": "Kernel nft ruleset — pairs with UFW on modern Ubuntu.",
        "used_by": "nftables diagnostic",
        "run_cmd": "sudo nft list ruleset",
        "run_label": "List nft rules",
    },
    {
        "id": "tshark",
        "label": "tshark",
        "packages": ["tshark"],
        "bins": ["tshark"],
        "hub": "network",
        "description": "CLI packet capture and decode — lighter than full Wireshark GUI.",
        "used_by": "Packet analysis",
        "run_cmd": "sudo tshark -i any -c 25 -n",
        "run_label": "Sample capture",
    },
    {
        "id": "arping",
        "label": "arping",
        "packages": ["arping"],
        "bins": ["arping"],
        "hub": "network",
        "description": "ARP-level reachability on your LAN segment.",
        "used_by": "LAN neighbor probe",
        "run_cmd": "arping -c 3 $(ip route | awk '/default/ {print $3; exit}')",
        "run_label": "Ping gateway (ARP)",
    },
    {
        "id": "hping3",
        "label": "hping3",
        "packages": ["hping3"],
        "bins": ["hping3"],
        "hub": "network",
        "description": "Advanced ICMP/TCP/UDP probes when ping is blocked.",
        "used_by": "Reachability tests",
        "run_cmd": "hping3 -c 3 -S -p 443 1.1.1.1",
        "run_label": "TCP probe 1.1.1.1:443",
    },
    {
        "id": "socat",
        "label": "socat",
        "packages": ["socat"],
        "bins": ["socat"],
        "hub": "network",
        "description": "Bidirectional socket relay — quick TCP/UDP tunnel tests.",
        "used_by": "Socket relay tests",
        "run_cmd": "socat -V",
        "run_label": "Show socat version",
    },
    {
        "id": "wget",
        "label": "wget",
        "packages": ["wget"],
        "bins": ["wget"],
        "hub": "network",
        "description": "HTTP/FTP fetch — backup for curl and mirror checks.",
        "used_by": "HTTP download checks",
        "run_cmd": "wget -qO- --timeout=5 https://ifconfig.me/ip",
        "run_label": "Fetch public IP",
    },
    {
        "id": "ethtool",
        "label": "ethtool",
        "packages": ["ethtool"],
        "bins": ["ethtool"],
        "hub": "network",
        "description": "NIC link speed, driver, and error counters.",
        "used_by": "Interface health",
        "run_cmd": "ethtool $(ip route | awk '/default/ {print $5; exit}')",
        "run_label": "Default NIC stats",
    },
    {
        "id": "vnstat",
        "label": "vnstat",
        "packages": ["vnstat"],
        "bins": ["vnstat"],
        "hub": "network",
        "description": "Historical bandwidth per interface (needs vnstat enabled once).",
        "used_by": "Bandwidth history",
        "run_cmd": "vnstat -i $(ip route | awk '/default/ {print $5; exit}')",
        "run_label": "Interface stats",
    },
    {
        "id": "openssl",
        "label": "OpenSSL",
        "packages": ["openssl"],
        "bins": ["openssl"],
        "hub": "network",
        "description": "TLS certificate expiry and cipher checks from the shell.",
        "used_by": "TLS / cert checks",
        "run_cmd": "openssl s_client -connect cloudflare.com:443 -servername cloudflare.com </dev/null 2>/dev/null | openssl x509 -noout -dates",
        "run_label": "Check TLS cert dates",
    },
    {
        "id": "tcptraceroute",
        "label": "tcptraceroute",
        "packages": ["tcptraceroute"],
        "bins": ["tcptraceroute"],
        "hub": "network",
        "description": "Traceroute over TCP when ICMP is filtered.",
        "used_by": "TCP path trace",
        "run_cmd": "tcptraceroute -n 443 google.com",
        "run_label": "TCP trace to google.com",
    },
    {
        "id": "iptables",
        "label": "iptables",
        "packages": ["iptables"],
        "bins": ["iptables"],
        "hub": "network",
        "description": "Legacy firewall rules listing alongside nft/UFW.",
        "used_by": "iptables -L snapshot",
        "run_cmd": "sudo iptables -L -n -v",
        "run_label": "List iptables",
    },
    {
        "id": "iftop",
        "label": "iftop",
        "packages": ["iftop"],
        "bins": ["iftop"],
        "hub": "network",
        "description": "Live bandwidth by connection on the default interface.",
        "used_by": "Traffic by host",
        "run_cmd": "sudo iftop -t -s 5",
        "run_label": "Sample iftop",
    },
    {
        "id": "wavemon",
        "label": "wavemon",
        "packages": ["wavemon"],
        "bins": ["wavemon"],
        "hub": "network",
        "description": "WiFi signal, bitrate, and link quality in the terminal.",
        "used_by": "WiFi signal monitor",
        "run_cmd": "wavemon -i $(iw dev | awk '$1==\"Interface\"{print $2; exit}')",
        "run_label": "WiFi monitor",
    },
    {
        "id": "arp-scan",
        "label": "arp-scan",
        "packages": ["arp-scan"],
        "bins": ["arp-scan"],
        "hub": "network",
        "description": "Discover devices on your LAN via ARP.",
        "used_by": "LAN device scan",
        "run_cmd": "sudo arp-scan --localnet",
        "run_label": "Scan LAN",
    },
    {
        "id": "fping",
        "label": "fping",
        "packages": ["fping"],
        "bins": ["fping"],
        "hub": "network",
        "description": "Ping many hosts in parallel — fast LAN reachability sweep.",
        "used_by": "Parallel ping",
        "run_cmd": "fping -a -g $(ip route | awk '/src/ {print $1; exit}')/24 2>/dev/null | head -20",
        "run_label": "Ping LAN (/24)",
    },
    {
        "id": "nethogs",
        "label": "nethogs",
        "packages": ["nethogs"],
        "bins": ["nethogs"],
        "hub": "network",
        "description": "Live bandwidth per process — see which app is using the link.",
        "used_by": "Traffic by process",
        "run_cmd": "sudo nethogs -t -c 5 $(ip route | awk '/default/ {print $5; exit}')",
        "run_label": "Sample nethogs",
    },
    {
        "id": "ipcalc",
        "label": "ipcalc",
        "packages": ["ipcalc"],
        "bins": ["ipcalc"],
        "hub": "network",
        "description": "CIDR and subnet math — plan split tunnels and allowlists.",
        "used_by": "Subnet calculator",
        "run_cmd": "ipcalc $(ip route | awk '/src/ {print $1; exit}')/24",
        "run_label": "Your LAN subnet",
    },
    {
        "id": "avahi-utils",
        "label": "Avahi (mDNS)",
        "packages": ["avahi-utils"],
        "bins": ["avahi-browse"],
        "hub": "network",
        "description": "Browse mDNS/Bonjour services on the LAN (.local hostnames).",
        "used_by": "mDNS discovery",
        "run_cmd": "timeout 5 avahi-browse -a -t 2>/dev/null | head -25",
        "run_label": "Browse mDNS",
    },
    {
        "id": "ngrep",
        "label": "ngrep",
        "packages": ["ngrep"],
        "bins": ["ngrep"],
        "hub": "network",
        "description": "Grep packet payloads — quick HTTP/DNS pattern checks without full Wireshark.",
        "used_by": "Packet grep",
        "run_cmd": "sudo timeout 10 ngrep -q -W byline 'GET|POST' port 80 2>/dev/null | head -15",
        "run_label": "Sample HTTP grep",
    },
    # ── Top 10 security (Security hub) ──
    {
        "id": "ufw",
        "label": "UFW firewall",
        "packages": ["ufw"],
        "bins": ["ufw"],
        "hub": "security",
        "description": "Linux host firewall — Firewall tab rule editor.",
        "used_by": "Firewall tab · UFW status",
        "run_cmd": "sudo ufw status verbose",
        "run_label": "UFW status",
    },
    {
        "id": "tcpdump",
        "label": "tcpdump",
        "packages": ["tcpdump"],
        "bins": ["tcpdump"],
        "hub": "security",
        "description": "Short packet captures on the Security tab (lite .pcap).",
        "used_by": "Packet capture",
        "run_cmd": "sudo timeout 15 tcpdump -i any -c 30 -n",
        "run_label": "Sample capture",
    },
    {
        "id": "nftables",
        "label": "nftables",
        "packages": ["nftables"],
        "bins": ["nft"],
        "hub": "security",
        "description": "Read kernel nft rules alongside UFW in Network diagnostics.",
        "used_by": "nftables diagnostic",
        "run_cmd": "sudo nft list ruleset",
        "run_label": "List rules",
    },
    {
        "id": "fail2ban",
        "label": "fail2ban",
        "packages": ["fail2ban"],
        "bins": ["fail2ban-client"],
        "hub": "security",
        "description": "Blocks repeated SSH/login abuse — status shown after install.",
        "used_by": "Intrusion prevention",
        "run_cmd": "sudo fail2ban-client status",
        "run_label": "fail2ban status",
    },
    {
        "id": "rkhunter",
        "label": "rkhunter",
        "packages": ["rkhunter"],
        "bins": ["rkhunter"],
        "hub": "security",
        "description": "Rootkit hunter — full check in terminal (may take several minutes).",
        "used_by": "Rootkit scan",
        "run_cmd": "sudo rkhunter --check --sk",
        "run_label": "Run rkhunter",
    },
    {
        "id": "lynis",
        "label": "Lynis audit",
        "packages": ["lynis"],
        "bins": ["lynis"],
        "hub": "security",
        "description": "System hardening audit — runs in terminal (may take several minutes).",
        "used_by": "Security audit",
        "run_cmd": "sudo lynis audit system",
        "run_label": "Run Lynis",
    },
    {
        "id": "chkrootkit",
        "label": "chkrootkit",
        "packages": ["chkrootkit"],
        "bins": ["chkrootkit"],
        "hub": "security",
        "description": "Lightweight rootkit check — runs in terminal.",
        "used_by": "Rootkit scan",
        "run_cmd": "sudo chkrootkit",
        "run_label": "Run chkrootkit",
    },
    {
        "id": "clamav",
        "label": "ClamAV",
        "packages": ["clamav"],
        "bins": ["clamscan"],
        "hub": "security",
        "description": "On-demand malware scan of your home folder.",
        "used_by": "Malware scan",
        "run_cmd": "clamscan -r --infected --remove=no ~",
        "run_label": "Scan home",
    },
    {
        "id": "libnotify",
        "label": "Desktop notifications",
        "packages": ["libnotify-bin"],
        "bins": ["notify-send"],
        "hub": "security",
        "description": "VPN disconnect alerts to the desktop tray.",
        "used_by": "Disconnect alerts",
    },
    {
        "id": "apparmor-utils",
        "label": "AppArmor",
        "packages": ["apparmor-utils"],
        "bins": ["aa-status"],
        "hub": "security",
        "description": "Mandatory access control status.",
        "used_by": "MAC / AppArmor",
        "run_cmd": "sudo aa-status",
        "run_label": "AppArmor status",
    },
    {
        "id": "auditd",
        "label": "auditd",
        "packages": ["auditd"],
        "bins": ["auditctl"],
        "hub": "security",
        "description": "Linux audit framework — who changed what on the system.",
        "used_by": "System auditing",
        "run_cmd": "sudo auditctl -s",
        "run_label": "Audit status",
    },
    {
        "id": "unattended-upgrades",
        "label": "Unattended upgrades",
        "packages": ["unattended-upgrades"],
        "bins": ["unattended-upgrade"],
        "hub": "security",
        "description": "Automatic security patch installs from Ubuntu archives.",
        "used_by": "Auto security updates",
        "run_cmd": "sudo unattended-upgrade --dry-run --debug",
        "run_label": "Dry-run upgrades",
    },
    {
        "id": "aide",
        "label": "AIDE",
        "packages": ["aide"],
        "bins": ["aide"],
        "hub": "security",
        "description": "File integrity monitoring — detects unexpected changes to system files.",
        "used_by": "Integrity checks",
        "run_cmd": "sudo aide --check",
        "run_label": "Integrity check",
    },
    {
        "id": "debsums",
        "label": "debsums",
        "packages": ["debsums"],
        "bins": ["debsums"],
        "hub": "security",
        "description": "Verify installed package files match Ubuntu archive checksums.",
        "used_by": "Package integrity",
        "run_cmd": "debsums -s 2>&1 | head -40",
        "run_label": "Check changed files",
    },
    {
        "id": "unhide",
        "label": "unhide",
        "packages": ["unhide"],
        "bins": ["unhide"],
        "hub": "security",
        "description": "Find hidden processes and rootkits using /proc and syscall tests.",
        "used_by": "Hidden process scan",
        "run_cmd": "sudo unhide proc",
        "run_label": "Scan for hidden procs",
    },
    {
        "id": "lsof",
        "label": "lsof",
        "packages": ["lsof"],
        "bins": ["lsof"],
        "hub": "security",
        "description": "List open files and network listeners — spot unexpected services.",
        "used_by": "Open files audit",
        "run_cmd": "lsof -i -P -n 2>/dev/null | head -30",
        "run_label": "Network listeners",
    },
    {
        "id": "usbguard",
        "label": "USBGuard",
        "packages": ["usbguard"],
        "bins": ["usbguard"],
        "hub": "security",
        "description": "Authorize or block USB devices — useful on laptops in untrusted places.",
        "used_by": "USB device policy",
        "run_cmd": "usbguard list-devices",
        "run_label": "List USB devices",
    },
    {
        "id": "needrestart",
        "label": "needrestart",
        "packages": ["needrestart"],
        "bins": ["needrestart"],
        "hub": "security",
        "description": "After apt upgrades, shows services still running old libraries.",
        "used_by": "Post-update restart check",
        "run_cmd": "sudo needrestart -b 2>&1 | head -40",
        "run_label": "Check stale services",
    },
    {
        "id": "firejail",
        "label": "Firejail",
        "packages": ["firejail"],
        "bins": ["firejail"],
        "hub": "security",
        "description": "Sandbox untrusted apps with Linux namespaces — reduces blast radius.",
        "used_by": "App sandboxing",
        "run_cmd": "firejail --list",
        "run_label": "Active sandboxes",
    },
    {
        "id": "libcap2-bin",
        "label": "File capabilities",
        "packages": ["libcap2-bin"],
        "bins": ["getcap"],
        "hub": "security",
        "description": "Audit Linux file capabilities (setcap) that can grant extra privileges.",
        "used_by": "Capability audit",
        "run_cmd": "getcap -r /usr/bin /usr/sbin 2>/dev/null | head -30",
        "run_label": "Scan capabilities",
    },
    {
        "id": "yara",
        "label": "YARA",
        "packages": ["yara"],
        "bins": ["yara"],
        "hub": "security",
        "description": "Pattern matching for malware research — pairs with ClamAV for custom rules.",
        "used_by": "Malware patterns",
        "run_cmd": "yara --version",
        "run_label": "YARA version",
    },
    {
        "id": "nikto",
        "label": "Nikto",
        "packages": ["nikto"],
        "bins": ["nikto"],
        "hub": "security",
        "description": "Well-known web server scanner — checks local HTTP services you run.",
        "used_by": "Web server scan",
        "run_cmd": "nikto -Version",
        "run_label": "Nikto version",
    },
    {
        "id": "openscap-scanner",
        "label": "OpenSCAP",
        "packages": ["openscap-scanner"],
        "bins": ["oscap"],
        "hub": "security",
        "description": "SCAP security compliance scanner — CIS/STIG-style checks on Ubuntu.",
        "used_by": "Compliance scan",
        "run_cmd": "oscap --version",
        "run_label": "OpenSCAP version",
    },
    {
        "id": "logwatch",
        "label": "logwatch",
        "packages": ["logwatch"],
        "bins": ["logwatch"],
        "hub": "security",
        "description": "Summarizes auth, sudo, and system logs — good daily hygiene check.",
        "used_by": "Log summary",
        "run_cmd": "sudo logwatch --output stdout --range today --detail low 2>&1 | head -60",
        "run_label": "Today's log summary",
    },
    {
        "id": "acct",
        "label": "Process accounting",
        "packages": ["acct"],
        "bins": ["lastcomm"],
        "hub": "security",
        "description": "Login and command accounting — see who ran what and when.",
        "used_by": "Login / command audit",
        "run_cmd": "lastcomm 2>/dev/null | head -25",
        "run_label": "Recent commands",
    },
    {
        "id": "sshguard",
        "label": "SSHGuard",
        "packages": ["sshguard"],
        "bins": ["sshguard"],
        "hub": "security",
        "description": "Lightweight SSH brute-force blocker — complements fail2ban on exposed hosts.",
        "used_by": "SSH intrusion block",
        "run_cmd": "systemctl is-active sshguard 2>/dev/null; sshguard -v 2>/dev/null | head -3",
        "run_label": "SSHGuard status",
    },
    {
        "id": "psad",
        "label": "psad",
        "packages": ["psad"],
        "bins": ["psad"],
        "hub": "security",
        "description": "Port scan attack detector — analyzes firewall logs for reconnaissance.",
        "used_by": "Scan detection",
        "run_cmd": "sudo psad --Status 2>/dev/null | head -30",
        "run_label": "psad status",
    },
    {
        "id": "hashdeep",
        "label": "hashdeep",
        "packages": ["hashdeep"],
        "bins": ["hashdeep"],
        "hub": "security",
        "description": "Recursive file hashing — baseline directories for unexpected changes.",
        "used_by": "File hash audit",
        "run_cmd": "hashdeep -v",
        "run_label": "hashdeep version",
    },
    {
        "id": "tiger",
        "label": "Tiger",
        "packages": ["tiger"],
        "bins": ["tiger"],
        "hub": "security",
        "description": "Classic Unix security audit — complementary checks to Lynis.",
        "used_by": "Security audit",
        "run_cmd": "sudo tiger -H 2>&1 | head -40",
        "run_label": "Run Tiger (preview)",
    },
    {
        "id": "psmisc",
        "label": "psmisc (fuser)",
        "packages": ["psmisc"],
        "bins": ["fuser"],
        "hub": "security",
        "description": "Find which process holds a port or file — investigate suspicious listeners.",
        "used_by": "Process / port audit",
        "run_cmd": "sudo fuser -v 22/tcp 2>&1 | head -15",
        "run_label": "Who uses SSH port",
    },
]

HUB_LABELS = {
    "network": {
        "title": "Networking tools",
        "summary": "Thirty optional packages for Audit diagnostics and the WiFi hub. "
        "Install what is missing — each card shows where it is used.",
    },
    "security": {
        "title": "Security tools",
        "summary": "Thirty packages for firewall, capture, audits, sandboxing, and alerts. "
        "Install what is missing — use Run in terminal for scans when installed.",
    },
    "custom": {
        "title": "Custom packages",
        "summary": "Your own apt packages and categories — separate from Networking and Security catalogs.",
    },
}

DEFAULT_PACKAGE_CATEGORIES: dict[str, list[dict[str, str]]] = {
    "network": [
        {"id": "recommended", "label": "Recommended packages"},
    ],
    "security": [
        {"id": "recommended", "label": "Recommended packages"},
    ],
}

DEFAULT_CUSTOM_PACKAGE_CATEGORIES: list[dict[str, str]] = [
    {"id": "miscellaneous", "label": "Miscellaneous"},
]

_BUILTIN_PACKAGE_CATEGORY_IDS = frozenset({"recommended", "my-packages"})
_BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS = frozenset({"miscellaneous"})


def _optional_tools_cfg(cfg: dict[str, Any]) -> dict[str, Any]:
    opt = cfg.setdefault("optional_tools", {"custom": []})
    if not isinstance(opt.get("custom"), list):
        opt["custom"] = []
    if not isinstance(opt.get("categories"), dict):
        opt["categories"] = {}
    if not isinstance(opt.get("package_categories"), list):
        opt["package_categories"] = []
    return opt


def _package_category_defs(cfg: dict[str, Any]) -> list[dict[str, str]]:
    opt = _optional_tools_cfg(cfg)
    stored = opt.get("package_categories") or []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for raw in stored:
        if not isinstance(raw, dict):
            continue
        cid = str(raw.get("id") or "").strip()
        label = str(raw.get("label") or "").strip()
        if not cid or not label or cid in seen:
            continue
        seen.add(cid)
        out.append({"id": cid, "label": label})
    if out:
        return out
    return [dict(c) for c in DEFAULT_CUSTOM_PACKAGE_CATEGORIES]


def _default_custom_package_category(cfg: dict[str, Any]) -> str:
    defs = _package_category_defs(cfg)
    for d in defs:
        if d["id"] == "miscellaneous":
            return "miscellaneous"
    return defs[0]["id"] if defs else "miscellaneous"


def _ensure_custom_packages_layout(cfg: dict[str, Any]) -> bool:
    """Migrate legacy shared categories and move all custom apt entries to Tools → Custom packages."""
    from nordctl.config import save_config

    opt = _optional_tools_cfg(cfg)
    changed = False
    legacy: dict[str, str] = {}
    cats = opt.setdefault("categories", {})
    for hub in ("network", "security"):
        hub_list = list(cats.get(hub) or [])
        kept: list[dict[str, str]] = []
        for raw in hub_list:
            if not isinstance(raw, dict):
                continue
            cid = str(raw.get("id") or "").strip()
            label = str(raw.get("label") or "").strip()
            if cid in _BUILTIN_PACKAGE_CATEGORY_IDS:
                kept.append({"id": cid, "label": label or cid})
            elif cid and label:
                legacy[cid] = label
                changed = True
        if len(kept) != len(hub_list):
            cats[hub] = kept
            changed = True

    pkg_cats = list(opt.get("package_categories") or [])
    known = {str(c.get("id") or "") for c in pkg_cats if isinstance(c, dict)}
    if "miscellaneous" not in known:
        pkg_cats.insert(0, {"id": "miscellaneous", "label": "Miscellaneous"})
        known.add("miscellaneous")
        changed = True
    for cid, label in legacy.items():
        if cid not in known:
            pkg_cats.append({"id": cid, "label": label})
            known.add(cid)
            changed = True
    opt["package_categories"] = pkg_cats

    default_cat = _default_custom_package_category(cfg)
    custom = list(opt.get("custom") or [])
    for item in custom:
        if not isinstance(item, dict):
            continue
        if str(item.get("hub") or "") != "custom":
            item["hub"] = "custom"
            changed = True
        cat = str(item.get("category") or "").strip()
        if cat in ("", "recommended", "my-packages") or cat not in known:
            item["category"] = default_cat
            changed = True
    if changed:
        opt["custom"] = custom
        save_config(cfg)
    return changed


def _hub_category_defs(cfg: dict[str, Any], hub_id: str) -> list[dict[str, str]]:
    if hub_id == "custom":
        return _package_category_defs(cfg)
    return [dict(c) for c in DEFAULT_PACKAGE_CATEGORIES.get(hub_id, [])]


def _tool_category_id(item: dict[str, Any]) -> str:
    if item.get("custom"):
        return str(item.get("category") or "my-packages")
    cat = str(item.get("category") or "").strip()
    if cat and cat not in ("network", "security", "other"):
        return cat
    return "recommended"


def _build_hub_categories(cfg: dict[str, Any], hub_id: str, hub_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    defs = _hub_category_defs(cfg, hub_id)
    buckets: dict[str, list[dict[str, Any]]] = {d["id"]: [] for d in defs}
    for row in hub_rows:
        cat = str(row.get("category") or "recommended")
        if cat not in buckets:
            buckets[cat] = []
            if not any(d["id"] == cat for d in defs):
                defs.append({"id": cat, "label": cat.replace("-", " ").title()})
        buckets[cat].append(row)
    assigned_ids = {t["id"] for tools in buckets.values() for t in tools}
    for row in hub_rows:
        if row["id"] not in assigned_ids:
            buckets.setdefault("recommended", []).append(row)
    out: list[dict[str, Any]] = []
    for d in defs:
        tools = buckets.get(d["id"], [])
        missing = sum(1 for t in tools if not t.get("installed"))
        out.append(
            {
                "id": d["id"],
                "label": d["label"],
                "shared": bool(d.get("shared")),
                "tools": tools,
                "total": len(tools),
                "missing_count": missing,
                "installed_count": len(tools) - missing,
                **(
                    {"deletable": d["id"] not in _BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS}
                    if hub_id == "custom"
                    else {}
                ),
            }
        )
    return out


def _slug(s: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", (s or "").lower()).strip("-")[:48]


def custom_tools(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    raw = (cfg.get("optional_tools") or {}).get("custom") or []
    out: list[dict[str, Any]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        tid = str(item.get("id") or "").strip().lower()
        label = str(item.get("label") or "").strip()
        pkgs = [str(p).strip() for p in (item.get("packages") or []) if str(p).strip()]
        if not tid or not label or not pkgs:
            continue
        hub = str(item.get("hub") or "custom").strip().lower()
        if hub not in ("network", "security", "custom"):
            hub = "custom"
        if hub != "custom":
            hub = "custom"
        bins = [str(b).strip() for b in (item.get("bins") or []) if str(b).strip()] or pkgs[:1]
        out.append(
            {
                "id": tid,
                "label": label,
                "packages": pkgs,
                "bins": bins,
                "hub": hub,
                "category": str(item.get("category") or "miscellaneous"),
                "description": str(item.get("description") or f"Custom package — {label}"),
                "used_by": str(item.get("used_by") or "Custom"),
                "run_cmd": str(item.get("run_cmd") or "").strip(),
                "run_label": str(item.get("run_label") or "").strip(),
                "custom": True,
            }
        )
    return out


def catalog_items(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    items = [dict(x) for x in TOOL_CATALOG]
    for c in custom_tools(cfg):
        items.append(c)
    return items


def _run(argv: list[str], timeout: float = 300.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _dedupe_pkgs(items: list[dict[str, Any]]) -> list[str]:
    pkgs: list[str] = []
    for item in items:
        for pkg in item.get("packages") or []:
            p = str(pkg).strip()
            if p and p not in pkgs:
                pkgs.append(p)
    return pkgs


def _apt_error_hints(out: str) -> list[str]:
    low = (out or "").lower()
    hints: list[str] = []
    if "could not get lock" in low or "unable to lock" in low:
        hints.append(
            "Another apt/dpkg process is running — wait for it to finish, then retry."
        )
    if "broken" in low or "unmet dependencies" in low or "dpkg:" in low:
        hints.append("Broken package state — nordctl will try apt --fix-broken install.")
    if "404" in out or "failed to fetch" in low or "hash sum mismatch" in low:
        hints.append("Package lists may be stale — nordctl will try apt update.")
    if "held packages" in low or "kept back" in low:
        hints.append(
            "Some packages are held back — run sudo apt install with the suggested packages, "
            "or upgrade held packages manually."
        )
    if not hints and out:
        hints.append("See output below — copy the manual command to Diagnostics → Shell if needed.")
    return hints


def _apt_install_pkgs(pkgs: list[str], *, timeout: float = 900.0) -> dict[str, Any]:
    manual = "sudo apt install -y " + " ".join(pkgs)
    if not pkgs:
        return {"ok": True, "output": "", "fixes_applied": [], "manual": manual}
    if not shutil.which("apt-get"):
        return {"ok": False, "error": "apt-get not found", "manual": manual}
    if not passwordless_sudo():
        return {
            "ok": False,
            "error": "Passwordless sudo required for web UI install",
            "manual": manual,
        }

    fixes: list[str] = []
    argv = ["sudo", "-n", "apt-get", "install", "-y", "-qq", *pkgs]
    ok, out = _run(argv, timeout=timeout)
    if ok:
        return {"ok": True, "output": out, "fixes_applied": fixes, "manual": manual}

    low = out.lower()
    if "broken" in low or "unmet dependencies" in low or "dpkg:" in low:
        fix_ok, fix_out = _run(["sudo", "-n", "apt-get", "install", "-y", "-f"], timeout=600)
        fixes.append("fix-broken")
        out = (fix_out + "\n" + out).strip()
        if fix_ok:
            ok, retry_out = _run(argv, timeout=timeout)
            out = (out + "\n" + retry_out).strip()
            if ok:
                return {
                    "ok": True,
                    "output": out,
                    "fixes_applied": fixes,
                    "manual": manual,
                    "note": "Repaired broken packages, then installed.",
                }

    if "404" in out or "failed to fetch" in low or "hash sum mismatch" in low:
        upd_ok, upd_out = _run(["sudo", "-n", "apt-get", "update", "-qq"], timeout=300)
        fixes.append("apt-update")
        out = (out + "\n" + upd_out).strip()
        if upd_ok:
            ok, retry_out = _run(argv, timeout=timeout)
            out = (out + "\n" + retry_out).strip()
            if ok:
                return {
                    "ok": True,
                    "output": out,
                    "fixes_applied": fixes,
                    "manual": manual,
                    "note": "Updated package lists, then installed.",
                }

    return {
        "ok": False,
        "error": (out.splitlines()[-1] if out else "apt install failed"),
        "output": out[-4000:] if out else "",
        "hints": _apt_error_hints(out),
        "fixes_applied": fixes,
        "manual": manual,
        "retry_cmd": (
            "sudo apt --fix-broken install -y && sudo apt update && "
            + manual.replace("sudo ", "", 1)
        ),
    }


def _apt_remove_pkgs(pkgs: list[str], *, timeout: float = 600.0) -> dict[str, Any]:
    manual = "sudo apt remove -y " + " ".join(pkgs)
    if not pkgs:
        return {"ok": True, "output": "", "manual": manual}
    if not shutil.which("apt-get"):
        return {"ok": False, "error": "apt-get not found", "manual": manual}
    if not passwordless_sudo():
        return {
            "ok": False,
            "error": "Passwordless sudo required for web UI uninstall",
            "manual": manual,
        }

    argv = ["sudo", "-n", "apt-get", "remove", "-y", "-qq", *pkgs]
    ok, out = _run(argv, timeout=timeout)
    if ok:
        return {"ok": True, "output": out, "manual": manual}

    low = out.lower()
    if "broken" in low or "dpkg:" in low:
        fix_ok, fix_out = _run(["sudo", "-n", "apt-get", "install", "-y", "-f"], timeout=600)
        out = (fix_out + "\n" + out).strip()
        if fix_ok:
            ok, retry_out = _run(argv, timeout=timeout)
            out = (out + "\n" + retry_out).strip()
            if ok:
                return {"ok": True, "output": out, "manual": manual, "note": "Repaired dpkg, then removed."}

    return {
        "ok": False,
        "error": (out.splitlines()[-1] if out else "apt remove failed"),
        "output": out[-4000:] if out else "",
        "hints": _apt_error_hints(out),
        "manual": manual,
    }


def _run_where(item: dict[str, Any]) -> dict[str, str]:
    tid = str(item.get("id") or "").lower()
    hub = str(item.get("hub") or "network")
    used = str(item.get("used_by") or "").lower()

    if item.get("custom") or hub == "custom":
        cat = str(item.get("category") or "miscellaneous")
        cat_label = cat.replace("-", " ").title()
        return {
            "label": f"Tools → Custom shell → {cat_label}",
            "route": f"tools/custom-shell/{cat}",
        }
    if tid == "ufw" or "ufw" in used or tid in ("nftables-net", "iptables", "nftables"):
        return {"label": "Network & Security → Linux UFW", "route": "network/host-ufw"}
    if tid == "network-manager" or "wifi" in used:
        return {"label": "Network & Security → WiFi", "route": "network/wifi/profiles"}
    if tid in ("tcpdump", "tshark", "wireshark-common") or "capture" in used or "packet" in used:
        return {"label": "Diagnostics → Shell (sudo for capture)", "route": "network/diagnostics/shell"}
    if hub == "security" or tid in (
        "lynis", "rkhunter", "chkrootkit", "clamav", "clamav-freshclam",
        "debsecan", "trivy", "openscap", "aide", "unhide", "fail2ban",
        "sshguard", "psad", "rkhunter",
    ) or any(x in used for x in ("lynis", "rootkit", "clam", "audit", "scan", "hardening")):
        return {
            "label": "Diagnostics → Shell or Network → Configuration",
            "route": "network/diagnostics/shell",
        }
    if "traffic" in used or tid in ("iftop", "vnstat", "nethogs"):
        return {"label": "Network & Security → Internet traffic", "route": "network/map-internet"}
    if tid == "iperf3":
        return {"label": "Network → Speed test", "route": "network/network/speed"}
    return {"label": "Network & Security → Diagnostics → Checks", "route": "network/diagnostics"}


def _tool_result_row(item: dict[str, Any]) -> dict[str, Any]:
    row = _row(item)
    return {
        "id": row["id"],
        "label": row["label"],
        "installed": row["installed"],
        "used_by": row["used_by"],
        "run_where": row["run_where"],
        "run_cmd": row["run_cmd"],
        "run_label": row["run_label"],
    }


def _tool_by_id(tool_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any] | None:
    tid = (tool_id or "").strip().lower()
    if tid == "wireshark-common":
        tid = "tshark"
    for item in catalog_items(cfg):
        if item["id"] == tid:
            return item
    return None


def _dpkg_installed(pkg: str) -> bool:
    try:
        r = subprocess.run(
            ["dpkg-query", "-W", "-f=${Status}", pkg],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    return r.returncode == 0 and "install ok installed" in (r.stdout or "").lower()


def _bin_exists(name: str) -> bool:
    if not name:
        return False
    if shutil.which(name):
        return True
    for base in ("/usr/bin", "/usr/sbin", "/bin", "/sbin", "/usr/local/bin"):
        path = Path(base) / name
        if path.is_file() and os.access(path, os.X_OK):
            return True
    return False


def _is_installed(item: dict[str, Any]) -> bool:
    bins = [str(b) for b in (item.get("bins") or []) if b]
    for name in bins:
        if _bin_exists(name):
            return True
    # wireshark-common alone does not ship the tshark binary — require the actual CLI.
    pkgs = [str(p) for p in (item.get("packages") or []) if p]
    if pkgs and bins and all(_dpkg_installed(p) for p in pkgs):
        return any(_bin_exists(b) for b in bins)
    return False


def _primary_bin(item: dict[str, Any]) -> str:
    for name in item.get("bins") or []:
        if _bin_exists(str(name)):
            return str(name)
    bins = list(item.get("bins") or [])
    return str(bins[0]) if bins else ""


def _help_cmd(bin_name: str) -> str:
    return f"{bin_name} --help 2>&1 | head -25"


# Basic one-shot demos when catalog has no explicit run_cmd.
_DEFAULT_PROGRAM_CMDS: dict[str, str] = {
    "curl": "curl -sS --max-time 5 https://ifconfig.me/ip",
    "dnsutils": "dig +short cloudflare.com A",
    "mtr": "mtr -r -c 3 -w 1.1.1.1",
    "iputils-ping": "ping -c 3 1.1.1.1",
    "net-tools": "netstat -tuln | head -25",
    "nmap": "nmap --version 2>&1 | head -12",
    "iperf3": "iperf3 --version 2>&1 | head -12",
    "whois": "whois example.com 2>&1 | head -20",
    "netcat": "nc -zv -w 3 1.1.1.1 443 2>&1",
    "network-manager": "nmcli general status",
    "iproute2": "ip -4 addr show scope global | head -20",
}

# Programs that need a real TTY to animate — show a static demo in the web shell.
_DEMO_PROGRAM_CMDS: dict[str, str] = {
    "sl": (
        "printf '%s\\n' '' "
        "'sl — Steam Locomotive (example)' "
        "'      oOOO OOo ooo' "
        "'     _|_|_|___' "
        "'    ( @ @ @  )   Needs a real terminal for animation — run `sl`' "
        "'   /---------\\  in your Linux console for the full train.' "
        "'  o===========o'"
    ),
}


def _default_program_cmd(item: dict[str, Any], bin_name: str) -> str:
    tid = str(item.get("id") or "").strip().lower()
    if tid in _DEFAULT_PROGRAM_CMDS:
        return _DEFAULT_PROGRAM_CMDS[tid]
    if bin_name in _DEMO_PROGRAM_CMDS:
        return _DEMO_PROGRAM_CMDS[bin_name]
    if item.get("custom"):
        return bin_name
    return f"{bin_name} --version 2>&1 | head -15"


def custom_package_quick_commands(category_id: str, cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Runnable quick-command rows for installed custom apt packages in one category."""
    cfg = cfg or load_config()
    cid = (category_id or "").strip()
    if not cid:
        return []
    out: list[dict[str, Any]] = []
    for item in custom_tools(cfg):
        if str(item.get("category") or "miscellaneous") != cid:
            continue
        row = _row(item)
        if not row.get("installed"):
            continue
        run_cmd = str(row.get("run_cmd") or "").strip()
        if not run_cmd:
            continue
        cmd = run_cmd if run_cmd.endswith("\n") else f"{run_cmd}\n"
        out.append(
            {
                "label": str(row.get("run_label") or row.get("label") or "Run").strip(),
                "cmd": cmd,
                "scope": f"custom:{cid}",
                "tool_id": row.get("id"),
                "from_package": True,
            }
        )
    out.sort(key=lambda c: str(c.get("label") or "").lower())
    return out


def custom_package_shell_categories(cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Custom shell tabs derived from Tools → Custom packages categories."""
    cfg = cfg or load_config()
    _ensure_custom_packages_layout(cfg)
    labels = {d["id"]: d["label"] for d in _package_category_defs(cfg)}
    packages_by_cat: dict[str, list[dict[str, Any]]] = {}
    for item in custom_tools(cfg):
        cat = str(item.get("category") or "miscellaneous")
        packages_by_cat.setdefault(cat, []).append(item)
    if not packages_by_cat:
        return []

    ordered_ids: list[str] = []
    seen: set[str] = set()
    for d in _package_category_defs(cfg):
        if d["id"] in packages_by_cat and d["id"] not in seen:
            ordered_ids.append(d["id"])
            seen.add(d["id"])
    for cat in sorted(packages_by_cat):
        if cat not in seen:
            ordered_ids.append(cat)
            seen.add(cat)

    out: list[dict[str, Any]] = []
    for cat_id in ordered_ids:
        tools = packages_by_cat.get(cat_id) or []
        if not tools:
            continue
        cmd_rows = [
            {
                "id": f"pkg-{pkg_row.get('tool_id') or _slug(str(pkg_row.get('label') or 'run'))}",
                "label": pkg_row["label"],
                "cmd": pkg_row["cmd"],
                "enabled": True,
                "from_package": True,
            }
            for pkg_row in custom_package_quick_commands(cat_id, cfg)
        ]
        out.append(
            {
                "id": cat_id,
                "label": labels.get(cat_id, cat_id.replace("-", " ").title()),
                "commands": cmd_rows,
                "from_packages": True,
                "package_count": len(tools),
            }
        )
    return out


def _row(item: dict[str, Any]) -> dict[str, Any]:
    installed = _is_installed(item)
    bins = list(item.get("bins") or [])
    primary = _primary_bin(item) if installed else (str(bins[0]) if bins else "")
    explicit_run = str(item.get("run_cmd") or "").strip()
    explicit_label = str(item.get("run_label") or "").strip()

    help_cmd = _help_cmd(primary) if primary else ""
    help_label = "Run help"

    if explicit_run:
        program_cmd = explicit_run
        program_label = explicit_label or "Run program"
    elif primary:
        program_cmd = _default_program_cmd(item, primary)
        if primary == "sl" and primary in _DEMO_PROGRAM_CMDS and not explicit_run:
            program_label = explicit_label or "Train (demo)"
        else:
            program_label = explicit_label or (str(item.get("label") or "").strip() if item.get("custom") else "Run program") or "Run program"
    else:
        program_cmd = ""
        program_label = ""

    return {
        "id": item["id"],
        "label": item["label"],
        "hub": item.get("hub") or "other",
        "category": _tool_category_id(item),
        "description": item.get("description") or "",
        "used_by": item.get("used_by") or "",
        "packages": list(item.get("packages") or []),
        "installed": installed,
        "install_cmd": "sudo apt install -y " + " ".join(item.get("packages") or []),
        "run_cmd": program_cmd,
        "run_label": program_label,
        "help_cmd": help_cmd,
        "help_label": help_label,
        "run_where": _run_where(item),
        "custom": bool(item.get("custom")),
    }


def _install_hint() -> str | None:
    apt_ok = shutil.which("apt-get") is not None
    if not apt_ok:
        return "These packages use apt on Debian/Ubuntu — copy a command if you use another distro."
    if not sudo_available():
        return "Install commands need sudo — copy a command and run it in a terminal."
    if not passwordless_sudo():
        return (
            "Use Install in terminal — you'll enter your sudo password in Diagnostics → Shell. "
            "Or copy a command and run it yourself."
        )
    return "Missing packages can be installed with one click below."


def tools_payload(*, hub: str | None = None, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    _ensure_custom_packages_layout(cfg)
    items = catalog_items(cfg)
    rows = [_row(item) for item in items]
    if hub:
        rows = [r for r in rows if r["hub"] == hub or (hub == "custom" and r.get("custom"))]

    groups: dict[str, Any] = {}
    for hub_id, meta in HUB_LABELS.items():
        if hub_id == "custom":
            hub_rows = [r for r in (_row(item) for item in items) if r.get("custom")]
        else:
            hub_rows = [
                r for r in (_row(item) for item in items)
                if r["hub"] == hub_id and not r.get("custom")
            ]
        missing = sum(1 for r in hub_rows if not r["installed"])
        groups[hub_id] = {
            "id": hub_id,
            "title": meta["title"],
            "summary": meta["summary"],
            "tools": hub_rows,
            "categories": _build_hub_categories(cfg, hub_id, hub_rows),
            "missing_count": missing,
            "installed_count": len(hub_rows) - missing,
            "total": len(hub_rows),
        }

    missing_all = sum(1 for r in (_row(item) for item in items) if not r["installed"])
    apt_ok = shutil.which("apt-get") is not None
    has_sudo = sudo_available()
    can_install_web = apt_ok and has_sudo and passwordless_sudo()
    can_install_terminal = apt_ok and has_sudo
    hint = _install_hint()

    return {
        "ok": True,
        "tools": rows,
        "groups": groups,
        "missing_count": missing_all,
        "can_install": can_install_web,
        "can_install_terminal": can_install_terminal,
        "install_mode": "web" if can_install_web else ("terminal" if can_install_terminal else "manual"),
        "install_hint": hint,
        "catalog_version": 8,
    }


def add_custom_tool(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    label = str(body.get("label") or "").strip()
    if not label:
        return {"ok": False, "error": "Label is required"}
    raw_pkg = body.get("packages") or body.get("package") or label
    if isinstance(raw_pkg, list):
        pkgs = [str(p).strip() for p in raw_pkg if str(p).strip()]
    else:
        pkgs = [p.strip() for p in str(raw_pkg).replace(",", " ").split() if p.strip()]
    if not pkgs:
        return {"ok": False, "error": "At least one apt package name is required"}
    base = _slug(label) or _slug(pkgs[0]) or "tool"
    tid = f"custom-{base}"
    existing = {t["id"] for t in custom_tools(cfg)}
    n = 2
    while tid in existing:
        tid = f"custom-{base}-{n}"
        n += 1
    default_cat = _default_custom_package_category(cfg)
    category = str(body.get("category") or default_cat).strip() or default_cat
    valid_cats = {d["id"] for d in _package_category_defs(cfg)}
    if category not in valid_cats:
        category = default_cat
    entry = {
        "id": tid,
        "label": label,
        "packages": pkgs,
        "bins": [str(b).strip() for b in (body.get("bins") or []) if str(b).strip()] or pkgs[:1],
        "hub": "custom",
        "category": category,
        "description": str(body.get("description") or f"Custom — {label}"),
        "used_by": str(body.get("used_by") or "Custom"),
        "custom": True,
    }
    run_cmd = str(body.get("run_cmd") or "").strip()
    if run_cmd:
        entry["run_cmd"] = run_cmd
        entry["run_label"] = str(body.get("run_label") or "Run in terminal")
    opt = cfg.setdefault("optional_tools", {"custom": []})
    custom = list(opt.get("custom") or [])
    custom.append(entry)
    opt["custom"] = custom
    save_config(cfg)
    return {"ok": True, "tool": entry, "tools": tools_payload(cfg=cfg)}


def remove_custom_tool(tool_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    tid = (tool_id or "").strip().lower()
    if not tid.startswith("custom-"):
        return {"ok": False, "error": "Only custom tools can be removed from here"}
    opt = cfg.setdefault("optional_tools", {"custom": []})
    before = list(opt.get("custom") or [])
    after = [t for t in before if str((t or {}).get("id") or "").lower() != tid]
    if len(after) == len(before):
        return {"ok": False, "error": f"unknown custom tool: {tid}"}
    opt["custom"] = after
    save_config(cfg)
    return {"ok": True, "removed": tid, "tools": tools_payload(cfg=cfg)}


def _hub_items(hub: str, cfg: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    cfg = cfg or load_config()
    if hub == "custom":
        return custom_tools(cfg)
    return [
        item
        for item in catalog_items(cfg)
        if (item.get("hub") or "other") == hub and not item.get("custom")
    ]


def install_hub_tools(hub: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    hub = (hub or "").strip().lower()
    if hub not in HUB_LABELS:
        return {"ok": False, "error": f"unknown hub: {hub}"}
    items = _hub_items(hub, cfg)
    missing = [item for item in items if not _is_installed(item)]
    if not missing:
        return {
            "ok": True,
            "already": True,
            "message": "All tools in this tab are already installed.",
            "tools": tools_payload(cfg=cfg),
            "hub": hub,
        }

    pkgs = _dedupe_pkgs(missing)
    apt = _apt_install_pkgs(pkgs, timeout=900)
    if not apt.get("ok"):
        return {**apt, "tools": tools_payload(cfg=cfg), "hub": hub}

    from nordctl.activity_log import record_event

    installed_now = [item for item in missing if _is_installed(item)]
    still_missing = [item for item in missing if not _is_installed(item)]
    labels = ", ".join(item["label"] for item in installed_now[:6])
    if len(installed_now) > 6:
        labels += f" (+{len(installed_now) - 6} more)"
    record_event(
        "install",
        f"Installed {len(installed_now)} tool(s) — {hub}",
        detail=apt.get("manual") or "",
        level="info",
        ok=True,
        meta={"hub": hub, "tool_ids": [i["id"] for i in installed_now], "packages": pkgs},
    )
    msg = apt.get("note") or f"Installed {len(installed_now)} package(s) in {HUB_LABELS[hub]['title']}."
    if still_missing:
        msg += f" {len(still_missing)} still missing — check output and retry."
    return {
        "ok": not still_missing,
        "partial": bool(still_missing),
        "message": msg,
        "output": (apt.get("output") or "")[-2000:],
        "tools": tools_payload(cfg=cfg),
        "hub": hub,
        "installed_count": len(installed_now),
        "installed": [_tool_result_row(i) for i in installed_now],
        "failed": [_tool_result_row(i) for i in still_missing],
        "fixes_applied": apt.get("fixes_applied") or [],
        "where_to_run": [_tool_result_row(i)["run_where"] for i in installed_now[:8]],
    }


def install_tools_batch(tool_ids: list[str], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ids = [str(x or "").strip().lower() for x in (tool_ids or []) if str(x or "").strip()]
    if not ids:
        return {"ok": False, "error": "No tools selected"}

    items: list[dict[str, Any]] = []
    unknown: list[str] = []
    for tid in ids:
        item = _tool_by_id(tid, cfg)
        if not item:
            unknown.append(tid)
            continue
        items.append(item)
    if unknown:
        return {"ok": False, "error": f"Unknown tool(s): {', '.join(unknown)}"}
    if not items:
        return {"ok": False, "error": "No installable tools in selection"}

    missing = [item for item in items if not _is_installed(item)]
    already = [item for item in items if _is_installed(item)]
    if not missing:
        return {
            "ok": True,
            "already": True,
            "message": "Selected tools are already installed.",
            "tools": tools_payload(cfg=cfg),
            "installed": [_tool_result_row(i) for i in already],
        }

    pkgs = _dedupe_pkgs(missing)
    apt = _apt_install_pkgs(pkgs, timeout=900)
    if not apt.get("ok"):
        return {**apt, "tools": tools_payload(cfg=cfg), "failed_ids": [i["id"] for i in missing]}

    from nordctl.activity_log import record_event

    installed_now = [item for item in missing if _is_installed(item)]
    still_missing = [item for item in missing if not _is_installed(item)]
    record_event(
        "install",
        f"Batch install {len(installed_now)} tool(s)",
        detail=apt.get("manual") or "",
        level="info",
        ok=not still_missing,
        meta={"tool_ids": [i["id"] for i in installed_now], "packages": pkgs},
    )
    rows = [_tool_result_row(i) for i in installed_now]
    msg = apt.get("note") or f"Installed {len(installed_now)} of {len(missing)} selected tool(s)."
    if still_missing:
        msg += f" {len(still_missing)} failed — see details below."
    return {
        "ok": not still_missing,
        "partial": bool(still_missing),
        "message": msg,
        "output": (apt.get("output") or "")[-3000:],
        "tools": tools_payload(cfg=cfg),
        "installed_count": len(installed_now),
        "installed": rows,
        "failed": [_tool_result_row(i) for i in still_missing],
        "already_installed": [_tool_result_row(i) for i in already],
        "fixes_applied": apt.get("fixes_applied") or [],
        "hints": apt.get("hints") or [],
        "retry_cmd": apt.get("retry_cmd"),
    }


def uninstall_tools_batch(tool_ids: list[str], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    ids = [str(x or "").strip().lower() for x in (tool_ids or []) if str(x or "").strip()]
    if not ids:
        return {"ok": False, "error": "No tools selected"}

    items: list[dict[str, Any]] = []
    for tid in ids:
        item = _tool_by_id(tid, cfg)
        if not item:
            return {"ok": False, "error": f"Unknown tool: {tid}"}
        if item.get("custom"):
            return {"ok": False, "error": f"{tid} is custom — remove it from Your tools instead"}
        items.append(item)

    present = [item for item in items if _is_installed(item)]
    if not present:
        return {
            "ok": True,
            "already": True,
            "message": "Selected tools are not installed.",
            "tools": tools_payload(cfg=cfg),
        }

    pkgs = _dedupe_pkgs(present)
    apt = _apt_remove_pkgs(pkgs, timeout=600)
    if not apt.get("ok"):
        return {**apt, "tools": tools_payload(cfg=cfg)}

    from nordctl.activity_log import record_event

    removed = [item for item in present if not _is_installed(item)]
    still_there = [item for item in present if _is_installed(item)]
    record_event(
        "install",
        f"Batch removed {len(removed)} tool(s)",
        detail=apt.get("manual") or "",
        level="info",
        ok=not still_there,
        meta={"tool_ids": [i["id"] for i in removed], "packages": pkgs},
    )
    msg = apt.get("note") or f"Removed {len(removed)} package(s)."
    if still_there:
        msg += f" {len(still_there)} still installed."
    return {
        "ok": not still_there,
        "partial": bool(still_there),
        "message": msg,
        "output": (apt.get("output") or "")[-3000:],
        "tools": tools_payload(cfg=cfg),
        "removed_count": len(removed),
        "removed": [_tool_result_row(i) for i in removed],
        "failed": [_tool_result_row(i) for i in still_there],
        "hints": apt.get("hints") or [],
    }


def uninstall_tool(tool_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    item = _tool_by_id(tool_id, cfg)
    if not item:
        return {"ok": False, "error": f"unknown tool: {tool_id}"}
    if item.get("custom"):
        return remove_custom_tool(tool_id, cfg)

    if not _is_installed(item):
        return {
            "ok": True,
            "already": True,
            "message": f"{item['label']} is not installed.",
            "tools": tools_payload(cfg=cfg),
        }

    pkgs = list(item.get("packages") or [])
    apt = _apt_remove_pkgs(pkgs, timeout=600)
    if not apt.get("ok"):
        return {**apt, "tools": tools_payload(cfg=cfg), "hub": item.get("hub")}
    out = apt.get("output") or ""
    manual = apt.get("manual") or ("sudo apt remove -y " + " ".join(pkgs))

    from nordctl.activity_log import record_event

    record_event(
        "install",
        f"Removed {item['label']}",
        detail=manual,
        level="info",
        ok=True,
        meta={"tool_id": item["id"], "packages": pkgs, "hub": item.get("hub")},
    )
    return {
        "ok": True,
        "message": f"{item['label']} removed — refresh panels if a feature stops working.",
        "output": out[-2000:] if out else "",
        "tools": tools_payload(cfg=cfg),
        "hub": item.get("hub"),
    }


def install_tool(tool_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    item = _tool_by_id(tool_id, cfg)
    if not item:
        return {"ok": False, "error": f"unknown tool: {tool_id}"}
    if _is_installed(item):
        return {
            "ok": True,
            "already": True,
            "message": f"{item['label']} is already installed.",
            "tools": tools_payload(cfg=cfg),
        }

    pkgs = list(item.get("packages") or [])
    apt = _apt_install_pkgs(pkgs, timeout=600)
    if not apt.get("ok"):
        return {**apt, "tools": tools_payload(cfg=cfg), "hub": item.get("hub")}
    out = apt.get("output") or ""
    manual = apt.get("manual") or ("sudo apt install -y " + " ".join(pkgs))

    from nordctl.activity_log import record_event

    record_event(
        "install",
        f"Installed {item['label']}",
        detail=manual,
        level="info",
        ok=True,
        meta={"tool_id": item["id"], "packages": pkgs, "hub": item.get("hub")},
    )
    row = _tool_result_row(item)
    note = apt.get("note") or f"{item['label']} installed — refreshing panels…"
    return {
        "ok": True,
        "message": note,
        "output": out[-2000:] if out else "",
        "tools": tools_payload(cfg=cfg),
        "hub": item.get("hub"),
        "installed": [row],
        "run_where": row.get("run_where"),
        "fixes_applied": apt.get("fixes_applied") or [],
    }


def tool_installed(tool_id: str, cfg: dict[str, Any] | None = None) -> bool:
    item = _tool_by_id(tool_id, cfg)
    return bool(item and _is_installed(item))


def add_tool_category(body: dict[str, Any], cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    _ensure_custom_packages_layout(cfg)
    label = str(body.get("label") or "").strip()
    if not label:
        return {"ok": False, "error": "Category label is required"}
    cid = str(body.get("id") or _slug(label)).strip() or _slug(label)
    if not cid:
        return {"ok": False, "error": "Could not derive category id"}
    if cid in _BUILTIN_PACKAGE_CATEGORY_IDS or cid in _BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS:
        return {"ok": False, "error": "That category id is reserved"}
    opt = _optional_tools_cfg(cfg)
    pkg_cats = list(opt.get("package_categories") or [])
    for existing in pkg_cats:
        if str(existing.get("id") or "") == cid:
            return {"ok": False, "error": f"Category already exists: {label}"}
    entry = {"id": cid, "label": label}
    pkg_cats.append(entry)
    opt["package_categories"] = pkg_cats
    save_config(cfg)
    return {"ok": True, "category": {"id": cid, "label": label}, "tools": tools_payload(cfg=cfg)}


def remove_tool_category(category_id: str, cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    cfg = cfg or load_config()
    cid = (category_id or "").strip()
    if not cid:
        return {"ok": False, "error": "Category id is required"}
    if cid in _BUILTIN_PACKAGE_CATEGORY_IDS or cid in _BUILTIN_CUSTOM_PACKAGE_CATEGORY_IDS:
        return {"ok": False, "error": "Built-in categories cannot be removed"}
    opt = _optional_tools_cfg(cfg)
    before = list(opt.get("package_categories") or [])
    after = [c for c in before if str((c or {}).get("id") or "") != cid]
    if len(after) == len(before):
        return {"ok": False, "error": f"Unknown category: {cid}"}
    removed_cat = next(
        (c for c in before if str((c or {}).get("id") or "") == cid),
        {"id": cid, "label": cid},
    )
    removed_packages: list[dict[str, str]] = []
    custom = list(opt.get("custom") or [])
    kept: list[dict[str, Any]] = []
    for item in custom:
        if not isinstance(item, dict):
            continue
        if str(item.get("category") or "") == cid:
            removed_packages.append(
                {
                    "id": str(item.get("id") or ""),
                    "label": str(item.get("label") or item.get("id") or ""),
                }
            )
            continue
        kept.append(item)
    opt["package_categories"] = after
    opt["custom"] = kept
    save_config(cfg)
    pkg_n = len(removed_packages)
    note = (
        f"Removed category “{removed_cat.get('label') or cid}”"
        + (f" and {pkg_n} package entr{'y' if pkg_n == 1 else 'ies'}" if pkg_n else "")
        + " from config — apt packages stay installed on the system."
    )
    return {
        "ok": True,
        "removed": cid,
        "removed_packages": removed_packages,
        "removed_package_count": pkg_n,
        "note": note,
        "tools": tools_payload(cfg=cfg),
    }


def move_custom_tool_category(
    tool_id: str, category: str, cfg: dict[str, Any] | None = None
) -> dict[str, Any]:
    cfg = cfg or load_config()
    tid = (tool_id or "").strip().lower()
    cat = (category or "").strip()
    if not tid.startswith("custom-"):
        return {"ok": False, "error": "Only custom packages can be moved between categories"}
    if not cat:
        return {"ok": False, "error": "Category is required"}
    opt = _optional_tools_cfg(cfg)
    custom = list(opt.get("custom") or [])
    found = False
    for item in custom:
        if not isinstance(item, dict):
            continue
        if str(item.get("id") or "").lower() != tid:
            continue
        item["category"] = cat
        found = True
        break
    if not found:
        return {"ok": False, "error": f"Unknown custom tool: {tid}"}
    opt["custom"] = custom
    save_config(cfg)
    return {"ok": True, "tool": tid, "category": cat, "tools": tools_payload(cfg=cfg)}
