"""Release packages accept runtime binaries and exact shared documents only."""

from pathlib import Path
import zipfile

import pytest

from scripts import package_portable
from scripts.package_portable import (
    APPLICATION_DIRECTORY,
    ARCHIVE_NAME,
    GUIDE_DOCUMENTS,
    LICENSE_DOCUMENTS,
    build_portable_zip,
    validate_portable,
)


@pytest.fixture
def release_tree(tmp_path: Path) -> tuple[Path, Path]:
    portable = tmp_path / "dist" / APPLICATION_DIRECTORY
    portable.mkdir(parents=True)
    (portable / f"{APPLICATION_DIRECTORY}.exe").write_bytes(b"neutral executable fixture")
    (portable / "python310.dll").write_bytes(b"neutral DLL fixture")
    plugin = portable / "PySide6" / "QtCore.pyd"
    plugin.parent.mkdir()
    plugin.write_bytes(b"neutral extension fixture")
    for relative in (*LICENSE_DOCUMENTS, *GUIDE_DOCUMENTS):
        source = tmp_path / relative
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"Neutral shared document: {relative}\n", encoding="utf-8")
        if relative in LICENSE_DOCUMENTS:
            destination = portable / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(source.read_bytes())
    return tmp_path, portable


def test_portable_zip_contains_runtime_and_exact_shared_documents(release_tree):
    root, portable = release_tree
    expected = validate_portable(root)
    target = build_portable_zip(root)

    assert target == root / "dist" / ARCHIVE_NAME
    assert {p.name for p in (root / "dist").iterdir()} == {APPLICATION_DIRECTORY, ARCHIVE_NAME}
    assert len(expected) == 3 + len(LICENSE_DOCUMENTS) + len(GUIDE_DOCUMENTS)
    with zipfile.ZipFile(target) as archive:
        assert archive.namelist() == sorted(expected)
        assert archive.testzip() is None
        for name, path in expected.items():
            assert archive.read(name) == path.read_bytes()
    assert not (portable / "README.md").exists()


@pytest.mark.parametrize("relative", [
    "state/twic-archive-manager.db", "settings.json", "activity.log",
    "private.txt", "README.md", "licenses/preferences.txt", "twic-installed.flag",
])
def test_rejects_unapproved_runtime_files_before_replacing_zip(release_tree, relative):
    root, portable = release_tree
    target = root / "dist" / ARCHIVE_NAME
    target.write_bytes(b"previous release must remain intact")
    private = portable / relative
    private.parent.mkdir(parents=True, exist_ok=True)
    private.write_text("Neutral private fixture", encoding="utf-8")

    with pytest.raises(ValueError, match="Unexpected file"):
        build_portable_zip(root)
    assert target.read_bytes() == b"previous release must remain intact"
    assert private.read_text(encoding="utf-8") == "Neutral private fixture"


@pytest.mark.parametrize("relative", LICENSE_DOCUMENTS)
def test_rejects_disguised_data_in_legal_documents(release_tree, relative):
    root, portable = release_tree
    target = root / "dist" / ARCHIVE_NAME
    target.write_bytes(b"previous release")
    (portable / relative).write_text("Neutral private settings fixture", encoding="utf-8")
    with pytest.raises(ValueError, match="differs from repository"):
        build_portable_zip(root)
    assert target.read_bytes() == b"previous release"


@pytest.mark.parametrize("relative", LICENSE_DOCUMENTS)
def test_requires_every_runtime_legal_document(release_tree, relative):
    root, portable = release_tree
    (portable / relative).unlink()
    with pytest.raises(ValueError, match="Required release file is missing"):
        validate_portable(root)
    assert not (root / "dist" / ARCHIVE_NAME).exists()


@pytest.mark.parametrize("relative", (*LICENSE_DOCUMENTS, *GUIDE_DOCUMENTS))
def test_requires_every_repository_document(release_tree, relative):
    root, _portable = release_tree
    (root / relative).unlink()
    with pytest.raises(ValueError, match="Required release file is missing"):
        validate_portable(root)


def test_requires_canonical_executable(release_tree):
    root, portable = release_tree
    (portable / f"{APPLICATION_DIRECTORY}.exe").unlink()
    (portable / "alternate.exe").write_bytes(b"not the expected launch path")
    with pytest.raises(ValueError, match="Required release file is missing"):
        validate_portable(root)


def test_validation_does_not_create_or_modify_archive(release_tree):
    root, _portable = release_tree
    target = root / "dist" / ARCHIVE_NAME
    validate_portable(root)
    assert not target.exists()
    target.write_bytes(b"previous release")
    validate_portable(root)
    assert target.read_bytes() == b"previous release"


def test_check_only_cli_leaves_existing_archive_untouched(release_tree, monkeypatch, capsys):
    root, _portable = release_tree
    target = root / "dist" / ARCHIVE_NAME
    target.write_bytes(b"previous release")
    monkeypatch.setattr(package_portable, "__file__", str(root / "scripts" / "package_portable.py"))
    monkeypatch.setattr("sys.argv", ["package_portable.py", "--check-only"])

    package_portable.main()

    assert "checked release files" in capsys.readouterr().out
    assert target.read_bytes() == b"previous release"


def test_rejects_symlink_in_runtime(release_tree):
    root, portable = release_tree
    unrelated = root / "outside.dll"
    unrelated.write_bytes(b"must not be published")
    linked = portable / "linked.dll"
    try:
        linked.symlink_to(unrelated)
    except OSError:
        pytest.skip("Creating symbolic links is not permitted in this environment")
    with pytest.raises(ValueError, match="must not be links"):
        validate_portable(root)
