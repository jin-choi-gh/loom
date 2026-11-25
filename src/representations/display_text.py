import re

from models import SynthesisError, UnitDescription

from .display_format import DisplayFormat, Ids, Row, rows_of
from .display_poem_text import describe_poem
from .display_prose_text import describe_prose

DESCRIBERS = {"[ poem ]": describe_poem, "[ prose ]": describe_prose}
HEADINGS = " or ".join(DESCRIBERS)  # for errors: "[ poem ] or [ prose ]"

# A row written as a heading is, whether or not loom knows it: [ peom ], [poem]. [Exit] is text.
HEADING = re.compile(r"\[ .* \]|\[\s*(?:poem|prose)\s*\]", re.IGNORECASE)


class DisplayText(DisplayFormat):
    name = "display-text"
    suffix = ".display.txt"

    def describe(self, source: str) -> tuple[UnitDescription, ...]:
        ids = Ids()
        return tuple(
            describe_excerpt(heading, rows, ids)
            for heading, rows in excerpts_of(rows_of(source))
        )


def excerpts_of(rows: list[Row]) -> list[tuple[Row, list[Row]]]:
    """Each heading, with the rows under it."""
    excerpts: list[tuple[Row, list[Row]]] = []
    for row_number, row in rows:
        if HEADING.fullmatch(row.strip()):
            excerpts.append(((row_number, row.rstrip()), []))
        elif excerpts:
            excerpts[-1][1].append((row_number, row))
        elif row.strip():
            raise SynthesisError(
                f"row {row_number}: text before the first heading; begin with {HEADINGS}, "
                "or name the file display.poem.txt or display.prose.txt"
            )
    if not excerpts:
        raise SynthesisError("no text")
    return excerpts


def describe_excerpt(heading: Row, rows: list[Row], ids: Ids) -> UnitDescription:
    """The rows under one heading, described as it says."""
    row_number, name = heading
    if name not in DESCRIBERS:
        raise SynthesisError(
            f"row {row_number}: {name!r} is not a heading; write {HEADINGS}, "
            "at the left edge"
        )
    if not any(row.strip() for _, row in rows):
        raise SynthesisError(f"row {row_number}: nothing under {name}")
    return DESCRIBERS[name](rows, ids)
