"""Deterministic page-preserving PDF text extraction."""

import json
import re
from collections.abc import Sequence
from importlib.metadata import version
from pathlib import Path

import pymupdf

from gridlock_pipeline.extraction.page_model import ExtractedPage

EXPECTED_EXTRACTION_ENGINE_VERSION = "1.28.2"


def _printed_page_number(text: str) -> int | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in reversed(lines[-5:]):
        footer = re.search(r"\bPage\s+(\d{1,4})\s+of\s+\d{1,4}\b", line, re.IGNORECASE)
        if footer:
            return int(footer.group(1))
        if re.fullmatch(r"\d{1,4}", line):
            return int(line)
    return None


def extract_pdf_pages(pdf_path: Path, source_sha256: str) -> list[ExtractedPage]:
    engine_version = version("PyMuPDF")
    if engine_version != EXPECTED_EXTRACTION_ENGINE_VERSION:
        raise RuntimeError(
            "unverified PyMuPDF version: "
            f"expected {EXPECTED_EXTRACTION_ENGINE_VERSION}, received {engine_version}"
        )
    extracted: list[ExtractedPage] = []
    with pymupdf.open(pdf_path) as document:
        for index, page in enumerate(document):
            text = page.get_text("text", sort=True)
            warnings = ["EMPTY_PAGE_TEXT"] if not text.strip() else []
            extracted.append(
                ExtractedPage(
                    pdf_page_index=index,
                    printed_page_number=_printed_page_number(text),
                    text=text,
                    source_sha256=source_sha256,
                    extraction_engine="PyMuPDF",
                    extraction_engine_version=engine_version,
                    warnings=warnings,
                )
            )
    return extracted


def write_pages_jsonl(pages: Sequence[ExtractedPage], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = [
        json.dumps(page.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
        for page in pages
    ]
    path.write_text("\n".join(serialized) + ("\n" if serialized else ""), encoding="utf-8")


def read_pages_jsonl(path: Path) -> list[ExtractedPage]:
    return [
        ExtractedPage.model_validate_json(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
