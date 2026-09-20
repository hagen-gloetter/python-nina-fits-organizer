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
import hashlib
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
# All folder names that can occur directly below a target project directory; used to recognize
# already-organized files on re-runs so they are not mistakenly moved back up a level.
KNOWN_TARGET_SUBDIRS = SUPPORTED_CAPTURE_DIRS | set(TARGET_SUBDIR_MAP.values()) | {"UNKNOWN", "LIGHT_JPG"}
CRITICAL_FIELDS = ("OBJECT", "TELESCOP", "DATE-LOC", "FOCALLEN", "EXPOSURE", "CAMERAID")
IGNORED_SCAN_FOLDERS = {
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

# Canonical catalog designation patterns, matched against the OBJECT header value with all
# whitespace/dashes/underscores stripped and upper-cased (e.g. "M 31" / "m-31" / "Messier 31"
# all become "M31"). Order/prefix pairs: (folder prefix, compiled pattern).
CATALOG_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("M", re.compile(r"^M(?:ESSIER)?0*(\d{1,3})([A-Z]?)$")),
    ("NGC", re.compile(r"^NGC0*(\d{1,4})([A-Z]?)$")),
    ("IC", re.compile(r"^IC0*(\d{1,4})([A-Z]?)$")),
)

# Optional, hand-curated common names appended to well-known catalog designations
# (e.g. "M31" -> "M31-Andromedagalaxie"). Extend freely; unmatched IDs stay bare.
COMMON_NAMES: Dict[str, str] = {
    "M1": "Krebsnebel",
    "M8": "Lagunennebel",
    "M13": "Herkuleshaufen",
    "M16": "Adlernebel",
    "M17": "Schwan-Nebel",
    "M20": "Trifidnebel",
    "M27": "Hantelnebel",
    "M31": "Andromedagalaxie",
    "M33": "Dreiecksgalaxie",
    "M42": "Orionnebel",
    "M45": "Plejaden",
    "M51": "Whirlpoolgalaxie",
    "M57": "Ringnebel",
    "M81": "Bodes-Galaxie",
    "M101": "Feuerradgalaxie",
    "M104": "Sombrerogalaxie",
    "NGC7000": "Nordamerikanebel",
    "NGC6992": "Cirrusnebel-Ost",
    "NGC6960": "Cirrusnebel-West",
    "NGC2237": "Rosettennebel",
    "NGC7635": "Bubble-Nebel",
    "NGC281": "Pacman-Nebel",
    "NGC1499": "Kalifornienebel",
    "IC434": "Pferdekopfnebel",
    "IC1396": "Elefantenruesselnebel",
    "IC5070": "Pelikannebel",
}


class ProcessingSummary:
    """Collect processing counts for the final console summary."""

    def __init__(self) -> None:
        self.moved = 0
        self.skipped = 0
        self.errors = 0
        self.empty_dirs = 0
        self.duplicates_overwritten = 0
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
    camera_text = camera_text.replace("_", "-")
    camera_text = clean_string(camera_text)
    return clean_dashes(camera_text.strip(" _-"))


def normalize_object_name(raw_object: object) -> str:
    """Canonicalize Messier/NGC/IC designations so naming variants ('M 31', 'm31', 'M-31',
    'Messier 31') collapse to one target folder, optionally appending a common name."""
    text = str(raw_object).strip()
    if not text:
        return "UNKNOWN"

    compact = re.sub(r"[\s\-_]", "", text).upper()
    for prefix, pattern in CATALOG_PATTERNS:
        match = pattern.match(compact)
        if not match:
            continue
        catalog_id = f"{prefix}{int(match.group(1))}{match.group(2)}"
        common_name = COMMON_NAMES.get(catalog_id)
        canonical = f"{catalog_id}-{common_name}" if common_name else catalog_id
        return clean_string(canonical)

    return clean_string(text)


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


