# N.I.N.A. FITS Organizer
(german version below)

This Python script organizes and renames FITS files created by the astrophotography software [N.I.N.A.](https://nighttime-imaging.eu/). It reads FITS headers and automatically restructures folders and filenames based on imaging parameters and object names.

## 🔧 Features

- Automatically renames FITS files using metadata from the FITS header:
  - Object name, telescope, focal length, camera ID, gain, CCD temperature, exposure time, and date
- Supports all standard N.I.N.A. subfolders: `LIGHT`, `DARK`, `FLAT`, `BIAS`, `SNAPSHOT`
- Creates a new top-level folder for each unique object with a descriptive name
- Automatically prevents filename conflicts (appends numbers if needed)
- Deletes the original folder if it's empty after processing
- Generates a full log of all actions for review and safety

## 📂 Folder Naming Scheme

Top-level folder (where "LIGHT" etc. subfolders go):
```bash
OBJECT_TELESCOP_DATE-LOC_FOCALLEN_eEXPOSURE_gGAIN_tCCD-TEMP_CAMERAID
```
If `OBJECT` is missing or empty, `"UNKNOWN"` is used. All whitespace is replaced with `-`.  
The `DATE-LOC` field is formatted as `YYYY-MM-DD`.

## 🗂 File Naming Scheme

Each FITS file is renamed as:
```bash
IMAGETYP_DATE-LOC_eEXPOSURE_gGAIN_tCCD-TEMP_OBJECT.fits
```
Again, all spaces are replaced with `-` and fallback values like `UNKNOWN` are used if headers are missing.

## 🚀 Usage

```bash
python hg-nina-fits-organizer.py /path/to/nina/data
# If no path is given, the script will use its current directory.
```
### 📄 Example Output
LIGHT_2025-06-13_e120_g100_t-10_M42.fits
With folder:
M42_SkyWatcher_2025-06-13_800_e120_g100_t-10_ASI1600MM

## 📦 Requirements
Python 3.8+
astropy

Install with:

```bash
pip install astropy
```
## 🛡 License
This project is licensed under the MIT License.

Feel free to use, modify, and distribute this software in your own astrophotography workflow!


# German: N.I.N.A. FITS Organizer

Dieses Python-Skript organisiert und benennt FITS-Dateien, die mit der Astrofotografie-Software [N.I.N.A.](https://nighttime-imaging.eu/) erstellt wurden. Es analysiert die FITS-Header und erstellt automatisch strukturierte Ordner und Dateinamen nach Inhalt und Aufnahmeparametern.

## 🔧 Funktionen

- Automatische Umbenennung von FITS-Dateien basierend auf:
  - Objektname, Teleskop, Brennweite, Kamera, Gain, Temperatur, Belichtungszeit
- Automatische Erstellung neuer Ordnerstrukturen pro Himmelsobjekt
- Verarbeitung aller relevanten N.I.N.A.-Unterordner (`LIGHT`, `DARK`, `FLAT`, `BIAS`, `SNAPSHOT`)
- Sicheres Umbenennen (keine Überschreibung bei gleichen Namen)
- Leere Ursprungsordner werden entfernt
- Logdatei zur Nachverfolgung aller Änderungen

## 🚀 Verwendung

```bash
python hg-nina-fits-organizer.py /pfad/zum/nina/ordner
Wenn kein Pfad angegeben wird, verwendet das Skript automatisch den Ordner, in dem es liegt.
```
## 📂 Ordner-Namensschema

Ordner der obersten Ebene (wo die Unterordner "LIGHT" usw. hinkommen):
```bash
OBJECT_TELESCOP_DATE-LOC_FOCALLEN_eEXPOSURE_gGAIN_tCCD-TEMP_CAMERAID
```
Wenn `OBJECT` fehlt oder leer ist, wird `"UNKNOWN"` verwendet. Alle Leerzeichen werden durch „-“ ersetzt.  
Das Feld `DATE-LOC` wird als `YYYY-MM-DD` formatiert.

## 🗂 Dateibenennungsschema

Jede FITS-Datei wird wie folgt umbenannt:
```bash
IMAGETYP_DATE-LOC_eEXPOSURE_gGAIN_tCCD-TEMP_OBJECT.fits
```
Auch hier werden alle Leerzeichen durch `-` ersetzt und Fallback-Werte wie `UNKNOWN` verwendet, wenn Header fehlen.

## 📦 Abhängigkeiten
astropy

Installieren mit:
```bash
pip install astropy
```
## 🛡 Lizenz
Dieses Projekt steht unter der MIT-Lizenz.

