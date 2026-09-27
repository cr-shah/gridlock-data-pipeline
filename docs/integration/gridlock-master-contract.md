# Gridlock master dataset integration contract

`data/published/gridlock_master_projects.json` is the canonical analytical dataset. Excel is not
a source database; it is an optional human-readable report generated downstream from this file.

The publish command writes four synchronized machine artifacts:

| Artifact | Intended use |
|---|---|
| `gridlock_master_projects.json` | Canonical versioned snapshot and API/file consumers |
| `gridlock_master_projects.ndjson` | MongoDB document ingestion and streaming jobs |
| `gridlock_master_projects.csv` | SQL staging/import and analyst interoperability |
| `publication_manifest.json` | Dataset version, commit, counts, and SHA-256 artifact hashes |

All formats are generated in one run from the same in-memory canonical payload. The JSON remains
authoritative; NDJSON and CSV are transport formats and must never be edited by hand.

## Identity and geometry invariants

- `project_id` is the stable unique key in every system.
- A project exists once regardless of geometry state.
- `analysis_geometry` is selected by strict precedence: verified geometry, then estimated geometry,
  then null.
- Geometry is GeoJSON-shaped and uses longitude/latitude coordinate order.
- Confidence, method, source, notes, and unresolved reason remain attached to the record.
- AI-generated content must never change project identity, source facts, geometry state, geometry
  confidence, or provenance.

## MongoDB

Import the NDJSON file as one document per project and create a unique index on `project_id`.
Use `dataset_version` and `pipeline_commit` to identify the source snapshot. A future loader should
upsert by `project_id` inside a staging collection, validate all 78 records, then atomically promote
the completed snapshot. Do not maintain separate verified and estimated collections.

Recommended logical collections:

- `projects`: canonical project documents from NDJSON;
- `project_enrichments`: optional AI-derived descriptions keyed by `project_id`;
- `publication_runs`: manifest and load/audit metadata.

## SQL

The CSV is a flat staging representation. Fields ending in `_json` are JSON text and should become
`JSON`/`JSONB` columns where supported. Use `project_id` as the primary key. Production SQL loaders
should load a staging table, validate counts and uniqueness, then merge into the canonical table in
one transaction.

Do not create separate verified and estimated project tables. `geometry_status` is a state column;
`verified_geometry_json`, `estimated_geometry_json`, and `analysis_geometry_json` preserve the
selection evidence.

## Gemini enrichment boundary

Gemini is an enrichment service, not a source of record. Keep it out of the deterministic publish
path. A future Gemini job may read canonical project facts and produce a separate enrichment record:

```json
{
  "project_id": "stable project id",
  "dataset_version": "source dataset version",
  "model": "explicit model id",
  "prompt_version": "versioned prompt id",
  "generated_at": "ISO-8601 timestamp",
  "content": {},
  "review_status": "PENDING"
}
```

Store enrichments in a separate MongoDB collection or SQL table with a foreign key to
`project_id`. Never merge model output into the canonical project fields automatically. Any fact
promoted from AI output must return through the normal sourced, reviewed pipeline with provenance.

Keep `GEMINI_API_KEY`, `MONGODB_URI`, and `DATABASE_URL` in environment variables or a secret
manager. Never place credentials, prompts containing sensitive data, or model responses in the
canonical dataset.

## Regeneration

From an installed pipeline environment:

```bash
python -m gridlock_pipeline publish
```

This regenerates the canonical and transport datasets, then refreshes website, scoring, project
explorer, summary, and optional Excel outputs in the sibling product repository.
