# SERTP 2026 Public-Data Pipeline Design

Date: 2026-09-26

## 1. Objective

Phase 1 delivers a production-quality, auditable Python pipeline that converts the official public **2026 SERTP Preliminary Expansion Plan Report (Non-CEII)** into validated project observations with complete document and page provenance.

The completed pipeline must run as:

```bash
python -m gridlock_pipeline run --source sertp --year 2026
```

It must discover the report from SERTP's public site, safely acquire and cache it, extract page-preserving text, parse 2026 project records, validate and normalize those records, and export CSV, JSON, provenance, quality, and human-review artifacts.

Accuracy and traceability take precedence over record count. Ambiguous information remains unknown or enters a review queue.

## 2. Phase 1 Scope

Phase 1 includes only the 2026 SERTP report and the shared interfaces needed for later source-specific adapters.

It includes:

- repository and package architecture;
- configuration-driven source discovery and URL policy;
- anonymous public-document acquisition;
- rate limiting, retry, timeout, redirect, MIME, size, and PDF-magic validation;
- immutable cache behavior, SHA-256 hashing, and source-change history;
- page-preserving text extraction;
- a strict `sertp_2026` state-machine parser;
- raw, normalized, and derived fields kept separately;
- balancing-authority and owner-prefix preservation;
- deterministic normalization and conservative classification;
- record validation, confidence labels, warnings, review queues, and quality gates;
- CSV/JSON exports and a source manifest;
- fixtures, unit tests, integration tests, golden records, and deterministic-rerun checks;
- manual verification support for a representative sample of at least ten records.

Phase 1 explicitly excludes:

- all 2009-2025 downloads and parsers;
- assumptions about future parser-family year ranges;
- canonical-project matching and schedule-drift analysis;
- DESC/SCRTP ingestion;
- geocoding or fabricated geometry;
- Georgia Power attribution based solely on `SOUTHERN`;
- dashboard changes, ML/LLM parsing, and automatic scheduled refreshes.

The repository may carry a source inventory noting future public years, but it must not acquire or parse them in Phase 1.

## 3. Repository Structure

```text
gridlock-data-pipeline/
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── config/
│   ├── sources.yaml
│   └── normalization.yaml
├── src/gridlock_pipeline/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── pipeline.py
│   ├── discovery/{__init__.py,base.py,sertp.py}
│   ├── acquisition/{__init__.py,downloader.py,safety.py,hashing.py}
│   ├── extraction/{__init__.py,pdf_text.py,page_model.py}
│   ├── parsers/{__init__.py,base.py,sertp_2026.py}
│   ├── normalization/{__init__.py,names.py,voltage.py,dates.py,project_type.py,organizations.py,locations.py,lengths.py}
│   ├── validation/{__init__.py,schema.py,invariants.py,quality.py}
│   ├── export/{__init__.py,csv_export.py,json_export.py,manifest.py}
│   └── models/{__init__.py,source_document.py,project_observation.py}
├── scripts/inspect_pdf.py
├── data/
│   ├── raw/{html,pdf}/
│   ├── extracted/text/
│   ├── intermediate/projects/
│   └── processed/
├── tests/
│   ├── fixtures/sertp/
│   ├── golden/sertp_2026/
│   ├── test_discovery.py
│   ├── test_downloader.py
│   ├── test_extraction.py
│   ├── test_sertp_2026_parser.py
│   ├── test_normalization.py
│   ├── test_validation.py
│   ├── test_exports.py
│   └── test_pipeline.py
└── .github/workflows/test.yml
```

Raw PDFs and transient HTML are cached locally and ignored by Git. Small manually selected text fixtures, golden records, manifests, and processed outputs may be committed when they are necessary for reproducibility and review.

## 4. Architectural Boundaries

### 4.1 Discovery

`DocumentDiscovery` is a protocol returning ranked `SourceDocumentCandidate` objects. `SertpDiscovery` implements it for the configured public Reference Library and Archive pages, although Phase 1 selection is restricted to planning year 2026.

Candidate scoring considers year, expansion-plan title variants, explicit Non-CEII wording, PDF destination, discovery context, and domain policy. Multiple top candidates within a configured ambiguity threshold cause a review failure rather than silent selection.

