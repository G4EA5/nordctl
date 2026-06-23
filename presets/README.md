<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Preset catalog

nordctl ships **58 presets** covering common NordVPN scenarios. Add your own YAML files to `~/.config/nordctl/presets/` (set `presets_dir` in config) or copy from this directory.

## Step actions (for custom presets)

| Action | Purpose |
|--------|---------|
| `nordvpn_disconnect` | `nordvpn disconnect` |
| `nordvpn_connect` | Connect (optional `target`, `group`) |
| `nordvpn_reconnect` | Disconnect then connect |
| `nordvpn_set` | Single `set` (`key`, `value`, optional `extra`) |
| `nordvpn_settings` | Batch `settings:` map |
| `nordvpn_args` | Safe raw args list (validated) |
| `network_smart_dns` | Apply Smart DNS on WiFi profiles |
| `network_restore_dns` | Restore router DNS |
| `allowlist_subnet` | Allowlist one CIDR |
| `allowlist_subnets_from_config` | All `allowlist_subnets` in config |
| `allowlist_ports` | Ports list or `from_config` key |
| `allowlist_voip_ports` | Uses `voip_ports` from config |
| `meshnet_peer_connect` | Route via `mesh_peer` |

Placeholders: `{connect_country}`, `{travel_country}`, `{gaming_country}`, `{work_country}`, `{connect_server}`, `{connect_city}`, `{lan_allowlist_cidr}`, `{mesh_peer}`, `{custom_dns}`.

## Categories

- **Basics** — disconnect, restore defaults  
- **Streaming** — TV streaming Smart DNS / VPN  
- **Connect** — full VPN, reconnect, server, city  
- **Server groups** — P2P, Double VPN, Onion, Dedicated IP, Standard  
- **Technology** — NordLynx, OpenVPN, NordWhisper, post-quantum  
- **Security** — kill switch, firewall, public Wi‑Fi  
- **Privacy** — threat protection, analytics, privacy max  
- **DNS** — Nord DNS, custom DNS, Smart DNS  
- **Meshnet** — mesh-only, peer routing, on/off  
- **Split tunnel** — LAN allowlist, work VPN  
- **Settings** — auto-connect, notifications, tray, LAN discovery, virtual locations  
- **Performance** — gaming, minimal overhead, VoIP  
- **Advanced** — routing, ARP ignore  

## Advanced CLI (anything else)

Safe direct commands:

```bash
nordctl run set technology NORDLYNX
nordctl run connect United_Kingdom
nordctl run allowlist add subnet 192.168.0.0/16
```

Blocked: `login`, `logout`, `register`.

## Example custom preset

Save as `~/.config/nordctl/presets/my-home.yaml`:

```yaml
id: my-home
label: My home setup
category: Custom
summary: Connect to my country with LAN allowlisted
requires:
  - connect_country
steps:
  - action: network_restore_dns
  - action: allowlist_subnet
    cidr: "{lan_allowlist_cidr}"
  - action: nordvpn_settings
    settings:
      meshnet: "on"
      lan-discovery: "on"
      firewall: "off"
  - action: nordvpn_connect
    target: "{connect_country}"
```
