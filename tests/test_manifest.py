import json
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.export.manifest import write_source_manifest
from gridlock_pipeline.models import SourceDocument


def test_source_manifest_preserves_document_identity(tmp_path: Path) -> None:
    document = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 SERTP Preliminary Expansion Plan Report (Non-CEII)",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
        http_status=200,
        content_type="application/pdf",
        content_length=123,
        sha256="a" * 64,
        public_access=True,
        access_notes=["anonymous public download"],
        pipeline_version="0.1.0",
    )
    path = tmp_path / "source_manifest.json"

    write_source_manifest(document, path)
    manifest = json.loads(path.read_text())

    assert manifest["current"]["sha256"] == "a" * 64
    assert manifest["current"]["public_access"] is True
    assert manifest["history"] == []
