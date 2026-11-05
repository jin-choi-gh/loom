import re
import tomllib

from models import Metadata, NotesMetadata, SynthesisError

TAG = re.compile(r"[^\s{},]+")  # a tag is one word in a note's { }


def parse_metadata(source: str) -> Metadata:
    """A meta.toml as written. Top-level keys that loom does not know are left alone. [notes] may
    be absent, but if present it must declare tags: loom acts on it, so a mistake there must not
    pass silently."""
    try:
        values = tomllib.loads(source)
    except tomllib.TOMLDecodeError as error:
        raise SynthesisError(str(error)) from error

    return Metadata(
        title=parse_text(values, "title"),
        author=parse_text(values, "author"),
        notes=parse_notes(values["notes"]) if "notes" in values else NotesMetadata(),
    )


def parse_text(values: dict, key: str) -> str | None:
    value = values.get(key)
    if value is not None and not isinstance(value, str):
        raise SynthesisError(f"{key} must be text")
    return value


def parse_notes(values: object) -> NotesMetadata:
    if not isinstance(values, dict):
        raise SynthesisError("notes must be a [notes] table")
    unknown = sorted(key for key in values if key != "tags")
    if unknown:
        raise SynthesisError(
            f"[notes]: unknown key {unknown[0]!r}; the only key is tags"
        )
    if "tags" not in values:
        raise SynthesisError(
            "[notes]: tags is missing; declare them, or remove [notes]"
        )
    return NotesMetadata(parse_tags(values["tags"]))


def parse_tags(tags: object) -> tuple[str, ...]:
    if not isinstance(tags, list):
        raise SynthesisError("[notes]: tags must be a list")
    if not tags:
        raise SynthesisError("[notes]: tags is empty; declare some, or remove [notes]")
    seen: set[str] = set()
    for tag in tags:
        if not isinstance(tag, str) or not TAG.fullmatch(tag):
            raise SynthesisError(
                f"[notes]: {tag!r} is not a tag: one word, with no braces or commas"
            )
        if tag in seen:
            raise SynthesisError(f"[notes]: {tag!r} is declared twice")
        seen.add(tag)
    return tuple(tags)
