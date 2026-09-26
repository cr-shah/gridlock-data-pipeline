"""Discovery interfaces."""

from typing import Protocol

from gridlock_pipeline.models import SourceDocumentCandidate


class DocumentDiscovery(Protocol):
    def discover(self, year: int) -> SourceDocumentCandidate: ...

