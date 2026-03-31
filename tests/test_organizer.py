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
