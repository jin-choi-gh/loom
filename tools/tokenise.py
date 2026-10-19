"""Word tokenisation of TEI display files, written as TEI.

For every display file found, write its word file next to it: a TEI document listing the words of
every line, one word per line of the file, in order. A display file is named by its suffix alone,
or with a name before it:

    text/shakespeare/sonnet-116/diplomatic/tei-display.xml
    text/shakespeare/sonnet-116/diplomatic/tokens.xml      <- written

    elsewhere/easter-wings.tei-display.xml
    elsewhere/easter-wings.tokens.xml                      <- written

    <w xml:id="l2.w2">impediments</w>
    <w xml:id="l2.w3">loue</w>

A word is a run of letters, digits and combining marks, with apostrophes inside (Lou's). Its id
is its line's id, a dot, `w` and its number in the line, so a word's line is the part of its id
before the dot. Words hold plain text only: markup inside the display file's lines (such as a
drop cap) is left out.

Only words are written: no punctuation, no spaces, no lines. The display file keeps the full text,
and each word can be placed back in its line by finding its letters there, in order, skipping
everything that is not a word. Before writing, the script checks exactly that for every line.

Standalone: standard library only, nothing imported from loom's src.

    python tools/tokenise.py                         every display file under text/shakespeare
    python tools/tokenise.py text/herbert            every display file under another folder
    python tools/tokenise.py path/to/x.tei-display.xml   one file
"""

import argparse
import copy
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

TOKENISER = "loom-words"
TOKENISER_VERSION = "3"
SUFFIX = ".tei-display.xml"
OUTPUT_SUFFIX = ".tokens.xml"
BARE = SUFFIX.lstrip(".")  # a display file named by its suffix alone: tei-display.xml

TEI_NS = "http://www.tei-c.org/ns/1.0"
TEI = "{" + TEI_NS + "}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_MODEL = re.compile(r"<\?xml-model\b.*?\?>", re.DOTALL)

# A word character: a letter or digit (not the underscore), or a combining mark, in case a line
# has one that NFC could not compose.
COMBINING_MARKS = [  # Unicode blocks of combining marks, as (first, last) code points
    (0x0300, 0x036F),
    (0x1AB0, 0x1AFF),
    (0x1DC0, 0x1DFF),
    (0x20D0, 0x20FF),
    (0xFE20, 0xFE2F),
]
MARK_CLASS = "".join(f"{chr(first)}-{chr(last)}" for first, last in COMBINING_MARKS)
WORD_CHAR = rf"(?:[^\W_]|[{MARK_CLASS}])"
WORD = re.compile(rf"{WORD_CHAR}+(?:['’]{WORD_CHAR}+)*")  # Lou's, o'er: one word

DESCRIPTION = (
    "Words of each line, in order: runs of letters, digits and combining marks, with "
    "apostrophes inside. Each id is the line's id, a dot, w and the word's number in the line "
    "(l2.w3). Punctuation, spaces and markup are left out; the display file of the same name "
    "keeps the full text. Generated from that file; do not edit by hand."
)


class TokeniseError(Exception):
    """A display file cannot be tokenised. The message names the file and the line."""


@dataclass(frozen=True)
class Line:
    id: str
    text: str


@dataclass(frozen=True)
class Word:
    id: str
    text: str


def find_display_files(paths: list[Path]) -> list[Path]:
    """Every display file named, or found inside a folder named, in a fixed order."""
    found: list[Path] = []
    for path in paths:
        if path.is_dir():
            found.extend(sorted(p for p in path.rglob("*") if is_display(p)))
        elif is_display(path):
            found.append(path)
        else:
            raise TokeniseError(f"{path}: not a folder or a display file ({BARE})")
    return found


def is_display(path: Path) -> bool:
    """A display file: tei-display.xml, or <name>.tei-display.xml."""
    return path.is_file() and (path.name == BARE or path.name.endswith(SUFFIX))


def read_lines(root: ET.Element) -> list[Line]:
    """The text of each <l> in the body, in order, with its id (or l1, l2, ... if it has none)."""
    body = root.find(f"{TEI}text/{TEI}body")
    if body is None:
        raise TokeniseError("no <text>/<body> element")

    lines: list[Line] = []
    seen: set[str] = set()
    for number, element in enumerate(body.iter(f"{TEI}l"), start=1):
        line_id = element.get(XML_ID) or f"l{number}"
        if "." in line_id:
            raise TokeniseError(
                f"line id {line_id} contains '.', which word ids use as a separator"
            )
        if line_id in seen:
            raise TokeniseError(f"two lines are called {line_id}")
        seen.add(line_id)

        text = "".join(element.itertext())
        if not text:
            raise TokeniseError(f"line {line_id} is empty")
        if unicodedata.normalize("NFC", text) != text:
            raise TokeniseError(f"line {line_id} is not in Unicode NFC")
        lines.append(Line(line_id, text))

    if not lines:
        raise TokeniseError("no <l> lines found")
    return lines


