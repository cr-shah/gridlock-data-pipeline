"""Explainable record invariants and duplicate-candidate flags."""

import hashlib
import re
from collections import defaultdict
from collections.abc import Sequence

from gridlock_pipeline.models import ConfidenceLevel, ProjectObservation, ValidationStatus

KNOWN_AUTHORITIES = {
    "AECI",
    "DUKE CAROLINAS",
    "DUKE PROGRESS EAST",
    "DUKE PROGRESS WEST",
    "LG&E/KU",
    "SOUTHERN",
    "TVA",
}
KNOWN_PREFIXES = {"DU:", "GTC:", "MEAG:", "PS:", "SOCO:"}
LOW_CONFIDENCE_WARNINGS = {
    "MISSING_PROJECT_NAME",
    "UNKNOWN_BALANCING_AUTHORITY",
    "SUSPICIOUS_PROJECT_NAME",
}
WARNING_MESSAGES = {
    "MISSING_PROJECT_NAME": "The required source project name is empty.",
    "MISSING_DESCRIPTION": "The source record has no description.",
    "MISSING_SUPPORTING_STATEMENT": "The source record has no supporting statement.",
    "UNUSUAL_IN_SERVICE_YEAR": "The in-service year is outside the conservative range.",
    "UNKNOWN_BALANCING_AUTHORITY": "The balancing authority is not in the observed 2026 set.",
    "UNKNOWN_OWNER_PREFIX": "The source owner prefix is not in the observed 2026 set.",
    "SUSPICIOUS_PROJECT_NAME": "The project name is identifier-only or unusually short.",
    "AMBIGUOUS_ENDPOINTS": "A line-like name did not yield two conservative endpoint candidates.",
    "POSSIBLE_DUPLICATE": "Another observation has the same conservative duplicate fingerprint.",
}


def _append_unique(items: list[str], value: str) -> None:
    if value not in items:
        items.append(value)


def validate_observation(observation: ProjectObservation) -> ProjectObservation:
    warnings = list(observation.warning_codes)
    if not observation.project_name_raw.strip():
        _append_unique(warnings, "MISSING_PROJECT_NAME")
    if not observation.description_raw:
        _append_unique(warnings, "MISSING_DESCRIPTION")
    if not observation.supporting_statement_raw:
        _append_unique(warnings, "MISSING_SUPPORTING_STATEMENT")
    if observation.in_service_year is not None and not (
        2026 <= observation.in_service_year <= 2100
    ):
        _append_unique(warnings, "UNUSUAL_IN_SERVICE_YEAR")
    if observation.balancing_authority_normalized not in KNOWN_AUTHORITIES:
        _append_unique(warnings, "UNKNOWN_BALANCING_AUTHORITY")
    if observation.owner_prefix_raw and observation.owner_prefix_raw not in KNOWN_PREFIXES:
        _append_unique(warnings, "UNKNOWN_OWNER_PREFIX")
    if re.fullmatch(r"[A-Z]{1,6}\d{2,6}(?:-\d+)?", observation.project_name_raw.strip()):
        _append_unique(warnings, "SUSPICIOUS_PROJECT_NAME")
    if " - " in observation.project_name_raw and len(observation.endpoint_candidates) < 2:
        _append_unique(warnings, "AMBIGUOUS_ENDPOINTS")

    if "MISSING_PROJECT_NAME" in warnings:
        status = ValidationStatus.INVALID
    elif warnings:
        status = ValidationStatus.REVIEW
    else:
        status = ValidationStatus.VALID
    if status == ValidationStatus.INVALID or LOW_CONFIDENCE_WARNINGS.intersection(warnings):
        confidence = ConfidenceLevel.LOW
    elif warnings:
        confidence = ConfidenceLevel.MEDIUM
    else:
        confidence = ConfidenceLevel.HIGH
    notes = [WARNING_MESSAGES[code] for code in warnings if code in WARNING_MESSAGES]
    return observation.model_copy(
        update={
            "warning_codes": warnings,
            "validation_notes": notes,
            "validation_status": status,
            "confidence": confidence,
        }
    )


def _duplicate_fingerprint(observation: ProjectObservation) -> str:
    description = re.sub(r"\s+", " ", observation.description_raw or "").casefold()
    parts = (
        observation.balancing_authority_normalized or "",
        (observation.project_name_normalized or observation.project_name_raw).casefold(),
        str(observation.in_service_year or ""),
        ",".join(str(value) for value in observation.voltage_kv),
        observation.owner_prefix_raw or "",
        hashlib.sha256(description.encode()).hexdigest(),
    )
    return "\x1f".join(parts)


def flag_duplicate_candidates(
    observations: Sequence[ProjectObservation],
) -> list[ProjectObservation]:
    groups: dict[str, list[int]] = defaultdict(list)
    result = list(observations)
    for index, observation in enumerate(result):
        groups[_duplicate_fingerprint(observation)].append(index)
    for indexes in groups.values():
        if len(indexes) < 2:
            continue
        for index in indexes:
            warnings = list(result[index].warning_codes)
            _append_unique(warnings, "POSSIBLE_DUPLICATE")
            notes = list(result[index].validation_notes)
            _append_unique(notes, WARNING_MESSAGES["POSSIBLE_DUPLICATE"])
            confidence = (
                ConfidenceLevel.LOW
                if result[index].confidence == ConfidenceLevel.LOW
                else ConfidenceLevel.MEDIUM
            )
            result[index] = result[index].model_copy(
                update={
                    "warning_codes": warnings,
                    "validation_notes": notes,
                    "validation_status": ValidationStatus.REVIEW,
                    "confidence": confidence,
                }
            )
    return result
