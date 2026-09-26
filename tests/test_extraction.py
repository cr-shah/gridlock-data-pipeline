import json
from importlib.metadata import version
from pathlib import Path

import pymupdf

from gridlock_pipeline.extraction.pdf_text import extract_pdf_pages, write_pages_jsonl

SOURCE_SHA = "c" * 64


def test_extract_pdf_pages_preserves_order_text_and_provenance() -> None:
    pages = extract_pdf_pages(
        Path("tests/fixtures/sertp/two_page_projects.pdf"),
        SOURCE_SHA,
    )

    assert [page.pdf_page_index for page in pages] == [0, 1]
    assert [page.printed_page_number for page in pages] == [1, 2]
    assert "SOCO: Alpha 230 kV Line" in pages[0].text
    assert "Addresses thermal loading." in pages[1].text
    assert {page.source_sha256 for page in pages} == {SOURCE_SHA}
    assert {page.extraction_engine for page in pages} == {"PyMuPDF"}
    assert {page.extraction_engine_version for page in pages} == {version("PyMuPDF")}


def test_empty_page_warns_without_ocr(tmp_path: Path) -> None:
    path = tmp_path / "empty.pdf"
    document = pymupdf.open()
    document.new_page()
    document.save(path)
    document.close()

    pages = extract_pdf_pages(path, SOURCE_SHA)

    assert pages[0].text == ""
    assert pages[0].warnings == ["EMPTY_PAGE_TEXT"]


def test_detects_report_footer_page_number(tmp_path: Path) -> None:
    path = tmp_path / "report-footer.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "Project Name: Example")
    page.insert_text((72, 760), "06/12/2026                    Page 7 of 115")
    document.save(path)
    document.close()

    pages = extract_pdf_pages(path, SOURCE_SHA)

    assert pages[0].printed_page_number == 7


def test_pages_jsonl_is_stable_and_one_page_per_line(tmp_path: Path) -> None:
    pages = extract_pdf_pages(
        Path("tests/fixtures/sertp/two_page_projects.pdf"),
        SOURCE_SHA,
    )
    output = tmp_path / "pages.jsonl"

    write_pages_jsonl(pages, output)
    first = output.read_bytes()
    write_pages_jsonl(pages, output)

    lines = output.read_text().splitlines()
    assert output.read_bytes() == first
    assert len(lines) == 2
    assert json.loads(lines[0])["pdf_page_index"] == 0
