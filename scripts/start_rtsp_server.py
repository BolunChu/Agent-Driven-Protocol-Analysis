"""Start a minimal local RTSP-like server for probe validation on port 8554."""

from __future__ import annotations

import socketserver


class ProbeRTSPHandler(socketserver.BaseRequestHandler):
    def handle(self):
        buffer = b""
        while True:
            data = self.request.recv(4096)
            if not data:
                break
            buffer += data
            while b"\r\n\r\n" in buffer:
                packet, buffer = buffer.split(b"\r\n\r\n", 1)
                text = packet.decode("utf-8", errors="replace")
                lines = text.splitlines()
                if not lines:
                    continue
                first = lines[0]
                parts = first.split()
                method = parts[0].upper() if parts else "OPTIONS"
                cseq = "1"
                for line in lines[1:]:
                    if line.lower().startswith("cseq:"):
                        cseq = line.split(":", 1)[1].strip()
                        break
                response = (
                    "RTSP/1.0 200 OK\r\n"
                    f"CSeq: {cseq}\r\n"
                    f"Public: OPTIONS, DESCRIBE, SETUP, PLAY, TEARDOWN\r\n"
                    f"X-Method: {method}\r\n\r\n"
                )
                self.request.sendall(response.encode("utf-8"))


class ThreadedRTSPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True


def main() -> None:
    with ThreadedRTSPServer(("127.0.0.1", 8554), ProbeRTSPHandler) as server:
        print("RTSP probe server started on 127.0.0.1:8554")
        print("Press Ctrl+C to stop")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
