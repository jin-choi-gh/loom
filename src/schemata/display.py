from models import Line, MatchingRule, Rank, SchemaKind, UnitDescription

POEM = Rank(name="poem")
STANZA = Rank(name="stanza", parents=frozenset({"poem"}))
LINE = Rank(name="line", parents=frozenset({"stanza"}), values=None)
HIGHLIGHT = Rank(name="highlight", parents=frozenset({"line"}), values=None)

DISPLAY = SchemaKind(name="display", ranks=(POEM, STANZA, LINE, HIGHLIGHT))

EXACT = MatchingRule(
    compare=lambda a, b: a == b,
    may_skip=lambda c: False,
    line_break_matches=None,
)


def text_of(d: UnitDescription) -> str:
    return "".join(c if isinstance(c, str) else text_of(c) for c in d.content)


def walk(descriptions: tuple[UnitDescription, ...]):
    for d in descriptions:
        yield d
        yield from walk(tuple(c for c in d.content if isinstance(c, UnitDescription)))


def lines_of(descriptions: tuple[UnitDescription, ...]) -> tuple[Line, ...]:
    """The poem's lines, in order: each line description's id and text."""
    return tuple(
        Line(d.local_id, text_of(d)) for d in walk(descriptions) if d.rank is LINE
    )
