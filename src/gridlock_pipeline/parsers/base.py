"""Parser interfaces and result contracts."""

from collections.abc import Sequence
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field

from gridlock_pipeline.extraction import ExtractedPage
from gridlock_pipeline.models import ProjectObservation, SourceDocument


class ParserDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    pdf_page_index: int | None = None


class ParseResult(BaseModel):
    observations: list[ProjectObservation]
    diagnostics: list[ParserDiagnostic] = Field(default_factory=list)


class ProjectParser(Protocol):
    def parse(
        self,
        pages: Sequence[ExtractedPage],
        document: SourceDocument,
    ) -> ParseResult: ...

