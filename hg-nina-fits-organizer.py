#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hg-NINA-FITS-Organizer
Organize and rename FITS files produced by N.I.N.A.
This Python script organizes and renames FITS files created by the 
astrophotography software N.I.N.A.. 
It reads FITS headers and automatically restructures folders and filenames 
based on imaging parameters and object names.

Verwendung:
    python hg-nina-fits-organizer.py <nina-ordner> [--dry-run]

Parameter:
    <nina-ordner>  Pfad zum N.I.N.A.-Basisordner.
                   Darunter werden FITS-Dateien in den Ordnern LIGHT, DARK,
                   FLAT, BIAS und SNAPSHOT verarbeitet.
    --dry-run      Zeigt die geplanten Verschiebungen nur an. Es werden keine
                   Dateien verschoben und keine leeren Quellordner geloescht.

Beispiele:
    python hg-nina-fits-organizer.py D:\\Bilder\\NINA\\2025-01-15
    python hg-nina-fits-organizer.py D:\\Bilder\\NINA\\2025-01-15 --dry-run
    python hg-nina-fits-organizer.py /home/user/bilder/nina/2025-01-15

Hinweis:
    Die Dateien werden anhand von Jahr, OBJECT, Teleskop und Kamera in einen
    Hauptordner einsortiert
    und umbenannt. Die Originaldateien werden dabei verschoben. Vor dem ersten
    echten Lauf wird ein Test mit --dry-run empfohlen. Eine Zeitstempel-Logdatei
    wird im angegebenen N.I.N.A.-Basisordner angelegt.

Copyright (c) 2024-2025 by ramona & hagen.gloetter@gmail.com
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable

from astropy.io import fits

SUPPORTED_CAPTURE_DIRS = {"LIGHT", "DARK", "FLAT", "BIAS", "SNAPSHOT"}
TARGET_SUBDIR_MAP = {"SNAPSHOT": "PROCESSING"}
CRITICAL_FIELDS = ("OBJECT", "TELESCOP", "DATE-LOC", "FOCALLEN", "EXPOSURE", "CAMERAID")


class ProcessingSummary:
    """Collect processing counts for the final console summary."""

    def __init__(self) -> None:
        self.moved = 0
        self.skipped = 0
        self.errors = 0
        self.empty_dirs = 0
        self.target_dirs: set[Path] = set()
        self.files_by_type: Dict[str, int] = {}


def setup_logging(source_dir: Path) -> Path:
    """Set up console and file logging once and return the log file path."""
    log_filename = f"{datetime.now():%Y-%m-%d_%H-%M-%S}_fits_organizer.log"
    log_path = source_dir / log_filename

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

    logging.info("Starte Verarbeitung in: %s", source_dir)
    return log_path


def clean_string(value: object) -> str:
    """Normalize values for filesystem-safe names."""
    text = str(value).strip()
    text = text.replace(" ", "-")
    text = re.sub(r"[\\/:*?\"<>|]", "-", text)
    return clean_dashes(text)


def clean_dashes(text: str) -> str:
    """Collapse repeated dashes and trim edges."""
    return re.sub(r"-{2,}", "-", text).strip("-")


def clean_camera_name(camera_id: object) -> str:
    """Remove common noisy camera prefixes and normalize spacing."""
    camera_text = str(camera_id)
    camera_text = camera_text.replace("ZWOptical_ZWO", "").replace("ZWO", "")
    camera_text = clean_string(camera_text)
    return clean_dashes(camera_text.strip(" _-"))


def ensure_project_structure(target_dir: Path) -> int:
    """Create PRO and FINAL folders in a target directory and seed the required placeholder files."""
    created_dirs = 0
    for folder_name in ("PRO", "FINAL"):
        dir_path = target_dir / folder_name
        if not dir_path.exists():
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs += 1

    pro_dir = target_dir / "PRO"
    final_dir = target_dir / "FINAL"

    pro_file = pro_dir / "Processing_Daten_hier.txt"
    if not pro_file.exists():
        pro_file.write_text("", encoding="utf-8")

    final_file = final_dir / "Fertige_Bilder_hier.txt"
    if not final_file.exists():
        final_file.write_text("", encoding="utf-8")

    return created_dirs


def get_header_value(header: fits.Header, key: str, default: str = "N/A") -> str:
    """Read and sanitize a FITS header value with fallback handling."""
    value = header.get(key, default)
    if value in (None, ""):
        return default
    if key == "CAMERAID":
        value = clean_camera_name(value)
    return clean_string(value)


