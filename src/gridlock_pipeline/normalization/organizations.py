"""Conservative organization normalization."""

import re

from gridlock_pipeline.models import FieldProvenance


def normalize_balancing_authority(value: str) -> tuple[str, FieldProvenance]:
    normalized = re.sub(r"\s+", " ", value).strip().upper()
    return normalized, FieldProvenance(
        origin="normalized",
        source_fields=["balancing_authority_raw"],
        rule_id="balancing_authority_v1",
    )


def extract_owner_prefix(value: str) -> tuple[str | None, FieldProvenance | None]:
    match = re.match(r"^\s*([A-Z][A-Z0-9&/ .-]{0,24}:)", value)
    if not match:
        return None, None
    return match.group(1).strip(), FieldProvenance(
        origin="derived_from_source",
        source_fields=["project_name_raw"],
        rule_id="owner_prefix_v1",
    )

