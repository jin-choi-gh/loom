from .display_prose_text import DisplayProseText
from .display_text import DisplayText
from .display_verse_text import DisplayVerseText
from .metre_text import MetreText
from .tei_display import TeiDisplay

REPRESENTATION_FORMATS = (
    TeiDisplay(),
    DisplayText(),
    DisplayVerseText(),
    DisplayProseText(),
    MetreText(),
)
