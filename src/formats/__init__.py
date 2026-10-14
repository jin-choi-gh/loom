from models import Format

from .metre_text import MetreText
from .poem_display import PoemDisplay

FORMATS: tuple[Format, ...] = (PoemDisplay(), MetreText())
