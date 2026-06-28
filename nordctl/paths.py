"""Resolve nordctl executable path for systemd units and CLI hints."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import shutil
import sys
from pathlib import Path

UFW_SUDOERS_SCRIPT = "install-ufw-sudoers.sh"
PRIV_SUDOERS_SCRIPT = "install-privilege-sudoers.sh"


def package_root() -> Path:
    """Directory containing install.sh, scripts/, and the nordctl package."""
    return Path(__file__).resolve().parent.parent


def install_script_path(name: str) -> Path:
    return package_root() / "scripts" / name


def install_script_sudo_cmd(name: str) -> str:
    return f"sudo bash {install_script_path(name)}"


def install_scripts_map() -> dict[str, str]:
    return {
        "ufw": str(install_script_path(UFW_SUDOERS_SCRIPT)),
        "privileges": str(install_script_path(PRIV_SUDOERS_SCRIPT)),
    }


def is_readable_file(path: Path) -> bool:
    """Stat a path without raising when the OS denies access (e.g. sudoers.d on CI)."""
    try:
        return path.is_file()
    except OSError:
        return False


def resolve_nordctl_bin() -> str:
    """Return absolute path to nordctl — prefer ~/.local/bin over /usr/bin."""
    home_bin = Path.home() / ".local" / "bin" / "nordctl"
    if home_bin.is_file():
        return str(home_bin)

    found = shutil.which("nordctl")
    if found:
        return found

    if sys.argv:
        invoked = Path(sys.argv[0]).resolve()
        if invoked.is_file() and invoked.name == "nordctl":
            return str(invoked)

    pkg_root = package_root()
    for candidate in (
        pkg_root / ".venv" / "bin" / "nordctl",
        Path.home() / ".local" / "bin" / "nordctl",
        pkg_root / "bin" / "nordctl",
    ):
        if candidate.is_file():
            return str(candidate)

    return str(pkg_root / ".venv" / "bin" / "nordctl")
