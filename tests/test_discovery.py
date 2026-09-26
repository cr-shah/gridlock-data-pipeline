from pathlib import Path

import pytest

from gridlock_pipeline.acquisition.safety import load_source_policy
from gridlock_pipeline.discovery.sertp import (
    AmbiguousDocumentError,
    UnsupportedPlanningYear,
    discover_sertp_document,
    rank_sertp_candidates,
)

DISCOVERY_URL = "https://www.southeasternrtp.com/reference_library.cshtml"


class FakeResponse:
    def __init__(self, text: str, url: str = DISCOVERY_URL):
        self.text = text
        self.url = url
        self.status_code = 200

    def raise_for_status(self) -> None:
        return None


class FakeSession:
    def __init__(self, html: str):
        self.html = html
        self.requested: list[str] = []

    def get(self, url: str, **_kwargs) -> FakeResponse:
        self.requested.append(url)
        return FakeResponse(self.html)


@pytest.fixture
def policy():
    return load_source_policy(Path("config/sources.yaml"), "sertp")


def test_rank_candidates_selects_official_relative_non_ceii_link(policy) -> None:
    html = Path("tests/fixtures/sertp/reference_library_2026.html").read_text()

    candidates = rank_sertp_candidates(html, DISCOVERY_URL, 2026, policy)

    assert candidates[0].title == "2026 SERTP Preliminary Expansion Plan Report (Non-CEII)"
    assert candidates[0].url == (
        "https://www.southeasternrtp.com/docs/general/2026/"
        "2026_SERTP_Preliminary_Expansion_Plan_Report_(Non-CEII).pdf"
    )
    assert candidates[0].score > candidates[1].score


def test_title_and_url_punctuation_variants_are_ranked(policy) -> None:
    html = """
    <a href='/docs/2026/2026-sertp_preliminary-expansion-plan_non-ceii.PDF'>
      2026 - Preliminary Expansion Plan, Non CEII
    </a>
    """

    candidates = rank_sertp_candidates(html, DISCOVERY_URL, 2026, policy)

    assert len(candidates) == 1
    assert "non-ceii" in candidates[0].reasons


def test_discover_returns_unambiguous_top_candidate(policy) -> None:
    html = Path("tests/fixtures/sertp/reference_library_2026.html").read_text()
    session = FakeSession(html)

    candidate = discover_sertp_document(session, 2026, policy)

    assert candidate.planning_year == 2026
    assert "Non-CEII" in candidate.title
    assert session.requested == [DISCOVERY_URL]


def test_discover_rejects_tied_top_candidates(policy) -> None:
    html = """
    <a href='/a/2026_preliminary_expansion_plan_non-ceii.pdf'>
      2026 Preliminary Expansion Plan Non-CEII
    </a>
    <a href='/b/2026_preliminary_expansion_plan_non-ceii.pdf'>
      2026 Preliminary Expansion Plan Non-CEII
    </a>
    """

    with pytest.raises(AmbiguousDocumentError):
        discover_sertp_document(FakeSession(html), 2026, policy)


def test_phase_one_rejects_unsupported_year(policy) -> None:
    with pytest.raises(UnsupportedPlanningYear, match="only 2026"):
        rank_sertp_candidates("", DISCOVERY_URL, 2025, policy)


def test_external_candidate_is_ignored(policy) -> None:
    html = """
    <a href='https://evil.example/2026_preliminary_expansion_plan_non-ceii.pdf'>
      2026 Preliminary Expansion Plan Non-CEII
    </a>
    """

    assert rank_sertp_candidates(html, DISCOVERY_URL, 2026, policy) == []
