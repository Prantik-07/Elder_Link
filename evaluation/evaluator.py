"""Compares expected Care Events against generated Care Events.

Matching, field-level comparison, evidence comparison and claim-stance
comparison all live here. Text comparisons are normalized (case,
punctuation, whitespace) but never use semantic similarity/embeddings -
correctness here must stay fully deterministic and explainable.

Operates entirely on the canonical CareEvent from backend.core.care_event -
this module does not define its own event representation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from backend.core.care_event import CareEvent, temporal_display_key
from evaluation.models import GoldenCase

# --- text normalization -----------------------------------------------------

_PUNCT_RE = re.compile(r"[^\w\s]")
_WS_RE = re.compile(r"\s+")


def normalize_text(text: Optional[str]) -> str:
    text = (text or "").lower().strip()
    text = _PUNCT_RE.sub("", text)
    text = _WS_RE.sub(" ", text)
    return text


def token_overlap(a: Optional[str], b: Optional[str]) -> float:
    """Jaccard overlap of normalized word sets. Deterministic, no embeddings."""
    ta, tb = set(normalize_text(a).split()), set(normalize_text(b).split())
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def set_overlap(a: list[str], b: list[str]) -> float:
    """Jaccard overlap of two id sets, used only as a matching *signal*.
    Both-empty returns 0.0 (no signal either way), unlike token_overlap
    above, since an empty evidence list shouldn't count as "these two
    events agree"."""
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


SUMMARY_MATCH_THRESHOLD = 0.4
EVIDENCE_RECALL_MATCH_THRESHOLD = 0.5


# --- verdicts ----------------------------------------------------------------


class Verdict(str, Enum):
    CORRECT = "correct"
    PARTIAL = "partial"
    UNSUPPORTED = "unsupported"
    MISSING = "missing"
    CONTRADICTORY = "contradictory"


@dataclass
class FieldComparison:
    field_name: str
    matched: bool
    expected: object
    generated: object


@dataclass
class EvidenceScores:
    """Evidence-grounding scores for one generated event's cited segments.

    validity  - fraction of cited segment ids that actually exist in the
                transcript (penalize invented/non-existent ids).
    precision - of the *valid* cited ids, fraction that were actually
                expected evidence for this event (extra valid ids that
                aren't expected still count as valid but drag precision
                down - a metric, not a verdict).
    recall    - fraction of the expected evidence ids that were recovered
                among the valid cited ids. None when there is no expected
                evidence to recall against (an unmatched generated event
                has no paired expected event).
    has_valid_evidence - at least one cited id is real. An event with none
                is treated as unsupported regardless of anything else.
    invalid_ids - cited ids that don't exist in the transcript at all.
    """

    validity: float
    precision: float
    recall: Optional[float]
    has_valid_evidence: bool
    invalid_ids: list[str]


def compute_evidence_scores(
    expected_ids: list[str], generated_ids: list[str], valid_segment_ids: set[str]
) -> EvidenceScores:
    valid_generated = [i for i in generated_ids if i in valid_segment_ids]
    invalid_generated = [i for i in generated_ids if i not in valid_segment_ids]
    valid_set = set(valid_generated)
    expected_set = set(expected_ids)

    validity = (len(valid_set) / len(generated_ids)) if generated_ids else 0.0
    precision = (len(valid_set & expected_set) / len(valid_set)) if valid_set else 0.0
    recall = (len(valid_set & expected_set) / len(expected_set)) if expected_set else None

    return EvidenceScores(
        validity=validity,
        precision=precision,
        recall=recall,
        has_valid_evidence=len(valid_set) > 0,
        invalid_ids=invalid_generated,
    )


@dataclass
class EventComparison:
    verdict: Verdict
    expected: Optional[CareEvent]
    generated: Optional[CareEvent]
    field_results: list[FieldComparison] = field(default_factory=list)
    evidence: Optional[EvidenceScores] = None
    reason: str = ""

    def get_field(self, name: str) -> Optional[FieldComparison]:
        return next((f for f in self.field_results if f.field_name == name), None)


@dataclass
class CaseResult:
    case_id: str
    comparisons: list[EventComparison]

    @property
    def verdict_counts(self) -> dict[str, int]:
        counts = {v.value: 0 for v in Verdict}
        for c in self.comparisons:
            counts[c.verdict.value] += 1
        return counts

    @property
    def is_fully_correct(self) -> bool:
        return all(c.verdict == Verdict.CORRECT for c in self.comparisons)


