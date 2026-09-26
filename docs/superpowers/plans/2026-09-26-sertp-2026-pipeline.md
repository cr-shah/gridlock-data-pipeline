# SERTP 2026 Public-Data Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a deterministic, auditable Python pipeline that discovers, downloads, extracts, parses, validates, and exports project observations from the official public 2026 SERTP Preliminary Expansion Plan Report.

**Architecture:** A vertical slice first proves the real 2026 path from public-page discovery through JSON/CSV output. Source discovery, acquisition, page extraction, source-version parsing, normalization, validation, and export communicate through typed Pydantic contracts; later tasks harden the verified slice without adding historical years.

**Tech Stack:** Python 3.11+, Pydantic 2, requests, BeautifulSoup 4, PyMuPDF, PyYAML, pytest, Ruff, standard-library CSV/JSON/hashlib/logging.

**Spec:** `docs/superpowers/specs/2026-09-26-sertp-2026-pipeline-design.md`

## Global Constraints

- Phase 1 supports planning year 2026 only; every other year fails explicitly.
- Only anonymous public HTTP(S) resources on `southeasternrtp.com` and `www.southeasternrtp.com` are eligible.
- Never access, authenticate to, or crawl SERTP Secure Area resources.
- The repeated `CEII` template header inside the publicly linked Non-CEII PDF does not make the document restricted.
- Preserve raw source fields, `raw_record_text`, source/page provenance, extraction engine/version, parser version, and pipeline version.
- Derived fields must not overwrite source facts and must carry machine-readable `field_provenance`.
- Preserve `SOUTHERN`, `SOCO:`, and `GTC:` independently; never infer Georgia Power from balancing authority alone.
- Never fabricate latitude, longitude, geometry, utility ownership, completion status, costs, or dates.
- Ordinary tests are offline and deterministic; real-network execution is explicit.
- Raw PDFs and transient HTML remain Git-ignored; small fixtures, schemas, reports, and processed review artifacts may be committed.
- No 2025 work starts before the human reviewer accepts the Phase 1 verification packet.

## Review Focus

- A public URL redirects through an allowed host and then to a blocked Secure Area path: reject before reading or caching the response body.
- A PDF extraction upgrade changes whitespace or line joining without changing the source SHA: exported extraction provenance must expose the engine-version change and golden tests must fail deliberately.
- Two legitimate records have the same normalized name but different circuit, phase, voltage, or description: retain both and flag only defensible duplicate candidates.
- A project record crosses a page whose repeated header contains `CEII`: retain one continuous `raw_record_text` block and the full page range without rejecting the source.
- A run fails after writing staged outputs or sees a quality collapse: preserve the last known-good processed files and emit a failed-run report.

## File Map

- `pyproject.toml`: package metadata, dependency ranges, pytest and Ruff configuration.
- `config/sources.yaml`: approved domains, discovery pages, keywords, blocked fragments, network limits.
- `config/normalization.yaml`: balancing-authority aliases and deterministic-rule configuration.
- `src/gridlock_pipeline/models/*.py`: stable Pydantic contracts and enums.
- `src/gridlock_pipeline/discovery/*.py`: public-page parsing and candidate ranking.
- `src/gridlock_pipeline/acquisition/*.py`: URL policy, HTTP download/cache, hashing, source manifest history.
- `src/gridlock_pipeline/extraction/*.py`: page-preserving PyMuPDF extraction.
- `src/gridlock_pipeline/parsers/*.py`: parser protocol and strict 2026 state machine.
- `src/gridlock_pipeline/normalization/*.py`: pure derived-field rules and provenance.
- `src/gridlock_pipeline/validation/*.py`: record validation, confidence, duplicate warnings, run gates, quality report.
- `src/gridlock_pipeline/export/*.py`: deterministic CSV/JSON/schema/manifest outputs and atomic promotion.
- `src/gridlock_pipeline/pipeline.py`: stage orchestration and last-known-good protection.
- `src/gridlock_pipeline/cli.py`, `__main__.py`: command-line surface.
- `scripts/inspect_pdf.py`: inspect page ranges from extracted JSONL.
- `tests/fixtures/sertp/`: synthetic and manually selected real-text fixtures.
- `tests/golden/sertp_2026/`: manually verified expected records.
- `schemas/project_observation.schema.json`: generated ProjectObservation JSON Schema.
- `.github/workflows/test.yml`: offline lint and test workflow.

