"""Conservative location mention extraction without geocoding."""

import re

from gridlock_pipeline.models import FieldProvenance


def extract_candidate_locations(
    project_name: str,
) -> tuple[list[str], list[str], FieldProvenance | None]:
    value = re.sub(r"^\s*[A-Z][A-Z0-9&/ .-]{0,24}:\s*", "", project_name)
    value = re.split(r"\b\d+(?:/\d+)*\s*kV\b", value, maxsplit=1, flags=re.IGNORECASE)[0]
    value = value.split(",", 1)[0].strip()
    parts = [part.strip() for part in re.split(r"\s+-\s+", value) if part.strip()]
    if len(parts) < 2:
        return [], [], None
    candidates = parts[:2]
    provenance = FieldProvenance(
        origin="derived_from_source",
        source_fields=["project_name_raw"],
        rule_id="location_candidates_v1",
        notes="Text candidates only; no geocoding or entity resolution applied.",
    )
    return candidates, candidates.copy(), provenance

