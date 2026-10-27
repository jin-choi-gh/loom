from __future__ import annotations

from dataclasses import dataclass

from .core import Span


@dataclass(frozen=True)
class Locator:
    line_id: str
    quote: str | None = None
    occurrence: int = 1


@dataclass(frozen=True)
class TargetDescription:
    first: Locator
    last: Locator | None = None


@dataclass(frozen=True)
class AnnotationDescription:
    row: int
    targets: tuple[TargetDescription, ...]
    body: str


@dataclass(frozen=True)
class SpanTarget:
    """A stretch of the version's substrate: the note is about the text itself."""

    span: Span


@dataclass(frozen=True)
class Annotation:
    """A note on a version's text: what it says, and what it is about."""

    targets: tuple[SpanTarget, ...]  # one or more, joined by && in the file
    body: str  # the note's text, its indentation removed
