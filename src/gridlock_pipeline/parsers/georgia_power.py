"""Parser for project pages linked by Georgia Power's current-project listing."""

import hashlib
import re
from dataclasses import dataclass

import bs4
from bs4 import BeautifulSoup, Tag

from gridlock_pipeline import __version__
from gridlock_pipeline.discovery import GeorgiaPowerProjectLink
from gridlock_pipeline.models import (
    ConfidenceLevel,
    FieldProvenance,
    GeorgiaPowerProjectObservation,
    SourceDocument,
    ValidationStatus,
)
from gridlock_pipeline.normalization import (
    extract_candidate_locations,
    extract_lengths,
    extract_voltage,
    normalize_project_name,
)
from gridlock_pipeline.parsers.base import ParseResult

PARSER_VERSION = "georgia_power_current_v1"
TYPE_MAP = {
    "Area Project": "area_project",
    "New Transmission Line": "new_transmission_line",
    "Transmission Line Upgrade": "transmission_line_upgrade",
}


@dataclass(frozen=True)
class GeorgiaPowerProjectPage:
    project: GeorgiaPowerProjectLink
    html: str
    sha256: str


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _heading(soup: BeautifulSoup, label: str) -> Tag | None:
    expected = label.casefold()
    for heading in soup.find_all(re.compile(r"^h[1-6]$")):
        if _clean(heading.get_text(" ", strip=True)).casefold() == expected:
            return heading
    return None


def _section_text(heading: Tag | None) -> str | None:
    if heading is None:
        return None
    container = heading.find_parent(class_="content-card--content") or heading.parent
    values = [
        _clean(item.get_text(" ", strip=True))
        for item in container.find_all(["p", "li"])
    ]
    values = [value for value in values if value]
    return " ".join(dict.fromkeys(values)) or None


def _included_text(heading: Tag | None) -> str | None:
    if heading is None:
        return None
    values: list[str] = []
    for item in heading.find_all_next(["h2", "h3", "p", "li"]):
        value = _clean(item.get_text(" ", strip=True))
        if item.name in {"h2", "h3"}:
            if value.casefold() == "what to expect":
                break
            continue
        if item.name == "p" and item.find_parent("li") is not None:
            continue
        if value:
            values.append(value)
    return " ".join(dict.fromkeys(values)) or None


def _timeline(soup: BeautifulSoup) -> list[tuple[str, str]]:
    heading = _heading(soup, "Project Timeline")
    table = heading.find_next("table") if heading is not None else None
    if table is None:
        return []
    rows: list[tuple[str, str]] = []
    for row in table.find_all("tr"):
        cells = row.find_all(["th", "td"], recursive=False)
        if len(cells) < 2:
            continue
        date = _clean(cells[0].get_text(" ", strip=True))
        milestone = _clean(cells[1].get_text(" ", strip=True))
        if date and milestone:
            rows.append((date, milestone))
    return rows


