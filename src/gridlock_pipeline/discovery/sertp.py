"""Discovery of the official public SERTP 2026 report."""

import re
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


def discover_sertp_document(
    session,
    year: int,
    policy: SourcePolicy,
) -> SourceDocumentCandidate:
    _ensure_supported(year, policy)
    ranked: list[SourceDocumentCandidate] = []
    for discovery_url in policy.discovery_pages:
        safe_discovery_url = validate_public_url(discovery_url, policy)
        response = session.get(safe_discovery_url, timeout=policy.timeout_seconds)
        response.raise_for_status()
        final_discovery_url = validate_public_url(response.url, policy)
        ranked.extend(rank_sertp_candidates(response.text, final_discovery_url, year, policy))
    ranked.sort(key=lambda item: (-item.score, item.url, item.title))
    if not ranked:
        raise AmbiguousDocumentError(f"no public SERTP document candidate found for {year}")
    top_score = ranked[0].score
    tied = [item for item in ranked if top_score - item.score <= policy.ambiguity_margin]
    if len(tied) != 1:
        raise AmbiguousDocumentError(f"{len(tied)} document candidates tie for {year}")
    return ranked[0]

