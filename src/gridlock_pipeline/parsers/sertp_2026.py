"""Strict state-machine parser for the 2026 SERTP public report."""

import hashlib
import re
from collections.abc import Sequence
from dataclasses import dataclass, field

from gridlock_pipeline import __version__
from gridlock_pipeline.extraction import ExtractedPage
from gridlock_pipeline.models import (
    ConfidenceLevel,
    FieldProvenance,
    ProjectObservation,
    SourceDocument,
    ValidationStatus,
)
from gridlock_pipeline.normalization import (
    classify_project_type,
    extract_candidate_locations,
    extract_lengths,
    extract_owner_prefix,
    extract_voltage,
    normalize_balancing_authority,
    normalize_project_name,
    parse_in_service_year,
)
from gridlock_pipeline.parsers.base import ParserDiagnostic, ParseResult

PARSER_VERSION = "sertp_2026_v1"
FOOTER_PATTERN = re.compile(r"\bPage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)


@dataclass
class _Record:
    balancing_authority: str
    pdf_page_start: int
    printed_page_start: int | None
    pdf_page_end: int
    printed_page_end: int | None
    raw_lines: list[str] = field(default_factory=list)
    year_parts: list[str] = field(default_factory=list)
    name_parts: list[str] = field(default_factory=list)
    description_parts: list[str] = field(default_factory=list)
    supporting_parts: list[str] = field(default_factory=list)


def _authority_from_page(text: str) -> str | None:
    header = " ".join(text.splitlines()[:5]).upper().replace(" ", "")
    if "DUKE" in header and "PROGRESS" in header and "EAST" in header:
        return "DUKE PROGRESS EAST"
    if "DUKE" in header and "PROGRESS" in header and "WEST" in header:
        return "DUKE PROGRESS WEST"
    if "DUKE" in header and "CAROLINAS" in header:
        return "DUKE CAROLINAS"
    if "LG&E/KU" in header:
        return "LG&E/KU"
    for authority in ("SOUTHERN", "AECI", "TVA"):
        if authority in header:
            return authority
    return None


def _clean_lines(text: str) -> list[str]:
    cleaned: list[str] = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        upper = line.upper()
        if upper in {"SERTP TRANSMISSION PROJECTS", "BALANCING AUTHORITY"}:
            continue
        if "SERTP" in upper and "PROJECTS" in upper and (
            "CEII" in upper or "AUTHORITY" in upper
        ):
            continue
        if FOOTER_PATTERN.search(line) and re.search(r"\d{2}/\d{2}/\d{4}", line):
            continue
        cleaned.append(line)
    return cleaned


def _collapse(parts: list[str]) -> str | None:
    value = re.sub(r"\s+", " ", " ".join(parts)).strip()
    return value or None


class Sertp2026Parser:
    """Parse only the verified 2026 report layout."""

    def parse(
        self,
        pages: Sequence[ExtractedPage],
        document: SourceDocument,
    ) -> ParseResult:
        if document.planning_year != 2026:
            raise ValueError("Sertp2026Parser accepts only planning year 2026")
        observations: list[ProjectObservation] = []
        diagnostics: list[ParserDiagnostic] = []
        authority: str | None = None
        record: _Record | None = None
        state: str | None = None

        for page in sorted(pages, key=lambda item: item.pdf_page_index):
            page_authority = _authority_from_page(page.text)
            if page_authority:
                authority = page_authority
            for line in _clean_lines(page.text):
                if line.startswith("In-Service"):
                    if record is not None:
                        observations.append(self._build_observation(record, document, pages))
                    if authority is None:
                        authority = "UNKNOWN"
                        diagnostics.append(
                            ParserDiagnostic(
                                code="UNKNOWN_BALANCING_AUTHORITY",
                                message="Record began before an authority header was recognized.",
                                pdf_page_index=page.pdf_page_index,
                            )
                        )
                    record = _Record(
                        balancing_authority=authority,
                        pdf_page_start=page.pdf_page_index,
                        printed_page_start=page.printed_page_number,
                        pdf_page_end=page.pdf_page_index,
                        printed_page_end=page.printed_page_number,
                    )
                    state = "year"
                    record.raw_lines.append(line)
                    year = re.search(r"\b((?:19|20)\d{2})\b", line)
                    if year:
                        record.year_parts.append(year.group(1))
                    continue
                if record is None:
                    continue

                record.pdf_page_end = page.pdf_page_index
                record.printed_page_end = page.printed_page_number
                record.raw_lines.append(line)
                if line == "Year:":
                    continue
                if line.startswith("Project Name:"):
                    state = "name"
                    value = line.partition(":")[2].strip()
                    if value:
                        record.name_parts.append(value)
                    continue
                if line.startswith("Description:"):
                    state = "description"
                    value = line.partition(":")[2].strip()
                    if value:
                        record.description_parts.append(value)
                    continue
                if line.startswith("Supporting"):
                    state = "supporting"
                    value = re.sub(r"^Supporting\s*", "", line).strip()
                    if value:
                        record.supporting_parts.append(value)
                    continue
                if line.startswith("Statement:"):
                    state = "supporting"
                    value = line.partition(":")[2].strip()
                    if value:
                        record.supporting_parts.append(value)
                    continue
                if state == "year":
                    year = re.fullmatch(r"(?:19|20)\d{2}", line)
                    if year:
                        record.year_parts.append(year.group(0))
                elif state == "name":
                    record.name_parts.append(line)
                elif state == "description":
                    record.description_parts.append(line)
                elif state == "supporting":
                    record.supporting_parts.append(line)

        if record is not None:
            observations.append(self._build_observation(record, document, pages))
        return ParseResult(observations=observations, diagnostics=diagnostics)

    def _build_observation(
        self,
        record: _Record,
        document: SourceDocument,
        pages: Sequence[ExtractedPage],
    ) -> ProjectObservation:
        name_raw = _collapse(record.name_parts) or ""
        year_raw = _collapse(record.year_parts)
        description_raw = _collapse(record.description_parts)
        supporting_raw = _collapse(record.supporting_parts)

        authority, authority_provenance = normalize_balancing_authority(
            record.balancing_authority
        )
        normalized_name, name_provenance = normalize_project_name(name_raw)
        owner_prefix, owner_provenance = extract_owner_prefix(name_raw)
        in_service_year, year_provenance = parse_in_service_year(year_raw)
        voltage_raw, voltage_kv, voltage_provenance = extract_voltage(
            " ".join(part for part in (name_raw, description_raw, supporting_raw) if part)
        )
        project_type, type_confidence, type_method, type_provenance = classify_project_type(
            name_raw, description_raw
        )
        mentions, endpoints, locations_provenance = extract_candidate_locations(name_raw)
        length_raw, length_miles, length_provenance = extract_lengths(description_raw or "")

        provenance: dict[str, FieldProvenance] = {
            "balancing_authority_normalized": authority_provenance,
            "project_name_normalized": name_provenance,
            "project_type": type_provenance,
        }
        optional_provenance = {
            "owner_prefix_raw": owner_provenance,
            "in_service_year": year_provenance,
            "voltage_kv": voltage_provenance,
            "location_mentions": locations_provenance,
            "endpoint_candidates": locations_provenance,
            "length_miles": length_provenance,
        }
        provenance.update(
            {name: item for name, item in optional_provenance.items() if item is not None}
        )

        stable_facts = "\x1f".join(
            [document.sha256, authority, year_raw or "", name_raw, description_raw or ""]
        )
        observation_id = f"sertp-2026-{hashlib.sha256(stable_facts.encode()).hexdigest()[:20]}"
        page_lookup = {page.pdf_page_index: page for page in pages}
        relevant_pages = [
            page_lookup[index]
            for index in range(record.pdf_page_start, record.pdf_page_end + 1)
            if index in page_lookup
        ]
        has_extraction_warning = any(page.warnings for page in relevant_pages)
        extraction_confidence = (
            ConfidenceLevel.MEDIUM if has_extraction_warning else ConfidenceLevel.HIGH
        )
        engine = relevant_pages[0].extraction_engine
        engine_version = relevant_pages[0].extraction_engine_version

        return ProjectObservation(
            observation_id=observation_id,
            source=document.source,
            planning_year=document.planning_year,
            document_id=document.document_id,
            balancing_authority_raw=record.balancing_authority,
            balancing_authority_normalized=authority,
            owner_prefix_raw=owner_prefix,
            project_name_raw=name_raw,
            project_name_normalized=normalized_name,
            raw_record_text="\n".join(record.raw_lines),
            in_service_year_raw=year_raw,
            in_service_year=in_service_year,
            description_raw=description_raw,
            supporting_statement_raw=supporting_raw,
            voltage_raw=voltage_raw,
            voltage_kv=voltage_kv,
            project_type=project_type,
            project_type_confidence=type_confidence,
            project_type_method=type_method,
            location_mentions=mentions,
            endpoint_candidates=endpoints,
            length_raw=length_raw,
            length_miles=length_miles,
            pdf_page_start=record.pdf_page_start,
            pdf_page_end=record.pdf_page_end,
            printed_page_start=record.printed_page_start,
            printed_page_end=record.printed_page_end,
            source_url=document.final_url,
            source_title=document.title,
            source_sha256=document.sha256,
            extraction_engine=engine,
            extraction_engine_version=engine_version,
            parser_version=PARSER_VERSION,
            pipeline_version=__version__,
            extraction_confidence=extraction_confidence,
            validation_status=ValidationStatus.VALID,
            warning_codes=[],
            validation_notes=[],
            field_provenance=provenance,
            latitude=None,
            longitude=None,
            geometry=None,
        )