---

### Task 1: Package Skeleton and Typed Contracts

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `.env.example`
- Create: `config/sources.yaml`
- Create: `config/normalization.yaml`
- Create: `src/gridlock_pipeline/__init__.py`
- Create: `src/gridlock_pipeline/models/__init__.py`
- Create: `src/gridlock_pipeline/models/source_document.py`
- Create: `src/gridlock_pipeline/models/project_observation.py`
- Create: `src/gridlock_pipeline/extraction/page_model.py`
- Create: `tests/test_models.py`

**Interfaces:**
- Produces: `SourceDocumentCandidate`, `SourceDocument`, `ExtractedPage`, `FieldProvenance`, `ProjectObservation`, `ValidationStatus`, `ConfidenceLevel`.
- Produces: `ProjectObservation.model_json_schema()` as the authoritative future adapter contract.

- [ ] **Step 1: Write failing contract tests**

Add tests asserting that `ProjectObservation` requires source identity, raw record text, page range, extraction provenance, version provenance, null geometry, and a provenance entry for every populated derived field. Assert that invalid page ranges and derived fields without provenance raise `ValidationError`.

- [ ] **Step 2: Run the contract tests and verify RED**

Run: `python -m pytest tests/test_models.py -q`

Expected: FAIL during import because the package models do not exist.

- [ ] **Step 3: Add packaging, configuration, enums, and Pydantic models**

Implement:

```python
class FieldProvenance(BaseModel):
    origin: Literal["normalized", "derived_from_source", "deterministic_rule"]
    source_fields: list[str]
    rule_id: str | None = None
    notes: str | None = None

class ExtractedPage(BaseModel):
    pdf_page_index: int
    printed_page_number: int | None
    text: str
    source_sha256: str
    extraction_engine: str
    extraction_engine_version: str
```

Define `ProjectObservation` fields exactly from the spec, including `raw_record_text`, `field_provenance`, explicitly null geometry fields, and an after-validation rule that checks provenance for populated derived fields.

- [ ] **Step 4: Run contract tests and lint**

Run: `python -m pytest tests/test_models.py -q && python -m ruff check src tests`

Expected: PASS; Ruff reports no errors.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml .gitignore .env.example config src/gridlock_pipeline tests/test_models.py
git commit -m "feat: define pipeline contracts"
```

### Task 2: Public Discovery and URL Safety

**Files:**
- Create: `src/gridlock_pipeline/discovery/__init__.py`
- Create: `src/gridlock_pipeline/discovery/base.py`
- Create: `src/gridlock_pipeline/discovery/sertp.py`
- Create: `src/gridlock_pipeline/acquisition/__init__.py`
- Create: `src/gridlock_pipeline/acquisition/safety.py`
- Create: `tests/fixtures/sertp/reference_library_2026.html`
- Create: `tests/test_discovery.py`
- Create: `tests/test_safety.py`

**Interfaces:**
- Consumes: `SourceDocumentCandidate` from Task 1 and `config/sources.yaml`.
- Produces: `validate_public_url(url: str, policy: SourcePolicy) -> str`.
- Produces: `rank_sertp_candidates(html: str, discovery_url: str, year: int, policy: SourcePolicy) -> list[SourceDocumentCandidate]`.
- Produces: `discover_sertp_document(session: requests.Session, year: int, policy: SourcePolicy) -> SourceDocumentCandidate`.

- [ ] **Step 1: Write failing safety and discovery tests**

Cover the official 2026 title, title/URL punctuation variants, relative URLs, one unambiguous winner, tied top candidates, unsupported 2025, external hosts, embedded credentials, non-HTTP schemes, login/auth fragments, and `/secure_area...` paths. Include the Review Focus redirect-path case at the policy level.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_safety.py tests/test_discovery.py -q`

