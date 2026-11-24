from models import (
    MatchingRule,
    Position,
    Schema,
    SchemaDescription,
    Span,
    Substrate,
    SynthesisError,
    Unit,
    UnitDescription,
)


def match(
    schema_name: str,
    schema_description: SchemaDescription,
    substrate: Substrate,
) -> Schema:
    matcher = Matcher(schema_name, schema_description.matching_rule, substrate)
    for d in schema_description.descriptions:
        matcher.description(d, parent_id=None)

    matcher.skip()
    if not matcher.at_end():
        raise SynthesisError(f"text left over at {matcher.label()}")

    return Schema(schema_name, schema_description.kind, tuple(matcher.units))


class Matcher:
    def __init__(self, name: str, rule: MatchingRule, substrate: Substrate) -> None:
        self.name = name
        self.blocks = substrate.blocks
        self.rule = rule
        self.cursor = Position(0, 0)
        self.units: list[Unit | None] = []

    def at_block_end(self) -> bool:
        return self.cursor.offset == len(self.blocks[self.cursor.block].text)

    def at_end(self) -> bool:
        return self.cursor.block == len(self.blocks) - 1 and self.at_block_end()

    def peek_at_char(self) -> str:
        return self.blocks[self.cursor.block].text[self.cursor.offset]

    def advance(self) -> None:
        if self.at_block_end():
            self.cursor = Position(self.cursor.block + 1, 0)
        else:
            self.cursor = Position(self.cursor.block, self.cursor.offset + 1)

    def label(self) -> str:
        return f"{self.blocks[self.cursor.block].id}@{self.cursor.offset}"

    def skip(self) -> None:
        """Step over the breaks between blocks, and whatever the rule allows between pieces."""
        while not self.at_end():
            if self.at_block_end() or self.rule.may_skip(self.peek_at_char()):
                self.advance()
            else:
                break

    def text(self, text: str) -> Span:
        if not text:
            raise SynthesisError(f"an empty piece of text at {self.label()}")

        start = self.cursor
        for c in text:
            if self.at_end():
                raise SynthesisError(f"{text!r} runs past the end of the text")
            if self.at_block_end():
                if self.rule.break_matches != c:
                    raise SynthesisError(
                        f"{text!r} runs past the end of {self.blocks[self.cursor.block].id}"
                    )
                self.advance()
            elif self.rule.compare(c, self.peek_at_char()):
                self.advance()
            else:
                raise self.mismatch(text, start)
        return Span(start, self.cursor)

    def mismatch(self, text: str, start: Position) -> SynthesisError:
        block = self.blocks[start.block]
        found = block.text[start.offset : start.offset + len(text)]
        return SynthesisError(
            f"{text!r} does not match the text at {self.label()}; "
            f"from {block.id}@{start.offset} the text reads {found!r}"
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
