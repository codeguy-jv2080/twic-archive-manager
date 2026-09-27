"""Package the canonical portable application without local user storage."""

from __future__ import annotations

import argparse
from pathlib import Path
import stat
import zipfile


APPLICATION_DIRECTORY = "TWIC Archive Manager"
ARCHIVE_NAME = "TWIC-Archive-Manager-Portable.zip"
RUNTIME_EXTENSIONS = frozenset({".exe", ".dll", ".pyd"})
LICENSE_DOCUMENTS = (
    "LICENSE",
    "THIRD_PARTY_NOTICES.md",
    "licenses/LGPL-3.0.txt",
    "licenses/Python-LICENSE.txt",
)
GUIDE_DOCUMENTS = (
    "README.md",
    "BEGINNER_GUIDE.md",
    "docs/installer-verification.md",
)


def _reject_redirected_path(path: Path, root: Path) -> None:
    """Do not package through symlinks or Windows directory junctions."""
    for candidate in (path, *path.parents):
        if candidate == root:
            break
        if candidate.is_symlink() or (
            candidate.exists()
            and getattr(candidate.lstat(), "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError(f"Release paths must not be links: {candidate}")


def _require_file(path: Path, root: Path) -> None:
    _reject_redirected_path(path, root)
    if not path.is_file():
        raise ValueError(f"Required release file is missing: {path}")


def validate_portable(project_root: Path) -> dict[str, Path]:
    """Return checked ZIP entries, rejecting unexpected runtime files first.

    Legal documents must be present beside the executable and must exactly
    match the repository copies. User guides come only from the repository.
    No file is written by this function.
    """
    root = project_root.resolve(strict=True)
    portable = root / "dist" / APPLICATION_DIRECTORY
    _reject_redirected_path(portable, root)
    if not portable.is_dir():
        raise ValueError(f"Portable application folder is missing: {portable}")

    documents = {
        relative: root / relative for relative in (*LICENSE_DOCUMENTS, *GUIDE_DOCUMENTS)
    }
    for path in documents.values():
        _require_file(path, root)
    for relative in LICENSE_DOCUMENTS:
        runtime_document = portable / relative
        _require_file(runtime_document, root)
        if runtime_document.read_bytes() != documents[relative].read_bytes():
            raise ValueError(f"Runtime legal document differs from repository: {relative}")

    executable = portable / f"{APPLICATION_DIRECTORY}.exe"
    _require_file(executable, root)
    entries: dict[str, Path] = {}
    for path in sorted(portable.rglob("*")):
        _reject_redirected_path(path, root)
        if path.is_dir():
            continue
        if not path.is_file():
            raise ValueError(f"Unexpected non-file in portable application: {path}")
        relative = path.relative_to(portable).as_posix()
        if relative not in LICENSE_DOCUMENTS and path.suffix.lower() not in RUNTIME_EXTENSIONS:
            raise ValueError(f"Unexpected file in portable application: {relative}")
        entries[f"{APPLICATION_DIRECTORY}/{relative}"] = path

    for relative in GUIDE_DOCUMENTS:
        entries[f"{APPLICATION_DIRECTORY}/{relative}"] = documents[relative]
    return entries


def build_portable_zip(project_root: Path) -> Path:
    """Validate inputs, replace the canonical ZIP, and verify every member."""
    root = project_root.resolve(strict=True)
    entries = validate_portable(root)
    target = root / "dist" / ARCHIVE_NAME
    _reject_redirected_path(target, root)
    # All input validation happens before an existing archive is opened/truncated.
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, path in sorted(entries.items()):
            archive.write(path, name)

    with zipfile.ZipFile(target) as archive:
        if archive.namelist() != sorted(entries):
            raise ValueError("Portable ZIP contains missing, extra, or duplicate entries.")
        damaged = archive.testzip()
        if damaged is not None:
            raise ValueError(f"Portable ZIP verification failed: {damaged}")
        for name, path in entries.items():
            if archive.read(name) != path.read_bytes():
                raise ValueError(f"Portable ZIP content differs from its input: {name}")
    return target


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check-only", action="store_true",
        help="Validate the canonical portable folder and release documents without writing a ZIP.",
    )
    arguments = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if arguments.check_only:
        entries = validate_portable(root)
        print(f"PASS: {len(entries)} checked release files; no local user storage included.")
    else:
        target = build_portable_zip(root)
        print(f"PASS: canonical portable ZIP rebuilt and verified: {target}")


if __name__ == "__main__":
    main()
