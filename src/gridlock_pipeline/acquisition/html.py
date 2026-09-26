"""Small, policy-checked HTML cache used by current-project web sources."""

import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from gridlock_pipeline.acquisition.downloader import (
    DownloadError,
    _follow_public_redirects,
    _read_limited_content,
)
from gridlock_pipeline.acquisition.hashing import sha256_bytes
from gridlock_pipeline.acquisition.safety import SourcePolicy, validate_public_url


@dataclass(frozen=True)
class DownloadedHtmlPage:
    url: str
    content: bytes
    sha256: str
    cache_hit: bool

    @property
    def text(self) -> str:
        return self.content.decode("utf-8", errors="replace")


def _filename(url: str) -> str:
    name = Path(urlsplit(url).path).stem or "index"
    return f"{name}.html"


def download_html_page(
    url: str,
    session,
    cache_root: Path,
    policy: SourcePolicy,
    *,
    force: bool = False,
    sleeper: Callable[[float], None] = time.sleep,
) -> DownloadedHtmlPage:
    """Download one approved HTML page, or return its byte-identical cache entry."""

    requested_url = validate_public_url(url, policy)
    path = cache_root / "html" / "georgia_power" / "current" / _filename(requested_url)
    if path.exists() and not force:
        content = path.read_bytes()
        return DownloadedHtmlPage(
            url=requested_url,
            content=content,
            sha256=sha256_bytes(content),
            cache_hit=True,
        )

    response, final_url, _ = _follow_public_redirects(
        session, requested_url, policy, sleeper
    )
    raw_content_type = response.headers.get("Content-Type", "")
    content_type = raw_content_type.split(";", 1)[0].strip().casefold()
    if content_type not in {"text/html", "application/xhtml+xml"}:
        raise DownloadError(f"incompatible content type: {raw_content_type!r}")
    content = _read_limited_content(response, policy.max_content_bytes)
    if b"<html" not in content[:4096].lower():
        raise DownloadError("downloaded content failed HTML validation")

    path.parent.mkdir(parents=True, exist_ok=True)
    staged = path.with_suffix(".html.part")
    staged.write_bytes(content)
    staged.replace(path)
    return DownloadedHtmlPage(
        url=final_url,
        content=content,
        sha256=sha256_bytes(content),
        cache_hit=False,
    )
