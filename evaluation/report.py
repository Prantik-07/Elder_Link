"""Human-readable and machine-readable reporting for an evaluation run."""

from __future__ import annotations

from evaluation.evaluator import CaseResult, Verdict
from evaluation.metrics import Metrics


def _pct(value: float | None) -> str:
    return f"{value * 100:.1f}%" if value is not None else "n/a"


def to_dict(case_results: list[CaseResult], metrics: Metrics) -> dict:
    """Machine-readable form of a full evaluation run."""
    return {
        "cases": metrics.case_count,
        "metrics": {
            "event_precision": metrics.event_precision,
            "event_recall": metrics.event_recall,
            "field_accuracy": metrics.field_accuracy,
            "per_field_accuracy": metrics.per_field_accuracy,
            "evidence_validity": metrics.evidence_validity,
            "evidence_precision": metrics.evidence_precision,
            "evidence_recall": metrics.evidence_recall,
            "claim_stance_accuracy": metrics.claim_stance_accuracy,
            "unsupported_event_rate": metrics.unsupported_event_rate,
        },
        "verdict_counts": {
            "correct": metrics.correct_count,
            "partial": metrics.partial_count,
            "unsupported": metrics.unsupported_count,
            "missing": metrics.missing_count,
            "contradictory": metrics.contradictory_count,
        },
        "case_results": [
            {
                "case_id": cr.case_id,
                "verdict_counts": cr.verdict_counts,
                "comparisons": [
                    {
                        "verdict": c.verdict.value,
                        "reason": c.reason,
                        "expected_summary": c.expected.summary if c.expected else None,
                        "generated_summary": c.generated.summary if c.generated else None,
                    }
                    for c in cr.comparisons
                ],
            }
            for cr in case_results
        ],
    }


def format_report(case_results: list[CaseResult], metrics: Metrics) -> str:
    lines = []
    lines.append("ElderLink Extraction Evaluation")
    lines.append("")
    lines.append(f"Cases: {metrics.case_count}")
    lines.append("")
    lines.append(f"Event precision:          {_pct(metrics.event_precision)}")
    lines.append(f"Event recall:             {_pct(metrics.event_recall)}")
    lines.append(f"Field accuracy:           {_pct(metrics.field_accuracy)}")
    lines.append(f"Evidence validity:        {_pct(metrics.evidence_validity)}")
    lines.append(f"Evidence precision:       {_pct(metrics.evidence_precision)}")
    lines.append(f"Evidence recall:          {_pct(metrics.evidence_recall)}")
    lines.append(f"Claim stance accuracy:    {_pct(metrics.claim_stance_accuracy)}")
    lines.append(f"Unsupported event rate:   {_pct(metrics.unsupported_event_rate)}")
    lines.append("")
    lines.append(
        "Verdicts: "
        f"correct={metrics.correct_count} "
        f"partial={metrics.partial_count} "
        f"unsupported={metrics.unsupported_count} "
        f"missing={metrics.missing_count} "
        f"contradictory={metrics.contradictory_count}"
    )

    failures = [
        (cr.case_id, c)
        for cr in case_results
        for c in cr.comparisons
        if c.verdict != Verdict.CORRECT
    ]

    if not failures:
        lines.append("")
        lines.append("No failures - every case matched exactly.")
        return "\n".join(lines)

    lines.append("")
    lines.append(f"Per-case failures ({len(failures)}):")
    lines.append("")
    for case_id, c in failures:
        lines.append(f"[{case_id}] {c.verdict.value.upper()}")
        if c.expected is not None:
            lines.append(f"    expected:  {c.expected.summary!r} ({c.expected.claim_stance.value}/{c.expected.source_type.value})")
        if c.generated is not None:
            lines.append(f"    generated: {c.generated.summary!r} ({c.generated.claim_stance.value}/{c.generated.source_type.value})")
        if c.reason:
            lines.append(f"    reason:    {c.reason}")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n"
