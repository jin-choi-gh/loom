from dataclasses import replace
from pathlib import Path

from anchoring import anchor
from annotations import ANNOTATION_FORMATS
from integration import integrate
from matching import match
from models import (
    Annotation,
    AnnotationDescription,
    AnnotationFormat,
    Representation,
    RepresentationFormat,
    Schema,
    SchemaDescription,
    SchemaKind,
    Substrate,
    SynthesisError,
    Version,
)
from representations import REPRESENTATION_FORMATS


def compose(paths: list[Path], version_name: str | None = None) -> Version:
    """Compose one version from its representations: the base supplies the substrate,
    each representation gives one or more schemata, and integration joins them. Then
    annotations are anchored to the substrate."""

    notes_paths = [p for p in paths if find_format(p, ANNOTATION_FORMATS) is not None]
    representations = tuple(load(p) for p in paths if p not in notes_paths)
    described = {r.path: read(r) for r in representations}
    noted = {p: read_notes(p) for p in notes_paths}

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

    version = integrate(substrate, schemata, version_name)

    annotations: dict[str, tuple[Annotation, ...]] = {}
    notes_origins: dict[
        str, Path
    ] = {}  # which file gave each set, to name both in a clash

    for path, (name, descriptions) in noted.items():
        if name in annotations:
            raise SynthesisError(
                f"two notes files called {name}, from {notes_origins[name]} and {path}; "
                "give one of the files a qualifier"
            )
        notes_origins[name] = path
        annotations[name] = make_annotations(path, descriptions, version)

    return replace(version, annotations=annotations)


def load(
    path: Path, formats: tuple[RepresentationFormat, ...] = REPRESENTATION_FORMATS
) -> Representation:
    if not path.is_file():
        raise SynthesisError(f"{path}: no such file")

    found = find_format(path, formats)
    if found is None:
        known = ", ".join(f.suffix for f in formats) or "none yet"
        raise SynthesisError(
            f"{path}: no format for this file (known suffixes: {known})"
        )

    chosen_format, qualifier = found
    source = path.read_text(encoding="utf-8-sig")

    return Representation(
        path=path,
        format=chosen_format,
        source=source,
        qualifier=qualifier,
    )


def find_format[F: (RepresentationFormat, AnnotationFormat)](
    path: Path, formats: tuple[F, ...]
) -> tuple[F, str] | None:
    """The format that reads a file, judged by its name (the longest matching suffix wins),
    with the file's qualifier; None if no format reads it."""

    matches = {
        f: qualifier
        for f in formats
        if (qualifier := qualifier_of(path.name, f.suffix)) is not None
    }
    if not matches:
        return None
    chosen = max(matches, key=lambda f: len(f.suffix))
    return chosen, matches[chosen]


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
        return representation.format.read(representation)
    except SynthesisError as error:
        raise SynthesisError(f"{representation.path}: {error}") from error


def read_notes(path: Path) -> tuple[str, tuple[AnnotationDescription, ...]]:
    if not path.is_file():
        raise SynthesisError(f"{path}: no such file")
    found = find_format(path, ANNOTATION_FORMATS)
    assert found is not None  # compose passes only paths it has recognised as notes
    notes_format, qualifier = found
    name = f"{notes_format.name}-{qualifier}" if qualifier else notes_format.name
    try:
        return name, notes_format.read(path.read_text(encoding="utf-8-sig"))
    except SynthesisError as error:
        raise SynthesisError(f"{path}: {error}") from error


def choose_base(representations: tuple[Representation, ...]) -> Representation:
    candidates = [r for r in representations if r.format.can_be_base]

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
        return base.format.transcribe(schemata)
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


def make_annotations(
    path: Path, descriptions: tuple[AnnotationDescription, ...], version: Version
) -> tuple[Annotation, ...]:
    try:
        return anchor(descriptions, version)
    except SynthesisError as error:
        lines = str(error).splitlines()  # one line per broken note
        raise SynthesisError("\n".join(f"{path}: {line}" for line in lines)) from error
