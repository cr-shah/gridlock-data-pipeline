import csv
import json
from pathlib import Path

from gridlock_pipeline.pipeline import PipelineRunner

DISCOVERY_URL = "https://www.southeasternrtp.com/reference_library.cshtml"
PDF_URL = "https://www.southeasternrtp.com/report.pdf"


class FakeResponse:
    def __init__(self, *, text="", content=b"", url=DISCOVERY_URL, content_type="text/html"):
        self.text = text
        self.content = content
        self.url = url
        self.status_code = 200
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, pdf: bytes):
        self.pdf = pdf

    def get(self, url: str, **_kwargs) -> FakeResponse:
        if url == DISCOVERY_URL:
            return FakeResponse(
                text=(
                    "<a href='/report.pdf'>"
                    "2026 SERTP Preliminary Expansion Plan Report (Non-CEII)</a>"
                )
            )
        if url == PDF_URL:
            return FakeResponse(content=self.pdf, url=PDF_URL, content_type="application/pdf")
        raise AssertionError(f"unexpected URL: {url}")


def test_vertical_slice_exports_cached_source_with_complete_provenance(tmp_path: Path) -> None:
    pdf = Path("tests/fixtures/sertp/two_page_projects.pdf").read_bytes()
    runner = PipelineRunner(root=tmp_path, session=FakeSession(pdf))

    result = runner.run(source="sertp", year=2026)

    assert result.document.sha256
    assert result.document.page_count == 2
    assert len(result.observations) == 1
    observation = result.observations[0]
    assert observation.raw_record_text
    assert observation.pdf_page_range == [0, 1]
    assert observation.source_sha256 == result.document.sha256
    assert observation.extraction_engine == "PyMuPDF"
    assert observation.field_provenance

    json_rows = json.loads((tmp_path / "data/processed/sertp_2026_projects.json").read_text())
    with (tmp_path / "data/processed/sertp_2026_projects.csv").open(
        newline="", encoding="utf-8"
    ) as stream:
        csv_rows = list(csv.DictReader(stream))
    assert len(json_rows) == len(csv_rows) == 1
    assert (tmp_path / "schemas/project_observation.schema.json").exists()
    assert (tmp_path / "data/processed/source_manifest.json").exists()
