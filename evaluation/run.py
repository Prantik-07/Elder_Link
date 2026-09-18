"""CLI entrypoint for the ElderLink Care Event evaluation harness.

Usage:
    python -m evaluation.run
    python -m evaluation.run --generated path/to/generated_events.json
    python -m evaluation.run --json

With no --generated file, runs against the bundled sample_generated_events.json
demo fixture (a hand-written stand-in output, NOT a real extractor - see that
file's _comment) so the CLI is runnable out of the box. Pass --generated to
evaluate real extractor output once one exists.

The --generated file must be a JSON object mapping case_id -> list of
generated Care Event dicts (same shape as an expected_events entry in
evaluation/data/golden_cases.json). Any case_id missing from the file is
treated as having produced zero generated events.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from evaluation.dataset import load_dataset
from evaluation.evaluator import evaluate_case
from evaluation.metrics import compute_metrics
from evaluation.models import CareEvent
from evaluation.report import format_report, to_dict

DEFAULT_GENERATED_PATH = Path(__file__).parent / "data" / "sample_generated_events.json"


def load_generated_events(path: Path) -> dict[str, list[CareEvent]]:
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    result: dict[str, list[CareEvent]] = {}
    for case_id, events in raw.items():
        if case_id.startswith("_"):
            continue
        result[case_id] = [CareEvent.from_dict(e) for e in events]
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ElderLink Care Event evaluation harness")
    parser.add_argument(
        "--generated",
        type=Path,
        default=DEFAULT_GENERATED_PATH,
        help="Path to a JSON file mapping case_id -> generated Care Events (default: bundled demo fixture)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of the human-readable report",
    )
    args = parser.parse_args(argv)

    dataset = load_dataset()
    generated_by_case = load_generated_events(args.generated)

    case_results = [
        evaluate_case(case, generated_by_case.get(case.case_id, []))
        for case in dataset
    ]
    metrics = compute_metrics(case_results)

    if args.json:
        print(json.dumps(to_dict(case_results, metrics), indent=2))
    else:
        if args.generated == DEFAULT_GENERATED_PATH:
            print("(using bundled demo fixture, not a real extractor - pass --generated to evaluate one)\n")
        print(format_report(case_results, metrics))

    return 0


if __name__ == "__main__":
    sys.exit(main())
