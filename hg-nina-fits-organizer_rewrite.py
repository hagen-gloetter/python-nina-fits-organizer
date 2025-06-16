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
import logging
import re

# ==== CONFIG ====
DRY_RUN = True  # Set to False to enable actual renaming/moving
LOG_FILE = "nina_fits_organizer.log"

# Subfolders to process
SUBFOLDERS = ["LIGHT", "DARK", "FLAT", "BIAS", "SNAPSHOT"]

# ==== LOGGING ====
logging.basicConfig(
    filename=LOG_FILE,
    filemode='w',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def sanitize(value):
    if not value or str(value).strip() == "":
        return "UNKNOWN"
    return str(value).strip().replace(" ", "-")

def extract_number_suffix(filename):
    """Extrahiert eine 3- bis 6-stellige Zahl direkt vor .fits"""
    match = re.search(r"(\\d{3,6})(?=\\.fits$)", filename.name, re.IGNORECASE)
    return match.group(1) if match else ""

def get_fits_metadata(fits_path):
    try:
        with fits.open(fits_path) as hdul:
            hdr = hdul[0].header
            return {
                'OBJECT': sanitize(hdr.get('OBJECT', 'UNKNOWN')),
                'TELESCOP': sanitize(hdr.get('TELESCOP', 'UNKNOWN')),
                'DATE-LOC': sanitize(hdr.get('DATE-LOC', 'UNKNOWN'))[:10],
                'FOCALLEN': sanitize(hdr.get('FOCALLEN', 'UNKNOWN')),
                'EXPOSURE': sanitize(hdr.get('EXPOSURE', 'UNKNOWN')),
                'GAIN': sanitize(hdr.get('GAIN', 'UNKNOWN')),
                'CCD-TEMP': sanitize(hdr.get('CCD-TEMP', 'UNKNOWN')),
                'IMAGETYP': sanitize(hdr.get('IMAGETYP', 'UNKNOWN')),
                'CAMERAID': sanitize(hdr.get('CAMERAID', 'UNKNOWN')),
            }
    except Exception as e:
        logging.warning(f"Failed to read FITS header from {fits_path}: {e}")
        return None

def process_fits_file(fits_file, subfolder, base_dir, destination_map):
    metadata = get_fits_metadata(fits_file)
    if not metadata:
        return

    number_suffix = extract_number_suffix(fits_file)

    folder_key = (
        metadata['OBJECT'], metadata['TELESCOP'], metadata['DATE-LOC'],
        metadata['FOCALLEN'], metadata['EXPOSURE'], metadata['GAIN'],
        metadata['CCD-TEMP'], metadata['CAMERAID']
    )

    folder_name = f"{metadata['OBJECT']}_{metadata['TELESCOP']}_{metadata['DATE-LOC']}_"
    folder_name += f"{metadata['FOCALLEN']}_e{metadata['EXPOSURE']}_g{metadata['GAIN']}_"
    folder_name += f"t{metadata['CCD-TEMP']}_{metadata['CAMERAID']}"

    if folder_key not in destination_map:
        dest_folder = base_dir / folder_name
        for sub in SUBFOLDERS:
            (dest_folder / sub).mkdir(parents=True, exist_ok=True)
        destination_map[folder_key] = dest_folder
    else:
        dest_folder = destination_map[folder_key]

    new_name = (
        f"{metadata['IMAGETYP']}_{metadata['DATE-LOC']}_e{metadata['EXPOSURE']}"
        f"_g{metadata['GAIN']}_t{metadata['CCD-TEMP']}_{metadata['OBJECT']}"
    )
    if number_suffix:
        new_name += f"_{number_suffix}"
    new_name += ".fits"

    new_path = dest_folder / subfolder / new_name

    logging.info(f"{'[DRY-RUN]' if DRY_RUN else '[MOVE]'} {fits_file} -> {new_path}")                 
    if not DRY_RUN:
        shutil.move(str(fits_file), str(new_path))



def cleanup_folder(folder):
    try:
        if not any(folder.rglob("*.fits")):
            shutil.rmtree(folder)
            logging.info(f"Deleted empty folder: {folder}")
    except Exception as e:
        logging.warning(f"Could not delete folder {folder}: {e}")

def main():
    if len(sys.argv) > 1:
        root_dir = Path(sys.argv[1]).resolve()
    else:
        root_dir = Path(__file__).parent.resolve()

    logging.info(f"Starting FITS Organizer in {'DRY-RUN' if DRY_RUN else 'LIVE'} mode.")
    logging.info(f"Working directory: {root_dir}")

    destination_map = {}

    for date_dir in root_dir.iterdir():
        if not date_dir.is_dir():
            continue
        for sub in SUBFOLDERS:
            sub_dir = date_dir / sub
            if not sub_dir.exists():
                continue
            for fits_file in sub_dir.glob("*.fits"):
                process_fits_file(fits_file, sub, root_dir, destination_map)
        cleanup_folder(date_dir)

    logging.info("Finished processing.")

if __name__ == "__main__":
    main()
