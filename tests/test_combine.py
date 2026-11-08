from pathlib import Path
import zipfile

import pytest

from app.services.archive import ArchiveLayout, NoExtractedPgns, combine_extracted_pgns
from app.services.sync import ConfigurationError, combine_profile


@pytest.fixture(autouse=True)
def isolated_storage_and_no_network(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "appdata"))
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "settings.db")
    network_attempts = []

    def reject_network(*args, **kwargs):
        network_attempts.append((args, kwargs))
        raise AssertionError("Manual combining must not contact the website or download files.")

    monkeypatch.setattr("app.services.sync.download_file", reject_network)
    monkeypatch.setattr("app.services.sync.fetch_latest_issue", reject_network)
    monkeypatch.setattr("urllib.request.OpenerDirector.open", reject_network)
    yield
    assert network_attempts == []


def profile_for(layout: ArchiveLayout, *, keep_zips: bool = False) -> dict[str, object]:
    return {
        "name": "Combine fixture",
        "archive_root": str(layout.root),
        "download_pgn": True,
        "download_cbv": False,
        "extract_archives": False,
        "keep_zip_files": keep_zips,
        "combine_after_sync": False,
    }


def pgn(issue: int, label: str = "fixture") -> bytes:
    return f'[Event "TWIC {issue} {label}"]\n\n1. e4 e5 *\n'.encode("utf-8")


def make_zip(layout: ArchiveLayout, issue: int, members: dict[str, bytes] | None = None) -> Path:
    target = layout.downloads("pgn") / f"twic{issue}g.zip"
    with zipfile.ZipFile(target, "w") as archive:
        for name, contents in (members or {f"twic{issue}g.pgn": pgn(issue)}).items():
            archive.writestr(name, contents)
    return target


