#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hg-FITS-Duplicate-Finder
Find and quarantine byte-for-byte identical FITS files within a folder tree.

This is a standalone companion script to hg-nina-fits-organizer.py. It scans
a folder recursively for *.fits / *.fit files, groups them by content
(size + SHA-256 hash, filename is irrelevant), and moves every duplicate but
the first one (alphabetically by path) into a quarantine folder instead of
deleting it, so accidental false positives remain recoverable.

Verwendung:
    python hg-remove-duplicates.py <ordner> [--dry-run]

Parameter:
    <ordner>    Pfad zum Ordner, der rekursiv nach doppelten FITS-Dateien
                durchsucht werden soll.
    --dry-run   Zeigt nur an, welche Dateien als Duplikate erkannt und
                verschoben wuerden. Es werden keine Dateien verschoben.

Beispiele:
    python hg-remove-duplicates.py K:\\NINA3\\2026_Snapshot_ASA10_ASI6200MM-Pro\\LIGHT
    python hg-remove-duplicates.py K:\\NINA3 --dry-run

Hinweis:
    Von jeder Gruppe inhaltlich identischer Dateien bleibt die Datei mit dem
    (alphabetisch) ersten Pfad unangetastet an ihrem Ort. Alle weiteren
    Dateien der Gruppe werden - unter Beibehaltung ihres relativen Pfads -
    in einen Quarantaene-Ordner "_DUPLICATES_REMOVED" im Basisordner
    verschoben, NICHT geloescht. Eine Zeitstempel-Logdatei wird im
    Basisordner angelegt.

Copyright (c) 2024-2025 by ramona & hagen.gloetter@gmail.com
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List

QUARANTINE_DIR_NAME = "_DUPLICATES_REMOVED"
IGNORED_SCAN_FOLDERS = {
    QUARANTINE_DIR_NAME.upper(),
    "PRO",
    "FINAL",
    ".GIT",
    ".GITHUB",
    ".VSCODE",
    "__PYCACHE__",
    "ASTRO_ENV",
    "ASTRO_ENV_WIN",
    "ASTRO_ENV_LINUX",
    ".VENV",
    "VENV",
    "ENV",
    "$RECYCLE.BIN",
    "SYSTEM VOLUME INFORMATION",
}


class DuplicateSummary:
    """Collect counts for the final console summary."""

    def __init__(self) -> None:
        self.groups_found = 0
        self.duplicates_quarantined = 0
        self.bytes_reclaimed = 0
        self.errors = 0


def setup_logging(root_dir: Path) -> Path:
    """Set up console and file logging once and return the log file path."""
    log_filename = f"{datetime.now():%Y-%m-%d_%H-%M-%S}_duplicate_finder.log"
    log_path = root_dir / log_filename

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.WARNING)
    logger.addHandler(console_handler)

    logging.info("Starte Duplikatsuche in: %s", root_dir)
    return log_path


def compute_file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute a SHA-256 hash of a file's contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def iter_fits_files(root_dir: Path) -> Iterable[Path]:
    """Recursively discover *.fits / *.fit files, skipping ignored/quarantine folders."""
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if d.upper() not in IGNORED_SCAN_FOLDERS and not d.startswith(".")]
        root_path = Path(root)
        for file_name in files:
            lower_name = file_name.lower()
            if lower_name.endswith(".fits") or lower_name.endswith(".fit"):
                yield root_path / file_name


