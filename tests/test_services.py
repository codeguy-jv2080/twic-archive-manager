from __future__ import annotations

from pathlib import Path
from io import BytesIO
import zipfile

import pytest

from app.database import create_profile, initialize_database
from app.services.archive import ArchiveLayout, NoExtractedPgns, combine_extracted_pgns
from app.services.catalog import CatalogError, TwicIssue, fetch_latest_issue, numbered_issue, parse_latest_issue
from app.services.sync import ConfigurationError, Selection, select_issues, sync_profile


def test_latest_issue_parser_uses_download_links_without_a_table() -> None:
    newest = parse_latest_issue(
        """
        <main><h1>A changed layout</h1>
          <a href="/zips/twic1600g.zip">Older download</a>
          <section><a href="https://theweekinchess.com/zips/twic1660c6.zip">ChessBase</a></section>
          <a href="/zips/twic1659g.zip">Previous issue</a>
          <a href="/twic-archive-2">Issues before 1600</a>
          <a href="https://example.test/zips/twic9999g.zip">Unrelated external link</a>
          <a href="/articles/twic9998g.zip">Not an archive download</a>
        </main>
        """
    )

    assert newest == 1660


@pytest.mark.parametrize("issue_number", [970, 1599, 1600, 1660])
def test_numbered_issue_builds_the_official_pgn_and_cbv_addresses(issue_number: int) -> None:
    assert numbered_issue(issue_number) == TwicIssue(
        issue_number=issue_number,
        publication_date=None,
        pgn_url=f"https://theweekinchess.com/zips/twic{issue_number}g.zip",
        cbv_url=f"https://theweekinchess.com/zips/twic{issue_number}c6.zip",
        game_count=None,
    )


@pytest.mark.parametrize("html", ["", "<h1>TWIC 1660</h1>", '<a href="/zips/twic0g.zip">Invalid issue</a>'])
def test_latest_issue_parser_does_not_silently_accept_missing_or_invalid_downloads(html: str) -> None:
    with pytest.raises(CatalogError):
        parse_latest_issue(html)


def test_fetch_latest_issue_reads_the_page_once() -> None:
    requests = []

    def opener(request, *, timeout):
        requests.append((request.full_url, timeout))
        return BytesIO(b'<a href="/zips/twic1660g.zip">Download</a>')

    assert fetch_latest_issue(opener=opener, timeout=7) == 1660
    assert requests == [("https://theweekinchess.com/twic", 7)]


def test_fetch_latest_issue_reports_a_page_failure() -> None:
    def opener(request, *, timeout):
        raise OSError("Test website unavailable")

    with pytest.raises(CatalogError, match="Test website unavailable"):
        fetch_latest_issue(opener=opener)


def test_selection_modes_are_inclusive_and_ascending() -> None:
    assert [entry.issue_number for entry in select_issues(None, Selection.issue_range(10, 11))] == [
        10,
        11,
    ]
    assert [entry.issue_number for entry in select_issues(12, Selection.through_newest(11))] == [
        11,
        12,
    ]
    assert [entry.issue_number for entry in select_issues(12, Selection.latest(2))] == [11, 12]


def test_starting_at_970_does_not_depend_on_the_page_listing_older_issues() -> None:
    newest = parse_latest_issue('<a href="/zips/twic1600g.zip">1600</a><a href="/zips/twic1660g.zip">1660</a>')
    selected = select_issues(newest, Selection.through_newest(970))

    assert [issue.issue_number for issue in selected] == list(range(970, 1661))
    assert selected[0].pgn_url == "https://theweekinchess.com/zips/twic970g.zip"


def test_explicit_range_crosses_the_archive_page_boundary() -> None:
    assert [issue.issue_number for issue in select_issues(None, Selection.issue_range(1599, 1601))] == [
        1599, 1600, 1601,
    ]


def test_latest_count_can_extend_before_the_issues_listed_on_the_page() -> None:
    newest = parse_latest_issue('<a href="/zips/twic1660g.zip">Newest download only</a>')
    assert [issue.issue_number for issue in select_issues(newest, Selection.latest(100))] == list(range(1561, 1661))
    assert [issue.issue_number for issue in select_issues(3, Selection.latest(100))] == [1, 2, 3]


