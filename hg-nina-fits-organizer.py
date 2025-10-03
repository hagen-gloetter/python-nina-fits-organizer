import os
import shutil
from astropy.io import fits
from datetime import datetime
import argparse
import logging
import sys

# Konfiguration
DRY_RUN = False  # Trockenlauf: True (Testmodus), False (echte Ausführung)

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

def clean_string(value):
    """Ersetze Leerzeichen durch Bindestriche und entferne ungültige Zeichen."""
    if not isinstance(value, str):
        value = str(value)
    return value.replace(" ", "-").replace("/", "-").replace(":", "-")

def clean_dashes(text: str) -> str:
    """Ersetzt aufeinanderfolgende Bindestriche durch einen einzelnen."""
    import re
    return re.sub(r'-{2,}', '-', text).strip('-')

def clean_camera_name(camera_id):
    """Entfernt überflüssige 'ZWOptical_ZWO' Präfixe aus Kameranamen."""
    if not isinstance(camera_id, str):
        camera_id = str(camera_id)
    # Entferne "ZWOptical_ZWO" und "ZWO" Präfixe
    camera_id = camera_id.replace("ZWOptical_ZWO", "").replace("ZWO", "").strip(" _-")
    return camera_id

def get_header_value(header, key, default="N/A"):
    """Hole einen Header-Wert oder gib Default zurück."""
    value = header.get(key, default)
    if key == "CAMERAID":
        value = clean_camera_name(value)
    return clean_string(value) if value != "" else default

def count_unknown_fields(header):
    """Zählt wie viele kritische Felder UNKNOWN oder N/A sind."""
    critical_fields = ["OBJECT", "TELESCOP", "DATE-LOC", "FOCALLEN", "EXPOSURE", "CAMERAID"]
    unknown_count = 0
    
    for field in critical_fields:
        value = get_header_value(header, field, "N/A")
        if value in ["UNKNOWN", "N/A"]:
            unknown_count += 1
    
    return unknown_count

def create_target_directory(source_dir, header, imagetype):
    """Erzeuge den Zielordner-Namen basierend auf dem Header und IMAGETYP."""
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    date_loc = get_header_value(header, "DATE-LOC").split("T")[0]  # Nur YYYY-MM-DD
    focal_length = get_header_value(header, "FOCALLEN")
    exposure = get_header_value(header, "EXPOSURE")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    camera_id = get_header_value(header, "CAMERAID")

    # Für DARK und FLAT: Spezielle Ordnernamen
    if imagetype.upper() in ["DARK", "FLAT"]:
        dir_name = f"{imagetype.upper()}_{telescope}_{date_loc}_{focal_length}_e{exposure}_g{gain}_t{ccd_temp}_{camera_id}"
    else:
        dir_name = f"{object_name}_{telescope}_{date_loc}_{focal_length}_e{exposure}_g{gain}_t{ccd_temp}_{camera_id}"
    
    dir_name = clean_dashes(dir_name)  # Bereinige doppelte Bindestriche!
    target_dir = os.path.join(source_dir, dir_name)
    return target_dir

def process_fits_file(source_path, target_dir, imagetype):
    """Verarbeite eine FITS-Datei: Kopiere/verschiebe sie mit neuem Namen."""
    with fits.open(source_path) as hdul:
        header = hdul[0].header

    # Prüfe auf zu viele UNKNOWN-Felder
    unknown_count = count_unknown_fields(header)
    if unknown_count > 2:
        logging.warning(f"SKIP: Zu viele unbekannte Felder ({unknown_count}) -> {source_path}")
        print(f"⚠️  SKIP: {os.path.basename(source_path)} (zu viele unbekannte Felder: {unknown_count})")
        return

    date_loc = get_header_value(header, "DATE-LOC").split("T")[0]
    exposure = get_header_value(header, "EXPOSURE")
    gain = get_header_value(header, "GAIN")
    ccd_temp = get_header_value(header, "CCD-TEMP")
    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
    telescope = get_header_value(header, "TELESCOP")
    filter_name = get_header_value(header, "FILTER", "NOFILTER")
    camera_id = get_header_value(header, "CAMERAID")

    # Extrahiere Nummer aus dem Dateinamen (z.B. "_0007" in "file_0007.fits")
    base_name = os.path.basename(source_path)
    number_part = "_" + base_name.split("_")[-1].split(".")[0]  # Behält "_0007"
    
    # Für DARK und FLAT: Spezielle Dateinamen mit Teleskop
    if imagetype.upper() in ["DARK", "FLAT"]:
        new_filename = f"{imagetype.upper()}_{date_loc}_{object_name}_{camera_id}_e{exposure}_g{gain}_{filter_name}_t{ccd_temp}{number_part}.fits"
    else:
        # LIGHT Dateien: IMAGETYP_DATUM_OBJECT_KAMERA_eEXPOSURE_gGAIN_FILTER_tTEMP_NUMMER
        new_filename = f"{imagetype.upper()}_{date_loc}_{object_name}_{camera_id}_e{exposure}_g{gain}_{filter_name}_t{ccd_temp}{number_part}.fits"
    
    new_filename = clean_dashes(new_filename)  # Bereinige doppelte Bindestriche!

    # Zielpfad erstellen (gleiche Ebene für alle Dateitypen)
    target_subdir = target_dir  # Keine Unterordner mehr für DARK/FLAT
    os.makedirs(target_subdir, exist_ok=True)
    target_path = os.path.join(target_subdir, new_filename)

    # Skip-Logik bei identischen Pfaden
    if os.path.normpath(source_path) == os.path.normpath(target_path):
        logging.info(f"SKIP: Quelle und Ziel identisch -> {source_path}")
        if not DRY_RUN:
            print(f"SKIP: {source_path}")  # Zusätzliche Konsolenausgabe
        return  # Frühzeitiger Abbruch

    # Loggen der Aktion
    logging.info(f"Verschiebe: {source_path} -> {target_path}")
    if not DRY_RUN:
        shutil.move(source_path, target_path)

