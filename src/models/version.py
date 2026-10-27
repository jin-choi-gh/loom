from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from functools import cached_property

from .core import Line, Span, Substrate
from .schema import Schema, Unit


@dataclass(frozen=True)
class Atom:
    span: Span
    text: str
    innermost: dict[str, Unit]
    starts: tuple[Unit, ...] = ()
    ends: tuple[Unit, ...] = ()


@dataclass(frozen=True)
class Version:
    name: str | None
    substrate: Substrate
    schemata: dict[str, Schema]
    atoms: tuple[Atom, ...]

    @cached_property
    def _atoms_by_line(self) -> dict[int, tuple[Atom, ...]]:
        by_line: dict[int, list[Atom]] = {}
        for atom in self.atoms:
            by_line.setdefault(atom.span.start.line, []).append(atom)
        return {line: tuple(atoms) for line, atoms in by_line.items()}

    def lines(self) -> Iterator[tuple[Line, tuple[Atom, ...]]]:
        for index, line in enumerate(self.substrate.lines):
            yield line, self._atoms_by_line.get(index, ())

    def units_of(self, atom: Atom, schema_name: str) -> tuple[Unit, ...]:
        """The atom's units in one schema: innermost first, then each parent up to the root."""
        schema = self.schemata[schema_name]
        chain: list[Unit] = []
        unit = atom.innermost.get(schema_name)
        while unit is not None:
            chain.append(unit)
            unit = schema.parent(unit)
        return tuple(chain)
