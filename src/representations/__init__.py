from models import RepresentationFormat

from .metre_text import MetreText
from .tei_display import TeiDisplay

REPRESENTATION_FORMATS: tuple[RepresentationFormat, ...] = (TeiDisplay(), MetreText())
