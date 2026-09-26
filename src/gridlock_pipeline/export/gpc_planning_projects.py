"""Curated, public Georgia Power planning records from the final 2025 SERTP plan."""

import csv
import hashlib
import json
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from gridlock_pipeline.models import ProjectObservation

SERTP_2025_URL = (
    "https://www.southeasternrtp.com/docs/general/2025/"
    "2025%20Regional%20Transmission%20Plan%20and%20Input%20Assumptions.pdf"
)
SERTP_2025_TITLE = "2025 Regional Transmission Plan and Input Assumptions"
CURRENT_PAGE_SCOPE = "Georgia Power current transmission projects page"
PLANNING_SCOPE = "SERTP 2025 Regional Transmission Plan"


def _planning_record(
    *,
    slug: str,
    name: str,
    project_type: str,
    voltage_kv: list[float],
    endpoints: list[str],
    region: str,
    year: int,
    pages: str,
    description: str,
    source_owner_label: str,
    length_miles: list[float] | None = None,
) -> dict[str, Any]:
    owner_note = (
        "The final SERTP table labels this legacy Savannah-area record SAV; SAV is mapped to "
        "Georgia Power for utility attribution while the published owner label is retained."
        if source_owner_label == "SAV"
        else "The public planning source explicitly attributes this component to GPC."
    )
    page_start = int(pages.split("–", 1)[0])
    status_verification_needed = year == 2026
    return {
        "observation_id": f"gpc-sertp-2025-{slug}",
        "utility": "GPC",
        "source": "sertp",
        "planning_year": 2025,
        "plan_year": 2025,
        "document_id": "sertp-2025-final-regional-transmission-plan",
        "balancing_authority_raw": "SOUTHERN",
        "balancing_authority_normalized": "SOUTHERN",
        "owner_prefix_raw": None,
        "source_owner_label": source_owner_label,
        "ownership_provenance_note": owner_note,
        "utility_attribution_confidence": "HIGH",
        "project_name_raw": name,
        "project_name_normalized": name,
        "source_project_name": name,
        "project_type": project_type,
        "project_type_raw": project_type.replace("_", " ").title(),
        "description_raw": description,
        "supporting_statement_raw": None,
        "raw_record_text": (
            f"Project: {name}\nOwner: {source_owner_label}\nIn-Service Year: {year}\n"
            f"Description: {description}"
        ),
        "voltage_raw": [f"{value:g} kV" for value in voltage_kv],
        "voltage_kv": voltage_kv,
        "endpoint_candidates": endpoints,
        "location_mentions": [region],
        "county_region_raw": region,
        "length_raw": [f"{value:g} miles" for value in (length_miles or [])],
        "length_miles": length_miles or [],
        "in_service_year_raw": str(year),
        "in_service_year": year,
        "planned_in_service_year": year,
        "planned_in_service_date_raw": str(year),
        "project_status_raw": "Planned",
        "status": "planned",
        "status_as_of_source": "Final 2025 SERTP regional plan",
        "status_verification_needed": status_verification_needed,
        "source_scope": PLANNING_SCOPE,
        "source_url": SERTP_2025_URL,
        "source_title": SERTP_2025_TITLE,
        "source_page": pages,
        "pdf_page_start": page_start,
        "pdf_page_end": int(pages.split("–", 1)[-1]),
        "printed_page_start": None,
        "printed_page_end": None,
        "confidence": "HIGH",
        "data_confidence": "HIGH",
        "extraction_confidence": "HIGH",
        "validation_status": "valid",
        "validation_notes": [],
        "warning_codes": [],
        "field_provenance": {
            "utility": {
                "origin": "deterministic_rule",
                "source_fields": ["source_owner_label"],
                "rule_id": "gpc_sav_owner_mapping_v1",
                "notes": owner_note,
            },
            "planned_in_service_year": {
                "origin": "derived_from_source",
                "source_fields": ["in_service_year_raw"],
                "rule_id": "sertp_final_plan_timing_v1",
                "notes": "Final 2025 SERTP timing supersedes older Georgia ITS timing.",
            },
        },
        "geometry": None,
        "latitude": None,
        "longitude": None,
        "parser_version": "gpc_sertp_2025_curated_v1",
        "pipeline_version": "0.1.0",
    }


