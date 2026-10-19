"""DRAFT, not yet reviewed (2026-10-17). To become src/annotations/notes_text.py.

The notes text format: how annotations are written in a *.notes.txt file, and how to read them.

    l1 ever ]                  the first "ever" in line l1
    l1 ever and forever ]      an exact stretch of text within one line
    l1 ever[2] ]               the second "ever" in l1, counted as plain text
    l1 ever[2] ~ l3 now ]      one span across lines
    l1 true && l4 new ]        several spans
    l13 ~ l14 ]                whole lines

Before the first head, a header of `key: value` lines; for now only `version: vendler-1997`, the
version that the file's ends refer to. A head is an unindented line ending in " ]"; its body is the
indented lines after it.

Only the syntax is checked here; resolving against a version is annotation.resolve. The first error
stops reading, since a broken head can throw off everything after it.
"""

import re
import textwrap

from models import (
    AnnotationDescription,
    AnnotationSetDescription,
    End,
    SynthesisError,
    TargetDescription,
)

OCCURRENCE = re.compile(r"(?P<quote>.+)\[(?P<n>\d+)\]")  # "ever[2]": a quote, then [n]
FIELD = re.compile(
    r"(?P<key>[a-z]+): (?P<value>.+)"
)  # a header line: "version: vendler-1997"
HEADER_KEYS = {"version"}


def parse(text: str) -> AnnotationSetDescription:
    """A notes file as written: its header, and each head's targets and body."""
    header: dict[str, str] = {}
    descriptions: list[AnnotationDescription] = []
    head: tuple[int, tuple[TargetDescription, ...]] | None = None  # the current head
    body: list[str] = []

    def finish() -> None:
        if head is not None:
            row, targets = head
            text = textwrap.dedent("\n".join(body)).strip("\n")
            descriptions.append(AnnotationDescription(row, targets, text))

    for row, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            body.append("")  # a blank line: part of the body, if there is one
        elif line[0] in " \t":
            if head is None:
                raise SynthesisError(
                    f"row {row}: an indented line before the first head"
                )
            body.append(line)
        else:
            head_text = line.rstrip()
            field = FIELD.fullmatch(head_text)
            if head is None and field and not head_text.endswith(" ]"):
                read_field(field["key"], field["value"].strip(), header, row)
                continue
            if not head_text.endswith(" ]"):
                raise SynthesisError(
                    f"row {row}: a line at the left edge must be a head ending in ' ]'; "
                    "indent it if it belongs to the note above"
                )
            finish()
            head, body = (row, parse_targets(head_text[: -len(" ]")], row)), []
    finish()
    return AnnotationSetDescription(header.get("version"), tuple(descriptions))


def read_field(key: str, value: str, header: dict[str, str], row: int) -> None:
    """One header line: a known key, given once."""
    if key not in HEADER_KEYS:
        known = ", ".join(sorted(HEADER_KEYS))
        raise SynthesisError(
            f"row {row}: unknown header field {key!r} (known: {known})"
        )
    if key in header:
        raise SynthesisError(f"row {row}: {key} is given twice")
    header[key] = value


def parse_targets(text: str, row: int) -> tuple[TargetDescription, ...]:
    """'l1 true && l4 new': targets separated by &&, each one end or two ends joined by ~."""
    if not text.strip():
        raise SynthesisError(f"row {row}: a head with no targets")
    targets = []
    for part in text.split(" && "):
        ends = part.split(" ~ ")
        if len(ends) > 2:
            raise SynthesisError(f"row {row}: {part!r} has more than one ~")
        first = parse_end(ends[0], row)
        last = parse_end(ends[1], row) if len(ends) == 2 else None
        targets.append(TargetDescription(first, last))
    return tuple(targets)


def parse_end(text: str, row: int) -> End:
    """'l1 ever[2]': a line id, then optionally a quote, then optionally [n]."""
    line_id, _, rest = text.strip().partition(" ")
    if not line_id:
        raise SynthesisError(f"row {row}: an empty target")
    if not rest:
        return End(line_id)  # the whole line
    found = OCCURRENCE.fullmatch(rest)
    if not found:
        return End(line_id, rest)  # the first occurrence
    n = int(found["n"])
    if n < 1:
        raise SynthesisError(f"row {row}: occurrences count from 1, not {n}")
    return End(line_id, found["quote"], n)
