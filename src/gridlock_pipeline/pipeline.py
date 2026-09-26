"""Phase 1 SERTP 2026 pipeline orchestration."""

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
    write_source_manifest,
)
from gridlock_pipeline.extraction import ExtractedPage, extract_pdf_pages, write_pages_jsonl
from gridlock_pipeline.models import ProjectObservation, SourceDocument, SourceDocumentCandidate
from gridlock_pipeline.parsers import ParseResult, Sertp2026Parser


@dataclass(frozen=True)
class PipelineRunResult:
    document: SourceDocument
    pages: list[ExtractedPage]
    observations: list[ProjectObservation]
    diagnostics: list


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
    ) -> None:
        processed = self.root / "data/processed"
        export_observations_json(observations, processed / "sertp_2026_projects.json")
        export_observations_csv(observations, processed / "sertp_2026_projects.csv")
        export_project_schema(self.root / "schemas/project_observation.schema.json")
        write_source_manifest(document, processed / "source_manifest.json")

    def run(
        self,
        *,
        source: str,
        year: int,
        force: bool = False,
    ) -> PipelineRunResult:
        candidate = self.discover(source=source, year=year)
        downloaded = self.download(candidate, force=force)
        pages = self.extract(downloaded)
        parsed = self.parse(pages, downloaded.metadata)
        self.export(parsed.observations, downloaded.metadata)
        return PipelineRunResult(
            document=downloaded.metadata,
            pages=pages,
            observations=parsed.observations,
            diagnostics=parsed.diagnostics,
        )

