from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from functools import cached_property

from .core import Span, SynthesisError


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
class SchemaKind:
    name: str
    ranks: tuple[Rank, ...]


@dataclass(frozen=True)
class SchemaDescription:
    """One schema as a format reads it from a representation: its kind, its units, and how to place them."""

    kind: SchemaKind
    descriptions: tuple[UnitDescription, ...]
    matching_rule: MatchingRule


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
    kind: SchemaKind
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

        for unit in self.units:
            self._check(unit)

    def _check(self, unit: Unit) -> None:
        rank = unit.rank
        if rank not in self.kind.ranks:
            raise SynthesisError(
                f"{unit.local_id}: a {rank.name} has no place in a {self.kind.name} schema"
            )

        parent = self.parent(unit)
        if parent is None and rank.parents:
            raise SynthesisError(
                f"{unit.local_id}: a {rank.name} must sit inside a "
                + " or ".join(sorted(rank.parents))
            )
        if parent is not None and parent.rank.name not in rank.parents:
            raise SynthesisError(
                f"{unit.local_id}: a {rank.name} cannot sit inside a {parent.rank.name}"
            )

        if rank.values is None:
            return
        if not rank.values and unit.value is not None:
            raise SynthesisError(
                f"{unit.local_id}: a {rank.name} takes no value, but has {unit.value!r}"
            )
        if rank.values and unit.value not in rank.values:
            raise SynthesisError(
                f"{unit.local_id}: {unit.value!r} is not a value a {rank.name} can have"
            )

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

    Not designed yet: a placeholder so MatchingRule can name its field.
    """


@dataclass(frozen=True)
class MatchingRule:
    compare: Callable[[str, str], bool]
    may_skip: Callable[[str], bool]
    line_break_matches: str | None
    variants: VariantTable | None = None
