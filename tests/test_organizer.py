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
    suffix = mod.derive_suffix_from_filename(Path("LIGHT_frame_0007.fits"))
    assert suffix == "_0007"


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

    expected_folder = tmp_path / "2026_M-66_ASA10_ASI2600MC-Duo"
    assert mod.create_target_directory(tmp_path, first_night) == expected_folder
    assert mod.create_target_directory(tmp_path, second_night) == expected_folder
    assert mod.create_target_directory(tmp_path, next_year) == tmp_path / "2027_M-66_ASA10_ASI2600MC-Duo"


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
    object_dir = tmp_path / "2026_M-66_ASA10_ASI2600MC-Duo"
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
