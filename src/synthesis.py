import argparse
import sys
import tomllib
from dataclasses import fields, replace
from pathlib import Path

from annotations import ANNOTATION_FORMATS
from composition import compose, find_format
from models import Atom, SynthesisError, Unit, Version, VersionMetadata
from representations import REPRESENTATION_FORMATS

VERSION_FILE = "version.toml"


def show_version(version: Version) -> None:
    """Every line's atoms, each with its innermost unit in every schema and, for every set of
    notes, the numbers of the notes covering it."""
    names = list(version.schemata)
    sets = list(version.annotations)

    def label(unit: Unit | None) -> str:
        return "–" if unit is None else f"{unit.rank.name} {unit.local_id}"

    def covering(atom: Atom, name: str) -> str:
        """Notes never cut the text, so a note covers an atom when their spans overlap."""
        numbers = [
            str(number)
            for number, annotation in enumerate(version.annotations[name], start=1)
            if any(target.span.overlaps(atom.span) for target in annotation.targets)
        ]
        return " ".join(numbers) or "–"

    print(f"{'atom':12}" + "".join(f"{name:22}" for name in names + sets))
    for line, atoms in version.lines():
        print(f"── {line.id}: {line.text}")
        for atom in atoms:
            cells = [label(atom.innermost.get(name)) for name in names]
            cells += [covering(atom, name) for name in sets]
            print(f"{atom.text!r:12}" + "".join(f"{cell:22}" for cell in cells))


def show_annotations(version: Version) -> None:
    """Each set of notes: every note's number, the text each of its targets covers, and its body."""
    for name, annotations in version.annotations.items():
        print(f"\n── {name}\n")
        for number, annotation in enumerate(annotations, start=1):
            covered = " · ".join(
                repr(version.substrate.text_of(target.span))
                for target in annotation.targets
            )
            print(f"{number:<4} covers {covered}")
            for line in annotation.body.splitlines():
                print(f"     {line}")
            print()


def read_metadata(folder: Path) -> VersionMetadata:
    """A version's metadata, from the version.toml in its folder; empty if there is none."""
    path = folder / VERSION_FILE
    if not path.is_file():
        return VersionMetadata()
    try:
        values = tomllib.loads(path.read_text(encoding="utf-8-sig"))
    except tomllib.TOMLDecodeError as error:
        raise SynthesisError(f"{path}: {error}") from error

    known = {f.name for f in fields(VersionMetadata)}
    for key, value in values.items():
        if key not in known:
            raise SynthesisError(
                f"{path}: unknown key {key!r} (known: {', '.join(sorted(known))})"
            )
        if not isinstance(value, str):
            raise SynthesisError(f"{path}: {key} must be text")
    return VersionMetadata(**values)


def compose_folder(folder: Path) -> Version:
    """A version from its folder: every file in it that some format reads, named after the folder."""
    if not folder.is_dir():
        raise SynthesisError(f"{folder}: no such folder")
    paths = sorted(
        p
        for p in folder.iterdir()
        if p.is_file()
        and (
            find_format(p, REPRESENTATION_FORMATS) is not None
            or find_format(p, ANNOTATION_FORMATS) is not None
        )
    )
    return replace(compose(paths, folder.name), metadata=read_metadata(folder))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Create a textual complex.")
    ap.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="a version's folder, or the files of one version",
    )
    args = ap.parse_args(argv)

    try:
        if len(args.paths) == 1 and args.paths[0].is_dir():
            version = compose_folder(args.paths[0])
        else:
            version = compose(args.paths)
        show_version(version)
        show_annotations(version)

    except SynthesisError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
