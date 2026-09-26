import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

from gridlock_pipeline.export.gpc_planning_projects import (
    CURRENT_PAGE_SCOPE,
    PLANNING_RECORDS,
    PLANNING_SCOPE,
    deduplication_key,
    merge_gpc_records,
    planning_payload_sha256,
    write_gpc_records,
)

PROCESSED = Path("data/processed")


def _current_records() -> list[dict]:
    records = json.loads(
        (PROCESSED / "georgia_power_current_projects.json").read_text(encoding="utf-8")
    )
    return [record for record in records if record.get("source_scope") == CURRENT_PAGE_SCOPE]


def test_curated_inventory_maps_sav_to_gpc_and_preserves_owner_provenance() -> None:
    assert len(PLANNING_RECORDS) == 14
    assert Counter(record["source_owner_label"] for record in PLANNING_RECORDS) == {
        "SAV": 12,
        "GPC": 2,
    }
    assert all(record["utility"] == "GPC" for record in PLANNING_RECORDS)
    sav = [record for record in PLANNING_RECORDS if record["source_owner_label"] == "SAV"]
    assert all("SAV" in record["ownership_provenance_note"] for record in sav)
    assert all(record["utility_attribution_confidence"] == "HIGH" for record in sav)


def test_goshen_area_contains_only_explicit_gpc_station_scope() -> None:
    goshen = next(
        record
        for record in PLANNING_RECORDS
        if record["observation_id"] == "gpc-sertp-2025-goshen-area-gpc-switching-station"
    )
    assert goshen["source_owner_label"] == "GPC"
    assert goshen["project_type"] == "switching_station"
    assert goshen["length_miles"] == []
    assert all(record["source_owner_label"] != "MEAG" for record in PLANNING_RECORDS)
    assert all(12.3 not in record["length_miles"] for record in PLANNING_RECORDS)


def test_merge_deduplicates_on_required_five_field_key() -> None:
    duplicate = deepcopy(PLANNING_RECORDS[0])
    duplicate["observation_id"] = "duplicate-id"
    assert deduplication_key(duplicate) == deduplication_key(PLANNING_RECORDS[0])
    with pytest.raises(ValueError, match="duplicate GPC project"):
        merge_gpc_records([], [PLANNING_RECORDS[0], duplicate])

    current = _current_records()[0]
    duplicate_current = deepcopy(current)
    duplicate_current["observation_id"] = "duplicate-current-id"
    with pytest.raises(ValueError, match="duplicate GPC project"):
        merge_gpc_records([current], [duplicate_current])


def test_source_provenance_and_2026_status_verification_flag() -> None:
    assert all(record["source_scope"] == PLANNING_SCOPE for record in PLANNING_RECORDS)
    assert all(
        record["source_url"].endswith("Input%20Assumptions.pdf")
        for record in PLANNING_RECORDS
    )
    assert all(record["source_page"] for record in PLANNING_RECORDS)
    assert all(record["plan_year"] == 2025 for record in PLANNING_RECORDS)
    records_2026 = [record for record in PLANNING_RECORDS if record["in_service_year"] == 2026]
    assert len(records_2026) == 2
    assert all(record["status"] == "planned" for record in records_2026)
    assert all(record["status_verification_needed"] is True for record in records_2026)
    assert all(
        record["status_verification_needed"] is False
        for record in PLANNING_RECORDS
        if record["in_service_year"] != 2026
    )


def test_gpc_output_is_deterministic_and_keeps_current_inventory(tmp_path: Path) -> None:
    current = _current_records()
    first_json, first_csv = tmp_path / "first.json", tmp_path / "first.csv"
    second_json, second_csv = tmp_path / "second.json", tmp_path / "second.csv"
    records = write_gpc_records(current, first_json, first_csv)
    write_gpc_records(reversed(current), second_json, second_csv)

    assert Counter(record["source_scope"] for record in records) == {
        CURRENT_PAGE_SCOPE: 10,
        PLANNING_SCOPE: 14,
    }
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_csv.read_bytes() == second_csv.read_bytes()
    assert len(planning_payload_sha256()) == 64


def test_existing_gis_geometry_evidence_is_preserved() -> None:
    products = json.loads(
        (PROCESSED / "gridlock_product_projects.json").read_text(encoding="utf-8")
    )
    by_id = {record["id"]: record for record in products}
    expected = {
        "georgia-power-2026-4a60199d0029a784348e": "LineString",
        "georgia-power-2026-57d55e09e3bd5e9f6cb2": "LineString",
        "scrtp-desc-2026-99cdb225cd296159f73c": "Point",
    }
    assert {project_id: by_id[project_id]["geometry_type"] for project_id in expected} == expected
    assert all(
        by_id[record["observation_id"]]["geometry"] is None for record in PLANNING_RECORDS
    )


def test_reference_only_and_excluded_projects_are_not_in_production() -> None:
    names = {
        record["project_name_raw"]
        for record in json.loads(
            (PROCESSED / "georgia_power_current_projects.json").read_text(encoding="utf-8")
        )
    }
    assert "Goldens Creek–Thomson Primary Rebuild" not in names
    assert "Evans Primary–Thurmond Dam #5 Rebuild" not in names
    assert "Evans Primary–Thomson Primary Rebuild" not in names
    assert "Calvert–West McIntosh Reconductor" not in names
    assert "Thomson–Vogtle" not in names
