"""Authoritative machine-readable ProjectObservation schema."""

import json
import os
from pathlib import Path

from gridlock_pipeline.models import ProjectObservation


def export_project_schema(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as stream:
        stream.write(
            json.dumps(ProjectObservation.model_json_schema(), indent=2, sort_keys=True) + "\n"
        )
        stream.flush()
        os.fsync(stream.fileno())
