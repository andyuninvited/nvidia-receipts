"""
CLI entrypoint.

    python -m src.cli "Which SKUs are at risk of stockout this week in the Midwest?"

Prints the answer, then the receipt JSON, then the path to the receipt file.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv

from .agent import run_agent

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RECEIPTS_DIR = ROOT / "receipts"


def _parse_reference_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(description="NVIDIA Receipts demo agent")
    parser.add_argument("question", help="The retail-operator question to answer")
    parser.add_argument(
        "--user",
        default=os.environ.get("RECEIPT_USER", "me@andyrosic.com"),
        help="Identity stamped on the receipt",
    )
    parser.add_argument(
        "--reference-date",
        default=os.environ.get("REFERENCE_DATE"),
        help="ISO date to treat as 'today'. Stabilizes recency for the demo.",
    )
    parser.add_argument(
        "--caveat-threshold",
        type=float,
        default=float(os.environ.get("CONFIDENCE_CAVEAT_THRESHOLD", "0.65")),
    )
    parser.add_argument(
        "--abstain-threshold",
        type=float,
        default=float(os.environ.get("CONFIDENCE_ABSTAIN_THRESHOLD", "0.40")),
    )
    parser.add_argument("--quiet", action="store_true", help="Print only the receipt JSON")
    args = parser.parse_args(argv)

    answer, receipt, path = run_agent(
        args.question,
        user=args.user,
        data_dir=DATA_DIR,
        receipts_dir=RECEIPTS_DIR,
        reference_date=_parse_reference_date(args.reference_date),
        caveat_threshold=args.caveat_threshold,
        abstain_threshold=args.abstain_threshold,
    )

    if args.quiet:
        print(json.dumps(receipt, indent=2))
        return 0

    print("=" * 72)
    print("ANSWER")
    print("=" * 72)
    print(answer)
    print()
    print("=" * 72)
    print("RECEIPT")
    print("=" * 72)
    print(json.dumps(receipt, indent=2))
    print()
    print(f"Receipt written to: {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
