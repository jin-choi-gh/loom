from models import Block, MatchingRule, Passage, SchemaKind, UnitDescription

from .display_prose import DISPLAY_PROSE, PARAGRAPH
from .display_verse import DISPLAY_VERSE, LINE

DISPLAY = SchemaKind(name="display", ranks=DISPLAY_VERSE + DISPLAY_PROSE)

BLOCKS = (LINE, PARAGRAPH)  # the ranks whose units are the substrate's blocks

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
    return tuple(Passage(d.local_id, blocks_of(d)) for d in descriptions)


def blocks_of(passage: UnitDescription) -> tuple[Block, ...]:
    """A passage's blocks, in order: each line's or paragraph's id and text."""
    return tuple(
        Block(d.local_id, text_of(d)) for d in walk((passage,)) if d.rank in BLOCKS
    )
