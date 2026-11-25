import re
import unicodedata

from models import SynthesisError, UnitDescription
from schemata.display_poem import LINE, POEM, STANZA

from .display_format import DisplayFormat, Ids, Row, groups_of, rows_of

INDENT = re.compile(r"(?:\t| {4})*")


class DisplayPoemText(DisplayFormat):
    name = "display-poem-text"
    suffix = ".display.poem.txt"

    def describe(self, source: str) -> tuple[UnitDescription, ...]:
        return (describe_poem(rows_of(source), Ids()),)


def describe_poem(rows: list[Row], ids: Ids) -> UnitDescription:
    """The rows as one poem: its stanzas divided by blank rows, each row a line."""
    poem_id = ids.next("poem")
    stanzas = tuple(describe_stanza(group, ids) for group in groups_of(rows))
    if not stanzas:
        raise SynthesisError("no lines")
    return UnitDescription(rank=POEM, content=stanzas, local_id=poem_id)


def describe_stanza(rows: list[Row], ids: Ids) -> UnitDescription:
    stanza_id = ids.next("s")
    lines = tuple(describe_line(row, row_number, ids) for row_number, row in rows)
    return UnitDescription(rank=STANZA, content=lines, local_id=stanza_id)


def describe_line(row: str, row_number: int, ids: Ids) -> UnitDescription:
    """One row as a line: its leading tabs, or fours of spaces, are its indent."""
    leading = INDENT.match(row).group()
    text = row[len(leading) :]
    indent = len(leading.replace("    ", "\t"))

    if text[0].isspace():
        raise SynthesisError(f"row {row_number}: indent with tabs or four spaces")
    if text != text.rstrip():
        raise SynthesisError(f"row {row_number}: whitespace at the end of the line")
    if "\t" in text:
        raise SynthesisError(f"row {row_number}: a tab inside the line")

    return UnitDescription(
        rank=LINE,
        content=(unicodedata.normalize("NFC", text),),
        value=str(indent),
        local_id=ids.next("l"),
    )
