"""Start a local FTP server on port 2121 using pyftpdlib."""

import os
import tempfile
from pathlib import Path
from pyftpdlib.authorizers import DummyAuthorizer
from pyftpdlib.handlers import FTPHandler
from pyftpdlib.servers import FTPServer


def main():
    ftproot = tempfile.mkdtemp(prefix="ftp_probe_root_")
    root = Path(ftproot)

    for fname, content in [
        ("readme.txt", "protocol-analysis demo file\n"),
        ("data.bin", "binary-placeholder\n"),
        ("report.pdf", "pdf-placeholder\n"),
        ("backup.tar.gz", "archive-placeholder\n"),
        ("upload.txt", "append target\n"),
    ]:
        (root / fname).write_text(content)

    for subdir in ["pub", "incoming", "logs", "nested/dir"]:
        (root / subdir).mkdir(parents=True, exist_ok=True)

    (root / "pub" / "index.txt").write_text("public index\n")
    (root / "incoming" / "drop.txt").write_text("drop zone\n")
    (root / "logs" / "ftp.log").write_text("log placeholder\n")

    authorizer = DummyAuthorizer()
    authorizer.add_user("ubuntu", "ubuntu", ftproot, perm="elradfmwMT")
    authorizer.add_user("admin", "admin123", ftproot, perm="elradfmwMT")
    authorizer.add_user("testuser", "test1234", ftproot, perm="elradfmwMT")
    authorizer.add_anonymous(ftproot, perm="elr")

    handler = FTPHandler
    handler.authorizer = authorizer
    handler.passive_ports = range(60000, 60100)
    handler.banner = "220 Protocol Analysis FTP Server Ready"

    server = FTPServer(("127.0.0.1", 2121), handler)
    print(f"FTP server started on 127.0.0.1:2121 (root: {ftproot})")
    print("Press Ctrl+C to stop")
    server.serve_forever()


if __name__ == "__main__":
    main()
