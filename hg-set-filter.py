#!/usr/bin/env python3
"""
hg_set_filter.py  –  FITS-Filter-Wert in allen FITS-Files eines Ordners setzen

Verwendung:
    python hg_set_filter.py <ordner> [filter]

Parameter:
    <ordner>   Pfad zum Ordner mit den FITS-Files (*.fits / *.fit)
    [filter]   Filterwert, der gesetzt werden soll (optional).
               Erlaubte Werte: B / G / L / NONE / NOFILTER / R / RGB
               Default: NOFILTER

Beispiele:
    python hg_set_filter.py D:\\Bilder\\LIGHT\\              # setzt NOFILTER (default)
    python hg_set_filter.py D:\\Bilder\\LIGHT\\ RGB          # setzt RGB
    python hg_set_filter.py D:\\Bilder\\LIGHT\\ L            # setzt L

Hinweis:
    Der FITS-Header-Key FILTER wird direkt in den Dateien überschrieben.
    Es wird kein Backup erstellt!
"""

import sys
from pathlib import Path
from astropy.io import fits

VALID_FILTERS = {"L", "R", "G", "B", "NONE", "RGB", "NOFILTER"}
DEFAULT_FILTER = "NOFILTER"


def set_filter(folder: Path, filter_value: str) -> None:
    fits_files = list(folder.glob("*.fits")) + list(folder.glob("*.fit"))
    if not fits_files:
        print(f"No FITS files found in {folder}")
        return

    for f in fits_files:
        with fits.open(f, mode="update") as hdul:
            hdul[0].header["FILTER"] = filter_value
        print(f"  {f.name}  ->  FILTER = {filter_value}")

    print(f"\nDone. Updated {len(fits_files)} file(s).")


def main():
    if len(sys.argv) < 2 or len(sys.argv) > 3:
        print(f"Usage: python hg_set_filter.py <folder> [filter]")
        print(f"  filter: {'/'.join(sorted(VALID_FILTERS))}  (default: {DEFAULT_FILTER})")
        sys.exit(1)

    folder = Path(sys.argv[1])
    if not folder.is_dir():
        print(f"Error: '{folder}' is not a valid directory.")
        sys.exit(1)

    filter_value = sys.argv[2].upper() if len(sys.argv) == 3 else DEFAULT_FILTER
    if filter_value not in VALID_FILTERS:
        print(f"Error: Invalid filter '{filter_value}'. Choose from: {'/'.join(sorted(VALID_FILTERS))}")
        sys.exit(1)

    print(f"Setting FILTER = '{filter_value}' in all FITS files in: {folder}\n")
    set_filter(folder, filter_value)


if __name__ == "__main__":
    main()
