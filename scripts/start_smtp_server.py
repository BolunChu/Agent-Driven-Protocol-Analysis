"""Start a minimal local SMTP server for probe validation on port 2525.

Uses Python's built-in asyncio + smtplib-compatible handler instead of the
deprecated smtpd/asyncore modules (removed in Python 3.12).

If aiosmtpd is installed it is used; otherwise falls back to a raw TCP
socket that speaks just enough SMTP to satisfy probe_service probes.
"""
from __future__ import annotations

import asyncio
import sys


# ---------------------------------------------------------------------------
# Preferred path: aiosmtpd (pip install aiosmtpd)
# ---------------------------------------------------------------------------

def _run_with_aiosmtpd(host: str, port: int) -> None:
    from aiosmtpd.controller import Controller

    class LogHandler:
        async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
            envelope.rcpt_tos.append(address)
            return "250 OK"

        async def handle_DATA(self, server, session, envelope):
            print(
                f"[SMTP/aiosmtpd] FROM={envelope.mail_from} "
                f"TO={envelope.rcpt_tos} size={len(envelope.content or b'')} bytes"
            )
            return "250 Message accepted"

    controller = Controller(LogHandler(), hostname=host, port=port)
    controller.start()
    print(f"SMTP probe server started on {host}:{port}  (aiosmtpd)")
    print("Press Ctrl+C to stop")
    try:
        asyncio.get_event_loop().run_forever()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()


# ---------------------------------------------------------------------------
# Fallback path: raw asyncio TCP server (no external dependencies)
# ---------------------------------------------------------------------------

class _SMTPFallbackProtocol(asyncio.Protocol):
    """Minimal SMTP server that handles EHLO/MAIL/RCPT/DATA/QUIT."""

    def connection_made(self, transport: asyncio.Transport) -> None:  # type: ignore[override]
        self._transport = transport
        self._state = "INIT"
        self._send("220 localhost ESMTP ProbeServer ready")

    def data_received(self, data: bytes) -> None:
        text = data.decode("utf-8", errors="replace")
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            upper = line.upper()
            if upper.startswith("EHLO") or upper.startswith("HELO"):
                domain = line.split(None, 1)[1] if " " in line else "client"
                self._send(f"250-localhost Hello {domain}")
                self._send("250-SIZE 10485760")
                self._send("250-AUTH PLAIN LOGIN")
                self._send("250 HELP")
                self._state = "GREETED"
            elif upper.startswith("MAIL FROM"):
                self._send("250 Ok")
                self._state = "MAIL"
            elif upper.startswith("RCPT TO"):
                self._send("250 Ok")
                self._state = "RCPT"
            elif upper.startswith("DATA"):
                self._send("354 End data with <CR><LF>.<CR><LF>")
                self._state = "DATA"
            elif self._state == "DATA" and line == ".":
                self._send("250 Ok: queued as 00000")
                self._state = "GREETED"
                print("[SMTP/fallback] message accepted")
            elif upper.startswith("RSET"):
                self._send("250 Ok")
                self._state = "GREETED"
            elif upper.startswith("NOOP"):
                self._send("250 Ok")
            elif upper.startswith("VRFY"):
                self._send("252 Cannot VRFY, will attempt")
            elif upper.startswith("AUTH"):
                self._send("235 Authentication successful")
                self._state = "AUTHENTICATED"
            elif upper.startswith("STARTTLS"):
                self._send("454 TLS not available on probe server")
            elif upper.startswith("QUIT"):
                self._send("221 Bye")
                self._transport.close()
            else:
                if self._state == "DATA":
                    pass  # absorb body lines
                else:
                    self._send("500 Unrecognised command")

    def _send(self, msg: str) -> None:
        self._transport.write((msg + "\r\n").encode("utf-8"))


def _run_fallback(host: str, port: int) -> None:
    async def _serve():
        loop = asyncio.get_event_loop()
        server = await loop.create_server(_SMTPFallbackProtocol, host, port)
        print(f"SMTP probe server started on {host}:{port}  (built-in asyncio fallback)")
        print("Press Ctrl+C to stop")
        async with server:
            await server.serve_forever()

    try:
        asyncio.run(_serve())
    except KeyboardInterrupt:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    host = "127.0.0.1"
    port = 2525
    try:
        _run_with_aiosmtpd(host, port)
    except ImportError:
        print("[SMTP] aiosmtpd not found, using built-in asyncio fallback")
        _run_fallback(host, port)


if __name__ == "__main__":
    main()