Expected: FAIL because discovery and safety functions are undefined.

- [ ] **Step 3: Implement policy loading, URL validation, and deterministic candidate ranking**

Define `SourcePolicy` in `acquisition/safety.py`; normalize hostnames without weakening the exact allowlist. Score year, expansion-plan phrases, Non-CEII wording, `.pdf` destination, and public discovery context. Raise `UnsupportedPlanningYear` for non-2026 and `AmbiguousDocumentError` for tied candidates inside the configured margin.

- [ ] **Step 4: Run discovery and safety tests**

Run: `python -m pytest tests/test_safety.py tests/test_discovery.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config src/gridlock_pipeline/discovery src/gridlock_pipeline/acquisition tests/fixtures tests/test_discovery.py tests/test_safety.py
git commit -m "feat: discover public SERTP 2026 report"
```

### Task 3: Minimal Verified Download, Hash, and Cache

**Files:**
- Create: `src/gridlock_pipeline/acquisition/hashing.py`
- Create: `src/gridlock_pipeline/acquisition/downloader.py`
- Create: `src/gridlock_pipeline/export/__init__.py`
- Create: `src/gridlock_pipeline/export/manifest.py`
- Create: `tests/test_downloader.py`
- Create: `tests/test_manifest.py`

**Interfaces:**
- Consumes: `SourceDocumentCandidate`, `SourcePolicy`.
- Produces: `sha256_bytes(content: bytes) -> str` and `sha256_file(path: Path) -> str`.
- Produces: `DownloadedDocument(path: Path, metadata: SourceDocument, cache_hit: bool)`.
- Produces: `download_document(candidate, session, cache_root, policy, *, force=False, clock=...) -> DownloadedDocument`.
- Produces: `write_source_manifest(document: SourceDocument, path: Path, previous: dict | None = None) -> None`.

- [ ] **Step 1: Write failing minimal-download tests**

Use fake session/response objects. Assert successful PDF download, `%PDF` enforcement, compatible MIME enforcement, SHA-256 correctness, deterministic cache path, cache hit without a second request, and initial manifest content.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_downloader.py tests/test_manifest.py -q`

Expected: FAIL because downloader/hash/manifest modules do not exist.

- [ ] **Step 3: Implement the smallest safe downloader needed for the vertical slice**

Validate the requested and final URL, successful status, MIME, configured content-length ceiling, and `%PDF` bytes. Store the verified file at `data/raw/pdf/sertp/2026/preliminary_expansion_plan.pdf`; do not implement hash-history archives or atomic processed promotion yet.

- [ ] **Step 4: Run minimal-download tests**

Run: `python -m pytest tests/test_downloader.py tests/test_manifest.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gridlock_pipeline/acquisition src/gridlock_pipeline/export tests/test_downloader.py tests/test_manifest.py
git commit -m "feat: download and hash public PDF"
```

### Task 4: Page-Preserving Extraction and Real-Text Inspection

**Files:**
- Create: `src/gridlock_pipeline/extraction/__init__.py`
- Create: `src/gridlock_pipeline/extraction/pdf_text.py`
- Create: `scripts/inspect_pdf.py`
- Create: `tests/fixtures/sertp/two_page_projects.pdf`
- Create: `tests/test_extraction.py`

**Interfaces:**
- Consumes: verified PDF path and source SHA-256 from Task 3.
- Produces: `extract_pdf_pages(pdf_path: Path, source_sha256: str) -> list[ExtractedPage]`.
- Produces: `write_pages_jsonl(pages: Sequence[ExtractedPage], path: Path) -> None`.
- Produces: CLI inspection of an inclusive page range from JSONL.

- [ ] **Step 1: Write failing extraction tests**

Assert two ordered physical pages, printed-page detection, complete page text, identical source SHA on every page, and runtime PyMuPDF name/version. Assert an empty-text page produces an extraction warning rather than OCR.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_extraction.py -q`

