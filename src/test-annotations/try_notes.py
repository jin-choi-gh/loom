"""Staging only: try the --notes option before anything is moved into src/.

    python src/test-annotations/try_notes.py <representations of one version> --notes <file>.notes.txt

Puts the staged classes into models (as appending models_additions.py to models.py would), makes the
staged modules importable as they will be from src/, then runs the staged main. Nothing on disk is
changed. Delete this file with the staging folder.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent)]  # staged modules first, then src/

import models

import models_additions

for name in (
    "End",
    "TargetDescription",
    "AnnotationDescription",
    "AnnotationSetDescription",
):
    setattr(models, name, getattr(models_additions, name))

import synthesis_additions

synthesis_additions.main()
