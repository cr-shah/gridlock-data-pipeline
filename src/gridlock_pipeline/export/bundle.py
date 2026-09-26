"""Transactional promotion and validation for generated output bundles."""

import csv
import json
import os
import shutil
import tempfile
from pathlib import Path

from gridlock_pipeline.models import ProjectObservation


def fsync_output_bundle(staging_dir: Path) -> None:
    """Flush every staged file before it becomes eligible for promotion."""
    for path in sorted(item for item in staging_dir.rglob("*") if item.is_file()):
        with path.open("rb") as stream:
            os.fsync(stream.fileno())


def validate_output_bundle(staging_dir: Path) -> None:
    """Check the generated contract files agree before publication."""
    processed = staging_dir / "data/processed"
    json_path = processed / "sertp_2026_projects.json"
    csv_path = processed / "sertp_2026_projects.csv"
    quality_path = processed / "data_quality.json"
    schema_path = staging_dir / "schemas/project_observation.schema.json"
    required = (json_path, csv_path, quality_path, schema_path)
    missing = [str(path.relative_to(staging_dir)) for path in required if not path.is_file()]
    if missing:
        raise ValueError(f"incomplete output bundle; missing: {', '.join(missing)}")

    json_rows = json.loads(json_path.read_text(encoding="utf-8"))
    with csv_path.open(newline="", encoding="utf-8") as stream:
        csv_rows = list(csv.DictReader(stream))
    quality = json.loads(quality_path.read_text(encoding="utf-8"))
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    if schema != ProjectObservation.model_json_schema():
        raise ValueError("generated schema does not match ProjectObservation")
    validated = [ProjectObservation.model_validate(row) for row in json_rows]
    json_ids = [row.observation_id for row in validated]
    csv_ids = [row["observation_id"] for row in csv_rows]
    if json_ids != csv_ids:
        raise ValueError("JSON and CSV observation identities differ")
    if quality.get("total_observations") != len(validated):
        raise ValueError("quality-report count differs from observation exports")


def promote_output_bundle(staging_dir: Path, processed_dir: Path) -> None:
    """Promote staged files as one rollback-safe transaction.

    ``processed_dir`` is the root against which staged relative paths are
    published. Existing files are backed up until every replacement succeeds.
    """
    files = sorted(path for path in staging_dir.rglob("*") if path.is_file())
    if not files:
        raise ValueError("cannot promote an empty output bundle")

    processed_dir.mkdir(parents=True, exist_ok=True)
    backup_dir = Path(tempfile.mkdtemp(prefix=".bundle-backup-", dir=processed_dir.parent))
    promoted: list[Path] = []
    backed_up: list[tuple[Path, Path]] = []
    try:
        for source in files:
            relative = source.relative_to(staging_dir)
            destination = processed_dir / relative
            backup = backup_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                os.replace(destination, backup)
                backed_up.append((backup, destination))
            os.replace(source, destination)
            promoted.append(destination)
    except Exception:
        for destination in reversed(promoted):
            destination.unlink(missing_ok=True)
        for backup, destination in reversed(backed_up):
            destination.parent.mkdir(parents=True, exist_ok=True)
            os.replace(backup, destination)
        raise
    finally:
        shutil.rmtree(backup_dir, ignore_errors=True)
