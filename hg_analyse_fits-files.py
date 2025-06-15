#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hg-NINA-FITS-Analyser
This Python script reads parameters from FITS files created by the 
astrophotography software N.I.N.A.. 

Ein Skript zum Analysieren von FITS-Dateien, die von NINA (Nighttime Imaging 'N' Astronomy) generiert wurden.
Dieses Skript extrahiert wichtige Metadaten aus den Headern der FITS-Dateien und gibt eine Zusammenfassung der Bildparameter aus.

Copyright (c) 2024-2025 by ramona & hagen.gloetter@gmail.com
Dieses Skript ist lizenziert unter der MIT-Lizenz.
"""

from astropy.io import fits
import numpy as np

def analyze_fits_header(file_path):
    # Lade FITS-Datei
    with fits.open(file_path) as hdul:
        header = hdul[0].header
        data = hdul[0].data  # Für spätere Bildanalyse

    # Extrahiere relevante Parameter
    params = {
        'object': header.get('OBJECT', 'Unbekannt'),
        'telescope': header.get('TELESCOP', 'Unbekannt'),
        'camera': header.get('INSTRUME', 'Unbekannt'),
        'exposure': header.get('EXPTIME', 0),
        'gain': header.get('GAIN', 0),
        'sensor_temp': header.get('CCD-TEMP', 0),
        'bayer_pattern': header.get('BAYERPAT', ''),
        'pixel_size': (header.get('XPIXSZ', 0), header.get('YPIXSZ', 0)),
        'focal_length': header.get('FOCALLEN', 0),
        'focal_ratio': header.get('FOCRATIO', 0),
        'ra': header.get('RA', 0),
        'dec': header.get('DEC', 0),
        'airmass': header.get('AIRMASS', 0)
    }

    # Berechne Bildstatistiken
    mean, std = np.mean(data), np.std(data)
    params['image_stats'] = (mean, std)

    # Ausgabe der Analyse
    print("\n" + "="*50)
    print(f"ANALYSE: {params['object']} ({params['telescope']})")
    print("="*50)
    print(f"Kamera: {params['camera']} (Gain: {params['gain']}, Sensor: {params['sensor_temp']}°C)")
    print(f"Belichtung: {params['exposure']}s | Fokalverhältnis: f/{params['focal_ratio']}")
    print(f"Pixelgröße: {params['pixel_size'][0]}µm | Bayer-Muster: {params['bayer_pattern']}")
    print(f"Koordinaten (J2000): RA={params['ra']:.4f}°, DEC={params['dec']:.4f}°")
    print(f"Luftmasse: {params['airmass']:.2f} ({'Gut' if params['airmass'] < 1.5 else 'Mäßig'})")
    print(f"\nBildstatistik: Mittelwert={mean:.1f}, StdDev={std:.1f} (ADU)")

    # Warnungen bei kritischen Werten
    if params['sensor_temp'] > -10:
        print("\n⚠️ Warnung: Sensortemperatur könnte zu hoch sein (Ziel: <-10°C)")
    if params['airmass'] > 2.0:
        print("⚠️ Warnung: Hohe Luftmasse -> Atmosphärische Störungen wahrscheinlich")

# Beispielaufruf (ersetze mit deinem Dateipfad)
analyze_fits_header("Example_FITS_Header.fits")