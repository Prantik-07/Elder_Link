"""Loads the golden dataset of (transcript, expected Care Events) cases."""

from __future__ import annotations

import json
from pathlib import Path

from evaluation.models import GoldenCase

DEFAULT_DATASET_PATH = Path(__file__).parent / "data" / "golden_cases.json"


def load_dataset(path: Path | str = DEFAULT_DATASET_PATH) -> list[GoldenCase]:
    path = Path(path)
    with path.open("r", encoding="utf-8") as f:
        raw_cases = json.load(f)

    if not isinstance(raw_cases, list):
        raise ValueError(f"Dataset at {path} must be a JSON array of cases")

    cases = [GoldenCase.from_dict(c) for c in raw_cases]

    seen_ids = set()
    duplicates = set()
    for case in cases:
        if case.case_id in seen_ids:
            duplicates.add(case.case_id)
        seen_ids.add(case.case_id)
    if duplicates:
        raise ValueError(f"Duplicate case_id(s) in dataset: {duplicates}")

    return cases
