# Gridlock canonical data: implementation and integration handoff

## Purpose of this document

This is the detailed handoff for the Gridlock data consolidation work completed locally across:

- `cr-shah/gridlock-data-pipeline`
- `cr-shah/gridlock-challenge`

It explains why the change was needed, what was implemented, what remains intentionally separate,
and how another developer can integrate the generated dataset into a website, MongoDB, SQL system,
or a future Gemini enrichment workflow.

> **Publication branches:** pipeline work is published from `feat/canonical-publishing`; product
> integration is published from `feat/real-data-integration`. Use those branches until the changes
> are reviewed and merged into each repository's default branch.

## What problem we found

The product repository had several files that looked like independent datasets even though they
described the same projects:

| Old file | Actual meaning |
|---|---|
| `data/verified_projects.json` | Real 78-project catalog, with verified geometry on some projects |
| `data/estimated_geometry.json` | Geometry fallback records for projects missing verified geometry |
| `data/analysis.json` | Generated verified-only scoring output |
| `data/estimated_analysis.json` | Generated full-coverage scoring output |
| `data/projects.json` | Legacy/demo-only projects |
| `data/demo_analysis.json` | Generated demo output with illustrative assumptions |

This made it easy for names, years, IDs, geometry, and counts to drift between outputs. It also
made “verified projects” and “estimated projects” appear to be different project inventories.
They are not. A real project has one identity and may have verified, estimated, or unresolved
geometry.

## Decision and resulting model

`gridlock-data-pipeline` is now the single source of truth for the real project inventory and
geometry-state publication.

The canonical generated file is:

```text
data/published/gridlock_master_projects.json
```

It contains all 78 real projects exactly once. Every record carries all three geometry slots:

```json
{
  "project_id": "stable-id",
  "utility": "DESC",
  "project_name": "Example project",
  "project_type": "line_rebuild",
  "voltage": [115],
  "planned_start_year": null,
  "planned_end_year": null,
  "in_service_year": 2028,
  "status": null,
  "source_metadata": {},
  "verified_geometry": null,
  "estimated_geometry": {
    "type": "Point",
    "coordinates": [-81.0, 32.0]
  },
  "analysis_geometry": {
    "type": "Point",
    "coordinates": [-81.0, 32.0]
  },
  "geometry_status": "ESTIMATED",
  "geometry_method": "estimated_facility_point",
  "geometry_confidence": "ESTIMATED"
}
```

The selection rule is deterministic:

```text
if verified_geometry exists:
    analysis_geometry = verified_geometry
    geometry_status = VERIFIED
else if estimated_geometry exists:
    analysis_geometry = estimated_geometry
    geometry_status = ESTIMATED
else:
    analysis_geometry = null
    geometry_status = UNRESOLVED
```

Verified geometry always wins. Estimated geometry cannot replace it. Unresolved projects remain in
the catalog and are never silently dropped or assigned invented coordinates.

## Current verified counts

The generated dataset currently contains:

| Metric | Count |
|---|---:|
| Total unique projects | 78 |
| DESC projects | 54 |
| GPC projects | 24 |
| Verified geometry | 15 |
| Estimated geometry | 44 |
| Unresolved geometry | 19 |
| Projects with analysis geometry | 59 |
| Full DESC × GPC evaluable pairs | 840 |
| Verified pairs within 40 km | 6 |
| Full-coverage pairs within 40 km | 38 |

These counts are computed during publication and checked by tests. They are not hard-coded business
rules for all future versions.

## Pipeline files added or updated

```text
gridlock-data-pipeline/
├── data/
│   ├── curated/
│   │   └── estimated_geometry.json
│   └── published/
│       ├── gridlock_master_projects.json
│       ├── gridlock_master_projects.ndjson
│       ├── gridlock_master_projects.csv
│       └── publication_manifest.json
├── docs/integration/
│   ├── gridlock-master-contract.md
│   └── GRIDLOCK_CANONICAL_DATA_HANDOFF.md
├── schemas/
│   └── gridlock_master_projects.schema.json
├── src/gridlock_pipeline/export/
│   └── master_projects.py
├── src/gridlock_pipeline/
│   └── cli.py
└── tests/
    └── test_master_projects.py
```

The estimated geometry source snapshot was copied into the pipeline under `data/curated`. The
original product-repository source files were not overwritten.

## Product files added or updated

```text
gridlock-challenge/
├── data/published/
│   ├── gridlock_master_projects.json
│   ├── website_data.json
│   ├── project_explorer.json
│   ├── summary_statistics.json
│   └── gridlock_all_project_pairs.xlsx
├── master_dataset.py
├── scripts/
│   ├── publish_downstream.py
│   └── export_all_pairs_excel.py
└── tests/
    └── test_published_outputs.py
```

The website consumes one generated project catalog. Its two real-data views reference that catalog
by project ID instead of embedding two independent project arrays:

- Verified filter: `geometry_status == "VERIFIED"`
- Full/Estimated Coverage filter: `geometry_status in ["VERIFIED", "ESTIMATED"]`

