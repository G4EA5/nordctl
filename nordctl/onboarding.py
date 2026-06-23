"""First-run onboarding — CLI and API shared logic.

Planned: slim install (3 choices) + dashboard welcome wizard for WiFi, country, etc.
See docs/INSTALL_WIZARD.md — current module picker remains until that ships.
"""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

from typing import Any

from nordctl.features import apply_modules, enable_all_modules, features_payload, get_enabled_modules, is_returning_user, module_catalog


def onboard_interactive() -> dict[str, Any]:
    """Terminal module picker after install."""
    print("")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  nordctl — choose feature modules")
    print("  (100% open source · MIT · local-only by default)")
    print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    print("  a) All modules (recommended — full hub)")
    print("  c) Choose each module individually")
    print("  m) Minimal — dashboard, lab, help, logs only")
    print("")
    pick = input("Your choice [a/c/m] (default a): ").strip().lower() or "a"

    if pick in ("a", "n", "t"):
        from nordctl.config import load_config, save_config

        cfg = load_config()
        cfg["usage_mode"] = "vpn"
        cfg["install_profile"] = "full"
        save_config(cfg)
        return enable_all_modules(complete=True)

    if pick == "m":
        minimal = {m["id"]: m["id"] in ("dashboard", "lab", "help", "logs", "editor") for m in module_catalog()}
        return apply_modules(minimal, legal_accepted=True, complete=True)

    selected: dict[str, bool] = {}
    print("\nToggle each module (y/n, Enter = default yes except alerts/traffic):")
    for m in module_catalog():
        if m.get("required"):
            selected[m["id"]] = True
            continue
        default = m["id"] not in ("alerts", "traffic", "services")
        hint = "Y/n" if default else "y/N"
        reply = input(f"  {m.get('emoji', '')} {m['label']}? [{hint}] ").strip().lower()
        if not reply:
            selected[m["id"]] = default
        else:
            selected[m["id"]] = reply in ("y", "yes", "1")
    print("\nBy continuing you accept LEGAL.md (not legal advice — comply with local law & Nord terms).")
    accept = input("Accept disclaimer and save? [Y/n] ").strip().lower()
    if accept in ("n", "no"):
        return {"ok": False, "error": "Onboarding cancelled — run nordctl onboard later"}
    return apply_modules(selected, legal_accepted=True, complete=True)


def onboard_payload(cfg: dict[str, Any] | None = None) -> dict[str, Any]:
    from nordctl.config import load_config
    from nordctl.privacy import privacy_manifest
    from nordctl.roadmap import roadmap_payload

    cfg = cfg or load_config()
    return {
        "ok": True,
        "returning_user": is_returning_user(cfg),
        "features": features_payload(cfg),
        "privacy": privacy_manifest(cfg),
        "roadmap": roadmap_payload(cfg),
        "legal_excerpt": (
            "nordctl is independent open-source software (MIT). Not affiliated with Nord Security. "
            "You are responsible for compliance with law and service terms. Smart DNS presets are technical configuration only."
        ),
    }
