"""Project-name normalization."""

import re
import unicodedata

from gridlock_pipeline.models import FieldProvenance


def normalize_project_name(value: str) -> tuple[str, FieldProvenance]:
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[–—−]", "-", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized, FieldProvenance(
        origin="normalized",
        source_fields=["project_name_raw"],
        rule_id="project_name_v1",
    )

