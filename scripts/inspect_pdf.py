#!/usr/bin/env python3
"""Print inclusive physical-page ranges from extracted JSON Lines."""

import argparse
from pathlib import Path

from gridlock_pipeline.extraction import read_pages_jsonl


def parse_range(value: str) -> tuple[int, int]:
    start, separator, end = value.partition(":")
    if not separator:
        page = int(start)
        return page, page
    return int(start), int(end)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--pages", required=True, help="inclusive zero-based range, e.g. 1:12")
    args = parser.parse_args()
    start, end = parse_range(args.pages)
    for page in read_pages_jsonl(args.input):
        if start <= page.pdf_page_index <= end:
            print(
                f"===== PDF index {page.pdf_page_index} "
                f"(printed {page.printed_page_number}) ====="
            )
            print(page.text.rstrip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
