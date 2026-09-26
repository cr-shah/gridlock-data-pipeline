"""Fixed official SCRTP/DESC current-project source."""

from gridlock_pipeline.acquisition.safety import SourcePolicy, validate_public_url
from gridlock_pipeline.models import SourceDocumentCandidate

DESC_CURRENT_PROJECTS_URL = (
    "https://www.scrtp.com/assets/pdfs/home/"
    "2026-2030-2million-and-above-project-descriptions.pdf"
)


def discover_scrtp_document(year: int, policy: SourcePolicy) -> SourceDocumentCandidate:
    if year not in policy.implemented_years:
        raise ValueError(f"SCRTP current projects supports only {policy.implemented_years}")
    url = validate_public_url(DESC_CURRENT_PROJECTS_URL, policy)
    return SourceDocumentCandidate(
        title="DESC 2026-2030 $2 Million and Above Project Descriptions",
        url=url,
        discovery_url=url,
        planning_year=year,
        score=100,
        reasons=["official-fixed-pdf", "current-planned-projects"],
    )
