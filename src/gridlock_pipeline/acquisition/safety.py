"""Configuration-backed public URL policy."""

from pathlib import Path
from urllib.parse import unquote, urlsplit, urlunsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field


class UnsafeUrlError(ValueError):
    """Raised when a URL violates the public-source policy."""


class SourcePolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    implemented_years: list[int]
    discovery_pages: list[str]
    allowed_hosts: list[str]
    blocked_path_fragments: list[str]
    title_keywords: list[str]
    timeout_seconds: float = Field(gt=0)
    max_content_bytes: int = Field(gt=0)
    request_interval_seconds: float = Field(ge=0)
    ambiguity_margin: int = Field(ge=0)


def load_source_policy(path: Path, source: str) -> SourcePolicy:
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    if source not in config:
        raise KeyError(f"source policy not found: {source}")
    return SourcePolicy.model_validate(config[source])


def validate_public_url(url: str, policy: SourcePolicy) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() not in {"http", "https"}:
        raise UnsafeUrlError("only HTTP(S) public URLs are permitted")
    if parsed.username is not None or parsed.password is not None:
        raise UnsafeUrlError("credential-bearing URLs are not permitted")
    host = (parsed.hostname or "").rstrip(".").lower()
    allowed = {item.rstrip(".").lower() for item in policy.allowed_hosts}
    if host not in allowed:
        raise UnsafeUrlError(f"host is not approved: {host}")
    decoded_path = unquote(parsed.path).casefold()
    for fragment in policy.blocked_path_fragments:
        if fragment.casefold() in decoded_path:
            raise UnsafeUrlError(f"URL path contains blocked fragment: {fragment}")
    port = f":{parsed.port}" if parsed.port is not None else ""
    netloc = f"{host}{port}"
    return urlunsplit((parsed.scheme.lower(), netloc, parsed.path, parsed.query, ""))