def test_manual_range_combines_zip_only_inputs_in_order_and_keeps_all_zips(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    # Create in reverse order so output ordering cannot depend on directory order.
    zips = [make_zip(layout, issue) for issue in (1602, 1601, 1600, 1599)]
    zip_contents = {path: path.read_bytes() for path in zips}
    events = []

    result = combine_profile(profile_for(layout), issue_range=(1600, 1601), on_event=events.append)

    assert result.issue_numbers == (1600, 1601)
    assert result.pgn_files == 2
    assert result.output_path == layout.combined_pgn_path
    assert result.output_path.read_bytes() == pgn(1600) + b"\n\n" + pgn(1601)
    assert {path.name for path in layout.extracted_root("pgn").iterdir()} == {
        "twic1600g.pgn", "twic1601g.pgn",
    }
    assert {path: path.read_bytes() for path in zips} == zip_contents
    assert any(event.kind == "extract" for event in events)


def test_manual_range_mixes_existing_pgns_and_zips_without_touching_other_issues(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    originals = {}
    for issue in (1599, 1600, 1602):
        target = layout.extracted_root("pgn") / f"twic{issue}.pgn"
        target.write_bytes(pgn(issue, "already extracted"))
        originals[target] = target.read_bytes()
    make_zip(layout, 1600, {"twic1600g.pgn": pgn(1600, "must not replace existing")})
    selected_zip = make_zip(layout, 1601)
    selected_zip_contents = selected_zip.read_bytes()
    outside_zip = make_zip(layout, 1603)
    outside_zip_contents = outside_zip.read_bytes()

    result = combine_profile(profile_for(layout), issue_range=(1600, 1601))

    assert result.issue_numbers == (1600, 1601)
    assert result.output_path.read_bytes() == pgn(1600, "already extracted") + b"\n\n" + pgn(1601)
    assert {path: path.read_bytes() for path in originals} == originals
    assert not (layout.extracted_root("pgn") / "twic1600g.pgn").exists()
    assert not (layout.extracted_root("pgn") / "twic1603g.pgn").exists()
    assert selected_zip.read_bytes() == selected_zip_contents
    assert outside_zip.read_bytes() == outside_zip_contents


def test_manual_combine_uses_existing_pgn_even_when_its_zip_is_corrupt(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    extracted = layout.extracted_root("pgn") / "twic1600.pgn"
    extracted.write_bytes(pgn(1600, "existing"))
    broken_zip = layout.downloads("pgn") / "twic1600g.zip"
    broken_zip.write_bytes(b"not a zip")

    result = combine_profile(profile_for(layout), issue_range=(1600, 1600))

    assert result.output_path.read_bytes() == pgn(1600, "existing")
    assert extracted.read_bytes() == pgn(1600, "existing")
    assert broken_zip.read_bytes() == b"not a zip"


def test_manual_combine_extracts_only_matching_pgn_members_and_ignores_cbv(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    make_zip(layout, 1600, {
        "nested/twic1600g.pgn": pgn(1600),
        "twic1599g.pgn": pgn(1599),
        "twic1601g.pgn": pgn(1601),
        "notes.txt": b"not a PGN",
        "twic1600.cbv": b"not a PGN",
    })
    cbv_zip = layout.downloads("cbv") / "twic1600c6.zip"
    cbv_zip.write_bytes(b"deliberately not a valid ZIP; CBV must not be opened")

    result = combine_profile(profile_for(layout), issue_range=(1600, 1600))

    assert result.output_path.read_bytes() == pgn(1600)
    assert {path.name for path in layout.extracted_root("pgn").iterdir()} == {"twic1600g.pgn"}
    assert list(layout.extracted_root("cbv").iterdir()) == []
    assert cbv_zip.read_bytes() == b"deliberately not a valid ZIP; CBV must not be opened"


def test_manual_combine_skips_missing_local_issues_with_visible_message(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    make_zip(layout, 1600)
    make_zip(layout, 1602)
    events = []

    result = combine_profile(profile_for(layout), issue_range=(1600, 1602), on_event=events.append)

    assert result.issue_numbers == (1600, 1602)
    assert result.output_path.read_bytes() == pgn(1600) + b"\n\n" + pgn(1602)
    assert any("No local PGN or ZIP" in event.message and "1 selected issue" in event.message for event in events)


def test_manual_combine_with_no_selected_inputs_preserves_previous_output(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    make_zip(layout, 1599)
    outside_pgn = layout.extracted_root("pgn") / "twic1602.pgn"
    outside_pgn.write_bytes(pgn(1602))
    layout.combined_pgn_path.write_bytes(b"previous combined output")

    with pytest.raises(NoExtractedPgns):
        combine_profile(profile_for(layout), issue_range=(1600, 1601))

    assert layout.combined_pgn_path.read_bytes() == b"previous combined output"
    assert outside_pgn.read_bytes() == pgn(1602)
    assert not (layout.extracted_root("pgn") / "twic1599g.pgn").exists()


def test_manual_combine_reports_corrupt_selected_zip_before_replacing_output(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    broken_zip = layout.downloads("pgn") / "twic1600g.zip"
    broken_zip.write_bytes(b"not a ZIP file")
    layout.combined_pgn_path.write_bytes(b"previous combined output")

    with pytest.raises(ValueError, match="1600"):
        combine_profile(profile_for(layout), issue_range=(1600, 1600))

    assert broken_zip.read_bytes() == b"not a ZIP file"
    assert layout.combined_pgn_path.read_bytes() == b"previous combined output"


def test_manual_combine_reports_zip_without_matching_pgn_and_preserves_output(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    source_zip = make_zip(layout, 1600, {"twic1601g.pgn": pgn(1601), "readme.txt": b"notes"})
    source_contents = source_zip.read_bytes()
    layout.combined_pgn_path.write_bytes(b"previous combined output")

    with pytest.raises(ValueError, match="1600"):
        combine_profile(profile_for(layout), issue_range=(1600, 1600))

    assert list(layout.extracted_root("pgn").iterdir()) == []
    assert source_zip.read_bytes() == source_contents
    assert layout.combined_pgn_path.read_bytes() == b"previous combined output"


@pytest.mark.parametrize("issue_range", [(1601, 1600), (0, 1600), (-1, 1)])
def test_manual_combine_rejects_invalid_range_before_creating_archive(tmp_path, issue_range):
    layout = ArchiveLayout(tmp_path / "not-created")

    with pytest.raises(ConfigurationError):
        combine_profile(profile_for(layout), issue_range=issue_range)

    assert not layout.root.exists()


def test_manual_combine_without_range_includes_all_local_pgn_issues(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    existing = layout.extracted_root("pgn") / "twic10.pgn"
    existing.write_bytes(pgn(10))
    source_zip = make_zip(layout, 20)
    zip_contents = source_zip.read_bytes()

    result = combine_profile(profile_for(layout))

    assert result.issue_numbers == (10, 20)
    assert result.output_path.read_bytes() == pgn(10) + b"\n\n" + pgn(20)
    assert existing.read_bytes() == pgn(10)
    assert source_zip.read_bytes() == zip_contents


def test_low_level_combine_range_is_inclusive_but_default_still_combines_all(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    for issue in (1599, 1600, 1601, 1602):
        (layout.extracted_root("pgn") / f"twic{issue}.pgn").write_bytes(pgn(issue))

    selected = combine_extracted_pgns(layout, issue_range=(1600, 1601))

    assert selected.issue_numbers == (1600, 1601)
    assert selected.output_path.read_bytes() == pgn(1600) + b"\n\n" + pgn(1601)
    all_issues = combine_extracted_pgns(layout)
    assert all_issues.issue_numbers == (1599, 1600, 1601, 1602)


def test_manual_combine_ignores_non_pgn_marker_and_extracts_real_pgn(tmp_path):
    layout = ArchiveLayout.create(tmp_path / "archive")
    marker = layout.extracted_root("pgn") / "twic1600.txt"
    marker.write_bytes(b"not an extracted PGN")
    make_zip(layout, 1600)

    result = combine_profile(profile_for(layout), issue_range=(1600, 1600))

    assert result.output_path.read_bytes() == pgn(1600)
    assert marker.read_bytes() == b"not an extracted PGN"
