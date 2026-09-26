import json
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.acquisition import SourcePolicy
from gridlock_pipeline.discovery import parse_georgia_power_listing
from gridlock_pipeline.export import export_observations_json
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers import GeorgiaPowerParser, GeorgiaPowerProjectPage

LISTING_URL = (
    "https://www.georgiapower.com/about/grid-reliability/grid-improvements/"
    "grid-projects/transmission-projects.html"
)
SHA = "a" * 64
PROJECT_PREFIX = (
    "/about/grid-reliability/grid-improvements/grid-projects/transmission-projects/"
)

LISTING_HTML = f"""
<html><body>
<table id="current-projects-table"><thead><tr><th>Project Name</th>
<th>County/Region</th><th>Type</th></tr></thead><tbody>
<tr><td><a href="{PROJECT_PREFIX}tomochichi-towaliga.html">
Tomochichi – Towaliga River 230 kV</a></td>
<td>Butts &amp; Spalding counties</td><td>Area Project</td></tr>
<tr><td><a href="{PROJECT_PREFIX}decatur-scottdale.html">
Decatur – Scottdale 115 kV</a></td>
<td>Dekalb County</td><td>Transmission Line Upgrade</td></tr>
</tbody></table>
<a href="/about/unrelated.html">Unrelated Georgia Power page</a>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<div class="content-card--content"><h2>About the Project</h2>
<p>Georgia Power is planning new transmission infrastructure in Butts and Spalding
counties.</p></div>
<div class="content-card--content"><h3>What’s included in the project?</h3>
<ul><li><strong>Tomochichi – Towaliga River #1 230 kV Transmission Line</strong>:
Construction of one new approximately 5‑mile 230 kV transmission line.</li>
<li>Construction of the Tomochichi Substation.</li></ul></div>
<div class="content-card--content"><h2>Project Timeline</h2></div>
<table>
<tr><td><strong>Q2 2026 - Q1 2027</strong></td>
<td>Transmission Line Survey Notifications and Land Acquisition Activities</td></tr>
<tr><td><strong>Q1 2027</strong></td><td>Transmission Line Construction Begins</td></tr>
<tr><td><strong>Q4 2027</strong></td><td>Project Completion Target</td></tr>
</table>
</body></html>
"""


def policy() -> SourcePolicy:
    return SourcePolicy(
        implemented_years=[2026],
        discovery_pages=[LISTING_URL],
        allowed_hosts=["www.georgiapower.com"],
        blocked_path_fragments=["login"],
        title_keywords=["current projects"],
        timeout_seconds=30,
        max_content_bytes=5_242_880,
        request_interval_seconds=0,
        ambiguity_margin=0,
    )


def document() -> SourceDocument:
    return SourceDocument(
        document_id="georgia-power-2026-current-transmission-projects",
        source="georgia_power",
        planning_year=2026,
        document_type="current_projects_listing",
        title="Georgia Power Current Transmission Projects",
        discovery_url=LISTING_URL,
        source_url=LISTING_URL,
        final_url=LISTING_URL,
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="text/html",
        content_length=1,
        sha256=SHA,
        page_count=2,
        public_access=True,
        pipeline_version="0.1.0",
    )


def parsed_observation():
    project = parse_georgia_power_listing(LISTING_HTML, LISTING_URL, policy())[0]
    page = GeorgiaPowerProjectPage(project=project, html=DETAIL_HTML, sha256=SHA)
    return GeorgiaPowerParser().parse([page], document()).observations[0]


def test_listing_parser_follows_only_rows_in_official_project_table() -> None:
    projects = parse_georgia_power_listing(LISTING_HTML, LISTING_URL, policy())

    assert [project.name for project in projects] == [
        "Tomochichi – Towaliga River 230 kV",
        "Decatur – Scottdale 115 kV",
    ]
    assert projects[0].county_region == "Butts & Spalding counties"
    assert projects[1].project_type == "Transmission Line Upgrade"
    assert all("/transmission-projects/" in project.url for project in projects)


def test_detail_parser_preserves_attribution_technical_fields_and_provenance() -> None:
    observation = parsed_observation()

    assert observation.utility == "GPC"
    assert observation.source == "georgia_power"
    assert observation.county_region_raw == "Butts & Spalding counties"
    assert observation.project_type_raw == "Area Project"
    assert observation.project_type == "area_project"
    assert observation.voltage_kv == [230.0]
    assert observation.length_miles == [5.0]
    assert observation.endpoint_candidates == ["Tomochichi", "Towaliga River"]
    assert observation.source_url.endswith("/tomochichi-towaliga.html")
    assert observation.source_sha256 == SHA
    assert "About the Project:" in observation.raw_record_text


def test_quarter_timeline_is_not_converted_to_exact_dates() -> None:
    observation = parsed_observation()

    assert observation.timeline_raw[0].startswith("Q2 2026 - Q1 2027 |")
    assert observation.construction_start_raw == [
        "Q1 2027 | Transmission Line Construction Begins"
    ]
    assert observation.completion_target_raw == "Q4 2027 | Project Completion Target"
    assert observation.in_service_year_raw == "Q4 2027"
    assert observation.in_service_year is None


def test_georgia_power_export_is_deterministic(tmp_path: Path) -> None:
    first_observation = parsed_observation()
    second_project = parse_georgia_power_listing(LISTING_HTML, LISTING_URL, policy())[1]
    second_observation = GeorgiaPowerParser().parse(
        [GeorgiaPowerProjectPage(second_project, DETAIL_HTML, "b" * 64)], document()
    ).observations[0]
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    export_observations_json([first_observation, second_observation], first)
    export_observations_json([second_observation, first_observation], second)

    assert first.read_bytes() == second.read_bytes()
    assert {item["utility"] for item in json.loads(first.read_text())} == {"GPC"}
