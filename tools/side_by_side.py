"""A side-by-side reader for the versions of a poem, as one HTML file.

Give it a work's folder, or a collection holding works at any depth. A work is a folder with a
work.toml:

    text/shakespeare/sonnet-116/
        work.toml                            title = "Sonnet 116", author = "William Shakespeare"
        versions/
            quarto-1609/                     a version: one text
                version.toml                 label = "1609 Quarto", type = "diplomatic", language = "en"
                tei-display.xml
            vendler-1997/
                version.toml                 label = "Vendler (1997)", type = "critical", …
                tei-display.xml
        facsimile/1609-quarto.png            optional: one image (.png, .jpg or .jpeg)
        annotations/
            vendler-1997.notes.txt           optional: notes on a version (its header names it)

and for each work it will:

  1. compose each version with loom (loom/src), from every representation file in its folder: its
     lines, stanzas, indents and drop caps from the display schema, its words from the word-tokens
     schema, and its scansion from an accentual-metre schema (a metre.txt) if it has one. A Metre
     key on the bar, off until pressed, shows the scansion over the syllables.
  2. pair the words of every two versions, line by line
  3. write loom/outputs/<work>.html: two panes, each showing any version or the facsimile,
     switched from a menu above it. Hovering a word lights up its counterpart in the other pane.
     Menus show each version's label; versions are ordered by type (diplomatic, critical, then
     the rest), and critical versions number every fifth line.
  4. read the notes files in the work's annotations/ folder, each resolved against the version its
     header names (loom's annotation code, layer 1); a Notes key on the bar shows them, the notes
     in the drawer and their passages marked in the text. Two pages are written, differing only
     in how notes are marked (NOTE_STYLES): <work>.html (sepia: whole lines bracketed in the margin,
     words underlined) and <work>-blue.html (a blue wash, deeper where more notes overlap).
  5. write <work>-mobile.html: the same work read on a phone (tools/mobile_page.py, with Ionic).

Nothing is written into text/.

    python tools/side_by_side.py text/shakespeare/sonnet-116  one work
    python tools/side_by_side.py text/shakespeare             every work in a collection
    python tools/side_by_side.py FOLDER -o DIR                write the pages somewhere other than loom/outputs

How words are paired (a prototype, not yet loom's collation):

  - lines are paired by id (l1 with l1, …); a line missing from one version has no counterparts
  - each word gets a comparison key: lower case, accents removed, long s as s, u as v, j as i,
    apostrophes removed. Words with equal keys are paired by longest common subsequence, so
    "loue" pairs with "Love"
  - words left unpaired between two pairings are paired with each other: one to one when both
    sides have the same number ("mindes" with "minds"), as one group otherwise
"""

import argparse
import base64
import html
import json
import re
import sys
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from itertools import combinations, pairwise
from pathlib import Path

import tomllib

TOOLS = Path(__file__).resolve().parent
LOOM = TOOLS.parent
sys.path.insert(0, str(LOOM / "src"))

import mobile_page  # tools/mobile_page.py

from composition import (
    compose,
    qualifier_of,
)  # loom/src, importable through the path set above
from models import Position, Schema, Span, SynthesisError, Version
from representations import REPRESENTATION_FORMATS
from representations.tei_display import INITIAL

NOTE_STYLES = {  # how notes are marked in the text: page name suffix → style
    "": "sepia",  # passages of whole lines bracketed in the margin; words underlined
    "-blue": "blue",  # every passage washed in blue, deeper where more notes overlap
}
STAGING = (
    LOOM / "src" / "test-annotations"
)  # annotation, layer 1, until it is moved into src/
NOTES = "annotations"  # in a work: its notes files
NOTES_SUFFIX = ".notes.txt"


def annotation_code():
    """loom's parse and resolve: from src/ once layer 1 is moved in, from staging until then."""
    try:
        from annotation import resolve
        from annotations.notes_text import parse
    except ImportError:
        sys.path.insert(1, str(STAGING))
        import models_additions

        import models

        for name in (
            "End",
            "TargetDescription",
            "AnnotationDescription",
            "AnnotationSetDescription",
        ):
            if not hasattr(models, name):
                setattr(models, name, getattr(models_additions, name))
        from annotation import resolve
        from annotations.notes_text import parse
    return parse, resolve


TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
IMAGE_TYPES = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}
WORK_FILE = "work.toml"  # marks a work's folder: title, author
VERSIONS = "versions"  # in a work: one folder per version
VERSION_FILE = "version.toml"  # in a version: label, type, language
FACSIMILE = "facsimile"  # in a work: the folder holding its facsimile image
DISPLAY_FILE = "tei-display.xml"  # a version's display file: tei-display.xml or <name>.tei-display.xml
TYPE_ORDER = [
    "diplomatic",
    "critical",
]  # shown first, in this order; other types follow
NUMBERED_TYPES = {
    "critical"
}  # versions whose lines are numbered, every fifth, in the margin
NUMBER_EVERY = 5
METRE = "accentual-metre"  # the schema kind whose syllables the Metre key marks
FONTS = (
    TOOLS / "fonts"
)  # Libertinus Serif (SIL Open Font License, fonts/OFL.txt), embedded in the page
FONT_FILES = {
    400: "LibertinusSerif-Regular.woff2",
    600: "LibertinusSerif-Semibold.woff2",
}


class ViewerError(Exception):
    """The folder can't be turned into a viewer. The message says what is missing."""


@dataclass(frozen=True)
class Word:
    id: str  # as in the word file: l2.w3
    text: str
    start: int  # offset in the line, end exclusive
    end: int
    key: str


@dataclass(frozen=True)
class Work:
    title: str  # "Sonnet 116"; the folder's name when there is no work.toml
    author: str | None  # "William Shakespeare"


@dataclass(frozen=True)
class Initial:
    start: int  # offset in the line, end exclusive
    end: int
    lines: int  # how many lines it drops: 2 for initial(2)


@dataclass(frozen=True)
class Syllable:
    start: int  # offset in the line, end exclusive
    end: int
    stressed: bool
    foot: int  # which foot of its verse, from 1
    feet: int  # how many feet the verse has
    number: int  # which syllable of its verse, from 1
    count: int  # how many syllables the verse has
    foot_text: str  # its foot as a metre file writes it: "the MAR"
    opens_foot: str  # "" inside a foot; where a later foot begins: "space" after a space, else "in"


@dataclass(frozen=True)
class NoteView:
    id: str  # n1, n2, …, in the order of the notes files and of the notes in them
    row: int  # its head's row in its file
    source: str  # its file's name, without the suffix: vendler-1997
    lemma: str  # what its targets cover, shortened: "impediments · alters"
    body: str  # as HTML paragraphs
    whole: bool  # it covers the whole text: listed apart, not washed over every line


@dataclass(frozen=True)
class LineView:
    id: str
    text: str
    indent: float
    words: tuple[Word, ...]
    initials: tuple[Initial, ...]  # drop caps, in order
    # (start, end, note id, passage, size, inline): the line's noted stretches. A passage is one
    # target of a note, keyed by where it runs ("4.15-4.30"), so notes on the very same passage share
    # it; inline when it lies within one line without being the whole line.
    notes: tuple[tuple[int, int, str, str, int, bool], ...]
    # (passage, lane, first line?, last line?, note ids): the margin brackets beside this line
    margin: tuple[tuple[str, int, bool, bool, str], ...]
    stanza: str | None  # the stanza it belongs to, from the display schema
    syllables: tuple[
        Syllable, ...
    ]  # from the version's metrical reading, if it has one


@dataclass(frozen=True)
class VersionPart:
    name: str  # the version's folder: quarto-1609
    display: Path  # its display file
    files: tuple[
        Path, ...
    ]  # every representation file in its folder, composed together
    label: str  # from version.toml, for menus: "1609 Quarto"; the folder's name if none
    type: str  # from version.toml: diplomatic, critical, …; "" if none


@dataclass(frozen=True)
class VersionView:
    name: str  # the version's folder: quarto-1609
    label: str
    type: str
    lines: tuple[LineView, ...]
    head: str | None  # the poem's <head>, shown above its lines
    notes: tuple[NoteView, ...]  # the notes on this version, from every notes file
    passages: dict[str, str]  # passage key → its text, shortened, for the status bar
    lanes: int  # how many brackets the margin needs side by side
    metre: bool  # it has a metrical reading, which the Metre key shows


# ── Finding the work's parts ────────────────────────────────────────────────────────────────────


def find_works(folder: Path) -> list[Path]:
    """The works to build: the folder itself if it is a work, else every work below it."""
    if not folder.is_dir():
        raise ViewerError(f"{folder}: not a folder")
    if (folder / WORK_FILE).is_file():
        return [folder]
    works = sorted(path.parent for path in folder.rglob(WORK_FILE))
    if not works:
        raise ViewerError(f"{folder}: no work (a folder with a {WORK_FILE}) found")
    return works


def is_display(path: Path) -> bool:
    return path.is_file() and (
        path.name == DISPLAY_FILE or path.name.endswith("." + DISPLAY_FILE)
    )


