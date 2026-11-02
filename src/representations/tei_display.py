import re
import unicodedata
import xml.etree.ElementTree as ET

from models import (
    Representation,
    RepresentationFormat,
    SchemaDescription,
    Substrate,
    SynthesisError,
    UnitDescription,
)
from schemata.display import DISPLAY, EXACT, HIGHLIGHT, POEM, STANZA, lines_of, text_of
from schemata.display import LINE as DISPLAY_LINE
from schemata.word_tokens import WORD_TOKENS, WORDS, describe_tokens

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
INDENT = re.compile(r"indent\(([^)]*)\)")
INITIAL = re.compile(r"initial\(([^)]*)\)")


class TeiDisplay(RepresentationFormat):
    name = "tei-display"
    suffix = ".tei-display.xml"
    can_be_base = True

    def read(self, representation: Representation) -> tuple[SchemaDescription, ...]:
        try:
            root = ET.fromstring(representation.source)
        except ET.ParseError as error:
            raise SynthesisError(f"not well-formed XML: {error}")

        body = root.find(f"{TEI}text/{TEI}body")
        if body is None:
            raise SynthesisError("no <text>/<body> element")

        display = describe_children(body)

        tokens = describe_tokens(lines_of(display))

        return (
            SchemaDescription(DISPLAY, display, EXACT),
            SchemaDescription(WORD_TOKENS, tokens, WORDS),
        )

    def transcribe(self, schemata: tuple[SchemaDescription, ...]) -> Substrate:
        display = next(s for s in schemata if s.kind == DISPLAY)
        return Substrate(lines=lines_of(display.descriptions))


def describe_children(element: ET.Element) -> tuple[UnitDescription, ...]:
    return tuple(d for child in element for d in describe(child))


def describe(element: ET.Element) -> tuple[UnitDescription, ...]:
    if element.tag == TEI + "div" and element.get("type") == "poem":
        return (
            UnitDescription(
                rank=POEM,
                content=describe_children(element),
                local_id=element.get(XML_ID),
            ),
        )
    if element.tag == TEI + "lg":
        return (
            UnitDescription(
                rank=STANZA,
                content=describe_children(element),
                local_id=element.get(XML_ID),
            ),
        )
    if element.tag == TEI + "l":
        return (describe_line(element),)
    return describe_children(element)


def describe_line(element: ET.Element) -> UnitDescription:
    line_id = element.get(XML_ID)
    if not line_id:
        raise SynthesisError("a line has no xml:id")

    match = INDENT.search(element.get("rend", ""))
    indent = match.group(1) if match else "0"

    line = UnitDescription(
        rank=DISPLAY_LINE,
        content=describe_inline(element, line_id),
        value=indent,
        local_id=line_id,
    )

    text = text_of(line)

    if not text:
        raise SynthesisError(f"line {line_id} is empty")
    if text != text.strip():
        raise SynthesisError(f"line {line_id} has whitespace at its edges")
    return line


def describe_inline(
    element: ET.Element, line_id: str
) -> tuple[str | UnitDescription, ...]:
    content: list[str | UnitDescription] = [element.text or ""]
    for number, child in enumerate(element, start=1):
        content.append(describe_highlight(child, f"{line_id}.h{number}"))
        content.append(child.tail or "")
    return tuple(
        unicodedata.normalize("NFC", c) if isinstance(c, str) else c
        for c in content
        if c != ""
    )


def describe_highlight(element: ET.Element, local_id: str) -> UnitDescription:
    tag = element.tag.removeprefix(TEI)
    if tag != "hi":
        raise SynthesisError(f"{local_id}: unexpected <{tag}> in a line")

    rend = element.get("rend", "")
    if not INITIAL.fullmatch(rend):
        raise SynthesisError(f"{local_id}: unknown rendition {rend!r}")

    if len(element) or not element.text:
        raise SynthesisError(f"{local_id}: a highlight must hold text only")

    return UnitDescription(
        rank=HIGHLIGHT,
        content=(unicodedata.normalize("NFC", element.text),),
        value=rend,
        local_id=local_id,
    )