def count_unknown_fields(header: fits.Header) -> int:
    """Count missing critical fields to avoid bad grouping and naming."""
    unknown_count = 0
    for field in CRITICAL_FIELDS:
        if get_header_value(header, field, "N/A") in {"UNKNOWN", "N/A"}:
            unknown_count += 1
    return unknown_count


def get_date_part(header: fits.Header) -> str:
    """Extract YYYY-MM-DD from DATE-LOC when available."""
    raw = get_header_value(header, "DATE-LOC")
    return raw.split("T", 1)[0]


def get_year_part(header: fits.Header) -> str:
    """Extract the four-digit year from DATE-LOC when available."""
    return get_date_part(header).split("-", 1)[0]


def derive_suffix_from_filename(file_path: Path) -> str:
    """Preserve sequence numbers from source names where possible."""
    match = re.search(r"(\d+)$", file_path.stem)
    if match:
        return f"_{match.group(1)}"
    return ""


def get_capture_stamp(header: fits.Header) -> str:
    """Build a sortable YYYYMMDD-HHMMSS prefix from DATE-LOC."""
    raw = str(header.get("DATE-LOC", ""))
    if not raw:
        return datetime.now().strftime("%Y%m%d-%H%M%S")

    normalized = raw.replace("Z", "").strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(normalized, fmt)
            return dt.strftime("%Y%m%d-%H%M%S")
        except ValueError:
            continue

    return clean_dashes(normalized.replace(":", "").replace("T", "-"))


def create_target_directory(source_dir: Path, header: fits.Header) -> Path:
    """Build one target folder per year, object, telescope, and camera."""
    year = get_year_part(header)
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    camera_id = get_header_value(header, "CAMERAID")

    dir_name = f"{year}_{object_name}_{telescope}_{camera_id}"
    return source_dir / clean_dashes(dir_name)


def build_target_directory_key(header: fits.Header) -> str:
    """Group files that belong to the same year/object/telescope/camera folder."""
    return (
        f"{get_year_part(header)}_"
        f"{get_header_value(header, 'OBJECT', 'UNKNOWN')}_"
        f"{get_header_value(header, 'TELESCOP')}_"
        f"{get_header_value(header, 'CAMERAID')}"
    )


def build_target_filename(source_path: Path, header: fits.Header, imagetype: str) -> str:
    """Build destination filename in a deterministic and readable format."""
    capture_stamp = get_capture_stamp(header)
    date_loc = get_date_part(header)
    exposure = get_header_value(header, "EXPOSURE")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    filter_name = get_header_value(header, "FILTER", "NOFILTER")
    camera_id = get_header_value(header, "CAMERAID")
    number_part = derive_suffix_from_filename(source_path)

    new_filename = (
        f"{capture_stamp}_{imagetype}_{date_loc}_{object_name}_{camera_id}_"
        f"e{exposure}_g{gain}_{filter_name}_t{ccd_temp}{number_part}.fits"
    )
    return clean_dashes(new_filename)


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


def iter_source_fits_files(source_dir: Path) -> Iterable[Path]:
    """Only process capture folders to prevent reprocessing already moved files."""
    for root, _dirs, files in os.walk(source_dir):
        root_path = Path(root)
        if root_path.name.upper() not in SUPPORTED_CAPTURE_DIRS:
            continue
        for file_name in files:
            if file_name.lower().endswith(".fits"):
                yield root_path / file_name


def process_fits_file(source_path: Path, target_dir: Path, header: fits.Header, imagetype: str, dry_run: bool) -> bool:
    """Move one FITS file to target directory using normalized naming."""
    unknown_count = count_unknown_fields(header)
    if unknown_count > 2:
        logging.warning("SKIP: Zu viele unbekannte Felder (%s) -> %s", unknown_count, source_path)
        print(f"SKIP: {source_path.name} (zu viele unbekannte Felder: {unknown_count})")
        return False

    target_subdir = TARGET_SUBDIR_MAP.get(imagetype, imagetype)
    target_dir = target_dir / target_subdir
    target_dir.mkdir(parents=True, exist_ok=True)
    target_name = build_target_filename(source_path, header, imagetype)
    target_path = ensure_unique_path(target_dir / target_name)

    if source_path.resolve() == target_path.resolve():
        logging.info("SKIP: Quelle und Ziel identisch -> %s", source_path)
        return False

    logging.info("Verschiebe: %s -> %s", source_path, target_path)
    if not dry_run:
        shutil.move(str(source_path), str(target_path))
    return True


