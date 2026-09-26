"""Build the GIS-enriched product export from the verified DESC/GPC inventory."""

import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

ALLOWED_UTILITIES = frozenset({"DESC", "GPC"})
ALLOWED_CONFIDENCE = frozenset({"HIGH", "MEDIUM", "LOW"})
EXPECTED_COUNTS = {"DESC": 54, "GPC": 10}
YEAR_PATTERN = re.compile(r"\b(20\d{2})\b")
PROJECT_LONGITUDE_BOUNDS = (-86.0, -78.0)
PROJECT_LATITUDE_BOUNDS = (30.0, 36.0)

CALLAWAY_SOURCE = (
    "https://www.georgiapower.com/about/grid-reliability/grid-improvements/"
    "grid-projects/transmission-projects/callaway-thomson.html"
)
JASPER_OKATIE_SOURCE = (
    "https://www.dominionenergy.com/-/media/content/about/power-line-projects/"
    "jasper-okatie-riverport/pdfs/jor-final-route-selection-map.pdf"
)
EIA_860_SOURCE = "https://www.eia.gov/electricity/data/eia860/"


# This intentionally small map contains only evidence auditable against a stable project ID.
# Coordinates are GeoJSON order: [longitude, latitude].
GIS_EVIDENCE: dict[str, dict[str, Any]] = {
    "georgia-power-2026-4a60199d0029a784348e": {
        "geometry": [
            [-82.41269284, 33.45645761],
            [-82.40626089, 33.45875844],
            [-82.40622496, 33.46009997],
            [-82.40902413, 33.46150711],
            [-82.40902735, 33.46150913],
            [-82.40902842, 33.46151158],
            [-82.40902858, 33.46151209],
            [-82.41095834, 33.46849810],
            [-82.41095839, 33.46849827],
            [-82.41095953, 33.46850602],
            [-82.41168671, 33.47693070],
            [-82.41304197, 33.48345849],
            [-82.41304310, 33.48346671],
            [-82.41304313, 33.48346773],
            [-82.41296236, 33.49111038],
            [-82.41296155, 33.49111615],
            [-82.41296135, 33.49111693],
            [-82.41207238, 33.49415252],
            [-82.41104795, 33.49765039],
            [-82.40752843, 33.50966543],
            [-82.40752715, 33.50966837],
            [-82.40752619, 33.50966913],
            [-82.40752289, 33.50967125],
            [-82.39458695, 33.51718586],
            [-82.39458273, 33.51718790],
            [-82.39458235, 33.51718785],
            [-82.39457660, 33.51718643],
            [-82.37866143, 33.51247149],
            [-82.37865588, 33.51246948],
            [-82.37865190, 33.51246756],
            [-82.37732516, 33.51168248],
            [-82.37582817, 33.51091517],
            [-82.38059608, 33.50601332],
            [-82.37450549, 33.49879975],
            [-82.36720596, 33.49508605],
            [-82.36720272, 33.49508403],
            [-82.36720472, 33.49508070],
            [-82.37049657, 33.49059904],
            [-82.37369401, 33.48624541],
            [-82.39345709, 33.45932444],
            [-82.39345917, 33.45932187],
            [-82.39346018, 33.45932086],
            [-82.39346021, 33.45932083],
            [-82.40394834, 33.45540984],
            [-82.40394963, 33.45540940],
            [-82.40395216, 33.45540877],
            [-82.40395506, 33.45541058],
            [-82.40723109, 33.45795657],
            [-82.41248625, 33.45608291],
        ],
        "geometry_type": "LineString",
        "geometry_source": CALLAWAY_SOURCE,
        "geometry_method": "official_project_route_coordinates",
        "geometry_confidence": "HIGH",
        "geometry_notes": (
            "Two official proposed 500 kV route components embedded in the Georgia Power "
            "project page are joined at their shared Callaway Road endpoint as one LineString. "
            "The page states that the route is preliminary and based on pre-engineering data."
        ),
    },
    "scrtp-desc-2026-6c4897da52154c18c1d1": {
        "geometry": [
            [-81.124490, 32.359587],
            [-81.123960, 32.366611],
            [-81.117305, 32.367684],
            [-81.101113, 32.367541],
            [-81.092115, 32.364492],
            [-81.078616, 32.357476],
            [-81.065119, 32.351070],
            [-81.053424, 32.345122],
            [-81.048564, 32.338253],
            [-81.039930, 32.335205],
            [-81.032376, 32.334445],
        ],
        "geometry_type": "LineString",
        "geometry_source": JASPER_OKATIE_SOURCE,
        "geometry_method": "official_georeferenced_route_map_trace",
        "geometry_confidence": "HIGH",
        "geometry_notes": (
            "Centerline traced from the official georeferenced final selected 400-foot route "
            "corridor map. It represents the selected corridor, not an as-built survey alignment."
        ),
    },
    "scrtp-desc-2026-99cdb225cd296159f73c": {
        "geometry": [-81.032376, 32.334445],
        "geometry_type": "Point",
        "geometry_source": JASPER_OKATIE_SOURCE,
        "geometry_method": "official_project_map_facility_point",
        "geometry_confidence": "HIGH",
        "geometry_notes": "Existing Okatie Substation location from the official project map.",
    },
    "scrtp-desc-2026-709d9acc84bd6eb25bd2": {
        "geometry": [-81.9111, 33.4350],
        "geometry_type": "Point",
        "geometry_source": EIA_860_SOURCE,
        "geometry_method": "public_facility_endpoint_point",
        "geometry_confidence": "MEDIUM",
        "geometry_notes": (
            "EIA-860 coordinates for Urquhart plant (Plant ID 3295); this represents only the "
            "named Urquhart endpoint, not the Aiken PSA line route."
        ),
    },
    "scrtp-desc-2026-51b7f3df6753d9825f1a": {
        "geometry": [-81.9111, 33.4350],
        "geometry_type": "Point",
        "geometry_source": EIA_860_SOURCE,
        "geometry_method": "public_facility_endpoint_point",
        "geometry_confidence": "MEDIUM",
        "geometry_notes": (
            "EIA-860 coordinates for Urquhart plant (Plant ID 3295); this represents only the "
            "named Urquhart endpoint, not the Toolebeck line route."
        ),
    },
}


