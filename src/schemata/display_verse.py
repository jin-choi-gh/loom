from models import Rank

VERSE_PASSAGE = Rank(name="verse-passage")
STANZA = Rank(name="stanza", parents=frozenset({"verse-passage"}))
LINE = Rank(name="line", parents=frozenset({"stanza"}), values=None)
HIGHLIGHT = Rank(name="highlight", parents=frozenset({"line"}), values=None)

DISPLAY_VERSE = (VERSE_PASSAGE, STANZA, LINE, HIGHLIGHT)
