import re
from dataclasses import dataclass

from models import SynthesisError, UnitDescription

from .display_format import DisplayFormat, Ids, Row, rows_of
from .display_prose_text import describe_prose
from .display_verse_text import describe_verse

DESCRIBERS = {"verse": describe_verse, "prose": describe_prose}

# "[ verse: bird ]": a passage's form and its name. Spaces inside the brackets are free.
HEADING = re.compile(r"\[\s*(?P<form>verse|prose)\s*:\s*(?P<name>[A-Za-z0-9_-]+)\s*\]")

# A row that looks like a heading must be one: anything in brackets beginning with verse or
# prose, and any "[ word: name ]", such as a misspelt form. [Exit] and [ gap ] are text.
LIKE_HEADING = re.compile(
    r"\[\s*(?:(?:verse|prose)\b.*|[^\W\d_]+\s*:\s*[\w-]+\s*)\]", re.IGNORECASE
)

# How lines and paragraphs are called, so a passage may not be: l1, p3
LIKE_BLOCK = re.compile(r"[lp][0-9]+")


@dataclass(frozen=True)
class Heading:
    row_number: int
    form: str
    name: str


class DisplayText(DisplayFormat):
    name = "display-text"
    suffix = ".display.txt"

    def describe(self, source: str) -> tuple[UnitDescription, ...]:
        passages = split_at_headings(rows_of(source))
        refuse_repeated_names([heading for heading, _ in passages])
        return tuple(describe_passage(heading, rows) for heading, rows in passages)


def split_at_headings(rows: list[Row]) -> list[tuple[Heading, list[Row]]]:
    """Each heading, with the rows under it."""
    passages: list[tuple[Heading, list[Row]]] = []
    for row_number, row in rows:
        if LIKE_HEADING.fullmatch(row.strip()):
            passages.append((read_heading(row, row_number), []))
        elif passages:
            passages[-1][1].append((row_number, row))
        elif row.strip():
            raise SynthesisError(
                f"row {row_number}: text before the first heading; begin with "
                "[ verse: name ] or [ prose: name ], or name the file "
                "display.verse.txt or display.prose.txt"
            )
    if not passages:
        raise SynthesisError("no text")
    return passages


def read_heading(row: str, row_number: int) -> Heading:
    found = HEADING.fullmatch(row.rstrip())
    if not found:
        raise SynthesisError(
            f"row {row_number}: {row.rstrip()!r} is not a heading; write [ verse: name ] or "
            "[ prose: name ] at the left edge, the name in letters, digits, - and _"
        )
    if LIKE_BLOCK.fullmatch(found["name"]):
        raise SynthesisError(
            f"row {row_number}: a passage cannot be called {found['name']!r}, "
            "which is how a line or a paragraph is called"
        )
    return Heading(row_number, found["form"], found["name"])


def refuse_repeated_names(headings: list[Heading]) -> None:
    rows: dict[str, int] = {}
    for heading in headings:
        if heading.name in rows:
            raise SynthesisError(
                f"row {heading.row_number}: the passage on row {rows[heading.name]} "
                f"is already called {heading.name!r}"
            )
        rows[heading.name] = heading.row_number


def describe_passage(heading: Heading, rows: list[Row]) -> UnitDescription:
    """The rows under one heading, described as it says."""
    if not any(row.strip() for _, row in rows):
        raise SynthesisError(
            f"row {heading.row_number}: nothing under [ {heading.form}: {heading.name} ]"
        )
    return DESCRIBERS[heading.form](rows, Ids(heading.name))
