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
class Substrate:
    blocks: tuple[Block, ...]

    def __post_init__(self) -> None:
        if not self.blocks:
            raise SynthesisError("the substrate has no blocks")

        seen: set[str] = set()
        for block in self.blocks:
            if block.id in seen:
                raise SynthesisError(f"two blocks are called {block.id}")
            seen.add(block.id)

    @cached_property
    def _index_by_id(self) -> dict[str, int]:
        return {block.id: index for index, block in enumerate(self.blocks)}

    def block_index(self, block_id: str) -> int:
        try:
            return self._index_by_id[block_id]
        except KeyError:
            raise SynthesisError(f"no block called {block_id}") from None

    def text_of(self, span: Span) -> str:
        """The text a span covers. Across blocks, each block's part, joined by line breaks."""
        start, end = span.start, span.end
        if start.block == end.block:
            return self.blocks[start.block].text[start.offset : end.offset]
        first = self.blocks[start.block].text[start.offset :]
        middle = [block.text for block in self.blocks[start.block + 1 : end.block]]
        last = self.blocks[end.block].text[: end.offset]
        return "\n".join([first, *middle, last])