Expected: FAIL because extraction functions do not exist.

- [ ] **Step 3: Implement deterministic PyMuPDF extraction and inspection script**

Use `fitz.open`, `page.get_text("text", sort=True)`, and `importlib.metadata.version("PyMuPDF")`. Write one stable JSON object per line.

- [ ] **Step 4: Run extraction tests**

Run: `python -m pytest tests/test_extraction.py -q`

Expected: PASS.

- [ ] **Step 5: Run discovery, download, and extraction against the real 2026 public document**

Run the temporary Python entry points or focused module functions to create:

- `data/raw/pdf/sertp/2026/preliminary_expansion_plan.pdf`
- `data/extracted/text/sertp/2026/pages.jsonl`

Expected: one publicly discovered PDF, `%PDF` verified, SHA-256 recorded, and 115 extracted pages unless the official document has been revised.

- [ ] **Step 6: Inspect and record at least ten real project pages before parser work**

Run: `python scripts/inspect_pdf.py --input data/extracted/text/sertp/2026/pages.jsonl --pages 1:12` and additional ranges covering SOUTHERN, TVA, BA transitions, page-crossing records, SOCO/GTC prefixes, multi-voltage, and repeated CEII headers.

Create `tests/fixtures/sertp/2026_inspection_notes.md` with the inspected ranges, observed labels, header/footer forms, and boundary cases. Do not include invented expectations.

- [ ] **Step 7: Commit code, small fixture, and inspection notes**

```bash
git add src/gridlock_pipeline/extraction scripts tests/test_extraction.py tests/fixtures/sertp/2026_inspection_notes.md
git commit -m "feat: extract PDF pages with provenance"
```

### Task 5: Strict 2026 Parser and Core Normalization

**Files:**
- Create: `src/gridlock_pipeline/parsers/__init__.py`
- Create: `src/gridlock_pipeline/parsers/base.py`
- Create: `src/gridlock_pipeline/parsers/sertp_2026.py`
- Create: `src/gridlock_pipeline/normalization/__init__.py`
- Create: `src/gridlock_pipeline/normalization/names.py`
- Create: `src/gridlock_pipeline/normalization/organizations.py`
- Create: `src/gridlock_pipeline/normalization/voltage.py`
- Create: `src/gridlock_pipeline/normalization/project_type.py`
- Create: `src/gridlock_pipeline/normalization/locations.py`
- Create: `src/gridlock_pipeline/normalization/lengths.py`
- Create: `src/gridlock_pipeline/normalization/dates.py`
- Create: `tests/fixtures/sertp/2026_real_pages.jsonl`
- Create: `tests/test_sertp_2026_parser.py`
- Create: `tests/test_normalization.py`

**Interfaces:**
- Consumes: ordered `ExtractedPage` values and `SourceDocument`.
- Produces: `ProjectParser.parse(pages, document) -> ParseResult`.
- Produces: `Sertp2026Parser.parse(...) -> ParseResult` with observations and diagnostics.
- Produces pure normalizers returning `(value, FieldProvenance | None)` or typed derived-result objects.

- [ ] **Step 1: Build a minimal real-text fixture from inspected pages**

Copy only the exact extracted text needed for at least ten observed records and relevant headers into `2026_real_pages.jsonl`, retaining source page indexes. Include a cross-page record, BA transition, CEII header, SOCO prefix, GTC prefix, multi-voltage project, `#2`, temperature, and conductor number.

- [ ] **Step 2: Write failing parser and normalization tests**

Assert exact raw names, years, descriptions, supporting statements, complete `raw_record_text`, page ranges, BA values, owner prefixes, extraction provenance, and stable IDs. Assert `230/115 kV` yields `[230, 115]`, while `795 ACSR` and `100°C` do not. Assert normalized names preserve `#2` and `Phase 2`.