def find_duplicate_groups(files: List[Path], summary: DuplicateSummary) -> List[List[Path]]:
    """Group files by (size, hash); return only groups with more than one member, sorted by path."""
    print(f"Pruefe Dateigroessen von {len(files)} Dateien ...")
    by_size: Dict[int, List[Path]] = {}
    for file_path in files:
        try:
            size = file_path.stat().st_size
        except OSError as exc:
            summary.errors += 1
            logging.error("Konnte Dateigroesse nicht lesen: %s (%s)", file_path, exc)
            continue
        by_size.setdefault(size, []).append(file_path)

    hash_candidates = sum(len(paths) for paths in by_size.values() if len(paths) > 1)
    print(f"{hash_candidates} Dateien mit gleicher Groesse gefunden, werden per Hash verglichen ...")
    logging.info("%s Dateien gescannt, %s Kandidaten werden gehasht", len(files), hash_candidates)

    groups: List[List[Path]] = []
    hashed_count = 0
    progress_interval = max(1, hash_candidates // 20) if hash_candidates else 1
    for size, candidates in by_size.items():
        if len(candidates) < 2:
            continue
        by_hash: Dict[str, List[Path]] = {}
        for file_path in candidates:
            try:
                file_hash = compute_file_hash(file_path)
            except OSError as exc:
                summary.errors += 1
                logging.error("Konnte Datei nicht lesen: %s (%s)", file_path, exc)
                continue
            by_hash.setdefault(file_hash, []).append(file_path)
            hashed_count += 1
            if hashed_count % progress_interval == 0 or hashed_count == hash_candidates:
                print(f"  ... {hashed_count}/{hash_candidates} Dateien geprueft")
        for hash_value, paths in by_hash.items():
            if len(paths) > 1:
                groups.append(sorted(paths, key=str))

    return groups


def build_quarantine_path(file_path: Path, root_dir: Path, quarantine_root: Path) -> Path:
    """Mirror the file's relative path under the quarantine root to keep it traceable and unique."""
    relative_path = file_path.relative_to(root_dir)
    return quarantine_root / relative_path


def ensure_unique_path(path: Path) -> Path:
    """Avoid overwriting existing files by appending numeric suffixes."""
    if not path.exists():
        return path

    stem = path.stem
    suffix = path.suffix
    counter = 1
    while True:
        candidate = path.with_name(f"{stem}_{counter}{suffix}")
        if not candidate.exists():
            return candidate
        counter += 1


def process_directory(root_dir: Path, dry_run: bool) -> DuplicateSummary:
    """Find duplicate FITS files under root_dir and quarantine every extra copy per group."""
    summary = DuplicateSummary()
    print(f"Durchsuche {root_dir} rekursiv nach *.fits/*.fit Dateien ('{QUARANTINE_DIR_NAME}' wird dabei immer ausgeschlossen) ...")
    files = list(iter_fits_files(root_dir))
    print(f"{len(files)} FITS-Dateien gefunden.")
    groups = find_duplicate_groups(files, summary)
    summary.groups_found = len(groups)

    if not groups:
        print("Keine Duplikate gefunden.")
        return summary

    run_stamp = f"{datetime.now():%Y-%m-%d_%H-%M-%S}"
    quarantine_root = root_dir / QUARANTINE_DIR_NAME / run_stamp

    for group in groups:
        keeper, *duplicates = group
        logging.info("Gruppe identischer Dateien (%s Kopien): behalte %s", len(group), keeper)
        print(f"\n[GRUPPE] {len(group)} identische Kopien - behalte: {keeper}")

        for duplicate_path in duplicates:
            try:
                file_size = duplicate_path.stat().st_size
                destination = build_quarantine_path(duplicate_path, root_dir, quarantine_root)
                destination = ensure_unique_path(destination)
                status = "DRY-RUN" if dry_run else "VERSCHOBEN"
                print(f"  [{status:10}] {duplicate_path} -> {destination}")
                logging.info("Duplikat in Quarantaene: %s -> %s", duplicate_path, destination)
                if not dry_run:
                    destination.parent.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(duplicate_path), str(destination))
                summary.duplicates_quarantined += 1
                summary.bytes_reclaimed += file_size
            except OSError as exc:
                summary.errors += 1
                logging.error("Fehler beim Verschieben von %s: %s", duplicate_path, exc)

    return summary


def print_summary(root_dir: Path, log_path: Path, summary: DuplicateSummary, dry_run: bool) -> None:
    """Print a compact, human-readable processing summary."""
    action_label = "Vorgesehen" if dry_run else "Verschoben"
    size_mb = summary.bytes_reclaimed / (1024 * 1024)

    print("\n" + "=" * 64)
    print("FITS DUPLICATE FINDER - ZUSAMMENFASSUNG")
    print("=" * 64)
    print(f"Quelle         : {root_dir}")
    print(f"Modus          : {'DRY-RUN (keine Änderungen)' if dry_run else 'ECHTLAUF'}")
    print(f"Gruppen        : {summary.groups_found} mit identischem Inhalt")
    print(f"{action_label:14} : {summary.duplicates_quarantined} Duplikate")
    print(f"Platz frei     : {size_mb:.1f} MB")
    print(f"Fehler         : {summary.errors}")
    print(f"\nLogdatei       : {log_path}")
    print("=" * 64)


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(
        description="Findet inhaltlich identische FITS-Dateien und verschiebt Duplikate in Quarantaene."
    )
    parser.add_argument("source", help="Pfad zum Ordner, der rekursiv durchsucht werden soll")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, welche Duplikate verschoben würden.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    root_dir = Path(args.source).expanduser().resolve()
    if not root_dir.exists() or not root_dir.is_dir():
        print(f"FEHLER: Ordner existiert nicht: {root_dir}")
        return 1

    print("=" * 64)
    print("FITS DUPLICATE FINDER")
    print("=" * 64)
    print(f"Quelle: {root_dir}")
    print(f"Hinweis: Der Quarantaene-Ordner '{QUARANTINE_DIR_NAME}' wird beim Scannen immer automatisch ausgeschlossen.")
    if args.dry_run:
        print("Modus: DRY-RUN - es werden keine Dateien verschoben")
    print()
    log_path = setup_logging(root_dir)
    summary = process_directory(root_dir, dry_run=args.dry_run)
    logging.info(
        "Duplikatsuche abgeschlossen. groups=%s quarantined=%s errors=%s",
        summary.groups_found,
        summary.duplicates_quarantined,
        summary.errors,
    )
    print_summary(root_dir, log_path, summary, dry_run=args.dry_run)

    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())
