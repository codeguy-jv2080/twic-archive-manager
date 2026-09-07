from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import re
from typing import Callable
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen


CATALOG_URL = "https://theweekinchess.com/twic"
ZIP_BASE_URL = "https://theweekinchess.com/zips"
_ZIP_PATH_RE = re.compile(r"^/zips/twic([1-9]\d*)(?:g|c6)\.zip$", re.IGNORECASE)


class CatalogError(RuntimeError):
    """The newest TWIC issue number could not be determined."""


@dataclass(frozen=True, slots=True)
class TwicIssue:
    """The download addresses for one numbered TWIC issue."""

    issue_number: int
    publication_date: str | None
    pgn_url: str | None
    cbv_url: str | None
    game_count: int | None


def numbered_issue(issue_number: int) -> TwicIssue:
    """Construct the official ZIP addresses without consulting an archive list."""

    if issue_number < 1:
        raise ValueError("Issue numbers must be at least 1.")
    return TwicIssue(
        issue_number=issue_number,
        publication_date=None,
        pgn_url=f"{ZIP_BASE_URL}/twic{issue_number}g.zip",
        cbv_url=f"{ZIP_BASE_URL}/twic{issue_number}c6.zip",
        game_count=None,
    )


class _LatestIssueParser(HTMLParser):
    """Read numbered ZIP links wherever they appear, without table assumptions."""

    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.latest_issue = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        address = urlparse(urljoin(self.base_url, href))
        if address.scheme not in {"http", "https"} or address.hostname not in {
            "theweekinchess.com", "www.theweekinchess.com",
        }:
            return
        match = _ZIP_PATH_RE.fullmatch(address.path)
        if match:
            self.latest_issue = max(self.latest_issue, int(match.group(1)))


def parse_latest_issue(html: str, *, base_url: str = CATALOG_URL) -> int:
    """Use the page only to find the newest issue, never to limit a chosen range."""

    parser = _LatestIssueParser(base_url)
    parser.feed(html)
    parser.close()
    if not parser.latest_issue:
        raise CatalogError("Could not determine the newest TWIC issue from the official page.")
    return parser.latest_issue


def fetch_latest_issue(
    *,
    url: str = CATALOG_URL,
    timeout: float = 30.0,
    opener: Callable[..., object] = urlopen,
) -> int:
    """Fetch the newest issue number for selections that need it."""

    request = Request(url, headers={"User-Agent": "TWIC Archive Manager"})
    try:
        with opener(request, timeout=timeout) as response:  # type: ignore[union-attr]
            body = response.read()
    except OSError as error:
        raise CatalogError(f"Could not determine the newest TWIC issue: {error}") from error

    try:
        html = body.decode("utf-8", errors="replace")
    except AttributeError as error:
        raise CatalogError("The TWIC page returned an unreadable response.") from error
    return parse_latest_issue(html, base_url=url)
