import re

from models import Rank, SchemaKind, UnitDescription

LINE = Rank(name="line")
WORD = Rank(name="word", parents=frozenset({"line"}))
WORD_TOKENS = SchemaKind(name="word-tokens", ranks=(LINE, WORD))

# What a word is:
#   - a run of letters, digits and combining marks (ſtar, yͤ), with apostrophes inside (o'er);
#   - or one of the signs for "and" (&, ⁊), standing alone.
# Hyphens and every other mark divide words (ever-fixèd is two words). An apostrophe at a
# word's edge ('tis, th') is left out for now: it cannot be told apart from a quotation mark.
AND_SIGNS = "&\u204a"  # & and the Tironian et ⁊

# Python's \w does not cover combining marks, so their Unicode blocks are listed. They are
# built with chr() so that no invisible combining character sits in the source.
COMBINING_MARKS = (
    (0x0300, 0x036F),
    (0x1AB0, 0x1AFF),
    (0x1DC0, 0x1DFF),
    (0x20D0, 0x20FF),
    (0xFE20, 0xFE2F),
)
MARKS = "".join(f"{chr(first)}-{chr(last)}" for first, last in COMBINING_MARKS)
LETTERLIKE = rf"(?:[^\W_]|[{MARKS}])"  # a letter or digit (not _), or a combining mark

WORD_TEXT = re.compile(rf"[{AND_SIGNS}]|{LETTERLIKE}+(?:['’]{LETTERLIKE}+)*")
LETTERLIKE_CHAR = re.compile(LETTERLIKE)


def is_word_char(c: str) -> bool:
    """A character that belongs to some word, so it is never skipped between words."""
    return c in AND_SIGNS or LETTERLIKE_CHAR.fullmatch(c) is not None


def describe_words(text: str, line_id: str) -> tuple[UnitDescription, ...]:
    """A line's words, in order, numbered l1.w1, l1.w2, ..., l2.w1, ..."""
    return tuple(
        UnitDescription(rank=WORD, content=(word,), local_id=f"{line_id}.w{number}")
        for number, word in enumerate(WORD_TEXT.findall(text), start=1)
    )
