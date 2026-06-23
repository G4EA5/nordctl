<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Community presets

Shareable preset YAML files for common scenarios. These ship with nordctl and can be copied to `~/.config/nordctl/presets/` to customize.

## Contributing

1. Use neutral labels (no streaming brand names — see LEGAL.md).
2. Include `id`, `label`, `summary`, `category`, and a `steps:` list.
3. Test with `nordctl apply --dry-run your-preset-id`.
4. Open a pull request adding one file under `presets/community/`.

## Import in the UI

**Dashboard → Workflows → Community presets** — paste a raw GitHub URL to a `.yaml` file, or use:

```bash
nordctl community import 'https://raw.githubusercontent.com/.../my-preset.yaml'
```

Imported presets are saved under `~/.config/nordctl/presets/`.
