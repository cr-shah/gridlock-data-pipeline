import csv
import json
from datetime import UTC, datetime
from pathlib import Path

import jsonschema

from gridlock_pipeline.export.csv_export import export_observations_csv
from gridlock_pipeline.export.json_export import export_observations_json
from gridlock_pipeline.export.schema_export import export_project_schema
from gridlock_pipeline.extraction import read_pages_jsonl
from gridlock_pipeline.models import ProjectObservation, SourceDocument
from gridlock_pipeline.parsers import Sertp2026Parser

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def observations():
    document = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 report",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        page_count=115,
        public_access=True,
        pipeline_version="0.1.0",
    )
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    return Sertp2026Parser().parse(pages, document).observations[:3]


def test_json_csv_and_schema_preserve_records_and_provenance(tmp_path: Path) -> None:
    records = observations()
    json_path = tmp_path / "projects.json"
    csv_path = tmp_path / "projects.csv"
    schema_path = tmp_path / "project_observation.schema.json"

    export_observations_json(records, json_path)
    export_observations_csv(records, csv_path)
    export_project_schema(schema_path)

    json_records = json.loads(json_path.read_text())
    with csv_path.open(newline="", encoding="utf-8") as stream:
        csv_records = list(csv.DictReader(stream))
    schema = json.loads(schema_path.read_text())

    assert len(json_records) == len(csv_records) == 3
    assert [row["observation_id"] for row in json_records] == [
        row["observation_id"] for row in csv_records
    ]
    assert json_records[0]["raw_record_text"]
    assert json_records[0]["extraction_engine_version"] == "1.28.2"
    assert json_records[0]["field_provenance"]
    for row in json_records:
        jsonschema.validate(row, schema)


def test_exports_are_byte_stable_and_order_independent(tmp_path: Path) -> None:
    records = observations()
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    export_observations_json(records, first)
    export_observations_json(list(reversed(records)), second)

    assert first.read_bytes() == second.read_bytes()


def test_generated_schema_is_authoritative_model_schema(tmp_path: Path) -> None:
    path = tmp_path / "schema.json"

    export_project_schema(path)

    assert json.loads(path.read_text()) == ProjectObservation.model_json_schema()

