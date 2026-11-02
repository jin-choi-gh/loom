import unicodedata

from models import (
    Representation,
    RepresentationFormat,
    SchemaDescription,
    Substrate,
    SynthesisError,
    UnitDescription,
)
from schemata.display import DISPLAY, EXACT, POEM, STANZA, lines_of
from schemata.display import LINE as DISPLAY_LINE
from schemata.word_tokens import WORD_TOKENS, WORDS, describe_tokens


class DisplayText(RepresentationFormat):
    name = "display-text"
    suffix = ".display.txt"
    can_be_base = True

    def read(self, representation: Representation) -> tuple[SchemaDescription, ...]:
        stanzas = describe_stanzas(representation.source)
        if not stanzas:
            raise SynthesisError("no lines")

        display = (UnitDescription(rank=POEM, content=stanzas, local_id="poem"),)

        tokens = describe_tokens(lines_of(display))

        return (
            SchemaDescription(DISPLAY, display, EXACT),
            SchemaDescription(WORD_TOKENS, tokens, WORDS),
        )

    def transcribe(self, schemata: tuple[SchemaDescription, ...]) -> Substrate:
        display = next(s for s in schemata if s.kind == DISPLAY)
        return Substrate(lines=lines_of(display.descriptions))


def describe_stanzas(source: str) -> tuple[UnitDescription, ...]:
    """The stanzas, divided by blank rows; lines numbered l1, l2, ... through the poem."""
    stanzas: list[UnitDescription] = []
    lines: list[UnitDescription] = []
    line_count = 0

    def close_stanza() -> None:
        if lines:
            stanzas.append(
                UnitDescription(
                    rank=STANZA, content=tuple(lines), local_id=f"s{len(stanzas) + 1}"
                )
            )
            lines.clear()

    for row_number, row in enumerate(source.splitlines(), start=1):
        if not row.strip():
            close_stanza()
            continue
        line_count += 1
        lines.append(describe_line(row, line_count, row_number))
    close_stanza()
    return tuple(stanzas)


def describe_line(row: str, line_number: int, row_number: int) -> UnitDescription:
    """One row as a line: its leading tabs are its indent."""
    text = row.lstrip("\t")
    indent = len(row) - len(text)

    if text[0].isspace():
        raise SynthesisError(f"row {row_number}: indent with tabs, not spaces")
    if text != text.rstrip():
        raise SynthesisError(f"row {row_number}: whitespace at the end of the line")
    if "\t" in text:
        raise SynthesisError(f"row {row_number}: a tab inside the line")

    return UnitDescription(
        rank=DISPLAY_LINE,
        content=(unicodedata.normalize("NFC", text),),
        value=str(indent),
        local_id=f"l{line_number}",
    )
