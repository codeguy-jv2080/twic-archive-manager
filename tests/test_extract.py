from pathlib import Path
import zipfile

import pytest

from app.database import create_profile, initialize_database
from app.services.archive import ArchiveLayout
from app.services.archive_lock import ArchiveBusy, archive_operation
from app.services.sync import ConfigurationError, ExtractResult, extract_profile


@pytest.fixture(autouse=True)
def isolated_local_operation(tmp_path, monkeypatch):
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")

    def forbidden(*args, **kwargs):
        pytest.fail("Manual extraction must not download, inspect issue selections, or combine")

    for target in (
        "app.services.sync.download_file",
        "app.services.sync.fetch_latest_issue",
        "app.services.sync.selection_from_profile",
        "app.services.sync.combine_extracted_pgns",
        "app.services.archive.urlopen",
        "app.services.catalog.urlopen",
    ):
        monkeypatch.setattr(target, forbidden)


@pytest.fixture
def profile(tmp_path):
    return {
        "name": "Local archives",
        "archive_root": str(tmp_path / "archive"),
        "download_pgn": True,
        "download_cbv": True,
        "extract_archives": False,
        "keep_zip_files": True,
        "combine_after_sync": True,
        "default_selection_mode": "latest",
        "default_selection_value": "invalid selection is irrelevant",
    }


def downloaded_zip(layout, issue, archive_format="pgn", *, filename=None, content=b"game"):
    suffix = "g" if archive_format == "pgn" else "c6"
    path = layout.downloads(archive_format) / (filename or f"twic{issue}{suffix}.zip")
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(f"twic{issue}.{archive_format}", content)
    return path


def test_extracts_existing_pgn_and_cbv_into_flat_folders_without_sync_or_combine(profile):
    layout = ArchiveLayout.create(profile["archive_root"])
    pgn = downloaded_zip(layout, 970, content=b"pgn content")
    cbv = downloaded_zip(layout, 970, "cbv", content=b"cbv content")
    events = []

    result = extract_profile(profile, on_event=events.append)

    assert result == ExtractResult(profile_name=profile["name"], total=2, extracted=2)
    assert (layout.extracted_root("pgn") / "twic970.pgn").read_bytes() == b"pgn content"
    assert (layout.extracted_root("cbv") / "twic970.cbv").read_bytes() == b"cbv content"
    assert not any(path.is_dir() for path in layout.extracted_root("pgn").iterdir())
    assert pgn.exists() and cbv.exists()
    assert not layout.combined_pgn_path.exists()
    assert [(event.issue_number, event.archive_format) for event in events] == [
        (970, "pgn"), (970, "cbv"),
    ]
    assert all(event.kind == "extract" and event.total == 2 for event in events)


def test_extracts_only_the_named_saved_setups_archive(tmp_path):
    initialize_database()
    selected = create_profile(name="Selected", archive_root=str(tmp_path / "selected"))
    other = create_profile(name="Other", archive_root=str(tmp_path / "other"))
    selected_layout = ArchiveLayout.create(selected["archive_root"])
    other_layout = ArchiveLayout.create(other["archive_root"])
    downloaded_zip(selected_layout, 970)
    other_zip = downloaded_zip(other_layout, 971)

    result = extract_profile("Selected")

    assert result.profile_name == "Selected" and result.extracted == 1
    assert (selected_layout.extracted_root("pgn") / "twic970.pgn").exists()
    assert not list(other_layout.extracted_root("pgn").iterdir())
    assert other_zip.exists()


@pytest.mark.parametrize("archive_format", ["pgn", "cbv"])
def test_respects_enabled_download_formats(profile, archive_format):
    layout = ArchiveLayout.create(profile["archive_root"])
    for candidate in ("pgn", "cbv"):
        profile[f"download_{candidate}"] = candidate == archive_format
        downloaded_zip(layout, 970, candidate)

    result = extract_profile(profile)

    assert result.total == result.extracted == 1
    for candidate in ("pgn", "cbv"):
        assert bool(list(layout.extracted_root(candidate).iterdir())) == (candidate == archive_format)


