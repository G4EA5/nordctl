# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# Build a simple .deb from the current tree (no fpm required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import nordctl; print(nordctl.__version__)")"
ARCH="${ARCH:-all}"
STAGE="$(mktemp -d)"
PKG="${PKG:-dist/nordctl_${VERSION}_${ARCH}.deb}"

cleanup() { rm -rf "$STAGE"; }
trap cleanup EXIT

echo "Building nordctl ${VERSION} → ${PKG}"

python3 -m pip install build --quiet
python3 -m build --outdir "$ROOT/dist" --wheel 2>/dev/null || python3 -m build --outdir "$ROOT/dist"
WHEEL="$(ls -1 "$ROOT/dist"/nordctl-"${VERSION}"-*.whl | head -1)"

mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/nordctl" "$STAGE/usr/bin"

python3 -m pip install "$WHEEL" --target "$STAGE/usr/lib/nordctl" --no-deps --quiet
python3 -m pip install pyyaml --target "$STAGE/usr/lib/nordctl" --quiet

cat > "$STAGE/usr/bin/nordctl" <<'WRAPPER'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/nordctl${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m nordctl "$@"
WRAPPER
chmod 755 "$STAGE/usr/bin/nordctl"

if [[ -d presets ]]; then
  mkdir -p "$STAGE/usr/share/nordctl/presets"
  cp -a presets/. "$STAGE/usr/share/nordctl/presets/"
fi
if [[ -d docs ]]; then
  mkdir -p "$STAGE/usr/share/nordctl/docs"
  cp -a docs/. "$STAGE/usr/share/nordctl/docs/"
fi

INSTALLED_KB="$(du -sk "$STAGE/usr" | cut -f1)"

cat > "$STAGE/DEBIAN/control" <<EOF
Package: nordctl
Version: ${VERSION}
Section: net
Priority: optional
Architecture: ${ARCH}
Maintainer: nordctl contributors <nordctl@users.noreply.github.com>
Description: Preset-driven NordVPN control for Linux
 Local CLI and web UI for NordVPN presets, leak lab, and automation.
Depends: python3 (>= 3.10), python3-yaml
Installed-Size: ${INSTALLED_KB}
EOF

mkdir -p "$(dirname "$PKG")"
dpkg-deb --build "$STAGE" "$PKG"
echo "Created $PKG"
echo "Install: sudo dpkg -i $PKG"
