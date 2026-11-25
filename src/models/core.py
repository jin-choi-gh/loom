from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property


class SynthesisError(Exception):
    """Something went wrong in the process of synthesising the textual complex"""


@dataclass(frozen=True, order=True)
class Position:
    block: int
    offset: int


# TODO: Write doc strings
# rule: A span never starts at the end of a block,
# and never ends at the start of a block.
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
class Block:
    id: str
    text: str


@dataclass(frozen=True)
class Passage:
    id: str
    blocks: tuple[Block, ...]

    def __post_init__(self) -> None:
        if not self.blocks:
            raise SynthesisError(f"passage {self.id} has no blocks")


@dataclass(frozen=True)
class Substrate:
    passages: tuple[Passage, ...]

    def __post_init__(self) -> None:
        if not self.passages:
            raise SynthesisError("the substrate has no passages")

        seen: set[str] = set()
        for part in (*self.passages, *self.blocks):
            if part.id in seen:
                raise SynthesisError(f"two parts of the text are called {part.id}")
            seen.add(part.id)

    @cached_property
    def blocks(self) -> tuple[Block, ...]:
        """Every passage's blocks, in order. A position counts blocks here, through the whole text."""
        return tuple(block for passage in self.passages for block in passage.blocks)

    @cached_property
    def _index_by_id(self) -> dict[str, int]:
        return {block.id: index for index, block in enumerate(self.blocks)}

    def block_index(self, block_id: str) -> int:
        """Where the block with this id is. In a text of one passage, the passage's id may be left
        out: l1 for bird.l1."""
        index = self._index_by_id.get(block_id)
        if index is None and len(self.passages) == 1:
            index = self._index_by_id.get(f"{self.passages[0].id}.{block_id}")
        if index is None:
            hint = self._hint(block_id)
            raise SynthesisError(f"nothing in the text is called {block_id}{hint}")
        return index

    def _hint(self, block_id: str) -> str:
        """For an id written without its passage: how it should have been written."""
        for passage in self.passages:
            if (full_id := f"{passage.id}.{block_id}") in self._index_by_id:
                return f"; write its passage too, as in {full_id}"
        return ""

    def passage_span(self, passage_id: str) -> Span | None:
        """All of the passage with this id, or None if no passage has it."""
        first = 0
        for passage in self.passages:
            last = first + len(passage.blocks) - 1
            if passage.id == passage_id:
                end = len(passage.blocks[-1].text)
                return Span(Position(first, 0), Position(last, end))
            first = last + 1
        return None

    def text_of(self, span: Span) -> str:
        """The text a span covers. Across blocks, each block's part, joined by line breaks."""
        start, end = span.start, span.end
        if start.block == end.block:
            return self.blocks[start.block].text[start.offset : end.offset]
        first = self.blocks[start.block].text[start.offset :]
        middle = [block.text for block in self.blocks[start.block + 1 : end.block]]
        last = self.blocks[end.block].text[: end.offset]
        return "\n".join([first, *middle, last])
