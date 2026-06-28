from nordctl.listeners import (
    PORT_LABELS,
    _bind_scope,
    _parse_ss_addr,
    _port_label,
    _resolve_process,
)


def test_parse_ss_addr_ipv4():
    assert _parse_ss_addr("0.0.0.0:22") == ("0.0.0.0", 22)
    assert _parse_ss_addr("127.0.0.1:8765") == ("127.0.0.1", 8765)


def test_parse_ss_addr_wildcard():
    assert _parse_ss_addr("*:18073") == ("*", 18073)


def test_bind_scope():
    assert _bind_scope("127.0.0.1") == "localhost"
    assert _bind_scope("0.0.0.0") == "lan"
    assert _bind_scope("::") == "lan"


def test_port_label_known():
    extra = {8022: "SSH (dropbear)"}
    assert _port_label(22, extra) == "SSH"
    assert _port_label(8022, extra) == "SSH (dropbear)"
    assert _port_label(99999, extra) == ""


def test_resolve_process_uses_label():
    proc = _resolve_process("0.0.0.0:22", "", {}, {}, PORT_LABELS)
    assert proc == "SSH"
