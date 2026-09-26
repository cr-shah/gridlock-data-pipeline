"""Authoritative machine-readable ProjectObservation schema."""

import json
from pathlib import Path

from gridlock_pipeline.models import ProjectObservation


def export_project_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(ProjectObservation.model_json_schema(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

