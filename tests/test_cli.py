from pathlib import Path

from gridlock_pipeline.cli import main


def test_dry_run_makes_no_files(tmp_path: Path, capsys) -> None:
    result = main(
        ["run", "--source", "sertp", "--year", "2026", "--dry-run"],
        root=tmp_path,
    )

    assert result == 0
    assert list(tmp_path.iterdir()) == []
    assert "dry run" in capsys.readouterr().out.casefold()


def test_cli_rejects_2025_explicitly(tmp_path: Path, capsys) -> None:
    result = main(
        ["run", "--source", "sertp", "--year", "2025", "--dry-run"],
        root=tmp_path,
    )

    assert result == 2
    assert "only 2026" in capsys.readouterr().err

