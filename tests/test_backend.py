from __future__ import annotations

from lexhint import DictionaryEntry, HeadwordRelation, Sense

from dictterm.backend import LexhintBackend, LookupResult


def _entry(word: str, pos: str) -> DictionaryEntry:
    return DictionaryEntry(
        word=word,
        pos=pos,
        senses=(Sense(glosses=(f"{word} {pos}",)),),
    )


class FakeLexicon:
    def __init__(self) -> None:
        self.entry_calls: list[tuple[str, bool]] = []
        self.complete_calls: list[tuple[str, int]] = []
        self.relations_calls: list[str] = []

    def entries(self, word: str, *, all_case_variants: bool = False):
        self.entry_calls.append((word, all_case_variants))
        return (_entry(word, "noun"), _entry(word, "verb"))

    def relations(self, word: str):
        self.relations_calls.append(word)
        return (HeadwordRelation(word, "adore", "synonym", ("formal",)),)

    def complete(self, prefix: str, *, limit: int = 20):
        self.complete_calls.append((prefix, limit))
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


def test_backend_lookup_returns_entries_and_relations_together() -> None:
    lexicon = FakeLexicon()
    backend = LexhintBackend(lexicon, all_case_variants=True, include_pos=("verb",))

    result = backend.lookup("love")

    assert isinstance(result, LookupResult)
    assert result.word == "love"
    assert tuple(entry.pos for entry in result.entries) == ("verb",)
    assert result.relations == (HeadwordRelation("love", "adore", "synonym", ("formal",)),)
    assert lexicon.entry_calls == [("love", True)]
    assert lexicon.relations_calls == ["love"]


def test_backend_forwards_bounded_completions() -> None:
    lexicon = FakeLexicon()
    backend = LexhintBackend(lexicon)

    assert backend.complete("lov", limit=7) == ("love", "lover")
    assert lexicon.complete_calls == [("lov", 7)]


def test_supported_lexhint_has_completion_api() -> None:
    from lexhint import Lexicon

    assert callable(getattr(Lexicon, "complete", None))
