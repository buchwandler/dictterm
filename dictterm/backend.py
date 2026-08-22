from __future__ import annotations

from typing import Protocol

from lexhint import DictionaryEntry, Lexicon

from .selection import filter_entries


class DictionaryBackend(Protocol):
    def entries(self, word: str) -> tuple[DictionaryEntry, ...]: ...

    def suggest(self, query: str, *, limit: int = 20) -> tuple[str, ...]: ...


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

    def entries(self, word: str) -> tuple[DictionaryEntry, ...]:
        raw = self.lexicon.entries(
            word,
            all_case_variants=self.all_case_variants,
        )
        return filter_entries(raw, include=self.include_pos, exclude=self.exclude_pos)

    def suggest(self, query: str, *, limit: int = 20) -> tuple[str, ...]:
        return tuple(self.lexicon.suggest(query, limit=limit))
