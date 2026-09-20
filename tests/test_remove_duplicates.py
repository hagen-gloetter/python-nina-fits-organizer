from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "hg-remove-duplicates.py"


def load_dedup_module():
    spec = spec_from_file_location("dedup", MODULE_PATH)
    module = module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_compute_file_hash_matches_for_identical_content(tmp_path):
    mod = load_dedup_module()
    file_a = tmp_path / "a.fits"
    file_b = tmp_path / "b.fits"
    file_a.write_bytes(b"same-bytes")
    file_b.write_bytes(b"same-bytes")

    assert mod.compute_file_hash(file_a) == mod.compute_file_hash(file_b)


def test_iter_fits_files_skips_quarantine_and_ignored_folders(tmp_path):
    mod = load_dedup_module()
    (tmp_path / "LIGHT").mkdir()
    keep = tmp_path / "LIGHT" / "frame.fits"
    keep.write_bytes(b"data")

    quarantine = tmp_path / mod.QUARANTINE_DIR_NAME / "run1"
    quarantine.mkdir(parents=True)
    (quarantine / "old.fits").write_bytes(b"old")

    venv_dir = tmp_path / "astro_env_win"
    venv_dir.mkdir()
    (venv_dir / "noise.fits").write_bytes(b"noise")

    result = list(mod.iter_fits_files(tmp_path))

    assert result == [keep]


def test_find_duplicate_groups_groups_by_content_not_name(tmp_path):
    mod = load_dedup_module()
    summary = mod.DuplicateSummary()
    file_a = tmp_path / "a.fits"
    file_b = tmp_path / "renamed_copy.fits"
    file_c = tmp_path / "unique.fits"
    file_a.write_bytes(b"identical")
    file_b.write_bytes(b"identical")
    file_c.write_bytes(b"different")

    groups = mod.find_duplicate_groups([file_a, file_b, file_c], summary)

    assert len(groups) == 1
    assert groups[0] == sorted([file_a, file_b], key=str)


def test_process_directory_quarantines_duplicates_keeping_alphabetically_first(tmp_path):
    mod = load_dedup_module()
    (tmp_path / "LIGHT").mkdir()
    (tmp_path / "sub" / "LIGHT").mkdir(parents=True)
    first = tmp_path / "LIGHT" / "a.fits"
    second = tmp_path / "sub" / "LIGHT" / "b.fits"
    unique = tmp_path / "LIGHT" / "c.fits"
    first.write_bytes(b"same-content")
    second.write_bytes(b"same-content")
    unique.write_bytes(b"unique-content")

    summary = mod.process_directory(tmp_path, dry_run=False)

    assert summary.groups_found == 1
    assert summary.duplicates_quarantined == 1
    assert summary.errors == 0
    # The alphabetically first path is kept in place, untouched.
    assert first.exists()
    assert first.read_bytes() == b"same-content"
    # The other copy was moved into quarantine, not deleted.
    assert not second.exists()
    quarantined_files = list((tmp_path / mod.QUARANTINE_DIR_NAME).rglob("b.fits"))
    assert len(quarantined_files) == 1
    assert quarantined_files[0].read_bytes() == b"same-content"
    # Unrelated unique file is left alone.
    assert unique.exists()


def test_process_directory_dry_run_makes_no_filesystem_changes(tmp_path):
    mod = load_dedup_module()
    (tmp_path / "LIGHT").mkdir()
    (tmp_path / "sub" / "LIGHT").mkdir(parents=True)
    first = tmp_path / "LIGHT" / "a.fits"
    second = tmp_path / "sub" / "LIGHT" / "b.fits"
    first.write_bytes(b"same-content")
    second.write_bytes(b"same-content")

    summary = mod.process_directory(tmp_path, dry_run=True)

    assert summary.groups_found == 1
    assert summary.duplicates_quarantined == 1
    assert first.exists()
    assert second.exists()
    assert not (tmp_path / mod.QUARANTINE_DIR_NAME).exists()


def test_process_directory_rerun_finds_nothing_once_quarantined(tmp_path):
    mod = load_dedup_module()
    (tmp_path / "LIGHT").mkdir()
    (tmp_path / "sub" / "LIGHT").mkdir(parents=True)
    first = tmp_path / "LIGHT" / "a.fits"
    second = tmp_path / "sub" / "LIGHT" / "b.fits"
    first.write_bytes(b"same-content")
    second.write_bytes(b"same-content")

    mod.process_directory(tmp_path, dry_run=False)
    summary_second_run = mod.process_directory(tmp_path, dry_run=False)

    assert summary_second_run.groups_found == 0
    assert summary_second_run.duplicates_quarantined == 0
