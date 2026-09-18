"""Deterministic adapter: canonical CareEvent state -> the frontend's
existing presentation state (frontend/src/data/types.ts: CareEventStatus =
"verified" | "needs_verification" | "uncertain").

The frontend itself is NOT modified by this module or by Phase 4 - this is
a one-directional, backend-side mapping a future integration layer can call
before handing data to the UI. It exists because the frontend's status is a
*presentation* simplification of three orthogonal backend fields
(claim_stance, source_type, review_state - see schema.py), and collapsing
three fields into one inevitably loses information; this module is the one
place that lossy collapse happens, spelled out and tested, rather than left
implicit in whatever code eventually calls it.
"""

from __future__ import annotations

from enum import Enum

from .schema import ClaimStance, ReviewState, SourceType


class FrontendCareEventStatus(str, Enum):
    VERIFIED = "verified"
    NEEDS_VERIFICATION = "needs_verification"
    UNCERTAIN = "uncertain"


def to_frontend_status(
    review_state: ReviewState,
    claim_stance: ClaimStance,
    source_type: SourceType,
) -> FrontendCareEventStatus:
    """Mapping, in priority order (first match wins):

      review_state == VERIFIED                                  -> verified
      review_state == NEEDS_VERIFICATION                        -> needs_verification
      review_state == UNREVIEWED and claim_stance == UNCERTAIN  -> uncertain
      otherwise (UNREVIEWED: asserted/negated, or secondhand)   -> needs_verification

    review_state=VERIFIED is only ever reachable through an actual human
    review action (backend.core.extraction never produces it - see
    extraction/review_policy.py), so this never exposes "verified" to the
    frontend merely because extraction ran and produced clean output.

    The final "otherwise" branch is deliberately conservative: an
    UNREVIEWED asserted/firsthand event has still not been checked against
    reality - "unreviewed" is not "true" (see docs/care_event_schema.md and
    the Phase 4 report) - so the frontend is told needs_verification rather
    than something that reads as more settled than the backend actually
    knows. This also covers UNREVIEWED + secondhand, which the extraction
    review policy should route to NEEDS_VERIFICATION before this adapter
    ever sees it, but the adapter does not assume that and stays correct
    even for a CareEvent built outside the extraction pipeline.
    """
    if review_state == ReviewState.VERIFIED:
        return FrontendCareEventStatus.VERIFIED
    if review_state == ReviewState.NEEDS_VERIFICATION:
        return FrontendCareEventStatus.NEEDS_VERIFICATION
    if review_state == ReviewState.UNREVIEWED and claim_stance == ClaimStance.UNCERTAIN:
        return FrontendCareEventStatus.UNCERTAIN
    if review_state == ReviewState.UNREVIEWED and source_type == SourceType.SECONDHAND:
        return FrontendCareEventStatus.NEEDS_VERIFICATION
    return FrontendCareEventStatus.NEEDS_VERIFICATION