- [ ] **Step 3: Run tests and verify RED**

Run: `python -m pytest tests/test_sertp_2026_parser.py tests/test_normalization.py -q`

Expected: FAIL because parser/normalizers do not exist.

- [ ] **Step 4: Implement exact header cleanup and the 2026 state machine**

Implement states for BA, year, name, description, and supporting statement. Track every cleaned line's physical and printed page. Finalize only on the next record/BA/end-of-document. Preserve the entire cleaned record block before field interpretation. Do not reject `CEII` text inside this already-approved public document.

- [ ] **Step 5: Implement minimal pure normalizers and provenance**

Add `normalize_project_name`, `normalize_balancing_authority`, `extract_owner_prefix`, `extract_voltage`, `classify_project_type`, `extract_candidate_locations`, `extract_lengths`, and `parse_in_service_year`, each with versioned rule IDs. Date normalization may return only a defensible planning year present in the source record; it must not infer a more precise date.

- [ ] **Step 6: Run parser and normalization tests**

Run: `python -m pytest tests/test_sertp_2026_parser.py tests/test_normalization.py -q`

Expected: PASS for the ten-plus real records and synthetic edge cases.

- [ ] **Step 7: Run the parser against all real extracted pages and inspect counts**

Expected: substantially more than ten observations, multiple balancing authorities, and no catastrophic boundary collapse. Record actual counts rather than adding hard-coded expectations.

- [ ] **Step 8: Commit**

```bash
git add src/gridlock_pipeline/parsers src/gridlock_pipeline/normalization tests/fixtures/sertp/2026_real_pages.jsonl tests/test_sertp_2026_parser.py tests/test_normalization.py
git commit -m "feat: parse SERTP 2026 project records"
```

### Task 6: Vertical-Slice Exports and CLI

**Files:**
- Create: `src/gridlock_pipeline/export/csv_export.py`
- Create: `src/gridlock_pipeline/export/json_export.py`
- Create: `src/gridlock_pipeline/export/schema_export.py`
- Create: `src/gridlock_pipeline/pipeline.py`
- Create: `src/gridlock_pipeline/cli.py`
- Create: `src/gridlock_pipeline/__main__.py`
- Create: `tests/test_exports.py`
- Create: `tests/test_cli.py`
- Create: `tests/test_vertical_slice.py`

**Interfaces:**
- Consumes: Tasks 1-5 discovery, download, extraction, parse functions.
- Produces: `export_observations_json`, `export_observations_csv`, and `export_project_schema`.
- Produces: `PipelineRunner.discover/download/extract/parse/export/run` for source `sertp`, year `2026`.
- Produces: the command surface in the spec with `--dry-run`, `--force`, and `--verbose`.

- [ ] **Step 1: Write failing export, CLI, and vertical-slice tests**

