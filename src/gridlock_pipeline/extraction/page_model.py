"""Page-preserving extraction contracts."""

from pydantic import BaseModel, ConfigDict, Field


class ExtractedPage(BaseModel):
    """Text from one physical PDF page with extraction provenance."""

    model_config = ConfigDict(extra="forbid")

    pdf_page_index: int = Field(ge=0)
    printed_page_number: int | None = None
    text: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    extraction_engine: str
    extraction_engine_version: str
    warnings: list[str] = Field(default_factory=list)

