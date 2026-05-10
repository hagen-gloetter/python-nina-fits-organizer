# PixInsight 1.9.3 Lockhart - Vollstaendiger HDR-Workflow fuer M13

## Setup
- Kamera: ZWO ASI2600MC Pro (Color OSC, Bayer RGGB)
- Teleskop: ASA10, 950 mm Brennweite, f/3.8
- Objekt: M13 (Grosser Herkules-Kugelsternhaufen)
- Serien: 1s / 3s / 10s / 30s / 180s (je mehrere Frames pro Serie)
- Kalibrierung: Darks (je Belichtungszeit), Flats, Biases vorhanden
- Plugins: GraXpert, StarXTerminator (StarNet2)
- Ziel: Publikationsreifes PNG mit vollem Dynamikumfang

## Schritt 1 - Projekt vorbereiten
1. PixInsight starten.
2. File > New Project -> Projektname: "M13_HDR"
3. Ordnerstruktur anlegen:

```text
M13_HDR/
  RAW/
    1s/
    3s/
    10s/
    30s/
    180s/
  CALIB/
    Darks/
    Flats/
    Biases/
  MASTERS/
  STACKED/
  HDR/
  FINAL/
```

## Schritt 2 - WeightedBatchPreprocessing (WBPP) konfigurieren
WBPP uebernimmt Master-Erstellung, Kalibrierung, Debayer, Registrierung und Integration.

- Script > Batch Processing > WeightedBatchPreprocessing
- Lights laden: alle 5 Serien (1s, 3s, 10s, 30s, 180s)
- Darks laden: je Belichtungszeit passende Darks
- Flats laden
- Biases laden

Wichtige WBPP-Einstellungen:
- CFA Images: ON (OSC-Daten)
- Debayer CFA Images: ON
- Bayer Pattern: RGGB
- Cosmetic Correction: nur wenn Hotpixel sichtbar
- Calibrate dark frames: OFF (klassisch)
- Optimize dark frames: ON
- Generate drizzle data: OFF (fuer diesen HDR-Workflow nicht noetig)

Gruppierung in WBPP:
- Lights nach Exposure gruppieren (1s/3s/10s/30s/180s)
- Darks streng nach Exposure matchen
- Flats nach Filter/Session matchen (hier Filter konsistent halten)

Output in WBPP:
- Separate integration groups behalten
- Ziel: pro Belichtungszeit ein fertiger, linearer Integrations-Stack

## Schritt 3 - WBPP ausfuehren und Outputs pruefen
Nach Run sollten mindestens diese Dateien vorliegen (Namen je nach WBPP-Template leicht abweichend):
- `WBPP/.../master/masterBias.xisf`
- `WBPP/.../master/masterDark_1s.xisf` bis `masterDark_180s.xisf`
- `WBPP/.../master/masterFlat.xisf`
- `WBPP/.../integrated/LIGHT_1s.xisf`
- `WBPP/.../integrated/LIGHT_3s.xisf`
- `WBPP/.../integrated/LIGHT_10s.xisf`
- `WBPP/.../integrated/LIGHT_30s.xisf`
- `WBPP/.../integrated/LIGHT_180s.xisf`

Qualitaetscheck vor HDR:
- Alle 5 Integrationen muessen linear sein (nicht gestretcht).
- Sternabbildung in allen 5 Bildern deckungsgleich pruefen.
- Falls noetig: StarAlignment nur auf die 5 integrierten Bilder erneut ausfuehren.

## Schritt 4 - Optionaler Feinschliff der WBPP-Integrationen
Nur falls ein Stack auffaellig schlechter ist:
- SubframeSelector auf der betroffenen Serie
- Schlechteste Frames verwerfen
- WBPP fuer diese Serie erneut laufen lassen

## Schritt 5 - Finale Dateiauswahl fuer HDR
Lege die 5 finalen WBPP-Integrationen in einem Ordner ab, z. B.:
- `STACKED/stack_1s.xisf`
- `STACKED/stack_3s.xisf`
- `STACKED/stack_10s.xisf`
- `STACKED/stack_30s.xisf`
- `STACKED/stack_180s.xisf`

Diese 5 Dateien sind die direkte Eingabe fuer HDRComposition.

## Schritt 6 - HDR Composition
- Process > HDRComposition
- Frames (aufsteigend):
  - `stack_1s.xisf`
  - `stack_3s.xisf`
  - `stack_10s.xisf`
  - `stack_30s.xisf`
  - `stack_180s.xisf`