def is_representation(path: Path) -> bool:
    """A file some loom format reads, judged by its name (as works.py judges it)."""
    return path.is_file() and any(
        qualifier_of(path.name, f.suffix) is not None for f in REPRESENTATION_FORMATS
    )


def display_in(folder: Path) -> Path | None:
    """A version folder's display file, if it holds one."""
    displays = sorted(p for p in folder.iterdir() if is_display(p))
    if len(displays) > 1:
        names = ", ".join(p.name for p in displays)
        raise ViewerError(f"{folder}: more than one display file: {names}")
    return displays[0] if displays else None


def read_toml(path: Path) -> dict:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        raise ViewerError(f"{path}: {error}") from error


def text_field(fields: dict, key: str, path: Path) -> str | None:
    """A field that must be some text, if present."""
    value = fields.get(key)
    if value is not None and (not isinstance(value, str) or not value.strip()):
        raise ViewerError(f"{path}: {key} must be some text")
    return value.strip() if value else None


def read_work(folder: Path) -> Work:
    """The work a text's folder holds versions of, from its work.toml, or named after the folder."""
    path = folder / WORK_FILE
    fields = read_toml(path)
    return Work(
        text_field(fields, "title", path) or folder.name,
        text_field(fields, "author", path),
    )


def find_parts(folder: Path) -> tuple[Path | None, list[VersionPart]]:
    """A work's facsimile image, if any, and its versions, in the order the menus show them."""
    facsimile = folder / FACSIMILE
    images = (
        sorted(p for p in facsimile.iterdir() if p.suffix.lower() in IMAGE_TYPES)
        if facsimile.is_dir()
        else []
    )
    if len(images) > 1:
        raise ViewerError(
            f"{facsimile}: more than one image: {', '.join(p.name for p in images)}"
        )

    versions_folder = folder / VERSIONS
    if not versions_folder.is_dir():
        raise ViewerError(f"{folder}: no {VERSIONS}/ folder")
    versions: list[VersionPart] = []
    for sub in sorted(p for p in versions_folder.iterdir() if p.is_dir()):
        display = display_in(sub)
        if display is None:
            raise ViewerError(f"{sub}: no display file ({DISPLAY_FILE})")
        path = sub / VERSION_FILE
        fields = read_toml(path) if path.is_file() else {}
        versions.append(
            VersionPart(
                sub.name,
                display,
                tuple(sorted(p for p in sub.iterdir() if is_representation(p))),
                text_field(fields, "label", path) or sub.name,
                text_field(fields, "type", path) or "",
            )
        )
    if not versions:
        raise ViewerError(f"{versions_folder}: no versions")

    def order(v: VersionPart) -> tuple[int, str]:
        rank = TYPE_ORDER.index(v.type) if v.type in TYPE_ORDER else len(TYPE_ORDER)
        return rank, v.name

    return (images[0] if images else None), sorted(versions, key=order)


# ── One version: lines and words from loom ──────────────────────────────────────


def comparison_key(word: str) -> str:
    """What makes two spellings count as the same word for pairing."""
    decomposed = unicodedata.normalize("NFD", word.casefold())
    letters = "".join(c for c in decomposed if not unicodedata.combining(c))
    for old, new in (("ſ", "s"), ("u", "v"), ("j", "i"), ("'", ""), ("’", "")):
        letters = letters.replace(old, new)
    return letters


def read_head(display: Path) -> str | None:
    """The text of the first <head> in the display file's body, if it has one.

    Read here, from the file, because loom's tei-display notation does not read heads yet.
    """
    root = ET.parse(display).getroot()
    head = root.find(f"{TEI}text/{TEI}body//{TEI}head")
    text = " ".join("".join(head.itertext()).split()) if head is not None else ""
    return text or None


def version_view(
    part: VersionPart,
    version: Version,
    head: str | None,
    notes: list[tuple[NoteView, tuple[Span, ...]]],
) -> VersionView:
    """A version's lines, each with its indent and drop caps (from the display schema), its
    words (from the word-tokens schema) and the stretches its notes cover."""
    noted: dict[
        int, list[tuple[int, int, str, str, int, bool]]
    ] = {}  # line → stretches
    passages: dict[str, str] = {}
    brackets: dict[
        str, dict
    ] = {}  # passages of whole lines, or across lines: for the margin
    for note, spans in notes:
        for span in spans:
            text = version.substrate.text_of(span)
            key = f"{span.start.line}.{span.start.offset}-{span.end.line}.{span.end.offset}"
            passages[key] = "the whole poem" if note.whole else shorten(text)
            line_text = version.substrate.lines[span.start.line].text
            inline = span.start.line == span.end.line and (
                span.start.offset > 0 or span.end.offset < len(line_text)
            )
            if not inline:
                bracket = brackets.setdefault(
                    key,
                    {"first": span.start.line, "last": span.end.line, "ids": []},
                )
                bracket["ids"].append(note.id)
            if note.whole:
                continue  # the whole poem: only its bracket, the outermost
            for index in range(span.start.line, span.end.line + 1):
                start = span.start.offset if index == span.start.line else 0
                end = (
                    span.end.offset
                    if index == span.end.line
                    else len(version.substrate.lines[index].text)
                )
                if start < end:
                    noted.setdefault(index, []).append(
                        (start, end, note.id, key, len(text), inline)
                    )
    lanes, margin = bracket_lanes(brackets, len(version.substrate.lines))

    display = version.schemata["display"]
    words: dict[int, list[Word]] = {}  # line index → its words, in order
    for unit in version.schemata["word-tokens"].units:
        if unit.rank.name != "word":
            continue  # the schema's lines, which hold the words
        start, end = unit.span.start, unit.span.end
        text = version.substrate.lines[start.line].text[start.offset : end.offset]
        words.setdefault(start.line, []).append(
            Word(unit.local_id, text, start.offset, end.offset, comparison_key(text))
        )

    metre = metre_schema(version)
    syllables = syllables_of(metre, version) if metre else {}

    lines: list[LineView] = []
    for index, line in enumerate(version.substrate.lines):
        try:
            indent = float(display.unit(line.id).value or 0)
        except (SynthesisError, ValueError):
            indent = 0.0
        lines.append(
            LineView(
                line.id,
                line.text,
                indent,
                tuple(words.get(index, [])),
                initials_of(display, line.id),
                tuple(noted.get(index, [])),
                tuple(margin[index]),
                stanza_of(display, line.id),
                tuple(syllables.get(index, [])),
            )
        )
    return VersionView(
        part.name,
        part.label,
        part.type,
        tuple(lines),
        head,
        tuple(note for note, _ in notes),
        passages,
        lanes,
        metre is not None,
    )


def stanza_of(display: Schema, line_id: str) -> str | None:
    """The stanza a line sits in, if the display schema puts it in one."""
    parent = display.parent(display.unit(line_id))
    return (
        parent.local_id if parent is not None and parent.rank.name == "stanza" else None
    )


def metre_schema(version: Version) -> Schema | None:
    """The version's metrical reading, if it has one: the unqualified one before any qualified."""
    readings = sorted(
        (s for s in version.schemata.values() if s.kind.name == METRE),
        key=lambda s: (s.name != METRE, s.name),
    )
    return readings[0] if readings else None


def syllables_of(metre: Schema, version: Version) -> dict[int, list[Syllable]]:
    """Every syllable of the reading, by the line it starts in, with its place in foot and verse."""
    by_line: dict[int, list[Syllable]] = {}
    lines = version.substrate.lines
    for verse in metre.roots():
        feet = [
            [(s, version.substrate.text_of(s.span)) for s in metre.children(foot)]
            for foot in metre.children(verse)
        ]
        count = sum(len(foot) for foot in feet)
        number = 0
        for f, foot in enumerate(feet, start=1):
            # The foot as the metre file writes it: stressed syllables in capitals.
            written = " ".join(
                text.upper() if unit.value == "stressed" else text.lower()
                for unit, text in foot
            )
            for i, (unit, _) in enumerate(foot):
                number += 1
                start, end = unit.span.start, unit.span.end
                text = lines[start.line].text
                opens = ""
                if f > 1 and i == 0:
                    opens = (
                        "space"
                        if start.offset and text[start.offset - 1] == " "
                        else "in"
                    )
                by_line.setdefault(start.line, []).append(
                    Syllable(
                        start.offset,
                        end.offset if end.line == start.line else len(text),
                        unit.value == "stressed",
                        f,
                        len(feet),
                        number,
                        count,
                        written,
                        opens,
                    )
                )
    return by_line


