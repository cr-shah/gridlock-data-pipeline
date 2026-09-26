# SERTP 2026 Phase 1 verification packet

Generated and checked on 2026-09-26. This packet reports the pipeline result; it does not claim that every derived interpretation has been manually certified.

## Official source

- Title: **2026 SERTP Preliminary Expansion Plan Report (Non-CEII)**
- Final public URL: <https://www.southeasternrtp.com/docs/general/2026/2026_SERTP_Preliminary_Expansion_Plan_Report_(Non-CEII).pdf>
- SHA-256: `d3785576bb2f558f558931b7fea22503deaafc6d1f81cec25b8d471deb32cb2c`
- PDF pages: **115**
- Extractor: **PyMuPDF 1.28.2**

The source was anonymously discovered from the configured public SERTP Reference Library. The downloader's allowlist and blocked-path rules exclude the Secure Area and authentication paths.

## Result and quality summary

The strict `sertp_2026` parser produced **426 observations** with **0 invalid records** and no parser diagnostics.

| Balancing authority | Observations |
|---|---:|
| AECI | 3 |
| DUKE CAROLINAS | 56 |
| DUKE PROGRESS EAST | 17 |
| DUKE PROGRESS WEST | 1 |
| LG&E/KU | 10 |
| SOUTHERN | 288 |
| TVA | 51 |

| Confidence | Observations |
|---|---:|
| HIGH | 413 |
| MEDIUM | 3 |
| LOW | 10 |

The review queue contains **13 records**: 3 with `AMBIGUOUS_ENDPOINTS` and 10 with `SUSPICIOUS_PROJECT_NAME`. The latter are source names such as `TS25-422`; they are retained verbatim instead of expanded speculatively. The 3 endpoint warnings likewise preserve the records while withholding unjustified certainty.

## Manually checked golden records

PDF indexes are zero-based in exported provenance; printed-page numbers are those detected in the report.

| PDF index | Printed page | Authority | Exact source project name | Check focus |
|---:|---:|---|---|---|
| 1 | 2 | DUKE CAROLINAS | BUSH RIVER TIE 115/100 KV AUTOTRANSFORMERS, REPLACE | transformer, two voltage levels, multiline fields |
| 26 | 27 | SOUTHERN | GTC: ADAMSVILLE - BUZZARD ROOST 230 KV REBUILD | GTC prefix, line rebuild |
| 26 | 27 | SOUTHERN | GTC: EAST MOULTRIE - HIGHWAY 112 230 KV LINE | GTC prefix, new-line description |
| 29 | 30 | SOUTHERN | GTC: REPLACE 230/115 KV AUTO TRANSFORMERS AT SOUTH HAZLEHURST | transformer, two voltage levels |
| 30 | 31 | SOUTHERN | SOCO: ANNISTON - BYNUM 115 KV TL UPGRADE | SOCO prefix, source punctuation |
| 31 | 32 | SOUTHERN | SOCO: ATHENA - EAST WATKINSVILLE 115 KV REBUILD | SOCO prefix, line rebuild |
| 31 | 32 | SOUTHERN | SOCO: AUTAUGAVILLE - EAST PELHAM NEW 230 KV TRANSMISSION LINE | SOCO prefix, multiline support |
| 31 | 32 | SOUTHERN | SOCO: BESSEMER – SOUTH BESSEMER 115 KV TL RECONDUCTOR - PHASE 1 | en dash, phase identifier, review warning |
| 102 | 103 | TVA | BULL RUN 500 KV SYNCHRONOUS CONDENSER, INSTALL | installation, multiline text |
| 102 | 103 | TVA | CORDOVA - YUM YUM 161 KV TRANSMISSION LINE, RECONDUCTOR | decimal length, conductor/temperature exclusion |

For each golden row, the rendered official page was checked against the exact raw name, year, description, supporting statement, page provenance, source hash, authority, owner prefix, voltage derivation, extraction provenance, and stable observation ID. The expected machine-readable records are in `tests/golden/sertp_2026/observations.json`.

## Determinism evidence

An unchanged cached-input rerun produced byte-identical deterministic artifacts:

| Artifact | SHA-256 |
|---|---|
| `sertp_2026_projects.json` | `68bd30edf2dbcc115b9aa15a731182d1739f1496231f9cb32d52606e37bf32cd` |
| `sertp_2026_projects.csv` | `a6fda62ab4b510fd0def8d6a1b653b5d8c27feb430c00859935d795c8367ea62` |
| `project_observation.schema.json` | `94580db9e62bf897c970d6e569c9920d74450a35de30fd299bb42b8cb9388755` |
| `review_queue.csv` | `3ae5755d58cc2c20d34b3e7dcad75335c35ecaa63bddfb0b9c38e11d290a78f9` |
| `data_quality.json` | `da88bb230346018ed95ecc5bf71739263d62f168307b28922c8a550616fec4c2` |

The source manifest is allowed to contain acquisition metadata, but the rerun retained the same source SHA-256 and empty change history.

## Generated paths

```text
data/processed/sertp_2026_projects.csv
data/processed/sertp_2026_projects.json
data/processed/review_queue.csv
data/processed/data_quality.json
data/processed/source_manifest.json
data/processed/bundle_manifest.json
schemas/project_observation.schema.json
```

Local source and extracted-page caches live under `data/raw/` and `data/extracted/`; they are intentionally ignored by Git.

## Reproduction and verification

```bash
python -m pip install -e '.[dev]'
python -m gridlock_pipeline run --source sertp --year 2026 --force --verbose
python -m ruff check src tests scripts
python -m pytest -q
python -m gridlock_pipeline validate --source sertp --year 2026
```

## Known limitations and stop boundary

- The parser relies on the public PDF text layer; Phase 1 has no OCR fallback.
- Derived project types and endpoint candidates are deterministic aids, not official source assertions. Machine-readable field provenance identifies their rules and inputs.
- The official 2026 report contains no record crossing a physical page boundary; parser continuity is covered by a synthetic fixture.
- No geocoding, Georgia Power attribution, historical matching, schedule-drift analysis, or historical parser-family assumption is included.

**The 2025 archive has not been started: it has not been discovered, downloaded, inspected, extracted, or parsed. Work stops here pending manual approval of the 2026 sample.**