def normalize_see_star_layout(source_dir: Path) -> None:
    """Normalize nested SeeStar folder names case-insensitively using a single bottom-up pass."""
    for root, dirs, _files in os.walk(source_dir, topdown=False):
        root_path = Path(root)
        try:
            relative_parts = root_path.relative_to(source_dir).parts
        except ValueError:
            relative_parts = ()
        if any(part.upper() in IGNORED_SCAN_FOLDERS or part.startswith(".") for part in relative_parts):
            continue
        for dir_name in list(dirs):
            lower = dir_name.lower()
            current_path = root_path / dir_name
            if lower == "lights":
                target = current_path.with_name("LIGHT")
                if not target.exists():
                    current_path.rename(target)
            elif lower == "lights_jpg":
                target = current_path.with_name("LIGHT_jpg")
                if not target.exists():
                    current_path.rename(target)
            elif lower == "seestar_stacked":
                # Already nested inside a PRO folder from an earlier run: leave it in place.
                if root_path.name == "PRO":
                    continue
                pro_dir = current_path.parent / "PRO"
                pro_dir.mkdir(exist_ok=True)
                merge_directory_contents(current_path, pro_dir / "seestar_stacked")


def merge_directory_contents(source_dir: Path, target_dir: Path) -> None:
    """Move all children of source_dir into target_dir, merging nested folders and de-duplicating name collisions."""
    target_dir.mkdir(parents=True, exist_ok=True)
    for child in list(source_dir.iterdir()):
        destination = target_dir / child.name
        if child.is_dir() and destination.is_dir():
            merge_directory_contents(child, destination)
            try:
                child.rmdir()
            except OSError:
                pass
            continue
        if destination.exists():
            if child.is_file() and destination.is_file():
                if child.name in {"Processing_Daten_hier.txt", "Fertige_Bilder_hier.txt"}:
                    child.unlink()
                    continue
                if child.stat().st_size == 0 and destination.stat().st_size == 0:
                    child.unlink()
                    continue
            destination = ensure_unique_path(destination)
        shutil.move(str(child), str(destination))
    try:
        source_dir.rmdir()
    except OSError:
        pass


def move_preview_folder_to_target(source_dir: Path, target_dir: Path) -> None:
    """Merge a sibling LIGHT_jpg directory into the target project's LIGHT_jpg folder."""
    source_preview = source_dir / "LIGHT_jpg"
    if source_preview.is_dir():
        merge_directory_contents(source_preview, target_dir / "LIGHT_jpg")


def move_stacked_folder_to_target(source_dir: Path, target_dir: Path) -> None:
    """Merge a leftover PRO/seestar_stacked directory into the target project's PRO/seestar_stacked folder."""
    source_stacked = source_dir / "PRO" / "seestar_stacked"
    if source_stacked.is_dir():
        merge_directory_contents(source_stacked, target_dir / "PRO" / "seestar_stacked")


def migrate_source_project_dir(source_project_dir: Path, target_dir: Path, dry_run: bool) -> None:
    """Migrate all companion folders and non-capture files from source_project_dir to target_dir."""
    if source_project_dir.resolve() == target_dir.resolve():
        return

    preview_dir = source_project_dir / "LIGHT_jpg"
    if preview_dir.is_dir():
        if not dry_run:
            merge_directory_contents(preview_dir, target_dir / "LIGHT_jpg")
        logging.info("Migriere Vorschauordner: %s -> %s", preview_dir, target_dir / "LIGHT_jpg")

    pro_dir = source_project_dir / "PRO"
    if pro_dir.is_dir():
        if not dry_run:
            merge_directory_contents(pro_dir, target_dir / "PRO")
        logging.info("Migriere PRO-Ordner: %s -> %s", pro_dir, target_dir / "PRO")

    final_dir = source_project_dir / "FINAL"
    if final_dir.is_dir():
        if not dry_run:
            merge_directory_contents(final_dir, target_dir / "FINAL")
        logging.info("Migriere FINAL-Ordner: %s -> %s", final_dir, target_dir / "FINAL")

    if not dry_run and source_project_dir.exists():
        for child in list(source_project_dir.iterdir()):
            if child.name.upper() in (KNOWN_TARGET_SUBDIRS | {"PRO", "FINAL"}):
                continue
            destination = target_dir / child.name
            if child.is_dir():
                if destination.is_dir():
                    merge_directory_contents(child, destination)
                else:
                    shutil.move(str(child), str(destination))
            elif child.is_file():
                if destination.exists():
                    if child.name in {"Processing_Daten_hier.txt", "Fertige_Bilder_hier.txt"}:
                        child.unlink()
                        continue
                    if child.stat().st_size == 0 and destination.stat().st_size == 0:
                        child.unlink()
                        continue
                    destination = ensure_unique_path(destination)
                shutil.move(str(child), str(destination))


