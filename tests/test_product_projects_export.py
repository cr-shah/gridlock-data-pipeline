import importlib
import json
from collections import Counter
from copy import deepcopy
from pathlib import Path

import pytest

PROCESSED = Path("data/processed")
REQUIRED_FIELDS = {
    "id",
    "utility",
    "name",
    "project_type",
    "planned_start_year",
    "planned_end_year",
    "in_service_year",
    "voltage_kv",
    "geometry",
    "geometry_type",
    "source_url",
    "source_page",
    "data_confidence",
    "geometry_source",
    "geometry_method",
    "geometry_confidence",
    "geometry_notes",
}


def _product_export_module():
    try:
        return importlib.import_module("gridlock_pipeline.export.product_projects")
    except ModuleNotFoundError:
        pytest.fail("product-project export module has not been implemented")


def test_product_export_has_required_inventory_schema_and_schedule_semantics(
    tmp_path: Path,
) -> None:
    module = _product_export_module()
    output_path = tmp_path / "projects.json"
    queue_path = tmp_path / "queue.json"

    projects, _ = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        output_path,
        queue_path,
    )

    assert len(projects) == 64
    assert Counter(project["utility"] for project in projects) == {"DESC": 54, "GPC": 10}
    assert len({project["id"] for project in projects}) == 64
    assert all(REQUIRED_FIELDS <= project.keys() for project in projects)

    desc = [project for project in projects if project["utility"] == "DESC"]
    assert all(project["planned_start_year"] is None for project in desc)
    assert all(project["planned_end_year"] is None for project in desc)
    verified = json.loads(
        (PROCESSED / "gridlock_verified_projects.json").read_text(encoding="utf-8")
    )
    expected_desc_years = {
        record["observation_id"]: record["in_service_year"]
        for record in verified
        if record["utility"] == "DESC"
    }
    assert {project["id"]: project["in_service_year"] for project in desc} == expected_desc_years

    by_id = {project["id"]: project for project in projects}
    assert by_id["georgia-power-2026-f86ec735e2182af8b86e"]["planned_start_year"] == 2027
    assert by_id["georgia-power-2026-f86ec735e2182af8b86e"]["planned_end_year"] == 2028
    assert by_id["georgia-power-2026-4a60199d0029a784348e"]["planned_start_year"] == 2027
    assert by_id["georgia-power-2026-4a60199d0029a784348e"]["planned_end_year"] is None
    assert by_id["georgia-power-2026-31e73b6a22013b33f193"]["planned_end_year"] == 2028
    assert all(
        project["in_service_year"] is None
        for project in projects
        if project["utility"] == "GPC"
    )


def test_gis_evidence_is_small_explicit_valid_and_conservative(tmp_path: Path) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    by_id = {project["id"]: project for project in projects}

    assert 1 <= len(module.GIS_EVIDENCE) <= 8
    assert set(module.GIS_EVIDENCE) <= set(by_id)
    assert by_id["georgia-power-2026-4a60199d0029a784348e"]["geometry_confidence"] == "HIGH"
    assert (
        by_id["georgia-power-2026-4a60199d0029a784348e"]["geometry_method"]
        == "official_project_route_coordinates"
    )
    assert by_id["georgia-power-2026-83a79bb18ac6d7434a20"]["geometry"] is None
    hatch_wadley = by_id["georgia-power-2026-57d55e09e3bd5e9f6cb2"]
    assert hatch_wadley["geometry_type"] == "LineString"
    assert hatch_wadley["geometry_method"] == "official_project_route_coordinates"
    assert hatch_wadley["geometry_confidence"] == "HIGH"
    assert hatch_wadley["geometry"][0] == [-82.3489551, 31.93446331]
    assert hatch_wadley["geometry"][-1] == [-82.41704969, 32.88427877]
    assert by_id["scrtp-desc-2026-51b7f3df6753d9825f1a"]["geometry"] == [-81.9111, 33.435]
    assert by_id["scrtp-desc-2026-3fcc16fb58dedf958023"]["geometry"] is None

    for project in projects:
        geometry = project["geometry"]
        if geometry is None:
            assert project["geometry_type"] is None
            assert project["geometry_source"] is None
            assert project["geometry_method"] is None
            assert project["geometry_confidence"] is None
            continue

        assert project["geometry_type"] in {"Point", "LineString"}
        assert project["geometry_source"].startswith("https://")
        assert project["geometry_method"]
        assert project["geometry_confidence"] in {"HIGH", "MEDIUM"}
        coordinates = geometry if project["geometry_type"] == "LineString" else [geometry]
        assert len(coordinates) >= (2 if project["geometry_type"] == "LineString" else 1)
        for longitude, latitude in coordinates:
            assert -180 <= longitude <= 180
            assert -90 <= latitude <= 90

    unresolved_ids = {item["id"] for item in review_queue}
    assert unresolved_ids == {project["id"] for project in projects if project["geometry"] is None}
    assert by_id["scrtp-desc-2026-6c4897da52154c18c1d1"]["geometry"] is not None
    assert by_id["scrtp-desc-2026-709d9acc84bd6eb25bd2"]["geometry"] == [-81.9111, 33.435]


def test_product_validation_rejects_swapped_axes(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _product_export_module()
    records = json.loads(
        (PROCESSED / "gridlock_verified_projects.json").read_text(encoding="utf-8")
    )
    evidence = deepcopy(module.GIS_EVIDENCE["scrtp-desc-2026-99cdb225cd296159f73c"])
    evidence["geometry"] = [32.334445, -81.032376]
    monkeypatch.setitem(
        module.GIS_EVIDENCE,
        "scrtp-desc-2026-99cdb225cd296159f73c",
        evidence,
    )

    with pytest.raises(ValueError, match="outside the expected SC/GA project region"):
        module.build_product_projects(records)


def test_product_validation_rejects_schema_field_type_mismatch() -> None:
    module = _product_export_module()
    records = json.loads(
        (PROCESSED / "gridlock_verified_projects.json").read_text(encoding="utf-8")
    )
    records[0]["in_service_year"] = "2027"

    with pytest.raises(ValueError, match="in_service_year"):
        module.build_product_projects(records)


def test_product_and_review_exports_are_deterministic(tmp_path: Path) -> None:
    module = _product_export_module()
    first_product = tmp_path / "first-product.json"
    first_queue = tmp_path / "first-queue.json"
    second_product = tmp_path / "second-product.json"
    second_queue = tmp_path / "second-queue.json"

    module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        first_product,
        first_queue,
    )
    module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        second_product,
        second_queue,
    )

    assert first_product.read_bytes() == second_product.read_bytes()
    assert first_queue.read_bytes() == second_queue.read_bytes()
    assert json.loads(first_product.read_text(encoding="utf-8"))
    assert json.loads(first_queue.read_text(encoding="utf-8"))