@pytest.mark.parametrize("newest", [None, 0, -1])
@pytest.mark.parametrize("selection", [Selection.latest(2), Selection.through_newest(970)])
def test_newest_modes_reject_missing_or_invalid_newest_issue(newest, selection: Selection) -> None:
    with pytest.raises(CatalogError):
        select_issues(newest, selection)


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
    monkeypatch.setattr("app.services.sync.numbered_issue", lambda number: issue)

    result = sync_profile("Main", newest_issue_loader=lambda: 999)

    assert result.succeeded
    assert result.downloaded == 1
    assert result.extracted == 1
    assert not list((archive_root / "Downloads" / "PGN").glob("*.zip"))
    assert (archive_root / "Extracted" / "PGN" / "twic999.pgn").exists()

    second_result = sync_profile("Main", newest_issue_loader=lambda: 999)
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
    monkeypatch.setattr("app.services.sync.numbered_issue", lambda number: issue)
    events = []

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(root),
            "download_pgn": archive_format == "pgn", "download_cbv": archive_format == "cbv",
            "extract_archives": True, "keep_zip_files": keep_zips,
        },
        newest_issue_loader=lambda: 999, on_event=events.append,
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
    monkeypatch.setattr("app.services.sync.numbered_issue", lambda number: issue)

    first = sync_profile(profile, newest_issue_loader=lambda: 999)
    second = sync_profile(profile, newest_issue_loader=lambda: 999)

    assert first.succeeded and second.succeeded
    assert first.downloaded == 1 and second.downloaded == 0
    assert second.skipped == 1
    assert first.extracted == second.extracted == 0
    assert (root / "Downloads" / "PGN" / source_zip.name).is_file()


def _local_issue(tmp_path: Path, number: int) -> TwicIssue:
    source_zip = tmp_path / f"twic{number}g.zip"
    with zipfile.ZipFile(source_zip, "w") as archive:
        archive.writestr(f"twic{number}.pgn", f'[Event "issue {number}"]\n')
    return TwicIssue(number, None, source_zip.as_uri(), None, None)


def test_explicit_range_sync_never_reads_an_archive_page(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issues = {number: _local_issue(tmp_path, number) for number in (1599, 1600, 1601)}
    monkeypatch.setattr("app.services.sync.numbered_issue", issues.__getitem__)
    root = tmp_path / "archive"

    result = sync_profile(
        {"name": "Main", "archive_root": str(root), "download_pgn": True},
        selection=Selection.issue_range(1599, 1601),
        newest_issue_loader=lambda: pytest.fail("A fixed range must not read any archive page"),
    )

    assert result.succeeded
    assert result.selected_issues == (1599, 1600, 1601)
    assert result.downloaded == 3
    assert sorted(path.name for path in (root / "Downloads" / "PGN").glob("*.zip")) == [
        "twic1599g.zip", "twic1600g.zip", "twic1601g.zip",
    ]


@pytest.mark.parametrize("selection", [Selection.latest(2), Selection.through_newest(970)])
def test_sync_reads_newest_once_for_newest_based_selections(tmp_path: Path, monkeypatch, selection: Selection) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issues = {number: _local_issue(tmp_path, number) for number in (970, 971)}
    monkeypatch.setattr("app.services.sync.numbered_issue", issues.__getitem__)
    reads = []

    def newest_issue_loader():
        reads.append(True)
        return 971

    result = sync_profile(
        {"name": "Main", "archive_root": str(tmp_path / "archive"), "download_pgn": True},
        selection=selection,
        newest_issue_loader=newest_issue_loader,
    )

    assert result.succeeded
    assert result.selected_issues == (970, 971)
    assert result.downloaded == 2
    assert reads == [True]


@pytest.mark.parametrize("selection", [Selection.latest(0), Selection.through_newest(0), Selection.issue_range(2, 1)])
def test_invalid_selection_fails_before_any_page_read(tmp_path: Path, monkeypatch, selection: Selection) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    with pytest.raises(ConfigurationError):
        sync_profile(
            {"name": "Main", "archive_root": str(tmp_path / "archive"), "download_pgn": True},
            selection=selection,
            newest_issue_loader=lambda: pytest.fail("Invalid selection must fail before reading the page"),
        )


@pytest.mark.parametrize("selection", [Selection.latest(2), Selection.through_newest(970)])
def test_sync_reports_newest_lookup_failure_instead_of_empty_success(tmp_path: Path, monkeypatch, selection: Selection) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")

    def newest_issue_loader():
        raise CatalogError("Could not determine the newest TWIC issue")

    with pytest.raises(CatalogError, match="newest TWIC issue"):
        sync_profile(
            {"name": "Main", "archive_root": str(tmp_path / "archive"), "download_pgn": True},
            selection=selection,
            newest_issue_loader=newest_issue_loader,
        )


@pytest.mark.parametrize("combine_after_sync", [False, True])
def test_unavailable_zip_is_visible_and_does_not_block_available_pgns(
    tmp_path: Path, monkeypatch, combine_after_sync: bool
) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issues = {
        970: TwicIssue(970, None, (tmp_path / "missing970g.zip").as_uri(), None, None),
        971: _local_issue(tmp_path, 971),
    }
    monkeypatch.setattr("app.services.sync.numbered_issue", issues.__getitem__)
    root = tmp_path / "archive"
    events = []

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(root), "download_pgn": True,
            "extract_archives": True, "keep_zip_files": True, "combine_after_sync": combine_after_sync,
        },
        selection=Selection.issue_range(970, 971),
        newest_issue_loader=lambda: pytest.fail("Fixed range must not read the page"),
        on_event=events.append,
    )

    assert not result.succeeded
    assert result.selected_issues == (970, 971)
    assert result.downloaded == 1
    assert result.extracted == 1
    assert len(result.failures) == 1 and "TWIC 970 PGN" in result.failures[0]
    assert any(event.kind == "failure" and event.issue_number == 970 for event in events)
    assert any(event.kind == "download" and event.issue_number == 971 for event in events)
    combined_events = [event for event in events if event.message.startswith("Combined ")]
    assert len(combined_events) == int(combine_after_sync)
    combined_path = ArchiveLayout.create(root).combined_pgn_path
    assert combined_path.exists() == combine_after_sync
    if combine_after_sync:
        assert result.combined is not None
        assert result.combined.issue_numbers == (971,)
        assert result.combined.pgn_files == 1
        assert combined_path.read_text(encoding="utf-8") == '[Event "issue 971"]\n'
        assert combined_events[0].kind == "complete"
        assert combined_events[0].completed == combined_events[0].total == 2
    else:
        assert result.combined is None


