"""Versioned deterministic project-type rules."""

from gridlock_pipeline.models import ConfidenceLevel, FieldProvenance


def classify_project_type(
    project_name: str,
    description: str | None,
) -> tuple[str, ConfidenceLevel, str, FieldProvenance]:
    text = f"{project_name} {description or ''}".casefold()
    rules = (
        ("reconductor", "line_reconductor"),
        ("rebuild", "line_rebuild"),
        ("replace", "equipment_replacement"),
        ("construct", "new_construction"),
        ("install", "equipment_installation"),
        ("upgrade", "equipment_upgrade"),
        ("uprate", "line_uprate"),
        ("expansion", "substation_expansion"),
    )
    project_type = "unknown"
    confidence = ConfidenceLevel.LOW
    for token, candidate in rules:
        if token in text:
            project_type = candidate
            confidence = ConfidenceLevel.HIGH
            break
    provenance = FieldProvenance(
        origin="deterministic_rule",
        source_fields=["project_name_raw", "description_raw"],
        rule_id="project_type_rules_v1",
    )
    return project_type, confidence, "project_type_rules_v1", provenance

