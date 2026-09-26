"""Validation, review, and quality-report contracts."""

from pydantic import BaseModel, ConfigDict, Field


class ReviewQueueEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    observation_id: str
    project_name_raw: str
    balancing_authority_raw: str
    pdf_page_start: int
    pdf_page_end: int
    confidence: str
    validation_status: str
    warning_codes_json: str
    source_url: str


class DataQualityReport(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = "1.0"
    total_observations: int = Field(ge=0)
    balancing_authority_counts: dict[str, int]
    confidence_counts: dict[str, int]
    validation_status_counts: dict[str, int]
    warning_counts: dict[str, int]
    parser_diagnostic_counts: dict[str, int]
    review_queue_count: int = Field(ge=0)
    invalid_count: int = Field(ge=0)

