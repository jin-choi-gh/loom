from dataclasses import dataclass, field

from models import Atom, Position, Schema, Span, Substrate, Version, Unit


@dataclass
class AtomDraft:
    """An atom while integration is still finding out what it belongs to."""

    span: Span
    innermost: dict[str, Unit] = field(default_factory=dict)
    starts: list[Unit] = field(default_factory=list)
    ends: list[Unit] = field(default_factory=list)

    def finish(self, substrate: Substrate) -> Atom:
        """The finished, frozen atom."""
        line = substrate.lines[self.span.start.line]
        text = line.text[self.span.start.offset : self.span.end.offset]
        return Atom(
            span=self.span,
            text=text,
            innermost=dict(self.innermost),
            starts=tuple(self.starts),
            ends=tuple(self.ends),
        )


class AtomDrafts:
    """Every atom draft in reading order, and which of them a unit covers."""

    def __init__(self, spans: list[Span]):
        self.all = [AtomDraft(span) for span in spans]
        self._first = {draft.span.start: index for index, draft in enumerate(self.all)}
        self._last = {draft.span.end: index for index, draft in enumerate(self.all)}

    def covered_by(self, unit: Unit) -> list[AtomDraft]:
        """The run of drafts a unit covers, from where it starts to where it ends."""
        return self.all[self._first[unit.span.start] : self._last[unit.span.end] + 1]


def find_cuts(substrate: Substrate, schemata: dict[str, Schema]) -> list[set[int]]:
    """For each line, every offset where a unit of any schema starts or ends, and both line ends."""
    cuts = [{0, len(line.text)} for line in substrate.lines]
    for schema in schemata.values():
        for unit in schema.units:
            for position in (unit.span.start, unit.span.end):
                cuts[position.line].add(position.offset)
    return cuts


def cut_atoms(substrate: Substrate, cuts: list[set[int]]) -> list[Span]:
    """The atoms' spans: each line cut at its cuts, in reading order."""
    spans: list[Span] = []
    for index, line in enumerate(substrate.lines):
        offsets = sorted(cuts[index])
        for start, end in zip(offsets, offsets[1:]):
            spans.append(Span(Position(index, start), Position(index, end)))
    return spans


def find_membership(drafts: AtomDrafts, schemata: dict[str, Schema]):
    """Record, on each atom draft, the units it belongs to and the units starting and ending there."""
    for schema in schemata.values():
        for unit in schema.units:  # parents before children
            covered = drafts.covered_by(unit)
            covered[0].starts.append(unit)
            covered[-1].ends.append(unit)
            for draft in covered:
                # a later unit is deeper, so it replaces its parent
                draft.innermost[schema.name] = unit


def integrate(
    substrate: Substrate, schemata: dict[str, Schema], base_schema: str
) -> Version:
    """Join schemata over one substrate into the textual version."""
    cuts = find_cuts(substrate, schemata)
    drafts = AtomDrafts(cut_atoms(substrate, cuts))
    find_membership(drafts, schemata)
    atoms = tuple(draft.finish(substrate) for draft in drafts.all)
    return Version(substrate, schemata, atoms, base_schema)
