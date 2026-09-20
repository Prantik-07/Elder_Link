"""The canonical Care Event schema - see schema.py for the full rationale.

This is the one authoritative CareEvent definition for ElderLink. Other
layers (evaluation harness, future extractor, future backend/API) import
from here rather than declaring their own; the frontend's separate
CareEventStatus is a presentation-layer concern and stays out of scope of
this package (see docs/care_event_schema.md, "Frontend compatibility"),
except for frontend_adapter.py, which is a one-directional, read-only
mapping FROM the canonical fields TO that presentation concept - it does
not pull frontend semantics back into the backend model.
"""

from .frontend_adapter import FrontendCareEventStatus, to_frontend_status
from .normalization import (
    normalize_event_type_token,
    normalize_subject,
    normalize_whitespace,
)
from .schema import (
    CareEvent,
    ClaimStance,
    Evidence,
    EventType,
    ReviewState,
    SourceType,
    TemporalInfo,
    TemporalPrecision,
    VerificationReason,
    VerificationReasonCode,
    evidence_text,
    temporal_display_key,
)
from .transcript import (
    TranscriptDocument,
    TranscriptSegment,
    from_day1_transcript,
    from_stored_transcript,
    stable_segment_id,
)
from .validation import (
    SchemaValidationError,
    assert_valid_care_event,
    validate_care_event,
)

__all__ = [
    "CareEvent",
    "ClaimStance",
    "Evidence",
    "EventType",
    "ReviewState",
    "SourceType",
    "TemporalInfo",
    "TemporalPrecision",
    "VerificationReason",
    "VerificationReasonCode",
    "evidence_text",
    "temporal_display_key",
    "TranscriptDocument",
    "TranscriptSegment",
    "from_day1_transcript",
    "from_stored_transcript",
    "stable_segment_id",
    "SchemaValidationError",
    "assert_valid_care_event",
    "validate_care_event",
    "normalize_event_type_token",
    "normalize_subject",
    "normalize_whitespace",
    "FrontendCareEventStatus",
    "to_frontend_status",
]
