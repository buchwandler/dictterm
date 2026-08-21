from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

from lexhint import DictionaryEntry


def normalize_pos(value: str) -> str:
    """Normalize POS labels for user-facing selection and navigation."""
    return re.sub(r"[\s_-]+", " ", value.strip().lower())


def parse_pos_list(value: str | None) -> tuple[str, ...]:
    """Parse a comma-separated POS list into normalized, unique labels."""
    if value is None:
        return ()
    labels = tuple(normalize_pos(item) for item in value.split(","))
    if not all(labels):
        raise ValueError("POS lists cannot contain empty values")
    return tuple(dict.fromkeys(labels))


def filter_entries(
    entries: Sequence[DictionaryEntry],
    *,
    include: Iterable[str] = (),
    exclude: Iterable[str] = (),
) -> tuple[DictionaryEntry, ...]:
    included = {normalize_pos(value) for value in include}
    excluded = {normalize_pos(value) for value in exclude}
    return tuple(
        entry
        for entry in entries
        if (not included or normalize_pos(entry.pos) in included)
        and normalize_pos(entry.pos) not in excluded
    )
