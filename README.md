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

# N.I.N.A. FITS Organizer

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
python nina_rename.py /pfad/zum/nina/ordner
