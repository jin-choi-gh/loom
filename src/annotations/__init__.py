from models import AnnotationFormat

from provisional.notes_text import ProvisionalNotesText

# Notes with @:ids supersede notes_text.NotesText while their syntax is on trial
ANNOTATION_FORMATS: tuple[AnnotationFormat, ...] = (ProvisionalNotesText(),)
