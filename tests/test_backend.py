from __future__ import annotations

from lexhint import DictionaryEntry, Sense

from dictterm.backend import LexhintBackend


def _entry(word: str, pos: str) -> DictionaryEntry:
    return DictionaryEntry(
        word=word,
        pos=pos,
        senses=(Sense(glosses=(f"{word} {pos}",)),),
    )


class FakeLexicon:
    def __init__(self) -> None:
        self.entry_calls: list[tuple[str, bool]] = []
        self.suggest_calls: list[tuple[str, int]] = []

    def entries(self, word: str, *, all_case_variants: bool = False):
        self.entry_calls.append((word, all_case_variants))
        return (_entry(word, "noun"), _entry(word, "verb"))

    def suggest(self, query: str, *, limit: int = 20):
        self.suggest_calls.append((query, limit))
        return ("love", "lover")


def test_backend_filters_entries_and_forwards_case_policy() -> None:
    lexicon = FakeLexicon()
    backend = LexhintBackend(
        lexicon,
        all_case_variants=True,
        include_pos=("verb",),
        exclude_pos=("adjective",),
    )

    assert tuple(entry.pos for entry in backend.entries("love")) == ("verb",)
    assert lexicon.entry_calls == [("love", True)]


def test_backend_forwards_bounded_suggestions() -> None:
    lexicon = FakeLexicon()
    backend = LexhintBackend(lexicon)

    assert backend.suggest("lov", limit=7) == ("love", "lover")
    assert lexicon.suggest_calls == [("lov", 7)]