PLANNING_RECORDS = (
    _planning_record(
        slug="big-ogeechee-new-substation",
        name="Big Ogeechee New Substation",
        project_type="area_project",
        voltage_kv=[500.0, 230.0],
        endpoints=["Big Ogeechee", "Little Ogeechee"],
        region="Savannah / Chatham County",
        year=2026,
        pages="74",
        description=(
            "Build a new 500/230 kV substation near Little Ogeechee, loop nearby 500 kV and "
            "230 kV facilities, and add 230 kV connections to Little Ogeechee."
        ),
        source_owner_label="SAV",
    ),
    _planning_record(
        slug="boulevard-deptford-reconductor",
        name="Boulevard–Deptford Reconductor",
        project_type="transmission_line_upgrade",
        voltage_kv=[115.0],
        endpoints=["Boulevard", "Deptford"],
        region="Savannah / Chatham County",
        year=2026,
        pages="74–75",
        description=(
            "Reconductor approximately 8 miles of the Boulevard–Deptford 115 kV line and "
            "complete associated Bolton bus and jumper work."
        ),
        source_owner_label="SAV",
        length_miles=[8.0],
    ),
    _planning_record(
        slug="goshen-kraft-first-segment",
        name="Goshen (Savannah)–Kraft Rebuild, First Segment",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Goshen (Savannah)", "Kraft"],
        region="Savannah / Effingham County",
        year=2027,
        pages="92",
        description="Rebuild the first approximately 3.48-mile segment of the 115 kV line.",
        source_owner_label="SAV",
        length_miles=[3.48],
    ),
    _planning_record(
        slug="coleman-dean-forest-rebuild",
        name="Coleman–Dean Forest Rebuild",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Coleman", "Dean Forest"],
        region="Savannah / Chatham County",
        year=2028,
        pages="109–110",
        description=(
            "Rebuild approximately 6.7 miles of Coleman–Dean Forest and approximately 1.7 "
            "miles of common-structure Coleman–Meldrim facilities."
        ),
        source_owner_label="SAV",
        length_miles=[6.7, 1.7],
    ),
    _planning_record(
        slug="goshen-mcintosh-rebuild",
        name="Goshen (Savannah)–McIntosh Rebuild",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Goshen (Savannah)", "Georgia Pacific (Rincon)"],
        region="Effingham County / Rincon",
        year=2028,
        pages="110",
        description=(
            "Rebuild approximately 6.7 miles of the Goshen–Georgia Pacific (Rincon) section."
        ),
        source_owner_label="SAV",
        length_miles=[6.7],
    ),
    _planning_record(
        slug="rice-hope-autotransformer",
        name="Rice Hope Autotransformer",
        project_type="substation_upgrade",
        voltage_kv=[230.0, 115.0],
        endpoints=["Rice Hope", "Crossgate", "McIntosh"],
        region="Savannah / Chatham–Effingham counties",
        year=2028,
        pages="110",
        description=(
            "Install a new 230/115 kV autotransformer at Rice Hope and loop the "
            "Crossgate–McIntosh 230 kV line."
        ),
        source_owner_label="SAV",
    ),
    _planning_record(
        slug="boulevard-magnolia-truman-parkway-rebuilds",
        name="Boulevard–Magnolia–Truman Parkway Rebuilds",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Boulevard", "Magnolia", "Truman Parkway"],
        region="Savannah / Chatham County",
        year=2029,
        pages="129–130",
        description=(
            "Rebuild approximately 3 miles of Magnolia–Truman Parkway and 4.56 miles of "
            "Boulevard–Magnolia 115 kV facilities."
        ),
        source_owner_label="SAV",
        length_miles=[3.0, 4.56],
    ),
    _planning_record(
        slug="coleman-meldrim-rebuild",
        name="Coleman–Meldrim Rebuild",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Four Lakes", "Structure 76A", "Quacco Road"],
        region="Savannah / Bryan–Chatham county fringe",
        year=2029,
        pages="130",
        description=(
            "Rebuild approximately 8.1 miles from Four Lakes to Structure 76A and upgrade "
            "Quacco Road switching facilities."
        ),
        source_owner_label="SAV",
        length_miles=[8.1],
    ),
    _planning_record(
        slug="dean-forest-little-ogeechee-rebuild",
        name="Dean Forest–Little Ogeechee Rebuild",
        project_type="transmission_line_rebuild",
        voltage_kv=[230.0],
        endpoints=["Little Ogeechee", "Salt Creek", "Dean Forest"],
        region="Savannah / Chatham County",
        year=2029,
        pages="130",
        description=(
            "Rebuild approximately 8 miles of the Little Ogeechee–Salt Creek–Dean Forest "
            "230 kV facilities."
        ),
        source_owner_label="SAV",
        length_miles=[8.0],
    ),
    _planning_record(
        slug="little-ogeechee-autotransformer-replacement",
        name="Little Ogeechee Autotransformer Replacement",
        project_type="transformer_replacement",
        voltage_kv=[230.0, 115.0],
        endpoints=["Little Ogeechee"],
        region="Savannah / Chatham County",
        year=2029,
        pages="130–131",
        description="Replace the 230/115 kV SATX autotransformer at Little Ogeechee.",
        source_owner_label="SAV",
    ),
    _planning_record(
        slug="goshen-kraft-rice-hope-segment",
        name="Goshen (Savannah)–Kraft Rebuild, Rice Hope Segment",
        project_type="transmission_line_rebuild",
        voltage_kv=[115.0],
        endpoints=["Goshen (Savannah)", "Rice Hope"],
        region="Savannah / Effingham County",
        year=2031,
        pages="156–157",
        description="Rebuild approximately 3.04 miles of Goshen–Rice Hope 115 kV facilities.",
        source_owner_label="SAV",
        length_miles=[3.04],
    ),
    _planning_record(
        slug="meldrim-bank-d-replacement",
        name="Meldrim Bank D Replacement",
        project_type="transformer_replacement",
        voltage_kv=[230.0, 115.0],
        endpoints=["Meldrim"],
        region="Savannah / Bryan–Chatham county fringe",
        year=2033,
        pages="162",
        description="Replace the Meldrim Bank D 230/115 kV autotransformer.",
        source_owner_label="SAV",
    ),
    _planning_record(
        slug="goldens-creek-warrenton-primary-rebuild",
        name="Goldens Creek–Warrenton Primary Rebuild",
        project_type="transmission_line_rebuild",
        voltage_kv=[230.0],
        endpoints=["Goldens Creek", "Warrenton Primary"],
        region="Thomson / McDuffie–Warren counties",
        year=2030,
        pages="140–141",
        description="Rebuild approximately 0.34 miles of 230 kV transmission facilities.",
        source_owner_label="GPC",
        length_miles=[0.34],
    ),
    _planning_record(
        slug="goshen-area-gpc-switching-station",
        name="Goshen Area Strategic Solution — GPC Switching-Station Component",
        project_type="switching_station",
        voltage_kv=[230.0],
        endpoints=["Waynesboro", "Wilson"],
        region="Augusta / Richmond County–Vogtle area",
        year=2030,
        pages="149",
        description=(
            "Construct the GPC switching station on the Waynesboro–Wilson 230 kV line. This "
            "record intentionally excludes MEAG's separate 12.3-mile transmission line."
        ),
        source_owner_label="GPC",
    ),
)


