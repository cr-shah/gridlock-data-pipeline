from datetime import UTC, datetime, timedelta
from pathlib import Path

from gridlock_pipeline.export.csv_export import export_observations_csv
from gridlock_pipeline.export.json_export import export_observations_json
from gridlock_pipeline.export.schema_export import export_project_schema
from gridlock_pipeline.extraction import read_pages_jsonl
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers import Sertp2026Parser

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def document(acquired_at: datetime) -> SourceDocument:
    return SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 report",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=acquired_at,
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        page_count=115,
        public_access=True,
        pipeline_version="0.1.0",
    )


def parsed(acquired_at: datetime, *, extraction_version: str | None = None):
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    if extraction_version:
        pages = [
            page.model_copy(update={"extraction_engine_version": extraction_version})
            for page in pages
        ]
    return Sertp2026Parser().parse(pages, document(acquired_at)).observations


def write_contract_bundle(tmp_path: Path, stem: str, observations) -> dict[str, bytes]:
    json_path = tmp_path / f"{stem}.json"
    csv_path = tmp_path / f"{stem}.csv"
    schema_path = tmp_path / f"{stem}.schema.json"
    export_observations_json(observations, json_path)
    export_observations_csv(observations, csv_path)
    export_project_schema(schema_path)
    return {
        "json": json_path.read_bytes(),
        "csv": csv_path.read_bytes(),
        "schema": schema_path.read_bytes(),
    }


def test_observation_bundle_is_byte_identical_for_identical_cached_input(tmp_path: Path) -> None:
    acquired_at = datetime(2026, 9, 26, tzinfo=UTC)

    first = write_contract_bundle(tmp_path, "first", parsed(acquired_at))
    second = write_contract_bundle(tmp_path, "second", parsed(acquired_at))

    assert first == second


def test_acquisition_time_does_not_perturb_observation_outputs(tmp_path: Path) -> None:
    acquired_at = datetime(2026, 9, 26, tzinfo=UTC)

    first = write_contract_bundle(tmp_path, "first", parsed(acquired_at))
    second = write_contract_bundle(tmp_path, "second", parsed(acquired_at + timedelta(days=1)))

    assert first == second


def test_extraction_version_is_explicit_and_changes_observation_output(tmp_path: Path) -> None:
    acquired_at = datetime(2026, 9, 26, tzinfo=UTC)

    first = write_contract_bundle(tmp_path, "first", parsed(acquired_at))
    second = write_contract_bundle(
        tmp_path, "second", parsed(acquired_at, extraction_version="99.0-test")
    )

    assert first["json"] != second["json"]
    assert first["csv"] != second["csv"]
    assert first["schema"] == second["schema"]
