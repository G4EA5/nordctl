<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Arch Linux packaging template

Community-maintained PKGBUILD for [AUR](https://wiki.archlinux.org/title/AUR).

1. Copy `PKGBUILD` to a build directory  
2. Update `pkgver`, `source` URL, and `sha256sums` for the release tarball  
3. Run `makepkg -si`  

Official install for most users: `./install.sh` from the repo (complete package). Debian/Ubuntu users can download a `.deb` from [GitHub Releases](https://github.com/G4EA5/nordctl/releases) or build with `bash scripts/build-deb.sh` — adds an app-menu launcher. PyPI is for manual step-by-step installs.

See also `scripts/build-deb.sh` and `packaging/debian/` for the desktop entry, icon, and `nordctl-open` launcher script.
