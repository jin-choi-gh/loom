import argparse
import json
import sys
from dataclasses import replace
from pathlib import Path

from annotations import ANNOTATION_FORMATS
from composition import compose, find_format
from exports.textual_complex_json import textual_complex_to_json
from metadata import parse_metadata
from models import Atom, Metadata, SynthesisError, TextualComplex, Unit
from representations import REPRESENTATION_FORMATS

META_FILE = "meta.toml"


def show_textual_complex(textual_complex: TextualComplex) -> None:
    """Every line's atoms, each with its innermost unit in every schema and, for every set of
    notes, the numbers of the notes covering it."""
    names = list(textual_complex.schemata)
    sets = list(textual_complex.annotations)

    def label(unit: Unit | None) -> str:
        return "–" if unit is None else f"{unit.rank.name} {unit.local_id}"

    def covering(atom: Atom, name: str) -> str:
        """Notes never cut the text, so a note covers an atom when their spans overlap."""
        numbers = [
            str(number)
            for number, annotation in enumerate(
                textual_complex.annotations[name], start=1
            )
            if any(target.span.overlaps(atom.span) for target in annotation.targets)
        ]
        return " ".join(numbers) or "–"

    print(f"{'atom':12}" + "".join(f"{name:22}" for name in names + sets))
    for line, atoms in textual_complex.lines():
        print(f"── {line.id}: {line.text}")
        for atom in atoms:
            cells = [label(atom.innermost.get(name)) for name in names]
            cells += [covering(atom, name) for name in sets]
            print(f"{atom.text!r:12}" + "".join(f"{cell:22}" for cell in cells))


def show_annotations(textual_complex: TextualComplex) -> None:
    """Each set of notes: every note's number, the text each of its targets covers, and its body."""
    for name, annotations in textual_complex.annotations.items():
        print(f"\n── {name}\n")
        for number, annotation in enumerate(annotations, start=1):
            covered = " · ".join(
                repr(textual_complex.substrate.text_of(target.span))
                for target in annotation.targets
            )
            print(f"{number:<4} covers {covered}")
            for line in annotation.body.splitlines():
                print(f"     {line}")
            print()


def read_metadata(folder: Path) -> Metadata:
    """A textual complex's metadata, from the meta.toml in its folder; empty if there is none."""
    path = folder / META_FILE
    if not path.is_file():
        return Metadata()
    try:
        return parse_metadata(path.read_text(encoding="utf-8-sig"))
    except SynthesisError as error:
        raise SynthesisError(f"{path}: {error}") from error


def compose_folder(folder: Path) -> TextualComplex:
    """A textual complex from its folder: every file in it that some format reads, named after the folder."""
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
        help="a textual complex's folder, or the files of one textual complex",
    )
    ap.add_argument(
        "--json",
        type=Path,
        metavar="FILE",
        help="write the textual complex to FILE as JSON",
    )

    args = ap.parse_args(argv)

    try:
        if len(args.paths) == 1 and args.paths[0].is_dir():
            textual_complex = compose_folder(args.paths[0])
        else:
            textual_complex = compose(args.paths)
        if args.json:
            data = textual_complex_to_json(textual_complex)
            args.json.write_text(
                json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            print(f"wrote {args.json}")
        else:
            show_textual_complex(textual_complex)
            show_annotations(textual_complex)

    except SynthesisError as e:
        sys.exit(f"error: {e}")
    except OSError as e:
        sys.exit(f"error: cannot write {args.json}: {e.strerror}")


if __name__ == "__main__":
    main()
