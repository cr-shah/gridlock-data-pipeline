"""Deterministic JSON observation export."""

import json
from collections.abc import Sequence
from pathlib import Path

from gridlock_pipeline.models import ProjectObservation


def observation_sort_key(observation: ProjectObservation) -> tuple:
    return (
        observation.source,
        observation.planning_year,
        observation.pdf_page_start,
        observation.pdf_page_end,
        observation.project_name_normalized or observation.project_name_raw,
        observation.observation_id,
    )


def export_observations_json(
    observations: Sequence[ProjectObservation],
    path: Path,
) -> None:
    payload = [
        item.model_dump(mode="json")
        for item in sorted(observations, key=observation_sort_key)
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
