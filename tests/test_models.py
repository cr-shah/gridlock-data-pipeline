from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from gridlock_pipeline.extraction.page_model import ExtractedPage
from gridlock_pipeline.models import (
    ConfidenceLevel,
    FieldProvenance,
    ProjectObservation,
    SourceDocument,
    SourceDocumentCandidate,
    ValidationStatus,
)


def observation_data() -> dict:
    return {
        "observation_id": "sertp-2026-abc123",
        "source": "sertp",
        "planning_year": 2026,
        "document_id": "sertp-2026-preliminary-non-ceii",
        "balancing_authority_raw": "SOUTHERN",
        "balancing_authority_normalized": "SOUTHERN",
        "owner_prefix_raw": "SOCO:",
        "project_name_raw": "SOCO: Alpha 230 kV Line",
        "project_name_normalized": "SOCO: Alpha 230 kV Line",
        "raw_record_text": "In-Service Year\n2028\nProject Name\nSOCO: Alpha 230 kV Line",
        "in_service_year_raw": "2028",
        "in_service_year": 2028,
        "description_raw": "Rebuild the Alpha line.",
        "supporting_statement_raw": "Addresses thermal loading.",
        "voltage_raw": ["230 kV"],
        "voltage_kv": [230.0],
        "project_type": "line_rebuild",
        "project_type_confidence": ConfidenceLevel.HIGH,
        "project_type_method": "project_type_rules_v1",
        "location_mentions": ["Alpha"],
        "endpoint_candidates": ["Alpha"],
        "length_raw": [],
        "length_miles": [],
        "pdf_page_start": 12,
        "pdf_page_end": 13,
        "printed_page_start": 9,
        "printed_page_end": 10,
        "source_url": "https://www.southeasternrtp.com/report.pdf",
        "source_title": "2026 SERTP Preliminary Expansion Plan Report (Non-CEII)",
        "source_sha256": "a" * 64,
        "extraction_engine": "PyMuPDF",
        "extraction_engine_version": "1.28.2",
        "parser_version": "sertp_2026_v1",
        "pipeline_version": "0.1.0",
        "extraction_confidence": ConfidenceLevel.HIGH,
        "validation_status": ValidationStatus.VALID,
        "warning_codes": [],
        "validation_notes": [],
        "field_provenance": {
            "balancing_authority_normalized": FieldProvenance(
                origin="normalized", source_fields=["balancing_authority_raw"]
            ),
            "owner_prefix_raw": FieldProvenance(
                origin="derived_from_source",
                source_fields=["project_name_raw"],
                rule_id="owner_prefix_v1",
            ),
            "project_name_normalized": FieldProvenance(
                origin="normalized",
                source_fields=["project_name_raw"],
                rule_id="project_name_v1",
            ),
            "in_service_year": FieldProvenance(
                origin="derived_from_source",
                source_fields=["in_service_year_raw"],
                rule_id="in_service_year_v1",
            ),
            "voltage_kv": FieldProvenance(
                origin="derived_from_source",
                source_fields=["project_name_raw"],
                rule_id="voltage_kv_v1",
            ),
            "project_type": FieldProvenance(
                origin="deterministic_rule",
                source_fields=["project_name_raw", "description_raw"],
                rule_id="project_type_rules_v1",
            ),
            "location_mentions": FieldProvenance(
                origin="derived_from_source",
                source_fields=["project_name_raw"],
                rule_id="location_mentions_v1",
            ),
            "endpoint_candidates": FieldProvenance(
                origin="derived_from_source",
                source_fields=["project_name_raw"],
                rule_id="endpoint_candidates_v1",
            ),
        },
        "latitude": None,
        "longitude": None,
        "geometry": None,
    }


def test_project_observation_preserves_required_provenance() -> None:
    observation = ProjectObservation.model_validate(observation_data())

    assert observation.raw_record_text.startswith("In-Service Year")
    assert observation.pdf_page_range == [12, 13]
    assert observation.extraction_engine == "PyMuPDF"
    assert observation.latitude is None
    assert observation.longitude is None
    assert observation.geometry is None


def test_project_observation_rejects_reversed_page_range() -> None:
    data = observation_data()
    data["pdf_page_end"] = 11

    with pytest.raises(ValidationError, match="page range"):
        ProjectObservation.model_validate(data)


def test_project_observation_requires_provenance_for_derived_value() -> None:
    data = observation_data()
    del data["field_provenance"]["voltage_kv"]

    with pytest.raises(ValidationError, match="voltage_kv"):
        ProjectObservation.model_validate(data)


def test_source_and_page_models_validate_identity() -> None:
    candidate = SourceDocumentCandidate(
        title="2026 report",
        url="https://www.southeasternrtp.com/report.pdf",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        planning_year=2026,
        score=100,
    )
    document = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title=candidate.title,
        discovery_url=candidate.discovery_url,
        source_url=candidate.url,
        final_url=candidate.url,
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=123,
        sha256="b" * 64,
        public_access=True,
        pipeline_version="0.1.0",
    )
    page = ExtractedPage(
        pdf_page_index=0,
        printed_page_number=1,
        text="Project Name",
        source_sha256=document.sha256,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )

    assert document.source_url == candidate.url
    assert page.source_sha256 == document.sha256


def test_project_observation_schema_is_machine_readable() -> None:
    schema = ProjectObservation.model_json_schema()

    assert schema["title"] == "ProjectObservation"
    assert "raw_record_text" in schema["properties"]
    assert "field_provenance" in schema["properties"]
