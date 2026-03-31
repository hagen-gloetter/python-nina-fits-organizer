#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Analyze FITS files created by N.I.N.A. and print key acquisition metadata.

Hg-NINA-FITS-Analyser
This Python script reads parameters from FITS files created by the 
astrophotography software N.I.N.A.. 
It extracts key metadata from the FITS headers and prints a
readable analysis report.

Copyright (c) 2024-2025 by ramona & hagen.gloetter@gmail.com
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
from astropy.io import fits


def _as_float(value: object, default: float = 0.0) -> float:
    """Convert values safely for numeric output formatting."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def analyze_fits_header(file_path: Path) -> dict[str, object]:
    """Read header/data and return normalized analysis values."""
    with fits.open(file_path) as hdul:
        header = hdul[0].header
        data = hdul[0].data

    if data is None:
        mean, std = float("nan"), float("nan")
    else:
        mean = float(np.mean(data))
        std = float(np.std(data))

    params = {
        "object": header.get("OBJECT", "Unbekannt"),
        "telescope": header.get("TELESCOP", "Unbekannt"),
        "camera": header.get("INSTRUME", header.get("CAMERAID", "Unbekannt")),
        "exposure": _as_float(header.get("EXPTIME", header.get("EXPOSURE", 0))),
        "gain": _as_float(header.get("GAIN", 0)),
        "sensor_temp": _as_float(header.get("CCD-TEMP", 0)),
        "bayer_pattern": header.get("BAYERPAT", ""),
        "pixel_size": (_as_float(header.get("XPIXSZ", 0)), _as_float(header.get("YPIXSZ", 0))),
        "focal_length": _as_float(header.get("FOCALLEN", 0)),
        "focal_ratio": _as_float(header.get("FOCRATIO", 0)),
        "ra": _as_float(header.get("RA", 0)),
        "dec": _as_float(header.get("DEC", 0)),
        "airmass": _as_float(header.get("AIRMASS", 0)),
        "image_stats": (mean, std),
    }

    return params


def print_analysis(params: dict[str, object]) -> None:
    """Print a readable analysis report for one FITS file."""
    mean, std = params["image_stats"]
    quality = "Gut" if float(params["airmass"]) < 1.5 else "Maessig"

    print("\n" + "=" * 50)
    print(f"ANALYSE: {params['object']} ({params['telescope']})")
    print("=" * 50)
    print(f"Kamera: {params['camera']} (Gain: {params['gain']}, Sensor: {params['sensor_temp']}°C)")
    print(f"Belichtung: {params['exposure']}s | Fokalverhältnis: f/{params['focal_ratio']}")
    print(f"Pixelgroesse: {params['pixel_size'][0]}um | Bayer-Muster: {params['bayer_pattern']}")
    print(f"Koordinaten (J2000): RA={params['ra']:.4f}°, DEC={params['dec']:.4f}°")
    print(f"Luftmasse: {params['airmass']:.2f} ({quality})")
    print(f"\nBildstatistik: Mittelwert={mean:.1f}, StdDev={std:.1f} (ADU)")

    if params['sensor_temp'] > -10:
        print("\nWarnung: Sensortemperatur koennte zu hoch sein (Ziel: <-10C)")
    if params['airmass'] > 2.0:
        print("Warnung: Hohe Luftmasse -> Atmosphaerische Stoerungen wahrscheinlich")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analysiert FITS-Header und Bildstatistiken.")
    parser.add_argument("fits_file", help="Pfad zur FITS-Datei")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    fits_file = Path(args.fits_file).expanduser().resolve()

    if not fits_file.exists() or not fits_file.is_file():
        print(f"FEHLER: Datei nicht gefunden: {fits_file}")
        return 1

    params = analyze_fits_header(fits_file)
    print_analysis(params)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())