def bracket_lanes(
    brackets: dict[str, dict], line_count: int
) -> tuple[int, list[list[tuple[str, int, bool, bool, str]]]]:
    """A lane in the margin for each bracketed passage, so that overlapping ones stand side by side.
    Passages are taken by first line, longest first, each into the first lane free by then: so an
    outer passage takes a lane before the passages inside it, and is drawn furthest out."""
    order = sorted(
        brackets.items(),
        key=lambda item: (item[1]["first"], item[1]["first"] - item[1]["last"]),
    )
    taken_to: list[int] = []  # each lane: the last line it is taken to
    margin: list[list[tuple[str, int, bool, bool, str]]] = [
        [] for _ in range(line_count)
    ]
    for key, bracket in order:
        first, last = bracket["first"], bracket["last"]
        lane = next((i for i, t in enumerate(taken_to) if t < first), len(taken_to))
        if lane == len(taken_to):
            taken_to.append(last)
        else:
            taken_to[lane] = last
        ids = " ".join(bracket["ids"])
        for index in range(first, last + 1):
            margin[index].append((key, lane, index == first, index == last, ids))
    return len(taken_to), margin


def read_notes(
    folder: Path, versions: dict[str, Version]
) -> dict[str, list[tuple[NoteView, tuple[Span, ...]]]]:
    """Every notes file in the work's annotations/ folder, resolved against the version its header
    names: for each version's name, its notes and the spans each covers."""
    files = sorted((folder / NOTES).glob(f"*{NOTES_SUFFIX}"))
    if not files:
        return {}
    parse, resolve = annotation_code()
    notes: dict[str, list[tuple[NoteView, tuple[Span, ...]]]] = {}
    number = 0
    for path in files:
        try:
            written = parse(path.read_text(encoding="utf-8-sig"))
            if written.version is None:
                raise SynthesisError("names no version: add a line 'version: <name>'")
            if written.version not in versions:
                known = ", ".join(versions)
                raise SynthesisError(
                    f"no version called {written.version} (this work's: {known})"
                )
            version = versions[written.version]
            annotations = resolve(written.annotations, version)
        except SynthesisError as error:
            raise ViewerError(f"{path}: {error}") from error
        for description, annotation in zip(written.annotations, annotations):
            number += 1
            spans = tuple(target.span for target in annotation.targets)
            note = NoteView(
                f"n{number}",
                description.row,
                path.name.removesuffix(NOTES_SUFFIX),
                " · ".join(shorten(version.substrate.text_of(span)) for span in spans),
                body_html(annotation.body),
                any(covers_all(span, version) for span in spans),
            )
            notes.setdefault(written.version, []).append((note, spans))
    return notes


def covers_all(span: Span, version: Version) -> bool:
    lines = version.substrate.lines
    return span.start == Position(0, 0) and span.end == Position(
        len(lines) - 1, len(lines[-1].text)
    )


def shorten(text: str) -> str:
    """A lemma: the text a target covers, its line breaks as /, and long ones cut in the middle."""
    words = " / ".join(text.splitlines()).split()
    if len(words) <= 9:
        return " ".join(words)
    return " ".join(words[:4]) + " … " + " ".join(words[-3:])


def body_html(body: str) -> str:
    """A note's body as HTML: its blank-line-separated paragraphs, each one flowing."""
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*\n", body) if p.strip()]
    return "".join(f"<p>{html.escape(p)}</p>" for p in paragraphs)


def initials_of(display: Schema, line_id: str) -> tuple[Initial, ...]:
    """The drop caps in a line: its highlights whose rendition is initial(n)."""
    initials = []
    for unit in display.children(display.unit(line_id)):
        match = INITIAL.fullmatch(unit.value or "")
        if unit.rank.name != "highlight" or not match:
            continue
        if not match.group(1).isdigit() or int(match.group(1)) < 1:
            raise ViewerError(
                f"{unit.local_id}: {unit.value} does not say how many lines it drops"
            )
        initials.append(
            Initial(unit.span.start.offset, unit.span.end.offset, int(match.group(1)))
        )
    return tuple(sorted(initials, key=lambda initial: initial.start))


# ── Pairing the words of two versions ───────────────────────────────────────────────────────────


