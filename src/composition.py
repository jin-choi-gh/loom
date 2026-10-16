from pathlib import Path

from integration import integrate
from matching import match
from models import (
    Notation,
    Representation,
    Schema,
    SchemaDescription,
    SchemaKind,
    Substrate,
    SynthesisError,
    Version,
)
from notations import NOTATIONS


def compose(paths: list[Path]) -> Version:
    """Compose one version from its representations: the base supplies the substrate,
    each representation gives one or more schemata, and integration joins them."""
    representations = tuple(load(path) for path in paths)
    described = {r.path: read(r) for r in representations}

    base = choose_base(representations)
    substrate = make_substrate(base, described[base.path])

    schemata: dict[str, Schema] = {}
    origins: dict[
        str, Path
    ] = {}  # which file gave each schema, to name both in a clash

    for r in representations:
        for schema_description in described[r.path]:
            name = schema_name(schema_description.kind, r.qualifier)
            if name in schemata:
                raise SynthesisError(
                    f"two schemata called {name}, from {origins[name]} and {r.path}; "
                    "give one of the files a qualifier"
                )
            origins[name] = r.path
            schemata[name] = make_schema(r, name, schema_description, substrate)

    return integrate(substrate, schemata)


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

    return Representation(
        path=path,
        notation=chosen_notation,
        source=source,
        qualifier=matches[chosen_notation],
    )


def qualifier_of(file_name: str, suffix: str) -> str | None:
    if file_name.lower() == suffix.lstrip("."):
        return ""
    if file_name.lower().endswith(suffix):
        return file_name[: -len(suffix)]
    return None


def schema_name(kind: SchemaKind, qualifier: str) -> str:
    return f"{kind.name}-{qualifier}" if qualifier else kind.name


def read(representation: Representation) -> tuple[SchemaDescription, ...]:
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
    base: Representation, schemata: tuple[SchemaDescription, ...]
) -> Substrate:
    try:
        return base.notation.transcribe(schemata)
    except SynthesisError as error:
        raise SynthesisError(f"{base.path}: {error}") from error


def make_schema(
    representation: Representation,
    schema_name: str,
    schema_description: SchemaDescription,
    substrate: Substrate,
) -> Schema:
    try:
        return match(schema_name, schema_description, substrate)
    except SynthesisError as error:
        raise SynthesisError(f"{representation.path}: {error}") from error
