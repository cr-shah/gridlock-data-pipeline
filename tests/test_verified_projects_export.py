import csv
import json
from pathlib import Path

import pytest

from gridlock_pipeline.export.verified_projects import (
    combine_verified_projects,
    write_verified_projects,
)


def test_verified_export_is_scoped_unique_matched_and_deterministic(tmp_path: Path) -> None:
    processed = Path("data/processed")
    first_json = tmp_path / "first.json"
    first_csv = tmp_path / "first.csv"
    second_json = tmp_path / "second.json"
    second_csv = tmp_path / "second.csv"

    records = write_verified_projects(
        processed / "desc_current_projects.json",
        processed / "georgia_power_current_projects.json",
        first_json,
        first_csv,
    )
    write_verified_projects(
        processed / "desc_current_projects.json",
        processed / "georgia_power_current_projects.json",
        second_json,
        second_csv,
    )

    with first_csv.open(newline="", encoding="utf-8") as stream:
        csv_records = list(csv.DictReader(stream))
    assert {record["utility"] for record in records} == {"DESC", "GPC"}
    assert len({record["observation_id"] for record in records}) == len(records)
    assert len(json.loads(first_json.read_text(encoding="utf-8"))) == len(csv_records)
    assert first_json.read_bytes() == second_json.read_bytes()
    assert first_csv.read_bytes() == second_csv.read_bytes()


def test_verified_export_rejects_other_utilities() -> None:
    with pytest.raises(ValueError, match="expected exactly DESC and GPC"):
        combine_verified_projects(
            [[{"utility": "DESC", "observation_id": "desc-1"}],
             [{"utility": "SOUTHERN", "observation_id": "regional-1"}]]
        )
