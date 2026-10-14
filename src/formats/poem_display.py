import re
import unicodedata
import xml.etree.ElementTree as ET
from pathlib import Path

from models import (
    Alignment,
    Format,
    Line,
    Rank,
    Representation,
    Substrate,
    SynthesisError,
    UnitDescription,
)

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
INDENT = re.compile(r"indent\(([^)]*)\)")

POEM = Rank(name="poem")
STANZA = Rank(name="stanza", parents=frozenset({"poem"}))
LINE = Rank(name="line", parents=frozenset({"stanza"}), values=None)

EXACT = Alignment(
    compare=lambda a, b: a == b,
    may_skip=lambda c: False,
    line_break_matches=None,
)


class PoemDisplay(Format):
    name = "poem-display"
    suffix = ".display.xml"
    ranks = {rank.name: rank for rank in (POEM, STANZA, LINE)}
    alignment = EXACT
    can_be_base = True

    def read(self, representation: Representation) -> tuple[UnitDescription, ...]:
        try:
            root = ET.fromstring(representation.source)
        except ET.ParseError as error:
            raise SynthesisError(f"not well-formed XML: {error}")

        body = root.find(f"{TEI}text/{TEI}body")
        if body is None:
            raise SynthesisError("no <text>/<body> element")

        return describe_children(body, representation.path)

    def transcribe(self, descriptions: tuple[UnitDescription, ...]) -> Substrate:
        lines = tuple(
            Line(d.local_id, d.content[0]) for d in walk(descriptions) if d.rank is LINE
        )
        return Substrate(lines=lines)


def describe_children(element: ET.Element, path: Path) -> tuple[UnitDescription, ...]:
    return tuple(d for child in element for d in describe(child, path))


def describe(element: ET.Element, path: Path) -> tuple[UnitDescription, ...]:
    if element.tag == TEI + "div" and element.get("type") == "poem":
        return (
            UnitDescription(
                rank=POEM,
                content=describe_children(element, path),
                local_id=element.get(XML_ID),
            ),
        )
    if element.tag == TEI + "lg":
        return (
            UnitDescription(
                rank=STANZA,
                content=describe_children(element, path),
                local_id=element.get(XML_ID),
            ),
        )
    if element.tag == TEI + "l":
        return (describe_line(element, path),)
    return describe_children(element, path)


def describe_line(element: ET.Element, path: Path) -> UnitDescription:
    line_id = element.get(XML_ID)
    if not line_id:
        raise SynthesisError("a line has no xml:id")

    text = unicodedata.normalize("NFC", "".join(element.itertext()))
    if not text:
        raise SynthesisError(f"line {line_id} is empty")
    if text != text.strip():
        raise SynthesisError(f"line {line_id} has whitespace at its edges")

    match = INDENT.search(element.get("rend", ""))
    indent = match.group(1) if match else "0"

    return UnitDescription(
        rank=LINE,
        content=(text,),
        value=indent,
        local_id=line_id,
    )


def walk(descriptions: tuple[UnitDescription, ...]):
    for d in descriptions:
        yield d
        yield from walk(tuple(c for c in d.content if isinstance(c, UnitDescription)))
