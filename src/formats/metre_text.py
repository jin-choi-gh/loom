import re

from models import (
    Alignment,
    Format,
    Rank,
    Representation,
    SynthesisError,
    UnitDescription,
)

LETTER = r"[^\W\d_]"
STRAY_MARK = re.compile(rf"(?<={LETTER})[^\w\s.'’|\-–—](?={LETTER})")
SYLLABLE_TEXT = re.compile(rf"{LETTER}+(?:['’]{LETTER}+)*")

VERSE = Rank(name="verse")
FOOT = Rank(name="foot", parents=frozenset({"verse"}))
SYLLABLE = Rank(
    name="syllable",
    parents=frozenset({"foot"}),
    values=frozenset({"stressed", "unstressed"}),
)

LETTERS = Alignment(
    compare=lambda a, b: a.casefold() == b.casefold(),
    may_skip=lambda c: not c.isalpha(),
    line_break_matches=None,
)


class MetreText(Format):
    name = "metre"
    suffix = ".metre.txt"
    ranks = {rank.name: rank for rank in (VERSE, FOOT, SYLLABLE)}
    alignment = LETTERS
    can_be_base = False

    def read(self, representation: Representation) -> tuple[UnitDescription, ...]:
        verses: list[UnitDescription] = []
        for row_number, row in enumerate(representation.source.splitlines(), start=1):
            row = row.strip()
            if not row or row.startswith("#"):
                continue
            verses.append(describe_verse(row, len(verses) + 1, row_number))
        return tuple(verses)


def describe_verse(row: str, number: int, row_number: int) -> UnitDescription:
    stray = STRAY_MARK.search(row)
    if stray:
        raise SynthesisError(
            f"row {row_number}, column {stray.start() + 1}: {stray.group()!r} "
            "between two letters; write '.' for a syllable break"
        )

    verse_id = f"v{number}"
    feet: list[UnitDescription] = []
    syllables_so_far = 0

    for foot_number, foot_text in enumerate(row.split("|"), start=1):
        syllables = describe_syllables(
            foot_text, verse_id, syllables_so_far, row_number
        )
        if not syllables:
            raise SynthesisError(
                f"row {row_number}: foot {foot_number} has no syllables"
            )
        syllables_so_far += len(syllables)
        feet.append(
            UnitDescription(
                rank=FOOT, content=syllables, local_id=f"{verse_id}.f{foot_number}"
            )
        )

    return UnitDescription(rank=VERSE, content=tuple(feet), local_id=verse_id)


def describe_syllables(
    foot_text: str, verse_id: str, syllables_so_far: int, row_number: int
) -> tuple[UnitDescription, ...]:
    syllables: list[UnitDescription] = []
    for found in SYLLABLE_TEXT.finditer(foot_text):
        text = found.group()
        number = syllables_so_far + len(syllables) + 1
        syllables.append(
            UnitDescription(
                rank=SYLLABLE,
                content=(text,),
                value=stress_of(text, row_number),
                local_id=f"{verse_id}.s{number}",
            )
        )
    return tuple(syllables)


def stress_of(text: str, row_number: int) -> str:
    if text == text.lower():
        return "unstressed"
    if text == text.upper():
        return "stressed"
    raise SynthesisError(
        f"row {row_number}: syllable {text!r} mixes capitals and lower case"
    )
