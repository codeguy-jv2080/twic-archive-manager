from __future__ import annotations

from dataclasses import dataclass, field
from html.parser import HTMLParser
import re
from typing import Callable
from urllib.parse import urljoin
from urllib.request import Request, urlopen


CATALOG_URL = "https://theweekinchess.com/twic"


class CatalogError(RuntimeError):
    """The official TWIC archive page could not be read or understood."""


@dataclass(frozen=True, slots=True)
class TwicIssue:
    """One downloadable issue listed on the official TWIC archive page."""

    issue_number: int
    publication_date: str | None
    pgn_url: str | None
    cbv_url: str | None
    game_count: int | None


@dataclass(slots=True)
class _Cell:
    text: list[str] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)

    def rendered_text(self) -> str:
        return " ".join("".join(self.text).split())


class _ArchiveTableParser(HTMLParser):
    """Small table parser kept deliberately independent of page styling."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[list[_Cell]] = []
        self._row: list[_Cell] | None = None
        self._cell: _Cell | None = None
        self._cell_depth = 0
        self._link_href: str | None = None
        self._link_text: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag == "tr":
            self._row = []
            self._cell = None
            self._cell_depth = 0
        elif tag in {"td", "th"} and self._row is not None:
            if self._cell is None:
                self._cell = _Cell()
                self._row.append(self._cell)
            self._cell_depth += 1
        elif tag == "a" and self._cell is not None:
            attributes = dict(attrs)
            self._link_href = attributes.get("href")
            self._link_text = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "a" and self._cell is not None and self._link_text is not None:
            if self._link_href:
                self._cell.links.append(("".join(self._link_text).strip(), self._link_href))
            self._link_href = None
            self._link_text = None
        elif tag in {"td", "th"} and self._cell is not None:
            self._cell_depth -= 1
            if self._cell_depth <= 0:
                self._cell = None
                self._cell_depth = 0
        elif tag == "tr" and self._row is not None:
            if self._row:
                self.rows.append(self._row)
            self._row = None
            self._cell = None
            self._cell_depth = 0

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.text.append(data)
        if self._link_text is not None:
            self._link_text.append(data)


_ISSUE_RE = re.compile(r"^\s*(?:twic\s*)?(\d+)\s*$", re.IGNORECASE)
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_NUMBER_RE = re.compile(r"\b\d{1,3}(?:,\d{3})*\b|\b\d+\b")


def _format_for_link(label: str, href: str) -> str | None:
    value = f"{label} {href}".lower()
    if "pgn" in value:
        return "pgn"
    if "cbv" in value or "chessbase" in value:
        return "cbv"
    return None


def _game_count(cells: list[_Cell]) -> int | None:
    # The current TWIC table has Games as its sixth column.  Fall back to
    # the first number after the date for older/newer table variants.
    candidates = [cells[5]] if len(cells) > 5 else cells[2:]
    for cell in candidates:
        match = _NUMBER_RE.search(cell.rendered_text())
        if match:
            return int(match.group(0).replace(",", ""))
    return None


def parse_catalog(html: str, *, base_url: str = CATALOG_URL) -> list[TwicIssue]:
    """Parse the TWIC archive table into unique issues, newest first."""

    parser = _ArchiveTableParser()
    parser.feed(html)
    parser.close()

    parsed: dict[int, TwicIssue] = {}
    for cells in parser.rows:
        if not cells:
            continue
        issue_match = _ISSUE_RE.match(cells[0].rendered_text())
        if not issue_match:
            continue

        issue_number = int(issue_match.group(1))
        date_match = _DATE_RE.search(" ".join(cell.rendered_text() for cell in cells))
        urls: dict[str, str] = {}
        for cell in cells:
            for label, href in cell.links:
                archive_format = _format_for_link(label, href)
                if archive_format:
                    urls[archive_format] = urljoin(base_url, href)

        # Ignore ordinary article/summary tables which happen to start with a
        # number.  A catalog row has at least one downloadable archive link.
        if not urls:
            continue

        parsed[issue_number] = TwicIssue(
            issue_number=issue_number,
            publication_date=date_match.group(0) if date_match else None,
            pgn_url=urls.get("pgn"),
            cbv_url=urls.get("cbv"),
            game_count=_game_count(cells),
        )

    issues = sorted(parsed.values(), key=lambda issue: issue.issue_number, reverse=True)
    if not issues:
        raise CatalogError("No TWIC archive issues were found on the official archive page.")
    return issues


def fetch_catalog(
    *,
    url: str = CATALOG_URL,
    timeout: float = 30.0,
    opener: Callable[..., object] = urlopen,
) -> list[TwicIssue]:
    """Fetch and parse the official TWIC catalog using the standard library."""

    request = Request(url, headers={"User-Agent": "TWIC Archive Manager"})
    try:
        with opener(request, timeout=timeout) as response:  # type: ignore[union-attr]
            body = response.read()
    except OSError as error:
        raise CatalogError(f"Could not read the TWIC archive page: {error}") from error

    try:
        html = body.decode("utf-8", errors="replace")
    except AttributeError as error:
        raise CatalogError("The TWIC archive page returned an unreadable response.") from error
    return parse_catalog(html, base_url=url)
