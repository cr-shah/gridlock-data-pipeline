"""Command-line interface for the Phase 1 pipeline."""

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path

from gridlock_pipeline.pipeline import PipelineRunner

COMMANDS = ("discover", "download", "extract", "parse", "validate", "export", "run")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="gridlock_pipeline")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in COMMANDS:
        subparser = subparsers.add_parser(command)
        subparser.add_argument("--source", required=True)
        subparser.add_argument("--year", type=int, required=True)
        subparser.add_argument("--dry-run", action="store_true")
        subparser.add_argument("--force", action="store_true")
        subparser.add_argument("--verbose", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, root: Path | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.source not in {"sertp", "scrtp", "georgia_power"} or args.year != 2026:
        print(
            "Implemented sources are sertp, scrtp, and georgia_power for only 2026; "
            f"received {args.source}/{args.year}",
            file=sys.stderr,
        )
        return 2
    if args.dry_run:
        print(f"Dry run: would {args.command} {args.source} planning year {args.year}")
        return 0

    runner = PipelineRunner(root=root)
    if args.command == "discover":
        candidate = runner.discover(source=args.source, year=args.year)
        print(candidate.model_dump_json(indent=2))
        return 0

    result = runner.run(source=args.source, year=args.year, force=args.force)
    summary = {
        "command": args.command,
        "document_id": result.document.document_id,
        "sha256": result.document.sha256,
        "pages": len(result.pages),
        "observations": len(result.observations),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
