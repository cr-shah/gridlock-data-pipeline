import csv
import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from gridlock_pipeline.export.master_projects import build_master_payload, write_machine_exports

ROOT = Path(__file__).resolve().parents[1]


def source_data():
    projects = json.loads(
        (ROOT / "data/processed/gridlock_product_projects.json").read_text(encoding="utf-8")
    )
    estimates = json.loads(
        (ROOT / "data/curated/estimated_geometry.json").read_text(encoding="utf-8")
    )
    return projects, estimates


def test_repository_master_has_one_record_per_real_project() -> None:
    projects, estimates = source_data()
    payload = build_master_payload(
        projects,
        estimates,
        pipeline_commit="test-commit",
        generated_at="2026-09-26T00:00:00+00:00",
    )
    ids = [item["project_id"] for item in payload["projects"]]
    assert len(ids) == len(set(ids)) == 78
    assert payload["DESC_count"] == 54
    assert payload["GPC_count"] == 24
    assert payload["verified_geometry_count"] == 15
    assert payload["estimated_geometry_count"] == 44
    assert payload["unresolved_count"] == 19


def test_verified_geometry_takes_precedence() -> None:
    projects = [
        {
            "id": "p1",
            "utility": "DESC",
            "name": "One",
            "voltage_kv": [],
            "geometry": [-81.0, 32.0],
            "geometry_type": "Point",
            "geometry_method": "official",
            "geometry_confidence": "HIGH",
        }
    ]
    estimates = {
        "estimates": [
            {
                "project_id": "p1",
                "geometry": [-82.0, 33.0],
                "geometry_type": "Point",
                "geometry_method": "estimate",
                "geometry_confidence": "ESTIMATED",
            }
        ]
    }
    payload = build_master_payload(
        projects, estimates, pipeline_commit="test", generated_at="fixed"
    )
    project = payload["projects"][0]
    assert project["geometry_status"] == "VERIFIED"
    assert project["analysis_geometry"] == project["verified_geometry"]
    assert project["analysis_geometry"] != project["estimated_geometry"]
    assert project["geometry_method"] == "official"


def test_duplicate_projects_and_estimates_fail() -> None:
    project = {"id": "same", "utility": "DESC", "name": "Same", "voltage_kv": []}
    with pytest.raises(ValueError, match="duplicate project"):
        build_master_payload(
            [project, project], {}, pipeline_commit="test", generated_at="fixed"
        )
    with pytest.raises(ValueError, match="duplicate estimate"):
        build_master_payload(
            [project],
            {"estimates": [{"project_id": "same"}, {"project_id": "same"}]},
            pipeline_commit="test",
            generated_at="fixed",
        )


def test_machine_exports_keep_ids_names_years_and_counts_consistent(tmp_path: Path) -> None:
    projects, estimates = source_data()
    payload = build_master_payload(
        projects,
        estimates,
        pipeline_commit="test-commit",
        generated_at="2026-09-26T00:00:00+00:00",
    )
    output = tmp_path / "data/published/gridlock_master_projects.json"
    output.parent.mkdir(parents=True)
    output.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    paths = write_machine_exports(output, payload)

    ndjson = [json.loads(line) for line in paths["ndjson"].read_text().splitlines()]
    with paths["csv"].open(encoding="utf-8", newline="") as handle:
        csv_rows = list(csv.DictReader(handle))

    expected = {
        project["project_id"]: (
            project["project_name"],
            project["planned_start_year"],
            project["planned_end_year"],
            project["in_service_year"],
        )
        for project in payload["projects"]
    }
    from_ndjson = {
        project["project_id"]: (
            project["project_name"],
            project["planned_start_year"],
            project["planned_end_year"],
            project["in_service_year"],
        )
        for project in ndjson
    }
    from_csv = {
        project["project_id"]: (
            project["project_name"],
            int(project["planned_start_year"]) if project["planned_start_year"] else None,
            int(project["planned_end_year"]) if project["planned_end_year"] else None,
            int(project["in_service_year"]) if project["in_service_year"] else None,
        )
        for project in csv_rows
    }
    assert expected == from_ndjson == from_csv
    assert len(expected) == 78

    manifest = json.loads(paths["manifest"].read_text())
    assert manifest["total_projects"] == 78
    for name, artifact in manifest["artifacts"].items():
        artifact_path = output.parent / name
        assert hashlib.sha256(artifact_path.read_bytes()).hexdigest() == artifact["sha256"]


def test_master_matches_published_json_schema() -> None:
    projects, estimates = source_data()
    payload = build_master_payload(
        projects,
        estimates,
        pipeline_commit="test-commit",
        generated_at="2026-09-26T00:00:00+00:00",
    )
    schema = json.loads(
        (ROOT / "schemas/gridlock_master_projects.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(payload)
