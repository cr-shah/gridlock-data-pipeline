"""Stable project-observation contract."""

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ValidationStatus(StrEnum):
    VALID = "valid"
    REVIEW = "review"
    INVALID = "invalid"


class ConfidenceLevel(StrEnum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class FieldProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: Literal["normalized", "derived_from_source", "deterministic_rule"]
    source_fields: list[str] = Field(min_length=1)
    rule_id: str | None = None
    notes: str | None = None


class ProjectObservation(BaseModel):
    """One source-faithful transmission project observation."""

    model_config = ConfigDict(extra="forbid")

    observation_id: str
    source: str
    planning_year: int
    document_id: str
    balancing_authority_raw: str
    balancing_authority_normalized: str | None = None
    owner_prefix_raw: str | None = None
    project_name_raw: str
    project_name_normalized: str | None = None
    raw_record_text: str
    in_service_year_raw: str | None = None
    in_service_year: int | None = None
    description_raw: str | None = None
    supporting_statement_raw: str | None = None
    voltage_raw: list[str] = Field(default_factory=list)
    voltage_kv: list[float] = Field(default_factory=list)
    project_type: str | None = None
    project_type_confidence: ConfidenceLevel | None = None
    project_type_method: str | None = None
    location_mentions: list[str] = Field(default_factory=list)
    endpoint_candidates: list[str] = Field(default_factory=list)
    length_raw: list[str] = Field(default_factory=list)
    length_miles: list[float] = Field(default_factory=list)
    pdf_page_start: int = Field(ge=0)
    pdf_page_end: int = Field(ge=0)
    printed_page_start: int | None = None
    printed_page_end: int | None = None
    source_url: str
    source_title: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_engine: str
    extraction_engine_version: str
    parser_version: str
    pipeline_version: str
    confidence: ConfidenceLevel = ConfidenceLevel.HIGH
    extraction_confidence: ConfidenceLevel
    validation_status: ValidationStatus
    warning_codes: list[str] = Field(default_factory=list)
    validation_notes: list[str] = Field(default_factory=list)
    field_provenance: dict[str, FieldProvenance] = Field(default_factory=dict)
    latitude: None = None
    longitude: None = None
    geometry: None = None

    @property
    def pdf_page_range(self) -> list[int]:
        return [self.pdf_page_start, self.pdf_page_end]

    @model_validator(mode="after")
    def validate_ranges_and_provenance(self) -> "ProjectObservation":
        if self.pdf_page_end < self.pdf_page_start:
            raise ValueError("PDF page range ends before it starts")
        if (
            self.printed_page_start is not None
            and self.printed_page_end is not None
            and self.printed_page_end < self.printed_page_start
        ):
            raise ValueError("printed page range ends before it starts")

        derived_fields = (
            "balancing_authority_normalized",
            "owner_prefix_raw",
            "project_name_normalized",
            "in_service_year",
            "voltage_kv",
            "project_type",
            "location_mentions",
            "endpoint_candidates",
            "length_miles",
        )
        missing = [
            name
            for name in derived_fields
            if self._is_populated(getattr(self, name)) and name not in self.field_provenance
        ]
        if missing:
            raise ValueError(f"missing field provenance for: {', '.join(missing)}")
        return self

    @staticmethod
    def _is_populated(value: Any) -> bool:
        return value is not None and value != "" and value != []


class DescProjectObservation(ProjectObservation):
    """DESC fields present in the SCRTP current-project report."""

    utility: Literal["DESC"] = "DESC"
    project_id_raw: str
    project_need_raw: str | None = None
    project_status_raw: str | None = None
    planned_in_service_date_raw: str | None = None
    estimated_cost_raw: str | None = None
    estimated_cost_usd: int | None = Field(default=None, ge=0)


class GeorgiaPowerProjectObservation(ProjectObservation):
    """Fields explicitly published on Georgia Power current-project pages."""

    utility: Literal["GPC"] = "GPC"
    county_region_raw: str
    project_type_raw: str
    timeline_raw: list[str] = Field(default_factory=list)
    construction_start_raw: list[str] = Field(default_factory=list)
    completion_target_raw: str | None = None
