from models import Rank

PROSE = Rank(name="prose")
PARAGRAPH = Rank(name="paragraph", parents=frozenset({"prose"}))

DISPLAY_PROSE = (PROSE, PARAGRAPH)