# --- field-level comparison --------------------------------------------------


def _occurred_at_matches(expected: CareEvent, generated: CareEvent) -> bool:
    ek, gk = temporal_display_key(expected.occurred_at), temporal_display_key(generated.occurred_at)
    if ek is None or gk is None:
        return ek == gk  # both unknown counts as agreement; one-sided doesn't
    return ek == gk


def _build_field_comparisons(
    expected: CareEvent, generated: CareEvent, evidence: EvidenceScores
) -> list[FieldComparison]:
    evidence_matched = (
        evidence.has_valid_evidence
        and evidence.validity == 1.0
        and (evidence.recall is None or evidence.recall >= EVIDENCE_RECALL_MATCH_THRESHOLD)
    )
    return [
        FieldComparison(
            "event_type",
            expected.event_type == generated.event_type,
            expected.event_type.value,
            generated.event_type.value,
        ),
        FieldComparison(
            "subject",
            normalize_text(expected.subject) == normalize_text(generated.subject),
            expected.subject,
            generated.subject,
        ),
        FieldComparison(
            "claim_stance",
            expected.claim_stance == generated.claim_stance,
            expected.claim_stance.value,
            generated.claim_stance.value,
        ),
        FieldComparison(
            "source_type",
            expected.source_type == generated.source_type,
            expected.source_type.value,
            generated.source_type.value,
        ),
        FieldComparison(
            "review_state",
            expected.review_state == generated.review_state,
            expected.review_state.value,
            generated.review_state.value,
        ),
        FieldComparison(
            "reported_by",
            normalize_text(expected.reported_by) == normalize_text(generated.reported_by),
            expected.reported_by,
            generated.reported_by,
        ),
        FieldComparison(
            "occurred_at",
            _occurred_at_matches(expected, generated),
            temporal_display_key(expected.occurred_at),
            temporal_display_key(generated.occurred_at),
        ),
        FieldComparison(
            "summary",
            token_overlap(expected.summary, generated.summary) >= SUMMARY_MATCH_THRESHOLD,
            expected.summary,
            generated.summary,
        ),
        FieldComparison(
            "evidence",
            evidence_matched,
            expected.evidence_segment_ids,
            generated.evidence_segment_ids,
        ),
    ]


# --- matching -----------------------------------------------------------------

# Priority order per spec: subject compatibility outweighs temporal, which
# is a secondary signal; evidence overlap is a strong supporting signal but
# never the sole identity mechanism (transcript segmentation may legitimately
# differ from golden segmentation); summary overlap is the weakest/last-
# resort signal. event_type is a hard filter, not part of this scoring.
_SUBJECT_WEIGHT = 3.0
_TEMPORAL_WEIGHT = 1.0
_EVIDENCE_WEIGHT = 2.0
_SUMMARY_WEIGHT = 1.0


def _candidate_score(expected: CareEvent, generated: CareEvent) -> float:
    """How likely `generated` describes the same real-world event as
    `expected` - used only to pair candidates, never to judge correctness.
    A matched pair can still be scored contradictory or partial. Returns
    0.0 (never a candidate) when event types differ - type is never
    force-matched."""
    if expected.event_type != generated.event_type:
        return 0.0

    subject_score = _SUBJECT_WEIGHT if normalize_text(expected.subject) == normalize_text(generated.subject) else 0.0
    temporal_score = _TEMPORAL_WEIGHT if _occurred_at_matches(expected, generated) and temporal_display_key(expected.occurred_at) else 0.0
    evidence_score = _EVIDENCE_WEIGHT * set_overlap(expected.evidence_segment_ids, generated.evidence_segment_ids)
    summary_score = _SUMMARY_WEIGHT * token_overlap(expected.summary, generated.summary)

    return subject_score + temporal_score + evidence_score + summary_score


