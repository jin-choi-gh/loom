from .display_poem_text import DisplayPoemText
from .display_prose_text import DisplayProseText
from .display_text import DisplayText
from .metre_text import MetreText
from .tei_display import TeiDisplay

REPRESENTATION_FORMATS = (
    TeiDisplay(),
    DisplayText(),
    DisplayPoemText(),
    DisplayProseText(),
    MetreText(),
)