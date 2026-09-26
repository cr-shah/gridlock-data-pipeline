"""Source-faithful planning-year parsing."""

import re

from gridlock_pipeline.models import FieldProvenance


def parse_in_service_year(value: str | None) -> tuple[int | None, FieldProvenance | None]:
    if value is None:
        return None, None
    match = re.fullmatch(r"\s*((?:19|20)\d{2})\s*", value)
    if not match:
        return None, None
    return int(match.group(1)), FieldProvenance(
        origin="derived_from_source",
        source_fields=["in_service_year_raw"],
        rule_id="in_service_year_v1",
    )