### 4.2 Acquisition

`DocumentDownloader` accepts a validated candidate and returns a `DownloadedDocument`. URL safety is enforced both before the request and after every redirect. Only HTTP(S) URLs on `southeasternrtp.com` or `www.southeasternrtp.com` are allowed. Credential-bearing URLs and paths containing blocked authentication or Secure Area fragments are rejected.

The downloader uses a descriptive user agent, one-request-per-second pacing, bounded retries with exponential backoff, explicit timeouts, a maximum content-size limit, content-type checks, and `%PDF` magic-byte validation.

Cached source bytes are immutable by hash. A changed source is archived by hash and produces manifest history containing the prior and new digest. A failed refresh never overwrites a known-good processed dataset.

### 4.3 Extraction

`PdfExtractor` consumes a verified local PDF and returns ordered `ExtractedPage` values. Every page stores the zero-based physical index, detected printed page number when available, complete raw text, and source SHA-256. The extractor writes deterministic JSON Lines without flattening page boundaries.

Nearly empty or unexpectedly unreadable pages generate warnings. OCR is not part of Phase 1.

### 4.4 Parsing

`ProjectParser` is a protocol whose input is ordered extracted pages and source metadata and whose output is `ProjectObservation` values plus parser diagnostics.

`Sertp2026Parser` is a source/version-specific state machine. It recognizes balancing-authority headers and the `In-Service Year`, `Project Name`, `Description`, and `Supporting Statement` transitions while tolerating line wrapping and page boundaries. Exact recurring headers and footers are removed only from a cleaned parsing stream; raw page text remains unchanged.

The parser must not classify the public report as restricted merely because its repeated template header contains `CEII`. Acquisition context determines public eligibility.

### 4.5 Normalization

Normalization functions are pure and deterministic. They never replace raw source fields.

- Names: Unicode normalization, whitespace collapse, dash standardization, and case-folded search form while preserving identifiers such as `#2`, colors, phases, and circuit numbers.
- Organizations: conservative balancing-authority normalization and extraction of raw leading prefixes such as `SOCO:` and `GTC:`. No automatic Georgia Power attribution.
- Voltage: capture supported `kV` expressions and all levels, avoiding conductor and temperature values.
- Project type: rule-based classification with explicit method and confidence; uncertain cases remain `unknown`.
- Locations: optional candidate station/end-point names only when syntax is sufficiently clear; no geocoding.
- Length: preserve raw phrases and individual numeric components; do not sum ambiguous components.

### 4.6 Validation and Quality Gates

Validation retains questionable records and attaches explicit warning codes. A record missing a project name is invalid; missing descriptions or supporting statements normally generate warnings. Confidence is `HIGH`, `MEDIUM`, or `LOW`, derived from explainable rules.

Run-level gates fail before processed outputs are replaced when any of these occur:

- no or implausibly few records from the full report;
- no balancing authorities;
- excessive required-field failure;
- HTML or malformed content presented as a PDF;
- a source-hash change paired with major quality deterioration;
- export counts inconsistent with validated in-memory observations.

Thresholds are configuration values and are initially established only after the first manually inspected 2026 run. The first run reports metrics without pretending an unverified record count is authoritative.

### 4.7 Export

Exports are written to a staging directory, validated, and atomically promoted only after all run-level gates pass.

Required outputs:

- `data/processed/sertp_2026_projects.csv`
- `data/processed/sertp_2026_projects.json`
- `data/processed/review_queue.csv`
- `data/processed/data_quality.json`
- `data/processed/source_manifest.json`

JSON uses stable key ordering and excludes volatile run timestamps from content whose determinism is asserted. Volatile acquisition timestamps remain in the source manifest but do not cause project-observation output drift.

## 5. Core Data Contracts

### 5.1 SourceDocument

Stores document identity, discovery provenance, source and final URLs, planning year, document type, timestamps, HTTP metadata, content length/type, SHA-256, page count, public-access classification, access notes, and pipeline version.

### 5.2 ExtractedPage

Stores `pdf_page_index`, optional printed page number, raw page text, and source SHA-256.

