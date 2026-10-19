"""DRAFT, not yet reviewed (2026-10-17). To become src/annotation.py.

Resolving annotations: turning annotations as written (AnnotationDescription, from any annotation
format) into annotations on a version, each target found in its substrate. Independent of any
format, as matching.py places what any representation describes.

Notes are independent of each other, so every error is collected, by row, and reported together.
"""

import unicodedata

from models import (
    Annotation,
    AnnotationDescription,
    End,
    Position,
    Span,
    SpanTarget,
    Substrate,
    SynthesisError,
    TargetDescription,
    Version,
)


def resolve(
    descriptions: tuple[AnnotationDescription, ...], version: Version
) -> tuple[Annotation, ...]:
    """Each annotation's targets found in the version's substrate."""
    annotations: list[Annotation] = []
    errors: list[str] = []
    for description in descriptions:
        try:
            targets = tuple(
                SpanTarget(resolve_target(target, version.substrate))
                for target in description.targets
            )
        except SynthesisError as error:
            errors.append(f"row {description.row}: {error}")
            continue
        annotations.append(Annotation(targets, description.body))
    if errors:
        raise SynthesisError("\n".join(errors))
    return tuple(annotations)


def resolve_target(target: TargetDescription, substrate: Substrate) -> Span:
    """One end's span, or, for two ends joined by ~, from the first's start to the last's end."""
    first = resolve_end(target.first, substrate)
    if target.last is None:
        return first
    last = resolve_end(target.last, substrate)
    if last.start < first.start or last.end < first.end:
        raise SynthesisError(
            f"the range must run forwards: {describe(target.last)} "
            f"does not come after {describe(target.first)}"
        )
    return Span(first.start, last.end)


def resolve_end(end: End, substrate: Substrate) -> Span:
    """Where an end is: its whole line, or the n-th occurrence of its quote in that line."""
    index = substrate.line_index(end.line_id)
    text = substrate.lines[index].text
    if end.quote is None:
        return Span(Position(index, 0), Position(index, len(text)))

    quote = unicodedata.normalize("NFC", end.quote)  # the substrate is in NFC
    start = find_occurrence(text, quote, end.occurrence)
    if start is None:
        count = text.count(quote)
        found = "not in" if count == 0 else f"only {count} time(s) in"
        raise SynthesisError(
            f"{describe(end)}: {quote!r} is {found} line {end.line_id}: {text!r}"
        )
    return Span(Position(index, start), Position(index, start + len(quote)))


def find_occurrence(text: str, quote: str, n: int) -> int | None:
    """Where the n-th occurrence of quote begins in text, counting without overlaps, or None."""
    start = -len(quote)
    for _ in range(n):
        start = text.find(quote, start + len(quote))
        if start == -1:
            return None
    return start


def describe(end: End) -> str:
    """An end as it was written: l1 'ever'[2], or l13 for a whole line."""
    if end.quote is None:
        return end.line_id
    occurrence = f"[{end.occurrence}]" if end.occurrence != 1 else ""
    return f"{end.line_id} {end.quote!r}{occurrence}"
