import json
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.extraction import read_pages_jsonl
from gridlock_pipeline.models import ConfidenceLevel, SourceDocument, ValidationStatus
from gridlock_pipeline.parsers import Sertp2026Parser
from gridlock_pipeline.validation.invariants import (
    flag_duplicate_candidates,
    validate_observation,
)
from gridlock_pipeline.validation.quality import build_review_queue

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def sample_observation():
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
    return Sertp2026Parser().parse(pages, document).observations[0]


def test_missing_project_name_is_invalid_but_retained() -> None:
    observation = sample_observation().model_copy(update={"project_name_raw": ""})

    validated = validate_observation(observation)

    assert validated.observation_id == observation.observation_id
    assert validated.validation_status == ValidationStatus.INVALID
    assert validated.confidence == ConfidenceLevel.LOW
    assert "MISSING_PROJECT_NAME" in validated.warning_codes


def test_missing_optional_fields_are_review_warnings() -> None:
    observation = sample_observation().model_copy(
        update={"description_raw": None, "supporting_statement_raw": None}
    )

    validated = validate_observation(observation)

    assert validated.validation_status == ValidationStatus.REVIEW
    assert validated.confidence == ConfidenceLevel.MEDIUM
    assert validated.warning_codes == ["MISSING_DESCRIPTION", "MISSING_SUPPORTING_STATEMENT"]


def test_unusual_year_unknown_authority_prefix_and_suspicious_name_are_explainable() -> None:
    observation = sample_observation().model_copy(
        update={
            "in_service_year": 1901,
            "balancing_authority_normalized": "UNKNOWN",
            "owner_prefix_raw": "XYZ:",
            "project_name_raw": "TS25-422",
            "project_name_normalized": "TS25-422",
        }
    )

    validated = validate_observation(observation)

    assert validated.confidence == ConfidenceLevel.LOW
    assert set(validated.warning_codes) >= {
        "UNUSUAL_IN_SERVICE_YEAR",
        "UNKNOWN_BALANCING_AUTHORITY",
        "UNKNOWN_OWNER_PREFIX",
        "SUSPICIOUS_PROJECT_NAME",
    }


def test_ambiguous_endpoint_detection_enters_review() -> None:
    observation = sample_observation().model_copy(
        update={
            "project_name_raw": "ALPHA - BETA 230 KV LINE",
            "project_name_normalized": "ALPHA - BETA 230 KV LINE",
            "endpoint_candidates": [],
        }
    )

    validated = validate_observation(observation)

    assert "AMBIGUOUS_ENDPOINTS" in validated.warning_codes
    assert validated.validation_status == ValidationStatus.REVIEW


def test_duplicate_candidates_are_flagged_without_merging() -> None:
    first = sample_observation()
    second = first.model_copy(update={"observation_id": "another-id"})

    result = flag_duplicate_candidates([first, second])

    assert len(result) == 2
    assert all("POSSIBLE_DUPLICATE" in item.warning_codes for item in result)


def test_same_name_with_different_description_is_not_a_duplicate() -> None:
    first = sample_observation()
    second = first.model_copy(
        update={"observation_id": "another-id", "description_raw": "A different circuit phase."}
    )

    result = flag_duplicate_candidates([first, second])

    assert all("POSSIBLE_DUPLICATE" not in item.warning_codes for item in result)


def test_same_name_with_different_supporting_statement_is_not_a_duplicate() -> None:
    first = sample_observation()
    second = first.model_copy(
        update={
            "observation_id": "another-id",
            "supporting_statement_raw": "A different circuit overloads.",
        }
    )

    result = flag_duplicate_candidates([first, second])

    assert all("POSSIBLE_DUPLICATE" not in item.warning_codes for item in result)


def test_review_queue_is_machine_readable() -> None:
    reviewed = validate_observation(
        sample_observation().model_copy(update={"supporting_statement_raw": None})
    )

    queue = build_review_queue([reviewed])

    assert len(queue) == 1
    assert queue[0].observation_id == reviewed.observation_id
    assert json.loads(queue[0].warning_codes_json) == ["MISSING_SUPPORTING_STATEMENT"]
