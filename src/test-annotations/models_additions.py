"""DRAFT, not yet reviewed (2026-10-17). To be appended to src/models.py, after Annotation.

Annotations as written, before they are resolved against a version: what every annotation format
produces (the notes text format today; Markdown or TOML later), as UnitDescription is what every
representation format produces. In models.py, the imports below are already there.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class End:
    """One end of a target, as written: a line, and optionally a quote in it."""

    line_id: str
    quote: str | None = None  # None: the whole line
    occurrence: int = 1  # [n]; the first, if not written


@dataclass(frozen=True)
class TargetDescription:
    """A target as written: one end, or two joined by ~."""

    first: End
    last: End | None = None  # None: the first end alone


@dataclass(frozen=True)
class AnnotationDescription:
    """An annotation as written, before it is resolved against a version."""

    row: int  # where its head is in its file, counting from 1, for messages
    targets: tuple[TargetDescription, ...]
    body: str  # its text, indentation removed


@dataclass(frozen=True)
class AnnotationSetDescription:
    """A set of annotations as written, with what its header says: what parsing a notes file gives."""

    # the version its ends refer to (version: vendler-1997); None if not given
    version: str | None
    annotations: tuple[AnnotationDescription, ...]
