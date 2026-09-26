from datetime import UTC, datetime
from pathlib import Path

from gridlock_pipeline.extraction import ExtractedPage, read_pages_jsonl
from gridlock_pipeline.models import SourceDocument
from gridlock_pipeline.parsers.sertp_2026 import Sertp2026Parser

SHA = "d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c"


def source_document() -> SourceDocument:
    return SourceDocument(
        document_id="sertp-2026-preliminary-non-ceii",
        source="sertp",
        planning_year=2026,
        document_type="preliminary_expansion_plan",
        title="2026 SERTP Preliminary Expansion Plan Report (Non-CEII)",
        discovery_url="https://www.southeasternrtp.com/reference_library.cshtml",
        source_url=(
            "https://www.southeasternrtp.com/docs/general/2026/"
            "2026_SERTP_Preliminary_Expansion_Plan_Report_(Non-CEII).pdf"
        ),
        final_url=(
            "https://www.southeasternrtp.com/docs/general/2026/"
            "2026_SERTP_Preliminary_Expansion_Plan_Report_(Non-CEII).pdf"
        ),
        acquired_at=datetime(2026, 9, 26, tzinfo=UTC),
        content_type="application/pdf",
        content_length=1,
        sha256=SHA,
        page_count=115,
        public_access=True,
        pipeline_version="0.1.0",
    )


def test_parser_extracts_ten_plus_real_records_with_raw_and_derived_fields() -> None:
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))

    result = Sertp2026Parser().parse(pages, source_document())

    assert len(result.observations) == 22
    first = result.observations[0]
    assert first.project_name_raw == (
        "GAINESVILLE #2 - BULL SHOALS 161 KV TRANSMISSION LINE, REBUILD"
    )
    assert first.in_service_year == 2027
    assert first.balancing_authority_raw == "AECI"
    assert first.description_raw == (
        "Rebuild the 24.42 mile-long Gainesville #2 - Bull Shoals 161 kV transmission line "
        "795 ACSR at 100°C."
    )
    assert first.supporting_statement_raw == (
        "The Gainesville - Bull Shoals 161 kV transmission line overloads under contingency."
    )
    assert "Project Name:" in first.raw_record_text
    assert first.pdf_page_range == [0, 0]
    assert first.extraction_engine == "PyMuPDF"
    assert first.extraction_engine_version == "1.28.2"
    assert first.voltage_kv == [161.0]
    assert first.owner_prefix_raw is None
    assert first.latitude is None


def test_parser_preserves_authority_and_owner_prefix_independently() -> None:
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))

    observations = Sertp2026Parser().parse(pages, source_document()).observations
    gtc = next(item for item in observations if item.project_name_raw.startswith("GTC:"))
    soco = next(item for item in observations if item.project_name_raw.startswith("SOCO:"))
    tva = next(item for item in observations if item.balancing_authority_raw == "TVA")

    assert (gtc.balancing_authority_raw, gtc.owner_prefix_raw) == ("SOUTHERN", "GTC:")
    assert (soco.balancing_authority_raw, soco.owner_prefix_raw) == ("SOUTHERN", "SOCO:")
    assert (tva.balancing_authority_raw, tva.owner_prefix_raw) == ("TVA", None)
    assert "Georgia Power" not in soco.model_dump_json()


def test_parser_handles_multi_voltage_phase_and_non_voltage_numbers() -> None:
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))

    observations = Sertp2026Parser().parse(pages, source_document()).observations
    bank = next(item for item in observations if "SOUTH HAZLEHURST" in item.project_name_raw)
    phase = next(item for item in observations if "PHASE 2" in item.project_name_raw)

    assert bank.voltage_kv == [230.0, 115.0]
    assert 795.0 not in observations[0].voltage_kv
    assert 100.0 not in observations[0].voltage_kv
    assert phase.project_name_normalized.endswith("PHASE 2")


def test_parser_keeps_one_record_across_public_ceii_page_header() -> None:
    page_one = ExtractedPage(
        pdf_page_index=200,
        printed_page_number=201,
        text=(
            "SERTP TRANSMISSION PROJECTS\n"
            "SOUTHERNSERTP TRANSMISSIONPROJECTS(CEII)AuthorityArea\n"
            "Balancing Authority\n"
            "In-Service 2030\nYear:\n"
            "Project Name: SOCO: ALPHA - BETA 230 KV LINE REBUILD\n"
            "Description: Rebuild the Alpha - Beta line with"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )
    page_two = ExtractedPage(
        pdf_page_index=201,
        printed_page_number=202,
        text=(
            "SERTP TRANSMISSION PROJECTS\n"
            "SOUTHERNSERTP TRANSMISSIONPROJECTS(CEII)AuthorityArea\n"
            "Balancing Authority\n"
            "bundled conductor.\n"
            "Supporting The line overloads under contingency.\nStatement:\n"
            "06/12/2026 Page 202 of 202"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )

    observation = Sertp2026Parser().parse([page_one, page_two], source_document()).observations[0]

    assert observation.pdf_page_range == [200, 201]
    assert observation.description_raw == "Rebuild the Alpha - Beta line with bundled conductor."
    assert "CEII" not in observation.raw_record_text
    assert "The line overloads under contingency." in observation.raw_record_text


def test_observation_ids_are_stable_across_reruns() -> None:
    pages = read_pages_jsonl(Path("tests/fixtures/sertp/2026_real_pages.jsonl"))
    parser = Sertp2026Parser()

    first = parser.parse(pages, source_document())
    second = parser.parse(pages, source_document())

    assert [item.observation_id for item in first.observations] == [
        item.observation_id for item in second.observations
    ]
    assert len({item.observation_id for item in first.observations}) == 22


def test_supporting_statement_continues_across_page_header() -> None:
    first_page = ExtractedPage(
        pdf_page_index=300,
        printed_page_number=301,
        text=(
            "SERTP TRANSMISSION PROJECTS\nTVASERTP PROJECTS(CEII)AuthorityArea\n"
            "Balancing Authority\nIn-Service 2031\nYear:\nProject Name: TS25-422\n"
            "Description: Preserve an official typo equpiment.\n"
            "Supporting First half of the supporting statement"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )
    second_page = ExtractedPage(
        pdf_page_index=301,
        printed_page_number=302,
        text=(
            "SERTP TRANSMISSION PROJECTS\nTVASERTP PROJECTS(CEII)AuthorityArea\n"
            "Balancing Authority\nsecond half with   malformed whitespace.\n"
            "06/12/2026 Page 302 of 302"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )

    observation = Sertp2026Parser().parse(
        [first_page, second_page], source_document()
    ).observations[0]

    assert observation.supporting_statement_raw == (
        "First half of the supporting statement second half with malformed whitespace."
    )
    assert "equpiment" in observation.description_raw
    assert observation.pdf_page_range == [300, 301]


def test_missing_optional_fields_remain_null_instead_of_being_invented() -> None:
    page = ExtractedPage(
        pdf_page_index=400,
        printed_page_number=401,
        text=(
            "SERTP TRANSMISSION PROJECTS\nAECISERTP PROJECTS(CEII)AuthorityArea\n"
            "Balancing Authority\nIn-Service 2032\nYear:\nProject Name: ID-ONLY"
        ),
        source_sha256=SHA,
        extraction_engine="PyMuPDF",
        extraction_engine_version="1.28.2",
    )

    observation = Sertp2026Parser().parse([page], source_document()).observations[0]

    assert observation.description_raw is None
    assert observation.supporting_statement_raw is None