Assert JSON/CSV record parity, stable observation ordering, raw/extraction/field provenance, valid JSON Schema, dry-run non-mutation, explicit rejection of 2025, and a cached-input vertical slice from source metadata through exported observations.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_exports.py tests/test_cli.py tests/test_vertical_slice.py -q`

Expected: FAIL because exporters, runner, and CLI do not exist.

- [ ] **Step 3: Implement deterministic exporters and minimal runner/CLI**

Use stable observation ordering and JSON key order. Flatten list/dict values as JSON strings in CSV without discarding information. Export the Pydantic schema to `schemas/project_observation.schema.json`.

- [ ] **Step 4: Run vertical-slice tests**

Run: `python -m pytest tests/test_exports.py tests/test_cli.py tests/test_vertical_slice.py -q`

Expected: PASS.

- [ ] **Step 5: Run the real vertical slice**

Run: `python -m gridlock_pipeline run --source sertp --year 2026 --verbose`

Expected: discovery selects the public Non-CEII report, cached/verified PDF is extracted, observations are parsed, and preliminary JSON/CSV/schema/manifest files are created. This is the early proof point before secondary hardening.

- [ ] **Step 6: Commit**

```bash
git add src/gridlock_pipeline/export src/gridlock_pipeline/pipeline.py src/gridlock_pipeline/cli.py src/gridlock_pipeline/__main__.py schemas tests/test_exports.py tests/test_cli.py tests/test_vertical_slice.py
git commit -m "feat: complete SERTP 2026 vertical slice"
```

### Task 7: Acquisition and Manifest Hardening

**Files:**
- Modify: `src/gridlock_pipeline/acquisition/downloader.py`
- Modify: `src/gridlock_pipeline/acquisition/safety.py`
- Modify: `src/gridlock_pipeline/export/manifest.py`
- Modify: `tests/test_downloader.py`
- Modify: `tests/test_manifest.py`

**Interfaces:**
- Preserves Task 3 signatures.
- Adds retry/backoff, pacing, streamed size enforcement, redirect-chain validation, hash-history archives, response metadata, and explicit refresh status.

- [ ] **Step 1: Extend tests to RED for hardening cases**

Cover timeouts and bounded retries, retryable versus terminal statuses, `Retry-After`/backoff behavior, missing or false content length, streamed size overflow, allowed-host redirect then Secure Area redirect, HTML error body with HTTP 200, changed bytes at the same URL, prior-hash retention, and no overwrite of cached known-good bytes.

- [ ] **Step 2: Run hardened acquisition tests and verify RED**

Run: `python -m pytest tests/test_downloader.py tests/test_manifest.py -q`

Expected: new tests FAIL against the minimal Task 3 implementation.

- [ ] **Step 3: Implement hardening without changing caller contracts**

Archive changed copies by SHA under the year cache, record HTTP status/final URL/ETag/Last-Modified/content metadata, and keep manifest history. Validate every redirect hop and the final URL before accepting bytes.

- [ ] **Step 4: Run acquisition tests**

Run: `python -m pytest tests/test_safety.py tests/test_downloader.py tests/test_manifest.py -q`

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/gridlock_pipeline/acquisition src/gridlock_pipeline/export/manifest.py tests/test_downloader.py tests/test_manifest.py
git commit -m "feat: harden public document acquisition"
```

### Task 8: Full Validation, Confidence, Review Queue, and Quality Report

**Files:**
- Create: `src/gridlock_pipeline/validation/__init__.py`
- Create: `src/gridlock_pipeline/validation/schema.py`
- Create: `src/gridlock_pipeline/validation/invariants.py`
- Create: `src/gridlock_pipeline/validation/quality.py`
- Modify: `src/gridlock_pipeline/pipeline.py`
- Create: `tests/test_validation.py`
- Create: `tests/test_quality.py`

**Interfaces:**
- Consumes: `Sequence[ProjectObservation]`, `SourceDocument`, parser diagnostics.
- Produces: `validate_observation(observation) -> ProjectObservation` with status/notes/confidence.
- Produces: `flag_duplicate_candidates(observations) -> list[ProjectObservation]` without merging.
- Produces: `build_review_queue(observations) -> list[ReviewQueueEntry]`.
- Produces: `build_quality_report(...) -> DataQualityReport`.
- Produces: `enforce_run_gates(report, previous_report=None) -> None`.

- [ ] **Step 1: Write failing validation and quality tests**