def process_directory(source_dir):
    """Durchsuche den Ausgangsordner und gruppiere Dateien nach Objekt+Datum+IMAGETYP."""
    object_date_map = {}  # { (object, date, imagetype): target_dir }

    for root, dirs, files in os.walk(source_dir):
        for file in files:
            if file.lower().endswith(".fits"):
                source_path = os.path.join(root, file)
                try:
                    with fits.open(source_path) as hdul:
                        header = hdul[0].header

                    # Prüfe auf zu viele UNKNOWN-Felder für die Gruppierung
                    unknown_count = count_unknown_fields(header)
                    if unknown_count > 2:
                        logging.warning(f"SKIP: Zu viele unbekannte Felder ({unknown_count}) -> {source_path}")
                        print(f"⚠️  SKIP: {file} (zu viele unbekannte Felder: {unknown_count})")
                        continue  # Überspringe diese Datei komplett

                    imagetype = get_header_value(header, "IMAGETYP").upper()

                    # Eindeutiger Schlüssel für Objekt+Datum+IMAGETYP
                    object_name = get_header_value(header, "OBJECT", "UNKNOWN")
                    date_part = get_header_value(header, "DATE-LOC").split("T")[0]
                    
                    # Für DARK und FLAT: Gruppiere separat (ohne OBJECT)
                    if imagetype in ["DARK", "FLAT"]:
                        object_date_key = (imagetype, date_part)
                    else:
                        object_date_key = (object_name, date_part, imagetype)

                    # Zielordner wiederverwenden oder neu erstellen
                    if object_date_key not in object_date_map:
                        target_dir = create_target_directory(source_dir, header, imagetype)
                        object_date_map[object_date_key] = target_dir
                        logging.info(f"Neuer Zielordner: {target_dir}")
                    else:
                        target_dir = object_date_map[object_date_key]

                    process_fits_file(source_path, target_dir, imagetype)

                except Exception as e:
                    logging.error(f"Fehler bei {file}: {str(e)}")

    # Bereinige leere Ordner
    for root, dirs, files in os.walk(source_dir, topdown=False):
        for dir in dirs:
            dir_path = os.path.join(root, dir)
            if not os.listdir(dir_path):
                logging.info(f"Lösche leeren Ordner: {dir_path}")
                if not DRY_RUN:
                    os.rmdir(dir_path)

def print_usage():
    """Gibt Usage-Informationen aus."""
    print("\n" + "="*60)
    print("FITS ORGANIZER - Astrofotografie Datei-Organisation")
    print("="*60)
    print("Usage:")
    print("  python fits_organizer.py <PFAD_ZU_FITS_ORDNER>")
    print("\nBeispiele:")
    print("  python fits_organizer.py C:\\Astro\\Aufnahmen\\2025-06-14")
    print("  python fits_organizer.py \"/home/user/astro/raw_data\"")
    print("  python fits_organizer.py .                         (aktuelles Verzeichnis)")
    print("\nOptionen:")
    print("  --help, -h     Zeige diese Hilfemeldung")
    print("\nOrdnerstruktur:")
    print("  LIGHT:  M-51_ASA10_2025-06-14_950_e180_g200_t-9.8_ASI2600MC-Pro/")
    print("  DARK:   DARK_ASA10_2025-06-14_950_e180_g200_t-9.8_ASI2600MC-Pro/")
    print("  FLAT:   FLAT_ASA10_2025-06-14_950_e180_g200_t-9.8_ASI2600MC-Pro/")
    print("\nDateinamen:")
    print("  LIGHT:  LIGHT_2025-06-14_M-51_ASI2600MC-Pro_e180_g200_L-Pro_t-9.8_0007.fits")
    print("  DARK:   DARK_2025-06-14_UNKNOWN_ASI2600MC-Pro_e180_g200_NOFILTER_t-9.8_0001.fits")
    print("  FLAT:   FLAT_2025-06-14_UNKNOWN_ASI2600MC-Pro_e0.1_g200_L-Pro_t-9.8_0001.fits")
    print("="*60 + "\n")

def main():
    # Prüfe Hilfe-Parameter
    if len(sys.argv) > 1 and (sys.argv[1] in ["--help", "-h", "/?"]):
        print_usage()
        sys.exit(0)
    
    # Bestimme Quellordner
    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
    else:
        print("❌ FEHLER: Bitte gib einen Pfad an!")
        print_usage()
        sys.exit(1)
    
    # Prüfe ob der Ordner existiert
    if not os.path.exists(source_dir):
        print(f"❌ FEHLER: Ordner '{source_dir}' existiert nicht!")
        sys.exit(1)
    
    source_dir = os.path.abspath(source_dir)
    print(f"🎯 Starte Verarbeitung von: {source_dir}")
    
    setup_logging(source_dir)
    process_directory(source_dir)
    logging.info("Verarbeitung abgeschlossen.")
    print("✅ Verarbeitung abgeschlossen!")

if __name__ == "__main__":
    main()