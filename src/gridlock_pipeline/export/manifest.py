"""Deterministic source-manifest serialization."""

import json
from pathlib import Path

from gridlock_pipeline.models import SourceDocument


def write_source_manifest(
    document: SourceDocument,
    path: Path,
    previous: dict | None = None,
) -> None:
    history = list((previous or {}).get("history", []))
    current = (previous or {}).get("current")
    if current and current.get("sha256") != document.sha256:
        history.append(current)
    payload = {
        "schema_version": "1.0",
        "current": document.model_dump(mode="json"),
        "history": history,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

