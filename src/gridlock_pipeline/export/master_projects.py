"""Publish the canonical Gridlock project/geometry dataset."""

from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATASET_VERSION = "1.0.0"
GEOMETRY_STATUSES = frozenset({"VERIFIED", "ESTIMATED", "UNRESOLVED"})

SQL_COLUMNS = (
    "dataset_version",
    "pipeline_commit",
    "project_id",
    "utility",
    "project_name",
    "project_type",
    "voltage_json",
    "planned_start_year",
    "planned_end_year",
    "in_service_year",
    "status",
    "geometry_status",
    "geometry_method",
    "geometry_confidence",
    "verified_geometry_json",
    "estimated_geometry_json",
    "analysis_geometry_json",
    "source_metadata_json",
)


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _unique_by(records: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for record in records:
        value = record.get(field)
        if not isinstance(value, str) or not value:
            raise ValueError(f"{label} has a missing {field}")
        if value in indexed:
            raise ValueError(f"duplicate {label} {field}: {value}")
        indexed[value] = record
    return indexed


def _geojson(geometry: Any, geometry_type: str | None) -> dict[str, Any] | None:
    if geometry is None:
        return None
    if isinstance(geometry, dict) and geometry.get("coordinates") is not None:
        return {
            "type": geometry.get("type") or geometry_type,
            "coordinates": geometry["coordinates"],
        }
    if not geometry_type:
        raise ValueError("non-null geometry is missing geometry_type")
    return {"type": geometry_type, "coordinates": geometry}


def _source_metadata(project: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "source_url",
        "source_page",
        "source_scope",
        "source_project_name",
        "source_owner_label",
        "status_as_of_source",
        "status_verification_needed",
        "utility_attribution_confidence",
        "ownership_provenance_note",
        "data_confidence",
        "plan_year",
    )
    return {key: project.get(key) for key in keys}


def build_master_payload(
    projects: list[dict[str, Any]],
    estimate_payload: dict[str, Any],
    *,
    pipeline_commit: str,
    generated_at: str | None = None,
) -> dict[str, Any]:
    """Merge geometry states without duplicating the underlying projects."""
    projects_by_id = _unique_by(projects, "id", "project")
    estimates = estimate_payload.get("estimates") or []
    estimates_by_id = _unique_by(estimates, "project_id", "estimate")
    unresolved_by_id = {
        item.get("project_id"): item.get("reason")
        for item in estimate_payload.get("unresolved") or []
        if item.get("project_id")
    }
    orphan_estimates = sorted(set(estimates_by_id) - set(projects_by_id))
    if orphan_estimates:
        raise ValueError(f"estimated geometry refers to unknown projects: {orphan_estimates}")

    canonical: list[dict[str, Any]] = []
    for project_id, project in projects_by_id.items():
        verified = _geojson(project.get("geometry"), project.get("geometry_type"))
        estimate = estimates_by_id.get(project_id)
        estimated = None
        if estimate:
            estimated = _geojson(estimate.get("geometry"), estimate.get("geometry_type"))

        if verified is not None:
            analysis = verified
            status = "VERIFIED"
            geometry_record = project
        elif estimated is not None:
            analysis = estimated
            status = "ESTIMATED"
            geometry_record = estimate or {}
        else:
            analysis = None
            status = "UNRESOLVED"
            geometry_record = {}

        canonical.append(
            {
                "project_id": project_id,
                "utility": project.get("utility"),
                "project_name": project.get("name"),
                "project_type": project.get("project_type"),
                "voltage": project.get("voltage_kv") or [],
                "planned_start_year": project.get("planned_start_year"),
                "planned_end_year": project.get("planned_end_year"),
                "in_service_year": project.get("in_service_year"),
                "status": project.get("status"),
                "source_metadata": _source_metadata(project),
                "verified_geometry": verified,
                "estimated_geometry": estimated,
                "analysis_geometry": analysis,
                "geometry_status": status,
                "geometry_method": geometry_record.get("geometry_method"),
                "geometry_confidence": geometry_record.get("geometry_confidence"),
                "geometry_source": geometry_record.get("geometry_source"),
                "geometry_notes": geometry_record.get("geometry_notes"),
                "geometry_tier_eligibility": geometry_record.get("tier_eligibility"),
                "unresolved_reason": (
                    unresolved_by_id.get(project_id)
                    if status == "UNRESOLVED"
                    else None
                ),
                "county_region": project.get("county_region"),
                "endpoint_candidates": project.get("endpoint_candidates") or [],
            }
        )

    canonical.sort(
        key=lambda item: (
            item["utility"],
            (item["project_name"] or "").casefold(),
            item["project_id"],
        )
    )
    utilities = Counter(item["utility"] for item in canonical)
    statuses = Counter(item["geometry_status"] for item in canonical)
    if set(statuses) - GEOMETRY_STATUSES:
        unsupported = sorted(set(statuses) - GEOMETRY_STATUSES)
        raise ValueError(f"unsupported geometry status: {unsupported}")

    return {
        "dataset_version": DATASET_VERSION,
        "generated_at": generated_at or datetime.now(UTC).isoformat(),
        "pipeline_commit": pipeline_commit,
        "total_projects": len(canonical),
        "DESC_count": utilities["DESC"],
        "GPC_count": utilities["GPC"],
        "verified_geometry_count": statuses["VERIFIED"],
        "estimated_geometry_count": statuses["ESTIMATED"],
        "unresolved_count": statuses["UNRESOLVED"],
        "projects": canonical,
    }


def _pipeline_commit(root: Path) -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def _json_cell(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_machine_exports(output_path: Path, payload: dict[str, Any]) -> dict[str, Path]:
    """Write transport formats derived only from the canonical JSON payload."""
    published = output_path.parent
    ndjson_path = published / "gridlock_master_projects.ndjson"
    csv_path = published / "gridlock_master_projects.csv"
    manifest_path = published / "publication_manifest.json"

    with ndjson_path.open("w", encoding="utf-8") as handle:
        for project in payload["projects"]:
            document = {
                "dataset_version": payload["dataset_version"],
                "pipeline_commit": payload["pipeline_commit"],
                **project,
            }
            handle.write(_json_cell(document) + "\n")

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SQL_COLUMNS)
        writer.writeheader()
        for project in payload["projects"]:
            writer.writerow(
                {
                    "dataset_version": payload["dataset_version"],
                    "pipeline_commit": payload["pipeline_commit"],
                    "project_id": project["project_id"],
                    "utility": project["utility"],
                    "project_name": project["project_name"],
                    "project_type": project["project_type"],
                    "voltage_json": _json_cell(project["voltage"]),
                    "planned_start_year": project["planned_start_year"],
                    "planned_end_year": project["planned_end_year"],
                    "in_service_year": project["in_service_year"],
                    "status": project["status"],
                    "geometry_status": project["geometry_status"],
                    "geometry_method": project["geometry_method"],
                    "geometry_confidence": project["geometry_confidence"],
                    "verified_geometry_json": _json_cell(project["verified_geometry"]),
                    "estimated_geometry_json": _json_cell(project["estimated_geometry"]),
                    "analysis_geometry_json": _json_cell(project["analysis_geometry"]),
                    "source_metadata_json": _json_cell(project["source_metadata"]),
                }
            )

    artifacts = {}
    for artifact_path, artifact_format in (
        (output_path, "canonical-json"),
        (ndjson_path, "ndjson"),
        (csv_path, "csv"),
    ):
        artifacts[artifact_path.name] = {
            "format": artifact_format,
            "path": str(artifact_path.relative_to(output_path.parents[2])),
            "sha256": _sha256(artifact_path),
        }
    manifest = {
        "dataset_version": payload["dataset_version"],
        "generated_at": payload["generated_at"],
        "pipeline_commit": payload["pipeline_commit"],
        "total_projects": payload["total_projects"],
        "artifacts": artifacts,
    }
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {
        "json": output_path,
        "ndjson": ndjson_path,
        "csv": csv_path,
        "manifest": manifest_path,
    }


def publish_master(root: Path) -> tuple[Path, dict[str, Any]]:
    product_path = root / "data/processed/gridlock_product_projects.json"
    estimate_path = root / "data/curated/estimated_geometry.json"
    output_path = root / "data/published/gridlock_master_projects.json"
    projects = _read_json(product_path)
    estimates = _read_json(estimate_path)
    if not isinstance(projects, list):
        raise ValueError("gridlock_product_projects.json must be an array")
    if not isinstance(estimates, dict):
        raise ValueError("estimated_geometry.json must be an object")
    payload = build_master_payload(
        projects,
        estimates,
        pipeline_commit=_pipeline_commit(root),
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    write_machine_exports(output_path, payload)
    return output_path, payload


def publish_all(root: Path, product_root: Path | None = None) -> dict[str, Any]:
    master_path, payload = publish_master(root)
    if product_root is not None:
        script = product_root / "scripts/publish_downstream.py"
        if not script.exists():
            raise FileNotFoundError(f"downstream publisher not found: {script}")
        subprocess.run(
            [sys.executable, str(script), "--master", str(master_path)],
            cwd=product_root,
            check=True,
        )
    return payload
