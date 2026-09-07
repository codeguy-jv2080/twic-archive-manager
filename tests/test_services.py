from __future__ import annotations

from pathlib import Path
import zipfile

import pytest

from app.database import create_profile, initialize_database
from app.services.archive import ArchiveLayout, NoExtractedPgns, combine_extracted_pgns
from app.services.catalog import TwicIssue, parse_catalog
from app.services.sync import Selection, select_issues, sync_profile


def test_catalog_parser_reads_download_links_and_metadata() -> None:
    catalog = parse_catalog(
        """
        <table>
          <tr><th>TWIC</th><th>Date</th><th>Read</th><th>PGN</th><th>CBV</th><th>Games</th></tr>
          <tr>
            <td>1234</td><td>2024-01-01</td><td>HTML</td>
            <td><a href="downloads/twic1234g.zip">PGN</a></td>
            <td><a href="downloads/twic1234cbv.zip">Chessbase</a></td>
            <td>1,234</td>
          </tr>
        </table>
        """,
        base_url="https://example.test/twic/",
    )

    assert catalog == [
        TwicIssue(
            issue_number=1234,
            publication_date="2024-01-01",
            pgn_url="https://example.test/twic/downloads/twic1234g.zip",
            cbv_url="https://example.test/twic/downloads/twic1234cbv.zip",
            game_count=1234,
        )
    ]


def test_selection_modes_are_inclusive_and_ascending() -> None:
    catalog = [
        TwicIssue(12, None, "pgn-12", None, None),
        TwicIssue(10, None, "pgn-10", None, None),
        TwicIssue(11, None, "pgn-11", None, None),
    ]

    assert [entry.issue_number for entry in select_issues(catalog, Selection.issue_range(10, 11))] == [
        10,
        11,
    ]
    assert [entry.issue_number for entry in select_issues(catalog, Selection.through_newest(11))] == [
        11,
        12,
    ]
    assert [entry.issue_number for entry in select_issues(catalog, Selection.latest(2))] == [11, 12]


def test_combine_orders_pgns_by_issue(tmp_path: Path) -> None:
    layout = ArchiveLayout.create(tmp_path / "archive")
    extracted = layout.extraction_directory("pgn")
    (extracted / "twic20.pgn").write_text('[Event "twenty"]\n', encoding="utf-8")
    (extracted / "twic10.pgn").write_text('[Event "ten"]\n', encoding="utf-8")

    result = combine_extracted_pgns(layout)

    assert result.issue_numbers == (10, 20)
    assert result.pgn_files == 2
    assert result.output_path.read_text(encoding="utf-8") == '[Event "ten"]\n\n\n[Event "twenty"]\n'


def test_combine_without_extracted_pgns_keeps_existing_output(tmp_path: Path) -> None:
    layout = ArchiveLayout.create(tmp_path / "archive")
    layout.combined_pgn_path.write_text('[Event "existing"]\n', encoding="utf-8")

    with pytest.raises(NoExtractedPgns, match="No extracted PGN"):
        combine_extracted_pgns(layout)

    assert layout.combined_pgn_path.read_text(encoding="utf-8") == '[Event "existing"]\n'


def test_sync_uses_extracted_files_as_its_source_of_truth(tmp_path: Path, monkeypatch) -> None:
    database = tmp_path / "state" / "twic.db"
    monkeypatch.setattr("app.database.database_path", lambda: database)
    initialize_database()
    archive_root = tmp_path / "archive"
    create_profile(
        name="Main",
        archive_root=str(archive_root),
        download_pgn=True,
        download_cbv=False,
        extract_archives=True,
        keep_zip_files=False,
        default_selection_mode="latest_n",
        default_selection_value="1",
    )

    source_zip = tmp_path / "twic999g.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("twic999.pgn", '[Event "test"]\n')
    issue = TwicIssue(999, "2026-01-01", source_zip.as_uri(), None, 1)

    result = sync_profile("Main", catalog_loader=lambda: [issue])

    assert result.succeeded
    assert result.downloaded == 1
    assert result.extracted == 1
    assert not list((archive_root / "Downloads" / "PGN").glob("*.zip"))
    assert (archive_root / "Extracted" / "PGN" / "twic999.pgn").exists()

    second_result = sync_profile("Main", catalog_loader=lambda: [issue])
    assert second_result.succeeded
    assert second_result.skipped == 1
    assert second_result.downloaded == 0
    assert second_result.extracted == 0


@pytest.mark.parametrize("archive_format", ["pgn", "cbv"])
@pytest.mark.parametrize("keep_zips,zip_present", [(False, True), (False, False), (True, True), (True, False)])
def test_keep_zip_setting_applies_to_already_extracted_issues(
    tmp_path: Path, monkeypatch, archive_format: str, keep_zips: bool, zip_present: bool
) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    root = tmp_path / "archive"
    layout = ArchiveLayout.create(root)
    filename = f"twic999.{archive_format}"
    source_zip = tmp_path / f"twic999{archive_format}.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr(filename, "source content")
    extracted = layout.extraction_directory(archive_format) / filename
    extracted.write_text("existing extracted content", encoding="utf-8")
    zip_path = layout.download_path(archive_format, 999, source_zip.as_uri())
    if zip_present:
        zip_path.write_bytes(source_zip.read_bytes())
    issue = TwicIssue(999, None, source_zip.as_uri(), source_zip.as_uri(), None)
    events = []

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(root),
            "download_pgn": archive_format == "pgn", "download_cbv": archive_format == "cbv",
            "extract_archives": True, "keep_zip_files": keep_zips,
        },
        catalog_loader=lambda: [issue], on_event=events.append,
    )

    assert result.succeeded
    assert result.downloaded == int(keep_zips and not zip_present)
    assert result.skipped == int(not keep_zips or zip_present)
    assert result.extracted == 0
    assert extracted.read_text(encoding="utf-8") == "existing extracted content"
    assert zip_path.exists() == keep_zips
    assert events[-1].completed == events[-1].total == 1
    if not keep_zips and zip_present:
        assert "Removed ZIP" in events[0].message


def test_download_only_keeps_zip_even_when_keep_after_extraction_is_off(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    source_zip = tmp_path / "twic999g.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr("twic999.pgn", "test")
    root = tmp_path / "archive"
    profile = {
        "name": "Main", "archive_root": str(root), "download_pgn": True,
        "extract_archives": False, "keep_zip_files": False,
    }
    issue = TwicIssue(999, None, source_zip.as_uri(), None, None)

    first = sync_profile(profile, catalog_loader=lambda: [issue])
    second = sync_profile(profile, catalog_loader=lambda: [issue])

    assert first.succeeded and second.succeeded
    assert first.downloaded == 1 and second.downloaded == 0
    assert second.skipped == 1
    assert first.extracted == second.extracted == 0
    assert (root / "Downloads" / "PGN" / source_zip.name).is_file()
