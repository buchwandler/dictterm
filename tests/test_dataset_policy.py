from __future__ import annotations

import pytest
from lexhint import LexiconCapabilityError

from dictterm.dataset_policy import (
    DEFAULT_VARIANT,
    MANAGED_VARIANTS,
    REQUIRED_CAPABILITIES,
    require_dictterm_capabilities,
    validate_managed_variant,
)


def test_managed_variants_are_capability_derived() -> None:
    assert DEFAULT_VARIANT == "dictionary"
    assert "dictionary" in MANAGED_VARIANTS
    assert "rich" in MANAGED_VARIANTS
    assert "lexical" not in MANAGED_VARIANTS
    assert "runtime" not in MANAGED_VARIANTS


def test_validate_managed_variant_normalizes_allowed_values() -> None:
    assert validate_managed_variant(" RICH ") == "rich"


@pytest.mark.parametrize("variant", ("lexical", "runtime"))
def test_validate_managed_variant_rejects_incompatible_values(variant: str) -> None:
    with pytest.raises(ValueError, match="choose dictionary, rich"):
        validate_managed_variant(variant)


def test_require_dictterm_capabilities_accepts_dictionary_capable_artifact() -> None:
    artifact = type("Artifact", (), {"capabilities": ("lexical", "semantic", "dictionary")})()
    require_dictterm_capabilities(artifact)


def test_require_dictterm_capabilities_reports_missing_capabilities() -> None:
    artifact = type("Artifact", (), {"capabilities": ("lexical", "semantic")})()
    with pytest.raises(LexiconCapabilityError, match="dictionary"):
        require_dictterm_capabilities(artifact)


def test_required_capabilities_are_explicit() -> None:
    assert frozenset({"lexical", "dictionary"}) == REQUIRED_CAPABILITIES
