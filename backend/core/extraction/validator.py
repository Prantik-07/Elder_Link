"""The boundary between untrusted extraction output and trusted CareEvents.

Wraps backend.core.care_event's generic schema validation with one
extraction-specific policy: a freshly extracted event must never carry
review_state=verified. VERIFIED is legitimate elsewhere (e.g. a human
review workflow constructing/updating a CareEvent directly) - it is only
extraction's own output that must never claim it for itself. A model
producing well-grounded, unhedged output has still only told you what was
*said*, not confirmed what actually happened.

validate_extracted_event is a convenience for checking a fully-formed
CareEvent (including a possibly-VERIFIED one) in one call - useful for ad
hoc/manual checking. pipeline.py does NOT use it directly: it needs the
VERIFIED check on the raw candidate specifically (before review_policy
overwrites review_state/verification_reason for everything else), so it
composes REJECT_VERIFIED_REASON and validate_care_event itself in that
order - see pipeline.py's module docstring.
"""

from __future__ import annotations

from backend.core.care_event import CareEvent, ReviewState, TranscriptDocument, validate_care_event

REJECT_VERIFIED_REASON = (
    "freshly extracted events must not have review_state=verified - "
    "extraction proves what was said, not that it happened"
)


def validate_extracted_event(event: CareEvent, document: TranscriptDocument) -> list[str]:
    errors = validate_care_event(event, document)
    if event.review_state == ReviewState.VERIFIED:
        errors.append(REJECT_VERIFIED_REASON)
    return errors
