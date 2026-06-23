# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# Example post-preset hook — copy to ~/.config/nordctl/hooks/post-preset/default
set -euo pipefail
logger -t nordctl "Preset ${NORDCTL_PRESET:-?} applied (ok=${NORDCTL_PRESET_OK:-?})"