@pytest.mark.parametrize("keep_zips", [True, False])
def test_removes_zips_only_when_keep_zips_is_off_and_preserves_existing_extractions(profile, keep_zips):
    profile["keep_zip_files"] = keep_zips
    layout = ArchiveLayout.create(profile["archive_root"])
    existing = layout.extracted_root("pgn") / "twic970.pgn"
    existing.write_bytes(b"Existing edited PGN must stay untouched")
    before = existing.stat().st_mtime_ns
    old_zip = downloaded_zip(layout, 970, content=b"Do not overwrite existing PGN")
    new_zip = downloaded_zip(layout, 971, content=b"New PGN")

    result = extract_profile(profile)

    assert result.total == 2 and result.extracted == 1 and result.skipped == 1
    assert not result.failures
    assert existing.read_bytes() == b"Existing edited PGN must stay untouched"
    assert existing.stat().st_mtime_ns == before
    assert (layout.extracted_root("pgn") / "twic971.pgn").read_bytes() == b"New PGN"
    assert old_zip.exists() == new_zip.exists() == keep_zips


def test_invalid_zip_remains_and_next_zip_extracts_with_a_visible_failure(profile):
    profile["keep_zip_files"] = False
    layout = ArchiveLayout.create(profile["archive_root"])
    broken = layout.downloads("pgn") / "twic970g.zip"
    broken.write_bytes(b"not a ZIP")
    valid = downloaded_zip(layout, 971)
    events = []

    result = extract_profile(profile, on_event=events.append)

    assert result.total == 2 and result.extracted == 1 and len(result.failures) == 1
    assert "TWIC 970 PGN" in result.failures[0]
    assert any(event.kind == "failure" and event.message == result.failures[0] for event in events)
    assert broken.read_bytes() == b"not a ZIP" and not valid.exists()
    assert (layout.extracted_root("pgn") / "twic971.pgn").exists()
    with archive_operation(layout.root):
        pass  # Per-file failures must not leave the archive locked.


def test_ignores_non_twic_files_and_subfolders_and_accepts_uppercase_zip(profile):
    layout = ArchiveLayout.create(profile["archive_root"])
    for filename in ("unrelated.zip", "twic-no-number.zip", "twic0g.zip", "twic970g.txt"):
        (layout.downloads("pgn") / filename).write_bytes(b"Leave untouched")
    nested = layout.downloads("pgn") / "twic971g.zip"
    nested.mkdir()
    (nested / "twic972g.zip").write_bytes(b"Do not descend into subfolders")
    downloaded_zip(layout, 973, filename="TWIC973G.ZIP")

    result = extract_profile(profile)

    assert result.total == result.extracted == 1 and not result.failures
    assert [path.name for path in layout.extracted_root("pgn").iterdir()] == ["twic973.pgn"]
    assert (nested / "twic972g.zip").read_bytes() == b"Do not descend into subfolders"


def test_empty_download_folders_return_zero_without_a_network_lookup(profile):
    assert extract_profile(profile) == ExtractResult(profile_name=profile["name"])


def test_cancellation_stops_before_the_next_zip(profile):
    layout = ArchiveLayout.create(profile["archive_root"])
    downloaded_zip(layout, 970)
    second_zip = downloaded_zip(layout, 971)
    first_output = layout.extracted_root("pgn") / "twic970.pgn"
    events = []

    result = extract_profile(profile, is_cancelled=first_output.exists, on_event=events.append)

    assert result.cancelled and result.total == 2 and result.extracted == 1
    assert second_zip.exists() and not (layout.extracted_root("pgn") / "twic971.pgn").exists()
    assert events[-1].kind == "canceled" and events[-1].completed == 1
    with archive_operation(layout.root):
        pass


def test_extract_uses_the_same_archive_lock_as_sync_and_combine(profile):
    with archive_operation(profile["archive_root"]):
        with pytest.raises(ArchiveBusy):
            extract_profile(profile)
    assert not Path(profile["archive_root"]).exists()
    assert extract_profile(profile).total == 0


def test_unexpected_setup_failure_releases_archive_lock(profile, monkeypatch):
    def broken_layout(*args):
        raise OSError("Test folder unavailable")

    with monkeypatch.context() as patch:
        patch.setattr(ArchiveLayout, "create", broken_layout)
        with pytest.raises(OSError, match="Test folder unavailable"):
            extract_profile(profile)

    assert extract_profile(profile).total == 0


def test_no_enabled_formats_reports_configuration_error(profile):
    profile.update(download_pgn=False, download_cbv=False)
    with pytest.raises(ConfigurationError, match="Select PGN, CBV, or both"):
        extract_profile(profile)
