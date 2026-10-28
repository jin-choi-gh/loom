from models import AnnotationFormat

from .notes_text import NotesText

ANNOTATION_FORMATS: tuple[AnnotationFormat, ...] = (NotesText(),)
