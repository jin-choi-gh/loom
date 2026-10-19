"""DRAFT, not yet reviewed (2026-10-17). Additions to src/synthesis.py: the --notes option.

    python src/synthesis.py --notes text/shakespeare/sonnet-116/annotations/vendler-1997.notes.txt
    python src/synthesis.py <representations of one version> --notes <file>.notes.txt

reads the notes file, composes the version it is about (the version its header names, in the work the
file belongs to; or the representation files given), resolves the notes against it, and prints the version's table of atoms with a
last column naming the notes that cover each atom (by row), then each note with the exact text each of
its targets covers.

What goes into src/synthesis.py:
  1. the imports marked NEW, beside the existing ones;
  2. NOTES_SUFFIX and the functions read_notes, version_for, resolve_notes,
     show_version_with_notes, show_annotations and describe_target, after show_version;
  3. main, replacing the existing main (the changes are marked CHANGED).

Everything else in this file is for trying it from the staging folder (see try_notes.py).
"""

import argparse
import sys
from pathlib import Path

from composition import compose
from models import (
    Annotation,  # NEW
    AnnotationDescription,  # NEW
    AnnotationSetDescription,  # NEW
    Atom,  # NEW
    SynthesisError,
    TargetDescription,  # NEW
    Unit,
    Version,
)
from synthesis import show_version  # staging only: in synthesis.py it is defined above

from annotation import describe, resolve  # NEW
from annotations.notes_text import parse  # NEW
from works import compose_version, work_of  # NEW

NOTES_SUFFIX = ".notes.txt"


def read_notes(path: Path) -> AnnotationSetDescription:
    """A notes file, as written. Errors are prefixed with its path."""
    if not path.name.endswith(NOTES_SUFFIX):
        raise SynthesisError(f"{path}: not a notes file (expected {NOTES_SUFFIX})")
    try:
        return parse(path.read_text(encoding="utf-8-sig"))
    except SynthesisError as error:
        raise SynthesisError(f"{path}: {error}") from error


def version_for(
    notes: AnnotationSetDescription, path: Path, files: list[Path]
) -> Version:
    """The version a notes file is about: composed from the files given, if any; otherwise the
    version its header names, in the work the file belongs to."""
    if files:
        return compose(files)
    if notes.version is None:
        raise SynthesisError(
            f"{path}: names no version: add a line 'version: <name>' at its top, "
            "or give the version's representation files"
        )
    return compose_version(work_of(path), notes.version)


def resolve_notes(
    notes: AnnotationSetDescription, path: Path, version: Version
) -> tuple[tuple[AnnotationDescription, Annotation], ...]:
    """Each note resolved against the version, beside how it was written. Errors are prefixed with
    the file's path, one per line."""
    try:
        annotations = resolve(notes.annotations, version)
    except SynthesisError as error:
        lines = str(error).splitlines()  # resolve reports every error, one per line
        if len(lines) == 1:
            raise SynthesisError(f"{path}: {lines[0]}") from error
        raise SynthesisError(f"{path}:\n  " + "\n  ".join(lines)) from error
    return tuple(
        zip(notes.annotations, annotations)
    )  # resolve keeps the order, or raises


def show_version_with_notes(
    version: Version, notes: tuple[tuple[AnnotationDescription, Annotation], ...]
) -> None:
    """The version as show_version prints it, with a last column: the notes covering each atom,
    by the row of their head. Then the notes themselves, to look the rows up."""
    names = list(version.schemata)

    def label(unit: Unit | None) -> str:
        return "–" if unit is None else f"{unit.rank.name} {unit.local_id}"

    def rows_covering(atom: Atom) -> str:
        """Notes attach and never cut, so a note covers an atom when their spans overlap."""
        rows = [
            str(description.row)
            for description, annotation in notes
            if any(target.span.overlaps(atom.span) for target in annotation.targets)
        ]
        return " ".join(rows) or "–"

    print(f"version: {version.name or '(unnamed)'}\n")
    print(f"{'atom':12}" + "".join(f"{name:22}" for name in names) + "notes (by row)")
    for line, atoms in version.lines():
        print(f"── {line.id}: {line.text}")
        for atom in atoms:
            cells = [label(atom.innermost.get(name)) for name in names]
            print(
                f"{atom.text!r:12}"
                + "".join(f"{cell:22}" for cell in cells)
                + rows_covering(atom)
            )
    print("\n── notes\n")
    show_annotations(version, notes)


def show_annotations(
    version: Version, notes: tuple[tuple[AnnotationDescription, Annotation], ...]
) -> None:
    """Each note: its row and head as written, the text each target covers, then its body."""
    for description, annotation in notes:
        head = " && ".join(describe_target(t) for t in description.targets)
        covered = " · ".join(
            repr(version.substrate.text_of(target.span))
            for target in annotation.targets
        )
        print(f"row {description.row:<4} {head}")
        print(f"         covers {covered}")
        for line in annotation.body.splitlines():
            print(f"         {line}")
        print()


def describe_target(target: TargetDescription) -> str:
    """A target as written: l2 'love'[2], or l2 'love'[2] ~ l3 'alters'."""
    if target.last is None:
        return describe(target.first)
    return f"{describe(target.first)} ~ {describe(target.last)}"


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Create a textual complex.")
    ap.add_argument(  # CHANGED: nargs="*", since --notes can name the version itself
        "files", nargs="*", type=Path, help="The representations of one text"
    )
    ap.add_argument(  # CHANGED: a new option
        "--notes",
        type=Path,
        help=f"a notes file ({NOTES_SUFFIX}) to resolve against its version and print",
    )
    args = ap.parse_args(argv)
    if not args.files and not args.notes:  # CHANGED
        ap.error("give the representation files of one version, or --notes FILE")

    try:
        if (
            args.notes
        ):  # CHANGED: the atoms with their notes, then the notes, when given
            notes = read_notes(args.notes)
            version = version_for(notes, args.notes, args.files)
            show_version_with_notes(version, resolve_notes(notes, args.notes, version))
        else:
            show_version(compose(args.files))

    except SynthesisError as e:
        sys.exit(f"error: {e}")
