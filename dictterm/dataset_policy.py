from __future__ import annotations

from lexhint import DATASET_VARIANTS, LexiconCapabilityError

REQUIRED_CAPABILITIES = frozenset({"lexical", "dictionary"})
DEFAULT_VARIANT = "dictionary"
MANAGED_VARIANTS = tuple(
    name
    for name, spec in DATASET_VARIANTS.items()
    if frozenset(spec.capabilities) >= REQUIRED_CAPABILITIES
)


def validate_managed_variant(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in MANAGED_VARIANTS:
        allowed = ", ".join(MANAGED_VARIANTS)
        raise ValueError(f"unsupported dictterm dataset variant {value!r}; choose {allowed}")
    return normalized


def require_dictterm_capabilities(lexicon: object) -> None:
    capabilities = frozenset(getattr(lexicon, "capabilities", ()))
    missing = REQUIRED_CAPABILITIES - capabilities
    if missing:
        missing_text = ", ".join(sorted(missing))
        raise LexiconCapabilityError(
            "selected Lexhint artifact does not provide the capabilities required by "
            f"dictterm: {missing_text}"
        )
