"""Runs the full Phase 3 chain over the Phase 1/2 golden dataset:

    golden transcript -> ExtractionProvider -> validator -> Phase 1 evaluator

This is the "evaluation integration" required by Phase 3: it proves the
extraction pipeline end-to-end against the same golden cases used to judge
any other extractor, and it reports failures at the layer they actually
happened at - a provider that failed outright, a candidate the validator
rejected before it ever reached the evaluator, and (for whatever survived
validation) the same correct/partial/unsupported/missing/contradictory
verdicts Phase 1/2 already define. It does not invent a second scoring
system; the evaluator, verdicts and metrics are the ones already in
evaluation.evaluator / evaluation.metrics / evaluation.report.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from typing import Optional

from backend.core.extraction import (
    BedrockExtractionProvider,
    ExtractionProvider,
    MockExtractionProvider,
    RejectedCandidate,
    run_extraction_pipeline,
)
from evaluation.dataset import load_dataset
from evaluation.evaluator import CaseResult, evaluate_case
from evaluation.metrics import compute_metrics
from evaluation.models import GoldenCase
from evaluation.report import format_report


@dataclass
class CaseBenchResult:
    case_id: str
    extraction_error: Optional[str]
    rejected: list[RejectedCandidate]
    case_result: Optional[CaseResult]  # None only when extraction itself failed


def run_benchmark(provider: ExtractionProvider, dataset: Optional[list[GoldenCase]] = None) -> list[CaseBenchResult]:
    dataset = dataset if dataset is not None else load_dataset()
    bench_results = []

    for case in dataset:
        pipeline_result = run_extraction_pipeline(case.document, provider)

        if pipeline_result.extraction_failed:
            bench_results.append(
                CaseBenchResult(
                    case_id=case.case_id,
                    extraction_error=pipeline_result.extraction_error,
                    rejected=[],
                    case_result=None,
                )
            )
            continue

        case_result = evaluate_case(case, pipeline_result.validated_events)
        bench_results.append(
            CaseBenchResult(
                case_id=case.case_id,
                extraction_error=None,
                rejected=pipeline_result.rejected,
                case_result=case_result,
            )
        )

    return bench_results


def format_bench_report(bench_results: list[CaseBenchResult]) -> str:
    lines: list[str] = []

    extraction_errors = [b for b in bench_results if b.extraction_error is not None]
    scored = [b for b in bench_results if b.case_result is not None]

    if extraction_errors:
        lines.append(f"Extraction errors ({len(extraction_errors)} case(s) never reached the evaluator):")
        lines.extend(f"  [{b.case_id}] {b.extraction_error}" for b in extraction_errors)
        lines.append("")

    validation_rejections = [(b.case_id, r) for b in scored for r in b.rejected]
    if validation_rejections:
        lines.append(f"Validation rejections ({len(validation_rejections)} candidate(s) rejected before scoring):")
        lines.extend(f"  [{case_id}] ({r.stage}) {r.reason}" for case_id, r in validation_rejections)
        lines.append("")

    case_results = [b.case_result for b in scored]
    if case_results:
        metrics = compute_metrics(case_results)
        lines.append(format_report(case_results, metrics))
    else:
        lines.append("No cases reached the evaluator - every case hit an extraction error.")

    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Run the Phase 3 extraction pipeline over the golden dataset")
    parser.add_argument("--provider", choices=["mock", "bedrock"], default="mock")
    args = parser.parse_args(argv)

    provider: ExtractionProvider
    if args.provider == "mock":
        provider = MockExtractionProvider()
    else:
        provider = BedrockExtractionProvider()
        print(
            "(bedrock provider selected - live inference is not yet verified for this "
            "AWS account; expect extraction errors, not results)\n"
        )

    print(f"(using {provider.provider_name}/{provider.model_id})\n")

    bench_results = run_benchmark(provider)
    print(format_bench_report(bench_results))
    return 0


if __name__ == "__main__":
    sys.exit(main())
