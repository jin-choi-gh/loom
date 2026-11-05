from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NotesMetadata:
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Metadata:
    title: str | None = None
    author: str | None = None
    notes: NotesMetadata = NotesMetadata()
