"""Phase 1 SERTP 2026 pipeline orchestration."""

import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

from gridlock_pipeline.acquisition import SourcePolicy, load_source_policy
from gridlock_pipeline.acquisition.downloader import DownloadedDocument, download_document
from gridlock_pipeline.discovery import discover_sertp_document
from gridlock_pipeline.export import (
    export_observations_csv,
    export_observations_json,
    export_project_schema,
    fsync_output_bundle,
    promote_output_bundle,
    validate_output_bundle,
    write_output_bundle_manifest,
    write_source_manifest,
)
from gridlock_pipeline.extraction import ExtractedPage, extract_pdf_pages, write_pages_jsonl
from gridlock_pipeline.models import ProjectObservation, SourceDocument, SourceDocumentCandidate
from gridlock_pipeline.parsers import ParseResult, Sertp2026Parser
from gridlock_pipeline.validation import (
    DataQualityReport,
    build_quality_report,
    enforce_run_gates,
    flag_duplicate_candidates,
    validate_observation,
    write_data_quality,
    write_review_queue,
)


@dataclass(frozen=True)
class PipelineRunResult:
    document: SourceDocument
    pages: list[ExtractedPage]
    observations: list[ProjectObservation]
    diagnostics: list
    quality_report: DataQualityReport


class PipelineRunner:
    def __init__(
        self,
        *,
        root: Path | None = None,
        session=None,
        policy: SourcePolicy | None = None,
    ):
        self.root = (root or Path.cwd()).resolve()
        self.session = session or requests.Session()
        config_path = self.root / "config/sources.yaml"
        if not config_path.exists():
            config_path = Path.cwd() / "config/sources.yaml"
        self.policy = policy or load_source_policy(config_path, "sertp")

    @staticmethod
    def _check_scope(source: str, year: int) -> None:
        if source != "sertp":
            raise ValueError(f"unsupported source: {source}")
        if year != 2026:
            raise ValueError(f"Phase 1 implements only 2026; received {year}")

    def discover(self, *, source: str, year: int) -> SourceDocumentCandidate:
        self._check_scope(source, year)
        return discover_sertp_document(self.session, year, self.policy)

    def download(
        self,
        candidate: SourceDocumentCandidate,
        *,
        force: bool = False,
    ) -> DownloadedDocument:
        return download_document(
            candidate,
            self.session,
            self.root / "data/raw",
            self.policy,
            force=force,
        )

    def extract(self, downloaded: DownloadedDocument) -> list[ExtractedPage]:
        pages = extract_pdf_pages(downloaded.path, downloaded.metadata.sha256)
        output = self.root / "data/extracted/text/sertp/2026/pages.jsonl"
        write_pages_jsonl(pages, output)
        downloaded.metadata.page_count = len(pages)
        return pages

    def parse(
        self,
        pages: list[ExtractedPage],
        document: SourceDocument,
    ) -> ParseResult:
        return Sertp2026Parser().parse(pages, document)

    def export(
        self,
        observations: list[ProjectObservation],
        document: SourceDocument,
        quality_report: DataQualityReport,
    ) -> None:
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.root))
        staged_processed = staging / "data/processed"
        published_manifest = self.root / "data/processed/source_manifest.json"
        previous_manifest = None
        if published_manifest.exists():
            previous_manifest = json.loads(published_manifest.read_text(encoding="utf-8"))
        try:
            export_observations_json(
                observations, staged_processed / "sertp_2026_projects.json"
            )
            export_observations_csv(
                observations, staged_processed / "sertp_2026_projects.csv"
            )
            export_project_schema(staging / "schemas/project_observation.schema.json")
            write_source_manifest(
                document,
                staged_processed / "source_manifest.json",
                previous=previous_manifest,
            )
            write_review_queue(observations, staged_processed / "review_queue.csv")
            write_data_quality(quality_report, staged_processed / "data_quality.json")
            write_output_bundle_manifest(staging)
            validate_output_bundle(staging)
            fsync_output_bundle(staging)
            promote_output_bundle(staging, self.root)
        except Exception as error:
            self._write_failure_diagnostic(error)
            raise
        finally:
            shutil.rmtree(staging, ignore_errors=True)

    def _write_failure_diagnostic(self, error: Exception) -> None:
        path = self.root / "data/failed_runs/latest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"error_type": type(error).__name__, "message": str(error)},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def run(
        self,
        *,
        source: str,
        year: int,
        force: bool = False,
    ) -> PipelineRunResult:
        try:
            previous_report = self._load_previous_quality_report()
            candidate = self.discover(source=source, year=year)
            downloaded = self.download(candidate, force=force)
            pages = self.extract(downloaded)
            parsed = self.parse(pages, downloaded.metadata)
            observations = [validate_observation(item) for item in parsed.observations]
            observations = flag_duplicate_candidates(observations)
            quality_report = build_quality_report(observations, diagnostics=parsed.diagnostics)
            minimum_records = 10 if len(pages) >= 50 else 1
            enforce_run_gates(
                quality_report,
                previous_report=previous_report,
                minimum_records=minimum_records,
            )
            self.export(observations, downloaded.metadata, quality_report)
            return PipelineRunResult(
                document=downloaded.metadata,
                pages=pages,
                observations=observations,
                diagnostics=parsed.diagnostics,
                quality_report=quality_report,
            )
        except Exception as error:
            self._write_failure_diagnostic(error)
            raise

    def _load_previous_quality_report(self) -> DataQualityReport | None:
        path = self.root / "data/processed/data_quality.json"
        if not path.exists():
            return None
        return DataQualityReport.model_validate_json(path.read_text(encoding="utf-8"))
