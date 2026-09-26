"""Verified download and local cache for public PDFs."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline import __version__
from gridlock_pipeline.acquisition.hashing import sha256_bytes, sha256_file
from gridlock_pipeline.acquisition.safety import SourcePolicy, validate_public_url
from gridlock_pipeline.models import SourceDocument, SourceDocumentCandidate


class DownloadError(RuntimeError):
    """Raised when remote bytes cannot be accepted as the source PDF."""


@dataclass(frozen=True)
class DownloadedDocument:
    path: Path
    metadata: SourceDocument
    cache_hit: bool


def _cache_path(cache_root: Path, candidate: SourceDocumentCandidate) -> Path:
    return (
        cache_root
        / "pdf"
        / "sertp"
        / str(candidate.planning_year)
        / "preliminary_expansion_plan.pdf"
    )


def _metadata(
    candidate: SourceDocumentCandidate,
    *,
    final_url: str,
    acquired_at: datetime,
    content_type: str,
    content_length: int,
    digest: str,
    status: int = 200,
    etag: str | None = None,
    last_modified: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        document_id=f"sertp-{candidate.planning_year}-preliminary-non-ceii",
        source="sertp",
        planning_year=candidate.planning_year,
        document_type="preliminary_expansion_plan",
        title=candidate.title,
        discovery_url=candidate.discovery_url,
        source_url=candidate.url,
        final_url=final_url,
        acquired_at=acquired_at,
        http_status=status,
        content_type=content_type,
        content_length=content_length,
        sha256=digest,
        etag=etag,
        last_modified=last_modified,
        public_access=True,
        access_notes=["anonymous public download from approved host"],
        pipeline_version=__version__,
    )


def download_document(
    candidate: SourceDocumentCandidate,
    session,
    cache_root: Path,
    policy: SourcePolicy,
    *,
    force: bool = False,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> DownloadedDocument:
    requested_url = validate_public_url(candidate.url, policy)
    path = _cache_path(cache_root, candidate)
    if path.exists() and not force:
        content_length = path.stat().st_size
        metadata = _metadata(
            candidate,
            final_url=requested_url,
            acquired_at=clock(),
            content_type="application/pdf",
            content_length=content_length,
            digest=sha256_file(path),
        )
        return DownloadedDocument(path=path, metadata=metadata, cache_hit=True)

    response = session.get(
        requested_url,
        timeout=policy.timeout_seconds,
        headers={"User-Agent": "GridlockDataPipeline/0.1 (+public research)"},
    )
    try:
        response.raise_for_status()
    except Exception as exc:
        raise DownloadError(f"source request failed: {exc}") from exc
    final_url = validate_public_url(response.url, policy)
    raw_content_type = response.headers.get("Content-Type", "")
    content_type = raw_content_type.split(";", 1)[0].strip().casefold()
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise DownloadError(f"incompatible content type: {raw_content_type!r}")
    declared_length = response.headers.get("Content-Length")
    if declared_length and int(declared_length) > policy.max_content_bytes:
        raise DownloadError("declared source size exceeds configured limit")
    content = response.content
    if len(content) > policy.max_content_bytes:
        raise DownloadError("downloaded source size exceeds configured limit")
    if not content.startswith(b"%PDF"):
        raise DownloadError("downloaded content failed PDF magic-byte validation")

    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".pdf.part")
    staged.write_bytes(content)
    staged.replace(path)
    metadata = _metadata(
        candidate,
        final_url=final_url,
        acquired_at=clock(),
        content_type=content_type,
        content_length=len(content),
        digest=sha256_bytes(content),
        status=response.status_code,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
    )
    return DownloadedDocument(path=path, metadata=metadata, cache_hit=False)
