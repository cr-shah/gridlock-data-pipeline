"""Discovery of the official public SERTP 2026 report."""

import re
import time
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from gridlock_pipeline.acquisition.safety import (
    SourcePolicy,
    UnsafeUrlError,
    validate_public_url,
)
from gridlock_pipeline.models import SourceDocumentCandidate


class UnsupportedPlanningYear(ValueError):
    """Raised when a parser year is outside the implemented Phase 1 scope."""


class AmbiguousDocumentError(RuntimeError):
    """Raised when discovery cannot identify one defensible source document."""


class DiscoveryError(RuntimeError):
    """Raised when a discovery page cannot be safely accepted."""


def _search_text(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.casefold()).strip()


def _ensure_supported(year: int, policy: SourcePolicy) -> None:
    if year not in policy.implemented_years:
        implemented = ", ".join(str(item) for item in policy.implemented_years)
        raise UnsupportedPlanningYear(f"Phase 1 implements only {implemented}; received {year}")


def rank_sertp_candidates(
    html: str,
    discovery_url: str,
    year: int,
    policy: SourcePolicy,
) -> list[SourceDocumentCandidate]:
    _ensure_supported(year, policy)
    validate_public_url(discovery_url, policy)
    candidates: list[SourceDocumentCandidate] = []
    soup = BeautifulSoup(html, "html.parser")
    for anchor in soup.find_all("a", href=True):
        title = " ".join(anchor.get_text(" ", strip=True).split())
        absolute_url = urljoin(discovery_url, str(anchor["href"]))
        try:
            safe_url = validate_public_url(absolute_url, policy)
        except UnsafeUrlError:
            continue
        searchable = _search_text(f"{title} {safe_url}")
        if str(year) not in searchable:
            continue
        score = 50
        reasons = ["planning-year"]
        if "preliminary expansion plan" in searchable:
            score += 30
            reasons.append("preliminary-expansion-plan")
        if "non ceii" in searchable:
            score += 20
            reasons.append("non-ceii")
        if urlsplit_path(safe_url).casefold().endswith(".pdf"):
            score += 10
            reasons.append("pdf")
        candidates.append(
            SourceDocumentCandidate(
                title=title,
                url=safe_url,
                discovery_url=discovery_url,
                planning_year=year,
                score=score,
                reasons=reasons,
            )
        )
    return sorted(candidates, key=lambda item: (-item.score, item.url, item.title))


def urlsplit_path(url: str) -> str:
    from urllib.parse import urlsplit

    return urlsplit(url).path


def _read_bounded_html(response, maximum: int) -> str:
    declared = response.headers.get("Content-Length")
    try:
        declared_length = int(declared) if declared else None
    except (TypeError, ValueError):
        declared_length = None
    if declared_length is not None and declared_length > maximum:
        raise DiscoveryError("discovery page size exceeds configured limit")

    iterator = getattr(response, "iter_content", None)
    if iterator is None:
        text = response.text
        if len(text.encode("utf-8")) > maximum:
            raise DiscoveryError("discovery page size exceeds configured limit")
        return text

    content = bytearray()
    for chunk in iterator(chunk_size=64 * 1024):
        if not chunk:
            continue
        content.extend(chunk)
        if len(content) > maximum:
            raise DiscoveryError("discovery page size exceeds configured limit")
    encoding = getattr(response, "encoding", None) or "utf-8"
    return bytes(content).decode(encoding, errors="replace")


def _fetch_public_discovery_html(
    session, requested_url: str, policy: SourcePolicy
) -> tuple[str, str]:
    current = validate_public_url(requested_url, policy)
    for redirect_count in range(6):
        response = session.get(
            current,
            timeout=policy.timeout_seconds,
            headers={"User-Agent": "GridlockDataPipeline/0.1 (+public research)"},
            allow_redirects=False,
            stream=True,
        )
        if response.status_code in {301, 302, 303, 307, 308}:
            location = response.headers.get("Location")
            if not location:
                raise DiscoveryError("discovery redirect omitted Location header")
            next_url = validate_public_url(urljoin(current, location), policy)
            close = getattr(response, "close", None)
            if close is not None:
                close()
            current = next_url
            if redirect_count < 5 and policy.request_interval_seconds:
                time.sleep(policy.request_interval_seconds)
            continue
        response.raise_for_status()
        final_url = validate_public_url(response.url or current, policy)
        return _read_bounded_html(response, policy.max_content_bytes), final_url
    raise DiscoveryError("discovery page exceeded redirect limit")


def discover_sertp_document(
    session,
    year: int,
    policy: SourcePolicy,
) -> SourceDocumentCandidate:
    _ensure_supported(year, policy)
    ranked: list[SourceDocumentCandidate] = []
    for discovery_url in policy.discovery_pages:
        html, final_discovery_url = _fetch_public_discovery_html(session, discovery_url, policy)
        ranked.extend(rank_sertp_candidates(html, final_discovery_url, year, policy))
    ranked.sort(key=lambda item: (-item.score, item.url, item.title))
    if not ranked:
        raise AmbiguousDocumentError(f"no public SERTP document candidate found for {year}")
    top_score = ranked[0].score
    tied = [item for item in ranked if top_score - item.score <= policy.ambiguity_margin]
    if len(tied) != 1:
        raise AmbiguousDocumentError(f"{len(tied)} document candidates tie for {year}")
    return ranked[0]