Cover missing required fields, missing optional fields, unusual years, unknown BA/prefix, suspicious names, ambiguous endpoints, confidence mapping, defensible duplicates, same-name-but-different-circuit non-merge behavior, BA/warning distributions, and zero/few-record catastrophic gates.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_validation.py tests/test_quality.py -q`

Expected: FAIL because validation and quality modules do not exist.

- [ ] **Step 3: Implement explainable record validation and run gates**

Warnings are stable codes; validation never silently deletes observations. Duplicate fingerprints include BA, normalized name, year, voltage, owner prefix, and description fingerprint. First-run gates use conservative structural checks rather than an invented exact record count.

- [ ] **Step 4: Implement review queue and quality report integration**

Write `review_queue.csv` and `data_quality.json` fields exactly from the spec; propagate warnings and parser diagnostics.

- [ ] **Step 5: Run validation and quality tests**

Run: `python -m pytest tests/test_validation.py tests/test_quality.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/gridlock_pipeline/validation src/gridlock_pipeline/pipeline.py tests/test_validation.py tests/test_quality.py
git commit -m "feat: validate observations and report quality"
```

### Task 9: Golden Records and Full Parser Edge-Case Matrix

**Files:**
- Create: `tests/golden/sertp_2026/observations.json`
- Create: `tests/golden/sertp_2026/verification.md`
- Modify: `tests/test_sertp_2026_parser.py`
- Modify: `tests/test_normalization.py`
- Create: `tests/test_golden_sertp_2026.py`

**Interfaces:**
- Consumes: real cached extraction and parser output.
- Produces: at least ten manually checked immutable expected records and a checklist linking each to source pages.

- [ ] **Step 1: Select and manually verify real records without creating the golden data file yet**

Check at least three SOUTHERN/SOCO, two SOUTHERN/GTC, one Duke, one TVA, one transformer, one line rebuild, one multi-voltage, and one multiline/page-boundary record against the official PDF. Record exact raw fields and page references in `verification.md`, but leave `observations.json` absent for the initial RED run.

- [ ] **Step 2: Write golden and missing edge-case tests first**

Add exact golden assertions that require `tests/golden/sertp_2026/observations.json`, plus fixtures for several projects on one page, empty/missing fields, official typo, malformed whitespace, en/em dash, ID-only title, duplicate-looking records, `#2`, Phase 2, CEII public header, and a record whose supporting statement crosses a page.

- [ ] **Step 3: Run focused tests and verify RED**

Run: `python -m pytest tests/test_golden_sertp_2026.py tests/test_sertp_2026_parser.py tests/test_normalization.py -q`

Expected: FAIL because the deliberately absent golden data file is required. Additional failures may expose parser or normalizer gaps.

- [ ] **Step 4: Create the golden data from the manually verified expectations and make the smallest parser/normalizer fixes**

Write `observations.json` from the values checked in Step 1, never by blindly copying current parser output. Preserve public-source raw text exactly; fixes affect parsing boundaries or derived fields only.

- [ ] **Step 5: Run golden/parser/normalization tests**

Run: `python -m pytest tests/test_golden_sertp_2026.py tests/test_sertp_2026_parser.py tests/test_normalization.py -q`

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add tests/golden tests/test_golden_sertp_2026.py tests/test_sertp_2026_parser.py tests/test_normalization.py src/gridlock_pipeline/parsers src/gridlock_pipeline/normalization
git commit -m "test: freeze verified SERTP 2026 records"
```

### Task 10: Atomic Promotion, Determinism, Failure Preservation, and CI

**Files:**
- Modify: `src/gridlock_pipeline/export/csv_export.py`
- Modify: `src/gridlock_pipeline/export/json_export.py`
- Modify: `src/gridlock_pipeline/export/schema_export.py`
- Modify: `src/gridlock_pipeline/pipeline.py`
- Create: `tests/test_atomic_exports.py`
- Create: `tests/test_determinism.py`
- Create: `tests/test_failure_preservation.py`
- Create: `.github/workflows/test.yml`

**Interfaces:**
- Preserves all public interfaces from Tasks 1-8.
- Adds staged output bundles and `promote_output_bundle(staging_dir: Path, processed_dir: Path) -> None`.

- [ ] **Step 1: Write failing atomicity, determinism, and preservation tests**

Assert a mid-export exception leaves known-good files byte-identical; quality-gate failure does not promote staged outputs; identical cached input produces byte-identical observation JSON/CSV/schema; changing only acquisition time does not perturb observations; changing extraction version does perturb explicit provenance/golden expectations.

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest tests/test_atomic_exports.py tests/test_determinism.py tests/test_failure_preservation.py -q`

