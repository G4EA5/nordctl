<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Preset hooks

Run your own scripts **before** or **after** a preset applies — useful for notifications, backups, or custom automation.

## Directory layout

```
~/.config/nordctl/hooks/
├── pre-preset/
│   ├── default          # runs before every preset (executable)
│   └── streaming-smartdns   # runs only for that preset id
└── post-preset/
    └── default
```

Override the root with `hooks_dir:` in `config.yaml`. Disable all hooks with `hooks_enabled: false`.

## Script requirements

- File must be **executable** (`chmod +x script`)
- Name = preset id (e.g. `streaming-smartdns`) or `default`
- Optional `.sh` suffix
- **Pre-preset**: non-zero exit code **blocks** the preset
- **Post-preset**: exit code is logged only

## Environment variables

| Variable | Description |
|----------|-------------|
| `NORDCTL_PRESET` | Preset id being applied |
| `NORDCTL_HOOK_PHASE` | `pre` or `post` |
| `NORDCTL_PRESET_OK` | `1` or `0` (post hooks only) |

## Example: notify on TV preset

```bash
#!/usr/bin/env bash
# ~/.config/nordctl/hooks/post-preset/streaming-smartdns
notify-send "nordctl" "Smart DNS preset applied"
```

## Example: block apply on untrusted WiFi

```bash
#!/usr/bin/env bash
# ~/.config/nordctl/hooks/pre-preset/default
ssid=$(nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2)
if [[ "$ssid" != "MyHomeWiFi" && "$ssid" != "MyHomeWiFi-5G" ]]; then
  echo "Refusing preset on SSID: $ssid" >&2
  exit 1
fi
```

## API

`GET /api/hooks` — list configured hook scripts.

Hooks are **not** shipped in the repository; only this documentation and optional examples under `examples/hooks/`.
