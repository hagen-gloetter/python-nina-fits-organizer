# N.I.N.A. FITS Organizer

Python tools for astrophotography workflows with N.I.N.A.-generated FITS files.

This repository contains:
- a production script to organize and rename FITS files safely
- an analysis script to inspect one FITS file and print useful acquisition stats
- a standalone duplicate-finder script to quarantine byte-for-byte identical FITS files
- lightweight automated tests for critical naming/path helpers

## Project Purpose

The organizer script restructures FITS files into metadata-based target folders and applies deterministic filenames. This helps with:
- consistent data curation
- easier stacking/preprocessing in later tools
- reduced manual file handling errors

## Features

- Reads FITS headers via astropy
- Creates PixInsight-compatible target structure (`<JAHR>_<OBJEKT>_<Teleskop>[_<Kamera>]`) with subfolders `LIGHT`, `DARK`, `FLAT`, `BIAS`, `PROCESSING`, `PRO`, `FINAL`
- Canonicalizes Messier/NGC/IC object names regardless of spelling (`"M 31"`, `"m31"`, `"M-31"`, `"Messier 31"` all become `M31`) and appends a common name for well-known objects (e.g. `M31-Andromedagalaxie`); existing folders using an older spelling are automatically migrated on the next real run
- Automatically organizes FITS files located directly in night/session folders or in capture subfolders into their corresponding frame-type directories
- Frames whose type cannot be determined from header, folder, or filename are routed to a visible `UNKNOWN` subfolder instead of being guessed as `LIGHT`
- Generates deterministic file names from key acquisition values
- Migrates existing companion files, stacked results, and preview images into the target project
- Detects byte-for-byte identical re-copies of an already-organized file (e.g. accidentally re-imported raw data) and overwrites the existing target instead of creating a duplicate frame
- Prevents accidental overwrites by adding numeric suffixes for genuinely different files that happen to compute the same target name
- Cleans up empty source folders after restructuring
- Writes timestamped log files in the selected source directory
- Supports dry-run mode to preview actions

## Repository Structure

- hg-nina-fits-organizer.py: main organizer CLI
- hg_analyse_fits-files.py: single-file FITS analyzer CLI
- hg-remove-duplicates.py: standalone duplicate-finder/quarantine CLI
- tests/test_organizer.py: unit tests for helper behavior
- tests/test_remove_duplicates.py: unit tests for the duplicate finder
- requirements.txt: Python dependencies
- make_venv.bat: Windows setup helper

## Setup

### Requirements

- Python 3.10+
- pip

### Installation (macOS/Linux/Windows)

```bash
python -m venv astro_env
source astro_env/bin/activate  # Windows: astro_env\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### Windows Shortcut

Run in PowerShell (from the repo root):

```powershell
.\make_venv.bat
```

Creates/updates the `astro_env_win` virtual environment and installs dependencies.
It automatically rebuilds the venv if a previous run was interrupted, and verifies
the `py` launcher and each install step, so it's safe to re-run at any time.

Activate afterwards with:

```powershell
.\astro_env_win\Scripts\Activate.ps1   # PowerShell
astro_env_win\Scripts\activate.bat     # cmd.exe
```

## Usage

### Organize a N.I.N.A. dataset

Verwendung:

```bash
python hg-nina-fits-organizer.py /path/to/nina/root
```

Parameter:

- `/path/to/nina/root`: N.I.N.A.-Basisordner mit den Capture-Ordnern `LIGHT`, `DARK`, `FLAT`, `BIAS` oder `SNAPSHOT`.
- `--dry-run`: zeigt die geplanten Verschiebungen und das Entfernen leerer Unterordner an, ohne Änderungen vorzunehmen.

Beispiele:

```bash
python hg-nina-fits-organizer.py /path/to/nina/root --dry-run
python hg-nina-fits-organizer.py D:\\Bilder\\NINA\\2025-01-15
```

Nach der Verarbeitung zeigt das Skript eine Zusammenfassung mit Modus,
Dateizahlen, Zielordnern, übersprungenen Dateien, Fehlern und einer Aufteilung
nach Bildtyp. Im `--dry-run`-Modus werden die geplanten Aktionen mit
`[DRY-RUN]` markiert; die ausführlichen Zeitstempel-Einträge stehen weiterhin
in der erzeugten Logdatei.

Beispielausgabe:

```text
================================================================
N.I.N.A. FITS ORGANIZER - ZUSAMMENFASSUNG
================================================================
Quelle        : D:\Bilder\NINA\2026-04
Modus         : ECHTLAUF
Dateien       : 128
Verarbeitet   : 128
Übersprungen   : 0
Fehler         : 0
Zielordner     : 1
Entfernt       : 4 leere Ordner

