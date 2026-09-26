from pathlib import Path
from types import SimpleNamespace

import pytest
from test_exports import observations

import gridlock_pipeline.pipeline as pipeline_module
from gridlock_pipeline.parsers import ParseResult
from gridlock_pipeline.pipeline import PipelineRunner
from gridlock_pipeline.validation import QualityGateError, build_quality_report
from gridlock_pipeline.validation.quality import write_data_quality


def test_mid_export_failure_preserves_known_good_outputs_and_writes_diagnostic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processed = tmp_path / "data/processed"
    processed.mkdir(parents=True)
    known_good = {
        "sertp_2026_projects.json": b"known-good-json",
        "sertp_2026_projects.csv": b"known-good-csv",
    }
    for name, content in known_good.items():
        (processed / name).write_bytes(content)
    records = observations()
    report = build_quality_report(records)

    def fail_export(*_args, **_kwargs) -> None:
        raise RuntimeError("simulated CSV export failure")

    monkeypatch.setattr(pipeline_module, "export_observations_csv", fail_export)

    with pytest.raises(RuntimeError, match="simulated CSV export failure"):
        PipelineRunner(root=tmp_path).export(records, _document(records), report)

    assert {
        name: (processed / name).read_bytes() for name in known_good
    } == known_good
    diagnostic = tmp_path / "data/failed_runs/latest.json"
    assert diagnostic.exists()
    assert "simulated CSV export failure" in diagnostic.read_text()


def test_quality_gate_failure_never_promotes_candidate_outputs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processed = tmp_path / "data/processed"
    processed.mkdir(parents=True)
    published = processed / "sertp_2026_projects.json"
    published.write_bytes(b"known-good-json")
    records = observations()
    source_document = _document(records)
    runner = PipelineRunner(root=tmp_path)
    monkeypatch.setattr(runner, "discover", lambda **_kwargs: object())
    monkeypatch.setattr(
        runner,
        "download",
        lambda *_args, **_kwargs: SimpleNamespace(metadata=source_document),
    )
    monkeypatch.setattr(runner, "extract", lambda *_args: [object()] * 50)
    monkeypatch.setattr(
        runner,
        "parse",
        lambda *_args: ParseResult(observations=records, diagnostics=[]),
    )

    with pytest.raises(QualityGateError, match="implausibly few"):
        runner.run(source="sertp", year=2026)

    assert published.read_bytes() == b"known-good-json"


def test_previous_quality_collapse_preserves_outputs_and_reports_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    processed = tmp_path / "data/processed"
    processed.mkdir(parents=True)
    published = processed / "sertp_2026_projects.json"
    published.write_bytes(b"known-good-json")
    seed = observations()[0]
    previous_records = [seed.model_copy(update={"observation_id": f"old-{i}"}) for i in range(426)]
    current_records = [seed.model_copy(update={"observation_id": f"new-{i}"}) for i in range(100)]
    write_data_quality(build_quality_report(previous_records), processed / "data_quality.json")
    runner = PipelineRunner(root=tmp_path)
    source_document = _document(current_records)
    monkeypatch.setattr(runner, "discover", lambda **_kwargs: object())
    monkeypatch.setattr(
        runner,
        "download",
        lambda *_args, **_kwargs: SimpleNamespace(metadata=source_document),
    )
    monkeypatch.setattr(runner, "extract", lambda *_args: [object()] * 115)
    monkeypatch.setattr(
        runner,
        "parse",
        lambda *_args: ParseResult(observations=current_records, diagnostics=[]),
    )

    with pytest.raises(QualityGateError, match="collapse"):
        runner.run(source="sertp", year=2026)

    assert published.read_bytes() == b"known-good-json"
    assert "collapse" in (tmp_path / "data/failed_runs/latest.json").read_text()


def _document(records):
    record = records[0]
    from datetime import UTC, datetime

    from gridlock_pipeline.models import SourceDocument

    return SourceDocument(
        document_id=record.document_id,
        source=record.source,
        planning_year=record.planning_year,
        document_type="preliminary_expansion_plan",
        title=record.source_title,
        discovery_url=record.source_url,
        source_url=record.source_url,
        final_url=record.source_url,
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=record.source_sha256,
        page_count=115,
        public_access=True,
        pipeline_version=record.pipeline_version,
    )