class GeorgiaPowerParser:
    """Create one source-faithful observation per linked official detail page."""

    def parse(
        self,
        pages: list[GeorgiaPowerProjectPage],
        document: SourceDocument,
    ) -> ParseResult:
        if document.source != "georgia_power" or document.planning_year != 2026:
            raise ValueError(
                "GeorgiaPowerParser accepts only Georgia Power planning year 2026"
            )
        observations = [
            self._parse_page(page, document, index)
            for index, page in enumerate(pages)
        ]
        return ParseResult(observations=observations)

    def _parse_page(
        self,
        page: GeorgiaPowerProjectPage,
        document: SourceDocument,
        index: int,
    ) -> GeorgiaPowerProjectObservation:
        soup = BeautifulSoup(page.html, "html.parser")
        about = _section_text(_heading(soup, "About the Project"))
        included = _included_text(_heading(soup, "What’s included in the project?"))
        if included is None:
            included = _included_text(_heading(soup, "What's included in the project?"))
        timeline = _timeline(soup)
        timeline_raw = [f"{date} | {milestone}" for date, milestone in timeline]
        construction_starts = [
            item
            for item, (_, milestone) in zip(timeline_raw, timeline, strict=True)
            if "construction" in milestone.casefold()
            and re.search(
                r"\b(begin|began|begins|start|started|starts)\b", milestone, re.I
            )
        ]
        completion = next(
            (
                item
                for item, (_, milestone) in zip(timeline_raw, timeline, strict=True)
                if re.search(r"\bproject (?:completion|complete)\b", milestone, re.I)
            ),
            None,
        )

        name_normalized, name_provenance = normalize_project_name(page.project.name)
        technical_text = " ".join(
            value for value in (page.project.name, about, included) if value
        )
        voltage_raw, voltage_kv, voltage_provenance = extract_voltage(technical_text)
        length_raw, length_miles, length_provenance = extract_lengths(technical_text)
        _, endpoints, endpoint_provenance = extract_candidate_locations(name_normalized)
        project_type = TYPE_MAP.get(
            page.project.project_type, page.project.project_type.casefold().replace(" ", "_")
        )
        project_type_provenance = FieldProvenance(
            origin="normalized",
            source_fields=["project_type_raw"],
            rule_id="georgia_power_published_type_v1",
        )
        location_provenance = FieldProvenance(
            origin="derived_from_source",
            source_fields=["county_region_raw"],
            rule_id="georgia_power_county_region_v1",
            notes="Published county/region text only; no geocoding applied.",
        )
        provenance: dict[str, FieldProvenance] = {
            "balancing_authority_normalized": FieldProvenance(
                origin="deterministic_rule",
                source_fields=["source"],
                rule_id="georgia_power_utility_v1",
            ),
            "project_name_normalized": name_provenance,
            "project_type": project_type_provenance,
            "location_mentions": location_provenance,
        }
        if endpoints and endpoint_provenance is not None:
            provenance["endpoint_candidates"] = endpoint_provenance
        if voltage_provenance is not None:
            provenance["voltage_kv"] = voltage_provenance
        if length_provenance is not None:
            provenance["length_miles"] = length_provenance

        raw_parts = [
            f"Project Name: {page.project.name}",
            f"County/Region: {page.project.county_region}",
            f"Type: {page.project.project_type}",
        ]
        if about:
            raw_parts.append(f"About the Project: {about}")
        if included:
            raw_parts.append(f"What's Included: {included}")
        raw_parts.extend(f"Timeline: {item}" for item in timeline_raw)
        raw_record = "\n".join(raw_parts)
        stable_facts = "\x1f".join((page.project.url, raw_record))
        observation_id = (
            "georgia-power-2026-"
            f"{hashlib.sha256(stable_facts.encode()).hexdigest()[:20]}"
        )
        return GeorgiaPowerProjectObservation(
            observation_id=observation_id,
            source="georgia_power",
            planning_year=2026,
            document_id=document.document_id,
            balancing_authority_raw="GPC",
            balancing_authority_normalized="GPC",
            project_name_raw=page.project.name,
            project_name_normalized=name_normalized,
            raw_record_text=raw_record,
            in_service_year_raw=completion.split(" | ", 1)[0] if completion else None,
            description_raw=about,
            supporting_statement_raw=included,
            voltage_raw=voltage_raw,
            voltage_kv=voltage_kv,
            project_type=project_type,
            project_type_confidence=ConfidenceLevel.HIGH,
            project_type_method="georgia_power_published_type_v1",
            location_mentions=[page.project.county_region],
            endpoint_candidates=endpoints,
            length_raw=length_raw,
            length_miles=length_miles,
            pdf_page_start=index,
            pdf_page_end=index,
            source_url=page.project.url,
            source_title=page.project.name,
            source_sha256=page.sha256,
            extraction_engine="BeautifulSoup",
            extraction_engine_version=bs4.__version__,
            parser_version=PARSER_VERSION,
            pipeline_version=__version__,
            extraction_confidence=ConfidenceLevel.HIGH,
            validation_status=ValidationStatus.VALID,
            field_provenance=provenance,
            utility="GPC",
            county_region_raw=page.project.county_region,
            project_type_raw=page.project.project_type,
            timeline_raw=timeline_raw,
            construction_start_raw=construction_starts,
            completion_target_raw=completion,
        )