def longest_common_subsequence(a: list[str], b: list[str]) -> list[tuple[int, int]]:
    """Index pairs of equal items, as many as possible, in order. Ties go to the earliest item."""
    rows, cols = len(a), len(b)
    table = [[0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            table[i][j] = (
                table[i + 1][j + 1] + 1
                if a[i] == b[j]
                else max(table[i + 1][j], table[i][j + 1])
            )
    pairs, i, j = [], 0, 0
    while i < rows and j < cols:
        if a[i] == b[j]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif table[i + 1][j] >= table[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def kind_of(a: list[Word], b: list[Word]) -> str:
    if not a:
        return "only-b"
    if not b:
        return "only-a"
    return "same" if [w.text for w in a] == [w.text for w in b] else "different"


def pair_lines(a: LineView | None, b: LineView | None) -> list[dict]:
    """Groups of corresponding words in one pair of lines, as {"a": ids, "b": ids, "kind": …}."""
    groups: list[dict] = []

    def add(words_a: list[Word], words_b: list[Word]) -> None:
        if words_a or words_b:
            groups.append(
                {
                    "a": [w.id for w in words_a],
                    "b": [w.id for w in words_b],
                    "kind": kind_of(words_a, words_b),
                }
            )

    def add_gap(words_a: list[Word], words_b: list[Word]) -> None:
        if len(words_a) == len(words_b):
            for word_a, word_b in zip(words_a, words_b):
                add([word_a], [word_b])
        else:
            add(words_a, words_b)

    words_a, words_b = list(a.words) if a else [], list(b.words) if b else []
    previous_a = previous_b = 0
    for i, j in longest_common_subsequence(
        [w.key for w in words_a], [w.key for w in words_b]
    ):
        add_gap(words_a[previous_a:i], words_b[previous_b:j])
        add([words_a[i]], [words_b[j]])
        previous_a, previous_b = i + 1, j + 1
    add_gap(words_a[previous_a:], words_b[previous_b:])
    return groups


def pair_versions(a: VersionView, b: VersionView) -> list[dict]:
    """Groups of corresponding words across two whole versions, lines paired by id."""
    lines_a = {line.id: line for line in a.lines}
    lines_b = {line.id: line for line in b.lines}
    line_ids = list(lines_a) + [
        line_id for line_id in lines_b if line_id not in lines_a
    ]
    return [
        group
        for line_id in line_ids
        for group in pair_lines(lines_a.get(line_id), lines_b.get(line_id))
    ]


# ── The page ────────────────────────────────────────────────────────────────────────────────────


def render_version(view: VersionView) -> str:
    """A version as HTML: its head, then its lines, each word a span carrying its id and
    everything else plain text. Numbered versions carry every fifth line's number after it; a
    version with a metrical reading carries each syllable's scansion, and each line's syllable count,
    for the Metre key to show. A gap separates stanzas, crossed by the brackets that run on."""
    numbered = view.type in NUMBERED_TYPES
    rows = []
    for number, line in enumerate(view.lines, start=1):
        previous = view.lines[number - 2] if number > 1 else None
        if previous and line.stanza != previous.stanza:
            running = {key for key, *_ in previous.margin}
            rules = "".join(
                rule(key, lane, False, False, ids)
                for key, lane, top, _, ids in line.margin
                if key in running and not top
            )
            rows.append(
                f'<div class="gap"><span class="gs"></span><span class="mg">{rules}</span></div>'
            )
        parts, cursor = [], 0
        for word in line.words:
            parts.append(scanned(line, cursor, word.start))
            parts.append(
                f'<span class="w" data-w="{word.id}" tabindex="0">{scanned(line, word.start, word.end)}</span>'
            )
            cursor = word.end
        parts.append(scanned(line, cursor, len(line.text)))
        indent = f' style="--indent:{line.indent:g}"' if line.indent else ""
        shown = number if numbered and number % NUMBER_EVERY == 0 else ""
        rules = "".join(rule(*bracket) for bracket in line.margin)
        count = (
            f'<span class="sc">{line.syllables[0].count}</span>'
            if line.syllables
            else ""
        )
        rows.append(
            f'<div class="line"><span class="lt"{indent}>{"".join(parts)}</span>'
            f'<span class="mg">{rules}</span><span class="ln">{shown}</span>{count}</div>'
        )
    head = f'<h2 class="head">{html.escape(view.head)}</h2>' if view.head else ""
    metre = " has-metre" if view.metre else ""
    return (
        f'<div class="text{metre}" style="--lanes:{view.lanes}">'
        + head
        + "\n".join(rows)
        + "</div>"
    )


def rule(key: str, lane: int, top: bool, end: bool, ids: str) -> str:
    """One line's part of a margin bracket: with its top tick on its first line, its foot on its last."""
    return (
        f'<span class="rule{" top" if top else ""}{" end" if end else ""}" '
        f'data-pass="{key}" data-n="{ids}" style="--lane:{lane}"></span>'
    )


def scanned(line: LineView, start: int, end: int) -> str:
    """The line's text from start to end, as marked() gives it, each syllable set apart for the
    scansion marks. A syllable the range cuts carries its marks on the piece where it begins."""
    parts, cursor = [], start
    for syllable in line.syllables:
        first, last = max(syllable.start, start), min(syllable.end, end)
        if first >= last:
            continue
        parts.append(marked(line, cursor, first))
        data = ""
        if first == syllable.start:
            stress = "stressed" if syllable.stressed else "unstressed"
            about = (
                f"{line.id} · foot {syllable.foot} of {syllable.feet}: {syllable.foot_text}"
                f" · syllable {syllable.number} of {syllable.count}, {stress}"
            )
            data = f' data-s="{int(syllable.stressed)}" data-m="{html.escape(about)}"'
            if syllable.opens_foot:
                data += f' data-ft="{syllable.opens_foot}"'
        parts.append(f'<span class="sy"{data}>{marked(line, first, last)}</span>')
        cursor = last
    parts.append(marked(line, cursor, end))
    return "".join(parts)


def marked(line: LineView, start: int, end: int) -> str:
    """The line's text from start to end, escaped: cut wherever a drop cap or a noted stretch
    begins or ends, each piece set apart as what it is (a drop cap, noted by some notes, or both)."""
    edges = {start, end}
    edges.update(e for i in line.initials for e in (i.start, i.end))
    edges.update(e for s, f, *_ in line.notes for e in (s, f))
    cuts = sorted(e for e in edges if start <= e <= end)
    parts = []
    for first, last in pairwise(cuts):
        piece = html.escape(line.text[first:last])
        for initial in line.initials:
            if initial.start <= first and last <= initial.end:
                piece = (
                    f'<span class="initial" data-drop="{initial.lines}">{piece}</span>'
                )
        on = [
            (n, key, size, inline)
            for s, f, n, key, size, inline in line.notes
            if s <= first and last <= f
        ]
        if on:
            ids = " ".join(dict.fromkeys(n for n, *_ in on))
            found = " ".join(f"{key}|{size}|{n}" for n, key, size, _ in on)
            inline = len(
                {key for _, key, _, i in on if i}
            )  # passages within the line here
            kind = "an u" if inline else "an"
            depth = min(len({key for _, key, _, _ in on}), 4)  # every passage here
            piece = (
                f'<span class="{kind}" data-n="{ids}" data-p="{found}" '
                f'data-k="{min(inline, 2)}" data-d="{depth}">{piece}</span>'
            )
        parts.append(piece)
    return "".join(parts)


def render_facsimile(path: Path, title: str) -> str:
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    mime = IMAGE_TYPES[path.suffix.lower()]
    return f'<figure class="facsimile"><img src="data:{mime};base64,{data}" alt="Facsimile of {html.escape(title)}"></figure>'


def font_faces() -> str:
    """@font-face rules for Libertinus, each font embedded as a data URI so the page stands alone."""
    rules = []
    for weight, name in FONT_FILES.items():
        data = base64.b64encode((FONTS / name).read_bytes()).decode("ascii")
        rules.append(
            f"@font-face {{ font-family: Libertinus; font-weight: {weight}; font-style: normal; "
            f'font-display: swap; src: url("data:font/woff2;base64,{data}") format("woff2"); }}'
        )
    return "\n".join(rules)


def page_data(work: Work, facsimile: Path | None, views: list[VersionView]) -> dict:
    """Everything a page needs, in the form its script reads: each source's HTML, its label, the
    word pairs between every two versions, and the notes. Shared by the desktop and mobile pages."""
    sources: dict[str, str] = {}
    if facsimile:
        sources["facsimile"] = render_facsimile(facsimile, work.title)
    for view in views:
        sources[view.name] = render_version(view)

    pairs = {
        f"{a.name}|{b.name}": pair_versions(a, b) for a, b in combinations(views, 2)
    }
    text_names = [view.name for view in views]
    left = text_names[0]
    right = (
        text_names[1]
        if len(text_names) > 1
        else ("facsimile" if facsimile else text_names[0])
    )

    labels = {view.name: view.label for view in views} | {"facsimile": "Facsimile"}
    # The sources travel inside the script, as strings: a browser's "Save page as… Complete" writes
    # the page as it stands, and would drop the contents of <template> elements.
    return {
        "texts": text_names,
        "pairs": pairs,
        "left": left,
        "right": right,
        "sources": sources,
        "labels": labels,
        "notes": {
            view.name: [
                {
                    "id": n.id,
                    "row": n.row,
                    "source": n.source,
                    "lemma": n.lemma,
                    "body": n.body,
                    "whole": n.whole,
                }
                for n in view.notes
            ]
            for view in views
            if view.notes
        },
        "passages": {view.name: view.passages for view in views if view.passages},
        "metre": [view.name for view in views if view.metre],
    }


def script_json(data: dict) -> str:
    """Data for a page's script: JSON, with every "</" escaped so no text can close the script."""
    return json.dumps(data, ensure_ascii=False).replace("</", "<\\/")


def build_page(
    work: Work, facsimile: Path | None, views: list[VersionView], style: str = "sepia"
) -> str:
    """The desktop page: two columns, notes marked in the given style."""
    title = work.title
    data = page_data(work, facsimile, views)
    options = "".join(
        f'<option value="{html.escape(name)}">{html.escape(data["labels"][name])}</option>'
        for name in data["sources"]
    )
    script_data = script_json(data)
    return (
        PAGE.replace("%FONTS%", font_faces())
        .replace("%TAB%", html.escape(" · ".join(filter(None, [title, work.author]))))
        .replace("%TITLE%", html.escape(title))
        .replace(
            "%BYLINE%",
            f"<small>{html.escape(work.author)}</small>" if work.author else "",
        )
        .replace("%OPTIONS%", options)
        .replace("%STYLE%", style)
        .replace("%DATA%", script_data)
    )


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>%TAB%</title>
<style>
/* After Geist (gitlab.lrz.de/badw-it/geist), as in the MIAS Archive: white sheets on grey paper,
   soft blue shadows instead of borders, Libertinus, keys that glow when hovered. */
%FONTS%
:root {
  --paper: #f0f0f0; --sheet: #ffffff; --ink: #000000; --fade: #666666;
  --editor: #3050b0;                     /* the editor's hand: line numbers */
  --edge: #b0c0e0;                       /* the shadow a sheet casts */
  --glow: #66afff;                       /* hovered, focused, linked */
  --key: #f7f8ff; --key-edge: #aaafff; --key-down: #b8c8f8;
  --dark: #002266; --dark-ink: #e8f8ff;  /* a key that is on */
  --th: #dfe2f6; --row: #f4f4f6; --row-lit: #ecf3fe;
  --differs: #cc0000;
  --bar: 2.1em;                          /* the bar along the bottom */
  --drawer: min(42vh, 26em);             /* the differences drawer, when open */
  --gutter: max(20px, calc((100vw - 1240px) / 2));  /* lines the drawer up with the page */
  --serif: Libertinus, "Libertinus Serif", "Linux Libertine O", "Palatino Linotype", Georgia, serif;
}
::selection { background-color: #a4c5ff; }
* { box-sizing: border-box; }
.w, select, .drawer-tab, .toggle, .drawer .close, .drawer tbody tr {
  transition: background-color .2s ease-out, box-shadow .2s ease-out, color .2s ease-out, opacity .2s ease-out;
}
html { background: var(--paper); color: var(--ink); font: 19px/1.32 var(--serif); }
body { margin: 0; background: var(--paper); }
main { max-width: 1280px; margin: 0 auto; padding: 1.4em 20px 5em; }
h1 { font-size: 1.76em; font-weight: normal; line-height: 1.2; margin: 0 0 .2em; }
h1 small { display: block; margin-top: .15em; font-size: .55em; color: var(--fade); }  /* the author, as in Geist */

hr { height: 4px; margin: .7em 0 1.1em; border: 0; border-top: 1px solid #e8e8ef; border-bottom: 2px solid #f8f8f8;
  background: #e0e0e8; }
/* Two columns of exactly equal width (minmax(0, 1fr): long lines scroll inside, never widen a
   column), on the page itself, with a rule between them that runs as long as the longer one. Each
   column's edition is chosen at its top; the text then runs on for as long as it is. */
.panes { display: grid; grid-template-columns: minmax(0, 1fr) minmax(0, 1fr); align-items: stretch; }
.pane { display: flex; flex-direction: column; min-width: 0; padding: 0 2.2em 0 0; }
.pane + .pane { padding: 0 0 0 2.2em; border-left: 1.2px solid var(--edge); }
.pane header { display: flex; gap: .6em; align-items: baseline; margin-bottom: 1.2em; }
.pane header label { color: var(--fade); font-variant-caps: all-small-caps; letter-spacing: .06em; }
select { font: inherit; color: inherit; background: var(--sheet); border: 0; padding: 0 3px; max-width: 12em;
  box-shadow: 0 0 2px 0 var(--key-edge) inset; cursor: pointer; }
select:hover, select:focus { outline: none; box-shadow: 0 0 2px 1px var(--glow) inset; }
.content { flex: 1; overflow-x: auto; padding: 0 0 .4em 1.2em; }
.live { display: flex; flex-direction: column; min-width: 0; }
/* The lines in one column, as wide as the longest; the line numbers in a narrow column to its right. */
.text { display: grid; grid-template-columns: max-content auto 1.5em auto; align-items: baseline; line-height: 1.8; }
/* Between stanzas, a gap; brackets that run on cross it. */
.gap { display: contents; }
.gap .gs { grid-column: 1; height: .9em; }
.line { display: contents; }
.head { grid-column: 1; margin: 0 0 .4em; font-size: 1.2em; font-weight: normal; text-align: center; }  /* centred over the lines */
.lt { grid-column: 1; position: relative; white-space: pre; padding-left: calc(var(--indent, 0) * 2em); }
/* A drop cap. Until the page has measured it (setInitials) it is an ordinary letter; then it is
   lifted out of the line, sized to reach down the lines it drops, and those lines move aside. */
.initial.dropped { position: absolute; left: 0; top: 0; line-height: 1; }
.w.lit .initial.dropped { text-shadow: 0 0 6px var(--glow); }
.probe { display: inline-block; width: 0; height: 0; }  /* sits on the baseline: see baseline() */
.ln { grid-column: 3; color: var(--editor); font-size: .75em; text-align: right; }
/* The margin between a line and its number: brackets for notes on whole lines (see Notes, below). */
.mg { grid-column: 2; align-self: stretch; position: relative; width: calc(var(--lanes, 0) * var(--lane-width));
  margin-left: calc(min(var(--lanes, 0), 1) * .4em); }
/* The facsimile sits at the top of its column, in the middle; it shrinks to fit, but is never
   enlarged beyond its own size. */
.facsimile { margin: 0; display: flex; justify-content: center; }
.facsimile img { display: block; max-width: 100%; max-height: 80vh; width: auto; height: auto;
  background: #fff; border: 1px solid #c8ccd1; padding: 2px; border-radius: 2px; box-shadow: 0 1px 2px rgba(0, 0, 0, .06); }
.w { outline: none; }
.show-diff .w.differs { text-decoration: underline dotted var(--differs); text-decoration-thickness: 1.5px;
  text-underline-offset: .2em; }
.w.lit { background: var(--sheet); box-shadow: 0 0 6px 1.5px var(--glow); }
.w:focus-visible { box-shadow: 0 0 0 2px var(--glow); }
/* The tally of the two texts' words, just under the panes. */
.tally { color: var(--fade); text-align: center; margin: .8em 0 0; min-height: 1.32em; }
.tally b { color: var(--ink); font-weight: 600; }
/* The differences: a drawer that slides up from behind the bar, opened and closed by a key at the
   bar's right end. The key is there only when two different texts face each other. While the
   drawer is open the page gains room at its foot, so the poems can be scrolled clear of it. */
.drawer-tab { flex: none; display: flex; align-items: baseline; gap: .5em; padding: .1em .8em; font: inherit;
  color: var(--ink); cursor: pointer; border: 0; background: var(--key);
  box-shadow: 0 0 0 1px #ffffff inset, 0 0 3px 0 var(--key-edge); }
.drawer-tab[hidden] { display: none; }
.drawer-tab + .drawer-tab { margin-left: .6em; }
.drawer-tab::before { content: "▲"; color: #707070; font-size: .7em; }  /* Geist's arrows */
.drawer-tab[aria-expanded="true"]::before { content: "▼"; }
.drawer-tab:hover, .drawer-tab:focus-visible { outline: none; background: var(--sheet);
  box-shadow: 0 0 0 1px #ffffff inset, 0 0 6px 1.5px var(--glow); }
.drawer-tab .count, .drawer .count { color: var(--fade); font-size: .8em; }
.drawer { position: fixed; left: 0; right: 0; bottom: var(--bar); z-index: 2; height: var(--drawer); display: flex;
  flex-direction: column; background: var(--sheet); box-shadow: 0 0 3px 0 var(--edge), 0 -6px 18px rgba(40, 68, 144, .10);
  transform: translateY(calc(100% + var(--bar))); visibility: hidden; transition: transform .25s ease-out, visibility 0s .25s; }
.drawer.open { transform: none; visibility: visible; transition: transform .25s ease-out; }
body.drawer-open main { padding-bottom: calc(var(--drawer) + 3em); }
/* The drawer runs the width of the window; what is in it lines up with the page above. */
.drawer header { display: flex; align-items: baseline; gap: .6em; padding: .45em var(--gutter) .4em;
  border-bottom: 1.2px solid var(--edge); }
.drawer h2 { margin: 0; font-size: 1.2em; font-weight: normal; }
.drawer .close { margin-left: auto; font: inherit; color: #707070; background: none; border: 0; cursor: pointer; padding: 0 .3em; }
.drawer .close:hover, .drawer .close:focus-visible { outline: none; color: var(--ink); box-shadow: 0 0 6px 1.5px var(--glow); }
.drawer .body { flex: 1; overflow: auto; padding: 0 var(--gutter); scroll-padding-top: 2em; }  /* clear of the headings */
.drawer table { width: 100%; border-collapse: collapse; }
.drawer th { position: sticky; top: 0; text-align: left; padding: 2px 1.1em; background: var(--th); font-size: .85em;
  font-weight: normal; border-right: 1px solid #ffffff; white-space: nowrap; }
.drawer td { padding: .2em 1.1em; border-top: 1px solid #e8e8ef; vertical-align: baseline; }
.drawer td.lnum { width: 5em; color: var(--editor); font-size: .8em; }
.drawer td.none { color: var(--fade); }
.drawer tbody tr { cursor: default; }
.drawer tbody tr:hover { background: var(--row); }
.drawer tbody tr.lit { background: var(--row-lit); }
/* Notes, in sepia: the ink of pencil marginalia, apart from the editor's blue (the apparatus) and
   red (variants). With the notes open, passages of whole lines are bracketed in the margin, nested
   brackets side by side and the outermost furthest out; passages within a line are underlined,
   more heavily where two meet. Neither touches the letters, so reading is undisturbed. The passage
   chosen (clicked, or its note hovered) darkens in the margin and is highlighted in the text. */
:root { --note: #c9a35f; --note-faint: #dcc59a; --note-deep: #8a5a1c; --note-paper: #f7e9c4; }
:root { --lane-width: 11px; }  /* each bracket's lane: the whole lane can be clicked */
.rule { position: absolute; top: 0; bottom: 0; width: var(--lane-width); visibility: hidden; cursor: pointer;
  left: calc((var(--lanes) - 1 - var(--lane)) * var(--lane-width));
  --ink: var(--note); --stroke: 1.5px;  /* the drawn line: thin, in the middle of its lane */
  background: linear-gradient(var(--ink), var(--ink)) center / var(--stroke) 100% no-repeat; }
.rule.top { top: .55em; }
.rule.end { bottom: .55em; }
.rule.top::before, .rule.end::after { content: ""; position: absolute; right: 50%; width: 5px; height: var(--stroke);
  background: var(--ink); }  /* the bracket's ticks, turned toward the line */
.rule.top::before { top: 0; }
.rule.end::after { bottom: 0; }
.show-notes .rule { visibility: visible; }
.show-notes .rule:hover { --ink: var(--note-deep); }
.show-notes .rule.sel, .show-notes .rule.lit-note { --ink: var(--note-deep); --stroke: 2.5px; }
.show-notes .an { cursor: pointer; }
.notes-sepia .show-notes .an.u { text-decoration: underline var(--note-faint) 1px; text-underline-offset: .24em; }
.notes-sepia .show-notes .an.u[data-k="2"] { text-decoration-color: var(--note); text-decoration-thickness: 2px; }
.notes-sepia .show-notes .an.sel, .notes-sepia .show-notes .an.lit-note { background: var(--note-paper);
  text-decoration-color: var(--note-deep); }
/* The blue page: no margin; every passage washed in the editor's blue, deeper where more notes overlap.
   The passage chosen (clicked, or its note hovered) is washed deeper still. */
.notes-blue .mg { display: none; }
.notes-blue .show-notes .an { background: rgba(48, 80, 176, var(--wash)); border-radius: 2px; }
.notes-blue .an[data-d="1"] { --wash: .07; } .notes-blue .an[data-d="2"] { --wash: .13; }
.notes-blue .an[data-d="3"] { --wash: .19; } .notes-blue .an[data-d="4"] { --wash: .25; }
.notes-blue .show-notes .an.sel, .notes-blue .show-notes .an.lit-note { background: rgba(48, 80, 176, .5); }
.notes-list { max-width: 82ch; padding: .3em 0 1em; }
.notes-list h3 { margin: 1em 0 .2em; font-size: .85em; font-weight: normal; color: var(--fade);
  font-variant-caps: all-small-caps; letter-spacing: .06em; }
.nt { padding: .6em .8em; border-top: 1px solid #e8e8ef; cursor: pointer; }
.notes-sepia .nt:hover { background: #fbf6ea; }
.notes-sepia .nt.lit { background: #fbf6ea; box-shadow: inset 3px 0 0 var(--note-deep); }
.notes-blue .nt:hover, .notes-blue .nt.lit { background: var(--row-lit); }
.nt .lemma { margin: 0 0 .3em; }
.nt .lemma i { font-style: italic; }
.nt p { margin: 0 0 .5em; line-height: 1.45; }
/* Scansion, while the Metre key is on, in a version with a metrical reading: over each syllable a
   stress (ˊ) or a slack (˘), in the editor's blue, and a hairline where a foot begins; after each line,
   how many syllables its verse has. The marks sit in the room the taller lines give above the letters,
   so the text itself is untouched. */
.sy { position: relative; }
.sc { grid-column: 4; display: none; padding-left: 1.1em; color: #9a9a9a; font-size: .68em; font-style: italic;
  font-variant-numeric: tabular-nums; }
.show-metre .has-metre { line-height: 2.25; }
.show-metre .has-metre .sc { display: block; }
.show-metre .has-metre .rule.top { top: .78em; }
.show-metre .has-metre .rule.end { bottom: .78em; }
.show-metre .sy[data-s]::before { position: absolute; left: 50%; top: -.28em; transform: translateX(-50%);
  font-size: 1.15em; line-height: 1; text-indent: 0; color: var(--editor); pointer-events: none; }
.show-metre .sy[data-s="1"]::before { content: "\\02CA"; }
.show-metre .sy[data-s="0"]::before { content: "\\02D8"; color: #8a9bc8; }
.show-metre .sy[data-ft]::after { content: ""; position: absolute; top: -.18em; height: .32em;
  border-left: 1px solid #9fb0dc; pointer-events: none; }
.show-metre .sy[data-ft="in"]::after { left: -.5px; }
.show-metre .sy[data-ft="space"]::after { left: -.16em; }  /* in the middle of the space before */
.toggle { flex: none; margin-left: .6em; padding: .1em .8em; font: inherit; color: var(--ink); cursor: pointer;
  border: 0; background: var(--key); box-shadow: 0 0 0 1px #ffffff inset, 0 0 3px 0 var(--key-edge); }
.toggle[hidden] { display: none; }
.toggle + .drawer-tab { margin-left: .6em; }
.toggle:hover, .toggle:focus-visible { outline: none; background: var(--sheet);
  box-shadow: 0 0 0 1px #ffffff inset, 0 0 6px 1.5px var(--glow); }
.toggle[aria-pressed="true"] { background: var(--dark); color: var(--dark-ink); box-shadow: 0 0 0 1px var(--dark); }
.toggle[aria-pressed="true"]:hover, .toggle[aria-pressed="true"]:focus-visible { background: var(--dark);
  box-shadow: 0 0 6px 1.5px var(--glow); }
@media (prefers-reduced-motion: reduce) { .w, select, .drawer, .drawer-tab, .drawer .close, .drawer tbody tr { transition: none; } }
.note { color: var(--fade); font-size: .8em; margin-top: 1.4em; max-width: 80ch; }
/* The bar along the bottom: what is hovered. */
.bar { position: fixed; left: 0; right: 0; bottom: 0; z-index: 3; height: var(--bar); display: flex; align-items: center; padding: 0 20px;
  background: var(--sheet); box-shadow: 0 0 3px 0 var(--edge); }
.status { flex: 1; min-width: 0; min-height: 1.32em; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: var(--fade); }
.status .pair { color: var(--ink); }
.status .kind { margin-left: .8em; font-size: .8em; }
/* On a narrow screen the columns stack, and the rule between them lies across. */
@media (max-width: 860px) {
  .panes { grid-template-columns: minmax(0, 1fr); }
  .pane { padding: 0; }
  .pane + .pane { padding: 1.2em 0 0; margin-top: 1.2em; border-left: 0; border-top: 1.2px solid var(--edge); }
}
</style>
</head>
<body class="notes-%STYLE%">
<main>
  <h1>%TITLE%%BYLINE%</h1>
  <hr>
  <div class="panes" id="panes">
    <section class="pane" data-side="left">
      <header><label for="pick-left">Edition</label><select id="pick-left" aria-label="Left edition">%OPTIONS%</select></header>
      <div class="content"><div class="live"></div></div>
    </section>
    <section class="pane" data-side="right">
      <header><label for="pick-right">Edition</label><select id="pick-right" aria-label="Right edition">%OPTIONS%</select></header>
      <div class="content"><div class="live"></div></div>
    </section>
  </div>
  <p class="tally" id="tally"></p>
  <p class="note">Choose what each side shows. When both sides show a text, hover or focus a word to see its
  counterpart. Words are paired line by line, after setting aside case, accents, long s, u/v and apostrophes;
  words left over between pairings are paired with each other. A prototype of loom's collation.</p>
</main>
<aside class="drawer" id="differences" aria-labelledby="drawer-title">
  <header>
    <h2 id="drawer-title">Differences</h2><span class="count" id="drawer-count"></span>
    <button type="button" class="close" id="diff-close" aria-label="Close the drawer">✕</button>
  </header>
  <div class="body">
    <table id="diff-table">
      <thead><tr><th>Line</th><th id="th-left"></th><th id="th-right"></th></tr></thead>
      <tbody id="diff-rows"></tbody>
    </table>
    <div class="notes-list" id="notes-list" hidden></div>
  </div>
</aside>
<div class="bar">
  <div class="status" id="status" aria-live="polite"></div>
  <button type="button" class="toggle" id="metre-key" aria-pressed="false" hidden>Metre</button>
  <button type="button" class="drawer-tab" id="notes-tab" aria-expanded="false" aria-controls="differences" hidden>
    Notes<span class="count" id="notes-count"></span>
  </button>
  <button type="button" class="drawer-tab" id="diff-tab" aria-expanded="false" aria-controls="differences" hidden>
    See differences<span class="count" id="diff-count"></span>
  </button>
</div>
<script>
const DATA = %DATA%;
const panes = { left: document.querySelector('[data-side="left"]'), right: document.querySelector('[data-side="right"]') };
const picks = { left: document.getElementById("pick-left"), right: document.getElementById("pick-right") };
const panesBox = document.getElementById("panes");
const status = document.getElementById("status");
const tally = document.getElementById("tally");
const differences = document.getElementById("differences");  // the drawer
const diffTab = document.getElementById("diff-tab");
const diffClose = document.getElementById("diff-close");
const drawerCount = document.getElementById("drawer-count");
const diffRows = document.getElementById("diff-rows");
const diffCount = document.getElementById("diff-count");
const KIND = { same: "identical", different: "differs", "only-a": "no counterpart", "only-b": "no counterpart" };
let lookup = { left: new Map(), right: new Map() };  // word id → its group, seen from that side
let current = null;  // the groups from left to right, when two different texts are shown
let lit = [];
let drawerOpen = false;  // the drawer: closed until a key is pressed
let drawerMode = "differences";  // what it shows: "differences" or "notes"
const notesTab = document.getElementById("notes-tab");
const notesCount = document.getElementById("notes-count");
const notesList = document.getElementById("notes-list");
const diffTable = document.getElementById("diff-table");
const drawerTitle = document.getElementById("drawer-title");
let litNotes = [];
const metreKey = document.getElementById("metre-key");
let metreOn = false;  // scansion: off until the key is pressed
const METRE_HINT = "Metre: ˊ stressed, ˘ unstressed, a hairline where a foot begins; after each line, its syllables. Hover a syllable for its foot.";

function isText(name) { return DATA.texts.includes(name); }

// The Metre key is there while either side shows a version with a metrical reading; pressed, it
// shows the scansion of each such version. The taller lines it needs move drop caps, so they are
// measured again.
function updateMetre() {
  const available = [picks.left.value, picks.right.value].some(name => DATA.metre.includes(name));
  metreKey.hidden = !available;
  metreKey.setAttribute("aria-pressed", String(metreOn && available));
  panesBox.classList.toggle("show-metre", metreOn && available);
}

function showScansion(target) {
  if (!panesBox.classList.contains("show-metre") || panesBox.classList.contains("show-notes")) return;
  const syllable = target.closest(".sy[data-m]");
  if (syllable) status.textContent = syllable.dataset.m;
}
function lineOf(wordId) { return wordId.slice(0, wordId.lastIndexOf(".")); }
function textOf(side, ids) {
  return ids.map(id => panes[side].querySelector(`.live [data-w="${id}"]`)?.textContent ?? "").join(" ");
}

// The groups linking two texts, oriented so that "mine" is this side's words and "other" the other side's.
function groupsFor(mine, other) {
  if (mine === other) return null;  // the same text on both sides: every word is its own counterpart
  const forward = DATA.pairs[mine + "|" + other];
  if (forward) return forward.map(g => ({ mine: g.a, other: g.b, kind: g.kind }));
  return DATA.pairs[other + "|" + mine].map(g => ({ mine: g.b, other: g.a, kind: g.kind }));
}

// Drop caps. An initial(n) sinks into n lines: its top level with the capitals of its own line,
// its foot on the baseline of the n-th, and those n lines moved aside for it. The sizes are measured
// on the page, so this runs after each render and again once the fonts are in.
const measure = document.createElement("canvas").getContext("2d");
function baseline(el) {
  // An empty inline-block's bottom edge is the baseline it sits on.
  const probe = document.createElement("span");
  probe.className = "probe";
  el.append(probe);
  const y = probe.getBoundingClientRect().bottom;
  probe.remove();
  return y;
}
function setInitials(root) {
  root.querySelectorAll(".lt.beside").forEach(lt => { lt.classList.remove("beside"); lt.style.marginLeft = ""; });
  for (const cap of root.querySelectorAll(".initial")) {
    cap.classList.remove("dropped");
    cap.removeAttribute("style");
    const first = cap.closest(".lt");
    const lines = [...first.closest(".text").querySelectorAll(".lt")];
    const covered = lines.slice(lines.indexOf(first), lines.indexOf(first) + Number(cap.dataset.drop));
    const style = getComputedStyle(first), size = parseFloat(style.fontSize);
    measure.font = `${style.fontWeight} ${size}px ${style.fontFamily}`;
    const capHeight = measure.measureText(cap.textContent).actualBoundingBoxAscent / size;  // per unit of font size
    const top = baseline(first) - capHeight * size, foot = baseline(covered[covered.length - 1]);

    cap.classList.add("dropped");
    cap.style.fontSize = `${(foot - top) / capHeight}px`;
    cap.style.top = `${foot - baseline(cap)}px`;
    const width = cap.getBoundingClientRect().width + 0.25 * size;
    cap.style.left = `${-width}px`;
    covered.forEach(lt => { lt.classList.add("beside"); lt.style.marginLeft = `${width}px`; });
  }
}

// A source (a text, or the facsimile) as fresh nodes, from its HTML in DATA.sources.
function sourceOf(name) {
  const template = document.createElement("template");
  template.innerHTML = DATA.sources[name];
  return template.content;
}

function render() {
  updateMetre();
  for (const side of ["left", "right"]) {
    panes[side].querySelector(".live").replaceChildren(sourceOf(picks[side].value));
    setInitials(panes[side].querySelector(".live"));
  }
  const left = picks.left.value, right = picks.right.value;
  lookup = { left: new Map(), right: new Map() };
  current = null;
  if (isText(left) && isText(right)) {
    current = groupsFor(left, right);
    if (current) {
      for (const g of current) {
        g.mine.forEach(id => lookup.left.set(id, g));
        const back = { mine: g.other, other: g.mine, kind: g.kind, source: g };
        g.other.forEach(id => lookup.right.set(id, back));
      }
      const counts = { same: 0, different: 0, only: 0 };
      current.forEach(g => g.kind === "same" ? counts.same++ : g.kind === "different" ? counts.different++ : counts.only++);
      tally.innerHTML = `<b>${counts.same}</b> words identical · <b>${counts.different}</b> differ · <b>${counts.only}</b> without a counterpart`;
    } else {
      tally.textContent = "The same text on both sides.";
    }
    for (const side of ["left", "right"]) {
      panes[side].querySelectorAll(".live .w").forEach(w => {
        const g = lookup[side].get(w.dataset.w);
        w.classList.toggle("differs", Boolean(g && g.kind !== "same"));
      });
    }
    status.textContent = "Hover a word to see its counterpart.";
  } else {
    tally.textContent = "";
    status.textContent = "Words are linked when both sides show a text.";
  }
  lit = [];
  clearDrill();
  updateDifferences();
  updateNotes();
}

// The drawer, its tab, the highlighting in the panes, and the table: all follow whether the drawer
// is open, and the current pair. The tab is there only when two different texts face each other
// (not a facsimile, nor the same text twice); the drawer remembers being open while it is away, and
// its table and count are kept up to date even while it is closed.
function updateDifferences() {
  const applicable = Boolean(current);
  const open = drawerOpen && drawerMode === "differences" && applicable;
  diffTab.hidden = !applicable;
  diffTab.setAttribute("aria-expanded", String(open));
  panesBox.classList.toggle("show-diff", open);
  showDrawer();
  if (!applicable) return;

  document.getElementById("th-left").textContent = DATA.labels[picks.left.value];
  document.getElementById("th-right").textContent = DATA.labels[picks.right.value];
  const cell = (text, kind) => {
    const td = document.createElement("td");
    td.className = text ? kind : kind + " none";
    td.textContent = text || "—";
    return td;
  };
  const rows = current.filter(g => g.kind !== "same").map(g => {
    const row = document.createElement("tr");
    row.append(cell(lineOf(g.mine[0] ?? g.other[0]), "lnum"), cell(textOf("left", g.mine), "word"), cell(textOf("right", g.other), "word"));
    row.addEventListener("mouseenter", () => g.mine.length ? light("left", g.mine[0]) : light("right", g.other[0]));
    row.addEventListener("mouseleave", () => light("left", null));
    g.row = row;
    return row;
  });
  diffRows.replaceChildren(...rows);
  diffCount.textContent = drawerCount.textContent = String(rows.length);
}

// Notes: those on the versions the two sides show. Listed in the drawer, each as a commentary entry
// (its lemma, then its text); notes on the whole poem first. Hovering a note lights its passages;
// clicking a washed passage brings its notes into view.
function shownNotes() {
  const names = [...new Set([picks.left.value, picks.right.value])].filter(n => DATA.notes[n]);
  return names.map(name => ({ name, notes: DATA.notes[name] }));
}

function updateNotes() {
  const groups = shownNotes();
  const count = groups.reduce((sum, g) => sum + g.notes.length, 0);
  const open = drawerOpen && drawerMode === "notes" && count > 0;
  notesTab.hidden = count === 0;
  notesTab.setAttribute("aria-expanded", String(open));
  notesCount.textContent = String(count);
  panesBox.classList.toggle("show-notes", open);
  if (!open) clearDrill();
  if (open && !drill && !fixedNote) status.textContent = HINT;
  showDrawer();
  const sections = [];
  for (const { name, notes } of groups) {
    const whole = notes.filter(n => n.whole), parts = notes.filter(n => !n.whole);
    if (groups.length > 1) sections.push(heading(`Notes on ${DATA.labels[name]}`));
    if (whole.length) sections.push(heading("On the whole poem"), ...whole.map(entry));
    if (parts.length) sections.push(heading("On passages"), ...parts.map(entry));
  }
  notesList.replaceChildren(...sections);
}

function heading(text) {
  const h = document.createElement("h3");
  h.textContent = text;
  return h;
}

function entry(note) {
  const article = document.createElement("article");
  article.className = "nt";
  article.dataset.id = note.id;
  const lemma = document.createElement("p");
  lemma.className = "lemma";
  const quoted = document.createElement("i");
  quoted.textContent = note.whole ? "the whole poem" : note.lemma;
  lemma.append(quoted, " ]");
  article.append(lemma);
  article.insertAdjacentHTML("beforeend", note.body);
  article.addEventListener("mouseenter", () => lightNotes([note.id]));
  article.addEventListener("mouseleave", () => lightNotes([]));
  article.addEventListener("click", () => fixNote(note.id));
  return article;
}

// Hovering a note lights its passages in the panes; clicking a passage lights its notes in the drawer,
// and brings the first of them into view.
function lightNotes(ids) {
  litNotes.forEach(el => el.classList.remove("lit-note"));
  litNotes = [];
  document.querySelectorAll(".live .an, .live .rule").forEach(el => {
    if (el.dataset.n.split(" ").some(id => ids.includes(id))) litNotes.push(el);
  });
  litNotes.forEach(el => el.classList.add("lit-note"));
}

// Clicking a washed spot selects the broadest passage over it and shows that passage's notes; each
// further click on the same spot goes one passage narrower, down to the narrowest, then round again.
let drill = null;  // { piece, side, version, levels, at }
let selected = [];

function levelsAt(piece) {
  const byPassage = new Map();
  for (const entry of piece.dataset.p.split(" ")) {
    const [key, size, id] = entry.split("|");
    if (!byPassage.has(key)) byPassage.set(key, { key, size: Number(size), ids: [] });
    byPassage.get(key).ids.push(id);
  }
  return [...byPassage.values()].sort((a, b) => b.size - a.size);
}

function drillInto(piece, side) {
  if (drill && drill.piece === piece) drill.at = (drill.at + 1) % drill.levels.length;
  else drill = { piece, side, version: picks[side].value, levels: levelsAt(piece), at: 0 };
  const level = drill.levels[drill.at];
  selectPassage(side, level.key);
  showNotesOf(level.ids);

  const n = drill.levels.length;
  const next = drill.at + 1 < n ? "click again for a narrower passage" : "the narrowest; click again to start over";
  status.textContent = `Passage ${drill.at + 1} of ${n}: ${describePassage(level)}; ${next}.`;
}

// Clicking a bracket in the margin chooses its passage directly.
function chooseBracket(rule, side) {
  const level = { key: rule.dataset.pass, ids: rule.dataset.n.split(" ") };
  drill = { piece: rule, side, version: picks[side].value, levels: [level], at: 0 };
  selectPassage(side, level.key);
  showNotesOf(level.ids);
  status.textContent = `${describePassage(level)}.`;
}

function describePassage(level) {
  const notes = level.ids.length === 1 ? "1 note" : `${level.ids.length} notes`;
  return `“${DATA.passages[drill.version][level.key]}” — ${notes}`;
}

// A passage, chosen: its bracket darkened in the margin, its text highlighted.
function selectPassage(side, key) {
  selected.forEach(el => el.classList.remove("sel"));
  fixedNote = null;
  const pieces = [...panes[side].querySelectorAll(".live .an")].filter(el =>
    el.dataset.p.split(" ").some(entry => entry.startsWith(key + "|")));
  const rules = [...panes[side].querySelectorAll(".live .rule")].filter(el => el.dataset.pass === key);
  selected = pieces.concat(rules);
  selected.forEach(el => el.classList.add("sel"));
}

function clearDrill() {
  selected.forEach(el => el.classList.remove("sel"));
  selected = [];
  drill = null;
  fixedNote = null;
  notesList.querySelectorAll(".nt.lit").forEach(a => a.classList.remove("lit"));
}

// Clicking a note in the drawer fixes it instead of whatever was fixed: its passages highlighted and
// its brackets darkened, in every pane that shows its version. Clicking it again lets it go.
let fixedNote = null;
const HINT = document.body.classList.contains("notes-blue")
  ? "Click a washed passage for its notes; click again to go narrower; click a note to fix it."
  : "Click a bracket or an underlined word for its notes; click a note to fix it.";

function fixNote(id) {
  if (fixedNote === id) {
    clearDrill();
    status.textContent = HINT;
    return;
  }
  clearDrill();
  fixedNote = id;
  selected = [...document.querySelectorAll(".live .an, .live .rule")].filter(el =>
    el.dataset.n.split(" ").includes(id));
  selected.forEach(el => el.classList.add("sel"));
  const article = notesList.querySelector(`[data-id="${id}"]`);
  article?.classList.add("lit");
  const lemma = article?.querySelector(".lemma i").textContent ?? "";
  status.textContent = `Fixed: “${lemma}”; click the note again to let it go.`;
}

function showNotesOf(ids) {
  notesList.querySelectorAll(".nt.lit").forEach(a => a.classList.remove("lit"));
  const articles = ids.map(id => notesList.querySelector(`[data-id="${id}"]`)).filter(Boolean);
  articles.forEach(a => a.classList.add("lit"));
  if (articles[0]) {  // scroll the drawer's list only, never the page
    const list = notesList.parentElement;
    list.scrollTop += articles[0].getBoundingClientRect().top - list.getBoundingClientRect().top - 8;
  }
}

// One drawer, two contents: whichever key was pressed last.
function showDrawer() {
  const diffOpen = drawerOpen && drawerMode === "differences" && Boolean(current);
  const notesOpen = drawerOpen && drawerMode === "notes" && !notesTab.hidden;
  const open = diffOpen || notesOpen;
  differences.classList.toggle("open", open);
  document.body.classList.toggle("drawer-open", open);
  diffTable.hidden = !diffOpen;
  notesList.hidden = !notesOpen;
  drawerTitle.textContent = notesOpen ? "Notes" : "Differences";
  drawerCount.textContent = notesOpen ? notesCount.textContent : diffCount.textContent;
}

function setDrawer(open, mode = drawerMode) {
  drawerOpen = open;
  drawerMode = mode;
  updateDifferences();
  updateNotes();
  if (!open) (mode === "notes" ? notesTab : diffTab).focus({ preventScroll: true });
}

function toggleDrawer(mode) {
  setDrawer(!(drawerOpen && drawerMode === mode), mode);
}

function light(side, wordId) {
  lit.forEach(el => el.classList.remove("lit"));
  lit = [];
  if (!wordId || !isText(picks.left.value) || !isText(picks.right.value)) return;
  const other = side === "left" ? "right" : "left";
  const g = lookup[side].get(wordId);
  const mine = g ? g.mine : [wordId];
  const theirs = g ? g.other : (picks.left.value === picks.right.value ? [wordId] : []);
  mine.forEach(id => panes[side].querySelectorAll(`.live [data-w="${id}"]`).forEach(el => lit.push(el)));
  theirs.forEach(id => panes[other].querySelectorAll(`.live [data-w="${id}"]`).forEach(el => lit.push(el)));
  const row = g && (g.source || g).row;
  if (row && drawerOpen && drawerMode === "differences") {
    lit.push(row);
    row.scrollIntoView({ block: "nearest" });  // keep the lit row in view in the drawer
  }
  lit.forEach(el => el.classList.add("lit"));

  if (panesBox.classList.contains("show-notes")) return;  // the status bar shows the notes' passage
  const leftIds = side === "left" ? mine : theirs, rightIds = side === "left" ? theirs : mine;
  const pair = document.createElement("span");
  pair.className = "pair";
  pair.textContent = `${textOf("left", leftIds) || "—"}  ↔  ${textOf("right", rightIds) || "—"}`;
  const kind = document.createElement("span");
  kind.className = "kind";
  kind.textContent = g ? KIND[g.kind] : "identical";
  status.replaceChildren(pair, kind);
}

for (const side of ["left", "right"]) {
  panes[side].addEventListener("mouseover", e => {
    const w = e.target.closest(".w");
    if (w) light(side, w.dataset.w);
    showScansion(e.target);
  });
  panes[side].addEventListener("focusin", e => { const w = e.target.closest(".w"); if (w) light(side, w.dataset.w); });
  panes[side].addEventListener("mouseleave", () => light(side, null));
  panes[side].addEventListener("click", e => {
    if (!panesBox.classList.contains("show-notes")) return;
    const rule = e.target.closest(".rule"), noted = e.target.closest(".an");
    if (rule) chooseBracket(rule, side);
    else if (noted) drillInto(noted, side);
  });
  picks[side].addEventListener("change", render);
}
metreKey.addEventListener("click", () => {
  metreOn = !metreOn;
  updateMetre();
  setInitials(document);
  if (!panesBox.classList.contains("show-notes")) status.textContent = metreOn ? METRE_HINT : "";
});
notesTab.addEventListener("click", () => toggleDrawer("notes"));
diffTab.addEventListener("click", () => toggleDrawer("differences"));
diffClose.addEventListener("click", () => setDrawer(false));
document.addEventListener("keydown", e => { if (e.key === "Escape" && drawerOpen) setDrawer(false); });

picks.left.value = DATA.left;
picks.right.value = DATA.right;
render();
document.fonts.ready.then(() => setInitials(document));  // again, measured in the page's own font
</script>
</body>
</html>
"""


# ── Command line ────────────────────────────────────────────────────────────────────────────────


def main(argv: list[str] | None = None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(
        description="Write a side-by-side HTML reader for each text's versions."
    )
    parser.add_argument(
        "folder",
        type=Path,
        help="a work's folder (text/shakespeare/sonnet-116), or a collection of works",
    )
    parser.add_argument(
        "-o",
        "--out",
        type=Path,
        default=LOOM / "outputs",
        help="folder for the pages (default: loom/outputs)",
    )
    args = parser.parse_args(argv)

    try:
        for work in find_works(args.folder):
            build_work(work, args.out)
    except (ViewerError, SynthesisError) as error:
        sys.exit(f"error: {error}")


def build_work(folder: Path, out_folder: Path) -> None:
    """Compose one work's versions, and write its page, named after its folder."""
    facsimile, parts = find_parts(folder)
    versions = {part.name: compose(list(part.files), part.name) for part in parts}
    notes = read_notes(folder, versions)
    views = []
    for part in parts:
        view = version_view(
            part, versions[part.name], read_head(part.display), notes.get(part.name, [])
        )
        words = sum(len(line.words) for line in view.lines)
        noted = f", {len(view.notes)} notes" if view.notes else ""
        scanned = ", a metrical reading" if view.metre else ""
        print(
            f"{part.name} ({part.label}): {len(view.lines)} lines, {words} words{noted}{scanned}"
        )
        views.append(view)

    work = read_work(folder)
    out_folder.mkdir(parents=True, exist_ok=True)
    shown = ", ".join(["facsimile"] if facsimile else []) or "no facsimile"
    listed = ", ".join(v.name for v in views)
    for suffix, style in NOTE_STYLES.items():
        out = out_folder / f"{folder.name}{suffix}.html"
        out.write_text(build_page(work, facsimile, views, style), encoding="utf-8")
        print(f"wrote {out}: {work.title}; {listed}; {shown}; notes in {style}")

    data = page_data(work, facsimile, views)
    names = list(
        data["sources"]
    )  # the facsimile first, then the versions, as the menus show them
    first = data["texts"][
        -1
    ]  # opens on the last text: the critical one, which notes are usually on
    out = out_folder / f"{folder.name}-mobile.html"
    out.write_text(
        mobile_page.render(
            work.title,
            work.author,
            data["labels"],
            names,
            first,
            script_json(data),
            font_faces(),
        ),
        encoding="utf-8",
    )
    print(f"wrote {out}: {work.title}; {listed}; {shown}; mobile (Ionic)")


if __name__ == "__main__":
    main()
