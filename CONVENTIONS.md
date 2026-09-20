# Entwicklungs-Konventionen für dieses Repository

Diese Datei fasst die Regeln zusammen, die bei Änderungen an
`hg-nina-fits-organizer.py` eingehalten werden sollen. Ziel ist es, Code,
Tests und Dokumentation konsistent zu halten - unabhängig davon, auf welchem
Rechner oder mit welchem Tool das Skript weiterentwickelt wird.

## Bei jeder Änderung an hg-nina-fits-organizer.py IMMER mitpflegen

- [tests/test_organizer.py](tests/test_organizer.py) - passende Tests
  ergänzen/anpassen, danach die Testsuite ausführen (siehe unten)
- [README.md](README.md) - Abschnitte "Features" und "Usage" bei
  Verhaltensänderungen aktualisieren
- [CHANGELOG.md](CHANGELOG.md) - Eintrag unter `## [Unreleased]` in
  passender Kategorie (Added/Changed/Fixed/Removed/Breaking Changes)

## hg-remove-duplicates.py (eigenständiges Skript)

- Findet Duplikate NUR über Dateiinhalt (Größe + SHA-256), Dateiname ist
  irrelevant; behalten wird die Datei mit dem alphabetisch ersten Pfad
- Duplikate werden NIE gelöscht, sondern nach
  `<root>/_DUPLICATES_REMOVED/<Zeitstempel>/<relativer Pfad>/` verschoben
- `_DUPLICATES_REMOVED` wird beim Scannen automatisch ignoriert (Idempotenz)
- Bei Änderungen: [tests/test_remove_duplicates.py](tests/test_remove_duplicates.py)
  und den entsprechenden README-Abschnitt mitpflegen

## Zielstruktur (PixInsight-kompatibel)

Zielordner-Schema: `<JAHR>_<OBJEKT>_<TELESKOP>[_<KAMERA>]`,
z. B. `2026_M27-Hantelnebel_S30-Pro` oder `2025_M51-Whirlpoolgalaxie_ASA10_ASI2600MC-Pro`.

OBJECT wird dabei über `normalize_object_name()` kanonisiert: Messier/NGC/IC-
Bezeichnungen werden unabhängig von Schreibweise (`"M 31"`, `"m31"`, `"M-31"`,
`"Messier 31"`) auf eine feste Form reduziert (`M31`, `NGC7000`, `IC434`, ...)
und bei bekannten Objekten um einen deutschen Eigennamen ergänzt (`M31-Andromedagalaxie`).
Freitext-Namen (Sterne, Kometen, eigene Bezeichnungen) bleiben unverändert.

Darin werden folgende Unterordner angelegt:

- `LIGHT/`, `DARK/`, `FLAT/`, `BIAS/`
- `PROCESSING/` (Ziel für Quelltyp `SNAPSHOT`)
- `UNKNOWN/` (Fallback, falls Bildtyp nicht sicher bestimmbar ist - bewusst
  NICHT `LIGHT`, um Kalibrierdaten nicht versehentlich zu vermischen)
- `PRO/` (inkl. Platzhalter `Processing_Daten_hier.txt`)
- `FINAL/` (inkl. Platzhalter `Fertige_Bilder_hier.txt`)

Wichtige Funktionen (Namen bei Refactorings entsprechend anpassen):

- `normalize_image_type()` - erkennt Bildtyp aus Header, Ordnername oder
  Dateiname; unbekannter Typ -> `"UNKNOWN"`, NIE `"LIGHT"` raten
- `KNOWN_TARGET_SUBDIRS` - alle möglichen Namen von Zielunterordnern; wird
  gebraucht, damit bereits einsortierte Dateien (auch in `UNKNOWN/`,
  `PROCESSING/`) bei einem erneuten Lauf nicht fälschlich eine Ebene nach
  oben verschoben werden
- `iter_source_fits_files()` - scannt auch flache/unstrukturierte Ordner,
  ignoriert `IGNORED_SCAN_FOLDERS`
- `remove_empty_directories()` - muss ebenfalls `IGNORED_SCAN_FOLDERS`
  respektieren (nicht in venv/.git aufräumen)
- `files_have_identical_content()` - Größen- + SHA-256-Vergleich; bei
  Namenskollision im Zielordner entscheidet das, ob überschrieben (echtes
  Duplikat) oder ein `_1`-Suffix vergeben wird (unterschiedlicher Inhalt)
- `normalize_object_name()` / `CATALOG_PATTERNS` / `COMMON_NAMES` -
  kanonisiert Messier/NGC/IC-Bezeichnungen (siehe oben); neue Katalog-
  Präfixe oder Eigennamen hier ergänzen
- `normalize_existing_target_dir_names()` - migriert/merged bereits
  vorhandene Zielordner mit alter Objekt-Schreibweise (z. B. `M-27`) auf
  das aktuelle Schema; läuft automatisch bei jedem Echtlauf
- `create_target_directory()` / `build_target_directory_key()` -
  Zielordnernamen
- `migrate_source_project_dir()` - migriert `PRO`/`FINAL`/`LIGHT_jpg`/lose
  Dateien vom alten Projektordner ins Ziel
- `process_directory()` - Hauptablauf

## Testumgebung

Windows (venv `astro_env_win`):

```powershell
astro_env_win\Scripts\pytest.exe tests
```

macOS/Linux (venv `astro_env` bzw. `astro_env_linux`):

```bash
astro_env/bin/pytest tests
```

Hinweis: `make_venv.bat` ist eine Windows-Batchdatei und muss direkt in
PowerShell/cmd ausgeführt werden (`.\make_venv.bat`), nicht über bash/WSL.
