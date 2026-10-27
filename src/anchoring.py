import unicodedata

from models import (
    Annotation,
    AnnotationDescription,
    Locator,
    Position,
    Span,
    SpanTarget,
    Substrate,
    SynthesisError,
    TargetDescription,
    Version,
)


def anchor(
    descriptions: tuple[AnnotationDescription, ...], version: Version
) -> tuple[Annotation, ...]:
    """Each annotation's targets found in the version's substrate."""
    annotations: list[Annotation] = []
    errors: list[str] = []
    for description in descriptions:
        try:
            targets = tuple(
                SpanTarget(anchor_target(target, version.substrate))
                for target in description.targets
            )
        except SynthesisError as error:
            errors.append(f"row {description.row}: {error}")
            continue
        annotations.append(Annotation(targets, description.body))
    if errors:
        raise SynthesisError("\n".join(errors))
    return tuple(annotations)


def anchor_target(target: TargetDescription, substrate: Substrate) -> Span:
    """One locator's span, or, for two joined by ~, from the first's start to the last's end."""
    first = anchor_locator(target.first, substrate)
    if target.last is None:
        return first
    last = anchor_locator(target.last, substrate)
    if last.start < first.start or last.end < first.end:
        raise SynthesisError(
            f"the range must run forwards: {describe(target.last)} "
            f"does not come after {describe(target.first)}"
        )
    return Span(first.start, last.end)


def anchor_locator(locator: Locator, substrate: Substrate) -> Span:
    """Where a locator points: its whole line, or the n-th occurrence of its quote in that line."""
    index = substrate.line_index(locator.line_id)
    text = substrate.lines[index].text
    if locator.quote is None:
        return Span(Position(index, 0), Position(index, len(text)))

    quote = unicodedata.normalize("NFC", locator.quote)  # the substrate is in NFC
    start = find_occurrence(text, quote, locator.occurrence)
    if start is None:
        count = text.count(quote)
        found = "not in" if count == 0 else f"only {count} time(s) in"
        raise SynthesisError(
            f"{describe(locator)}: {quote!r} is {found} line {locator.line_id}: {text!r}"
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


def describe(locator: Locator) -> str:
    """A locator as it was written: l1 'ever'[2], or l13 for a whole line."""
    if locator.quote is None:
        return locator.line_id
    occurrence = f"[{locator.occurrence}]" if locator.occurrence != 1 else ""
    return f"{locator.line_id} {locator.quote!r}{occurrence}"
