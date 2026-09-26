"""Source-document contracts."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SourceDocumentCandidate(BaseModel):
    """A ranked public-document link discovered on an approved page."""

    model_config = ConfigDict(extra="forbid")

    title: str
    url: str
    discovery_url: str
    planning_year: int
    score: int
    reasons: list[str] = Field(default_factory=list)


class SourceDocument(BaseModel):
    """Verified identity and acquisition metadata for a source PDF."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    source: str
    planning_year: int
    document_type: str
    title: str
    discovery_url: str
    source_url: str
    final_url: str
    acquired_at: datetime
    http_status: int = 200
    content_type: str
    content_length: int
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    page_count: int | None = None
    etag: str | None = None
    last_modified: str | None = None
    public_access: bool
    access_notes: list[str] = Field(default_factory=list)
    pipeline_version: str

