"""The canonical Care Event schema.

This is THE definition - extraction, evaluation, and any future backend
storage/API must import these types rather than re-declaring their own.
Adapters/mappings to other representations (the frontend's CareEventStatus,
Day 1's flat transcript JSON) are expected and fine; a second competing
CareEvent dataclass is not.

Four fields answer four genuinely different questions about a claim made in
a voice note, and the whole point of keeping them separate is that they
vary independently:

  claim_stance  - what is being claimed: that something happened
                  (asserted), that it might have (uncertain), or that it
                  did NOT happen (negated). See ClaimStance.
  source_type   - did the note's own speaker witness this directly, or are
                  they relaying someone else's account? See SourceType.
  review_state  - has anyone actually reviewed this against reality yet?
                  See ReviewState.

A transcript being clear, or an event having strong supporting evidence,
proves what was *reported* - not that the underlying real-world event is
objectively true. So review_state is never derived from how confidently
something was said; it starts unreviewed/needs_verification and only a real
review step (outside this package's scope) can set it to verified.

"Contradiction" - two claims in the same transcript disagreeing with each
other - is a relationship between two CareEvents, not a property of one. It
is represented as two separate events (e.g. one asserted, one that negates
or casts doubt on it), never as a third claim_stance value.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .transcript import TranscriptDocument


class EventType(str, Enum):
    """A small, controlled vocabulary. See docs/care_event_schema.md for
    the full description of each type and when to use OTHER."""

    MEDICATION = "medication"
    SYMPTOM = "symptom"
    APPOINTMENT = "appointment"
    VITAL = "vital"
    CARE_ACTION = "care_action"
    OBSERVATION = "observation"
    CONCERN = "concern"
    ROUTINE = "routine"
    OTHER = "other"


class ClaimStance(str, Enum):
    """What the speaker is claiming about whether this happened.

    ASSERTED  - stated as having happened (or being true), without hedging.
    UNCERTAIN - hedged: "I think", "may have", "not sure", vague phrasing.
    NEGATED   - stated as NOT having happened / not being true. This is a
                real, positive claim in its own right ("he did not miss his
                medication" is information worth keeping), not the absence
                of an event.
    """

    ASSERTED = "asserted"
    UNCERTAIN = "uncertain"
    NEGATED = "negated"


class SourceType(str, Enum):
    """Whether the note's own speaker witnessed this directly. Orthogonal
    to ClaimStance - any combination is valid (e.g. a secondhand report can
    itself be hedged: "my sister thinks Dad may have fallen")."""

    FIRSTHAND = "firsthand"
    SECONDHAND = "secondhand"
    UNKNOWN = "unknown"


class ReviewState(str, Enum):
    """Downstream workflow status, never inferred from claim_stance or
    evidence quality. See module docstring."""

    UNREVIEWED = "unreviewed"
    VERIFIED = "verified"
    NEEDS_VERIFICATION = "needs_verification"


class VerificationReasonCode(str, Enum):
    """Why an event needs review, when review_state is NEEDS_VERIFICATION.
    Kept small and specific rather than a giant enum - add a value only
    when the product actually needs to distinguish it."""

    EXPLICIT_UNCERTAINTY = "explicit_uncertainty"
    SECONDHAND_REPORT = "secondhand_report"
    CONFLICTING_INFORMATION = "conflicting_information"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    AMBIGUOUS_TIMING = "ambiguous_timing"
    AMBIGUOUS_SUBJECT = "ambiguous_subject"
    OTHER = "other"


@dataclass
class VerificationReason:
    """Why an event needs review. `code` is the controlled vocabulary above
    and is what any code (validation, review policy, UI filtering) should
    ever branch on. `detail` is a free-text elaboration - explanatory only,
    e.g. surfaced to a human reviewer - and must never be treated as
    evidence of anything: an LLM-generated explanation of why it thinks a
    claim is uncertain is not proof the claim is uncertain, still less
    proof of what actually happened."""

    code: VerificationReasonCode
    detail: Optional[str] = None

    @classmethod
    def from_dict(cls, data) -> "VerificationReason":
        if isinstance(data, str):
            # Tolerate a bare code string (no detail) for convenience.
            return cls(code=VerificationReasonCode(data))
        return cls(code=VerificationReasonCode(data["code"]), detail=data.get("detail"))


class TemporalPrecision(str, Enum):
    """How precisely "when" is known. Never inflate a vague phrase into a
    fake timestamp, and never collapse a known date/time down to "unknown"
    just because it isn't a full timestamp."""

    EXACT_TIMESTAMP = "exact_timestamp"  # a specific date+time is known
    DATE = "date"  # a specific calendar date is known, time of day isn't
    RELATIVE = "relative"  # an approximate/relative phrase, not resolved
    UNKNOWN = "unknown"  # nothing usable was said about timing at all


@dataclass
class TemporalInfo:
    """Exactly one of timestamp/date/expression is populated, matching
    `precision` - see validation.py for the consistency check. Kept as a
    required, always-present field on CareEvent (never a bare None) so
    "we don't know when" is an explicit, structured statement rather than
    an ambiguous missing value.
    """

    precision: TemporalPrecision
    timestamp: Optional[str] = None  # ISO 8601 datetime, only if EXACT_TIMESTAMP
    date: Optional[str] = None  # ISO 8601 date (YYYY-MM-DD), only if DATE
    expression: Optional[str] = None  # raw phrase as spoken, only if RELATIVE

    @classmethod
    def unknown(cls) -> "TemporalInfo":
        return cls(precision=TemporalPrecision.UNKNOWN)

    @classmethod
    def from_dict(cls, data: dict) -> "TemporalInfo":
        return cls(
            precision=TemporalPrecision(data.get("precision", "unknown")),
            timestamp=data.get("timestamp"),
            date=data.get("date"),
            expression=data.get("expression"),
        )


def temporal_display_key(t: TemporalInfo) -> Optional[str]:
    """A single comparable string for a TemporalInfo, or None when there's
    nothing to compare (UNKNOWN). Used for matching/comparison so callers
    don't need to branch on `precision` themselves."""
    if t.precision == TemporalPrecision.EXACT_TIMESTAMP and t.timestamp:
        return f"exact:{t.timestamp}"
    if t.precision == TemporalPrecision.DATE and t.date:
        return f"date:{t.date}"
    if t.precision == TemporalPrecision.RELATIVE and t.expression:
        return f"relative:{t.expression.strip().lower()}"
    return None


@dataclass
class Evidence:
    """A pointer into a TranscriptDocument's segments. Deliberately does
    NOT store a copy of the segment's text: the segment text in the
    TranscriptDocument is the one authoritative source, and duplicating it
    here would let the two drift out of sync. Look the text up via the
    segment_id when you need it (see validation.py / docs for the lookup
    helper). start_time/end_time only matter if the evidence covers a
    sub-span of the segment; leave both None to mean "the whole segment"."""

    segment_id: str
    start_time: Optional[float] = None
    end_time: Optional[float] = None

    @classmethod
    def from_dict(cls, data: dict) -> "Evidence":
        return cls(
            segment_id=data.get("segment_id", ""),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
        )


def evidence_text(evidence: Evidence, document: TranscriptDocument) -> Optional[str]:
    """Look up the text an Evidence reference points to, from the one
    authoritative TranscriptDocument. Returns None if the segment doesn't
    exist (validate the event before trusting this in production code)."""
    for segment in document.segments:
        if segment.segment_id == evidence.segment_id:
            return segment.text
    return None


@dataclass
class CareEvent:
    """The canonical Care Event. Only fields with a clear, distinct purpose
    are included - see docs/care_event_schema.md for the rationale behind
    each one."""

    event_id: str
    event_type: EventType
    subject: str
    summary: str
    claim_stance: ClaimStance
    source_type: SourceType
    review_state: ReviewState
    occurred_at: TemporalInfo
    evidence: list[Evidence] = field(default_factory=list)
    # Free-text provenance: who supplied this information, when source_type
    # is SECONDHAND (e.g. "sister"). Separate from source_type itself so
    # "was this witnessed directly" and "who exactly said it" can be
    # compared/matched independently.
    reported_by: Optional[str] = None
    verification_reason: Optional[VerificationReason] = None

    @property
    def evidence_segment_ids(self) -> list[str]:
        return [e.segment_id for e in self.evidence]

    @classmethod
    def from_dict(cls, data: dict) -> "CareEvent":
        occurred_at_data = data.get("occurred_at")
        occurred_at = TemporalInfo.from_dict(occurred_at_data) if occurred_at_data else TemporalInfo.unknown()

        verification_reason = data.get("verification_reason")

        return cls(
            event_id=data.get("event_id", ""),
            event_type=EventType(data["event_type"]),
            subject=data["subject"],
            summary=data["summary"],
            claim_stance=ClaimStance(data["claim_stance"]),
            source_type=SourceType(data["source_type"]),
            review_state=ReviewState(data["review_state"]),
            occurred_at=occurred_at,
            evidence=[Evidence.from_dict(e) for e in data.get("evidence", [])],
            reported_by=data.get("reported_by"),
            verification_reason=VerificationReason.from_dict(verification_reason) if verification_reason else None,
        )
