from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hg-nina-fits-organizer.py"


def load_organizer_module():
    spec = spec_from_file_location("organizer", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_clean_camera_name_strips_vendor_prefixes():
    mod = load_organizer_module()
    assert mod.clean_camera_name("ZWOptical_ZWO ASI2600MC Pro") == "ASI2600MC-Pro"


def test_clean_string_replaces_invalid_characters():
    mod = load_organizer_module()
    assert mod.clean_string("M 42/Orion:Core") == "M-42-Orion-Core"


def test_derive_suffix_from_filename_handles_sequence_number():
    mod = load_organizer_module()
    assert mod.derive_suffix_from_filename(Path("LIGHT_frame_0007.fits")) == "_0007"
    assert mod.derive_suffix_from_filename(Path("Light_M13_20260808-225456.fit")) == ""
    assert mod.derive_suffix_from_filename(Path("Light_M13_20260808-225456_1.fit")) == "_1"
    # Do not confuse float/integer temperatures with sequence numbers:
    assert mod.derive_suffix_from_filename(
        Path("20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t29.9375.fits")
    ) == ""
    assert mod.derive_suffix_from_filename(
        Path("20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t29.9375_1.fits")
    ) == "_1"
    assert mod.derive_suffix_from_filename(
        Path("20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t-10.5.fits")
    ) == ""
    assert mod.derive_suffix_from_filename(
        Path("20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t20.fits")
    ) == ""


def test_process_fits_file_skips_already_organized_file(tmp_path):
    mod = load_organizer_module()
    target_dir = tmp_path / "2026_V2011-Cygni_S30-Pro"
    light_dir = target_dir / "LIGHT"
    light_dir.mkdir(parents=True)
    
    file_path = light_dir / "20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t29.9375.fits"
    file_path.write_text("dummy", encoding="utf-8")

    header = {
        "OBJECT": "V2011-Cygni",
        "TELESCOP": "S30 Pro_5915f86f",
        "DATE-LOC": "2026-08-11T01:59:39",
        "FOCALLEN": 135,
        "EXPOSURE": 30.0,
        "GAIN": 200,
        "CCD-TEMP": 29.9375,
        "FILTER": "IRCUT",
    }

    was_moved = mod.process_fits_file(file_path, target_dir, header, "LIGHT", dry_run=False)

    assert was_moved is False
    assert file_path.exists()
    assert not (light_dir / "20260811-015939_LIGHT_2026-08-11_V2011-Cygni_S30-Pro_e30.0_g200_IRCUT_t29.9375_1.fits").exists()


def test_ensure_unique_path_appends_counter(tmp_path):
    mod = load_organizer_module()
    occupied = tmp_path / "target.fits"
    occupied.write_text("exists", encoding="utf-8")

    candidate = mod.ensure_unique_path(occupied)

    assert candidate.name == "target_1.fits"
    assert not candidate.exists()


def test_create_target_directory_groups_dates_under_year_object_telescope_camera(tmp_path):
    mod = load_organizer_module()
    first_night = {
        "OBJECT": "M-66",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Duo",
        "DATE-LOC": "2026-04-07T22:00:00",
    }
    second_night = {
        "OBJECT": "M-66",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Duo",
        "DATE-LOC": "2026-04-17T22:00:00",
    }
    next_year = {
        "OBJECT": "M-66",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Duo",
        "DATE-LOC": "2027-04-17T22:00:00",
    }

    expected_folder = tmp_path / "2026_M66_ASA10_ASI2600MC-Duo"
    assert mod.create_target_directory(tmp_path, first_night) == expected_folder
    assert mod.create_target_directory(tmp_path, second_night) == expected_folder
    assert mod.create_target_directory(tmp_path, next_year) == tmp_path / "2027_M66_ASA10_ASI2600MC-Duo"


def test_remove_empty_directories_removes_nested_empty_folders(tmp_path):
    mod = load_organizer_module()
    empty_parent = tmp_path / "empty-parent"
    empty_child = empty_parent / "empty-child"
    empty_child.mkdir(parents=True)
    non_empty = tmp_path / "non-empty"
    non_empty.mkdir()
    (non_empty / "keep.txt").write_text("keep", encoding="utf-8")

    removed = mod.remove_empty_directories(tmp_path, dry_run=False)

    assert removed == 2
    assert not empty_parent.exists()
    assert non_empty.exists()


def test_ensure_project_structure_creates_pro_and_final_in_target_dir(tmp_path):
    mod = load_organizer_module()
    object_dir = tmp_path / "2026_M-66_ASA10_ASA2600MC-Duo"
    object_dir.mkdir(parents=True)

    created = mod.ensure_project_structure(object_dir)

    assert created == 2
    assert (object_dir / "PRO").is_dir()
    assert (object_dir / "FINAL").is_dir()
    assert (object_dir / "PRO" / "Processing_Daten_hier.txt").exists()
    assert not (object_dir / "PRO" / "Fertige_Bilder_hier.txt").exists()
    assert (object_dir / "FINAL" / "Fertige_Bilder_hier.txt").exists()
    assert not (object_dir / "FINAL" / "Processing_Daten_hier.txt").exists()
    assert not (tmp_path / "LIGHT").exists()


def test_normalize_see_star_layout_handles_lights_and_stacked_dirs(tmp_path):
    mod = load_organizer_module()
    source_dir = tmp_path / "see_star_session"
    source_dir.mkdir()
    nested = source_dir / "nested_object"
    nested.mkdir()
    (nested / "lights").mkdir()
    (nested / "lights_jpg").mkdir()
    stacked_dir = nested / "seestar_stacked"
    stacked_dir.mkdir()
    (stacked_dir / "stacked.fit").write_text("stack", encoding="utf-8")

    mod.normalize_see_star_layout(source_dir)

    assert (nested / "LIGHT").is_dir()
    assert (nested / "LIGHT_jpg").is_dir()
    assert (nested / "PRO").is_dir()
    assert (nested / "PRO" / "seestar_stacked").is_dir()
    assert (nested / "PRO" / "seestar_stacked" / "stacked.fit").exists()


def test_iter_source_fits_files_accepts_fit_extension(tmp_path):
    mod = load_organizer_module()
    light_dir = tmp_path / "LIGHT"
    light_dir.mkdir()
    file_path = light_dir / "sample.fit"
    file_path.write_text("data", encoding="utf-8")

    result = list(mod.iter_source_fits_files(tmp_path))

    assert result == [file_path]


def test_build_target_filename_uses_see_star_fallback_metadata():
    mod = load_organizer_module()
    source_path = Path("Light_M 13_30.0s_IRCUT_20260808-225456.fit")
    header = {
        "OBJECT": "M 13",
        "IMAGETYP": "Light",
        "TELESCOP": "S30 Pro_5915f86f",
        "EXPOSURE": 30.0,
        "FILTER": "IRCUT",
        "GAIN": 200,
        "CCD-TEMP": 26.4375,
    }

    result = mod.build_target_filename(source_path, header, "LIGHT")

    assert "20260808-225456_LIGHT_2026-08-08_M13-Herkuleshaufen_S30-Pro_e30.0_g200_IRCUT_t26.4375.fits" in result
    assert mod.count_unknown_fields(header) == 0


def test_get_header_value_uses_camera_fallback_without_duplicate_telescope_suffix():
    mod = load_organizer_module()
    header = {"TELESCOP": "S30 Pro_5915f86f"}

    value = mod.get_header_value(header, "CAMERAID")

    assert value == "S30-Pro"


def test_get_header_value_strips_device_id_suffix_from_telescope():
    mod = load_organizer_module()
    header = {"TELESCOP": "S30 Pro_5915f86f"}

    assert mod.get_header_value(header, "TELESCOP") == "S30-Pro"


def test_create_target_directory_does_not_duplicate_seestar_device_id(tmp_path):
    mod = load_organizer_module()
    header = {
        "OBJECT": "M-31",
        "TELESCOP": "S30 Pro_5915f86f",
        "DATE-LOC": "2026-04-07T22:00:00",
    }

    result = mod.create_target_directory(tmp_path, header)

    assert result == tmp_path / "2026_M31-Andromedagalaxie_S30-Pro"


def test_move_preview_folder_to_target_merges_multiple_sessions(tmp_path):
    mod = load_organizer_module()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    session_one = tmp_path / "session_one"
    (session_one / "LIGHT_jpg").mkdir(parents=True)
    (session_one / "LIGHT_jpg" / "frame1.jpg").write_text("a", encoding="utf-8")

    session_two = tmp_path / "session_two"
    (session_two / "LIGHT_jpg").mkdir(parents=True)
    (session_two / "LIGHT_jpg" / "frame2.jpg").write_text("b", encoding="utf-8")

    mod.move_preview_folder_to_target(session_one, target_dir)
    mod.move_preview_folder_to_target(session_two, target_dir)

    merged = target_dir / "LIGHT_jpg"
    assert (merged / "frame1.jpg").exists()
    assert (merged / "frame2.jpg").exists()
    assert not session_one.joinpath("LIGHT_jpg").exists()
    assert not session_two.joinpath("LIGHT_jpg").exists()


def test_move_stacked_folder_to_target_merges_multiple_sessions(tmp_path):
    mod = load_organizer_module()
    target_dir = tmp_path / "target"
    target_dir.mkdir()

    session_one = tmp_path / "session_one" / "PRO" / "seestar_stacked"
    session_one.mkdir(parents=True)
    (session_one / "stack1.fit").write_text("a", encoding="utf-8")

    session_two = tmp_path / "session_two" / "PRO" / "seestar_stacked"
    session_two.mkdir(parents=True)
    (session_two / "stack2.fit").write_text("b", encoding="utf-8")

    mod.move_stacked_folder_to_target(tmp_path / "session_one", target_dir)
    mod.move_stacked_folder_to_target(tmp_path / "session_two", target_dir)

    merged = target_dir / "PRO" / "seestar_stacked"
    assert (merged / "stack1.fit").exists()
    assert (merged / "stack2.fit").exists()
    assert not (tmp_path / "session_one" / "PRO" / "seestar_stacked").exists()
    assert not (tmp_path / "session_two" / "PRO" / "seestar_stacked").exists()


def test_repair_nested_pro_folders_flattens_double_pro(tmp_path):
    mod = load_organizer_module()
    nested = tmp_path / "session" / "PRO" / "PRO" / "seestar_stacked"
    nested.mkdir(parents=True)
    (nested / "stack.fit").write_text("data", encoding="utf-8")

    mod.repair_nested_pro_folders(tmp_path)

    pro_dir = tmp_path / "session" / "PRO"
    assert (pro_dir / "seestar_stacked" / "stack.fit").exists()
    assert not (pro_dir / "PRO").exists()


def test_normalize_see_star_layout_does_not_nest_pro_when_already_organized(tmp_path):
    mod = load_organizer_module()
    stacked = tmp_path / "session" / "PRO" / "seestar_stacked"
    stacked.mkdir(parents=True)
    (stacked / "stack.fit").write_text("data", encoding="utf-8")

    mod.normalize_see_star_layout(tmp_path)

    pro_dir = tmp_path / "session" / "PRO"
    assert (pro_dir / "seestar_stacked" / "stack.fit").exists()
    assert not (pro_dir / "PRO").exists()


def test_find_target_dir_for_leftover_project_matches_by_year_and_object(tmp_path):
    mod = load_organizer_module()
    target_dir = tmp_path / "2026_M31-Andromedagalaxie_S30-Pro"
    target_dir.mkdir()

    project_dir = tmp_path / "M31-2026-08-10"
    preview_dir = project_dir / "LIGHT_jpg"
    preview_dir.mkdir(parents=True)
    (preview_dir / "Light_M 31_20.0s_IRCUT_20260810-005446.jpg").write_text("x", encoding="utf-8")

    result = mod.find_target_dir_for_leftover_project(project_dir, [target_dir])

    assert result == target_dir


def test_iter_leftover_project_dirs_finds_orphaned_preview_and_stacked(tmp_path):
    mod = load_organizer_module()
    (tmp_path / "2026_M-31_S30-Pro").mkdir()

    orphan_preview = tmp_path / "M31-2026-08-10" / "LIGHT_jpg"
    orphan_preview.mkdir(parents=True)

    orphan_stacked = tmp_path / "M31-2026-08-14" / "PRO" / "seestar_stacked"
    orphan_stacked.mkdir(parents=True)

    result = {p.name for p in mod.iter_leftover_project_dirs(tmp_path)}

    assert result == {"M31-2026-08-10", "M31-2026-08-14"}


def test_iter_source_fits_files_finds_files_in_unstructured_folders(tmp_path):
    mod = load_organizer_module()
    session_dir = tmp_path / "2025-08-10_M27"
    session_dir.mkdir()
    direct_fits = session_dir / "capture_001.fits"
    direct_fits.write_text("dummy", encoding="utf-8")

    result = list(mod.iter_source_fits_files(tmp_path))

    assert direct_fits in result


def test_get_header_value_falls_back_to_instrume_for_camera():
    mod = load_organizer_module()
    header = {"INSTRUME": "ZWO ASI2600MC Pro", "TELESCOP": "ASA10"}

    assert mod.get_header_value(header, "CAMERAID") == "ASI2600MC-Pro"


def test_migrate_source_project_dir_moves_companion_files_and_folders(tmp_path):
    mod = load_organizer_module()
    source_proj = tmp_path / "M-27_S30-Pro"
    source_proj.mkdir()
    (source_proj / "PRO").mkdir()
    (source_proj / "PRO" / "Processing_Daten_hier.txt").write_text("", encoding="utf-8")
    (source_proj / "PRO" / "notes.txt").write_text("important", encoding="utf-8")
    (source_proj / "FINAL").mkdir()
    (source_proj / "FINAL" / "Fertige_Bilder_hier.txt").write_text("", encoding="utf-8")
    (source_proj / "FINAL" / "final.jpg").write_text("img", encoding="utf-8")
    (source_proj / "session_notes.txt").write_text("log", encoding="utf-8")

    target_dir = tmp_path / "2026_M-27_S30-Pro"
    mod.ensure_project_structure(target_dir)

    mod.migrate_source_project_dir(source_proj, target_dir, dry_run=False)

    assert (target_dir / "PRO" / "notes.txt").read_text(encoding="utf-8") == "important"
    assert (target_dir / "FINAL" / "final.jpg").read_text(encoding="utf-8") == "img"
    assert (target_dir / "session_notes.txt").read_text(encoding="utf-8") == "log"
    assert (target_dir / "PRO" / "Processing_Daten_hier.txt").exists()
    assert not (target_dir / "PRO" / "Processing_Daten_hier_1.txt").exists()


def test_process_directory_restructures_non_conforming_folder(tmp_path, monkeypatch):
    mod = load_organizer_module()
    # Create non-conforming source folder
    old_folder = tmp_path / "M-27_S30-Pro"
    old_folder.mkdir()
    (old_folder / "LIGHT").mkdir()
    raw_fits = old_folder / "LIGHT" / "frame_0001.fits"
    raw_fits.write_text("fits_content", encoding="utf-8")
    (old_folder / "PRO").mkdir()
    (old_folder / "PRO" / "Processing_Daten_hier.txt").write_text("", encoding="utf-8")
    (old_folder / "PRO" / "user_project.xisf").write_text("pixinsight", encoding="utf-8")

    # Mock fits.getheader
    fake_header = {
        "OBJECT": "M-27",
        "TELESCOP": "S30 Pro_5915f86f",
        "DATE-LOC": "2026-08-08T22:54:56",
        "IMAGETYP": "LIGHT",
        "EXPOSURE": 30.0,
        "GAIN": 200,
        "CCD-TEMP": 26.4375,
        "FILTER": "IRCUT",
        "FOCALLEN": 135,
    }
    monkeypatch.setattr(mod.fits, "getheader", lambda path, idx: fake_header)

    summary = mod.process_directory(tmp_path, dry_run=False)

    expected_target = tmp_path / "2026_M27-Hantelnebel_S30-Pro"
    assert summary.moved == 1
    assert not old_folder.exists()
    assert expected_target.is_dir()
    assert (expected_target / "LIGHT").is_dir()
    assert (expected_target / "PRO" / "user_project.xisf").exists()
    assert (expected_target / "PRO" / "Processing_Daten_hier.txt").exists()
    assert (expected_target / "FINAL" / "Fertige_Bilder_hier.txt").exists()


def test_normalize_image_type_resolves_various_formats():
    mod = load_organizer_module()
    assert mod.normalize_image_type("LIGHT FRAME", Path("test.fits")) == "LIGHT"
    assert mod.normalize_image_type("Dark", Path("test.fits")) == "DARK"
    assert mod.normalize_image_type("Flat Field", Path("test.fits")) == "FLAT"
    assert mod.normalize_image_type("BIAS FRAME", Path("test.fits")) == "BIAS"
    assert mod.normalize_image_type("OFFSET", Path("test.fits")) == "BIAS"
    assert mod.normalize_image_type("Snapshot", Path("test.fits")) == "SNAPSHOT"
    assert mod.normalize_image_type("", Path("some_path/FLAT/frame.fits")) == "FLAT"
    assert mod.normalize_image_type("", Path("some_path/Dark_001.fits")) == "DARK"


def test_process_directory_creates_pixinsight_folders_from_flat_source(tmp_path, monkeypatch):
    mod = load_organizer_module()
    # FITS files directly in unorganized night directory
    session_dir = tmp_path / "2025-06-14"
    session_dir.mkdir()
    (session_dir / "light_001.fits").write_text("light", encoding="utf-8")
    (session_dir / "dark_001.fits").write_text("dark", encoding="utf-8")
    (session_dir / "flat_001.fits").write_text("flat", encoding="utf-8")
    (session_dir / "bias_001.fits").write_text("bias", encoding="utf-8")

    def mock_getheader(path, idx):
        name = Path(path).name
        if "light" in name:
            return {
                "OBJECT": "M-51",
                "TELESCOP": "ASA10",
                "CAMERAID": "ASI2600MC-Pro",
                "DATE-LOC": "2025-06-14T23:00:00",
                "IMAGETYP": "LIGHT",
                "EXPOSURE": 180.0,
                "GAIN": 200,
                "CCD-TEMP": -10.0,
                "FILTER": "Slot 1",
            }
        elif "dark" in name:
            return {
                "OBJECT": "M-51",
                "TELESCOP": "ASA10",
                "CAMERAID": "ASI2600MC-Pro",
                "DATE-LOC": "2025-06-14T23:30:00",
                "IMAGETYP": "DARK",
                "EXPOSURE": 180.0,
                "GAIN": 200,
                "CCD-TEMP": -10.0,
            }
        elif "flat" in name:
            return {
                "OBJECT": "M-51",
                "TELESCOP": "ASA10",
                "CAMERAID": "ASI2600MC-Pro",
                "DATE-LOC": "2025-06-14T23:45:00",
                "IMAGETYP": "FLAT",
                "EXPOSURE": 1.0,
                "GAIN": 200,
                "CCD-TEMP": -10.0,
                "FILTER": "Slot 1",
            }
        else:
            return {
                "OBJECT": "M-51",
                "TELESCOP": "ASA10",
                "CAMERAID": "ASI2600MC-Pro",
                "DATE-LOC": "2025-06-14T23:55:00",
                "IMAGETYP": "BIAS",
                "EXPOSURE": 0.001,
                "GAIN": 200,
                "CCD-TEMP": -10.0,
            }

    monkeypatch.setattr(mod.fits, "getheader", mock_getheader)

    summary = mod.process_directory(tmp_path, dry_run=False)

    target_dir = tmp_path / "2025_M51-Whirlpoolgalaxie_ASA10_ASI2600MC-Pro"
    assert summary.moved == 4
    assert target_dir.is_dir()
    assert (target_dir / "LIGHT").is_dir()
    assert (target_dir / "DARK").is_dir()
    assert (target_dir / "FLAT").is_dir()
    assert (target_dir / "BIAS").is_dir()
    assert (target_dir / "PRO" / "Processing_Daten_hier.txt").exists()
    assert (target_dir / "FINAL" / "Fertige_Bilder_hier.txt").exists()
    assert not session_dir.exists()


def test_normalize_image_type_falls_back_to_unknown_not_light():
    mod = load_organizer_module()
    # No header hint, no folder hint, no filename hint -> must not silently become LIGHT.
    assert mod.normalize_image_type("", Path("some_path/session/frame_abc.fits")) == "UNKNOWN"


def test_process_directory_does_not_relocate_files_out_of_unknown_folder_on_rerun(tmp_path, monkeypatch):
    """Regression test: files already organized into a non-capture-dir subfolder (e.g. UNKNOWN)
    must not be moved back up a level when the organizer is run a second time."""
    mod = load_organizer_module()

    fake_header = {
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Pro",
        "DATE-LOC": "2026-01-01T22:00:00",
    }
    monkeypatch.setattr(mod.fits, "getheader", lambda path, idx: fake_header)

    target_dir = tmp_path / "2026_UNKNOWN_ASA10_ASI2600MC-Pro"
    unknown_dir = target_dir / "UNKNOWN"
    unknown_dir.mkdir(parents=True)
    existing_file = unknown_dir / "20260101-220000_UNKNOWN_2026-01-01_UNKNOWN_ASI2600MC-Pro_eN-A_gN-A_NOFILTER_tN-A.fits"
    existing_file.write_text("data", encoding="utf-8")

    mod.process_directory(tmp_path, dry_run=False)

    assert existing_file.exists()
    assert existing_file.parent == unknown_dir


def test_find_target_dir_for_leftover_project_rejects_loose_substring_match(tmp_path):
    mod = load_organizer_module()
    target_a = tmp_path / "2026_M-1_ASA10"
    target_b = tmp_path / "2026_M-13_ASA10"
    target_a.mkdir()
    target_b.mkdir()

    project_dir = tmp_path / "M-1"
    project_dir.mkdir()
    (project_dir / "PRO").mkdir()

    # "M-1" is a substring of "M-13"'s cleaned name; must not match on that basis alone.
    result = mod.find_target_dir_for_leftover_project(project_dir, [target_a, target_b])

    assert result == target_a


def test_remove_empty_directories_skips_ignored_folders(tmp_path):
    mod = load_organizer_module()
    ignored_empty = tmp_path / "astro_env_win" / "empty_subdir"
    ignored_empty.mkdir(parents=True)
    real_empty = tmp_path / "empty_real"
    real_empty.mkdir()

    removed = mod.remove_empty_directories(tmp_path, dry_run=False)

    assert removed == 1
    assert not real_empty.exists()
    assert ignored_empty.exists()


def test_reimporting_a_fresh_copy_of_original_raw_file_creates_numbered_duplicate_not_overwrite(tmp_path, monkeypatch):
    """Simulates: raw files copied to a temp folder, organized once, then someone re-copies the
    same original (pre-rename) raw files into the temp folder and runs the organizer again."""
    mod = load_organizer_module()

    fake_header = {
        "OBJECT": "M-51",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Pro",
        "DATE-LOC": "2025-06-14T23:00:00",
        "IMAGETYP": "LIGHT",
        "EXPOSURE": 180.0,
        "GAIN": 200,
        "CCD-TEMP": -9.8,
        "FILTER": "Slot 1",
    }
    monkeypatch.setattr(mod.fits, "getheader", lambda path, idx: fake_header)

    raw_name = "2025-06-14_00-14-59_Slot1_0007.fits"
    light_dir = tmp_path / "LIGHT"
    light_dir.mkdir()
    (light_dir / raw_name).write_text("original-bytes", encoding="utf-8")

    mod.process_directory(tmp_path, dry_run=False)

    target_dir = tmp_path / "2025_M51-Whirlpoolgalaxie_ASA10_ASI2600MC-Pro"
    first_copy = next((target_dir / "LIGHT").glob("*.fits"))
    assert first_copy.read_text(encoding="utf-8") == "original-bytes"

    # Someone else re-copies the same original raw file into the temp folder and reruns.
    light_dir.mkdir(parents=True, exist_ok=True)
    (light_dir / raw_name).write_text("second-copy-bytes", encoding="utf-8")

    mod.process_directory(tmp_path, dry_run=False)

    fits_files = sorted((target_dir / "LIGHT").glob("*.fits"))
    assert len(fits_files) == 2
    # The original file must not be overwritten/lost.
    assert first_copy.exists()
    assert first_copy.read_text(encoding="utf-8") == "original-bytes"
    # The re-copied file must exist as a distinct, numbered duplicate.
    duplicate = [f for f in fits_files if f != first_copy][0]
    assert duplicate.name != first_copy.name
    assert duplicate.read_text(encoding="utf-8") == "second-copy-bytes"


def test_files_have_identical_content_detects_true_duplicates(tmp_path):
    mod = load_organizer_module()
    file_a = tmp_path / "a.fits"
    file_b = tmp_path / "b.fits"
    file_c = tmp_path / "c.fits"
    file_a.write_bytes(b"same-bytes")
    file_b.write_bytes(b"same-bytes")
    file_c.write_bytes(b"different-bytes")

    assert mod.files_have_identical_content(file_a, file_b) is True
    assert mod.files_have_identical_content(file_a, file_c) is False


def test_reimporting_identical_content_overwrites_instead_of_duplicating(tmp_path, monkeypatch):
    """If the same original raw file (byte-for-byte identical) is re-copied into the source
    folder, the already-organized target file is overwritten in place, not duplicated."""
    mod = load_organizer_module()

    fake_header = {
        "OBJECT": "M-51",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Pro",
        "DATE-LOC": "2025-06-14T23:00:00",
        "IMAGETYP": "LIGHT",
        "EXPOSURE": 180.0,
        "GAIN": 200,
        "CCD-TEMP": -9.8,
        "FILTER": "Slot 1",
    }
    monkeypatch.setattr(mod.fits, "getheader", lambda path, idx: fake_header)

    raw_name = "2025-06-14_00-14-59_Slot1_0007.fits"
    light_dir = tmp_path / "LIGHT"
    light_dir.mkdir()
    (light_dir / raw_name).write_text("identical-bytes", encoding="utf-8")

    summary1 = mod.process_directory(tmp_path, dry_run=False)
    assert summary1.duplicates_overwritten == 0

    target_dir = tmp_path / "2025_M51-Whirlpoolgalaxie_ASA10_ASI2600MC-Pro"
    first_copy = next((target_dir / "LIGHT").glob("*.fits"))

    # Someone re-copies the exact same raw file (byte-for-byte) into the source folder.
    light_dir.mkdir(parents=True, exist_ok=True)
    (light_dir / raw_name).write_text("identical-bytes", encoding="utf-8")

    summary2 = mod.process_directory(tmp_path, dry_run=False)

    fits_files = sorted((target_dir / "LIGHT").glob("*.fits"))
    assert len(fits_files) == 1
    assert fits_files[0] == first_copy
    assert fits_files[0].read_text(encoding="utf-8") == "identical-bytes"
    assert summary2.duplicates_overwritten == 1


def test_reimporting_identical_content_in_dry_run_makes_no_changes(tmp_path, monkeypatch):
    mod = load_organizer_module()

    fake_header = {
        "OBJECT": "M-51",
        "TELESCOP": "ASA10",
        "CAMERAID": "ASI2600MC-Pro",
        "DATE-LOC": "2025-06-14T23:00:00",
        "IMAGETYP": "LIGHT",
        "EXPOSURE": 180.0,
        "GAIN": 200,
        "CCD-TEMP": -9.8,
        "FILTER": "Slot 1",
    }
    monkeypatch.setattr(mod.fits, "getheader", lambda path, idx: fake_header)

    raw_name = "2025-06-14_00-14-59_Slot1_0007.fits"
    light_dir = tmp_path / "LIGHT"
    light_dir.mkdir()
    (light_dir / raw_name).write_text("identical-bytes", encoding="utf-8")
    mod.process_directory(tmp_path, dry_run=False)

    light_dir.mkdir(parents=True, exist_ok=True)
    (light_dir / raw_name).write_text("identical-bytes", encoding="utf-8")

    summary = mod.process_directory(tmp_path, dry_run=True)

    assert summary.duplicates_overwritten == 1
    # Dry-run must not touch the filesystem: the re-copied source file is still present.
    assert (light_dir / raw_name).exists()


def test_normalize_object_name_canonicalizes_messier_ngc_ic_variants():
    mod = load_organizer_module()
    assert mod.normalize_object_name("M 31") == "M31-Andromedagalaxie"
    assert mod.normalize_object_name("m31") == "M31-Andromedagalaxie"
    assert mod.normalize_object_name("M-31") == "M31-Andromedagalaxie"
    assert mod.normalize_object_name("Messier 31") == "M31-Andromedagalaxie"
    # No curated common name -> bare catalog id, but still normalized (no dash, no leading zero).
    assert mod.normalize_object_name("M 66") == "M66"
    assert mod.normalize_object_name("M066") == "M66"
    assert mod.normalize_object_name("ngc 7000") == "NGC7000-Nordamerikanebel"
    assert mod.normalize_object_name("NGC-7000") == "NGC7000-Nordamerikanebel"
    assert mod.normalize_object_name("ic 434") == "IC434-Pferdekopfnebel"
    # Free-text targets (stars, comets, custom names) are left untouched.
    assert mod.normalize_object_name("V2011-Cygni") == "V2011-Cygni"
    assert mod.normalize_object_name("") == "UNKNOWN"


def test_normalize_existing_target_dir_names_migrates_old_dash_style_object_names(tmp_path):
    mod = load_organizer_module()
    old_dir = tmp_path / "2026_M-31_S30-Pro"
    (old_dir / "LIGHT").mkdir(parents=True)
    (old_dir / "LIGHT" / "frame.fits").write_text("data", encoding="utf-8")

    mod.normalize_existing_target_dir_names(tmp_path)

    new_dir = tmp_path / "2026_M31-Andromedagalaxie_S30-Pro"
    assert new_dir.is_dir()
    assert (new_dir / "LIGHT" / "frame.fits").exists()
    assert not old_dir.exists()


def test_normalize_existing_target_dir_names_merges_into_existing_new_style_folder(tmp_path):
    mod = load_organizer_module()
    old_dir = tmp_path / "2026_M-27_S30-Pro"
    (old_dir / "LIGHT").mkdir(parents=True)
    (old_dir / "LIGHT" / "old.fits").write_text("old", encoding="utf-8")

    new_dir = tmp_path / "2026_M27-Hantelnebel_S30-Pro"
    (new_dir / "LIGHT").mkdir(parents=True)
    (new_dir / "LIGHT" / "new.fits").write_text("new", encoding="utf-8")

    mod.normalize_existing_target_dir_names(tmp_path)

    assert not old_dir.exists()
    assert (new_dir / "LIGHT" / "old.fits").exists()
    assert (new_dir / "LIGHT" / "new.fits").exists()
