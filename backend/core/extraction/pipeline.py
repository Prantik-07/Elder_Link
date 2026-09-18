"""Orchestrates the Phase 3/4/4.1 architecture:

    TranscriptDocument -> ExtractionProvider -> Candidate CareEvents
        -> reject candidates claiming review_state=verified
        -> deterministic, order-independent event identity (identity.py)
        -> deterministic review policy (owns review_state/verification_reason)
        -> deterministic validation -> Validated CareEvents

The provider's output is untrusted by construction. A candidate dict is
parsed into a CareEvent (which itself rejects unknown enum values), and any
candidate that dares propose review_state=verified is rejected outright.
Two other fields the provider proposes are never trusted either:
event_id - always recomputed from the event's own semantic/evidence fields
via identity.assign_event_ids, independent of what the provider called it
or what position it appeared in - and review_state/verification_reason,
completely replaced by review_policy.derive_review_state. Only after both
of those deterministic steps have run does the fully structural
validate_care_event check apply, and only surviving events are returned as
validated_events.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from backend.core.care_event import CareEvent, ReviewState, TranscriptDocument, validate_care_event

from .conflicts import find_conflicting_event_ids
from .identity import assign_event_ids
from .review_policy import derive_review_state
from .service import ExtractionProvider
from .types import ExtractionErrorKind
from .validator import REJECT_VERIFIED_REASON


@dataclass
class RejectedCandidate:
    """A candidate that did not make it into validated_events, and why."""

    raw: dict
    reason: str
    stage: str  # "parse" (couldn't even become a CareEvent) | "policy" | "validation"


@dataclass
class ExtractionPipelineResult:
    provider: str
    model: str
    validated_events: list[CareEvent] = field(default_factory=list)
    rejected: list[RejectedCandidate] = field(default_factory=list)
    # Set only when the provider call itself failed (bad JSON, refusal,
    # provider/network failure, not-yet-available) - distinct from a
    # candidate individually failing validation.
    extraction_error: str | None = None
    extraction_error_kind: ExtractionErrorKind | None = None

    @property
    def extraction_failed(self) -> bool:
        return self.extraction_error is not None


def run_extraction_pipeline(document: TranscriptDocument, provider: ExtractionProvider) -> ExtractionPipelineResult:
    result = provider.extract(document)

    if not result.success:
        return ExtractionPipelineResult(
            provider=result.provider,
            model=result.model,
            extraction_error=result.error,
            extraction_error_kind=result.error_kind,
        )

    rejected: list[RejectedCandidate] = []
    raw_by_index: list[dict] = []
    candidates: list[CareEvent] = []

    for raw in result.candidate_events:
        try:
            candidate = CareEvent.from_dict(raw)
        except (ValueError, KeyError, TypeError) as e:
            rejected.append(RejectedCandidate(raw=raw, reason=str(e), stage="parse"))
            continue

        if candidate.review_state == ReviewState.VERIFIED:
            rejected.append(RejectedCandidate(raw=raw, reason=REJECT_VERIFIED_REASON, stage="policy"))
            continue

        raw_by_index.append(raw)
        candidates.append(candidate)

    # Transient, guaranteed-unique placeholder ids for internal
    # conflict-detection bookkeeping only - never surfaced. The provider's
    # own proposed event_id is not trusted for this either, since it may
    # be blank, reused, or otherwise not safe to use as a set key.
    indexed_for_conflicts = [replace(c, event_id=str(i)) for i, c in enumerate(candidates)]
    conflicting_indices = find_conflicting_event_ids(indexed_for_conflicts)

    # The real, order-independent identity - see identity.py. Computed once
    # over the whole batch so genuine collisions can be disambiguated
    # deterministically rather than by whatever order the provider used.
    final_ids = assign_event_ids(candidates, document.transcript_id)

    validated_events: list[CareEvent] = []
    for i, candidate in enumerate(candidates):
        review_state, verification_reason = derive_review_state(
            candidate.claim_stance,
            candidate.source_type,
            candidate.evidence,
            document,
            has_conflict=str(i) in conflicting_indices,
        )
        finalized = replace(
            candidate,
            event_id=final_ids[i],
            review_state=review_state,
            verification_reason=verification_reason,
        )

        errors = validate_care_event(finalized, document)
        if errors:
            rejected.append(RejectedCandidate(raw=raw_by_index[i], reason="; ".join(errors), stage="validation"))
            continue

        validated_events.append(finalized)

    return ExtractionPipelineResult(
        provider=result.provider,
        model=result.model,
        validated_events=validated_events,
        rejected=rejected,
    )
