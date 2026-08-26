from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from lexhint import DictionaryEntry, HeadwordRelation, Lexicon

from .selection import filter_entries


@dataclass(frozen=True, slots=True)
class LookupResult:
    word: str
    entries: tuple[DictionaryEntry, ...]
    relations: tuple[HeadwordRelation, ...] = ()


class DictionaryBackend(Protocol):
    def lookup(self, word: str) -> LookupResult: ...
    def complete(self, prefix: str, *, limit: int = 20) -> tuple[str, ...]: ...


class LexhintBackend:
    """Session adapter that keeps Lexhint data access out of the TUI."""

    def __init__(
        self,
        lexicon: Lexicon,
        *,
        all_case_variants: bool = False,
        include_pos: tuple[str, ...] = (),
        exclude_pos: tuple[str, ...] = (),
    ) -> None:
        self.lexicon = lexicon
        self.all_case_variants = all_case_variants
        self.include_pos = include_pos
        self.exclude_pos = exclude_pos

    def lookup(self, word: str) -> LookupResult:
        raw = self.lexicon.entries(
            word,
            all_case_variants=self.all_case_variants,
        )
        entries = filter_entries(raw, include=self.include_pos, exclude=self.exclude_pos)
        return LookupResult(
            word=word,
            entries=entries,
            relations=tuple(self.lexicon.relations(word)),
        )

    def entries(self, word: str) -> tuple[DictionaryEntry, ...]:
        return self.lookup(word).entries

    def complete(self, prefix: str, *, limit: int = 20) -> tuple[str, ...]:
        return tuple(self.lexicon.complete(prefix, limit=limit))
