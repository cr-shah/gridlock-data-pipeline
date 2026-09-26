"""SERTP and SCRTP/DESC pipeline orchestration."""

import json
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import requests

from gridlock_pipeline.acquisition import SourcePolicy, load_source_policy
from gridlock_pipeline.acquisition.downloader import DownloadedDocument, download_document
from gridlock_pipeline.acquisition.html import download_html_page
from gridlock_pipeline.discovery import (
    discover_georgia_power_document,
    discover_scrtp_document,
    discover_sertp_document,
    parse_georgia_power_listing,
)
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
from gridlock_pipeline.export.gpc_planning_projects import write_gpc_records
from gridlock_pipeline.extraction import ExtractedPage, extract_pdf_pages, write_pages_jsonl
from gridlock_pipeline.models import ProjectObservation, SourceDocument, SourceDocumentCandidate
from gridlock_pipeline.parsers import (
    GeorgiaPowerParser,
    GeorgiaPowerProjectPage,
    ParseResult,
    ScrtpDescParser,
    Sertp2026Parser,
)
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
    pages: list[ExtractedPage | GeorgiaPowerProjectPage]
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
        self.config_path = config_path
        self.policy = policy

    def _policy(self, source: str) -> SourcePolicy:
        return self.policy or load_source_policy(self.config_path, source)

    @staticmethod
    def _check_scope(source: str, year: int) -> None:
        if source not in {"sertp", "scrtp", "georgia_power"}:
            raise ValueError(f"unsupported source: {source}")
        if year != 2026:
            raise ValueError(f"implemented sources support only 2026; received {year}")

    def discover(self, *, source: str, year: int) -> SourceDocumentCandidate:
        self._check_scope(source, year)
        policy = self._policy(source)
        if source == "georgia_power":
            return discover_georgia_power_document(year, policy)
        if source == "scrtp":
            return discover_scrtp_document(year, policy)
        return discover_sertp_document(self.session, year, policy)

    def download(
        self,
        candidate: SourceDocumentCandidate,
        *,
        force: bool = False,
        source: str = "sertp",
    ) -> DownloadedDocument:
        return download_document(
            candidate,
            self.session,
            self.root / "data/raw",
            self._policy(source),
            force=force,
            source=source,
        )

    def extract(self, downloaded: DownloadedDocument) -> list[ExtractedPage]:
        pages = extract_pdf_pages(downloaded.path, downloaded.metadata.sha256)
        output = (
            self.root
            / "data/extracted/text"
            / downloaded.metadata.source
            / str(downloaded.metadata.planning_year)
            / "pages.jsonl"
        )
        write_pages_jsonl(pages, output)
        downloaded.metadata.page_count = len(pages)
        return pages

    def parse(
        self,
        pages: list[ExtractedPage],
        document: SourceDocument,
    ) -> ParseResult:
        if document.source == "scrtp":
            return ScrtpDescParser().parse(pages, document)
        return Sertp2026Parser().parse(pages, document)

    def export(
        self,
        observations: list[ProjectObservation],
        document: SourceDocument,
        quality_report: DataQualityReport,
    ) -> None:
        staging = Path(tempfile.mkdtemp(prefix=".staging-", dir=self.root))
        staged_processed = staging / "data/processed"
        if document.source == "scrtp":
            try:
                export_observations_json(
                    observations, staged_processed / "desc_current_projects.json"
                )
                export_observations_csv(
                    observations, staged_processed / "desc_current_projects.csv"
                )
                fsync_output_bundle(staging)
                promote_output_bundle(staging, self.root)
            except Exception as error:
                self._write_failure_diagnostic(error)
                raise
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            return
        if document.source == "georgia_power":
            try:
                write_gpc_records(
                    observations,
                    staged_processed / "georgia_power_current_projects.json",
                    staged_processed / "georgia_power_current_projects.csv",
                )
                fsync_output_bundle(staging)
                promote_output_bundle(staging, self.root)
            except Exception as error:
                self._write_failure_diagnostic(error)
                raise
            finally:
                shutil.rmtree(staging, ignore_errors=True)
            return
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
            if source == "georgia_power":
                return self._run_georgia_power(year=year, force=force)
            previous_report = self._load_previous_quality_report() if source == "sertp" else None
            candidate = self.discover(source=source, year=year)
            downloaded = self.download(candidate, force=force, source=source)
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

    def _run_georgia_power(self, *, year: int, force: bool) -> PipelineRunResult:
        self._check_scope("georgia_power", year)
        policy = self._policy("georgia_power")
        candidate = self.discover(source="georgia_power", year=year)
        listing = download_html_page(
            candidate.url,
            self.session,
            self.root / "data/raw",
            policy,
            force=force,
        )
        projects = parse_georgia_power_listing(listing.text, listing.url, policy)
        pages: list[GeorgiaPowerProjectPage] = []
        for project in projects:
            downloaded = download_html_page(
                project.url,
                self.session,
                self.root / "data/raw",
                policy,
                force=force,
            )
            pages.append(
                GeorgiaPowerProjectPage(
                    project=project,
                    html=downloaded.text,
                    sha256=downloaded.sha256,
                )
            )
        document = SourceDocument(
            document_id="georgia-power-2026-current-transmission-projects",
            source="georgia_power",
            planning_year=year,
            document_type="current_projects_listing",
            title=candidate.title,
            discovery_url=candidate.discovery_url,
            source_url=candidate.url,
            final_url=listing.url,
            acquired_at=datetime.now(UTC),
            content_type="text/html",
            content_length=len(listing.content),
            sha256=listing.sha256,
            page_count=len(pages),
            public_access=True,
            access_notes=["official listing and only its linked project-detail pages"],
            refresh_status="cache_hit" if listing.cache_hit else "downloaded",
            redirect_chain=[candidate.url, listing.url]
            if candidate.url != listing.url
            else [listing.url],
            pipeline_version="0.1.0",
        )
        parsed = GeorgiaPowerParser().parse(pages, document)
        observations = [validate_observation(item) for item in parsed.observations]
        observations = flag_duplicate_candidates(observations)
        quality_report = build_quality_report(observations, diagnostics=parsed.diagnostics)
        enforce_run_gates(quality_report, previous_report=None, minimum_records=1)
        self.export(observations, document, quality_report)
        return PipelineRunResult(
            document=document,
            pages=pages,
            observations=observations,
            diagnostics=parsed.diagnostics,
            quality_report=quality_report,
        )

    def _load_previous_quality_report(self) -> DataQualityReport | None:
        path = self.root / "data/processed/data_quality.json"
        if not path.exists():
            return None
        return DataQualityReport.model_validate_json(path.read_text(encoding="utf-8"))
