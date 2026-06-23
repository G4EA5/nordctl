"""Command-line interface."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import argparse
import json
import sys

from nordctl import __version__
from nordctl.provenance import SOURCE_ID
from nordctl.config import config_path, ensure_user_config, load_config
from nordctl.presets import apply_preset, load_presets
from nordctl.server import run_server
from nordctl.state import build_state


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="nordctl",
        description="Preset-driven NordVPN control for Linux",
    )
    parser.add_argument("--version", action="version", version=f"nordctl {__version__} · {SOURCE_ID}")

    sub = parser.add_subparsers(dest="command")

    p_init = sub.add_parser("init", help="Create config and pick a free UI port")
    p_init.add_argument(
        "--fix-port",
        action="store_true",
        help="If configured UI port is busy, update config with the next free port",
    )
    p_init.add_argument("--skip-onboard", action="store_true", help="Do not prompt for feature modules")
    p_init.add_argument(
        "--full",
        action="store_true",
        help="Enable all modules (legacy default); without this, minimal VPN profile is applied",
    )
    p_init.add_argument(
        "--headless",
        action="store_true",
        help="Server/VPS profile: API + CLI, no tray or browser alerts",
    )

    p_onboard = sub.add_parser("onboard", help="First-run module picker (features & legal accept)")
    p_onboard.add_argument("--all", action="store_true", help="Enable all modules")
    p_onboard.add_argument("--json", action="store_true")
    p_onboard.add_argument("--non-interactive", action="store_true", help="Use defaults without prompts")

    p_status = sub.add_parser("status", help="Show VPN and Smart DNS status")
    p_status.add_argument("--json", action="store_true", help="JSON output")

    p_list = sub.add_parser("presets", help="List available presets")
    p_list.add_argument("--json", action="store_true")

    p_apply = sub.add_parser("apply", help="Apply a preset by id")
    p_apply.add_argument("preset", help="Preset id (e.g. streaming-smartdns)")
    p_apply.add_argument("--dry-run", action="store_true", help="Preview steps without applying")
    p_apply.add_argument("--no-verify", action="store_true", help="Skip post-apply verification checks")
    p_apply.add_argument("--json", action="store_true")

    p_serve = sub.add_parser("serve", help="Run local web UI")
    p_serve.add_argument("--bind", default=None, help="Bind address (default from config)")
    p_serve.add_argument("--port", type=int, default=None, help="Port (default from config)")
    p_serve.add_argument("--demo", action="store_true", help="Demo mode — simulated VPN, no real changes")

    p_demo = sub.add_parser("demo", help="Run web UI in demo mode (no NordVPN required)")
    p_demo.add_argument("--bind", default="127.0.0.1", help="Bind address")
    p_demo.add_argument("--port", type=int, default=None, help="Port (default from config or 8765)")
    p_demo.add_argument("--json", action="store_true", help="Print URL and exit without serving")

    p_config = sub.add_parser("config", help="Export or import configuration bundle")
    p_config_sub = p_config.add_subparsers(dest="config_cmd")
    p_config_export = p_config_sub.add_parser("export", help="Export redacted config tarball")
    p_config_export.add_argument("--json", action="store_true")
    p_config_import = p_config_sub.add_parser("import", help="Import config tarball")
    p_config_import.add_argument("archive", help="Path to nordctl-export-*.tar.gz")
    p_config_import.add_argument("--replace", action="store_true", help="Replace config instead of merge")
    p_config_import.add_argument("--json", action="store_true")
    p_config.set_defaults(config_cmd="export")

    p_comm = sub.add_parser("community", help="Community preset helpers")
    p_comm_sub = p_comm.add_subparsers(dest="community_cmd")
    p_comm_list = p_comm_sub.add_parser("list", help="List community presets")
    p_comm_list.add_argument("--json", action="store_true")
    p_comm_import = p_comm_sub.add_parser("import", help="Import preset YAML from URL")
    p_comm_import.add_argument("url", help="https:// or file:// URL to preset YAML")
    p_comm_import.add_argument("--json", action="store_true")
    p_comm.set_defaults(community_cmd="list")

    p_doctor = sub.add_parser("doctor", help="Check system and show fix steps")
    p_doctor.add_argument("--json", action="store_true")

    p_inst = sub.add_parser("install-nordvpn", help="Install official NordVPN Linux client (Debian/Ubuntu)")
    p_inst.add_argument("--dry-run", action="store_true", help="Show commands only, do not run")
    p_inst.add_argument("--json", action="store_true")

    p_lab = sub.add_parser("leaklab", help="Run DNS/leak verification tests")
    p_lab.add_argument("--json", action="store_true")

    p_pubip = sub.add_parser("public-ip", help="Home ISP vs VPN exit (Smart DNS allowlist)")
    p_pubip.add_argument("--json", action="store_true")

    p_net = sub.add_parser("nettools", help="Network routing and traffic diagnostics")
    from nordctl.nettools import TOOL_DEFS

    p_net.add_argument(
        "tool",
        nargs="?",
        default="overview",
        choices=[t["id"] for t in TOOL_DEFS],
        help="Tool to run (default: overview)",
    )
    p_net.add_argument("-t", "--target", default="", help="Host or IP for trace, DNS, ping, route lookup")
    p_net.add_argument("--json", action="store_true")

    p_traffic = sub.add_parser("traffic", help="See what apps are talking to what (simple connection view)")
    p_traffic.add_argument(
        "--filter",
        default="all",
        choices=["all", "internet", "vpn", "direct", "local"],
        help="Filter connections (default: all)",
    )
    p_traffic.add_argument("--json", action="store_true")

    p_logs = sub.add_parser("logs", help="Human-readable activity log")
    p_logs.add_argument("--json", action="store_true")
    p_logs.add_argument("--clear", action="store_true", help="Clear log file")
    p_logs.add_argument("--errors", action="store_true", help="Show problems only")
    p_logs.add_argument("--category", default=None, choices=["vpn", "dns", "network", "service", "preset", "system", "security", "error"])
    p_logs.add_argument("-n", "--limit", type=int, default=40)

    p_sec = sub.add_parser("security", help="Security hub summary (health, profiles, tools)")
    p_sec.add_argument("--json", action="store_true")

    p_wifi = sub.add_parser("wifi", help="WiFi hub — profiles, zones, doctors, self-heal")
    p_wifi.add_argument("--json", action="store_true")
    p_wifi_sub = p_wifi.add_subparsers(dest="wifi_cmd")
    p_wifi_sub.add_parser("status", help="WiFi connection and profile overview")
    p_wifi_sub.add_parser("doctor", help="Run WiFi, network, and Nord doctors")
    p_wifi_sub.add_parser("heal", help="Run self-heal (sync, Smart DNS, zones)")
    p_wifi_sub.add_parser("sync", help="Sync NM profiles into config")
    p_wifi.set_defaults(wifi_cmd="status")

    p_snap = sub.add_parser("snapshot", help="Save or restore NordVPN settings snapshot")
    p_snap.add_argument("op", choices=["save", "list", "restore"], nargs="?", default="list")
    p_snap.add_argument("--id", default=None)
    p_snap.add_argument("--json", action="store_true")

    p_bundle = sub.add_parser("support-bundle", help="Export diagnostic bundle")
    p_bundle.add_argument("--anonymized", action="store_true", help="Scrub IPs, SSIDs, secrets for GitHub issues")
    p_bundle.add_argument("--json", action="store_true")

    p_journal = sub.add_parser("journal", help="Show local preset apply journal")
    p_journal.add_argument("--json", action="store_true")
    p_journal.add_argument("-n", "--limit", type=int, default=20)
    p_journal.add_argument("--preset", default=None, help="Filter by preset id")

    p_base = sub.add_parser("baseline", help="Install baseline backup and restore")
    p_base.add_argument("--json", action="store_true")
    p_base_sub = p_base.add_subparsers(dest="baseline_cmd")
    p_base_sub.add_parser("ensure", help="Create install baseline if missing")
    p_base_sub.add_parser("status", help="Show baseline info")
    p_base_restore = p_base_sub.add_parser("restore", help="Restore to install baseline")
    p_base_restore.add_argument("--resolv", action="store_true", help="Also restore resolv.conf (sudo)")
    p_base_re = p_base_sub.add_parser("recreate", help="Force new baseline from current state")
    p_base.set_defaults(baseline_cmd="status")

    p_factory = sub.add_parser("factory-reset", help="Undo all nordctl changes — restore pre-install state")
    p_factory.add_argument("--json", action="store_true")
    p_factory.add_argument("--resolv", action="store_true", help="Also restore resolv.conf (sudo)")

    p_tray = sub.add_parser("tray", help="System tray icon (requires nordctl[tray])")
    p_tray_sub = p_tray.add_subparsers(dest="tray_cmd")
    p_tray_sub.add_parser("install", help="Enable tray and autostart at login")
    p_tray_sub.add_parser("uninstall", help="Remove tray autostart")
    p_tray.set_defaults(tray_cmd="run")

    p_svc = sub.add_parser("service", help="Manage nordctl web UI systemd user service")
    p_svc.add_argument("--json", action="store_true")
    p_svc_sub = p_svc.add_subparsers(dest="service_cmd")
    p_svc_sub.add_parser("status", help="Show UI service and nordvpnd status")
    p_svc_sub.add_parser("install", help="Write unit, start UI, enable at login")
    p_svc_sub.add_parser("uninstall", help="Disable and remove UI unit")
    for cmd in ("start", "stop", "restart", "enable", "disable"):
        p_svc_sub.add_parser(cmd, help=f"{cmd} nordctl UI service")
    p_svc_nord = p_svc_sub.add_parser("nordvpnd", help="Control Nord VPN daemon (sudo)")
    p_svc_nord.add_argument(
        "nord_action",
        nargs="?",
        default="status",
        choices=["start", "stop", "restart", "enable", "disable", "status"],
    )
    p_svc.set_defaults(service_cmd="status")

    p_prov = sub.add_parser("provenance", help="Print canonical source identity (verify copies)")
    p_prov.add_argument("--json", action="store_true")

    p_run = sub.add_parser("run", help="Run a safe nordvpn command (advanced)")
    p_run.add_argument("args", nargs="+", help="e.g. set technology NORDLYNX")

    args = parser.parse_args()

    if args.command == "provenance":
        from nordctl.provenance import provenance_payload

        data = provenance_payload()
        if args.json:
            print(json.dumps(data, indent=2))
        else:
            print(f"source_id: {data['source_id']}")
            print(f"repository: {data['repository']}")
            print(f"marker: {data['source_marker']}")
        return

    if args.command == "init":
        path = ensure_user_config(
            fix_port=args.fix_port,
            minimal=not args.full and not args.headless,
            headless=args.headless,
        )
        print(f"Config: {path}")
        cfg = load_config()
        port = (cfg.get("server") or {}).get("port")
        print(f"UI port: {port}")
        if args.headless:
            print("Headless profile: nordctl serve — tray disabled, use API/CLI only")
        elif not args.full:
            print("Minimal profile: Nord Dashboard focus — enable Network & Security from Setup when ready")
        print("Edit wifi.profiles and connect_country, then: nordctl apply streaming-smartdns")
        if not args.skip_onboard:
            from nordctl.config import load_config as lc

            if not (lc().get("features") or {}).get("onboarding_complete"):
                print("Next: nordctl onboard   (pick feature modules)")
        return

    if args.command == "onboard":
        from nordctl.features import enable_all_modules
        from nordctl.onboarding import onboard_interactive

        if args.all:
            result = enable_all_modules(complete=True)
        elif args.non_interactive or not sys.stdin.isatty():
            from nordctl.features import apply_modules, module_catalog

            selected = {m["id"]: m["id"] not in ("alerts",) for m in module_catalog()}
            result = apply_modules(selected, legal_accepted=True, complete=True)
        else:
            result = onboard_interactive()
        if args.json:
            print(json.dumps(result, indent=2))
        elif result.get("ok", True):
            print("Onboarding saved. Open the web UI — disabled modules are hidden from the nav.")
        else:
            print(result.get("error") or "Failed", file=sys.stderr)
        sys.exit(0 if result.get("ok", True) else 1)
        return

    if args.command == "status":
        state = build_state()
        if args.json:
            print(json.dumps(state, indent=2))
        else:
            _print_status(state)
        return

    if args.command == "presets":
        presets = load_presets()
        if args.json:
            print(json.dumps(presets, indent=2))
        else:
            for p in presets:
                req = f"  (needs: {', '.join(p['requires'])})" if p.get("requires") else ""
                print(f"{p.get('id')}\t{p.get('label')}{req}")
                print(f"  {p.get('summary')}")
        return

    if args.command == "apply":
        from nordctl.presets import apply_preset

        result = apply_preset(
            args.preset,
            dry_run=args.dry_run,
            verify=not args.no_verify,
        )
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if args.dry_run:
                print(f"Dry run: {result.get('label') or args.preset} ({result.get('step_count', 0)} steps)")
                for s in result.get("steps") or []:
                    print(f"  {s.get('n')}. {s.get('text')}")
                if result.get("missing_config"):
                    print(f"Blocked: {result['missing_config']}", file=sys.stderr)
                    sys.exit(1)
                sys.exit(0)
            if result.get("note"):
                print(result["note"])
            ver = result.get("verification") or {}
            if ver:
                print(f"Verification: {ver.get('summary', ver.get('passed', '?'))}")
                for c in ver.get("checks") or []:
                    mark = "OK" if c.get("ok") else "FAIL"
                    print(f"  [{mark}] {c.get('name')}: {c.get('detail')}")
            print("OK" if result.get("ok") else "FAILED")
            if not result.get("ok"):
                print(result.get("error") or "see steps", file=sys.stderr)
                sys.exit(1)
        return

    if args.command == "serve":
        run_server(bind=args.bind, port=args.port, explicit_port=args.port is not None, demo=args.demo)
        return

    if args.command == "demo":
        cfg = load_config()
        port = args.port or int((cfg.get("server") or {}).get("port") or 8765)
        host = args.bind or str((cfg.get("server") or {}).get("bind") or "127.0.0.1")
        url = f"http://{host}:{port}/"
        if args.json:
            print(json.dumps({"ok": True, "demo_mode": True, "url": url}, indent=2))
            if not sys.stdin.isatty():
                run_server(bind=host, port=port, demo=True)
            return
        print(f"Starting demo UI at {url}")
        print("Simulated VPN state — no Nord account or network changes.")
        run_server(bind=host, port=port, demo=True)
        return

    if args.command == "config":
        if args.config_cmd == "import":
            from nordctl.config_bundle import import_config_bundle

            result = import_config_bundle(args.archive, merge=not args.replace)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                if result.get("ok"):
                    print("Imported:", ", ".join(result.get("imported") or []))
                    print(result.get("note") or "")
                else:
                    print(result.get("error") or "Import failed", file=sys.stderr)
            sys.exit(0 if result.get("ok") else 1)
            return
        from nordctl.config_bundle import export_config_bundle

        result = export_config_bundle()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result.get("path") or result.get("error"))
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "community":
        if args.community_cmd == "import":
            from nordctl.community_presets import import_preset_from_url

            result = import_preset_from_url(args.url)
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print(result.get("note") or result.get("error") or result.get("path"))
            sys.exit(0 if result.get("ok") else 1)
            return
        from nordctl.community_presets import list_community_presets

        result = list_community_presets()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            for p in result.get("presets") or []:
                tag = "installed" if p.get("installed") else p.get("source", "")
                print(f"{p.get('id')}\t{p.get('label')}\t[{tag}]")
                print(f"  {p.get('summary') or ''}")
        sys.exit(0)
        return

    if args.command == "doctor":
        from nordctl.doctor import run_doctor

        report = run_doctor()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            _print_doctor(report)
        sys.exit(0 if report.get("ok") else 1)
        return

    if args.command == "install-nordvpn":
        from nordctl.nordvpn_install import run_official_install

        result = run_official_install(dry_run=args.dry_run)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result.get("error"):
                print("ERROR:", result["error"], file=sys.stderr)
            for step in result.get("next_steps") or []:
                print("→", step)
            for fix in result.get("fix") or []:
                print("  ", fix)
            if result.get("plan"):
                print("\nManual steps:")
                for line in result["plan"].get("steps") or []:
                    print(" ", line)
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "leaklab":
        from nordctl.leaklab import run_leaklab

        report = run_leaklab()
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(f"Score: {report.get('score')}/{report.get('total')}")
            for t in report.get("tests") or []:
                mark = "OK" if t.get("ok") else "FAIL"
                print(f"  [{mark}] {t.get('name')}: {t.get('detail')}")
        sys.exit(0 if report.get("ok") else 1)
        return

    if args.command == "public-ip":
        from nordctl.ip_info import public_ip_report

        rep = public_ip_report(load_config())
        if args.json:
            print(json.dumps(rep, indent=2))
        else:
            sys.stdout.write(rep.get("text") or "Public IPv4: could not determine\n")
        sys.exit(0 if rep.get("ok") else 1)
        return

    if args.command == "nettools":
        from nordctl.nettools import run_tool

        result = run_tool(args.tool, args.target)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            label = result.get("label") or args.tool
            if result.get("error"):
                print(f"ERROR: {result['error']}", file=sys.stderr)
            else:
                print(f"# {label}" + (f" → {result['target']}" if result.get("target") else ""))
                if result.get("via_vpn"):
                    print("# traffic uses VPN tunnel")
                if result.get("summary"):
                    print(f"# {result['summary']}")
            print(result.get("output") or "")
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "traffic":
        from nordctl.traffic_watch import run_traffic_watch

        result = run_traffic_watch(args.filter)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if not result.get("ok"):
                print(result.get("error") or "failed", file=sys.stderr)
                sys.exit(1)
            print(result.get("summary", {}).get("plain_english", ""))
            print()
            for g in result.get("groups") or []:
                flags = []
                if g.get("via_vpn"):
                    flags.append(f"{g['via_vpn']} VPN")
                if g.get("via_direct"):
                    flags.append(f"{g['via_direct']} direct")
                extra = f" ({', '.join(flags)})" if flags else ""
                print(f"{g.get('emoji', '📱')} {g.get('app')} — {g.get('count')} connection(s){extra}")
                for s in g.get("samples") or []:
                    print(f"   · {s}")
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "logs":
        from nordctl.activity_log import clear_entries, logs_payload

        if args.clear:
            result = clear_entries()
            if args.json:
                print(json.dumps(result, indent=2))
            else:
                print("Log cleared.")
            sys.exit(0)
        payload = logs_payload(limit=args.limit, category=args.category, errors_only=args.errors)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            for e in payload.get("entries") or []:
                mark = "OK" if e.get("ok") else "!!"
                print(f"[{mark}] {e.get('ts')}  {e.get('title')}")
                if e.get("detail"):
                    print(f"      {e['detail']}")
        sys.exit(0)
        return

    if args.command == "security":
        from nordctl.security_hub import security_hub_payload

        payload = security_hub_payload()
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            h = payload.get("health") or {}
            print(f"Health: {h.get('score', '?')}/100 — {h.get('grade', '?')}")
            print(h.get("summary") or "")
            print("\nLocation profiles:")
            for p in payload.get("location_profiles") or []:
                print(f"  {p.get('emoji', '')} {p.get('label')} ({p.get('id')}) — preset {p.get('preset')}")
            dw = payload.get("disconnect_watch") or {}
            print(f"\nDisconnect alerts: {'on' if dw.get('enabled') else 'off'} (monitor {'running' if dw.get('running') else 'stopped'})")
            sp = payload.get("status_page") or {}
            print(f"Status page: {'enabled' if sp.get('enabled') else 'disabled'}")
            if sp.get("enabled"):
                print(f"  URL: {sp.get('url')}")
        sys.exit(0 if payload.get("ok") else 1)
        return

    if args.command == "wifi":
        from nordctl.wifi_hub import heal_wifi, sync_wifi_profiles, wifi_hub_payload
        from nordctl.wifi_doctor import run_all_wifi_hub_doctors

        cmd = args.wifi_cmd or "status"
        if cmd == "doctor":
            payload = run_all_wifi_hub_doctors()
        elif cmd == "heal":
            payload = heal_wifi()
        elif cmd == "sync":
            payload = sync_wifi_profiles()
        else:
            payload = wifi_hub_payload()
        if args.json:
            print(json.dumps(payload, indent=2))
            sys.exit(0)
        if cmd == "status":
            conn = payload.get("connection") or {}
            print(f"WiFi: {conn.get('ssid') or '—'} ({conn.get('state') or '?'})")
            print(f"Profile: {conn.get('active_profile') or '—'}")
            print(f"Profiles in config: {len(payload.get('profiles') or [])}")
            docs = payload.get("doctors") or {}
            print(docs.get("summary") or "")
        elif cmd == "doctor":
            for key in ("wifi", "network", "nord"):
                doc = payload.get(key) or {}
                print(f"\n{doc.get('title', key)}:")
                for c in doc.get("checks") or []:
                    mark = "OK" if c.get("ok") else "!!"
                    print(f"  [{mark}] {c.get('summary')}")
        else:
            print(payload.get("note") or ("OK" if payload.get("ok") else payload.get("error") or "Done"))
        sys.exit(0 if payload.get("ok", True) else 1)
        return

    if args.command == "snapshot":
        from nordctl.snapshot import capture_snapshot, list_snapshots, restore_snapshot

        if args.op == "save":
            result = capture_snapshot()
        elif args.op == "restore":
            result = restore_snapshot(args.id)
        else:
            result = {"ok": True, "snapshots": list_snapshots()}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if args.op == "list":
                for s in result.get("snapshots") or []:
                    print(f"{s.get('id')}\t{s.get('label')}\t{s.get('ts')}")
            else:
                print("OK" if result.get("ok") else result.get("error"))
        sys.exit(0 if result.get("ok", True) else 1)
        return

    if args.command == "support-bundle":
        from nordctl.support_bundle import build_anonymized_support_bundle, build_support_bundle

        result = build_anonymized_support_bundle() if args.anonymized else build_support_bundle()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result.get("path") or result.get("error"))
            if result.get("note"):
                print(result["note"])
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "journal":
        from nordctl.connection_journal import list_journal

        payload = list_journal(limit=args.limit, preset=args.preset)
        if args.json:
            print(json.dumps(payload, indent=2))
        else:
            entries = payload.get("entries") or []
            if not entries:
                print("No preset journal entries yet.")
            for e in entries:
                mark = "OK" if e.get("ok") else "FAIL"
                ver = (e.get("verification") or {}).get("summary") or ""
                extra = f" · {ver}" if ver else ""
                print(f"[{mark}] {e.get('ts')}  {e.get('label') or e.get('preset')}{extra}")
            print(f"\n{payload.get('path')}")
        sys.exit(0)
        return

    if args.command == "baseline":
        from nordctl.baseline import baseline_status, create_baseline, ensure_baseline, restore_baseline

        if args.baseline_cmd == "ensure":
            result = ensure_baseline()
        elif args.baseline_cmd == "restore":
            result = restore_baseline(restore_resolv=args.resolv)
        elif args.baseline_cmd == "recreate":
            result = create_baseline(force=True, label="manual")
        else:
            result = {"ok": True, **baseline_status()}
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if args.baseline_cmd == "status" or args.baseline_cmd is None:
                st = baseline_status()
                if st.get("exists"):
                    print(f"Baseline: {st.get('path')}")
                    print(f"Created: {st.get('created')}")
                    for c in st.get("components") or []:
                        print(f"  · {c}")
                else:
                    print(st.get("message"))
            else:
                print(result.get("message") or result.get("note") or result.get("error") or result)
        sys.exit(0 if result.get("ok", True) else 1)
        return

    if args.command == "factory-reset":
        from nordctl.factory_reset import factory_reset

        result = factory_reset(restore_resolv=args.resolv)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print(result.get("note") or result.get("error") or "Done")
            if result.get("warning"):
                print(f"Warning: {result['warning']}", file=sys.stderr)
        sys.exit(0 if result.get("ok") else 1)
        return

    if args.command == "tray":
        from nordctl.tray import install_tray, run_tray, tray_dependencies_ok, uninstall_tray

        if args.tray_cmd == "install":
            ok, err = tray_dependencies_ok()
            if not ok:
                print(err or "missing dependencies", file=sys.stderr)
                print("Run: pip install 'nordctl[tray]'", file=sys.stderr)
                sys.exit(1)
            result = install_tray(autostart=True)
            if result.get("ok"):
                print("Tray installed — starts at login.")
                print("Test now:", result.get("start_now"))
                if result.get("linux_hint"):
                    print(result["linux_hint"])
            else:
                print(result.get("error"), file=sys.stderr)
            sys.exit(0 if result.get("ok") else 1)
            return
        if args.tray_cmd == "uninstall":
            result = uninstall_tray()
            print("Tray autostart removed." if result.get("ok") else result)
            sys.exit(0)
            return
        ok, err = tray_dependencies_ok()
        if not ok:
            print(err or "missing dependencies", file=sys.stderr)
            sys.exit(1)
        try:
            run_tray()
        except KeyboardInterrupt:
            pass
        return

    if args.command == "service":
        from nordctl.service_mgr import (
            control_nordvpnd,
            control_ui_service,
            install_ui_service,
            nordvpnd_status,
            service_overview,
            uninstall_ui_service,
        )

        cmd = args.service_cmd or "status"
        if cmd == "install":
            result = install_ui_service(enable=True)
        elif cmd == "uninstall":
            result = uninstall_ui_service()
        elif cmd == "nordvpnd":
            result = control_nordvpnd(args.nord_action or "status")
        elif cmd == "status":
            result = {"ok": True, **service_overview()}
        else:
            result = control_ui_service(cmd)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if cmd == "status":
                ov = service_overview()
                ui = ov.get("ui") or {}
                nord = ov.get("nordvpnd") or {}
                print(f"UI ({ui.get('unit')}): {'running' if ui.get('active') else ui.get('status_text', '?')}")
                if ui.get("manual_running"):
                    print(f"  Also running manually (PIDs: {', '.join(map(str, ui.get('manual_pids') or []))})")
                print(f"  Login autostart: {'yes' if ui.get('enabled_at_login') else 'no'}")
                print(f"  URL: {ui.get('url', '?')}")
                print(f"Nord ({nord.get('unit')}): {nord.get('status_text', '?')} (boot: {nord.get('enabled_text', '?')})")
            elif cmd == "nordvpnd":
                if result.get("needs_password"):
                    print("ERROR: sudo password required", file=sys.stderr)
                    print(result.get("manual") or result.get("error"), file=sys.stderr)
                elif (args.nord_action or "status") == "status":
                    st = result if result.get("unit") else nordvpnd_status()
                    print(f"Nord ({st.get('unit')}): {st.get('status_text', '?')} (boot: {st.get('enabled_text', '?')})")
                else:
                    print(result.get("note") or result.get("output") or ("OK" if result.get("ok") else result.get("error")))
            elif result.get("needs_password"):
                print("ERROR: sudo password required", file=sys.stderr)
                print(result.get("manual") or result.get("error"), file=sys.stderr)
            else:
                print(result.get("note") or result.get("output") or ("OK" if result.get("ok") else result.get("error")))
        sys.exit(0 if result.get("ok", True) else 1)
        return

    if args.command == "run":
        from nordctl.actions import _validate_nordvpn_args
        from nordctl import nordvpn as nv

        cfg = load_config()
        bin_path = str(cfg.get("nordvpn_bin") or "nordvpn")
        cmd_args = list(args.args)
        err = _validate_nordvpn_args(cmd_args)
        if err:
            print(err, file=sys.stderr)
            sys.exit(1)
        r = nv.run(bin_path, cmd_args, timeout=60)
        print(r.get("output") or "")
        sys.exit(0 if r.get("ok") else 1)

    parser.print_help()


def _print_status(state: dict) -> None:
    if not state.get("ok"):
        print(state.get("error") or "unavailable")
        return
    st = state.get("status") or {}
    if st.get("connected"):
        print(f"VPN: connected — {st.get('Country', '?')} ({st.get('IP', '?')})")
    else:
        print("VPN: disconnected")
    sd = state.get("smart_dns") or {}
    if sd.get("active"):
        print(f"Smart DNS: active — {', '.join(sd.get('dns_servers') or [])}")
    if sd.get("public_ip"):
        print(f"Public IP: {sd['public_ip']}")
    if state.get("mesh_ip"):
        print(f"Meshnet IP: {state['mesh_ip']}")


def _print_doctor(report: dict) -> None:
    print(f"System: {report.get('distro', {}).get('name', '?')}")
    print(f"Ready: {'yes' if report.get('ready') else 'no'}")
    for c in report.get("checks") or []:
        mark = "OK" if c.get("ok") else c.get("severity", "!!").upper()
        print(f"  [{mark}] {c.get('summary')}")
        if not c.get("ok"):
            for line in c.get("fix") or []:
                if line:
                    print(f"       • {line}")
    print(f"\nHelp: open {report.get('help_url', '/help.html')} in the web UI")


if __name__ == "__main__":
    main()
