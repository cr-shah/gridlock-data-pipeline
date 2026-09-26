"""Voltage extraction that excludes conductors and temperatures."""

import re

from gridlock_pipeline.models import FieldProvenance

VOLTAGE_PATTERN = re.compile(
    r"(?<![\d.])(\d+(?:\.\d+)?(?:\s*/\s*\d+(?:\.\d+)?)*\s*kV)\b",
    re.IGNORECASE,
)


def extract_voltage(value: str) -> tuple[list[str], list[float], FieldProvenance | None]:
    raw: list[str] = []
    levels: list[float] = []
    for match in VOLTAGE_PATTERN.finditer(value):
        expression = re.sub(r"\s+", " ", match.group(1)).strip()
        if expression not in raw:
            raw.append(expression)
        numeric = re.sub(r"\s*kV$", "", expression, flags=re.IGNORECASE)
        for part in re.split(r"\s*/\s*", numeric):
            level = float(part)
            if level not in levels:
                levels.append(level)
    provenance = None
    if levels:
        provenance = FieldProvenance(
            origin="derived_from_source",
            source_fields=["project_name_raw", "description_raw", "supporting_statement_raw"],
            rule_id="voltage_kv_v1",
        )
    return raw, levels, provenance