def remove_empty_directories(source_dir: Path, dry_run: bool) -> int:
    """Remove every empty directory below source_dir, keeping source_dir itself."""
    planned_removals: set[Path] = set()
    removed_count = 0

    for root, dirs, _files in os.walk(source_dir, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            children = list(dir_path.iterdir())
            is_empty = not children or all(child in planned_removals for child in children)
            if not is_empty:
                continue

            planned_removals.add(dir_path)
            removed_count += 1
            logging.info("Entferne leeren Ordner: %s", dir_path)
            if not dry_run:
                dir_path.rmdir()

    return removed_count


def process_directory(source_dir: Path, dry_run: bool) -> ProcessingSummary:
    """Process all FITS files from N.I.N.A. capture subfolders."""
    target_dir_map: Dict[str, Path] = {}
    summary = ProcessingSummary()

    for source_path in iter_source_fits_files(source_dir):
        try:
            with fits.open(source_path) as hdul:
                header = hdul[0].header

            imagetype = get_header_value(header, "IMAGETYP", "UNKNOWN").upper()
            target_dir_key = build_target_directory_key(header)

            if target_dir_key not in target_dir_map:
                target_dir = create_target_directory(source_dir, header)
                target_dir_map[target_dir_key] = target_dir
                summary.target_dirs.add(target_dir)
                ensure_project_structure(target_dir)
                logging.info("Neuer Zielordner: %s", target_dir)
            else:
                target_dir = target_dir_map[target_dir_key]

            was_moved = process_fits_file(source_path, target_dir, header, imagetype, dry_run)
            if was_moved:
                summary.moved += 1
                target_subdir = TARGET_SUBDIR_MAP.get(imagetype, imagetype)
                summary.files_by_type[target_subdir] = summary.files_by_type.get(target_subdir, 0) + 1
                status = "DRY-RUN" if dry_run else "OK"
                print(f"[{status:7}] {source_path.name} -> {target_dir / target_subdir}")
            else:
                summary.skipped += 1

        except Exception as exc:  # Defensive broad catch for batch processing.
            summary.errors += 1
            logging.error("Fehler bei %s: %s", source_path, exc)

    summary.empty_dirs = remove_empty_directories(source_dir, dry_run)

    return summary


def print_summary(source_dir: Path, log_path: Path, summary: ProcessingSummary, dry_run: bool) -> None:
    """Print a compact, human-readable processing summary."""
    total_files = summary.moved + summary.skipped + summary.errors
    action_label = "Vorgesehen" if dry_run else "Verarbeitet"

    print("\n" + "=" * 64)
    print("N.I.N.A. FITS ORGANIZER - ZUSAMMENFASSUNG")
    print("=" * 64)
    print(f"Quelle        : {source_dir}")
    print(f"Modus         : {'DRY-RUN (keine Änderungen)' if dry_run else 'ECHTLAUF'}")
    print(f"Dateien       : {total_files}")
    print(f"{action_label:14}: {summary.moved}")
    print(f"Übersprungen   : {summary.skipped}")
    print(f"Fehler         : {summary.errors}")
    print(f"Zielordner     : {len(summary.target_dirs)}")
    empty_label = "Zu entfernen" if dry_run else "Entfernt"
    print(f"{empty_label:14}: {summary.empty_dirs} leere Ordner")

    if summary.files_by_type:
        print("\nDateien nach Typ:")
        for image_type, count in sorted(summary.files_by_type.items()):
            print(f"  {image_type:12}: {count}")

    print(f"\nLogdatei       : {log_path}")
    print("=" * 64)


def build_parser() -> argparse.ArgumentParser:
    """Create CLI parser."""
    parser = argparse.ArgumentParser(
        description="Organisiert N.I.N.A.-FITS-Dateien anhand ihrer Header-Metadaten."
    )
    parser.add_argument("source", help="Pfad zum N.I.N.A.-Basisordner")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, welche Dateien verschoben würden.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    source_dir = Path(args.source).expanduser().resolve()
    if not source_dir.exists() or not source_dir.is_dir():
        print(f"FEHLER: Ordner existiert nicht: {source_dir}")
        return 1

    print("=" * 64)
    print("N.I.N.A. FITS ORGANIZER")
    print("=" * 64)
    print(f"Quelle: {source_dir}")
    if args.dry_run:
        print("Modus: DRY-RUN - es werden keine Dateien verschoben")
    print()
    log_path = setup_logging(source_dir)
    summary = process_directory(source_dir, dry_run=args.dry_run)
    logging.info(
        "Verarbeitung abgeschlossen. moved=%s skipped=%s errors=%s",
        summary.moved,
        summary.skipped,
        summary.errors,
    )
    print_summary(source_dir, log_path, summary, dry_run=args.dry_run)

    return 1 if summary.errors else 0


if __name__ == "__main__":
    sys.exit(main())