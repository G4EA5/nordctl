# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env python3
"""Embed SOURCE_MARKER line into nordctl source files (idempotent)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from nordctl.provenance import SOURCE_ID, SOURCE_MARKER  # noqa: E402

SKIP_DIRS = {".venv", "venv", "__pycache__", ".git", ".dashboard-patch", "node_modules"}
SCAN_ROOTS = (
    ROOT / "nordctl",
    ROOT / "scripts",
    ROOT / "docs",
    ROOT / "presets",
    ROOT / "examples",
    ROOT / "packaging",
)
ROOT_FILES = (
    ROOT / "install.sh",
    ROOT / "config.example.yaml",
    ROOT / "README.md",
    ROOT / "OPEN_SOURCE.md",
    ROOT / "LEGAL.md",
    ROOT / "pyproject.toml",
    ROOT / "MANIFEST.in",
)

MARKER_BY_SUFFIX = {
    ".py": f"# {SOURCE_MARKER}\n",
    ".js": f"/* {SOURCE_MARKER} */\n",
    ".css": f"/* {SOURCE_MARKER} */\n",
    ".yaml": f"# {SOURCE_MARKER}\n",
    ".yml": f"# {SOURCE_MARKER}\n",
    ".sh": f"# {SOURCE_MARKER}\n",
    ".md": f"<!-- {SOURCE_MARKER} -->\n",
    ".html": f"<!-- {SOURCE_MARKER} -->\n",
    ".toml": f"# {SOURCE_MARKER}\n",
    ".in": f"# {SOURCE_MARKER}\n",
}


def marker_line(path: Path) -> str | None:
    return MARKER_BY_SUFFIX.get(path.suffix.lower())


def already_marked(text: str) -> bool:
    return SOURCE_ID in text or SOURCE_MARKER in text


def embed_file(path: Path) -> bool:
    line = marker_line(path)
    if not line:
        return False
    text = path.read_text(encoding="utf-8")
    if already_marked(text):
        return False
    if path.suffix == ".py" and text.startswith('"""'):
        end = text.find('"""', 3)
        if end != -1:
            insert_at = end + 3
            if text[insert_at : insert_at + 1] == "\n":
                insert_at += 1
            path.write_text(text[:insert_at] + "\n" + line + text[insert_at:], encoding="utf-8")
            return True
    path.write_text(line + text, encoding="utf-8")
    return True


def iter_files() -> list[Path]:
    out: list[Path] = []
    for base in SCAN_ROOTS:
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIRS for part in path.parts):
                continue
            if marker_line(path):
                out.append(path)
    for path in ROOT_FILES:
        if path.is_file() and marker_line(path):
            out.append(path)
    return out


def main() -> int:
    changed = 0
    for path in iter_files():
        if embed_file(path):
            changed += 1
            print(path.relative_to(ROOT))
    print(f"embedded marker in {changed} file(s); source_id={SOURCE_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
