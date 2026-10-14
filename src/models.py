from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from functools import cached_property
from pathlib import Path


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


@dataclass(frozen=True)
class UnitDescription:
    rank: Rank
    content: tuple[str | UnitDescription, ...] = ()
    value: str | None = None
    local_id: str | None = None


@dataclass(frozen=True)
class Rank:
    name: str
    parents: frozenset[str] = frozenset()
    values: frozenset[str] | None = frozenset()
    is_point: bool = False


@dataclass(frozen=True)
class Representation:
    path: Path
    format: Format
    source: str
    name: str


class Format:
    name: str
    suffix: str
    ranks: dict[str, Rank]
    alignment: Alignment
    can_be_base: bool

    def read(self, representation: Representation) -> tuple[UnitDescription, ...]:
        raise NotImplementedError

    def transcribe(self, descriptions: tuple[UnitDescription, ...]) -> Substrate:
        raise NotImplementedError


@dataclass(frozen=True)
class Unit:
    schema: str
    local_id: str
    rank: Rank
    span: Span
    value: str | None = None
    parent_id: str | None = None


@dataclass(frozen=True)
class Schema:
    name: str
    format: Format
    units: tuple[Unit, ...]

    def __post_init__(self) -> None:
        if not self.units:
            raise SynthesisError(f"schema {self.name} has no units")

        seen: set[str] = set()
        for unit in self.units:
            if unit.schema != self.name:
                raise SynthesisError(
                    f"unit {unit.local_id} belongs to schema {unit.schema}, not {self.name}"
                )
            if unit.local_id in seen:
                raise SynthesisError(
                    f"schema {self.name} has two units called {unit.local_id}"
                )
            seen.add(unit.local_id)

    @cached_property
    def _by_id(self) -> dict[str, Unit]:
        return {unit.local_id: unit for unit in self.units}

    @cached_property
    def _children(self) -> dict[str | None, tuple[Unit, ...]]:
        children: dict[str | None, list[Unit]] = {}
        for unit in self.units:
            children.setdefault(unit.parent_id, []).append(unit)
        return {k: tuple(v) for k, v in children.items()}

    def unit(self, local_id: str) -> Unit:
        try:
            return self._by_id[local_id]
        except KeyError:
            raise SynthesisError(f"schema {self.name} has no unit {local_id}") from None

    def roots(self) -> tuple[Unit, ...]:
        return self._children.get(None, ())

    def children(self, unit: Unit) -> tuple[Unit, ...]:
        return self._children.get(unit.local_id, ())

    def parent(self, unit: Unit) -> Unit | None:
        return None if unit.parent_id is None else self.unit(unit.parent_id)


class VariantTable:
    """Spelling variants the substrate may be matched against (e.g. oeconomy → economy).

    Not designed yet: a placeholder so Alignment can name its field.
    """


@dataclass(frozen=True)
class Alignment:
    compare: Callable[[str, str], bool]
    may_skip: Callable[[str], bool]
    line_break_matches: str | None
    variants: VariantTable | None = None


@dataclass(frozen=True)
class Atom:
    span: Span
    text: str
    innermost: dict[str, Unit]
    starts: tuple[Unit, ...] = ()
    ends: tuple[Unit, ...] = ()


@dataclass(frozen=True)
class Version:
    substrate: Substrate
    schemata: dict[str, Schema]
    atoms: tuple[Atom, ...]
    base_schema: str

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
