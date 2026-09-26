"""Parser for the current DESC planned-project PDF published by SCRTP."""

import hashlib
import re
from collections.abc import Sequence

from gridlock_pipeline import __version__
from gridlock_pipeline.extraction import ExtractedPage
from gridlock_pipeline.models import (
    ConfidenceLevel,
    DescProjectObservation,
    FieldProvenance,
    SourceDocument,
    ValidationStatus,
)
from gridlock_pipeline.normalization import (
    classify_project_type,
    extract_candidate_locations,
    extract_lengths,
    extract_voltage,
    normalize_project_name,
)
from gridlock_pipeline.parsers.base import ParseResult

PARSER_VERSION = "scrtp_desc_current_v1"
LABELS = (
    "Project ID",
    "Project Description",
    "Project Need",
    "Project Status",
    "Planned In-Service Date",
    "Estimated Project Cost",
)


def _lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()]


def _section(lines: list[str], label: str, next_label: str | None) -> str | None:
    try:
        start = lines.index(label) + 1
    except ValueError:
        return None
    end = len(lines)
    if next_label is not None:
        try:
            end = lines.index(next_label, start)
        except ValueError:
            pass
    value = " ".join(lines[start:end]).strip()
    return value or None


def _year_from_date(value: str | None) -> int | None:
    if value is None or " and " in value.casefold():
        return None
    match = re.fullmatch(r"\d{1,2}/\d{1,2}/(\d{2}|\d{4})", value.strip())
    if not match:
        return None
    year = int(match.group(1))
    return 2000 + year if year < 100 else year


def _cost(value: str | None) -> int | None:
    if value is None:
        return None
    amounts = re.findall(r"\$\s*([0-9][0-9,]*)", value)
    if not amounts:
        return None
    return int(amounts[-1].replace(",", ""))


class ScrtpDescParser:
    """Parse one source-faithful DESC record from each report page."""

    def parse(
        self, pages: Sequence[ExtractedPage], document: SourceDocument
    ) -> ParseResult:
        if document.source != "scrtp" or document.planning_year != 2026:
            raise ValueError("ScrtpDescParser accepts only SCRTP planning year 2026")
        observations = [
            self._parse_page(page, document)
            for page in sorted(pages, key=lambda item: item.pdf_page_index)
            if "Project ID" in page.text
        ]
        return ParseResult(observations=observations)

    def _parse_page(
        self, page: ExtractedPage, document: SourceDocument
    ) -> DescProjectObservation:
        lines = _lines(page.text)
        project_id = _section(lines, LABELS[0], LABELS[1]) or ""
        description = _section(lines, LABELS[1], LABELS[2])
        need = _section(lines, LABELS[2], LABELS[3])
        status = _section(lines, LABELS[3], LABELS[4])
        date_raw = _section(lines, LABELS[4], LABELS[5])
        cost_raw = _section(lines, LABELS[5], None)

        try:
            title_start = lines.index("5 Year Budget") + 1
            title_end = lines.index("Project ID", title_start)
            name_raw = " ".join(lines[title_start:title_end]).strip()
        except ValueError:
            name_raw = ""

        normalized_name, name_provenance = normalize_project_name(name_raw)
        voltage_raw, voltage_kv, voltage_provenance = extract_voltage(
            " ".join(filter(None, (name_raw, description)))
        )
        project_type, type_confidence, type_method, type_provenance = classify_project_type(
            name_raw, description
        )
        mentions, endpoints, locations_provenance = extract_candidate_locations(name_raw)
        length_raw, length_miles, length_provenance = extract_lengths(description or "")
        year = _year_from_date(date_raw)
        provenance: dict[str, FieldProvenance] = {
            "balancing_authority_normalized": FieldProvenance(
                origin="deterministic_rule",
                source_fields=["source"],
                rule_id="scrtp_desc_utility_v1",
            ),
            "project_name_normalized": name_provenance,
            "project_type": type_provenance,
        }
        optional = {
            "in_service_year": FieldProvenance(
                origin="derived_from_source",
                source_fields=["planned_in_service_date_raw"],
                rule_id="scrtp_desc_date_year_v1",
            )
            if year is not None
            else None,
            "voltage_kv": voltage_provenance,
            "location_mentions": locations_provenance,
            "endpoint_candidates": locations_provenance,
            "length_miles": length_provenance,
        }
        provenance.update({key: value for key, value in optional.items() if value is not None})

        raw_record = "\n".join(lines)
        page_label = re.search(r"\bProject\s+(\d+)\s+of\s+\d+\b", raw_record)
        printed_page = int(page_label.group(1)) if page_label else page.printed_page_number
        stable_facts = "\x1f".join((document.sha256, project_id, name_raw, raw_record))
        observation_id = (
            f"scrtp-desc-2026-{hashlib.sha256(stable_facts.encode()).hexdigest()[:20]}"
        )
        extraction_confidence = (
            ConfidenceLevel.MEDIUM if page.warnings else ConfidenceLevel.HIGH
        )
        return DescProjectObservation(
            observation_id=observation_id,
            source="scrtp",
            planning_year=2026,
            document_id=document.document_id,
            balancing_authority_raw="DESC",
            balancing_authority_normalized="DESC",
            project_name_raw=name_raw,
            project_name_normalized=normalized_name,
            raw_record_text=raw_record,
            in_service_year_raw=date_raw,
            in_service_year=year,
            description_raw=description,
            supporting_statement_raw=need,
            voltage_raw=voltage_raw,
            voltage_kv=voltage_kv,
            project_type=project_type,
            project_type_confidence=type_confidence,
            project_type_method=type_method,
            location_mentions=mentions,
            endpoint_candidates=endpoints,
            length_raw=length_raw,
            length_miles=length_miles,
            pdf_page_start=page.pdf_page_index,
            pdf_page_end=page.pdf_page_index,
            printed_page_start=printed_page,
            printed_page_end=printed_page,
            source_url=document.final_url,
            source_title=document.title,
            source_sha256=document.sha256,
            extraction_engine=page.extraction_engine,
            extraction_engine_version=page.extraction_engine_version,
            parser_version=PARSER_VERSION,
            pipeline_version=__version__,
            extraction_confidence=extraction_confidence,
            validation_status=ValidationStatus.VALID,
            field_provenance=provenance,
            utility="DESC",
            project_id_raw=project_id,
            project_need_raw=need,
            project_status_raw=status,
            planned_in_service_date_raw=date_raw,
            estimated_cost_raw=cost_raw,
            estimated_cost_usd=_cost(cost_raw),
        )
