"""
Local backup + CSV export for the CRM.

Air-gapped means the customer database lives on a single machine with no cloud copy.
These helpers make durable local copies (timestamped DB snapshots) and human-readable
CSV exports the operator can move to a second drive / USB.
"""

import csv
import logging
import shutil
import time
from dataclasses import fields
from pathlib import Path

from .repository import CRMRepository

logger = logging.getLogger(__name__)


def backup_database(db_path: Path | str, dest_dir: Path | str, keep: int = 30) -> Path:
    """Copy the SQLite DB to a timestamped snapshot; prune to the newest `keep`."""
    db_path = Path(db_path)
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = dest / f"crm-{stamp}.db"
    # sqlite files copy safely when the writer isn't mid-transaction; copy2 is atomic
    # enough for a single-workstation deployment and we keep many snapshots anyway.
    shutil.copy2(db_path, target)
    _prune(dest, "crm-*.db", keep)
    logger.info(f"CRM backup written: {target}")
    return target


def export_csv(repo: CRMRepository, dest_dir: Path | str) -> list[Path]:
    """Export contacts, companies, and deals to CSV files. Returns written paths."""
    dest = Path(dest_dir)
    dest.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    written = [
        _write_csv(dest / f"contacts-{stamp}.csv", repo.list_contacts(limit=100000)),
        _write_csv(dest / f"companies-{stamp}.csv", repo.list_companies(limit=100000)),
        _write_csv(dest / f"deals-{stamp}.csv", repo.list_deals()),
    ]
    logger.info(f"CRM CSV export written to {dest}")
    return written


def _write_csv(path: Path, rows: list) -> Path:
    """Write a list of dataclass rows to CSV (columns = dataclass fields)."""
    if not rows:
        path.write_text("", encoding="utf-8")
        return path
    columns = [f.name for f in fields(rows[0])]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow(row.to_dict())
    return path


def _prune(directory: Path, pattern: str, keep: int) -> None:
    """Keep only the newest `keep` files matching pattern."""
    snapshots = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    for stale in snapshots[keep:]:
        stale.unlink(missing_ok=True)
