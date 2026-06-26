# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a
#!/usr/bin/env bash
# Build a simple .deb from the current tree (no fpm required).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VERSION="$(python3 -c "import nordctl; print(nordctl.__version__)")"
ARCH="${ARCH:-all}"
STAGE="$(mktemp -d)"
BUILD_VENV="$(mktemp -d)"
PKG="${PKG:-dist/nordctl_${VERSION}_${ARCH}.deb}"

cleanup() { rm -rf "$STAGE" "$BUILD_VENV"; }
trap cleanup EXIT

echo "Building nordctl ${VERSION} → ${PKG}"

# PEP 668 (Ubuntu 24.04+): never pip-install into the system interpreter.
python3 -m venv "$BUILD_VENV"
# shellcheck disable=SC1091
source "$BUILD_VENV/bin/activate"
pip install -q build pyyaml wheel
python -m build --outdir "$ROOT/dist"
WHEEL="$(ls -1 "$ROOT/dist"/nordctl-"${VERSION}"-*.whl | head -1)"

mkdir -p "$STAGE/DEBIAN" "$STAGE/usr/lib/nordctl" "$STAGE/usr/bin"

pip install "$WHEEL" --target "$STAGE/usr/lib/nordctl" --no-deps --quiet
pip install pyyaml --target "$STAGE/usr/lib/nordctl" --quiet

cat > "$STAGE/usr/bin/nordctl" <<'WRAPPER'
#!/usr/bin/env bash
export PYTHONPATH="/usr/lib/nordctl${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m nordctl "$@"
WRAPPER
chmod 755 "$STAGE/usr/bin/nordctl"

DEBIAN_DIR="$ROOT/packaging/debian"
mkdir -p "$STAGE/usr/share/applications" \
  "$STAGE/usr/share/metainfo" \
  "$STAGE/usr/share/icons/hicolor/scalable/apps"
install -m 755 "$DEBIAN_DIR/nordctl-open" "$STAGE/usr/bin/nordctl-open"
install -m 644 "$DEBIAN_DIR/nordctl.desktop" "$STAGE/usr/share/applications/nordctl.desktop"
install -m 644 "$DEBIAN_DIR/nordctl.appdata.xml" "$STAGE/usr/share/metainfo/nordctl.appdata.xml"
install -m 644 "$DEBIAN_DIR/nordctl.svg" "$STAGE/usr/share/icons/hicolor/scalable/apps/nordctl.svg"
install -m 755 "$DEBIAN_DIR/postinst" "$STAGE/DEBIAN/postinst"

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
 Desktop launcher: search for nordctl in your app menu.
Depends: python3 (>= 3.10), python3-yaml
Installed-Size: ${INSTALLED_KB}
EOF

mkdir -p "$(dirname "$PKG")"
dpkg-deb --build "$STAGE" "$PKG"
echo "Created $PKG"
echo "Install: sudo dpkg -i $PKG"
