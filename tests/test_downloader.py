from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from gridlock_pipeline.acquisition.downloader import DownloadError, download_document
from gridlock_pipeline.acquisition.hashing import sha256_bytes, sha256_file
from gridlock_pipeline.acquisition.safety import load_source_policy
from gridlock_pipeline.models import SourceDocumentCandidate

PDF_BYTES = b"%PDF-1.7\nminimal test data\n%%EOF\n"
NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


class FakeResponse:
    def __init__(
        self,
        content: bytes = PDF_BYTES,
        content_type: str = "application/pdf",
        url: str = "https://www.southeasternrtp.com/report.pdf",
        status_code: int = 200,
    ):
        self.content = content
        self.url = url
        self.status_code = status_code
        self.headers = {
            "Content-Type": content_type,
            "Content-Length": str(len(content)),
        }

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = 0

    def get(self, *_args, **_kwargs) -> FakeResponse:
        self.calls += 1
        return self.response


@pytest.fixture
def policy():
    return load_source_policy(Path("config/sources.yaml"), "sertp")


@pytest.fixture
def candidate():
    return SourceDocumentCandidate(
        title="2026 SERTP Preliminary Expansion Plan Report (Non-CEII)",
        url="https://www.southeasternrtp.com/report.pdf",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        planning_year=2026,
        score=110,
        reasons=["planning-year", "preliminary-expansion-plan", "non-ceii", "pdf"],
    )


def test_hash_helpers_use_sha256(tmp_path: Path) -> None:
    path = tmp_path / "source.pdf"
    path.write_bytes(PDF_BYTES)
    expected = sha256(PDF_BYTES).hexdigest()

    assert sha256_bytes(PDF_BYTES) == expected
    assert sha256_file(path) == expected


def test_download_verifies_and_caches_pdf(tmp_path, candidate, policy) -> None:
    session = FakeSession(FakeResponse())

    result = download_document(
        candidate,
        session,
        tmp_path,
        policy,
        clock=lambda: NOW,
    )

    assert result.path == tmp_path / "pdf/sertp/2026/preliminary_expansion_plan.pdf"
    assert result.path.read_bytes() == PDF_BYTES
    assert result.metadata.sha256 == sha256(PDF_BYTES).hexdigest()
    assert result.metadata.final_url == candidate.url
    assert result.metadata.acquired_at == NOW
    assert result.cache_hit is False


def test_cache_hit_avoids_second_request(tmp_path, candidate, policy) -> None:
    session = FakeSession(FakeResponse())
    first = download_document(candidate, session, tmp_path, policy, clock=lambda: NOW)
    second = download_document(candidate, session, tmp_path, policy, clock=lambda: NOW)

    assert first.metadata.sha256 == second.metadata.sha256
    assert second.cache_hit is True
    assert session.calls == 1


@pytest.mark.parametrize(
    ("content", "content_type", "message"),
    [
        (b"<html>not a pdf</html>", "application/pdf", "magic"),
        (PDF_BYTES, "text/html", "content type"),
    ],
)
def test_download_rejects_non_pdf_content(
    tmp_path, candidate, policy, content: bytes, content_type: str, message: str
) -> None:
    session = FakeSession(FakeResponse(content=content, content_type=content_type))

    with pytest.raises(DownloadError, match=message):
        download_document(candidate, session, tmp_path, policy, clock=lambda: NOW)

    assert not (tmp_path / "pdf/sertp/2026/preliminary_expansion_plan.pdf").exists()


def test_download_rejects_declared_oversize(tmp_path, candidate, policy) -> None:
    response = FakeResponse()
    response.headers["Content-Length"] = str(policy.max_content_bytes + 1)

    with pytest.raises(DownloadError, match="size"):
        download_document(
            candidate,
            FakeSession(response),
            tmp_path,
            policy,
            clock=lambda: NOW,
        )

