"""Deterministic post-extraction review-state policy.

A freshly extracted CareEvent's review_state and verification_reason are
NEVER taken from the provider, even if the raw candidate proposed values
for them - untrusted output is trusted only for claim_stance, source_type
and evidence (and the other descriptive fields); this policy is the sole
authority for review_state/verification_reason on anything that comes out
of the extraction pipeline. See pipeline.py, which calls derive_review_state
and overwrites whatever the candidate said.

Policy, checked in this order - the first matching rule wins:

  1. claim_stance == UNCERTAIN        -> needs_verification / explicit_uncertainty
  2. source_type == SECONDHAND        -> needs_verification / secondhand_report
  3. conflicts with a sibling event    -> needs_verification / conflicting_information
  4. evidence is weak (see below)      -> needs_verification / insufficient_evidence
  5. otherwise                         -> unreviewed / (no reason)

Order matters when more than one condition is true (e.g. an event that is
both uncertain AND secondhand still needs review either way, and rule 1
gives the more specific/actionable reason for a reviewer). This does not
mean rule 2 stops applying in spirit - see docs for the worked example.

IMPORTANT: "unreviewed" does not mean "true" or "confirmed". It only means
no rule above fired and no downstream human review decision has occurred
yet. review_state can only ever become VERIFIED through an actual review
action outside this package - this policy never produces it.
"""

from __future__ import annotations

from backend.core.care_event import (
    ClaimStance,
    Evidence,
    ReviewState,
    SourceType,
    TranscriptDocument,
    VerificationReason,
    VerificationReasonCode,
)

# A conservative, deterministic placeholder for "evidence too thin to trust
# on its own" - not a truth judgment, just a floor on how much supporting
# text an event's evidence carries in total. Real evidence-strength scoring
# (e.g. cross-referencing against the Phase 1 evaluator's grounding metrics)
# is future work; this exists so the "insufficient_evidence" rule is not
# simply unreachable.
_MIN_EVIDENCE_TEXT_CHARS = 12


def _evidence_is_weak(evidence: list[Evidence], document: TranscriptDocument) -> bool:
    segments_by_id = {s.segment_id: s for s in document.segments}
    total_chars = sum(
        len(segments_by_id[e.segment_id].text.strip()) for e in evidence if e.segment_id in segments_by_id
    )
    return total_chars < _MIN_EVIDENCE_TEXT_CHARS


def derive_review_state(
    claim_stance: ClaimStance,
    source_type: SourceType,
    evidence: list[Evidence],
    document: TranscriptDocument,
    has_conflict: bool = False,
) -> tuple[ReviewState, VerificationReason | None]:
    if claim_stance == ClaimStance.UNCERTAIN:
        return ReviewState.NEEDS_VERIFICATION, VerificationReason(VerificationReasonCode.EXPLICIT_UNCERTAINTY)
    if source_type == SourceType.SECONDHAND:
        return ReviewState.NEEDS_VERIFICATION, VerificationReason(VerificationReasonCode.SECONDHAND_REPORT)
    if has_conflict:
        return ReviewState.NEEDS_VERIFICATION, VerificationReason(VerificationReasonCode.CONFLICTING_INFORMATION)
    if _evidence_is_weak(evidence, document):
        return ReviewState.NEEDS_VERIFICATION, VerificationReason(VerificationReasonCode.INSUFFICIENT_EVIDENCE)
    return ReviewState.UNREVIEWED, None
