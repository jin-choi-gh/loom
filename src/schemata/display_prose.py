from models import Rank

PROSE_PASSAGE = Rank(name="prose-passage")
PARAGRAPH = Rank(name="paragraph", parents=frozenset({"prose-passage"}))

DISPLAY_PROSE = (PROSE_PASSAGE, PARAGRAPH)
