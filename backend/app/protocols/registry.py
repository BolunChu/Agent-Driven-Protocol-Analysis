from __future__ import annotations

from .base import ProtocolAdapter
from .ftp.adapter import FTPProtocolAdapter
from .smtp import SMTPProtocolAdapter
from .rtsp import RTSPProtocolAdapter
from .http import HTTPProtocolAdapter


_ADAPTERS: dict[str, ProtocolAdapter] = {
    "FTP": FTPProtocolAdapter(),
    "SMTP": SMTPProtocolAdapter(),
    "RTSP": RTSPProtocolAdapter(),
    "HTTP": HTTPProtocolAdapter(),
}


def get_protocol_adapter(protocol_name: str) -> ProtocolAdapter:
    key = (protocol_name or "").strip().upper()
    if key not in _ADAPTERS:
        raise ValueError(f"Unsupported protocol: {protocol_name}")
    return _ADAPTERS[key]


def list_supported_protocols() -> list[str]:
    return sorted(_ADAPTERS.keys())