Expected: FAIL because staging/promotion is not implemented.

- [ ] **Step 3: Implement staging and atomic per-file promotion after gates pass**

Write the complete bundle under a temporary sibling directory, fsync/close files, validate cross-file counts and schema, then replace processed targets. On failure, retain the last known-good bundle and write diagnostics outside it.

- [ ] **Step 4: Add CI**

The workflow installs the package with dev dependencies and runs `python -m ruff check src tests scripts` and `python -m pytest -q`. It performs no network refresh and makes no commits.

- [ ] **Step 5: Run full offline verification**

Run: `python -m ruff check src tests scripts && python -m pytest -q`

Expected: PASS with zero failures.

- [ ] **Step 6: Commit**

```bash
git add src/gridlock_pipeline/export src/gridlock_pipeline/pipeline.py tests/test_atomic_exports.py tests/test_determinism.py tests/test_failure_preservation.py .github/workflows/test.yml
git commit -m "feat: protect deterministic processed outputs"
```

### Task 11: Documentation, Live Run, and Verification Packet

**Files:**
- Create: `README.md`
- Create: `data/processed/.gitkeep` if no processed artifact is committed before the live run
- Create: `docs/verification/sertp-2026-phase-1.md`
- Modify: generated `schemas/project_observation.schema.json`
- Generate: `data/processed/sertp_2026_projects.csv`
- Generate: `data/processed/sertp_2026_projects.json`
- Generate: `data/processed/review_queue.csv`
- Generate: `data/processed/data_quality.json`
- Generate: `data/processed/source_manifest.json`
- Test: full suite plus live pipeline and deterministic rerun

**Interfaces:**
- Consumes: the complete Phase 1 pipeline.
- Produces: human-reviewable Phase 1 outputs and the stop-before-2025 verification packet.

- [ ] **Step 1: Write README acceptance checks**

Add a small test or documentation assertion that README contains SERTP context, public-only constraint, explicit Secure Area exclusion, install commands, all CLI commands, outputs, provenance, limitations, quality method, and the 2026-only boundary.

- [ ] **Step 2: Write README and rerun documentation checks**

Document exact setup and commands without claiming unverified accuracy.

- [ ] **Step 3: Run the complete live pipeline**

Run: `python -m gridlock_pipeline run --source sertp --year 2026 --force --verbose`

Expected: one public source document, verified PDF, page-preserving extraction, validated observations, schema-valid JSON/CSV, review queue, quality report, and source manifest.

- [ ] **Step 4: Run the unchanged-input determinism check**

Hash the processed observation JSON, CSV, schema, review queue, and quality report; rerun without `--force`; hash again.

Expected: deterministic artifacts are byte-identical. The source manifest may add only explicitly allowed refresh metadata and must retain the same source SHA.

- [ ] **Step 5: Produce the verification packet**

Write `docs/verification/sertp-2026-phase-1.md` with:

1. source title and final URL;
2. source SHA-256 and page count;
3. total observations and BA counts;
4. HIGH/MEDIUM/LOW counts;
5. review-queue and warning counts;
6. at least ten golden-record summaries with page references;
7. known limitations;
8. exact rerun/test commands;
9. exact generated paths;
10. an explicit statement that 2025 has not been started.

- [ ] **Step 6: Run final verification**

Run: `python -m ruff check src tests scripts && python -m pytest -q && python -m gridlock_pipeline validate --source sertp --year 2026`

Expected: all commands exit 0; validation reports concrete counts and no failed run-level gates.

- [ ] **Step 7: Commit**

```bash
git add README.md docs/verification schemas data/processed tests
git commit -m "docs: publish SERTP 2026 verification packet"
```

Stop. Present the verification packet and 2026 sample to the human reviewer. Do not discover, download, inspect, or parse 2025.
