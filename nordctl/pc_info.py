"""Comprehensive local hardware and system inventory (no network/security focus)."""

# nordctl-src-id:NCTL-src-a7f3c912-6e4b-5d8a

from __future__ import annotations

import json
import os
import platform
import re
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from nordctl.doctor import detect_distro

_CACHE: dict[str, Any] = {"ts": 0.0, "data": None}
_TTL = float(os.environ.get("NORDCTL_PC_INFO_TTL", "30"))


def _run(argv: list[str], *, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        r = subprocess.run(argv, capture_output=True, text=True, timeout=timeout)
        out = ((r.stdout or "") + (r.stderr or "")).strip()
        return r.returncode == 0, out
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return False, str(exc)


def _read_text(path: str | Path, default: str = "") -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return default


def _read_int(path: str | Path) -> int | None:
    raw = _read_text(path)
    if raw.isdigit() or (raw.startswith("-") and raw[1:].isdigit()):
        return int(raw)
    return None


def _kb_human(kb: int | float | None) -> str | None:
    if kb is None:
        return None
    kb = float(kb)
    if kb >= 1024 * 1024:
        return f"{kb / 1024 / 1024:.1f} GiB"
    if kb >= 1024:
        return f"{kb / 1024:.1f} MiB"
    return f"{kb:.0f} KiB"


def _bytes_human(n: int | float | None) -> str | None:
    if n is None:
        return None
    n = float(n)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if n < 1024 or unit == "TiB":
            return f"{n:.1f} {unit}" if unit != "B" else f"{int(n)} B"
        n /= 1024
    return f"{n:.1f} TiB"


def _uptime_human(sec: float | None) -> str | None:
    if sec is None:
        return None
    s = int(sec)
    d, rem = divmod(s, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    parts = []
    if d:
        parts.append(f"{d}d")
    if h:
        parts.append(f"{h}h")
    if m or not parts:
        parts.append(f"{m}m")
    return " ".join(parts)


_DMI_MEMORY_TYPES = {
    1: "Other", 2: "Unknown", 3: "DRAM", 4: "EDRAM", 5: "VRAM", 6: "SRAM", 7: "RAM",
    8: "ROM", 9: "FLASH", 10: "EEPROM", 11: "FDC", 12: "EDD", 13: "VRAM", 14: "Cache",
    15: "SDRAM", 16: "SGRAM", 17: "RDRAM", 18: "DDR", 19: "DDR2", 20: "DDR2 FB-DIMM",
    21: "Reserved", 22: "DDR3", 23: "FBD2", 24: "DDR4", 25: "LPDDR", 26: "LPDDR2",
    27: "LPDDR3", 28: "LPDDR4", 29: "Logical", 30: "HBM", 31: "HBM2", 32: "DDR5", 33: "LPDDR5",
}

_DMI_FORM_FACTORS = {
    1: "Other", 2: "Unknown", 3: "SIMM", 4: "SIP", 5: "Chip", 6: "DIP", 7: "ZIP",
    8: "Proprietary", 9: "DIMM", 10: "TSOP", 11: "Row of chips", 12: "RIMM",
    13: "SODIMM", 14: "SRIMM", 15: "FB-DIMM", 16: "Die",
}

_CHASSIS_TYPES = {
    "1": "Other", "2": "Unknown", "3": "Desktop", "4": "Low profile desktop",
    "5": "Pizza box", "6": "Mini tower", "7": "Tower", "8": "Portable",
    "9": "Laptop", "10": "Notebook", "11": "Handheld", "12": "Docking station",
    "13": "All in one", "14": "Sub notebook", "15": "Space-saving", "16": "Lunch box",
    "17": "Main server chassis", "18": "Expansion chassis", "19": "Sub chassis",
    "20": "Bus expansion chassis", "21": "Peripheral chassis", "22": "RAID chassis",
    "23": "Rack mount", "24": "Sealed-case PC", "30": "Tablet", "31": "Convertible",
    "32": "Detachable",
}


def _parse_dmidecode_memory(text: str) -> list[dict[str, Any]]:
    """Parse `dmidecode -t memory` text into installed DIMM records."""
    modules: list[dict[str, Any]] = []
    if not text.strip():
        return modules
    blocks = re.split(r"\n(?=Handle\s+)", text)
    key_map = {
        "size": "size",
        "form factor": "form_factor",
        "locator": "slot",
        "bank locator": "bank",
        "type": "memory_type",
        "type detail": "type_detail",
        "speed": "speed",
        "configured memory speed": "configured_speed",
        "configured clock speed": "configured_speed",
        "manufacturer": "manufacturer",
        "serial number": "serial",
        "part number": "part_number",
        "rank": "rank",
        "total width": "total_width",
        "data width": "data_width",
        "minimum voltage": "voltage_min",
        "maximum voltage": "voltage_max",
        "configured voltage": "voltage_configured",
    }
    for block in blocks:
        if "Memory Device" not in block:
            continue
        low = block.lower()
        if "no module installed" in low or "size: no module installed" in low:
            continue
        if re.search(r"size:\s*0\s", low) and "size: no module" not in low:
            if not re.search(r"size:\s*[1-9]", block, re.I):
                continue
        mod: dict[str, Any] = {}
        for line in block.splitlines():
            if ":" not in line:
                continue
            key, val = (p.strip() for p in line.split(":", 1))
            lk = key.lower()
            if lk in key_map:
                mod[key_map[lk]] = val
        if not mod.get("size"):
            continue
        size_raw = str(mod.get("size", "")).lower()
        if "no module" in size_raw or size_raw in ("0", "0 mb", "0 gb"):
            continue
        mod["memory_type"] = mod.get("memory_type") or "Unknown"
        modules.append(mod)
    return modules


def _memory_modules() -> tuple[list[dict[str, Any]], str | None]:
    """Installed DIMMs via passwordless sudo dmidecode when available."""
    ok, out = _run(["sudo", "-n", "dmidecode", "-t", "memory"], timeout=15)
    if ok and out:
        mods = _parse_dmidecode_memory(out)
        if mods:
            try:
                cache = Path.home() / ".cache/nordctl/dmidecode-memory.txt"
                cache.parent.mkdir(parents=True, exist_ok=True)
                cache.write_text(out, encoding="utf-8")
            except OSError:
                pass
            return mods, "dmidecode (sudo)"
    ok2, out2 = _run(["dmidecode", "-t", "memory"], timeout=15)
    if ok2 and out2 and "permission denied" not in out2.lower():
        mods = _parse_dmidecode_memory(out2)
        if mods:
            return mods, "dmidecode"
    cache_path = Path.home() / ".cache/nordctl/dmidecode-memory.txt"
    if cache_path.is_file():
        try:
            cached = cache_path.read_text(encoding="utf-8", errors="replace")
            mods = _parse_dmidecode_memory(cached)
            if mods:
                return mods, "dmidecode (cached)"
        except OSError:
            pass
    return [], None


def _lscpu_map() -> dict[str, str]:
    ok, out = _run(["lscpu", "-J"], timeout=8)
    if not ok or not out.strip().startswith("{"):
        return {}
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return {}
    rows = data.get("lscpu") if isinstance(data.get("lscpu"), list) else data
    if not isinstance(rows, list):
        return {}
    result: dict[str, str] = {}
    for row in rows:
        if isinstance(row, dict) and row.get("field") and row.get("data") is not None:
            key = str(row["field"]).rstrip(":").strip().lower()
            result[key] = str(row["data"]).strip()
    return result


def _cpu_cache_sysfs() -> list[dict[str, Any]]:
    caches: list[dict[str, Any]] = []
    try:
        for idx in sorted(Path("/sys/devices/system/cpu/cpu0/cache").glob("index*")):
            caches.append({
                "level": _read_text(idx / "level") or None,
                "type": _read_text(idx / "type") or None,
                "size": _read_text(idx / "size") or None,
                "ways": _read_text(idx / "ways_of_associativity") or None,
                "line_size": _read_text(idx / "coherency_line_size") or None,
                "sets": _read_text(idx / "number_of_sets") or None,
            })
    except OSError:
        pass
    return caches


def _udev_properties(dev: str) -> dict[str, str]:
    ok, out = _run(["udevadm", "info", "--query=property", f"--name={dev}"], timeout=6)
    if not ok:
        return {}
    props: dict[str, str] = {}
    for line in out.splitlines():
        if line.startswith("E:") or line.startswith("ID_"):
            line = line[2:] if line.startswith("E:") else line
            if "=" in line:
                k, v = line.split("=", 1)
                props[k] = v
    return props


def _block_sysfs(name: str) -> dict[str, Any]:
    base = Path("/sys/block") / name
    if not base.is_dir():
        return {}
    dev = base / "device"
    detail: dict[str, Any] = {
        "rotational": _read_text(base / "queue/rotational") == "1",
        "scheduler": _read_text(base / "queue/scheduler"),
        "physical_block_size": _read_int(base / "queue/physical_block_size"),
        "logical_block_size": _read_int(base / "queue/logical_block_size"),
        "discard_granularity": _read_int(base / "queue/discard_granularity"),
        "discard_max_bytes": _read_int(base / "queue/discard_max_bytes"),
        "read_ahead_kb": _read_int(base / "queue/read_ahead_kb"),
    }
    for label, rel in (
        ("model", "model"),
        ("vendor", "vendor"),
        ("revision", "rev"),
        ("serial", "serial"),
    ):
        val = _read_text(dev / rel)
        if val:
            detail[label] = val.strip()
    # NVMe controller lives one level up for namespaces nvme0n1 -> nvme0
    if name.startswith("nvme") and "n" in name:
        ctrl = re.sub(r"n\d+$", "", name)
        ctrl_dev = Path("/sys/class/nvme") / ctrl / "device"
        if ctrl_dev.is_dir():
            for label, fname in (("model", "model"), ("firmware", "firmware_rev"), ("serial", "serial")):
                val = _read_text(ctrl_dev / fname) or _read_text(Path("/sys/class/nvme") / ctrl / fname)
                if val:
                    detail[label] = val.strip()
    return detail


def _disk_smart_info(dev: str) -> dict[str, Any] | None:
    ok, out = _run(["sudo", "-n", "smartctl", "-i", dev], timeout=12)
    if not ok or not out:
        return None
    info: dict[str, str] = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            info[k.strip().lower()] = v.strip()
    if not info:
        return None
    return {
        "model": info.get("device model") or info.get("model family"),
        "serial": info.get("serial number"),
        "firmware": info.get("firmware version"),
        "capacity": info.get("user capacity") or info.get("total nvm capacity"),
        "rotation": info.get("rotation rate"),
        "sata_version": info.get("sata version"),
        "smart_supported": "smart support is:" in out.lower(),
        "source": "smartctl",
    }


def _infer_disk_role(mounts: list[str], fstypes: list[str]) -> str:
    mount_set = set(mounts)
    if "/" in mount_set:
        return "Primary OS disk"
    if "/boot/efi" in mount_set or "/boot" in mount_set:
        return "Boot / EFI"
    if any("swap" in (f or "").lower() for f in fstypes):
        return "Swap"
    if mounts:
        return f"Data ({mounts[0]})"
    return "Storage (unmounted)"


_PARTTYPE_LABELS = {
    "0fc63daf-8483-4772-8e79-3d69d8477de4": "Linux filesystem",
    "0657fd6d-a4ab-43c4-84e7-c1133bca6c44": "Linux swap",
    "c12a7328-f81f-11d2-ba4b-00a0c93ec93b": "EFI system",
    "21686148-6449-6e6f-744e-656564454649": "BIOS boot",
    "e6d6d379-f507-44c2-9807-2b3b9d2e7f5c": "Linux LVM",
}


def _lsblk_tree() -> list[dict[str, Any]]:
    ok, out = _run(
        [
            "lsblk", "-J", "-b",
            "-o", "NAME,SIZE,TYPE,ROTA,RO,RM,HOTPLUG,MODEL,SERIAL,REV,VENDOR,TRAN,FSTYPE,MOUNTPOINT,UUID,LABEL,PKNAME,WWN,PHY-SEC,LOG-SEC,SCHED,DISC-GRAN,DISC-MAX,DISC-ZERO,HCTL,PARTTYPE,PARTLABEL,PARTUUID,FSVER,STATE,START,SUBSYSTEMS,GROUP",
        ],
        timeout=15,
    )
    if not ok or not out.strip().startswith("{"):
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []
    return data.get("blockdevices") or []


def _enrich_partition(node: dict[str, Any], parent_name: str) -> dict[str, Any]:
    name = node.get("name") or ""
    parttype = (node.get("parttype") or "").lower()
    props = _udev_properties(f"/dev/{name}")
    return {
        "name": name,
        "path": f"/dev/{name}",
        "parent": parent_name,
        "size_bytes": node.get("size"),
        "size_human": _bytes_human(node.get("size")),
        "fstype": node.get("fstype"),
        "fsver": node.get("fsver"),
        "mountpoint": node.get("mountpoint"),
        "uuid": node.get("uuid") or props.get("ID_FS_UUID"),
        "label": node.get("label") or props.get("ID_FS_LABEL"),
        "parttype": parttype,
        "parttype_label": _PARTTYPE_LABELS.get(parttype, parttype or None),
        "partlabel": node.get("partlabel"),
        "partuuid": node.get("partuuid"),
        "start_sector": node.get("start"),
        "read_only": bool(node.get("ro")),
    }


def _enrich_disk(node: dict[str, Any]) -> dict[str, Any]:
    name = node.get("name") or ""
    dev = f"/dev/{name}"
    rota = node.get("rota")
    transport = (node.get("tran") or "").strip().lower()
    sysfs = _block_sysfs(name)
    props = _udev_properties(dev)
    model = (node.get("model") or sysfs.get("model") or props.get("ID_MODEL") or "").strip()
    vendor = (node.get("vendor") or sysfs.get("vendor") or "").strip()
    serial = (node.get("serial") or sysfs.get("serial") or props.get("ID_SERIAL_SHORT") or "").strip()
    revision = (node.get("rev") or sysfs.get("revision") or "").strip()

    if rota == 0 and transport == "nvme":
        media = "NVMe SSD"
    elif rota == 0:
        media = "SSD (solid state)"
    elif rota == 1:
        media = "HDD (rotational)"
    else:
        media = "Fixed disk"

    partitions = [_enrich_partition(c, name) for c in node.get("children") or [] if c.get("type") == "part"]
    mounts = [p["mountpoint"] for p in partitions if p.get("mountpoint")]
    fstypes = [p.get("fstype") for p in partitions if p.get("fstype")]

    identity_parts = [media]
    if vendor and vendor not in model:
        identity_parts.append(vendor)
    if model:
        identity_parts.append(model)
    identity = " ".join(identity_parts).strip()

    smart = _disk_smart_info(dev)

    return {
        "name": name,
        "path": dev,
        "identity": identity,
        "media": media,
        "role": _infer_disk_role(mounts, fstypes),
        "size_bytes": node.get("size"),
        "size_human": _bytes_human(node.get("size")),
        "model": model or None,
        "vendor": vendor or None,
        "serial": serial or None,
        "revision": revision or None,
        "firmware": sysfs.get("firmware"),
        "transport": transport or None,
        "wwn": node.get("wwn") or props.get("ID_WWN"),
        "hctl": node.get("hctl"),
        "subsystems": node.get("subsystems"),
        "scheduler": node.get("sched") or sysfs.get("scheduler"),
        "physical_sector_bytes": node.get("phy-sec") or sysfs.get("physical_block_size"),
        "logical_sector_bytes": node.get("log-sec") or sysfs.get("logical_block_size"),
        "discard_granularity": node.get("disc-gran") or sysfs.get("discard_granularity"),
        "discard_max_bytes": node.get("disc-max") or sysfs.get("discard_max_bytes"),
        "trim_supported": bool(node.get("disc-max") or sysfs.get("discard_max_bytes")),
        "removable": bool(node.get("rm")),
        "hotplug": bool(node.get("hotplug")),
        "state": node.get("state"),
        "partitions": partitions,
        "partition_table": props.get("ID_PART_TABLE_TYPE"),
        "partition_table_uuid": props.get("ID_PART_TABLE_UUID"),
        "smart": smart,
        "udev": {k: v for k, v in props.items() if k.startswith("ID_") and k in (
            "ID_BUS", "ID_MODEL", "ID_SERIAL_SHORT", "ID_WWN", "ID_PART_TABLE_TYPE",
            "ID_PART_TABLE_UUID", "ID_ATA", "ID_ATA_DOWNLOAD_MICROCODE", "ID_PATH",
        )},
    }


def _physical_disks() -> list[dict[str, Any]]:
    return [_enrich_disk(n) for n in _lsblk_tree() if n.get("type") == "disk"]


def _system_section() -> dict[str, Any]:
    distro = detect_distro()
    uptime_sec = None
    try:
        uptime_sec = float(_read_text("/proc/uptime").split()[0])
    except (OSError, ValueError, IndexError):
        pass
    boot_epoch = time.time() - uptime_sec if uptime_sec is not None else None
    tz = time.tzname
    return {
        "hostname": socket.gethostname().split(".")[0] or "host",
        "fqdn": socket.getfqdn(),
        "kernel": platform.release(),
        "kernel_version": _read_text("/proc/version"),
        "architecture": platform.machine(),
        "platform": platform.platform(),
        "bitness": platform.architecture()[0],
        "distro": distro,
        "uptime_sec": uptime_sec,
        "uptime_human": _uptime_human(uptime_sec),
        "boot_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(boot_epoch)) if boot_epoch else None,
        "timezone": tz[0] if tz else None,
        "machine_id": _read_text("/etc/machine-id") or _read_text("/var/lib/dbus/machine-id"),
        "python": platform.python_version(),
        "cmdline": _read_text("/proc/cmdline"),
    }


def _cpu_section() -> dict[str, Any]:
    cpus: list[dict[str, str]] = []
    cur: dict[str, str] = {}
    try:
        for line in Path("/proc/cpuinfo").read_text(encoding="utf-8", errors="replace").splitlines():
            if not line.strip():
                if cur:
                    cpus.append(cur)
                    cur = {}
                continue
            if ":" not in line:
                continue
            k, v = (p.strip() for p in line.split(":", 1))
            cur[k] = v
        if cur:
            cpus.append(cur)
    except OSError:
        pass

    first = cpus[0] if cpus else {}
    physical_ids = {c.get("physical id") for c in cpus if c.get("physical id") is not None}
    sockets = len(physical_ids) or 1
    logical = len(cpus) or (os.cpu_count() or 1)
    cores_per_socket = None
    try:
        cores_per_socket = int(first.get("cpu cores") or first.get("siblings") or 0) or None
    except ValueError:
        pass
    physical_cores = cores_per_socket * sockets if cores_per_socket else logical

    flags = (first.get("flags") or first.get("Features") or "").split()
    freq: dict[str, Any] = {}
    for label, fname in (("current_mhz", "scaling_cur_freq"), ("min_mhz", "scaling_min_freq"), ("max_mhz", "scaling_max_freq")):
        raw = _read_int(f"/sys/devices/system/cpu/cpu0/cpufreq/{fname}")
        if raw:
            freq[label] = round(raw / 1000, 0) if raw > 10000 else raw

    caches: list[dict[str, str]] = []
    for c in cpus:
        idx = c.get("processor")
        for level in ("0", "1", "2", "3"):
            size = c.get(f"cache size") if level == "0" else None
            if level == "0" and size and not any(x.get("size") == size for x in caches):
                caches.append({"level": "L?", "size": size})
        break

    # dedupe cache lines from cpu0
    seen_cache: set[str] = set()
    for c in cpus[:1]:
        for key, val in c.items():
            if key.startswith("cache size") and val not in seen_cache:
                seen_cache.add(val)
                caches.append({"level": "cache", "size": val})

    bogomips = first.get("bogomips")
    model = first.get("model name") or first.get("Processor") or first.get("Hardware") or "Unknown CPU"
    vendor = first.get("vendor_id") or first.get("CPU implementer") or ""

    thermals: list[dict[str, Any]] = []
    try:
        for zone in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
            temp_raw = _read_int(zone / "temp")
            typ = _read_text(zone / "type") or zone.name
            if temp_raw is not None and temp_raw > 0:
                thermals.append({
                    "zone": typ,
                    "temp_c": round(temp_raw / 1000, 1),
                })
    except OSError:
        pass

    load = [0.0, 0.0, 0.0]
    try:
        load = [float(x) for x in _read_text("/proc/loadavg").split()[:3]]
    except (OSError, ValueError):
        pass

    virt = "none"
    ok, out = _run(["systemd-detect-virt", "--vm"], timeout=3)
    if ok and out and out != "none":
        virt = out
    elif any(f in flags for f in ("hypervisor", "vmx", "svm")):
        virt = "virtualized (cpu flag)"

    lscpu = _lscpu_map()
    cache_sysfs = _cpu_cache_sysfs()

    return {
        "model": model,
        "vendor": vendor,
        "family": first.get("cpu family") or first.get("CPU architecture"),
        "stepping": first.get("stepping"),
        "microcode": first.get("microcode"),
        "sockets": sockets,
        "cores_physical": physical_cores,
        "cores_logical": logical,
        "threads_per_core": round(logical / physical_cores, 1) if physical_cores else None,
        "architecture": lscpu.get("architecture") or platform.machine(),
        "address_sizes": lscpu.get("address sizes"),
        "byte_order": lscpu.get("byte order"),
        "bogomips": bogomips,
        "flags_count": len(flags),
        "flags_sample": flags[:32],
        "flags_all": flags,
        "frequency_mhz": freq,
        "caches": caches,
        "cache_sysfs": cache_sysfs,
        "lscpu": lscpu,
        "thermals": thermals,
        "load_1m": load[0] if load else None,
        "load_5m": load[1] if len(load) > 1 else None,
        "load_15m": load[2] if len(load) > 2 else None,
        "virtualization": virt,
        "hypervisor_vendor": lscpu.get("hypervisor vendor"),
    }


def _memory_section() -> dict[str, Any]:
    info: dict[str, int] = {}
    try:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            key, _, val = line.partition(":")
            if not val:
                continue
            parts = val.strip().split()
            if parts and parts[0].isdigit():
                info[key.strip()] = int(parts[0])
    except OSError:
        return {"total_kb": 0, "details": []}

    total = info.get("MemTotal") or 0
    avail = info.get("MemAvailable") or info.get("MemFree") or 0
    used = max(total - avail, 0) if total else 0
    swap_total = info.get("SwapTotal") or 0
    swap_free = info.get("SwapFree") or 0

    highlight_keys = (
        "MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached", "SwapCached",
        "Active", "Inactive", "Active(anon)", "Inactive(anon)", "Active(file)", "Inactive(file)",
        "Dirty", "Writeback", "AnonPages", "Mapped", "Shmem", "Slab", "SReclaimable", "SUnreclaim",
        "KernelStack", "PageTables", "VmallocUsed", "HugePages_Total", "Hugepagesize",
        "DirectMap4k", "DirectMap2M", "DirectMap1G",
    )
    details = [{"key": k, "kb": info[k], "human": _kb_human(info[k])} for k in highlight_keys if k in info]

    modules, modules_source = _memory_modules()
    module_summary = None
    if modules:
        types = sorted({m.get("memory_type") for m in modules if m.get("memory_type")})
        speeds = sorted({m.get("configured_speed") or m.get("speed") for m in modules if m.get("configured_speed") or m.get("speed")})
        forms = sorted({m.get("form_factor") for m in modules if m.get("form_factor")})
        module_summary = {
            "type": ", ".join(types) if types else None,
            "speed": ", ".join(speeds) if speeds else None,
            "form_factor": ", ".join(forms) if forms else None,
            "module_count": len(modules),
        }

    return {
        "total_kb": total,
        "used_kb": used,
        "available_kb": avail,
        "used_pct": round(100 * used / total, 1) if total else None,
        "total_human": _kb_human(total),
        "used_human": _kb_human(used),
        "swap_total_kb": swap_total,
        "swap_used_kb": max(swap_total - swap_free, 0),
        "swap_used_pct": round(100 * (swap_total - swap_free) / swap_total, 1) if swap_total else None,
        "details": details,
        "modules": modules,
        "modules_source": modules_source,
        "module_summary": module_summary,
        "modules_note": (
            None if modules
            else "Exact RAM type (DDR4/DDR5, speed, part numbers) needs SMBIOS. Run once in a terminal: sudo dmidecode -t memory | tee ~/.cache/nordctl/dmidecode-memory.txt then refresh this page."
        ),
    }


def _lsblk_devices() -> list[dict[str, Any]]:
    ok, out = _run(
        ["lsblk", "-J", "-b", "-o", "NAME,SIZE,TYPE,ROTA,RO,RM,HOTPLUG,MODEL,SERIAL,REV,VENDOR,TRAN,FSTYPE,MOUNTPOINT,UUID,PKNAME"],
        timeout=12,
    )
    if not ok or not out.strip().startswith("{"):
        return []
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        return []

    devices: list[dict[str, Any]] = []

    def walk(node: dict[str, Any], parent: str | None = None) -> None:
        name = node.get("name") or ""
        size = node.get("size")
        rota = node.get("rota")
        media = "SSD/NVMe" if rota == 0 else ("HDD" if rota == 1 else "—")
        if (node.get("tran") or "").lower() in ("nvme",):
            media = "NVMe"
        devices.append({
            "name": name,
            "path": f"/dev/{name}",
            "parent": parent,
            "size_bytes": size,
            "size_human": _bytes_human(size),
            "type": node.get("type"),
            "media": media,
            "model": (node.get("model") or "").strip() or None,
            "serial": (node.get("serial") or "").strip() or None,
            "vendor": (node.get("vendor") or "").strip() or None,
            "revision": (node.get("rev") or "").strip() or None,
            "transport": (node.get("tran") or "").strip() or None,
            "fstype": node.get("fstype"),
            "mountpoint": node.get("mountpoint"),
            "uuid": node.get("uuid"),
            "removable": bool(node.get("rm")),
            "read_only": bool(node.get("ro")),
        })
        for child in node.get("children") or []:
            walk(child, name)

    for blk in data.get("blockdevices") or []:
        walk(blk)
    return devices


def _mounts() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        for line in Path("/proc/mounts").read_text(encoding="utf-8", errors="replace").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            dev, mnt, fstype = parts[0], parts[1], parts[2]
            opts = parts[3] if len(parts) > 3 else ""
            usage = None
            if mnt.startswith("/") and not dev.startswith("tmpfs"):
                try:
                    du = shutil.disk_usage(mnt)
                    usage = {
                        "total_bytes": du.total,
                        "used_bytes": du.used,
                        "free_bytes": du.free,
                        "used_pct": round(100 * du.used / du.total, 1) if du.total else None,
                        "total_human": _bytes_human(du.total),
                        "used_human": _bytes_human(du.used),
                        "free_human": _bytes_human(du.free),
                    }
                except OSError:
                    pass
            rows.append({"device": dev, "mount": mnt, "fstype": fstype, "options": opts, "usage": usage})
    except OSError:
        pass
    return rows


def _storage_section() -> dict[str, Any]:
    physical = _physical_disks()
    devices = _lsblk_devices()
    mounts = _mounts()
    root = next((m for m in mounts if m.get("mount") == "/"), None)
    disks = [d for d in devices if d.get("type") == "disk"]
    parts = [d for d in devices if d.get("type") in ("part", "lvm", "crypt")]
    total_bytes = sum(d.get("size_bytes") or 0 for d in physical) or sum(d.get("size_bytes") or 0 for d in disks)
    return {
        "physical_disks": physical,
        "block_devices": devices,
        "disk_count": len(physical) or len(disks),
        "partition_count": len(parts),
        "total_capacity_human": _bytes_human(total_bytes) if total_bytes else None,
        "root_usage": root.get("usage") if root else None,
        "mounts": mounts,
    }


def _dmi_section() -> dict[str, Any]:
    fields = {
        "system_vendor": "sys_vendor",
        "system_product": "product_name",
        "system_version": "product_version",
        "system_serial": "product_serial",
        "system_uuid": "product_uuid",
        "board_vendor": "board_vendor",
        "board_name": "board_name",
        "board_version": "board_version",
        "board_serial": "board_serial",
        "bios_vendor": "bios_vendor",
        "bios_version": "bios_version",
        "bios_date": "bios_date",
        "chassis_vendor": "chassis_vendor",
        "chassis_type": "chassis_type",
        "chassis_version": "chassis_version",
        "chassis_serial": "chassis_serial",
    }
    out: dict[str, Any] = {}
    for label, fname in fields.items():
        val = _read_text(f"/sys/class/dmi/id/{fname}")
        if val and val not in ("None", "To Be Filled By O.E.M.", "Default string", "Not Specified"):
            out[label] = val
    ctype = out.get("chassis_type")
    if ctype and str(ctype).isdigit():
        out["chassis_type_label"] = _CHASSIS_TYPES.get(str(ctype), f"Type {ctype}")
    return out


def _pci_devices() -> list[dict[str, str]]:
    ok, out = _run(["lspci"], timeout=12)
    if not ok:
        return []
    rows = []
    for line in out.splitlines():
        m = re.match(r"^([0-9a-f:\.]+)\s+(.+)$", line.strip(), re.I)
        if m:
            rows.append({"slot": m.group(1), "description": m.group(2).strip()})
    return rows


def _usb_devices() -> list[dict[str, str]]:
    ok, out = _run(["lsusb"], timeout=8)
    if not ok:
        return []
    rows = []
    for line in out.splitlines():
        m = re.match(r"^Bus\s+(\d+)\s+Device\s+(\d+):\s+ID\s+([0-9a-f:]+)\s+(.+)$", line.strip(), re.I)
        if m:
            rows.append({
                "bus": m.group(1),
                "device": m.group(2),
                "id": m.group(3),
                "description": m.group(4).strip(),
            })
    return rows


def _gpu_section() -> dict[str, Any]:
    cards = []
    try:
        for card in sorted(Path("/sys/class/drm").glob("card*")):
            if not card.is_dir() or "-" in card.name:
                continue
            dev = _read_text(card / "device" / "uevent")
            vendor = model = None
            for line in dev.splitlines():
                if line.startswith("PCI_ID="):
                    vendor = line.split("=", 1)[1]
                elif line.startswith("PCI_SUBSYS_NAME="):
                    model = line.split("=", 1)[1]
            cards.append({
                "id": card.name,
                "vendor_pci": vendor,
                "status": _read_text(card / "device" / "power/runtime_status") or None,
            })
    except OSError:
        pass
    pci_gpus = [p for p in _pci_devices() if re.search(r"VGA|3D|Display", p["description"], re.I)]
    return {"drm_cards": cards, "pci": pci_gpus}


def _audio_devices() -> list[dict[str, str]]:
    cards: list[dict[str, str]] = []
    try:
        for line in Path("/proc/asound/cards").read_text(encoding="utf-8", errors="replace").splitlines():
            m = re.match(r"^\s*(\d+)\s+\[([^\]]+)\]\s*:\s*(.+)$", line)
            if m:
                cards.append({"index": m.group(1), "id": m.group(2), "name": m.group(3).strip()})
    except OSError:
        pass
    return cards


def _power_section() -> dict[str, Any]:
    batteries: list[dict[str, Any]] = []
    ac_online = None
    try:
        for ps in Path("/sys/class/power_supply").iterdir():
            typ = _read_text(ps / "type").lower()
            if typ == "mains" or ps.name.upper().startswith("AC"):
                online = _read_text(ps / "online")
                if online in ("0", "1"):
                    ac_online = online == "1"
            if typ != "battery" and not ps.name.upper().startswith("BAT"):
                continue
            cap = _read_int(ps / "capacity")
            status = _read_text(ps / "status")
            bat: dict[str, Any] = {
                "name": ps.name,
                "capacity_pct": cap,
                "status": status or None,
                "manufacturer": _read_text(ps / "manufacturer") or None,
                "model": _read_text(ps / "model_name") or None,
                "technology": _read_text(ps / "technology") or None,
                "cycle_count": _read_int(ps / "cycle_count"),
            }
            for label, fname, scale in (
                ("voltage_v", "voltage_now", 1_000_000),
                ("power_w", "power_now", 1_000_000),
                ("energy_full_wh", "energy_full", 1_000_000),
                ("energy_now_wh", "energy_now", 1_000_000),
            ):
                raw = _read_int(ps / fname)
                if raw is not None:
                    bat[label] = round(raw / scale, 2)
            batteries.append(bat)
    except OSError:
        pass
    return {"ac_online": ac_online, "batteries": batteries}


def _sensors_section() -> dict[str, Any]:
    fans: list[dict[str, Any]] = []
    hwmon: list[dict[str, Any]] = []
    try:
        for chip in Path("/sys/class/hwmon").iterdir():
            name = _read_text(chip / "name") or chip.name
            temps = []
            for tp in sorted(chip.glob("temp*_input")):
                raw = _read_int(tp)
                label_path = chip / tp.name.replace("_input", "_label")
                label = _read_text(label_path) or tp.name.replace("_input", "")
                if raw is not None:
                    temps.append({"label": label, "temp_c": round(raw / 1000, 1)})
            fans_list = []
            for fn in sorted(chip.glob("fan*_input")):
                raw = _read_int(fn)
                if raw is not None:
                    fans_list.append({"label": fn.name.replace("_input", ""), "rpm": raw})
            if temps or fans_list:
                hwmon.append({"chip": name, "temps": temps, "fans": fans_list})
            fans.extend(fans_list)
    except OSError:
        pass
    return {"hwmon": hwmon}


def _security_firmware() -> dict[str, Any]:
    out: dict[str, Any] = {}
    sb = list(Path("/sys/firmware/efi/efivars").glob("SecureBoot-*")) if Path("/sys/firmware/efi/efivars").is_dir() else []
    out["efi_present"] = Path("/sys/firmware/efi").is_dir()
    out["secure_boot_vars"] = len(sb) > 0
    ok, val = _run(["cat", "/sys/kernel/security/apparmor/profiles"], timeout=3) if Path("/sys/kernel/security/apparmor").is_dir() else (False, "")
    out["apparmor"] = Path("/sys/kernel/security/apparmor").is_dir()
    if Path("/sys/fs/selinux/enforce").is_file():
        out["selinux"] = _read_text("/sys/fs/selinux/enforce")
    tpm = list(Path("/sys/class/tpm").glob("tpm*")) if Path("/sys/class/tpm").is_dir() else []
    out["tpm_devices"] = [p.name for p in tpm]
    return out


def _runtime_section() -> dict[str, Any]:
    proc_count = 0
    try:
        proc_count = sum(1 for _ in Path("/proc").iterdir() if _.name.isdigit())
    except OSError:
        pass
    users: list[str] = []
    ok, out = _run(["who"], timeout=4)
    if ok:
        users = [ln.split()[0] for ln in out.splitlines() if ln.strip()]
    return {
        "process_count": proc_count,
        "logged_in_users": sorted(set(users)),
        "uid": os.getuid(),
        "gid": os.getgid(),
        "user": os.environ.get("USER") or os.environ.get("LOGNAME"),
    }


def _numa_section() -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    try:
        for node in sorted(Path("/sys/devices/system/node").glob("node*")):
            if not node.is_dir():
                continue
            meminfo: dict[str, int] = {}
            try:
                for line in (node / "meminfo").read_text(encoding="utf-8").splitlines():
                    key, _, val = line.partition(":")
                    if val.strip().split():
                        num = val.strip().split()[0]
                        if num.isdigit():
                            meminfo[key.strip()] = int(num)
            except OSError:
                pass
            try:
                cpu_list = _read_text(node / "cpulist")
            except OSError:
                cpu_list = ""
            nodes.append({
                "node": node.name,
                "cpus": cpu_list,
                "mem_total_kb": meminfo.get("MemTotal"),
                "mem_free_kb": meminfo.get("MemFree"),
            })
    except OSError:
        pass
    return nodes


def pc_info_payload(*, force: bool = False) -> dict[str, Any]:
    now = time.time()
    if not force:
        cached = _CACHE.get("data")
        if cached and now - float(_CACHE.get("ts") or 0) < _TTL:
            return cached

    payload: dict[str, Any] = {
        "ok": True,
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now)),
        "system": _system_section(),
        "cpu": _cpu_section(),
        "memory": _memory_section(),
        "storage": _storage_section(),
        "firmware": _dmi_section(),
        "gpu": _gpu_section(),
        "pci": _pci_devices(),
        "usb": _usb_devices(),
        "audio": _audio_devices(),
        "power": _power_section(),
        "sensors": _sensors_section(),
        "security_firmware": _security_firmware(),
        "runtime": _runtime_section(),
        "numa": _numa_section(),
    }
    _CACHE["ts"] = now
    _CACHE["data"] = payload
    return payload
