from models import Rank, SchemaKind

VERSE = Rank(name="verse")
FOOT = Rank(name="foot", parents=frozenset({"verse"}))
SYLLABLE = Rank(
    name="syllable",
    parents=frozenset({"foot"}),
    values=frozenset({"stressed", "unstressed"}),
)

ACCENTUAL_METRE = SchemaKind(name="accentual-metre", ranks=(VERSE, FOOT, SYLLABLE))
