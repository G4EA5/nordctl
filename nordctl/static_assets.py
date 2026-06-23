"""Verify shipped static UI assets (HTML classes have matching CSS)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

STATIC = Path(__file__).resolve().parent / "static"

# Structural class prefixes used in index.html — each must appear in app.css.
REQUIRED_CSS_PREFIXES: tuple[str, ...] = (
    "topbar-stack",
    "sys-chip",
    "page-metrics",
    "page-metric",
    "page-hero",
    "page-section-head",
    "page-empty",
    "live-bw",
    "speed-lab",
    "conn-hop-field",
    "conn-hop-marker",
    "settings-box-premium",
    "settings-check-row",
    "preset-builder",
    "sec-hero",
    "sec-score",
    "traffic-stat-pill",
    "help-full",
    "doctor-report",
    "leak-lab",
    "dns-assistant",
    "panel-nav-actions",
    "inline-subnav",
    "connect-home",
    "workflows-preset",
)

STATIC_FILES: tuple[str, ...] = ("index.html", "app.css", "app.js", "help.html")

_SKIP_HTML_PREFIXES = frozenset(
    {"btn", "hidden", "active", "glass", "panel", "badge", "muted", "help-text", "field-row", "actions"}
)


def _has_css_prefix(css: str, prefix: str) -> bool:
    return bool(re.search(r"\." + re.escape(prefix) + r"(?:-|[\s\.\{:#\[,>]|$)", css))


def _class_prefixes_from_html(html: str, min_uses: int = 2) -> set[str]:
    classes: set[str] = set()
    for m in re.finditer(r'class="([^"]+)"', html):
        for part in m.group(1).split():
            if "-" in part:
                classes.add(part)
    prefixes: dict[str, int] = {}
    for c in classes:
        parts = c.split("-")
        for i in range(2, min(4, len(parts)) + 1):
            p = "-".join(parts[:i])
            prefixes[p] = prefixes.get(p, 0) + html.count(p)
    return {p for p, n in prefixes.items() if n >= min_uses}


def verify_static_ui(static_dir: Path | None = None) -> dict[str, Any]:
    """Return {ok, files, missing_css, missing_files, css_bytes, html_uses_page_metrics}."""
    root = static_dir or STATIC
    missing_files = [name for name in STATIC_FILES if not (root / name).is_file()]
    css_path = root / "app.css"
    html_path = root / "index.html"
    html = html_path.read_text(encoding="utf-8") if html_path.is_file() else ""
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    missing_css: list[str] = []
    for prefix in REQUIRED_CSS_PREFIXES:
        if not _has_css_prefix(css, prefix):
            missing_css.append(prefix)
    html_prefix_warnings: list[str] = []
    for prefix in sorted(_class_prefixes_from_html(html)):
        if prefix in _SKIP_HTML_PREFIXES:
            continue
        if not _has_css_prefix(css, prefix) and prefix not in missing_css:
            html_prefix_warnings.append(prefix)
    brace_ok = css.count("{") == css.count("}") if css else False
    ok = not missing_files and not missing_css and brace_ok and len(css) > 50_000
    return {
        "ok": ok,
        "static_dir": str(root),
        "missing_files": missing_files,
        "missing_css": missing_css,
        "html_prefix_warnings": html_prefix_warnings[:20],
        "html_prefix_warning_count": len(html_prefix_warnings),
        "brace_ok": brace_ok,
        "css_bytes": len(css.encode("utf-8")),
        "js_bytes": (root / "app.js").stat().st_size if (root / "app.js").is_file() else 0,
        "html_has_page_metrics": "page-metrics" in html,
    }


def ui_health_payload() -> dict[str, Any]:
    """Public API payload for /api/ui-health and wizard."""
    report = verify_static_ui()
    repair_hint = ""
    if not report["ok"]:
        repair_hint = (
            "Reinstall nordctl to restore UI files: pip install --force-reinstall nordctl "
            "(or restart nordctl after updating the package)."
        )
    return {**report, "repair_hint": repair_hint}
