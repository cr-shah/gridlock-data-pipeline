# Gridlock public-data pipeline

This repository turns public non-CEII transmission sources into auditable project observations.
The automated regional-plan parser remains deliberately limited to the official **2026 SERTP
Preliminary Expansion Plan Report (Non-CEII)**. The verified product inventory also includes the
Georgia Power current-project page, the DESC current-project report, and a bounded 14-record
Georgia Power planning expansion curated from the final 2025 SERTP plan.

The pipeline uses anonymous public pages and PDFs only. It rejects credential-bearing URLs, authentication paths, and SERTP Secure Area links. It does not log in, bypass access controls, or acquire CEII material.

## Setup

Python 3.11 or newer is required.

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

## Run

The complete production path is:

```bash
python -m gridlock_pipeline run --source sertp --year 2026
```

Use `--force` to refresh the public PDF rather than reuse the verified cache, `--dry-run` to make no files or network requests, and `--verbose` for the CLI-compatible verbose mode. The package also exposes the following stage-oriented commands:

```bash
python -m gridlock_pipeline discover --source sertp --year 2026
python -m gridlock_pipeline download --source sertp --year 2026
python -m gridlock_pipeline extract --source sertp --year 2026
python -m gridlock_pipeline parse --source sertp --year 2026
python -m gridlock_pipeline validate --source sertp --year 2026
python -m gridlock_pipeline export --source sertp --year 2026
```

`discover` reports the selected candidate. In Phase 1, each other stage-oriented command executes the complete gated pipeline so it cannot publish a partial dataset. Any source/year other than `sertp`/`2026` fails explicitly.

## Outputs

Successful runs atomically publish:

- `data/processed/sertp_2026_projects.json` and `.csv`: the same observations in stable order;
- `data/processed/source_manifest.json`: discovery URL, final URL, HTTP metadata, SHA-256, page count, and source-change history;
- `data/processed/review_queue.csv`: records needing human attention;
- `data/processed/data_quality.json`: record, authority, confidence, validation, warning, and parser-diagnostic counts;
- `data/processed/bundle_manifest.json`: the atomic snapshot boundary and hashes for coherent multi-file reads;
- `schemas/project_observation.schema.json`: the Pydantic-generated machine-readable contract.

The challenge-ready verified inventory contains 54 DESC and 24 GPC records. The GPC total is the
10 projects on Georgia Power's public current-project page plus 14 separately source-scoped final
2025 SERTP planning records. Legacy `SAV` owner labels remain in provenance while their utility is
normalized to GPC; the MEAG line in the Goshen joint solution is not included.

Each observation preserves the complete cleaned `raw_record_text`, individual raw fields, separately normalized or derived values, source PDF SHA-256, zero-based PDF page range, printed-page range where detected, parser/pipeline versions, and PDF extraction engine/version. `field_provenance` identifies the raw source fields and deterministic rule behind derived values. `SOUTHERN` remains a balancing authority, while prefixes such as `SOCO:` and `GTC:` are preserved without attributing projects to Georgia Power. Multi-file consumers can use `read_verified_output_bundle` to accept a snapshot only when every file matches the manifest published last.

Before publication, records are validated, duplicate candidates are flagged, and run-level gates reject empty or implausibly small results, absent authorities, excessive invalid records, or cross-format count mismatches. Warnings lower confidence and send records to the review queue rather than silently inventing facts. Candidate exports are staged and cross-checked; an error leaves the last known-good bundle unchanged.

## Verification

Run the offline checks with:

```bash
python -m ruff check src tests scripts
python -m pytest -q
```

The live verification command is:

```bash
python -m gridlock_pipeline validate --source sertp --year 2026
```

See [`docs/verification/sertp-2026-phase-1.md`](docs/verification/sertp-2026-phase-1.md) for the source digest, observed counts, deterministic-output hashes, and ten manually checked records.

## Known limitations and scope boundary

- Phase 1 has no OCR; it relies on the PDF text layer.
- Location endpoints and project types are conservative deterministic interpretations, not official fields; ambiguous endpoints are review-queued.
- No geocoding, geometry fabrication, ML/LLM extraction, canonical-project matching, schedule-drift analysis, DESC/SCRTP ingestion, dashboard work, or automatic maintenance prediction is included.
- Historical SERTP documents do not have a generalized parser. The 14 final-2025 planning records
  are a bounded, page-cited curated layer; additional years require separate source review.
