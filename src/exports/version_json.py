"""A version as JSON, so that it can be read by front-end apps.

Positions are [line, offset]: the line's index in "lines", and a character offset within it.
Units are referred to by their local id, which is unique within their schema.
"""

from dataclasses import asdict

from models import Annotation, Atom, Position, Schema, Span, Version

FORMAT = "loom-version"
FORMAT_VERSION = 1


def version_to_json(version: Version) -> dict:
    return {
        "format": FORMAT,
        "format_version": FORMAT_VERSION,
        "name": version.name,
        "metadata": asdict(version.metadata),
        "lines": [
            {"id": line.id, "text": line.text} for line in version.substrate.lines
        ],
        "schemata": {name: schema_to_json(s) for name, s in version.schemata.items()},
        "atoms": [atom_to_json(atom) for atom in version.atoms],
        "annotations": {
            name: [annotation_to_json(a) for a in annotations]
            for name, annotations in version.annotations.items()
        },
    }


def schema_to_json(schema: Schema) -> dict:
    return {
        "kind": schema.kind.name,
        "units": [
            {
                "id": unit.local_id,
                "rank": unit.rank.name,
                **span_to_json(unit.span),
                "value": unit.value,
                "parent": unit.parent_id,
            }
            for unit in schema.units
        ],
    }


def atom_to_json(atom: Atom) -> dict:
    return {
        **span_to_json(atom.span),
        "text": atom.text,
        "innermost": {name: unit.local_id for name, unit in atom.innermost.items()},
    }


def annotation_to_json(annotation: Annotation) -> dict:
    return {
        "targets": [span_to_json(target.span) for target in annotation.targets],
        "body": annotation.body,
    }


def span_to_json(span: Span) -> dict:
    return {"start": position_to_json(span.start), "end": position_to_json(span.end)}


def position_to_json(position: Position) -> list[int]:
    return [position.line, position.offset]
