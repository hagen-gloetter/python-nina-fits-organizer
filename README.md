# N.I.N.A. FITS Organizer

Python tools for astrophotography workflows with N.I.N.A.-generated FITS files.

This repository contains:
- a production script to organize and rename FITS files safely
- an analysis script to inspect one FITS file and print useful acquisition stats
- lightweight automated tests for critical naming/path helpers

## Project Purpose

The organizer script restructures FITS files into metadata-based target folders and applies deterministic filenames. This helps with:
- consistent data curation
- easier stacking/preprocessing in later tools
- reduced manual file handling errors

## Features

- Reads FITS headers via astropy
- Supports N.I.N.A. capture folders: LIGHT, DARK, FLAT, BIAS, SNAPSHOT
- Generates folder names from object/session metadata
- Generates deterministic file names from key acquisition values
- Prevents accidental overwrites by adding numeric suffixes if needed
- Writes timestamped log files in the selected source directory
- Supports dry-run mode to preview actions

## Repository Structure

- hg-nina-fits-organizer.py: main organizer CLI
- hg_analyse_fits-files.py: single-file FITS analyzer CLI
- tests/test_organizer.py: unit tests for helper behavior
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

Run:

```bat
make_venv.bat
```

## Usage

### Organize a N.I.N.A. dataset

```bash
python hg-nina-fits-organizer.py /path/to/nina/root
```

### Dry-run mode

```bash
python hg-nina-fits-organizer.py /path/to/nina/root --dry-run
```

### Analyze one FITS file

```bash
python hg_analyse_fits-files.py /path/to/file.fits
```

## Naming Scheme

### Target folder hierarchy

The organizer creates one session folder and then one subfolder per frame type.

Session folder:

```text
OBJECT_TELESCOP_DATE_FOCALLEN_gGAIN_tCCD-TEMP_CAMERAID
```

Exposure is intentionally excluded from the session folder name so multiple exposure times for the same object/session stay together.

Subfolders inside this session folder:

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
- run both CLIs with --help
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

