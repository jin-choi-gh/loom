from models import (
    Position,
    Representation,
    Schema,
    Span,
    Substrate,
    SynthesisError,
    Unit,
    UnitDescription,
)


class Matcher:
    def __init__(self, representation: Representation, substrate: Substrate) -> None:
        self.name = representation.name
        self.lines = substrate.lines
        self.rule = representation.format.alignment
        self.cursor = Position(0, 0)
        self.units: list[Unit | None] = []

    def at_line_end(self) -> bool:
        return self.cursor.offset == len(self.lines[self.cursor.line].text)

    def at_end(self) -> bool:
        return self.cursor.line == len(self.lines) - 1 and self.at_line_end()

    def peek_at_char(self) -> str:
        return self.lines[self.cursor.line].text[self.cursor.offset]

    def advance(self) -> None:
        if self.at_line_end():
            self.cursor = Position(self.cursor.line + 1, 0)
        else:
            self.cursor = Position(self.cursor.line, self.cursor.offset + 1)

    def label(self) -> str:
        return f"{self.lines[self.cursor.line].id}@{self.cursor.offset}"

    def skip(self) -> None:
        """Step over line breaks, and whatever the rule allows between pieces."""
        while not self.at_end():
            if self.at_line_end() or self.rule.may_skip(self.peek_at_char()):
                self.advance()
            else:
                break

    def text(self, text: str) -> Span:
        if not text:
            raise SynthesisError(f"an empty piece of text at {self.label()}")

        start = self.cursor
        for c in text:
            if self.at_end():
                raise SynthesisError(f"{text!r} runs past the end of the poem")
            if self.at_line_end():
                if self.rule.line_break_matches != c:
                    raise SynthesisError(
                        f"{text!r} runs past the end of line {self.lines[self.cursor.line].id}"
                    )
                self.advance()
            elif self.rule.compare(c, self.peek_at_char()):
                self.advance()
            else:
                raise self.mismatch(text, start)
        return Span(start, self.cursor)

    def mismatch(self, text: str, start: Position) -> SynthesisError:
        line = self.lines[start.line]
        found = line.text[start.offset : start.offset + len(text)]
        return SynthesisError(
            f"{text!r} does not match the poem at {self.label()}; "
            f"from {line.id}@{start.offset} the poem reads {found!r}"
        )

    def description(self, d: UnitDescription, parent_id: str | None) -> Span:
        slot = len(self.units)
        self.units.append(None)

        first = last = None
        for item in d.content:
            if isinstance(item, str):
                self.skip()
                span = self.text(item)
            else:
                span = self.description(item, d.local_id)
            if first is None:
                first = span.start
            last = span.end

        span = Span(first, last)
        self.units[slot] = Unit(self.name, d.local_id, d.rank, span, d.value, parent_id)
        return span


def match(
    representation: Representation,
    descriptions: tuple[UnitDescription, ...],
    substrate: Substrate,
) -> Schema:
    matcher = Matcher(representation, substrate)
    for d in descriptions:
        matcher.description(d, parent_id=None)

    matcher.skip()
    if not matcher.at_end():
        raise SynthesisError(f"text left over at {matcher.label()}")

    return Schema(representation.name, representation.format, tuple(matcher.units))