def match_events(
    expected_events: list[CareEvent], generated_events: list[CareEvent]
) -> tuple[list[tuple[CareEvent, CareEvent]], list[CareEvent], list[CareEvent]]:
    """Deterministic one-to-one matching, highest score first.

    A candidate must share event_type (hard filter - never force-matched)
    and have a positive score (at least one of subject/temporal/evidence/
    summary agrees - never force-matched on type alone with zero other
    signal). Returns (matched_pairs, unmatched_expected, unmatched_generated).
    """
    candidates = []
    for ei, e in enumerate(expected_events):
        for gi, g in enumerate(generated_events):
            score = _candidate_score(e, g)
            if score > 0:
                candidates.append((score, ei, gi))
    candidates.sort(key=lambda c: c[0], reverse=True)

    matched_e: set[int] = set()
    matched_g: set[int] = set()
    pairs: list[tuple[CareEvent, CareEvent]] = []
    for _score, ei, gi in candidates:
        if ei in matched_e or gi in matched_g:
            continue
        matched_e.add(ei)
        matched_g.add(gi)
        pairs.append((expected_events[ei], generated_events[gi]))

    unmatched_expected = [e for i, e in enumerate(expected_events) if i not in matched_e]
    unmatched_generated = [g for i, g in enumerate(generated_events) if i not in matched_g]
    return pairs, unmatched_expected, unmatched_generated


# --- scoring a matched pair ----------------------------------------------------

# Fields whose disagreement changes the *meaning* of the event (what
# happened, to whom, how sure we should be) and therefore make it actively
# wrong rather than merely incomplete. Provenance (source_type/reported_by)
# and workflow status (review_state) are deliberately excluded - attribution
# is a separate, non-critical comparison, not an automatic contradiction.
_NON_CRITICAL_FIELDS = ("source_type", "reported_by", "review_state", "occurred_at", "summary", "evidence")


def evaluate_pair(expected: CareEvent, generated: CareEvent, valid_segment_ids: set[str]) -> EventComparison:
    evidence = compute_evidence_scores(expected.evidence_segment_ids, generated.evidence_segment_ids, valid_segment_ids)

    if not evidence.has_valid_evidence:
        # A claim with no real supporting segment can't be trusted even if
        # every other field happens to look right.
        return EventComparison(
            Verdict.UNSUPPORTED,
            expected,
            generated,
            evidence=evidence,
            reason="generated event has no valid supporting evidence segment",
        )

    fields = _build_field_comparisons(expected, generated, evidence)
    by_name = {f.field_name: f for f in fields}

    subject_explicit_mismatch = (
        not by_name["subject"].matched
        and expected.subject.strip() != ""
        and generated.subject.strip() != ""
    )
    if subject_explicit_mismatch:
        return EventComparison(
            Verdict.CONTRADICTORY,
            expected,
            generated,
            fields,
            evidence=evidence,
            reason=f"subject mismatch: expected {expected.subject!r}, got {generated.subject!r}",
        )

    if not by_name["claim_stance"].matched:
        return EventComparison(
            Verdict.CONTRADICTORY,
            expected,
            generated,
            fields,
            evidence=evidence,
            reason=f"claim_stance mismatch: expected {expected.claim_stance.value!r}, got {generated.claim_stance.value!r}",
        )

    mismatches = [name for name in _NON_CRITICAL_FIELDS if not by_name[name].matched]
    if not mismatches:
        return EventComparison(Verdict.CORRECT, expected, generated, fields, evidence=evidence)
    return EventComparison(
        Verdict.PARTIAL,
        expected,
        generated,
        fields,
        evidence=evidence,
        reason=f"field mismatch: {', '.join(mismatches)}",
    )


# --- case-level evaluation ------------------------------------------------------


def evaluate_case(case: GoldenCase, generated_events: list[CareEvent]) -> CaseResult:
    valid_segment_ids = case.document.segment_ids
    pairs, unmatched_expected, unmatched_generated = match_events(case.expected_events, generated_events)

    comparisons = [evaluate_pair(e, g, valid_segment_ids) for e, g in pairs]

    for e in unmatched_expected:
        comparisons.append(
            EventComparison(Verdict.MISSING, e, None, reason="no generated event matched this expected event")
        )

    for g in unmatched_generated:
        evidence = compute_evidence_scores([], g.evidence_segment_ids, valid_segment_ids)
        if not evidence.has_valid_evidence:
            reason = "generated event has no valid supporting evidence segment"
        else:
            reason = "generated event has no basis in the expected events"
        comparisons.append(EventComparison(Verdict.UNSUPPORTED, None, g, evidence=evidence, reason=reason))

    return CaseResult(case_id=case.case_id, comparisons=comparisons)
