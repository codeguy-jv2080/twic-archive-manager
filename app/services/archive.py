from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Callable
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import zipfile


ArchiveFormat = str
ProgressCallback = Callable[[int, int | None], None]
CancelledCallback = Callable[[], bool]


class DownloadCancelled(RuntimeError):
    """Raised when a caller asks an in-progress direct download to stop."""


class ArchiveRootUnavailable(RuntimeError):
    """The selected archive root cannot be created or used."""


class NoExtractedPgns(ValueError):
    """There are no extracted PGNs available for a combined output."""


@dataclass(frozen=True, slots=True)
class ArchiveLayout:
    root: Path

    @classmethod
    def create(cls, archive_root: str | Path) -> "ArchiveLayout":
        root = Path(archive_root).expanduser()
        try:
            root.mkdir(parents=True, exist_ok=True)
            if not root.is_dir():
                raise ArchiveRootUnavailable(f"Archive root is not a folder: {root}")
            layout = cls(root=root)
            for directory in (
                layout.downloads("pgn"),
                layout.downloads("cbv"),
                layout.extracted_root("pgn"),
                layout.extracted_root("cbv"),
                layout.combined_directory,
                layout.logs_directory,
            ):
                directory.mkdir(parents=True, exist_ok=True)
            return layout
        except ArchiveRootUnavailable:
            raise
        except OSError as error:
            raise ArchiveRootUnavailable(f"Archive root is unavailable: {root} ({error})") from error

    def downloads(self, archive_format: ArchiveFormat) -> Path:
        return self.root / "Downloads" / archive_format.upper()

    def extracted_root(self, archive_format: ArchiveFormat) -> Path:
        return self.root / "Extracted" / archive_format.upper()

    def extraction_directory(self, archive_format: ArchiveFormat) -> Path:
        return self.extracted_root(archive_format)

    def has_extracted_issue(self, archive_format: ArchiveFormat, issue_number: int) -> bool:
        """Return whether the flat extraction folder contains this labeled TWIC issue."""

        pattern = re.compile(rf"^twic\D*{issue_number}(?:\D|$)", re.IGNORECASE)
        root = self.extracted_root(archive_format)
        return any(path.is_file() and pattern.search(path.stem) for path in root.iterdir())

    @property
    def combined_directory(self) -> Path:
        return self.root / "Combined"

    @property
    def combined_pgn_path(self) -> Path:
        return self.combined_directory / "twic-all.pgn"

    @property
    def logs_directory(self) -> Path:
        return self.root / ".twic-archive-manager" / "logs"

    def download_path(self, archive_format: ArchiveFormat, issue_number: int, source_url: str) -> Path:
        filename = Path(urlparse(source_url).path).name
        if not filename.lower().endswith(".zip"):
            filename = f"twic-{issue_number}-{archive_format}.zip"
        return self.downloads(archive_format) / filename


@dataclass(frozen=True, slots=True)
class CombineResult:
    output_path: Path
    issue_numbers: tuple[int, ...]
    pgn_files: int
    bytes_written: int


def download_file(
    url: str,
    destination: Path,
    *,
    timeout: float = 60.0,
    progress: ProgressCallback | None = None,
    is_cancelled: CancelledCallback | None = None,
) -> int:
    """Download directly to ``destination``.  No staging, retry, or hashing."""

    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "TWIC Archive Manager"})
    total: int | None = None
    written = 0
    with urlopen(request, timeout=timeout) as response, destination.open("wb") as target:
        content_length = response.headers.get("Content-Length")
        if content_length and content_length.isdigit():
            total = int(content_length)
        while chunk := response.read(1024 * 64):
            if is_cancelled and is_cancelled():
                raise DownloadCancelled("Download canceled.")
            target.write(chunk)
            written += len(chunk)
            if progress:
                progress(written, total)
    if progress:
        progress(written, total)
    return written


def extract_zip(zip_path: Path, destination: Path) -> None:
    """Extract an archive directly into its format folder."""

    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as archive:
        archive.extractall(destination)


def combine_extracted_pgns(layout: ArchiveLayout) -> CombineResult:
    """Combine extracted PGNs by ascending issue number into one PGN file."""

    sources: list[tuple[int, Path]] = []
    root = layout.extracted_root("pgn")
    if root.exists():
        for pgn_path in root.iterdir():
            if not pgn_path.is_file() or pgn_path.suffix.lower() != ".pgn":
                continue
            issue_match = re.search(r"twic\D*(\d+)", pgn_path.stem, re.IGNORECASE)
            if issue_match:
                sources.append((int(issue_match.group(1)), pgn_path))

    if not sources:
        raise NoExtractedPgns("No extracted PGN files are available to combine.")

    sources.sort(key=lambda item: (item[0], item[1].as_posix().lower()))

    layout.combined_directory.mkdir(parents=True, exist_ok=True)
    files = 0
    written = 0
    with layout.combined_pgn_path.open("wb") as output:
        for _, pgn_path in sources:
            if files:
                output.write(b"\n\n")
                written += 2
            contents = pgn_path.read_bytes()
            output.write(contents)
            written += len(contents)
            files += 1

    return CombineResult(
        output_path=layout.combined_pgn_path,
        issue_numbers=tuple(sorted({issue for issue, _ in sources})),
        pgn_files=files,
        bytes_written=written,
    )
