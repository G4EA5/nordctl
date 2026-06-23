<!-- nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a -->
# Arch Linux packaging template

Community-maintained PKGBUILD for [AUR](https://wiki.archlinux.org/title/AUR).

1. Copy `PKGBUILD` to a build directory  
2. Update `pkgver`, `source` URL, and `sha256sums` for the release tarball  
3. Run `makepkg -si`  

Official install for most users: `pip install nordctl` or `./install.sh` from the repo.

See also `scripts/build-deb.sh` for Debian/Ubuntu `.deb` packages.
