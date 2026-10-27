import re
import textwrap

from models import (
    AnnotationDescription,
    Locator,
    SynthesisError,
    TargetDescription,
)

OCCURRENCE = re.compile(r"(?P<quote>.+)\[(?P<n>\d+)\]")  # "ever[2]": a quote, then [n]


def parse(text: str) -> tuple[AnnotationDescription, ...]:
    """A notes file as written: each head's targets and body."""
    descriptions: list[AnnotationDescription] = []
    head: tuple[int, tuple[TargetDescription, ...]] | None = None
    body: list[str] = []

    def finish_note() -> None:
        if head is not None:
            row, targets = head
            text = textwrap.dedent("\n".join(body)).strip("\n")
            descriptions.append(AnnotationDescription(row, targets, text))

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
            head_text = line.rstrip()
            if not head_text.endswith(" ]"):
                raise SynthesisError(
                    f"row {row}: a line at the left edge must be a head end in ' ]'; "
                    "indent it if it belongs to the note above"
                )
            finish_note()
            head, body = (row, parse_targets(head_text[: -len(" ]")], row)), []
    finish_note()
    return tuple(descriptions)


def parse_targets(text: str, row: int) -> tuple[TargetDescription, ...]:
    """'l1 true && l4 new': targets separated by &&, each one locator or two joined by ~."""
    if not text.strip():
        raise SynthesisError(f"row {row}: a head with no targets")
    targets = []
    for part in text.split(" && "):
        locators = [
            locator.strip() for locator in part.split(" ~ ")
        ]  # spaces around && and ~ are forgiven
        if len(locators) > 2:
            raise SynthesisError(f"row {row}: {part!r} has more than one ~")
        first = parse_locator(locators[0], row)
        last = parse_locator(locators[1], row) if len(locators) == 2 else None
        targets.append(TargetDescription(first, last))
    return tuple(targets)


def parse_locator(text: str, row: int) -> Locator:
    """'l1 ever[2]': a line id, then optionally a quote, then optionally [n]."""
    line_id, _, rest = text.partition(" ")
    if not line_id:
        raise SynthesisError(f"row {row}: an empty target")
    if not rest:
        return Locator(line_id)  # the whole line
    if rest[0].isspace():
        raise SynthesisError(f"row {row}: one space between {line_id} and its quote")
    found = OCCURRENCE.fullmatch(rest)
    if not found:
        return Locator(line_id, rest)  # the first occurrence
    n = int(found["n"])
    if n < 1:
        raise SynthesisError(f"row {row}: occurrences count from 1, not {n}")
    if found["quote"][-1].isspace():
        raise SynthesisError(f"row {row}: no space before [{n}]")
    return Locator(line_id, found["quote"], n)