def repair_nested_pro_folders(source_dir: Path) -> None:
    """Flatten PRO/PRO folders left behind by earlier runs that mishandled already-organized seestar_stacked dirs."""
    for nested_pro in sorted(source_dir.rglob("PRO/PRO"), key=lambda path: len(path.parts), reverse=True):
        if nested_pro.is_dir():
            merge_directory_contents(nested_pro, nested_pro.parent)


def normalize_existing_target_dir_names(source_dir: Path) -> None:
    """Rename (or merge) top-level target dirs whose OBJECT segment uses an older naming
    convention (e.g. 'M-27') into the current canonical form (e.g. 'M27-Hantelnebel')."""
    for entry in list(source_dir.iterdir()):
        if not entry.is_dir() or not re.match(r"^\d{4}_", entry.name):
            continue
        tokens = entry.name.split("_")
        if len(tokens) < 3:
            continue
        new_object = normalize_object_name(tokens[1])
        if new_object == tokens[1]:
            continue
        new_name = "_".join([tokens[0], new_object, *tokens[2:]])
        new_path = entry.parent / new_name
        logging.info("Ordnername an aktuelles Objekt-Schema angepasst: %s -> %s", entry.name, new_name)
        if new_path.exists():
            merge_directory_contents(entry, new_path)
        else:
            entry.rename(new_path)


def parse_date_from_file_name(file_path: Path) -> str | None:
    """Extract a YYYY-MM-DD or YYYYMMDD-HHMMSS value from a SeeStar-like filename."""
    match = re.search(r"(\d{8})[-_](\d{6})", file_path.stem)
    if match:
        date_part = match.group(1)
        try:
            dt = datetime.strptime(date_part, "%Y%m%d")
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            return None
    match = re.search(r"(\d{4})-(\d{2})-(\d{2})", file_path.stem)
    if match:
        return f"{match.group(1)}-{match.group(2)}-{match.group(3)}"
    return None


def get_header_value(header: fits.Header, key: str, default: str = "N/A") -> str:
    """Read and sanitize a FITS header value with fallback handling."""
    value = header.get(key)
    if value in (None, ""):
        if key == "CAMERAID":
            value = header.get("INSTRUME") or header.get("TELESCOP", default)
        else:
            value = default
    if key == "OBJECT" and str(value).upper() not in {"N/A", "N-A", "UNKNOWN"}:
        return normalize_object_name(value)
    if key == "TELESCOP":
        # Some devices embed a serial/id suffix after an underscore (e.g. "S30 Pro_5915f86f");
        # keep only the base name so it doesn't duplicate the CAMERAID fallback.
        telescope_name = str(value).strip()
        if telescope_name and "_" in telescope_name:
            value = telescope_name.split("_", 1)[0]
    if key == "CAMERAID":
        if str(value).upper() in {"N/A", "UNKNOWN"}:
            value = header.get("INSTRUME") or header.get("TELESCOP", default)
        telescope_name = str(header.get("TELESCOP", "")).strip()
        if telescope_name and "_" in telescope_name and value == telescope_name:
            base_name = telescope_name.split("_", 1)[0]
            value = base_name
        value = clean_camera_name(value)
    return clean_string(value)


