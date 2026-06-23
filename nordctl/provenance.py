"""Canonical source identity — search for SOURCE_ID if you need to verify copy origin."""

from __future__ import annotations

# Unique per-repository marker. Grep clones or paste into GitHub search: NCTL-src-a7f3c912-6e4b-5d8a
SOURCE_ID = "NCTL-src-a7f3c912-6e4b-5d8a"
SOURCE_MARKER = f"nordctl-src-id:{SOURCE_ID}"
COPYRIGHT_HOLDER = "G4EA5"
REPOSITORY_URL = "https://github.com/G4EA5/nordctl"
LICENSE = "MIT"


def provenance_payload() -> dict[str, str]:
    return {
        "ok": True,
        "source_id": SOURCE_ID,
        "source_marker": SOURCE_MARKER,
        "copyright": COPYRIGHT_HOLDER,
        "repository": REPOSITORY_URL,
        "license": LICENSE,
        "note": "If you find this ID in an unexpected fork or mirror, it originated from the nordctl repository above.",
    }
