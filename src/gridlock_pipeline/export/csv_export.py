"""Lossless flattened CSV observation export."""

import csv
import json
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from gridlock_pipeline.export.json_export import observation_sort_key
from gridlock_pipeline.models import ProjectObservation


def _csv_value(value: Any) -> str | int | float:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def export_observations_csv(
    observations: Sequence[ProjectObservation],
    path: Path,
) -> None:
    fieldnames = list(ProjectObservation.model_fields)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        for observation in sorted(observations, key=observation_sort_key):
            row = observation.model_dump(mode="json")
            writer.writerow({name: _csv_value(row[name]) for name in fieldnames})

