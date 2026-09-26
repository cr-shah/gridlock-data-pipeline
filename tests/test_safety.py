from pathlib import Path

import pytest

from gridlock_pipeline.acquisition.safety import (
    UnsafeUrlError,
    load_source_policy,
    validate_public_url,
)


@pytest.fixture
def policy():
    return load_source_policy(Path("config/sources.yaml"), "sertp")


@pytest.mark.parametrize(
    "url",
    [
        "ftp://www.southeasternrtp.com/report.pdf",
        "https://evil.example/report.pdf",
        "https://user:password@www.southeasternrtp.com/report.pdf",
        "https://www.southeasternrtp.com/secure_area/report.pdf",
        "https://www.southeasternrtp.com/path/login/report.pdf",
        "https://www.southeasternrtp.com/path/AUTH/report.pdf",
    ],
)
def test_validate_public_url_rejects_unsafe_locations(policy, url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url(url, policy)


def test_validate_public_url_accepts_exact_approved_host(policy) -> None:
    url = "https://www.southeasternrtp.com/docs/general/2026/report.pdf"

    assert validate_public_url(url, policy) == url


def test_redirect_chain_rejects_allowed_host_secure_area_destination(policy) -> None:
    redirect_chain = [
        "https://www.southeasternrtp.com/public/report.pdf",
        "https://www.southeasternrtp.com/secure_area/report.pdf",
    ]

    validate_public_url(redirect_chain[0], policy)
    with pytest.raises(UnsafeUrlError, match="blocked"):
        validate_public_url(redirect_chain[1], policy)


def test_lookalike_subdomain_is_not_allowed(policy) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_url("https://www.southeasternrtp.com.evil.example/report.pdf", policy)

