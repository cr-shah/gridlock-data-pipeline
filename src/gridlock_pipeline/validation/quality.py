"""Review queue, quality reporting, and run-level gates."""

import csv
import json
from collections import Counter
from collections.abc import Sequence
from pathlib import Path

from gridlock_pipeline.models import ProjectObservation, ValidationStatus
from gridlock_pipeline.parsers import ParserDiagnostic
from gridlock_pipeline.validation.invariants import KNOWN_AUTHORITIES
from gridlock_pipeline.validation.schema import DataQualityReport, ReviewQueueEntry


class QualityGateError(RuntimeError):
    """Raised before processed outputs can replace known-good artifacts."""


def build_review_queue(observations: Sequence[ProjectObservation]) -> list[ReviewQueueEntry]:
    return [
        ReviewQueueEntry(
            observation_id=item.observation_id,
            project_name_raw=item.project_name_raw,
            balancing_authority_raw=item.balancing_authority_raw,
            pdf_page_start=item.pdf_page_start,
            pdf_page_end=item.pdf_page_end,
            confidence=item.confidence.value,
            validation_status=item.validation_status.value,
            warning_codes_json=json.dumps(item.warning_codes, separators=(",", ":")),
            source_url=item.source_url,
        )
        for item in observations
        if item.warning_codes or item.validation_status != ValidationStatus.VALID
    ]


def build_quality_report(
    observations: Sequence[ProjectObservation],
    *,
    diagnostics: Sequence[ParserDiagnostic] = (),
) -> DataQualityReport:
    warning_counts = Counter(code for item in observations for code in item.warning_codes)
    queue = build_review_queue(observations)
    return DataQualityReport(
        total_observations=len(observations),
        balancing_authority_counts=dict(
            sorted(Counter(item.balancing_authority_raw for item in observations).items())
        ),
        confidence_counts=dict(
            sorted(Counter(item.confidence.value for item in observations).items())
        ),
        validation_status_counts=dict(
            sorted(Counter(item.validation_status.value for item in observations).items())
        ),
        warning_counts=dict(sorted(warning_counts.items())),
        parser_diagnostic_counts=dict(sorted(Counter(item.code for item in diagnostics).items())),
        review_queue_count=len(queue),
        invalid_count=sum(
            item.validation_status == ValidationStatus.INVALID for item in observations
        ),
    )


def enforce_run_gates(
    report: DataQualityReport,
    previous_report: DataQualityReport | None = None,
    *,
    minimum_records: int = 10,
) -> None:
    if report.total_observations == 0:
        raise QualityGateError("no observations were parsed")
    if report.total_observations < minimum_records:
        raise QualityGateError(
            f"implausibly few observations: {report.total_observations} < {minimum_records}"
        )
    recognized_authorities = sum(
        count
        for authority, count in report.balancing_authority_counts.items()
        if authority in KNOWN_AUTHORITIES
    )
    if recognized_authorities == 0:
        raise QualityGateError("no recognized balancing authorities were parsed")
    if report.invalid_count / report.total_observations > 0.05:
        raise QualityGateError("required-field failure rate exceeds five percent")
    if previous_report and report.total_observations < previous_report.total_observations * 0.5:
        raise QualityGateError("observation-count quality collapse relative to previous run")
    if previous_report:
        previous_recognized = sum(
            count
            for authority, count in previous_report.balancing_authority_counts.items()
            if authority in KNOWN_AUTHORITIES
        )
        if previous_recognized and recognized_authorities < previous_recognized * 0.5:
            raise QualityGateError("recognized-authority quality collapse relative to previous run")
        previous_high = previous_report.confidence_counts.get("HIGH", 0)
        current_high = report.confidence_counts.get("HIGH", 0)
        if previous_high and current_high < previous_high * 0.5:
            raise QualityGateError("confidence collapse relative to previous run")


def write_data_quality(report: DataQualityReport, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_review_queue(observations: Sequence[ProjectObservation], path: Path) -> None:
    queue = build_review_queue(observations)
    fieldnames = list(ReviewQueueEntry.model_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for item in queue:
            writer.writerow(item.model_dump(mode="json"))