def _years(value: Any) -> list[int]:
    if value is None:
        return []
    values = value if isinstance(value, list) else [value]
    return [int(year) for item in values for year in YEAR_PATTERN.findall(str(item))]


def _gpc_schedule(record: dict[str, Any]) -> tuple[int | None, int | None]:
    start_years = _years(record.get("construction_start_raw"))
    end_years = _years(record.get("completion_target_raw"))
    if not end_years:
        completion_entries = [
            item
            for item in record.get("timeline_raw", [])
            if "complete" in str(item).casefold() or "completion" in str(item).casefold()
        ]
        end_years = _years(completion_entries)
    return (min(start_years) if start_years else None, max(end_years) if end_years else None)


def _source_page(record: dict[str, Any]) -> int | str | None:
    source_url = record.get("source_url")
    if isinstance(source_url, str) and source_url.casefold().endswith(".pdf"):
        return record.get("pdf_page_start")
    return None


def _priority_region(record: dict[str, Any]) -> bool:
    text = " ".join(
        str(value)
        for value in (
            record.get("project_name_normalized"),
            record.get("county_region_raw"),
            record.get("location_mentions"),
        )
    ).casefold()
    return any(
        term in text
        for term in (
            "savannah",
            "jasper",
            "okatie",
            "bluffton",
            "effingham",
            "augusta",
            "urquhart",
            "thomson",
        )
    )


def _validate_coordinate(coordinate: Any) -> None:
    if not isinstance(coordinate, list) or len(coordinate) != 2:
        raise ValueError(f"invalid coordinate: {coordinate!r}")
    longitude, latitude = coordinate
    if not isinstance(longitude, (int, float)) or not -180 <= longitude <= 180:
        raise ValueError(f"invalid longitude: {longitude!r}")
    if not isinstance(latitude, (int, float)) or not -90 <= latitude <= 90:
        raise ValueError(f"invalid latitude: {latitude!r}")
    if not (
        PROJECT_LONGITUDE_BOUNDS[0] <= longitude <= PROJECT_LONGITUDE_BOUNDS[1]
        and PROJECT_LATITUDE_BOUNDS[0] <= latitude <= PROJECT_LATITUDE_BOUNDS[1]
    ):
        raise ValueError(f"coordinate outside the expected SC/GA project region: {coordinate!r}")


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _validate_projects(projects: list[dict[str, Any]]) -> None:
    counts = Counter(project["utility"] for project in projects)
    if len(projects) != 64 or counts != EXPECTED_COUNTS:
        raise ValueError(f"expected 64 projects with {EXPECTED_COUNTS}; found {dict(counts)}")
    ids = [project["id"] for project in projects]
    if len(ids) != len(set(ids)):
        raise ValueError("product project IDs must be unique")
    if set(counts) != ALLOWED_UTILITIES:
        raise ValueError(f"unsupported utilities: {sorted(set(counts) - ALLOWED_UTILITIES)}")

    for project in projects:
        for field in ("id", "name"):
            if not isinstance(project[field], str) or not project[field]:
                raise ValueError(f"{field} must be a non-empty string for {project['id']!r}")
        if project["project_type"] is not None and not isinstance(project["project_type"], str):
            raise ValueError(f"project_type must be a string or null for {project['id']}")
        for field in ("planned_start_year", "planned_end_year", "in_service_year"):
            if project[field] is not None and not isinstance(project[field], int):
                raise ValueError(f"{field} must be an integer or null for {project['id']}")
        if not isinstance(project["voltage_kv"], list) or not all(
            _is_number(voltage) for voltage in project["voltage_kv"]
        ):
            raise ValueError(f"voltage_kv must be a numeric array for {project['id']}")
        if project["source_url"] is not None and not isinstance(project["source_url"], str):
            raise ValueError(f"source_url must be a string or null for {project['id']}")
        source_page = project["source_page"]
        if source_page is not None and not (
            isinstance(source_page, str) or _is_number(source_page)
        ):
            raise ValueError(f"source_page has an invalid type for {project['id']}")
        if project["data_confidence"] not in ALLOWED_CONFIDENCE:
            raise ValueError(f"invalid data confidence for {project['id']}")
        geometry = project["geometry"]
        geometry_type = project["geometry_type"]
        if geometry is None:
            if geometry_type is not None:
                raise ValueError(f"null geometry must have null type for {project['id']}")
            if any(
                project[field] is not None
                for field in (
                    "geometry_source",
                    "geometry_method",
                    "geometry_confidence",
                    "geometry_notes",
                )
            ):
                raise ValueError(f"null geometry must have null GIS metadata for {project['id']}")
        elif geometry_type == "Point":
            _validate_coordinate(geometry)
        elif geometry_type == "LineString":
            if not isinstance(geometry, list) or len(geometry) < 2:
                raise ValueError(f"invalid LineString for {project['id']}")
            for coordinate in geometry:
                _validate_coordinate(coordinate)
        else:
            raise ValueError(f"invalid geometry type for {project['id']}: {geometry_type!r}")
        if geometry is not None:
            for field in ("geometry_source", "geometry_method", "geometry_notes"):
                if not isinstance(project[field], str) or not project[field]:
                    raise ValueError(f"{field} must be a non-empty string for {project['id']}")
            if project["geometry_confidence"] not in {"HIGH", "MEDIUM"}:
                raise ValueError(f"invalid geometry confidence for {project['id']}")


