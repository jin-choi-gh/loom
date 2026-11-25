from collections import Counter

from models import (
    Representation,
    RepresentationFormat,
    SchemaDescription,
    Substrate,
    UnitDescription,
)
from schemata.display import DISPLAY, EXACT, blocks_of
from schemata.word_tokens import WORD_TOKENS, WORDS, describe_tokens

Row = tuple[int, str]  # a row's number in its file, and what it holds


class DisplayFormat(RepresentationFormat):
    """A format that gives the display schema, and so can be the base. Each says how it
    describes its source."""

    can_be_base = True

    def describe(self, source: str) -> tuple[UnitDescription, ...]:
        raise NotImplementedError

    def read(self, representation: Representation) -> tuple[SchemaDescription, ...]:
        display = self.describe(representation.source)
        tokens = describe_tokens(blocks_of(display))
        return (
            SchemaDescription(DISPLAY, display, EXACT),
            SchemaDescription(WORD_TOKENS, tokens, WORDS),
        )

    def transcribe(self, schemata: tuple[SchemaDescription, ...]) -> Substrate:
        display = next(s for s in schemata if s.kind == DISPLAY)
        return Substrate(blocks=blocks_of(display.descriptions))


class Ids:
    """Local ids, numbered through the whole file: vp1, s1, l1, l2, ..., vp2, s2, l3, ..."""

    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()

    def next(self, prefix: str) -> str:
        self.counts[prefix] += 1
        return f"{prefix}{self.counts[prefix]}"


def rows_of(source: str) -> list[Row]:
    return list(enumerate(source.splitlines(), start=1))


def groups_of(rows: list[Row]) -> list[list[Row]]:
    """The rows that stand together, divided by blank rows."""
    groups: list[list[Row]] = [[]]
    for row_number, row in rows:
        if row.strip():
            groups[-1].append((row_number, row))
        elif groups[-1]:
            groups.append([])
    return [group for group in groups if group]