### 5.3 ProjectObservation

Stores:

- stable observation ID, source, planning year, and document ID;
- raw and normalized balancing authority;
- raw owner prefix;
- raw and normalized project name;
- in-service year;
- raw description and supporting statement;
- raw and derived voltage fields;
- deterministic project type, confidence, and method;
- conservative location mentions and candidate endpoints;
- raw and derived length fields;
- PDF and printed page ranges;
- source URL, title, and hash;
- parser and pipeline versions;
- extraction confidence, validation status, and warning notes;
- explicitly null latitude, longitude, and geometry.

IDs are derived from stable source facts rather than record order alone so reruns do not renumber unchanged observations.

## 6. Command-Line Interface

The package exposes:

```bash
python -m gridlock_pipeline discover --source sertp --year 2026
python -m gridlock_pipeline download --source sertp --year 2026
python -m gridlock_pipeline extract --source sertp --year 2026
python -m gridlock_pipeline parse --source sertp --year 2026
python -m gridlock_pipeline validate --source sertp --year 2026
python -m gridlock_pipeline export --source sertp --year 2026
python -m gridlock_pipeline run --source sertp --year 2026
```

All commands support `--dry-run`, `--force`, and `--verbose` where meaningful. Unsupported years fail explicitly in Phase 1 with a message that only 2026 is implemented.

## 7. Testing Strategy

Development follows test-driven implementation.

- Discovery tests use local HTML fixtures and cover title variations, candidate ranking, ambiguity, external domains, and blocked Secure Area links.
- Acquisition tests use fake HTTP responses and cover redirects, retries, cache hits, size limits, MIME validation, PDF magic bytes, hash changes, and HTML error pages.
- Extraction tests use small PDF fixtures and assert page order, printed-page detection, raw text, and source hashes.
- Parser tests cover all required field, wrapping, page-boundary, authority-transition, CEII-header, missing-field, prefix, typo, duplicate-looking, and unusual-name cases.
- Normalization tests cover dash variants, `#2`, `Phase 2`, multi-voltage values, conductor values, temperatures, lengths, and conservative endpoints.
- Validation tests cover required fields, warnings, confidence, duplicate flags, unusual years, and run-level gates.
- Export tests assert schema, provenance, stable ordering, atomic promotion, and cross-format record-count parity.
- Integration tests run the pipeline against a pinned cached 2026 source or an explicitly enabled network fixture.
- Determinism tests run the pipeline twice on identical cached input and compare processed observation outputs byte-for-byte.

Golden fixtures contain at least two SOUTHERN records, one SOCO-prefixed record, one GTC-prefixed record, one Duke record, one TVA record, a transformer, a line rebuild, and a multi-voltage record. At least ten real records are manually checked against their exact PDF pages before Phase 1 is declared complete.

## 8. Operational and Security Rules

- No authentication or Secure Area access.
- No traversal to unapproved domains after redirects.
- No secrets in configuration or fixtures.
- No automated weekly refresh in Phase 1.
- CI installs the package and runs lint/type checks chosen in the implementation plan plus the full test suite.
- Network integration is opt-in; ordinary tests remain deterministic and offline.
- Structured logs report document discovery, cache behavior, extraction counts, balancing-authority transitions, record counts, warnings, and failures without emitting sensitive data.

## 9. Manual Verification Deliverable

Phase 1 stops after producing a verification packet containing:

- source title, final URL, SHA-256, and page count;
- total observations and counts by balancing authority;
- confidence and warning distributions;
- review-queue count;
- at least ten selected observations with source-page references and raw fields;
- known parser limitations;
- rerun and test commands;
- exact output paths.

No 2025 work begins until the human reviewer accepts the 2026 sample.

## 10. Acceptance Criteria

Phase 1 is complete only when every item in the user-approved scope is implemented and verified, the full offline suite passes, the live 2026 pipeline succeeds against the official public document, processed outputs survive a deterministic rerun, and the manual verification packet is ready for review.

Future year support must implement new adapters behind the shared discovery, acquisition, extraction, parser, validation, and export contracts. Parser-family boundaries will be proposed only after representative source documents are extracted and compared; no year family is assumed in this design.
