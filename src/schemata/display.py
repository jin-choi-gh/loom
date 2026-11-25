from models import Block, MatchingRule, SchemaKind, UnitDescription

from .display_poem import DISPLAY_POEM, LINE
from .display_prose import DISPLAY_PROSE, PARAGRAPH

DISPLAY = SchemaKind(name="display", ranks=DISPLAY_POEM + DISPLAY_PROSE)

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


def blocks_of(descriptions: tuple[UnitDescription, ...]) -> tuple[Block, ...]:
    """The substrate's blocks, in order: each line's or paragraph's id and text."""
    return tuple(
        Block(d.local_id, text_of(d)) for d in walk(descriptions) if d.rank in BLOCKS
    )