def words_of(line: Line) -> list[Word]:
    """The line's words, in order, numbered l2.w1, l2.w2, ..."""
    return [
        Word(f"{line.id}.w{number}", found.group())
        for number, found in enumerate(WORD.finditer(line.text), start=1)
    ]


def check_placeable(line: Line, words: list[Word]) -> None:
    """Each word must be found in its line in order, with nothing word-like left between them.

    This is how the words are placed back in the text: by their letters, in order, skipping
    punctuation and spaces. If it works here, it works for anything that reads the file.
    """
    cursor = 0
    for word in words:
        start = line.text.find(word.text, cursor)
        skipped = line.text[cursor:start] if start != -1 else ""
        if start == -1 or WORD.search(skipped):
            raise TokeniseError(
                f"line {line.id}: word {word.id} {word.text!r} cannot be placed in order"
            )
        cursor = start + len(word.text)
    if WORD.search(line.text[cursor:]):
        raise TokeniseError(
            f"line {line.id}: words left over after {words[-1].id if words else 'the start'}"
        )


def build_document(source_root: ET.Element, words: list[Word]) -> ET.Element:
    """A TEI document: the display file's header, with this tool recorded, and the words."""
    root = ET.Element(f"{TEI}TEI", dict(source_root.attrib))

    header = source_root.find(f"{TEI}teiHeader")
    header = (
        copy.deepcopy(header) if header is not None else ET.Element(f"{TEI}teiHeader")
    )
    for (
        element
    ) in header.iter():  # drop the copied layout; indent() below lays it out afresh
        if element.text is not None and not element.text.strip():
            element.text = None
        if element.tail is not None and not element.tail.strip():
            element.tail = None
    record_tokeniser(header)
    root.append(header)

    text = ET.SubElement(root, f"{TEI}text")
    body = ET.SubElement(text, f"{TEI}body")
    block = ET.SubElement(body, f"{TEI}ab", {"type": "words"})
    for word in words:
        ET.SubElement(block, f"{TEI}w", {XML_ID: word.id}).text = word.text

    ET.indent(root, space="  ")
    return root


def record_tokeniser(header: ET.Element) -> None:
    """Say in the TEI header what made this file: <encodingDesc><appInfo><application>."""
    encoding = header.find(f"{TEI}encodingDesc")
    if encoding is None:
        encoding = ET.SubElement(header, f"{TEI}encodingDesc")
    app_info = encoding.find(f"{TEI}appInfo")
    if app_info is None:
        app_info = ET.SubElement(encoding, f"{TEI}appInfo")
    application = ET.SubElement(
        app_info,
        f"{TEI}application",
        {"ident": TOKENISER, "version": TOKENISER_VERSION},
    )
    ET.SubElement(application, f"{TEI}label").text = "loom tools/tokenise.py"
    ET.SubElement(application, f"{TEI}p").text = DESCRIPTION


def tokenise_file(path: Path) -> tuple[str, int, int]:
    """The word file's full text, and its numbers of lines and words."""
    source = path.read_text(encoding="utf-8-sig")
    try:
        source_root = ET.fromstring(source)
    except ET.ParseError as error:
        raise TokeniseError(f"not well-formed XML: {error}") from error

    words: list[Word] = []
    lines = read_lines(source_root)
    for line in lines:
        line_words = words_of(line)
        check_placeable(line, line_words)
        words += line_words

    ET.register_namespace("", TEI_NS)
    root = build_document(source_root, words)
    text = '<?xml version="1.0" encoding="UTF-8"?>\n'
    model = XML_MODEL.search(source)
    if model:
        text += model.group() + "\n"
    text += ET.tostring(root, encoding="unicode") + "\n"
    return text, len(lines), len(words)


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Write the words of each TEI display file, as TEI."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        type=Path,
        default=[Path("text/shakespeare")],
        help="folders to search, or display files (default: text/shakespeare)",
    )
    args = parser.parse_args(argv)

    try:
        files = find_display_files(args.paths)
        if not files:
            raise TokeniseError(f"no display files ({BARE}) found")
        for path in files:
            target, line_count, word_count = write_tokens(path)
            print(f"{target}: {line_count} lines, {word_count} words")
    except TokeniseError as error:
        sys.exit(f"error: {error}")


def tokens_path(path: Path) -> Path:
    """Where the word file of a display file goes: beside it, as tokens.xml or <name>.tokens.xml."""
    if path.name == BARE:
        return path.with_name(OUTPUT_SUFFIX.lstrip("."))
    return path.with_name(path.name[: -len(SUFFIX)] + OUTPUT_SUFFIX)


def write_tokens(path: Path) -> tuple[Path, int, int]:
    """Tokenise one display file and write its word file. Returns the file and its counts."""
    try:
        text, line_count, word_count = tokenise_file(path)
    except TokeniseError as error:
        raise TokeniseError(f"{path}: {error}") from error
    target = tokens_path(path)
    target.write_text(text, encoding="utf-8")
    return target, line_count, word_count


if __name__ == "__main__":
    main()
