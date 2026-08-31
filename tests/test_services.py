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
