import json
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.extraction import read_pages_jsonl
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers import Sertp2026Parser

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def test_manually_verified_golden_records_match_parser_output() -> None:
    golden = json.loads(
        Path("tests/golden/sertp_2026/observations.json").read_text(encoding="utf-8")
    )
    document = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 SERTP Preliminary Expansion Plan Report (Non-CEII)",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        public_access=True,
        pipeline_version="0.1.0",
    )
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    actual = {
        item.project_name_raw: item.model_dump(mode="json")
        for item in Sertp2026Parser().parse(pages, document).observations
    }

    assert len(golden) == 10
    for expected in golden:
        project_name = expected["project_name_raw"]
        assert project_name in actual
        for field, value in expected.items():
            assert actual[project_name][field] == value, f"{project_name}: {field}"
