"""Notes with ids, on trial: annotations/notes_text.py's syntax, and a note's id defined by @:
at the end of its head. Elsewhere, @id refers to a note; across texts, @text/id (not yet read)."""

import re
import textwrap

from annotations.notes_text import parse_tags, parse_targets
from models import (
    AnnotationDescription,
    AnnotationFormat,
    SynthesisError,
    TargetDescription,
)

# "l1 ever ] {gloss} @:ever": a head's targets, then perhaps its tags, then perhaps its id
HEAD = re.compile(r"(?P<targets>.*) \](?: \{(?P<tags>[^{}]*)\})?(?: @:(?P<id>\S+))?")

# An id: letters, digits, - and _. No / (kept for @text/id) and no : (kept for @:)
ID = re.compile(r"[A-Za-z0-9_-]+")


class ProvisionalNotesText(AnnotationFormat):
    name = "notes"
    suffix = ".notes.txt"

    def read(self, source: str) -> tuple[AnnotationDescription, ...]:
        return parse(source)


def parse(text: str) -> tuple[AnnotationDescription, ...]:
    """A notes file as written: each head's targets, tags and id, and its body. Ids are unique
    within the file."""
    descriptions: list[AnnotationDescription] = []
    head: (
        tuple[int, tuple[TargetDescription, ...], tuple[str, ...], str | None] | None
    ) = None
    body: list[str] = []
    rows_of_ids: dict[str, int] = {}

    def finish_note() -> None:
        if head is not None:
            row, targets, tags, note_id = head
            text = textwrap.dedent("\n".join(body)).strip("\n")
            descriptions.append(
                AnnotationDescription(row, targets, text, tags, note_id)
            )

    for row, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            body.append("")
        elif line[0] in " \t":
            if head is None:
                raise SynthesisError(
                    f"row {row}: an indented line before the first head"
                )
            body.append(line)
        else:
            found = HEAD.fullmatch(line.rstrip())
            if not found:
                raise SynthesisError(
                    f"row {row}: a line at the left edge must be a head ending in ' ]', "
                    "' ] { tags }', ' ] @:id' or ' ] { tags } @:id'; "
                    "indent it if it belongs to the note above"
                )
            finish_note()
            targets = parse_targets(found["targets"], row)
            note_id = parse_id(found["id"], row, rows_of_ids)
            head, body = (row, targets, parse_tags(found["tags"], row), note_id), []
    finish_note()
    return tuple(descriptions)


def parse_id(text: str | None, row: int, rows_of_ids: dict[str, int]) -> str | None:
    """'ever': the id after a head's @:, which no earlier note in the file has; none if no @:."""
    if text is None:
        return None
    if not ID.fullmatch(text):
        raise SynthesisError(
            f"row {row}: @:{text} is not an id: use letters, digits, - and _"
        )
    if text in rows_of_ids:
        raise SynthesisError(
            f"row {row}: @:{text} is already the id of the note at row {rows_of_ids[text]}"
        )
    rows_of_ids[text] = row
    return text
