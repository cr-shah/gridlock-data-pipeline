from pathlib import Path

import pytest

import gridlock_pipeline.export.bundle as bundle_module
from gridlock_pipeline.export.bundle import promote_output_bundle


def test_promotion_rolls_back_every_file_when_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "published"
    staging = tmp_path / "staging"
    target.mkdir()
    staging.mkdir()
    (target / "a.txt").write_bytes(b"known-good-a")
    (target / "b.txt").write_bytes(b"known-good-b")
    (staging / "a.txt").write_bytes(b"candidate-a")
    (staging / "b.txt").write_bytes(b"candidate-b")
    before = {path.name: path.read_bytes() for path in target.iterdir()}
    real_replace = bundle_module.os.replace
    failed = False

    def fail_on_second_candidate(source: Path, destination: Path) -> None:
        nonlocal failed
        if not failed and Path(source).parent == staging and Path(source).name == "b.txt":
            failed = True
            raise OSError("simulated promotion failure")
        real_replace(source, destination)

    monkeypatch.setattr(bundle_module.os, "replace", fail_on_second_candidate)

    with pytest.raises(OSError, match="simulated promotion failure"):
        promote_output_bundle(staging, target)

    assert {path.name: path.read_bytes() for path in target.iterdir()} == before


def test_promotion_rejects_an_empty_staging_bundle(tmp_path: Path) -> None:
    staging = tmp_path / "empty"
    staging.mkdir()

    with pytest.raises(ValueError, match="empty"):
        promote_output_bundle(staging, tmp_path / "published")
