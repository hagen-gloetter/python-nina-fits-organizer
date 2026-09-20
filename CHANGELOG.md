# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Added automated unit tests for core organizer helper functions.
- Added requirements file for reproducible environment setup.
- Added structured changelog tracking using Added/Changed/Fixed/Removed/Breaking Changes sections.
- Added content-based duplicate detection (`files_have_identical_content()`, size + SHA-256 hash): if a re-copied source file is byte-for-byte identical to an already-organized target file, the target is overwritten in place instead of creating a numbered duplicate, preventing accidental double-weighted frames in later stacks. Tracked in the run summary as "Ueberschrieben: N identische Duplikate".
- Added OBJECT name canonicalization for Messier/NGC/IC catalog designations (`normalize_object_name()`, `CATALOG_PATTERNS`, `COMMON_NAMES`): naming variants like `"M 31"`, `"m31"`, `"M-31"`, `"Messier 31"` all collapse to the same target folder (`M31`), optionally suffixed with a curated German common name (e.g. `M31-Andromedagalaxie`), preventing the same object from being fragmented across multiple target folders due to inconsistent target naming in the sequencer.
- Added `normalize_existing_target_dir_names()`, run automatically at the start of every real (non-dry-run) pass, to migrate/merge already-organized target folders that still use an older object-name spelling into the current canonical form.
- Added a standalone `hg-remove-duplicates.py` script (with `tests/test_remove_duplicates.py`) that recursively scans a folder for byte-for-byte identical `*.fits`/`*.fit` files (grouped by size + SHA-256 hash, filename irrelevant) and moves every extra copy per group into a `_DUPLICATES_REMOVED/<timestamp>/...` quarantine folder (mirroring the relative path) instead of deleting it; supports `--dry-run` and writes a timestamped log file, consistent with the main organizer.
- Added live progress output to `hg-remove-duplicates.py`: number of files found, how many share a size and need hashing, periodic "X/Y geprueft" progress during hashing, and an explicit console note that the `_DUPLICATES_REMOVED` quarantine folder is always excluded from scanning.

### Changed
- Refactored organizer script to use a robust CLI, pathlib-based paths, and deterministic filename generation.
- Replaced `fits.open()` with `fits.getheader(..., 0)` for significantly faster header-only parsing without loading image data or multi-HDU blocks over slow/network mounts.
- Consolidated multi-pass `rglob()` calls in SeeStar normalization into a single bottom-up `os.walk()` traversal.
- Added visible `[SKIP   ]` console output during runs so progress remains clear even when files are already organized.
- Organizer output now uses one object/session folder with frame-type subfolders (LIGHT/DARK/FLAT/BIAS/SNAPSHOT) for PixInsight-friendly import.
- Session folder naming now excludes exposure, so multiple exposure lengths for one session are grouped together.
- Source type SNAPSHOT is now written to target subfolder PROCESSING.
- Target filenames now start with capture date/time (`YYYYMMDD-HHMMSS_...`) to reduce accidental overwrite risk.
- Improved analyzer script with proper CLI behavior and safer numeric parsing.
- Updated .gitignore with Python cache, logs, and test artifacts.
- Updated Windows setup script to valid batch syntax and requirements-driven installs.
- Updated README with setup, usage, development workflow, and limitations.

### Fixed
- Fixed `normalize_image_type()` silently defaulting unrecognized frames to `LIGHT` (risk of contaminating light stacks with misclassified calibration frames); it now routes them to a visible `UNKNOWN` subfolder instead.
- Fixed already-organized files inside non-capture target subfolders (e.g. `UNKNOWN`, `PROCESSING`) being incorrectly moved back up a directory level on a second run, by consistently recognizing all known target subfolder names via a shared `KNOWN_TARGET_SUBDIRS` set.
- Fixed `remove_empty_directories()` walking and evaluating removal candidates inside ignored trees (`.git`, virtual environments, `PRO`/`FINAL`), which was inconsistent with the ignore rules used for FITS discovery; it now prunes the same folders and is safe/faster to run from a repo root.
- Fixed `find_target_dir_for_leftover_project()` using a raw substring match to find a leftover project's target folder, which risked merging data into an unrelated, only superficially similar target folder (e.g. `M-1` matching `M-13`); matching now requires a whole underscore-delimited name segment.
- Fixed folder restructuring when source folder names did not match the target schema (`YYYY_OBJECT_TELESCOPE...`), ensuring all companion files, `PRO`, `FINAL`, and preview subfolders are completely migrated and non-conforming folders removed.
- Fixed FITS file discovery to scan unnested/unstructured session directories while safely ignoring `PRO`, `FINAL`, and virtual environment folders.
- Fixed `CAMERAID` fallback to check `INSTRUME` in FITS header before falling back to `TELESCOP`.
- Fixed analyzer side effect where analysis executed automatically on import.
- Fixed potential re-processing of already moved FITS files by only scanning capture folders.
- Fixed target folder name duplicating the device id/CAMERAID fallback when TELESCOP already embeds it (e.g. SeeStar `S30 Pro_5915f86f`), so folders are now `YYYY_OBJECT_TELESCOPE` instead of `YYYY_OBJECT_TELESCOPE_TELESCOPE`.
- Fixed `LIGHT_jpg` and `PRO/seestar_stacked` preview/stacked data only ever being migrated for the first session folder of a target group, leaving previews from later sessions behind; these are now merged for every session folder.
- Fixed leftover preview/stacked folders from sessions whose FITS files were already moved by an earlier run never being picked up; they are now matched to their existing target folder by year and object name and merged in.
- Fixed `normalize_see_star_layout` nesting a second `PRO` folder (`PRO/PRO/seestar_stacked`) when re-run over an already-organized `seestar_stacked` directory; added a repair pass that flattens existing `PRO/PRO` folders from earlier runs.
- Fixed issue where decimal parts of temperatures in filenames (`_t29.9375`) were extracted as sequence suffixes, causing repeated renames and infinite uniqueness suffix appending (`_9375_1`).
- Fixed `process_fits_file` calling `ensure_unique_path` before verifying identity with source path.
- Fixed possible file overwrite collisions by enforcing unique target paths.
- Fixed inconsistent logging handler setup that could duplicate log entries.
- Fixed brittle extraction of numeric suffixes from source filenames.

### Removed
- Removed redundant manual usage printer in organizer in favor of argparse help output.

### Breaking Changes
- Organizer now requires explicit source path and supports optional `--dry-run` flag via argparse-driven CLI.
- Analyzer now requires a FITS file path argument and no longer runs a hardcoded example path.
- Target folder names for Messier/NGC/IC objects changed from a dash-separated form (e.g. `M-27`) to the canonical catalog form, optionally with a common name (e.g. `M27-Hantelnebel`); already-organized folders using the old form are automatically migrated/merged on the next real run (not in `--dry-run`).
