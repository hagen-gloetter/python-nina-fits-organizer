#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hg-NINA-FITS-Organizer
Organize and rename FITS files produced by N.I.N.A.
This Python script organizes and renames FITS files created by the 
astrophotography software N.I.N.A.. 
It reads FITS headers and automatically restructures folders and filenames 
based on imaging parameters and object names.

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
from typing import Dict, Iterable, Tuple

from astropy.io import fits

SUPPORTED_CAPTURE_DIRS = {"LIGHT", "DARK", "FLAT", "BIAS", "SNAPSHOT"}
TARGET_SUBDIR_MAP = {"SNAPSHOT": "PROCESSING"}
CRITICAL_FIELDS = ("OBJECT", "TELESCOP", "DATE-LOC", "FOCALLEN", "EXPOSURE", "CAMERAID")


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
    """Remove common noisy camera prefixes."""
    camera_text = str(camera_id)
    camera_text = camera_text.replace("ZWOptical_ZWO", "").replace("ZWO", "")
    return clean_dashes(camera_text.strip(" _-"))


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
    """Build one session folder per object and acquisition setup."""
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    date_loc = get_date_part(header)
    focal_length = get_header_value(header, "FOCALLEN")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    camera_id = get_header_value(header, "CAMERAID")

    dir_name = f"{object_name}_{telescope}_{date_loc}_{focal_length}_g{gain}_t{ccd_temp}_{camera_id}"

    return source_dir / clean_dashes(dir_name)


def build_session_key(header: fits.Header) -> Tuple[str, str, str, str, str, str]:
    """Group files by object and stable setup, intentionally ignoring exposure."""
    return (
        get_header_value(header, "OBJECT", "UNKNOWN"),
        get_header_value(header, "TELESCOP"),
        get_date_part(header),
        get_header_value(header, "FOCALLEN"),
        get_header_value(header, "GAIN"),
        get_header_value(header, "CAMERAID"),
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


def process_directory(source_dir: Path, dry_run: bool) -> Tuple[int, int, int]:
    """Process all FITS files from N.I.N.A. capture subfolders."""
    object_date_map: Dict[Tuple[str, str, str, str, str, str], Path] = {}
    moved_count = 0
    skipped_count = 0
    error_count = 0

    for source_path in iter_source_fits_files(source_dir):
        try:
            with fits.open(source_path) as hdul:
                header = hdul[0].header

            imagetype = get_header_value(header, "IMAGETYP", "UNKNOWN").upper()
            object_date_key = build_session_key(header)

            if object_date_key not in object_date_map:
                target_dir = create_target_directory(source_dir, header)
                object_date_map[object_date_key] = target_dir
                logging.info("Neuer Zielordner: %s", target_dir)
            else:
                target_dir = object_date_map[object_date_key]

            was_moved = process_fits_file(source_path, target_dir, header, imagetype, dry_run)
            if was_moved:
                moved_count += 1
            else:
                skipped_count += 1

        except Exception as exc:  # Defensive broad catch for batch processing.
            error_count += 1
            logging.error("Fehler bei %s: %s", source_path, exc)

    for root, dirs, _files in os.walk(source_dir, topdown=False):
        for dir_name in dirs:
            dir_path = Path(root) / dir_name
            if dir_path.name.upper() not in SUPPORTED_CAPTURE_DIRS:
                continue
            if not any(dir_path.iterdir()):
                logging.info("Lösche leeren Ordner: %s", dir_path)
                if not dry_run:
                    dir_path.rmdir()

    return moved_count, skipped_count, error_count


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

    print(f"Starte Verarbeitung von: {source_dir}")
    log_path = setup_logging(source_dir)
    moved, skipped, errors = process_directory(source_dir, dry_run=args.dry_run)
    logging.info("Verarbeitung abgeschlossen. moved=%s skipped=%s errors=%s", moved, skipped, errors)
    print(f"Verarbeitung abgeschlossen. moved={moved} skipped={skipped} errors={errors}")
    print(f"Logdatei: {log_path}")

    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())