def build_product_projects(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Transform verified records without changing their project-source provenance."""
    record_ids = {record.get("observation_id") for record in records}
    unknown_evidence = set(GIS_EVIDENCE) - record_ids
    if unknown_evidence:
        raise ValueError(f"GIS evidence refers to unknown project IDs: {sorted(unknown_evidence)}")

    projects: list[dict[str, Any]] = []
    review_queue: list[dict[str, Any]] = []
    for record in records:
        project_id = record["observation_id"]
        if record.get("utility") == "GPC":
            planned_start_year, planned_end_year = _gpc_schedule(record)
        else:
            planned_start_year, planned_end_year = None, None

        evidence = GIS_EVIDENCE.get(project_id)
        project = {
            "id": project_id,
            "utility": record["utility"],
            "name": record.get("project_name_normalized") or record.get("project_name_raw"),
            "project_type": record.get("project_type"),
            "planned_start_year": planned_start_year,
            "planned_end_year": planned_end_year,
            "in_service_year": (
                record.get("in_service_year") if record["utility"] == "DESC" else None
            ),
            "voltage_kv": record.get("voltage_kv") or [],
            "geometry": evidence["geometry"] if evidence else None,
            "geometry_type": evidence["geometry_type"] if evidence else None,
            "source_url": record.get("source_url"),
            "source_page": _source_page(record),
            "data_confidence": record.get("confidence"),
            "geometry_source": evidence["geometry_source"] if evidence else None,
            "geometry_method": evidence["geometry_method"] if evidence else None,
            "geometry_confidence": evidence["geometry_confidence"] if evidence else None,
            "geometry_notes": evidence["geometry_notes"] if evidence else None,
        }
        projects.append(project)

        if evidence is None:
            review_queue.append(
                {
                    "id": project_id,
                    "utility": record["utility"],
                    "name": project["name"],
                    "priority_region": _priority_region(record),
                    "review_reason": (
                        "No sufficiently precise public geometry was resolved within the bounded "
                        "source-check limit; geometry remains null."
                    ),
                    "project_source_url": record.get("source_url"),
                    "project_source_page": _source_page(record),
                }
            )

    projects.sort(key=lambda item: (item["utility"], item["name"].casefold(), item["id"]))
    review_queue.sort(
        key=lambda item: (
            not item["priority_region"],
            item["utility"],
            item["name"].casefold(),
            item["id"],
        )
    )
    _validate_projects(projects)
    return projects, review_queue


def write_product_exports(
    verified_path: Path,
    product_path: Path,
    review_queue_path: Path,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    records = json.loads(verified_path.read_text(encoding="utf-8"))
    if not isinstance(records, list):
        raise ValueError("verified project input must be a JSON array")
    projects, review_queue = build_product_projects(records)

    for path, payload in ((product_path, projects), (review_queue_path, review_queue)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return projects, review_queue


def main() -> None:
    processed = Path("data/processed")
    write_product_exports(
        processed / "gridlock_verified_projects.json",
        processed / "gridlock_product_projects.json",
        processed / "gridlock_gis_review_queue.json",
    )


if __name__ == "__main__":
    main()