def normalize_image_type(raw_type: str, source_path: Path) -> str:
    """Normalize FITS IMAGETYP or derive it from folder/filename (LIGHT, DARK, FLAT, BIAS, SNAPSHOT)."""
    val = clean_string(raw_type).upper()
    if "LIGHT" in val:
        return "LIGHT"
    if "DARK" in val:
        return "DARK"
    if "FLAT" in val:
        return "FLAT"
    if "BIAS" in val or "OFFSET" in val:
        return "BIAS"
    if "SNAP" in val:
        return "SNAPSHOT"

    # Try parent directory hierarchy
    for parent in (source_path.parent.name.upper(), source_path.parent.parent.name.upper() if len(source_path.parts) > 2 else ""):
        if "LIGHT" in parent:
            return "LIGHT"
        if "DARK" in parent:
            return "DARK"
        if "FLAT" in parent:
            return "FLAT"
        if "BIAS" in parent or "OFFSET" in parent:
            return "BIAS"
        if "SNAP" in parent or "PROCESS" in parent:
            return "SNAPSHOT"

    # Try filename stem
    stem = source_path.stem.upper()
    if "DARK" in stem:
        return "DARK"
    if "FLAT" in stem:
        return "FLAT"
    if "BIAS" in stem or "OFFSET" in stem:
        return "BIAS"
    if "SNAP" in stem:
        return "SNAPSHOT"

    # Never guess LIGHT for an unrecognized type: that could silently mix calibration
    # frames into light stacks. Route it to a visible UNKNOWN folder instead.
    return "UNKNOWN"


def count_unknown_fields(header: fits.Header, imagetype: str = "LIGHT") -> int:
    """Count missing critical fields to avoid bad grouping and naming."""
    critical = CRITICAL_FIELDS
    if imagetype in {"DARK", "BIAS"}:
        critical = ("TELESCOP", "CAMERAID")
    elif imagetype == "FLAT":
        critical = ("TELESCOP", "CAMERAID", "FILTER")
    unknown_count = 0
    for field in critical:
        if get_header_value(header, field, "N/A") in {"UNKNOWN", "N/A"}:
            unknown_count += 1
    return unknown_count


def get_date_part(header: fits.Header, source_path: Path | None = None) -> str:
    """Extract YYYY-MM-DD from DATE-LOC or a SeeStar-style filename fallback."""
    raw = get_header_value(header, "DATE-LOC", "N/A")
    if raw.upper() not in {"N/A", "N-A", "UNKNOWN"}:
        return raw.split("T", 1)[0]

    if source_path is not None:
        parsed = parse_date_from_file_name(source_path)
        if parsed:
            return parsed

    return datetime.now().strftime("%Y-%m-%d")


def get_year_part(header: fits.Header, source_path: Path | None = None) -> str:
    """Extract the four-digit year from DATE-LOC when available."""
    return get_date_part(header, source_path).split("-", 1)[0]


def derive_suffix_from_filename(file_path: Path) -> str:
    """Preserve sequence numbers from source names where possible, but ignore timestamp suffixes and temperature decimals."""
    stem = file_path.stem

    # If the file is already formatted with organizer naming (..._t<temp>(_<seq>)?),
    # ensure temperature decimals/integers are not mistaken for sequence numbers.
    organized_match = re.search(r"_t[-+]?[0-9.]+(?:_(\d+))?$", stem)
    if organized_match:
        return f"_{organized_match.group(1)}" if organized_match.group(1) else ""

    # Timestamp with sequence suffix: YYYYMMDD-HHMMSS_1
    ts_seq_match = re.search(r"(\d{8})[-_](\d{6})[_-](\d+)$", stem)
    if ts_seq_match:
        return f"_{ts_seq_match.group(3)}"

    # Pure timestamp at end: YYYYMMDD-HHMMSS or YYYYMMDD_HHMMSS
    if re.search(r"(\d{8})[-_](\d{6})$", stem):
        return ""

    # Sequence number preceded by separator (_, -, frame, #)
    match = re.search(r"(?:[_-]|frame|#)(\d+)$", stem, re.IGNORECASE)
    if match:
        return f"_{match.group(1)}"
    return ""


