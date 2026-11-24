from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass, field
from functools import cached_property

from .annotation import Annotation
from .core import Block, Span, Substrate
from .metadata import Metadata
from .schema import Schema, Unit


@dataclass(frozen=True)
class Atom:
    span: Span
    text: str
    innermost: dict[str, Unit]
    starts: tuple[Unit, ...] = ()
    ends: tuple[Unit, ...] = ()


@dataclass(frozen=True)
class TextualComplex:
    name: str | None
    substrate: Substrate
    schemata: dict[str, Schema]
    atoms: tuple[Atom, ...]
    annotations: dict[str, tuple[Annotation, ...]] = field(default_factory=dict)
    metadata: Metadata = field(default_factory=Metadata)

    @cached_property
    def _atoms_by_block(self) -> dict[int, tuple[Atom, ...]]:
        by_block: dict[int, list[Atom]] = {}
        for atom in self.atoms:
            by_block.setdefault(atom.span.start.block, []).append(atom)
        return {block: tuple(atoms) for block, atoms in by_block.items()}

    def blocks(self) -> Iterator[tuple[Block, tuple[Atom, ...]]]:
        for index, block in enumerate(self.substrate.blocks):
            yield block, self._atoms_by_block.get(index, ())

    def units_of(self, atom: Atom, schema_name: str) -> tuple[Unit, ...]:
        """The atom's units in one schema: innermost first, then each parent up to the root."""
        schema = self.schemata[schema_name]
        chain: list[Unit] = []
        unit = atom.innermost.get(schema_name)
        while unit is not None:
            chain.append(unit)
            unit = schema.parent(unit)
        return tuple(chain)
