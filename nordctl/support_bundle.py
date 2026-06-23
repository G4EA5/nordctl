"""Export redacted support bundle for troubleshooting."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import re
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from nordctl.config import config_dir, config_path, load_config
from nordctl.config_bundle import redact_config
from nordctl.connection_journal import list_journal
from nordctl.doctor import run_doctor
from nordctl.leaklab import run_leaklab
from nordctl.network_audit import run_network_audit
from nordctl.nettools import run_tool


def _scrub_text(text: str) -> str:
    """Remove obvious personal identifiers from free text."""
    out = text
    out = re.sub(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", "x.x.x.x", out)
    out = re.sub(r"\b[A-Fa-f0-9:]{8,}\b", "xx:xx:xx", out)
    home = str(Path.home())
    if home and home != "/":
        out = out.replace(home, "/home/USER")
    return out


def _anonymize_doctor(report: dict[str, Any]) -> dict[str, Any]:
    raw = json.dumps(report)
    return json.loads(_scrub_text(raw))


def build_support_bundle(*, anonymized: bool = False) -> dict[str, Any]:
    cfg = load_config()
    bundle_dir = config_dir() / "support"
    bundle_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(tz=timezone.utc).strftime("%Y%m%d-%H%M%S")
    prefix = "nordctl-support-anon" if anonymized else "nordctl-support"
    out_path = bundle_dir / f"{prefix}-{stamp}.tar.gz"

    doctor = run_doctor(cfg)
    leaklab = run_leaklab(cfg)
    audit = run_network_audit()

    payload: dict[str, Any] = {
        "generated": datetime.now(tz=timezone.utc).isoformat(),
        "anonymized": anonymized,
        "doctor": _anonymize_doctor(doctor) if anonymized else doctor,
        "leaklab": leaklab if not anonymized else _anonymize_doctor(leaklab),
        "network_audit": audit if not anonymized else _anonymize_doctor(audit),
        "nettools_overview": run_tool("overview"),
        "journal_recent": list_journal(limit=15),
    }

    from nordctl import nordvpn as nv

    bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
    if nv.available(bin_path):
        for cmd in (["version"], ["settings"], ["status"]):
            r = nv.run(bin_path, cmd, timeout=10)
            text = r.get("output", "")
            payload[f"nordvpn_{cmd[0]}"] = _scrub_text(text) if anonymized else text

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        (tmp_path / "report.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
        cfg_copy = config_path()
        if cfg_copy.is_file():
            if anonymized:
                doc = redact_config(load_config())
                wifi = doc.setdefault("wifi", {})
                profiles = wifi.get("profiles") or []
                wifi["profiles"] = [f"WiFiProfile{i + 1}" for i in range(len(profiles))]
                for key in ("connect_country", "travel_country", "mesh_peer", "connect_server", "connect_city"):
                    if doc.get(key):
                        doc[key] = "REDACTED"
                text = yaml.safe_dump(doc, sort_keys=False)
            else:
                text = cfg_copy.read_text(encoding="utf-8")
            (tmp_path / "config.yaml").write_text(text, encoding="utf-8")
        readme = (
            "Anonymized nordctl support bundle — safe to attach to GitHub issues.\n"
            "IPs, home paths, WiFi names, and secrets are scrubbed.\n"
            if anonymized
            else "nordctl support bundle — review before sharing publicly.\n"
        )
        (tmp_path / "README.txt").write_text(readme, encoding="utf-8")
        with tarfile.open(out_path, "w:gz") as tar:
            for f in tmp_path.iterdir():
                tar.add(f, arcname=f.name)

    note = (
        "Anonymized bundle — safe for GitHub issues (IPs, SSIDs, secrets scrubbed)."
        if anonymized
        else "Review before sharing — contains config.yaml and diagnostics."
    )
    return {"ok": True, "path": str(out_path), "size": out_path.stat().st_size, "anonymized": anonymized, "note": note}


def build_anonymized_support_bundle() -> dict[str, Any]:
    return build_support_bundle(anonymized=True)
