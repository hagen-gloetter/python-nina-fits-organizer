# Changelog

All notable changes to this project are documented in this file.

## [Unreleased]

### Added
- Added automated unit tests for core organizer helper functions.
- Added requirements file for reproducible environment setup.
- Added structured changelog tracking using Added/Changed/Fixed/Removed/Breaking Changes sections.

### Changed
- Refactored organizer script to use a robust CLI, pathlib-based paths, and deterministic filename generation.
- Organizer output now uses one object/session folder with frame-type subfolders (LIGHT/DARK/FLAT/BIAS/SNAPSHOT) for PixInsight-friendly import.
- Session folder naming now excludes exposure, so multiple exposure lengths for one session are grouped together.
- Source type SNAPSHOT is now written to target subfolder PROCESSING.
- Target filenames now start with capture date/time (`YYYYMMDD-HHMMSS_...`) to reduce accidental overwrite risk.
- Improved analyzer script with proper CLI behavior and safer numeric parsing.
- Updated .gitignore with Python cache, logs, and test artifacts.
- Updated Windows setup script to valid batch syntax and requirements-driven installs.
- Updated README with setup, usage, development workflow, and limitations.

### Fixed
- Fixed analyzer side effect where analysis executed automatically on import.
- Fixed potential re-processing of already moved FITS files by only scanning capture folders.
- Fixed possible file overwrite collisions by enforcing unique target paths.
- Fixed inconsistent logging handler setup that could duplicate log entries.
- Fixed brittle extraction of numeric suffixes from source filenames.

### Removed
- Removed redundant manual usage printer in organizer in favor of argparse help output.

### Breaking Changes
- Organizer now requires explicit source path and supports optional `--dry-run` flag via argparse-driven CLI.
- Analyzer now requires a FITS file path argument and no longer runs a hardcoded example path.
