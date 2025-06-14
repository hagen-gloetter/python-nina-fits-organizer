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

Copyright (c) 2024-2025 by ramona & hagen.gloetter@gmail.com
Dieses Skript ist lizenziert unter der MIT-Lizenz.
"""

import os
import sys
import shutil
from datetime import datetime
from astropy.io import fits

# === DRY-RUN-MODUS ===
DRY_RUN = True  # Auf False setzen für echten Modus

# === LOGFILE ===
log_prefix = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
logfile = f"{log_prefix}_fits_organizer.log"

def log(msg):
    print(msg)
    with open(logfile, "a", encoding="utf-8") as f:
        f.write(msg + "\n")

def sanitize(val):
    if val is None or str(val).strip() == "":
        return "UNKNOWN"
    return str(val).replace(" ", "-")

def get_header_value(header, keys, default="UNKNOWN"):
    for key in keys:
        if key in header:
            return sanitize(header[key])
    return default

def extract_date(date_str):
    # Erwartet z.B. '2025-06-13T23:57:30.115'
    if not date_str or "T" not in date_str:
        return "UNKNOWN"
    return date_str.split("T")[0]

def process_fits_file(fits_path):
    with fits.open(fits_path) as hdul:
        hdr = hdul[0].header
        object_ = get_header_value(hdr, ["OBJECT"])
        if object_ == "UNKNOWN":
            object_ = "UNKNOWN"
        telescop = get_header_value(hdr, ["TELESCOP"])
        date_loc = extract_date(get_header_value(hdr, ["DATE-LOC"]))
        focallen = get_header_value(hdr, ["FOCALLEN"])
        exposure = get_header_value(hdr, ["EXPOSURE", "EXPTIME"])
        gain = get_header_value(hdr, ["GAIN"])
        ccd_temp = get_header_value(hdr, ["CCD-TEMP"])
        cameraid = get_header_value(hdr, ["CAMERAID", "INSTRUME"])
        imagetyp = get_header_value(hdr, ["IMAGETYP"])
    return {
        "OBJECT": object_,
        "TELESCOP": telescop,
        "DATE-LOC": date_loc,
        "FOCALLEN": focallen,
        "EXPOSURE": exposure,
        "GAIN": gain,
        "CCD-TEMP": ccd_temp,
        "CAMERAID": cameraid,
        "IMAGETYP": imagetyp
    }

def build_folder_name(meta):
    return f"{meta['OBJECT']}_{meta['TELESCOP']}_{meta['DATE-LOC']}_{meta['FOCALLEN']}_e{meta['EXPOSURE']}_g{meta['GAIN']}_t{meta['CCD-TEMP']}_{meta['CAMERAID']}"

def build_file_name(meta, number, ext):
    return f"{meta['IMAGETYP']}_{meta['DATE-LOC']}_e{meta['EXPOSURE']}_g{meta['GAIN']}_t{meta['CCD-TEMP']}_{meta['OBJECT']}_{number}{ext}"

def find_number_suffix(filename):
    # Findet z.B. _0007 vor .fits
    base = os.path.splitext(filename)[0]
    parts = base.split("_")
    if len(parts) >= 2 and parts[-1].isdigit() and len(parts[-1]) == 4:
        return "_" + parts[-1]
    return ""

def main():
    if len(sys.argv) > 1:
        base_dir = sys.argv[1]
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    log(f"Starte {'DRY-RUN' if DRY_RUN else 'ECHTEN'} Lauf im Ordner: {base_dir}")

    for entry in os.listdir(base_dir):
        entry_path = os.path.join(base_dir, entry)
        if not os.path.isdir(entry_path):
            continue
        # Nur Ordner mit Datum als Namen (z.B. 2025-06-13)
        try:
            datetime.strptime(entry, "%Y-%m-%d")
        except ValueError:
            continue

        # Suche nach einer FITS-Datei in einem der Unterordner für die Metadaten
        fits_meta = None
        for sub in ["LIGHT", "FLAT", "DARK", "BIAS", "SNAPSHOT"]:
            sub_path = os.path.join(entry_path, sub)
            if not os.path.isdir(sub_path):
                continue
            for fname in os.listdir(sub_path):
                if fname.lower().endswith(".fits"):
                    fits_meta = process_fits_file(os.path.join(sub_path, fname))
                    break
            if fits_meta:
                break
        if not fits_meta:
            log(f"Kein FITS in {entry_path} gefunden, überspringe.")
            continue

        new_folder_name = build_folder_name(fits_meta)
        new_folder_path = os.path.join(base_dir, new_folder_name)
        if new_folder_path == entry_path:
            log(f"Ordner {entry} ist bereits korrekt benannt.")
        else:
            log(f"Ordner {entry_path} → {new_folder_path}")
            if not DRY_RUN:
                if not os.path.exists(new_folder_path):
                    os.rename(entry_path, new_folder_path)
                else:
                    log(f"Zielordner {new_folder_path} existiert bereits, überspringe Umbenennung!")
                    continue
            else:
                # Im Dry-Run: keine echte Umbenennung
                pass

        # Jetzt alle FITS-Dateien in den Unterordnern umbenennen
        for sub in ["LIGHT", "FLAT", "DARK", "BIAS", "SNAPSHOT"]:
            sub_path = os.path.join(new_folder_path if not DRY_RUN else entry_path, sub)
            if not os.path.isdir(sub_path):
                continue
            for fname in os.listdir(sub_path):
                if not fname.lower().endswith(".fits"):
                    continue
                fits_path = os.path.join(sub_path, fname)
                meta = process_fits_file(fits_path)
                number = find_number_suffix(fname)
                ext = ".fits"
                new_fname = build_file_name(meta, number[1:] if number else "0000", ext)
                new_fpath = os.path.join(sub_path, new_fname)
                if fits_path == new_fpath:
                    continue
                log(f"  Datei {fits_path} → {new_fpath}")
                if not DRY_RUN:
                    if not os.path.exists(new_fpath):
                        os.rename(fits_path, new_fpath)
                    else:
                        log(f"  Zieldatei {new_fpath} existiert bereits, überspringe Umbenennung!")

if __name__ == "__main__":
    main()