Dateien nach Typ:
	BIAS        : 20
	DARK        : 24
	FLAT        : 24
	LIGHT       : 60

Logdatei       : D:\Bilder\NINA\2026-04\2026-09-13_21-30-00_fits_organizer.log
================================================================
```

### Analyze one FITS file

Verwendung:

```bash
python hg_analyse_fits-files.py /path/to/file.fits
```

Parameter:

- `/path/to/file.fits`: genau eine FITS-Datei. Das Skript liest den Header und berechnet Bildstatistiken, verändert die Datei aber nicht.

Beispiel:

```bash
python hg_analyse_fits-files.py D:\\Bilder\\LIGHT\\bild_0001.fits
```

### Set the FITS filter value

Verwendung:

```bash
python hg_set_filter.py <folder> [filter]
```

Parameter:

- `<folder>`: Ordner mit FITS-Dateien (`*.fits` oder `*.fit`).
- `[filter]`: optionaler Wert `B`, `G`, `L`, `NONE`, `NOFILTER`, `R` oder `RGB`; Standard ist `NOFILTER`.

Beispiele:

```bash
python hg_set_filter.py D:\\Bilder\\LIGHT\\
python hg_set_filter.py D:\\Bilder\\LIGHT\\ RGB
python hg_set_filter.py D:\\Bilder\\LIGHT\\ L
```

Hinweis: Der FITS-Header-Key `FILTER` wird direkt in den Dateien überschrieben. Es wird kein Backup erstellt.

### Find and quarantine duplicate FITS files

Verwendung:

```bash
python hg-remove-duplicates.py <ordner> [--dry-run]
```

Parameter:

- `<ordner>`: Wird rekursiv nach `*.fits`/`*.fit`-Dateien durchsucht.
- `--dry-run`: zeigt nur an, welche Duplikate verschoben würden, ohne Änderungen vorzunehmen.

Beispiele:

```bash
python hg-remove-duplicates.py K:\NINA3\2026_Snapshot_ASA10_ASI6200MM-Pro\LIGHT --dry-run
python hg-remove-duplicates.py K:\NINA3
```

Duplikate werden ausschließlich über den Dateiinhalt erkannt (Größe + SHA-256-Hash, Dateiname spielt keine Rolle). Aus jeder Gruppe inhaltlich identischer Dateien bleibt die Datei mit dem alphabetisch ersten Pfad unangetastet; alle weiteren Kopien werden - unter Beibehaltung ihres relativen Pfads - in einen Ordner `_DUPLICATES_REMOVED/<Zeitstempel>/...` im Basisordner verschoben, **nicht gelöscht**. Der Quarantäne-Ordner selbst wird bei jedem Lauf automatisch von der Suche ausgeschlossen. Während des Laufs zeigt die Konsole laufend an, wie viele Dateien gefunden und geprüft wurden. Eine Zeitstempel-Logdatei wird im Basisordner angelegt.

## Naming Scheme

### Target folder hierarchy

The organizer creates one folder per year, object, telescope, and camera, then one subfolder per frame type.

Object folder:

```text
YYYY_OBJECT_TELESCOP_CAMERAID/
```

All nights and acquisition setups in the same year for the same object, telescope, and camera are kept together. The exact date and time remain in each FITS filename and in its FITS header.

Subfolders inside this object folder:

```text
LIGHT/
DARK/
FLAT/
BIAS/
PROCESSING/   # created from source folder SNAPSHOT
```

### Target filename

```text
YYYYMMDD-HHMMSS_IMAGETYP_DATE_OBJECT_CAMERAID_eEXPOSURE_gGAIN_FILTER_tCCD-TEMP_<sequence>.fits
```

Invalid filesystem characters are normalized to dashes.

## Configuration Notes

- The organizer only scans files inside known capture directories (LIGHT/DARK/FLAT/BIAS/SNAPSHOT) to avoid re-processing already moved output files.
- Files with too many unknown critical header fields are skipped by design.
- Log files are written into the source root and tracked by timestamp.

## Development Workflow

Run tests:

```bash
pytest -q
```

Recommended local checks before commit:
- run tests
- run all CLIs with `--help`
- test organizer with --dry-run on representative sample data

## Known Particularities

- FITS header field naming differs between devices/software versions. The scripts include fallbacks, but uncommon custom headers may still require extension.
- The analyzer prints a compact text report and is intentionally kept dependency-light.

## Security and Safety

- No overwrite by default for existing target names (numeric suffixing)
- Defensive parsing for numeric values in analyzer output
- Explicit CLI argument validation for existing file/directory paths

## License

MIT License. See LICENSE.

