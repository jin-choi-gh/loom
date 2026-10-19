"""DRAFT, not yet reviewed (2026-10-17). To become src/works.py.

The corpus layout, as far as loom needs it (text/ADDRESS_GRAMMAR.md):

    sonnet-116/                 a work: a folder with a work.toml
        work.toml
        versions/
            vendler-1997/       a version: its representation files (tei-display.xml, metre.txt, …)
        annotations/
            vendler-1997.notes.txt

The first part of src/ that knows this layout; until now only tools/side_by_side.py did.
"""

from pathlib import Path

from composition import compose, qualifier_of
from models import SynthesisError, Version
from representations import REPRESENTATION_FORMATS

WORK_FILE = "work.toml"
VERSIONS = "versions"


def work_of(path: Path) -> Path:
    """The work a file belongs to: the nearest folder above it with a work.toml."""
    for folder in path.resolve().parents:
        if (folder / WORK_FILE).is_file():
            return folder
    raise SynthesisError(
        f"{path}: not inside a work (no folder above it has a {WORK_FILE})"
    )


def version_names(work: Path) -> list[str]:
    """The names of a work's versions: the folders in its versions/."""
    folder = work / VERSIONS
    return (
        sorted(p.name for p in folder.iterdir() if p.is_dir())
        if folder.is_dir()
        else []
    )


def version_files(work: Path, name: str) -> list[Path]:
    """A version's representation files: those in versions/<name>/ that some format reads."""
    folder = work / VERSIONS / name
    if not folder.is_dir():
        names = ", ".join(version_names(work)) or "none"
        raise SynthesisError(
            f"{work}: no version called {name} (its versions: {names})"
        )
    files = sorted(p for p in folder.iterdir() if p.is_file() and is_representation(p))
    if not files:
        raise SynthesisError(f"{folder}: no representation files")
    return files


def is_representation(path: Path) -> bool:
    """A file some representation format reads, judged by its name alone."""
    return any(
        qualifier_of(path.name, f.suffix) is not None for f in REPRESENTATION_FORMATS
    )


def compose_version(work: Path, name: str) -> Version:
    """A version of a work, composed from its folder and named after it."""
    return compose(version_files(work, name), name)
