"""Conservative line-length extraction."""

import re

from gridlock_pipeline.models import FieldProvenance

LENGTH_PATTERN = re.compile(
    r"~?(?:\d+(?:\.\d+)?|\.\d+)(?:\s+miles?|[-\u2011]mile)\b", re.IGNORECASE
)


def extract_lengths(value: str) -> tuple[list[str], list[float], FieldProvenance | None]:
    raw: list[str] = []
    values: list[float] = []
    for match in LENGTH_PATTERN.finditer(value):
        expression = match.group(0)
        if expression not in raw:
            raw.append(expression)
            values.append(float(re.search(r"(?:\d+(?:\.\d+)?|\.\d+)", expression).group(0)))
    provenance = None
    if values:
        provenance = FieldProvenance(
            origin="derived_from_source",
            source_fields=["description_raw"],
            rule_id="length_miles_v1",
            notes="Values are preserved independently and are not summed.",
        )
    return raw, values, provenance