- Mask Binarizing Threshold: 0.85
- Auto Alignment: OFF
- Generate Masks: OFF
- Fit Plane: ON
- Output: `HDR/M13_hdr_raw.xisf`

Hinweis: Das Ergebnis bleibt linear und wirkt zunaechst sehr dunkel. Das ist korrekt.

## Schritt 7 - Hintergrundkorrektur
### A) DBE
- Process > Background Modeling > DynamicBackgroundExtraction
- Bild: `HDR/M13_hdr_raw.xisf`
- Samples in sternfreien Hintergrundbereichen setzen
- Zentrum des Sternhaufens ausnehmen
- Correction: Subtraction

### B) GraXpert (alternativ/ergaenzend)
- Process > GraXpert
- Correction Method: Subtraction
- AI Model: neueste verfuegbare Version
- Auf lineares Bild anwenden

## Schritt 8 - Farb-Kalibrierung (linear)
- Process > ColorCalibration > PhotometricColorCalibration
- Catalog: Gaia DR3
- Limiting Magnitude: 18
- Focal Length: 950 mm
- Aperture: 254 mm

## Schritt 9 - Stretch (linear -> nichtlinear)
Empfohlen: Generalized Hyperbolic Stretch (GHS)
- Script > Utilities > GeneralizedHyperbolicStretch
- Modus: Linked channels
- Moderat und in mehreren Schritten stretchen
- Hintergrund bei ca. 0.10-0.15 halten

Alternative: HistogramTransformation
- Process > IntensityTransformations > HistogramTransformation
- Midtones vorsichtig nach links ziehen

## Schritt 10 - Rauschreduzierung
Im nichtlinearen Zustand (nach Stretch):

- TGVDenoise
  - Edge Protection: 0.001
  - Smoothness: 2.0-4.0
  - Iterations: 200-400
  - Mit Luminanz-Maske

Oder:
- MultiscaleLinearTransform (MLT)
  - Nur Layer 1+2 bearbeiten
  - Threshold: 3.0
  - Amount: 0.7

## Schritt 11 - Sternfeld-Optimierung
### A) StarXTerminator
- Create Starless Image: ON
- Create Stars Image: ON
- Outputs: `M13_starless.xisf` und `M13_stars.xisf`

### B) Recombine
- PixelMath: `$T + M13_stars.xisf`

## Schritt 12 - Lokale Kontrastverstaerkung
- LocalHistogramEqualization
  - Kernel Radius: 64-128
  - Amount: 0.2-0.5
  - Mit Luminanz-Maske

Optional:
- UnsharpMask
  - Radius 2.5
  - Amount 0.4
  - Threshold 0.05

## Schritt 13 - Farbsaettigung
- CurvesTransformation
  - Saturation moderat anheben
  - Rotkanal leicht senken, falls Sterne zu orange wirken

Optional:
- SCNR bei Gruenstich
  - Amount: 0.5
  - Method: Maximum Neutral

## Schritt 14 - Export als PNG
- File > Save As
- Format: PNG
- Bit-Tiefe: 16 Bit (oder 8 Bit fuer Web)
- ICC-Profil: sRGB
- Output: `FINAL/M13_HDR_final.png`

Optional zusaetzlich speichern:
- `FINAL/M13_HDR_final.xisf`

## Zusammenfassung der Reihenfolge
1. WBPP konfigurieren (Lights/Darks/Flats/Biases + RGGB)
2. WBPP ausfuehren (Master + Kalibrierung + Debayer + Registrierung + Integration)
3. 5 integrierte Serien-Stacks pruefen und finalisieren
4. Optional SubframeSelector-Feinschliff, dann Re-Integration
5. 5 finale Stacks fuer HDRComposition bereitstellen
6. HDRComposition -> lineares HDR
7. DBE / GraXpert
8. PhotometricColorCalibration
9. GHS Stretch
10. Rauschreduzierung
11. StarXTerminator
12. LHE / UnsharpMask
13. Curves (Farbe/Saettigung)
14. PNG-Export

## Hinweise / Fallstricke
- HDRComposition erwartet lineare, nicht-gestretchte Inputs.
- Fuer HDR immer die WBPP-Integrationen je Belichtungszeit verwenden, nicht Einzel-Frames.
- Nicht doppelt Hintergrundkorrektur anwenden (DBE und GraXpert uebertreiben vermeiden).
- XISF als Arbeitsformat nutzen, PNG nur fuer den finalen Export.
