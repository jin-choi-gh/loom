import argparse
import sys
from pathlib import Path

from formats import FORMATS
from integration import integrate
from matching import match
from models import (
    Format,
    Representation,
    Schema,
    Substrate,
    SynthesisError,
    Version,
    Unit,
    UnitDescription,
)


def load(path: Path, formats: tuple[Format, ...] = FORMATS) -> Representation:
    if not path.is_file():
        raise SynthesisError(f"{path}: no such file")

    matches = [f for f in formats if path.name.lower().endswith(f.suffix)]

    if not matches:
        known = ", ".join(f.suffix for f in formats) or "none yet"
        raise SynthesisError(
            f"{path}: no format for this file (known suffixes: {known})"
        )
    chosen = max(matches, key=lambda f: len(f.suffix))

    source = path.read_text(encoding="utf-8-sig")

    rest = path.name[: -len(chosen.suffix)]
    _, _, qualifier = rest.partition(".")
    name = f"{chosen.name}-{qualifier}" if qualifier else chosen.name

    return Representation(path=path, format=chosen, source=source, name=name)


def read(representation: Representation) -> tuple[UnitDescription, ...]:
    try:
        return representation.format.read(representation)
    except SynthesisError as error:
        raise SynthesisError(f"{representation.path}: {error}") from error


def choose_base(representations: tuple[Representation, ...]) -> Representation:
    candidates = [r for r in representations if r.format.can_be_base]

    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise SynthesisError("none of the provided files can be the base")

    paths = ", ".join(str(r.path) for r in candidates)
    raise SynthesisError(f"several files could be the base: {paths}")


def make_substrate(
    base: Representation, descriptions: tuple[UnitDescription, ...]
) -> Substrate:
    try:
        return base.format.transcribe(descriptions)
    except SynthesisError as error:
        raise SynthesisError(f"{base.path}: {error}") from error


def make_schema(
    representation: Representation,
    descriptions: tuple[UnitDescription, ...],
    substrate: Substrate,
) -> Schema:
    try:
        return match(representation, descriptions, substrate)
    except SynthesisError as error:
        raise SynthesisError(f"{representation.path}: {error}") from error


def show_version(version: Version) -> None:
    """Every line's atoms, each with its innermost unit in every schema."""
    names = list(version.schemata)

    def label(unit: Unit | None) -> str:
        return "–" if unit is None else f"{unit.rank.name} {unit.local_id}"

    print(f"{'atom':12}" + "".join(f"{name:22}" for name in names))
    for line, atoms in version.lines():
        print(f"── {line.id}: {line.text}")
        for atom in atoms:
            cells = [label(atom.innermost.get(name)) for name in names]
            print(f"{atom.text!r:12}" + "".join(f"{cell:22}" for cell in cells))


def main(argv=None):
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="Create a textual complex.")
    ap.add_argument(
        "files", nargs="+", type=Path, help="The representations of one text"
    )
    args = ap.parse_args(argv)

    try:
        representations = tuple(load(path) for path in args.files)
        descriptions = {r.path: read(r) for r in representations}

        base = choose_base(representations)
        substrate = make_substrate(base, descriptions[base.path])

        schemata = {
            r.name: make_schema(r, descriptions[r.path], substrate)
            for r in representations
        }

        version = integrate(substrate, schemata, base.name)

        show_version(version)

    except SynthesisError as e:
        sys.exit(f"error: {e}")


if __name__ == "__main__":
    main()
