"""Verified download and local cache for public PDFs."""

import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urljoin

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
    refresh_status: str = "downloaded",
    redirect_chain: list[str] | None = None,
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
        refresh_status=refresh_status,
        redirect_chain=redirect_chain or [],
        pipeline_version=__version__,
    )


def _request_with_retries(
    session,
    url: str,
    policy: SourcePolicy,
    sleeper: Callable[[float], None],
):
    retryable = {429, 500, 502, 503, 504}
    last_error: Exception | None = None
    retry_already_paced = False
    for attempt in range(3):
        if attempt and not retry_already_paced:
            sleeper(max(policy.request_interval_seconds, float(2 ** (attempt - 1))))
        retry_already_paced = False
        try:
            response = session.get(
                url,
                timeout=policy.timeout_seconds,
                headers={"User-Agent": "GridlockDataPipeline/0.1 (+public research)"},
                allow_redirects=False,
                stream=True,
            )
        except Exception as exc:
            last_error = exc
            continue
        if response.status_code in retryable:
            if attempt == 2:
                raise DownloadError(
                    f"source request failed after retries: HTTP {response.status_code}"
                )
            retry_after = response.headers.get("Retry-After")
            if retry_after:
                try:
                    delay = float(retry_after)
                except ValueError:
                    delay = float(2**attempt)
                sleeper(max(policy.request_interval_seconds, delay))
                retry_already_paced = True
            continue
        if response.status_code >= 400:
            raise DownloadError(f"source request failed: HTTP {response.status_code}")
        return response
    raise DownloadError(f"source request failed after retries: {last_error}") from last_error


def _follow_public_redirects(
    session,
    requested_url: str,
    policy: SourcePolicy,
    sleeper: Callable[[float], None],
):
    current = requested_url
    chain = [requested_url]
    for redirect_count in range(6):
        response = _request_with_retries(session, current, policy, sleeper)
        if response.status_code not in {301, 302, 303, 307, 308}:
            final_url = validate_public_url(response.url or current, policy)
            if final_url != chain[-1]:
                chain.append(final_url)
            return response, final_url, chain
        location = response.headers.get("Location")
        if not location:
            raise DownloadError("redirect response omitted Location header")
        next_url = validate_public_url(urljoin(current, location), policy)
        chain.append(next_url)
        current = next_url
        if redirect_count < 5 and policy.request_interval_seconds:
            sleeper(policy.request_interval_seconds)
    raise DownloadError("source exceeded redirect limit")


def _read_limited_content(response, maximum: int) -> bytes:
    content = bytearray()
    iterator = getattr(response, "iter_content", None)
    chunks = iterator(chunk_size=64 * 1024) if iterator else (response.content,)
    for chunk in chunks:
        if not chunk:
            continue
        content.extend(chunk)
        if len(content) > maximum:
            raise DownloadError("downloaded source size exceeds configured limit")
    return bytes(content)


def download_document(
    candidate: SourceDocumentCandidate,
    session,
    cache_root: Path,
    policy: SourcePolicy,
    *,
    force: bool = False,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    sleeper: Callable[[float], None] = time.sleep,
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
            refresh_status="cache_hit",
            redirect_chain=[requested_url],
        )
        return DownloadedDocument(path=path, metadata=metadata, cache_hit=True)

    response, final_url, redirect_chain = _follow_public_redirects(
        session, requested_url, policy, sleeper
    )
    raw_content_type = response.headers.get("Content-Type", "")
    content_type = raw_content_type.split(";", 1)[0].strip().casefold()
    if content_type not in {"application/pdf", "application/octet-stream"}:
        raise DownloadError(f"incompatible content type: {raw_content_type!r}")
    declared_length = response.headers.get("Content-Length")
    try:
        parsed_length = int(declared_length) if declared_length else None
    except (TypeError, ValueError):
        parsed_length = None
    if parsed_length is not None and parsed_length > policy.max_content_bytes:
        raise DownloadError("declared source size exceeds configured limit")
    content = _read_limited_content(response, policy.max_content_bytes)
    if not content.startswith(b"%PDF"):
        raise DownloadError("downloaded content failed PDF magic-byte validation")

    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".pdf.part")
    staged.write_bytes(content)
    old_digest = sha256_file(path) if path.exists() else None
    new_digest = sha256_bytes(content)
    refresh_status = "downloaded"
    if old_digest == new_digest:
        refresh_status = "unchanged"
        staged.unlink()
    else:
        if old_digest is not None:
            archive = path.parent / "archive" / f"{old_digest}.pdf"
            archive.parent.mkdir(parents=True, exist_ok=True)
            if not archive.exists():
                shutil.copyfile(path, archive)
            refresh_status = "changed"
        staged.replace(path)
    metadata = _metadata(
        candidate,
        final_url=final_url,
        acquired_at=clock(),
        content_type=content_type,
        content_length=len(content),
        digest=new_digest,
        status=response.status_code,
        etag=response.headers.get("ETag"),
        last_modified=response.headers.get("Last-Modified"),
        refresh_status=refresh_status,
        redirect_chain=redirect_chain,
    )
    return DownloadedDocument(path=path, metadata=metadata, cache_hit=False)