The website currently still opens its Verified filter by default. A proposed change to make the
full map the default was explicitly stopped and was **not implemented**.

## Excel is optional

Excel is not the canonical dataset. The workbook exists only for people who want to review pairs,
sort distances, or share an analyst-friendly report.

The canonical JSON remains authoritative. The NDJSON and CSV files are generated transport formats.
They must never be edited by hand or treated as competing sources.

## One-command regeneration

The pipeline CLI now supports:

```bash
python -m gridlock_pipeline publish
```

When `gridlock-data-pipeline` and `gridlock-challenge` are sibling directories, that command:

1. Reads the pipeline-owned 78-project product inventory.
2. Reads the pipeline-owned curated estimated geometry overlay.
3. Applies verified-first geometry precedence.
4. Writes canonical JSON, MongoDB NDJSON, SQL CSV, and the publication manifest.
5. Finds the sibling `gridlock-challenge` checkout.
6. Copies the generated master into the product repository.
7. Regenerates website data and both scoring modes.
8. Regenerates project explorer data and summary statistics.
9. Regenerates the optional Excel pair workbook.

Use an explicit product path when the repositories are not siblings:

```bash
python -m gridlock_pipeline publish \
  --product-root /absolute/path/to/gridlock-challenge
```

Generate only the pipeline artifacts with:

```bash
python -m gridlock_pipeline publish --skip-downstream
```

## Local setup from the two repositories

Clone both repositories as siblings, then check out the publication branches:

```bash
mkdir gridlock
cd gridlock

git clone https://github.com/cr-shah/gridlock-data-pipeline.git
git clone https://github.com/cr-shah/gridlock-challenge.git

git -C gridlock-data-pipeline switch feat/canonical-publishing
git -C gridlock-challenge switch feat/real-data-integration
```

Install the pipeline and publishing dependencies:

```bash
cd gridlock-data-pipeline
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e '.[dev]'
```

Publish everything:

```bash
python -m gridlock_pipeline publish
```

Run the website locally:

```bash
cd ../gridlock-challenge
python -m http.server 8000
```

Then open `http://localhost:8000`. Opening `index.html` directly with `file://` will not allow its
JSON fetches to work.

## Integrating from GitHub

Before merge, consumers should use the pipeline feature branch:

```text
https://github.com/cr-shah/gridlock-data-pipeline/blob/feat/canonical-publishing/data/published/gridlock_master_projects.json
https://github.com/cr-shah/gridlock-data-pipeline/blob/feat/canonical-publishing/data/published/gridlock_master_projects.ndjson
https://github.com/cr-shah/gridlock-data-pipeline/blob/feat/canonical-publishing/data/published/gridlock_master_projects.csv
https://github.com/cr-shah/gridlock-data-pipeline/blob/feat/canonical-publishing/data/published/publication_manifest.json
```

After merge, replace `feat/canonical-publishing` with `main` in those URLs.

Consumers should download `publication_manifest.json` first, then verify the SHA-256 of the chosen
artifact before importing it. They should also store:

- `dataset_version`
- `generated_at`
- `pipeline_commit`
- artifact SHA-256

This makes every load reproducible and auditable.

## Minimal Python consumer

```python
import json
from pathlib import Path

payload = json.loads(
    Path("data/published/gridlock_master_projects.json").read_text()
)

assert payload["total_projects"] == len(payload["projects"])

all_projects = payload["projects"]
mapped_projects = [
    project
    for project in all_projects
    if project["geometry_status"] in {"VERIFIED", "ESTIMATED"}
]
verified_only = [
    project
    for project in all_projects
    if project["geometry_status"] == "VERIFIED"
]
```

Do not reconstruct `analysis_geometry` in consumers. Use the value published by the pipeline.

## MongoDB integration

Use `gridlock_master_projects.ndjson`. It contains one complete project document per line and adds
`dataset_version` and `pipeline_commit` to every document.

For a development import:

```bash
mongoimport \
  --uri "$MONGODB_URI" \
  --collection projects_staging \
  --file data/published/gridlock_master_projects.ndjson \
  --type json \
  --mode upsert \
  --upsertFields project_id
```

Create a unique key:

```javascript
db.projects_staging.createIndex({ project_id: 1 }, { unique: true })
```

Recommended production flow:

1. Download and hash-check the publication.
2. Import into a staging collection.
3. Confirm exactly 78 unique `project_id` values for the current snapshot.
4. Confirm geometry-status counts against the manifest/master metadata.
5. Create the unique index.
6. Atomically promote or rename the staging collection.
7. Record the dataset version, pipeline commit, and import time in `publication_runs`.

Do not create separate `verified_projects` and `estimated_projects` collections. They would restore
the drift this work removed. Store one project document and filter on `geometry_status`.

Recommended logical collections:

- `projects`: canonical project documents
- `project_enrichments`: optional Gemini-generated material
- `publication_runs`: import and artifact audit metadata

## SQL integration

Use `gridlock_master_projects.csv` for staging. Nested fields are stored as JSON text in columns
ending with `_json`.

