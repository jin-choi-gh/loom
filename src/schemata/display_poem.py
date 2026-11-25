from models import Rank

POEM = Rank(name="poem")
STANZA = Rank(name="stanza", parents=frozenset({"poem"}))
LINE = Rank(name="line", parents=frozenset({"stanza"}), values=None)
HIGHLIGHT = Rank(name="highlight", parents=frozenset({"line"}), values=None)

DISPLAY_POEM = (POEM, STANZA, LINE, HIGHLIGHT)
