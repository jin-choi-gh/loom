from pathlib import Path

from integration import integrate
from matching import match
from models import (
    Notation,
    Representation,
    Schema,
    Substrate,
    SynthesisError,
    UnitDescription,
    Version,
)
from notations import NOTATIONS


def compose(paths: list[Path]) -> Version:
    """Compose one version from its representations: the base supplies the substrate,
    every representation becomes a schema, and integration joins them."""
    representations = tuple(load(path) for path in paths)
    descriptions = {r.path: read(r) for r in representations}

    base = choose_base(representations)
    substrate = make_substrate(base, descriptions[base.path])

    schemata = {
        r.name: make_schema(r, descriptions[r.path], substrate) for r in representations
    }
    return integrate(substrate, schemata, base.name)


def load(path: Path, notations: tuple[Notation, ...] = NOTATIONS) -> Representation:
    if not path.is_file():
        raise SynthesisError(f"{path}: no such file")

    matches = {
        n: qualifier
        for n in notations
        if (qualifier := qualifier_of(path.name, n.suffix)) is not None
    }

    if not matches:
        known = ", ".join(n.suffix for n in notations) or "none yet"
        raise SynthesisError(
            f"{path}: no notation for this file (known suffixes: {known})"
        )

    chosen_notation = max(matches, key=lambda notation: len(notation.suffix))

    source = path.read_text(encoding="utf-8-sig")

    qualifier = matches[chosen_notation]
    name = f"{chosen_notation.name}-{qualifier}" if qualifier else chosen_notation.name

    return Representation(path=path, notation=chosen_notation, source=source, name=name)


def qualifier_of(file_name: str, suffix: str) -> str | None:
    if file_name.lower() == suffix.lstrip("."):
        return ""
    if file_name.lower().endswith(suffix):
        return file_name[: -len(suffix)]
    return None


def read(representation: Representation) -> tuple[UnitDescription, ...]:
    try:
        return representation.notation.read(representation)
    except SynthesisError as error:
        raise SynthesisError(f"{representation.path}: {error}") from error


def choose_base(representations: tuple[Representation, ...]) -> Representation:
    candidates = [r for r in representations if r.notation.can_be_base]

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
        return base.notation.transcribe(descriptions)
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
