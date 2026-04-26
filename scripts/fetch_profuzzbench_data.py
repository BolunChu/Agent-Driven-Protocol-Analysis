"""Fetch/import ProFuzzBench-like seed data into protocol-specific directories.

Usage examples:
1) Import from local extracted directory:
   python3 scripts/fetch_profuzzbench_data.py --from-local /path/to/seeds

2) Download a zip then import:
   python3 scripts/fetch_profuzzbench_data.py --zip-url https://example.com/profuzzbench.zip

Files are copied to:
  data/traces/profuzzbench/<protocol>/*.raw
"""

from __future__ import annotations

import argparse
import shutil
import tempfile
import zipfile
from pathlib import Path
from urllib.request import urlretrieve

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEST_ROOT = PROJECT_ROOT / "data" / "traces" / "profuzzbench"


def infer_protocol(path: Path) -> str | None:
    text = path.as_posix().lower()
    name = path.name.lower()
    if any(k in text for k in ["ftp", "proftpd", "pureftp", "vsftpd"]):
        return "ftp"
    if any(k in text for k in ["smtp", "postfix", "exim"]):
        return "smtp"
    if "rtsp" in text:
        return "rtsp"
    if any(k in text for k in ["http", "nginx", "apache"]):
        return "http"
    if name.endswith(".raw") and "seed" in name:
        return "ftp"
    return None


def import_from_dir(source: Path) -> dict[str, int]:
    stats: dict[str, int] = {"ftp": 0, "smtp": 0, "rtsp": 0, "http": 0}
    for file in source.rglob("*.raw"):
        protocol = infer_protocol(file)
        if not protocol:
            continue
        dest_dir = DEST_ROOT / protocol
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / file.name
        shutil.copy2(file, dest_path)
        stats[protocol] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-local", type=str, default="", help="Local directory containing ProFuzzBench seeds")
    parser.add_argument("--zip-url", type=str, default="", help="Remote zip URL to download and import")
    args = parser.parse_args()

    if not args.from_local and not args.zip_url:
        print("No data source provided. Use --from-local or --zip-url.")
        return

    if args.from_local:
        source = Path(args.from_local).expanduser().resolve()
        if not source.exists():
            raise SystemExit(f"Source directory does not exist: {source}")
        stats = import_from_dir(source)
        print("Import complete from local source:", stats)
        return

    with tempfile.TemporaryDirectory(prefix="profuzzbench_zip_") as tmpdir:
        tmp = Path(tmpdir)
        zip_path = tmp / "profuzzbench.zip"
        print(f"Downloading {args.zip_url} ...")
        urlretrieve(args.zip_url, zip_path)
        extract_dir = tmp / "extract"
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_dir)
        stats = import_from_dir(extract_dir)
        print("Download + import complete:", stats)


if __name__ == "__main__":
    main()
