from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridlock_pipeline.extraction import read_pages_jsonl
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers import ParserDiagnostic, Sertp2026Parser
from gridlock_pipeline.validation.invariants import validate_observation
from gridlock_pipeline.validation.quality import (
    QualityGateError,
    build_quality_report,
    enforce_run_gates,
    write_data_quality,
    write_review_queue,
)

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def parsed_observations():
    document = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 report",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        public_access=True,
        pipeline_version="0.1.0",
    )
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    return [
        validate_observation(item)
        for item in Sertp2026Parser().parse(pages, document).observations
    ]


def test_quality_report_contains_authority_confidence_warning_and_parser_counts() -> None:
    observations = parsed_observations()
    observations[0] = validate_observation(
        observations[0].model_copy(update={"description_raw": None})
    )
    diagnostics = [ParserDiagnostic(code="TEST_DIAGNOSTIC", message="test")]

    report = build_quality_report(observations, diagnostics=diagnostics)

    assert report.total_observations == 22
    assert report.balancing_authority_counts == {
        "AECI": 1,
        "DUKE CAROLINAS": 1,
        "SOUTHERN": 18,
        "TVA": 2,
    }
    assert report.confidence_counts["MEDIUM"] >= 1
    assert report.warning_counts["MISSING_DESCRIPTION"] == 1
    assert report.parser_diagnostic_counts == {"TEST_DIAGNOSTIC": 1}


def test_zero_and_implausibly_few_record_runs_fail_gates() -> None:
    empty = build_quality_report([])
    few = build_quality_report(parsed_observations()[:3])

    with pytest.raises(QualityGateError, match="no observations"):
        enforce_run_gates(empty)
    with pytest.raises(QualityGateError, match="implausibly few"):
        enforce_run_gates(few, minimum_records=10)


def test_major_quality_collapse_fails_against_previous_report() -> None:
    previous = build_quality_report(parsed_observations())
    current = build_quality_report(parsed_observations()[:5])

    with pytest.raises(QualityGateError, match="collapse"):
        enforce_run_gates(current, previous_report=previous, minimum_records=1)


def test_quality_and_review_outputs_are_written(tmp_path: Path) -> None:
    observations = parsed_observations()
    observations[0] = validate_observation(
        observations[0].model_copy(update={"supporting_statement_raw": None})
    )
    report = build_quality_report(observations)

    write_data_quality(report, tmp_path / "data_quality.json")
    write_review_queue(observations, tmp_path / "review_queue.csv")

    assert '"total_observations": 22' in (tmp_path / "data_quality.json").read_text()
    assert "MISSING_SUPPORTING_STATEMENT" in (tmp_path / "review_queue.csv").read_text()
