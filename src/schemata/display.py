from models import (
    Block,
    MatchingRule,
    Passage,
    SchemaKind,
    SynthesisError,
    UnitDescription,
)

from .display_prose import DISPLAY_PROSE, PARAGRAPH, PROSE_PASSAGE
from .display_verse import DISPLAY_VERSE, LINE, VERSE_PASSAGE

DISPLAY = SchemaKind(name="display", ranks=DISPLAY_VERSE + DISPLAY_PROSE)

# The ranks whose units are the substrate's passages, and its blocks
PASSAGES = (VERSE_PASSAGE, PROSE_PASSAGE)
BLOCKS = (LINE, PARAGRAPH)

EXACT = MatchingRule(
    compare=lambda a, b: a == b,
    may_skip=lambda c: False,
    break_matches=None,
)


def text_of(d: UnitDescription) -> str:
    return "".join(c if isinstance(c, str) else text_of(c) for c in d.content)


def walk(descriptions: tuple[UnitDescription, ...]):
    for d in descriptions:
        yield d
        yield from walk(tuple(c for c in d.content if isinstance(c, UnitDescription)))


def passages_of(descriptions: tuple[UnitDescription, ...]) -> tuple[Passage, ...]:
    """The substrate's passages, in order: each passage's id and blocks."""
    for d in descriptions:
        if d.rank not in PASSAGES:
            raise SynthesisError(f"{d.local_id}: a {d.rank.name} outside any passage")
    return tuple(Passage(d.local_id, blocks_of(d)) for d in descriptions)


def blocks_of(passage: UnitDescription) -> tuple[Block, ...]:
    """A passage's blocks, in order: each line's or paragraph's id and text."""
    return tuple(
        Block(d.local_id, text_of(d)) for d in walk((passage,)) if d.rank in BLOCKS
    )