An illustrative PostgreSQL table is:

```sql
CREATE TABLE gridlock_projects (
    project_id TEXT PRIMARY KEY,
    dataset_version TEXT NOT NULL,
    pipeline_commit TEXT NOT NULL,
    utility TEXT NOT NULL CHECK (utility IN ('DESC', 'GPC')),
    project_name TEXT NOT NULL,
    project_type TEXT,
    voltage JSONB NOT NULL,
    planned_start_year INTEGER,
    planned_end_year INTEGER,
    in_service_year INTEGER,
    status TEXT,
    geometry_status TEXT NOT NULL
        CHECK (geometry_status IN ('VERIFIED', 'ESTIMATED', 'UNRESOLVED')),
    geometry_method TEXT,
    geometry_confidence TEXT,
    verified_geometry JSONB,
    estimated_geometry JSONB,
    analysis_geometry JSONB,
    source_metadata JSONB NOT NULL
);
```

Recommended SQL load flow:

1. Load the CSV into a staging table with text/JSON staging columns.
2. Parse the `_json` columns into native JSON/JSONB.
3. Reject duplicate or null project IDs.
4. Compare row and status counts with the master metadata.
5. Merge/upsert into the canonical table in one transaction.
6. Record the publication version and artifact hash.

Do not use project name as a key. Names may change; `project_id` is the stable identity.

## Gemini integration

No Gemini API call was added to the deterministic publication command. This is intentional.
Gemini should enrich canonical records, not create or silently modify them.

A future enrichment record should look like:

```json
{
  "project_id": "stable-project-id",
  "dataset_version": "1.0.0",
  "pipeline_commit": "source commit",
  "model": "explicit Gemini model ID",
  "prompt_version": "gridlock-summary-v1",
  "generated_at": "ISO-8601 timestamp",
  "content": {
    "plain_language_summary": "..."
  },
  "review_status": "PENDING"
}
```

Required safeguards:

- Store AI results in `project_enrichments`, never inside canonical project fields.
- Join only with exact `project_id`.
- Record model ID, prompt version, dataset version, and generation time.
- Do not let Gemini set or change geometry, geometry status, confidence, utility, source metadata,
  dates, or project identity.
- Require review before showing AI-generated factual claims as authoritative.
- Never place `GEMINI_API_KEY` in JSON, source control, logs, or prompts.
- Keep `GEMINI_API_KEY`, `MONGODB_URI`, and `DATABASE_URL` in environment variables or a secret
  manager.
- Retry/rate-limit failures outside the canonical publisher so API availability cannot prevent a
  deterministic data publication.

If an AI-derived fact is believed to be correct, it must return through the sourced pipeline and
gain explicit provenance before becoming canonical.

## Publication manifest and integrity checking

`publication_manifest.json` contains SHA-256 values for:

- canonical JSON
- NDJSON
- CSV

Example verification:

```bash
python - <<'PY'
import hashlib
import json
from pathlib import Path

published = Path("data/published")
manifest = json.loads((published / "publication_manifest.json").read_text())

for filename, metadata in manifest["artifacts"].items():
    digest = hashlib.sha256((published / filename).read_bytes()).hexdigest()
    assert digest == metadata["sha256"], filename

print("Publication hashes verified")
PY
```

## Test and validation commands

Pipeline repository:

```bash
source .venv/bin/activate
python -m ruff check src tests scripts
python -m pytest -q
```

Current result: **122 pipeline tests passed**.

Product repository:

```bash
python -m unittest discover -s tests -q
```

Current result: **47 product tests passed**.

The tests cover:

- exactly 78 unique project IDs;
- no duplicate records;
- verified geometry precedence;
- geometry-state counts;
- JSON, NDJSON, CSV, website, explorer, and Excel identity consistency;
- names, years, and IDs across outputs;
- manifest hashes;
- existing Shapely distance behavior;
- existing Estimated Coverage eligibility behavior.

## What was deliberately not changed

- Shapely distance calculations
- distance thresholds
- Estimated Coverage close-tier eligibility rules
- original project source records
- original verified geometry
- demo data semantics
- the website default filter in the final follow-up
- any pull request or merge into a default branch

## Review and publication checklist

Before another developer publishes this work:

1. Review both repository working trees independently.
2. Confirm no unrelated local changes are included.
3. Run the complete pipeline and product tests.
4. Run `python -m gridlock_pipeline publish` one last time.
5. Confirm the pipeline and product master JSON files have identical hashes.
6. Confirm the manifest hashes.
7. Commit the pipeline changes first.
8. Rerun publication so `pipeline_commit` records the new pipeline commit.
9. Commit the regenerated pipeline artifacts.
10. Commit the product integration and regenerated downstream artifacts.
11. Push only after review.
12. Verify the raw GitHub URLs and the hosted website after merge.

Because `pipeline_commit` is generated from `git rev-parse HEAD`, the published artifact records
the implementation commit used by the publisher. Generated-artifact commits may follow that
implementation commit; this is expected and avoids a self-referential commit hash.