def get_capture_stamp(header: fits.Header, source_path: Path | None = None) -> str:
    """Build a sortable YYYYMMDD-HHMMSS prefix from DATE-LOC or a filename timestamp fallback."""
    raw = str(header.get("DATE-LOC", "")).strip()
    if raw:
        normalized = raw.replace("Z", "").strip()
        for fmt in ("%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(normalized, fmt)
                return dt.strftime("%Y%m%d-%H%M%S")
            except ValueError:
                continue
    
    if source_path is not None:
        match = re.search(r"(\d{8})[-_](\d{6})", source_path.stem)
        if match:
            date_part, time_part = match.groups()
            try:
                dt = datetime.strptime(f"{date_part}{time_part}", "%Y%m%d%H%M%S")
                return dt.strftime("%Y%m%d-%H%M%S")
            except ValueError:
                pass

    return datetime.now().strftime("%Y%m%d-%H%M%S")


def create_target_directory(source_dir: Path, header: fits.Header, source_path: Path | None = None) -> Path:
    """Build one target folder per year, object, telescope, and camera."""
    year = get_year_part(header, source_path)
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    camera_id = get_header_value(header, "CAMERAID")

    parts = [year, object_name, telescope]
    # Skip camera_id when it is just the CAMERAID-fallback repeating the telescope name (e.g. SeeStar).
    if camera_id != telescope:
        parts.append(camera_id)
    return source_dir / clean_dashes("_".join(parts))


def build_target_directory_key(header: fits.Header, source_path: Path | None = None) -> str:
    """Group files that belong to the same year/object/telescope/camera folder."""
    year = get_year_part(header, source_path)
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    camera_id = get_header_value(header, "CAMERAID")

    parts = [year, object_name, telescope]
    if camera_id != telescope:
        parts.append(camera_id)
    return "_".join(parts)


def build_target_filename(source_path: Path, header: fits.Header, imagetype: str) -> str:
    """Build destination filename in a deterministic and readable format."""
    capture_stamp = get_capture_stamp(header, source_path)
    date_loc = get_date_part(header, source_path)
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


def _compute_file_hash(path: Path, chunk_size: int = 1024 * 1024) -> str:
    """Compute a SHA-256 hash of a file's contents."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def files_have_identical_content(path_a: Path, path_b: Path) -> bool:
    """Compare two files by size first, then by SHA-256 hash, to detect true byte-for-byte duplicates."""
    try:
        if path_a.stat().st_size != path_b.stat().st_size:
            return False
        return _compute_file_hash(path_a) == _compute_file_hash(path_b)
    except OSError:
        return False


def iter_source_fits_files(source_dir: Path) -> Iterable[Path]:
    """Discover all FITS files in source_dir, excluding processing/final outputs and virtual environments."""
    for root, dirs, files in os.walk(source_dir):
        dirs[:] = [d for d in dirs if d.upper() not in IGNORED_SCAN_FOLDERS and not d.startswith(".")]
        root_path = Path(root)
        for file_name in files:
            lower_name = file_name.lower()
            if lower_name.endswith(".fits") or lower_name.endswith(".fit"):
                yield root_path / file_name


def process_fits_file(
    source_path: Path,
    target_dir: Path,
    header: fits.Header,
    imagetype: str,
    dry_run: bool,
    summary: ProcessingSummary | None = None,
) -> bool:
    """Move one FITS file to target directory using normalized naming and frame-type subfolder."""
    unknown_count = count_unknown_fields(header, imagetype)
    if unknown_count > 2:
        logging.warning("SKIP: Zu viele unbekannte Felder (%s) -> %s", unknown_count, source_path)
        print(f"SKIP: {source_path.name} (zu viele unbekannte Felder: {unknown_count})")
        return False

    target_subdir = TARGET_SUBDIR_MAP.get(imagetype, imagetype)
    target_subdir_path = target_dir / target_subdir
    if not dry_run:
        target_subdir_path.mkdir(parents=True, exist_ok=True)
    target_name = build_target_filename(source_path, header, imagetype)
    target_path = target_subdir_path / target_name

    # If source is already at the target location with the expected name, skip it
    if source_path.resolve() == target_path.resolve():
        logging.info("SKIP: Quelle und Ziel identisch -> %s", source_path)
        return False

    if target_path.exists():
        # A byte-for-byte duplicate (e.g. the same raw file re-copied into the source folder)
        # replaces the existing target instead of piling up as a numbered copy in the stack.
        if files_have_identical_content(source_path, target_path):
            logging.info("Duplikat mit identischem Inhalt erkannt, ueberschreibe: %s -> %s", source_path, target_path)
            print(f"[DUPLIKAT] {source_path.name} == {target_path.name} (identischer Inhalt, wird ueberschrieben)")
            if summary is not None:
                summary.duplicates_overwritten += 1
            if not dry_run:
                os.replace(str(source_path), str(target_path))
            return True

        # Otherwise it's a genuinely different file that happens to compute the same name.
        target_path = ensure_unique_path(target_path)
        if source_path.resolve() == target_path.resolve():
            logging.info("SKIP: Quelle und Ziel identisch -> %s", source_path)
            return False

    logging.info("Verschiebe: %s -> %s", source_path, target_path)
    if not dry_run:
        shutil.move(str(source_path), str(target_path))
    return True


def remove_empty_directories(source_dir: Path, dry_run: bool) -> int:
    """Remove every empty directory below source_dir, keeping source_dir itself and skipping ignored trees."""
    # Collect candidate dirs via a pruning topdown walk (skips ignored/hidden trees entirely),
    # then evaluate deepest-first so parents can become empty in turn.
    candidate_dirs: list[Path] = []
    for root, dirs, _files in os.walk(source_dir, topdown=True):
        dirs[:] = [d for d in dirs if d.upper() not in IGNORED_SCAN_FOLDERS and not d.startswith(".")]
        root_path = Path(root)
        candidate_dirs.extend(root_path / dir_name for dir_name in dirs)
    candidate_dirs.sort(key=lambda p: len(p.parts), reverse=True)

    planned_removals: set[Path] = set()
    removed_count = 0

    for dir_path in candidate_dirs:
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


def parse_object_name_from_preview(preview_dir: Path) -> str | None:
    """Extract the OBJECT name from a SeeStar preview JPG filename like 'Light_M 31_20.0s_IRCUT_...'."""
    for jpg_file in sorted(preview_dir.glob("*.jpg")):
        match = re.match(r"Light_(.+?)_\d+(?:\.\d+)?s_", jpg_file.stem, re.IGNORECASE)
        if match:
            return match.group(1).strip()
    return None


def parse_year_from_project_dir(project_dir: Path) -> str | None:
    """Extract a four-digit year from a session folder name or its preview filenames."""
    match = re.search(r"(\d{4})-\d{2}-\d{2}", project_dir.name)
    if match:
        return match.group(1)

    preview_dir = project_dir / "LIGHT_jpg"
    if preview_dir.is_dir():
        for jpg_file in preview_dir.glob("*.jpg"):
            match = re.search(r"(\d{4})\d{2}\d{2}[-_]\d{6}", jpg_file.stem)
            if match:
                return match.group(1)
    return None


def find_target_dir_for_leftover_project(project_dir: Path, existing_target_dirs: Iterable[Path]) -> Path | None:
    """Match a leftover project folder (whose FITS were already moved in an earlier run) to its target directory."""
    preview_dir = project_dir / "LIGHT_jpg"
    object_name = parse_object_name_from_preview(preview_dir) if preview_dir.is_dir() else None
    year = parse_year_from_project_dir(project_dir)

    if object_name and year:
        prefix = f"{year}_{normalize_object_name(object_name)}_"
        matches = [target_dir for target_dir in existing_target_dirs if target_dir.name.startswith(prefix)]
        if len(matches) == 1:
            return matches[0]

    dir_clean = clean_string(project_dir.name)
    # Require a whole underscore-delimited segment match (not a raw substring) to avoid
    # accidentally merging a leftover folder into an unrelated, only superficially similar target.
    if len(dir_clean) < 3:
        return None
    boundary_pattern = re.compile(rf"(^|_){re.escape(dir_clean)}(_|$)", re.IGNORECASE)
    matches = [target_dir for target_dir in existing_target_dirs if boundary_pattern.search(target_dir.name)]
    return matches[0] if len(matches) == 1 else None


def iter_leftover_project_dirs(source_dir: Path) -> Iterable[Path]:
    """Find project folders with orphaned preview, PRO, FINAL, or other data left behind from earlier runs."""
    for entry in source_dir.iterdir():
        if not entry.is_dir() or entry.name.upper() in IGNORED_SCAN_FOLDERS:
            continue
        if re.match(r"^\d{4}_", entry.name):
            continue
        if (entry / "LIGHT_jpg").is_dir() or (entry / "PRO").is_dir() or (entry / "FINAL").is_dir():
            yield entry


def process_directory(source_dir: Path, dry_run: bool) -> ProcessingSummary:
    """Process all FITS files from N.I.N.A. capture subfolders and restructure folders."""
    repair_nested_pro_folders(source_dir)
    normalize_see_star_layout(source_dir)
    if not dry_run:
        normalize_existing_target_dir_names(source_dir)

    target_dir_map: Dict[str, Path] = {}
    project_to_targets: Dict[Path, set[Path]] = {}
    summary = ProcessingSummary()

    for source_path in iter_source_fits_files(source_dir):
        try:
            header = fits.getheader(source_path, 0)

            raw_imagetype = get_header_value(header, "IMAGETYP", "")
            imagetype = normalize_image_type(raw_imagetype, source_path)

            target_dir_key = build_target_directory_key(header, source_path)

            if target_dir_key not in target_dir_map:
                target_dir = create_target_directory(source_dir, header, source_path)
                target_dir_map[target_dir_key] = target_dir
                summary.target_dirs.add(target_dir)
                if not dry_run:
                    ensure_project_structure(target_dir)
                logging.info("Neuer Zielordner: %s", target_dir)
            else:
                target_dir = target_dir_map[target_dir_key]

            # Determine the source project/session folder
            if source_path.parent.name.upper() in KNOWN_TARGET_SUBDIRS:
                source_project_dir = source_path.parent.parent
            else:
                source_project_dir = source_path.parent

            if source_project_dir.resolve() != source_dir.resolve() and source_project_dir.resolve() != target_dir.resolve():
                project_to_targets.setdefault(source_project_dir, set()).add(target_dir)

            was_moved = process_fits_file(source_path, target_dir, header, imagetype, dry_run, summary)
            if was_moved:
                summary.moved += 1
                target_subdir = TARGET_SUBDIR_MAP.get(imagetype, imagetype)
                summary.files_by_type[target_subdir] = summary.files_by_type.get(target_subdir, 0) + 1
                status = "DRY-RUN" if dry_run else "OK"
                print(f"[{status:7}] {source_path.name} -> {target_dir / target_subdir}")
            else:
                summary.skipped += 1
                print(f"[SKIP   ] {source_path.name}")

        except Exception as exc:  # Defensive broad catch for batch processing.
            summary.errors += 1
            logging.error("Fehler bei %s: %s", source_path, exc)

    # Migrate companion files & subfolders from source project dirs that mapped to a unique target
    for source_project_dir, targets in project_to_targets.items():
        if len(targets) == 1:
            target_dir = next(iter(targets))
            migrate_source_project_dir(source_project_dir, target_dir, dry_run)
        else:
            for target_dir in targets:
                move_preview_folder_to_target(source_project_dir, target_dir)
                move_stacked_folder_to_target(source_project_dir, target_dir)

    existing_target_dirs = set(summary.target_dirs) | {
        entry for entry in source_dir.iterdir() if entry.is_dir() and re.match(r"^\d{4}_", entry.name)
    }
    for project_dir in iter_leftover_project_dirs(source_dir):
        target_dir = find_target_dir_for_leftover_project(project_dir, existing_target_dirs)
        if target_dir is None:
            logging.warning("Verwaiste Vorschau-/PRO-Daten ohne eindeutiges Ziel: %s", project_dir)
            continue
        status = "DRY-RUN" if dry_run else "MERGE"
        migrate_source_project_dir(project_dir, target_dir, dry_run)
        logging.info("Verwaiste Projektdaten zusammengefuehrt: %s -> %s", project_dir, target_dir)
        print(f"[{status:7}] {project_dir.name} -> {target_dir.name}")

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
    if summary.duplicates_overwritten:
        overwrite_label = "Vorgesehen" if dry_run else "Ueberschrieben"
        print(f"{overwrite_label:14}: {summary.duplicates_overwritten} identische Duplikate")

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