def test_auto_combine_without_available_pgns_keeps_existing_output_and_reports_failure(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issue = TwicIssue(970, None, (tmp_path / "missing970g.zip").as_uri(), None, None)
    monkeypatch.setattr("app.services.sync.numbered_issue", lambda number: issue)
    layout = ArchiveLayout.create(tmp_path / "archive")
    original_output = b'[Event "existing combined output"]\n'
    layout.combined_pgn_path.write_bytes(original_output)
    events = []

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(layout.root), "download_pgn": True,
            "extract_archives": True, "combine_after_sync": True,
        },
        selection=Selection.issue_range(970, 970),
        newest_issue_loader=lambda: pytest.fail("Fixed range must not read the page"),
        on_event=events.append,
    )

    assert not result.succeeded
    assert result.downloaded == result.extracted == 0
    assert result.combined is None
    assert len(result.failures) == 2
    assert "TWIC 970 PGN" in result.failures[0]
    assert result.failures[1] == "No extracted PGN files are available to combine."
    assert events[-1].kind == "failure"
    assert events[-1].message == result.failures[1]
    assert not any(event.message.startswith("Combined ") for event in events)
    assert layout.combined_pgn_path.read_bytes() == original_output


@pytest.mark.parametrize("combine_after_sync", [False, True])
def test_direct_number_sync_preserves_optional_combining(tmp_path: Path, monkeypatch, combine_after_sync: bool) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issues = {number: _local_issue(tmp_path, number) for number in (970, 971)}
    monkeypatch.setattr("app.services.sync.numbered_issue", issues.__getitem__)
    root = tmp_path / "archive"

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(root), "download_pgn": True,
            "extract_archives": True, "keep_zip_files": True, "combine_after_sync": combine_after_sync,
        },
        selection=Selection.issue_range(970, 971),
        newest_issue_loader=lambda: pytest.fail("Fixed range must not read the page"),
    )

    assert result.succeeded
    assert result.extracted == 2
    assert (result.combined is not None) == combine_after_sync
    assert ArchiveLayout.create(root).combined_pgn_path.exists() == combine_after_sync


@pytest.mark.parametrize("cancel_after_extract", [False, True])
def test_direct_number_sync_still_honors_cancellation(
    tmp_path: Path, monkeypatch, cancel_after_extract: bool
) -> None:
    monkeypatch.setattr("app.database.database_path", lambda: tmp_path / "state.db")
    issues = {number: _local_issue(tmp_path, number) for number in (970, 971)}
    monkeypatch.setattr("app.services.sync.numbered_issue", issues.__getitem__)
    layout = ArchiveLayout.create(tmp_path / "archive")
    original_output = b'[Event "existing combined output"]\n'
    layout.combined_pgn_path.write_bytes(original_output)
    events = []

    result = sync_profile(
        {
            "name": "Main", "archive_root": str(layout.root), "download_pgn": True,
            "extract_archives": True, "combine_after_sync": True,
        },
        selection=Selection.issue_range(970, 971),
        newest_issue_loader=lambda: pytest.fail("Fixed range must not read the page"),
        is_cancelled=lambda: not cancel_after_extract or any(event.kind == "extract" for event in events),
        on_event=events.append,
    )

    assert result.cancelled and not result.succeeded
    assert result.downloaded == result.extracted == int(cancel_after_extract)
    assert result.combined is None
    assert layout.combined_pgn_path.read_bytes() == original_output
    assert not any(event.message.startswith("Combined ") for event in events)
    assert events[-1].kind == "canceled"
