#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hg-NINA-FITS-Organizer
This Python script organizes and renames FITS files created by the 
astrophotography software N.I.N.A.. 
It reads FITS headers and automatically restructures folders and filenames 
based on imaging parameters and object names.

Ein Skript zum Organisieren von FITS-Dateien, die von NINA (Nighttime Imaging 'N' Astronomy) generiert wurden.
Dieses Skript sortiert FITS-Dateien in Unterordnern basierend auf den Metadaten in den Headern der Dateien.

Copyright (c) 2024-2025 by hagen.gloetter@gmail.com
Dieses Skript ist lizenziert unter der MIT-Lizenz.
"""

import os
import sys
import shutil
from pathlib import Path
from astropy.io import fits
from datetime import datetime

# === Konfiguration ===
NINA_SUBFOLDERS = {"LIGHT", "DARK", "FLAT", "BIAS", "SNAPSHOT"}
log_lines = []
log_file_path = None

# === Logging ===
def log(message):
    timestamp = datetime.now().strftime("[%Y-%m-%d %H:%M:%S]")
    line = f"{timestamp} {message}"
    print(line)
    log_lines.append(line)

def write_log_file():
    global log_file_path
    if not log_file_path:
        script_dir = Path(__file__).parent.resolve()
        log_file_path = script_dir / f"nina_rename_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
    try:
        with open(log_file_path, "w", encoding="utf-8") as f:
            f.write("\n".join(log_lines))
        print(f"\n📄 Log gespeichert: {log_file_path}")
    except Exception as e:
        print(f"❌ Fehler beim Schreiben der Logdatei: {e}")

# === Hilfsfunktionen ===

def safe_header_get(header, key, default="UNKNOWN"):
    value = header.get(key, default)
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return default
        return value.replace(" ", "-")
    return str(value)

def extract_date_only(date_str):
    try:
        dt = datetime.fromisoformat(date_str)
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return "0000-00-00"

def build_folder_name(header):
    object_ = safe_header_get(header, "OBJECT")
    telescope = safe_header_get(header, "TELESCOP")
    date_loc = extract_date_only(safe_header_get(header, "DATE-LOC"))
    focallen = safe_header_get(header, "FOCALLEN")
    exposure = safe_header_get(header, "EXPOSURE")
    gain = safe_header_get(header, "GAIN")
    temp = safe_header_get(header, "CCD-TEMP")
    cameraid = safe_header_get(header, "CAMERAID")

    return f"{object_}_{telescope}_{date_loc}_{focallen}_e{exposure}_g{gain}_t{temp}_{cameraid}"

def build_file_name(header, image_type):
    object_ = safe_header_get(header, "OBJECT")
    date_loc = extract_date_only(safe_header_get(header, "DATE-LOC"))
    exposure = safe_header_get(header, "EXPOSURE")
    gain = safe_header_get(header, "GAIN")
    temp = safe_header_get(header, "CCD-TEMP")

    return f"{image_type}_{date_loc}_e{exposure}_g{gain}_t{temp}_{object_}.fits"

def process_fits_file(fits_path):
    with fits.open(fits_path) as hdul:
        header = hdul[0].header
    return header

def is_fits_file(file: Path):
    return file.suffix.lower() == ".fits"

# === Hauptverarbeitung ===

def main(base_folder: Path):
    for date_folder in base_folder.iterdir():
        if not date_folder.is_dir():
            continue

        for subfolder in NINA_SUBFOLDERS:
            sub_path = date_folder / subfolder
            if not sub_path.is_dir():
                continue

            for fits_file in sub_path.glob("*.fits"):
                try:
                    header = process_fits_file(fits_file)
                except Exception as e:
                    log(f"⚠️ Fehler beim Lesen: {fits_file} – {e}")
                    continue

                object_name = safe_header_get(header, "OBJECT")
                folder_name = build_folder_name(header)
                image_type = subfolder
                new_filename = build_file_name(header, image_type)

                # Zielverzeichnis vorbereiten
                target_main = base_folder / folder_name
                target_sub = target_main / subfolder
                target_sub.mkdir(parents=True, exist_ok=True)

                # Zieldateipfad
                target_path = target_sub / new_filename

                # Falls Dateiname bereits existiert, hänge Zahl an
                counter = 1
                while target_path.exists():
                    stem = target_path.stem
                    target_path = target_sub / f"{stem}_{counter}.fits"
                    counter += 1

                # Verschieben
                shutil.move(str(fits_file), target_path)
                log(f"✅ Verschoben: {fits_file} → {target_path}")

        # Wenn Ursprungsordner leer ist → löschen
        if not any(date_folder.rglob("*")):
            try:
                shutil.rmtree(date_folder)
                log(f"🗑️ Gelöscht: Leerer Ordner {date_folder}")
            except Exception as e:
                log(f"❌ Fehler beim Löschen von {date_folder}: {e}")

# === Einstiegspunkt ===

if __name__ == "__main__":
    try:
        if len(sys.argv) > 1:
            base_path = Path(sys.argv[1])
        else:
            base_path = Path(__file__).parent.resolve()

        if not base_path.exists() or not base_path.is_dir():
            log(f"❌ Ungültiger Pfad: {base_path}")
            sys.exit(1)

        log(f"🚀 Starte Verarbeitung in: {base_path}")
        main(base_path)

    finally:
        write_log_file()
