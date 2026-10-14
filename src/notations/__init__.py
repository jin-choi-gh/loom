from models import Notation

from .metre_text import MetreText
from .poem_display import PoemDisplay

NOTATIONS: tuple[Notation, ...] = (PoemDisplay(), MetreText())
