from models import Notation

from .metre_text import MetreText
from .tei_display import TeiDisplay

NOTATIONS: tuple[Notation, ...] = (TeiDisplay(), MetreText())
