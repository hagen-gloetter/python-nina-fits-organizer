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

# usage:
#  python .\hg-nina-fits-organizer_ds.py --source K:\NINA\NINA\

import os
import shutil
from astropy.io import fits
from datetime import datetime
import argparse
import logging

# Konfiguration
DRY_RUN =  False # Trockenlauf: True (Testmodus), False (echte Ausführung)

def setup_logging(source_dir):
    log_filename = datetime.now().strftime("%Y-%m-%d_%H-%M-%S") + "_fits_organizer.log"
    log_path = os.path.join(source_dir, log_filename)
    
    # Konfiguriere Logging für Datei UND Konsole
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    
    # Logging in Datei
    file_handler = logging.FileHandler(log_path)
    file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(file_handler)
    
    # Logging auf Konsole
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s', datefmt='%Y-%m-%d %H:%M:%S'))
    logger.addHandler(console_handler)
    
    logging.info(f"Starte Verarbeitung in: {source_dir}")
    

def sanitize(text: str, default: str = "LEER") -> str:
    """Bereinigt Header-Werte für Dateinamen/Ordner.
    Args:
        text: Rohwert aus FITS-Header
        default: Rückgabewert bei leerem String
    Returns:
        Bereinigter String oder default
    """
    if not isinstance(text, str):
        text = str(text)
    if not text.strip():
        return default

    # Sonderzeichen ersetzen
    replacements = {
        " ": "-", "/": "-", ":": "-",  # Basisersetzungen
        "\\": "-", "|": "-", "\"": "",  # Erweitert für Windows-Kompatibilität
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text.strip()

def clean_dashes(text: str) -> str:
    """Ersetzt aufeinanderfolgende Bindestriche durch einen einzelnen."""
    import re
    return re.sub(r'-{2,}', '-', text).strip('-')

def get_header_value(header, key, default="NA"):
    """Hole einen Header-Wert oder gib Default zurück."""
    value = header.get(key, default)
    return sanitize(value) if value != "" else default

def create_target_directory(source_dir, header):
    """Erzeuge den Zielordner-Namen basierend auf dem Header."""
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    date_loc = get_header_value(header, "DATE-LOC").split("T")[0]  # Nur YYYY-MM-DD
    focal_length = get_header_value(header, "FOCALLEN")
    exposure = get_header_value(header, "EXPOSURE")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    camera_id = get_header_value(header, "CAMERAID")

    dir_name = f"{object_name}_{telescope}_{date_loc}_{focal_length}_e{exposure}_g{gain}_t{ccd_temp}_{camera_id}"
    dir_name = clean_dashes(dir_name)  # Bereinige doppelte Bindestriche!
    target_dir = os.path.join(source_dir, dir_name)
    return target_dir

def process_fits_file(source_path, target_dir):
    """Verarbeite eine FITS-Datei: Kopiere/verschiebe sie mit neuem Namen."""
    with fits.open(source_path) as hdul:
        header = hdul[0].header

    imagetype = get_header_value(header, "IMAGETYP").upper()
    date_loc = get_header_value(header, "DATE-LOC").split("T")[0]
    exposure = get_header_value(header, "EXPOSURE")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")

    # Extrahiere Nummer aus dem Dateinamen (z.B. "_0007" in "file_0007.fits")
    base_name = os.path.basename(source_path)
    number_part = "_" + base_name.split("_")[-1].split(".")[0]  # Behält "_0007"
    new_filename = f"{imagetype}_{date_loc}_e{exposure}_g{gain}_t{ccd_temp}_{object_name}{number_part}.fits"
    new_filename = clean_dashes(new_filename)  # Bereinigt z.B. "LIGHT_2025-06-14_e--g200_t-9.8_M-51_0007.fits"
    # Zielpfad erstellen (z.B. "M-51_.../LIGHT/LIGHT_..._0007.fits")
    subfolder = imagetype if imagetype in ["LIGHT", "DARK", "FLAT", "BIAS", "SNAPSHOT"] else "OTHER"
    target_subdir = os.path.join(target_dir, subfolder)
    os.makedirs(target_subdir, exist_ok=True)
    target_path = os.path.join(target_subdir, new_filename)

    # Loggen der Aktion
    logging.info(f"Verschiebe: {source_path} -> {target_path}")

    if not DRY_RUN:
        shutil.move(source_path, target_path)

def process_directory(source_dir):
    """Durchsuche den Ausgangsordner und gruppiere Dateien nach Objekt+Datum."""
    object_date_map = {}  # { (object, date): target_dir }

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(".fits"):
                source_path = os.path.join(root, file)
                try:
                    with fits.open(source_path) as hdul:
                        header = hdul[0].header

                    # Eindeutiger Schlüssel für Objekt+Datum
                    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
                    date_part = get_header_value(header, "DATE-LOC").split("T")[0]
                    object_date_key = (object_name, date_part)

                    # Zielordner wiederverwenden oder neu erstellen
                    if object_date_key not in object_date_map:
                        target_dir = create_target_directory(source_dir, header)
                        object_date_map[object_date_key] = target_dir
                        logging.info(f"Neuer Zielordner: {target_dir}")
                    else:
                        target_dir = object_date_map[object_date_key]

                    process_fits_file(source_path, target_dir)

                except Exception as e:
                    logging.error(f"Fehler bei {file}: {str(e)}")

    # Bereinige leere Ordner nach der Verarbeitung
    for root, dirs, files in os.walk(source_dir, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                logging.info(f"Lösche leeren Ordner: {dir_path}")
                if not DRY_RUN:
                    os.rmdir(dir_path)

def main():
    parser = argparse.ArgumentParser(description="Organisiere FITS-Dateien nach Header-Daten.")
    parser.add_argument("--source", help="Ausgangsordner (Standard: aktuelles Verzeichnis)", default=".")
    args = parser.parse_args()

    source_dir = os.path.abspath(args.source)
    setup_logging(source_dir)
    process_directory(source_dir)
    logging.info("Verarbeitung abgeschlossen.")

if __name__ == "__main__":
    main()
