import re
import unicodedata

from models import SynthesisError, UnitDescription
from schemata.display_prose import PARAGRAPH, PROSE_PASSAGE

from .display_format import DisplayFormat, Ids, Row, groups_of, rows_of

INDENTED = re.compile(r" *\t| {4}")  # a tab or four spaces, as in a verse
SPACES = re.compile(r"[ \t]+")


class DisplayProseText(DisplayFormat):
    name = "display-prose-text"
    suffix = ".display.prose.txt"

    def describe(self, source: str) -> tuple[UnitDescription, ...]:
        return (describe_prose(rows_of(source), Ids()),)


def describe_prose(rows: list[Row], ids: Ids) -> UnitDescription:
    """The rows as a passage of prose: its paragraphs divided by blank rows."""
    passage_id = ids.next("pp")
    paragraphs = tuple(describe_paragraph(group, ids) for group in groups_of(rows))
    if not paragraphs:
        raise SynthesisError("no paragraphs")
    return UnitDescription(rank=PROSE_PASSAGE, content=paragraphs, local_id=passage_id)


def describe_paragraph(rows: list[Row], ids: Ids) -> UnitDescription:
    """The rows as one text: where they break means nothing, so each break is a space. Only
    the first row may be indented."""
    for row_number, row in rows[1:]:
        if INDENTED.match(row):
            raise SynthesisError(
                f"row {row_number}: an indented row inside a paragraph; "
                "divide paragraphs with a blank row"
            )

    text = SPACES.sub(" ", " ".join(row.strip() for _, row in rows))
    return UnitDescription(
        rank=PARAGRAPH,
        content=(unicodedata.normalize("NFC", text),),
        local_id=ids.next("p"),
    )
