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


def test_source_manifest_retains_prior_hash_once_when_source_changes(tmp_path: Path) -> None:
    current = SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 report",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url="https://www.southeasternrtp.com/report.pdf",
        final_url="https://www.southeasternrtp.com/report.pdf",
        acquired_at=datetime(2026, 9, 26, 12, 0, tzinfo=UTC),
        content_type="application/pdf",
        content_length=200,
        sha256="b" * 64,
        etag='"new"',
        last_modified="Fri, 26 Sep 2026 12:00:00 GMT",
        public_access=True,
        pipeline_version="0.1.0",
    )
    previous = {
        "schema_version": "1.0",
        "current": {"sha256": "a" * 64, "title": "old"},
        "history": [],
    }
    path = tmp_path / "manifest.json"

    write_source_manifest(current, path, previous=previous)
    manifest = json.loads(path.read_text())

    assert manifest["current"]["etag"] == '"new"'
    assert manifest["current"]["last_modified"] == "Fri, 26 Sep 2026 12:00:00 GMT"
    assert [item["sha256"] for item in manifest["history"]] == ["a" * 64]
