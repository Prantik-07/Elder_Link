"""Aggregate metrics computed from a list of per-case evaluation results."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from evaluation.evaluator import CaseResult, EventComparison, Verdict

_FIELD_NAMES = (
    "event_type",
    "subject",
    "claim_stance",
    "source_type",
    "review_state",
    "reported_by",
    "occurred_at",
    "summary",
    "evidence",
)


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


@dataclass
class Metrics:
    case_count: int
    event_precision: Optional[float]
    event_recall: Optional[float]
    field_accuracy: Optional[float]
    per_field_accuracy: dict[str, Optional[float]]
    evidence_validity: Optional[float]
    evidence_precision: Optional[float]
    evidence_recall: Optional[float]
    claim_stance_accuracy: Optional[float]
    unsupported_event_rate: Optional[float]
    correct_count: int
    partial_count: int
    unsupported_count: int
    missing_count: int
    contradictory_count: int


def _all_comparisons(case_results: list[CaseResult]) -> list[EventComparison]:
    return [c for cr in case_results for c in cr.comparisons]


def compute_metrics(case_results: list[CaseResult]) -> Metrics:
    comparisons = _all_comparisons(case_results)

    correct = [c for c in comparisons if c.verdict == Verdict.CORRECT]
    partial = [c for c in comparisons if c.verdict == Verdict.PARTIAL]
    unsupported = [c for c in comparisons if c.verdict == Verdict.UNSUPPORTED]
    missing = [c for c in comparisons if c.verdict == Verdict.MISSING]
    contradictory = [c for c in comparisons if c.verdict == Verdict.CONTRADICTORY]

    # True positives: a generated event that corresponds to a real expected
    # event, whether or not every field on it was right. False positives:
    # generated events that shouldn't exist (hallucinated, ungrounded, or
    # contradicting the source) even though some may have matched an
    # expected event's evidence. False negatives: expected events nothing
    # was generated for.
    tp = len(correct) + len(partial)
    fp = len(unsupported) + len(contradictory)
    fn = len(missing)

    event_precision = tp / (tp + fp) if (tp + fp) else None
    event_recall = tp / (tp + fn) if (tp + fn) else None

    matched_pairs = [c for c in comparisons if c.expected is not None and c.generated is not None]

    per_field_accuracy: dict[str, Optional[float]] = {}
    for name in _FIELD_NAMES:
        scores = [
            1.0 if fc.matched else 0.0
            for c in matched_pairs
            for fc in c.field_results
            if fc.field_name == name
        ]
        per_field_accuracy[name] = _mean(scores)

    available_field_scores = [v for v in per_field_accuracy.values() if v is not None]
    field_accuracy = _mean(available_field_scores)

    claim_stance_accuracy = per_field_accuracy["claim_stance"]

    # Evidence precision/recall/validity are computed over every comparison
    # that has a generated event (matched pairs and unmatched-generated
    # ones), not just matched pairs - an ungrounded hallucination's evidence
    # quality is exactly what we want this metric to expose.
    generated_comparisons = [c for c in comparisons if c.generated is not None and c.evidence is not None]
    evidence_validity = _mean([c.evidence.validity for c in generated_comparisons])
    evidence_precision = _mean([c.evidence.precision for c in generated_comparisons])
    recall_scores = [c.evidence.recall for c in generated_comparisons if c.evidence.recall is not None]
    evidence_recall = _mean(recall_scores)

    total_generated = len(comparisons) - len(missing)
    unsupported_event_rate = len(unsupported) / total_generated if total_generated else None

    return Metrics(
        case_count=len(case_results),
        event_precision=event_precision,
        event_recall=event_recall,
        field_accuracy=field_accuracy,
        per_field_accuracy=per_field_accuracy,
        evidence_validity=evidence_validity,
        evidence_precision=evidence_precision,
        evidence_recall=evidence_recall,
        claim_stance_accuracy=claim_stance_accuracy,
        unsupported_event_rate=unsupported_event_rate,
        correct_count=len(correct),
        partial_count=len(partial),
        unsupported_count=len(unsupported),
        missing_count=len(missing),
        contradictory_count=len(contradictory),
    )
