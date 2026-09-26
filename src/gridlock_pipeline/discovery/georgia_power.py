"""Discovery of current Georgia Power projects from the official listing only."""

from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from gridlock_pipeline.acquisition.safety import SourcePolicy, validate_public_url
from gridlock_pipeline.models import SourceDocumentCandidate

LISTING_URL = (
    "https://www.georgiapower.com/about/grid-reliability/grid-improvements/"
    "grid-projects/transmission-projects.html"
)
PROJECT_PATH_PREFIX = (
    "/about/grid-reliability/grid-improvements/grid-projects/transmission-projects/"
)


@dataclass(frozen=True)
class GeorgiaPowerProjectLink:
    name: str
    county_region: str
    project_type: str
    url: str


def discover_georgia_power_document(
    year: int, policy: SourcePolicy
) -> SourceDocumentCandidate:
    if year not in policy.implemented_years:
        raise ValueError(
            f"Georgia Power current projects supports only {policy.implemented_years}"
        )
    url = validate_public_url(LISTING_URL, policy)
    return SourceDocumentCandidate(
        title="Georgia Power Current Transmission Projects",
        url=url,
        discovery_url=url,
        planning_year=year,
        score=100,
        reasons=["official-current-project-listing"],
    )


def parse_georgia_power_listing(
    html: str, listing_url: str, policy: SourcePolicy
) -> list[GeorgiaPowerProjectLink]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("#current-projects-table")
    if table is None:
        raise ValueError("Georgia Power current-project table was not found")
    projects: list[GeorgiaPowerProjectLink] = []
    for row in table.select("tbody tr"):
        cells = row.find_all("td", recursive=False)
        link = cells[0].find("a", href=True) if len(cells) == 3 else None
        if link is None:
            continue
        url = validate_public_url(urljoin(listing_url, link["href"]), policy)
        if not urlsplit(url).path.startswith(PROJECT_PATH_PREFIX):
            raise ValueError(f"listing linked an out-of-scope project page: {url}")
        projects.append(
            GeorgiaPowerProjectLink(
                name=link.get_text(" ", strip=True),
                county_region=cells[1].get_text(" ", strip=True),
                project_type=cells[2].get_text(" ", strip=True),
                url=url,
            )
        )
    if not projects:
        raise ValueError("Georgia Power current-project table contained no projects")
    return projects
