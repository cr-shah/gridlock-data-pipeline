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
    "source_scope",
    "source_project_name",
    "source_owner_label",
    "status_as_of_source",
    "status_verification_needed",
    "utility_attribution_confidence",
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

    assert len(projects) == 78
    assert Counter(project["utility"] for project in projects) == {"DESC": 54, "GPC": 24}
    assert len({project["id"] for project in projects}) == 78
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
        and project["source_scope"] == "Georgia Power current transmission projects page"
    )
    planning = [
        project
        for project in projects
        if project["source_scope"] == "SERTP 2025 Regional Transmission Plan"
    ]
    assert len(planning) == 14
    assert all(project["source_page"] for project in planning)
    assert all(project["in_service_year"] == project["planned_end_year"] for project in planning)
    assert all(
        project["status_verification_needed"] == (project["in_service_year"] == 2026)
        for project in planning
    )


def test_gis_evidence_is_small_explicit_valid_and_conservative(tmp_path: Path) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    by_id = {project["id"]: project for project in projects}

    assert 1 <= len(module.GIS_EVIDENCE) <= 20
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
        assert project["geometry_confidence"] in {"HIGH", "MEDIUM", "ESTIMATED"}
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


OFFICIAL_GPC_ROUTES = [
        (
            "georgia-power-2026-f86ec735e2182af8b86e",
            "ashley-park",
            [-84.48891181, 33.51429517],
            [-85.03056406, 33.41102843],
            94,
        ),
        (
            "georgia-power-2026-31e73b6a22013b33f193",
            "big-tazewell-farley",
            [-85.11344023, 31.23258365],
            [-84.48428053, 32.36332714],
            68,
        ),
        (
            "georgia-power-2026-85c6d93852f8eda4b276",
            "conyers-klondike",
            [-84.04183998, 33.69766832],
            [-84.12597549, 33.63814738],
            116,
        ),
        (
            "georgia-power-2026-f4697ce681309cdee657",
            "decatur-scottdale",
            [-84.27152587, 33.7912509],
            [-84.29155805, 33.77069199],
            41,
        ),
        (
            "georgia-power-2026-aecc11f48e0f464e8c99",
            "grassy-hollow-great-valley",
            [-84.80266586, 34.28387466],
            [-84.67523952, 34.24458222],
            64,
        ),
]


@pytest.mark.parametrize(("project_id", "slug", "first", "last", "vertices"), OFFICIAL_GPC_ROUTES)
def test_official_gpc_route_geometry(
    tmp_path: Path, project_id: str, slug: str, first: list, last: list, vertices: int
) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    project = {item["id"]: item for item in projects}[project_id]
    official_url = (
        "https://www.georgiapower.com/about/grid-reliability/grid-improvements/"
        f"grid-projects/transmission-projects/{slug}.html"
    )

    assert project["utility"] == "GPC"
    assert project["source_url"] == official_url
    assert project["geometry_source"] == official_url
    assert project["geometry_type"] == "LineString"
    assert project["geometry_method"] == "official_project_route_coordinates"
    assert project["geometry_confidence"] == "HIGH"
    assert len(project["geometry"]) == vertices
    assert project["geometry"][0] == first
    assert project["geometry"][-1] == last
    for longitude, latitude in project["geometry"]:
        assert -86.0 <= longitude <= -80.0
        assert 30.0 <= latitude <= 35.5
    assert project_id not in {item["id"] for item in review_queue}


def test_multi_route_and_mapless_gpc_projects_stay_null(tmp_path: Path) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    by_id = {project["id"]: project for project in projects}
    reasons = {item["id"]: item["review_reason"] for item in review_queue}
    for project_id in (
        "georgia-power-2026-83a79bb18ac6d7434a20",
        "georgia-power-2026-a84d843ee3a3cc43ff5f",
        "georgia-power-2026-c78a361d12a5667dd3a1",
    ):
        assert by_id[project_id]["geometry"] is None
        assert project_id in reasons
    assert "map is not currently" in reasons["georgia-power-2026-83a79bb18ac6d7434a20"]


HIFLD_CORRIDOR_PROJECTS = [
    # id, geometry type, first coordinate, vertex count (LineString) or None (Point)
    (
        "gpc-sertp-2025-dean-forest-little-ogeechee-rebuild",
        "LineString",
        [-81.252833, 32.007156],
        63,
    ),
    (
        "gpc-sertp-2025-boulevard-magnolia-truman-parkway-rebuilds",
        "LineString",
        [-81.086164, 32.022696],
        103,
    ),
    (
        "gpc-sertp-2025-little-ogeechee-autotransformer-replacement",
        "Point",
        [-81.252833, 32.007156],
        None,
    ),
    (
        "gpc-sertp-2025-meldrim-bank-d-replacement",
        "Point",
        [-81.367813, 32.155394],
        None,
    ),
]


@pytest.mark.parametrize(("project_id", "kind", "first", "vertices"), HIFLD_CORRIDOR_PROJECTS)
def test_hifld_existing_corridor_geometry_is_labelled_medium(
    tmp_path: Path, project_id: str, kind: str, first: list, vertices: int | None
) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    project = {item["id"]: item for item in projects}[project_id]

    assert project["geometry_type"] == kind
    assert project["geometry_confidence"] == "MEDIUM"
    assert project["geometry_source"].startswith("https://services1.arcgis.com/")
    assert "HIFLD" in project["geometry_notes"]
    expected_method = (
        "existing_corridor_hifld" if kind == "LineString" else "public_facility_endpoint_point"
    )
    assert project["geometry_method"] == expected_method
    if kind == "LineString":
        assert project["geometry"][0] == first
        assert len(project["geometry"]) == vertices
    else:
        assert project["geometry"] == first
    assert project_id not in {item["id"] for item in review_queue}


def test_unverifiable_savannah_and_augusta_endpoints_stay_null(tmp_path: Path) -> None:
    module = _product_export_module()
    projects, review_queue = module.write_product_exports(
        PROCESSED / "gridlock_verified_projects.json",
        tmp_path / "projects.json",
        tmp_path / "queue.json",
    )
    by_id = {project["id"]: project for project in projects}
    reasons = {item["id"]: item["review_reason"] for item in review_queue}
    for project_id in (
        "gpc-sertp-2025-big-ogeechee-new-substation",
        "gpc-sertp-2025-boulevard-deptford-reconductor",
        "gpc-sertp-2025-coleman-dean-forest-rebuild",
        "gpc-sertp-2025-goshen-kraft-first-segment",
        "gpc-sertp-2025-goshen-area-gpc-switching-station",
    ):
        assert by_id[project_id]["geometry"] is None
        assert project_id in reasons
