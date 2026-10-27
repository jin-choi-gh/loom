from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property


class SynthesisError(Exception):
    """Something went wrong in the process of synthesising the textual complex"""


@dataclass(frozen=True, order=True)
class Position:
    line: int
    offset: int


# TODO: Write doc strings
# rule: A span never starts at the end of a line,
# and never ends at the start of a line.
#
# spans can be understood as half-open intervals of the form [pos_a, pos_b)
@dataclass(frozen=True)
class Span:
    start: Position
    end: Position

    def is_point(self) -> bool:
        return self.start == self.end

    def contains(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end


@dataclass(frozen=True)
class Line:
    id: str
    text: str


@dataclass(frozen=True)
class Substrate:
    lines: tuple[Line, ...]

    def __post_init__(self) -> None:
        if not self.lines:
            raise SynthesisError("the substrate has no lines")

        seen: set[str] = set()
        for line in self.lines:
            if line.id in seen:
                raise SynthesisError(f"two lines are called {line.id}")
            seen.add(line.id)

    @cached_property
    def _index_by_id(self) -> dict[str, int]:
        return {line.id: index for index, line in enumerate(self.lines)}

    def line_index(self, line_id: str) -> int:
        try:
            return self._index_by_id[line_id]
        except KeyError:
            raise SynthesisError(f"no line called {line_id}") from None

    def text_of(self, span: Span) -> str:
        """The text a span covers. Across lines, each line's part, joined by line breaks."""
        start, end = span.start, span.end
        if start.line == end.line:
            return self.lines[start.line].text[start.offset : end.offset]
        first = self.lines[start.line].text[start.offset :]
        middle = [line.text for line in self.lines[start.line + 1 : end.line]]
        last = self.lines[end.line].text[: end.offset]
        return "\n".join([first, *middle, last])
