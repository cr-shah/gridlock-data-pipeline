import json
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.export import export_observations_json
from gridlock_pipeline.extraction import ExtractedPage, read_pages_jsonl
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers import ScrtpDescParser, Sertp2026Parser

SHA = "a" * 64


def document(source: str = "scrtp") -> SourceDocument:
    return SourceDocument(
        document_id="scrtp-2026-desc-current-projects",
        source=source,
        planning_year=2026,
        document_type="planned_projects",
        title="DESC current projects",
        discovery_url="https://www.scrtp.com/report.pdf",
        source_url="https://www.scrtp.com/report.pdf",
        final_url="https://www.scrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        page_count=2,
        public_access=True,
        pipeline_version="0.1.0",
    )


def page(index: int, name: str, project_id: str, date: str, cost: str) -> ExtractedPage:
    return ExtractedPage(
        pdf_page_index=index,
        printed_page_number=index + 1,
        text=(
            f"Project {index + 1} of 54\nDominion Energy South Carolina\n"
            "Planned Transmission Projects $2M and above Total\n5 Year Budget\n"
            f"{name}\nProject ID\n{project_id}\nProject Description\n"
            "Rebuild 13.5 miles of the 115 kV line.\nProject Need\nGrid hardening.\n"
            f"Project Status\nPlanned\nPlanned In-Service Date\n{date}\n"
            "Estimated Project Cost\nPrevious 2026 2027 2028 2029 2030 Total\n"
            f"{cost}"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )


def test_desc_fields_dates_costs_and_page_provenance() -> None:
    observation = ScrtpDescParser().parse(
        [
            page(
                4,
                "Batesburg - Saluda County 115kV: Rebuild",
                "6809 N",
                "06/31/2026",
                "$12,223,765 $817,000 $13,040,765",
            )
        ],
        document(),
    ).observations[0]

    assert observation.utility == "DESC"
    assert observation.source == "scrtp"
    assert observation.project_id_raw == "6809 N"
    assert observation.project_name_raw == "Batesburg - Saluda County 115kV: Rebuild"
    assert observation.project_need_raw == "Grid hardening."
    assert observation.project_status_raw == "Planned"
    assert observation.planned_in_service_date_raw == "06/31/2026"
    assert observation.in_service_year == 2026
    assert observation.estimated_cost_usd == 13_040_765
    assert observation.pdf_page_range == [4, 4]
    assert observation.endpoint_candidates == ["Batesburg", "Saluda County"]


def test_desc_export_is_deterministic(tmp_path: Path) -> None:
    observations = ScrtpDescParser().parse(
        [
            page(1, "Alpha - Beta 115kV: Rebuild", "2 B", "12/31/2027", "$2,000,000"),
            page(0, "Gamma 230kV Sub: Construct", "1 A", "5/31/2026", "$3,000,000"),
        ],
        document(),
    ).observations
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    export_observations_json(observations, first)
    export_observations_json(list(reversed(observations)), second)

    assert first.read_bytes() == second.read_bytes()
    assert json.loads(first.read_text())[0]["project_id_raw"] == "1 A"


def test_existing_sertp_parser_remains_compatible() -> None:
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    sertp_document = document("sertp").model_copy(
        update={"document_id": "sertp-2026-preliminary-non-ceii"}
    )

    observations = Sertp2026Parser().parse(pages, sertp_document).observations

    assert len(observations) == 22
    assert not hasattr(observations[0], "project_id_raw")