def _normalize(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def _timing(record: dict[str, Any]) -> tuple[int, ...]:
    explicit = record.get("planned_in_service_year") or record.get("in_service_year")
    if isinstance(explicit, int):
        return (explicit,)
    text = " ".join(
        str(value)
        for value in (
            record.get("in_service_year_raw"),
            record.get("completion_target_raw"),
            record.get("timeline_raw"),
        )
    )
    return tuple(sorted({int(value) for value in re.findall(r"\b20\d{2}\b", text)}))


def deduplication_key(record: dict[str, Any]) -> tuple[Any, ...]:
    """Conservative five-field key required for deterministic GPC deduplication."""
    return (
        _normalize(record.get("project_name_normalized") or record.get("project_name_raw")),
        tuple(sorted(_normalize(value) for value in record.get("endpoint_candidates", []))),
        tuple(sorted(float(value) for value in record.get("voltage_kv", []))),
        _normalize(record.get("county_region_raw") or record.get("location_mentions")),
        _timing(record),
    )


def _annotate_current_record(record: dict[str, Any]) -> dict[str, Any]:
    result = dict(record)
    result.update(
        {
            "source_scope": CURRENT_PAGE_SCOPE,
            "source_project_name": record.get("project_name_raw"),
            "source_owner_label": "GPC",
            "ownership_provenance_note": (
                "Published directly on Georgia Power's current transmission projects page."
            ),
            "utility_attribution_confidence": "HIGH",
            "data_confidence": record.get("confidence", "HIGH"),
            "status": "current",
            "status_as_of_source": "Georgia Power current-project page acquisition",
            "status_verification_needed": False,
        }
    )
    return result


def merge_gpc_records(
    current_records: Iterable[dict[str, Any]],
    planning_records: Iterable[dict[str, Any]] = PLANNING_RECORDS,
) -> list[dict[str, Any]]:
    """Merge current and planning records, rejecting deterministic five-field duplicates."""
    current = [_annotate_current_record(record) for record in current_records]
    planning = [dict(record) for record in planning_records]
    records = current + planning
    seen: dict[tuple[Any, ...], str] = {}
    for record in records:
        key = deduplication_key(record)
        if key in seen:
            raise ValueError(
                f"duplicate GPC project {record['observation_id']} matches {seen[key]}"
            )
        seen[key] = record["observation_id"]
    ids = [record["observation_id"] for record in records]
    if len(ids) != len(set(ids)):
        raise ValueError("GPC observation_id values must be unique")
    return sorted(
        records,
        key=lambda record: (
            str(record.get("project_name_normalized") or record["project_name_raw"]).casefold(),
            record["observation_id"],
        ),
    )


def _csv_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_gpc_records(
    current_observations: Sequence[ProjectObservation] | Iterable[dict[str, Any]],
    json_path: Path,
    csv_path: Path,
) -> list[dict[str, Any]]:
    current = [
        item.model_dump(mode="json") if isinstance(item, ProjectObservation) else dict(item)
        for item in current_observations
    ]
    records = merge_gpc_records(current)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fieldnames = sorted({field for record in records for field in record})
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({field: _csv_value(record.get(field)) for field in fieldnames})
    return records


def planning_payload_sha256() -> str:
    """Stable digest used by tests and release notes to detect curated-data drift."""
    payload = json.dumps(PLANNING_RECORDS, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode()).hexdigest()


def main() -> None:
    processed = Path("data/processed")
    input_path = processed / "georgia_power_current_projects.json"
    existing = json.loads(input_path.read_text(encoding="utf-8"))
    current = [record for record in existing if record.get("source_scope") != PLANNING_SCOPE]
    write_gpc_records(
        current,
        input_path,
        processed / "georgia_power_current_projects.csv",
    )


if __name__ == "__main__":
    main()
