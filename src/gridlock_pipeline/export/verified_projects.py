"""Build the challenge-ready DESC and GPC project export."""

import csv
import json
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ALLOWED_UTILITIES = frozenset({"DESC", "GPC"})
PRIMARY_CSV_FIELDS = (
    "observation_id",
    "utility",
    "project_name_raw",
    "project_name_normalized",
    "project_type",
    "description_raw",
    "voltage_raw",
    "voltage_kv",
    "project_status_raw",
    "planned_in_service_date_raw",
    "in_service_year_raw",
    "in_service_year",
    "timeline_raw",
    "estimated_cost_raw",
    "estimated_cost_usd",
    "endpoint_candidates",
    "location_mentions",
    "source_url",
    "source_title",
    "pdf_page_start",
    "pdf_page_end",
    "confidence",
    "geometry",
    "latitude",
    "longitude",
)


def _sort_key(record: dict[str, Any]) -> tuple[str, str, str]:
    project_name = record.get("project_name_normalized") or record.get("project_name_raw") or ""
    return (
        str(record.get("utility", "")).casefold(),
        str(project_name).casefold(),
        str(record.get("observation_id", "")),
    )


def combine_verified_projects(
    record_groups: Iterable[Iterable[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Validate and sort source records without adding, dropping, or changing fields."""
    records = [record for group in record_groups for record in group]
    utilities = {record.get("utility") for record in records}
    if utilities != ALLOWED_UTILITIES:
        raise ValueError(f"expected exactly DESC and GPC utilities; found {sorted(utilities)}")

    ids = [record.get("observation_id") for record in records]
    if any(not isinstance(observation_id, str) or not observation_id for observation_id in ids):
        raise ValueError("every record must have a non-empty observation_id")
    if len(ids) != len(set(ids)):
        raise ValueError("observation_id values must be unique")

    return sorted(records, key=_sort_key)


def _csv_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def write_verified_projects(
    desc_path: Path,
    gpc_path: Path,
    json_path: Path,
    csv_path: Path,
) -> list[dict[str, Any]]:
    inputs = [json.loads(path.read_text(encoding="utf-8")) for path in (desc_path, gpc_path)]
    if any(not isinstance(records, list) for records in inputs):
        raise ValueError("each input must be a JSON array")

    records = combine_verified_projects(inputs)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    available_fields = {field for record in records for field in record}
    fieldnames = [field for field in PRIMARY_CSV_FIELDS if field in available_fields]
    fieldnames.extend(sorted(available_fields - set(fieldnames)))
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for record in records:
            writer.writerow({field: _csv_value(record.get(field)) for field in fieldnames})

    return records


def main() -> None:
    processed = Path("data/processed")
    write_verified_projects(
        processed / "desc_current_projects.json",
        processed / "georgia_power_current_projects.json",
        processed / "gridlock_verified_projects.json",
        processed / "gridlock_verified_projects.csv",
    )


if __name__ == "__main__":
    main()
