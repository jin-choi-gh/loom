from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .core import Substrate
from .schema import SchemaDescription


@dataclass(frozen=True)
class Representation:
    path: Path
    format: RepresentationFormat
    source: str
    qualifier: str  # what the file name holds before the suffix: "smith" in smith.metre.txt, or ""


class RepresentationFormat:
    name: str
    suffix: str
    can_be_base: bool

    def read(self, representation: Representation) -> tuple[SchemaDescription, ...]:
        raise NotImplementedError

    def transcribe(self, schemata: tuple[SchemaDescription, ...]) -> Substrate:
        raise NotImplementedError
