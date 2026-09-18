"""Strict validation for the canonical CareEvent.

Unknown enum values (event_type, claim_stance, source_type, review_state,
verification_reason) are already rejected at construction time - see
CareEvent.from_dict / Enum(...) in schema.py, which raise ValueError. This
module validates everything that a syntactically-valid CareEvent can still
get wrong: missing identifiers, missing/dangling evidence, and internally
inconsistent temporal data.

Deliberately does NOT validate:
  - that claim_stance/source_type combinations "make sense" (e.g. negated +
    secondhand is legitimate: "my sister said Dad did NOT miss his
    medication" is a real, valid claim).
  - that reported_by is set whenever source_type is SECONDHAND (a caregiver
    may legitimately not know exactly who told them).
These are real-world uncertainty, not schema errors - rejecting them would
throw away valid data.
"""

from __future__ import annotations

from .schema import CareEvent, Evidence, ReviewState, TemporalInfo, TemporalPrecision
from .transcript import TranscriptDocument, TranscriptSegment


class SchemaValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def validate_care_event(event: CareEvent, document: TranscriptDocument) -> list[str]:
    """Returns a list of human-readable error strings; empty means valid."""
    errors: list[str] = []

    if not event.event_id or not event.event_id.strip():
        errors.append("event_id is required")

    if not event.subject or not event.subject.strip():
        errors.append("subject is required")

    if not event.summary or not event.summary.strip():
        errors.append("summary is required")

    if not event.evidence:
        errors.append("at least one evidence segment is required - a CareEvent cannot become trusted persistent context ungrounded")
    else:
        segments_by_id = {s.segment_id: s for s in document.segments}
        for ev in event.evidence:
            segment = segments_by_id.get(ev.segment_id)
            if segment is None:
                errors.append(f"evidence references nonexistent segment '{ev.segment_id}'")
                continue
            errors.extend(_validate_evidence_timestamps(ev, segment))

    errors.extend(_validate_temporal(event.occurred_at))

    if event.review_state == ReviewState.NEEDS_VERIFICATION and event.verification_reason is None:
        errors.append("verification_reason.code is required when review_state is needs_verification")

    return errors


def _validate_evidence_timestamps(evidence: Evidence, segment: TranscriptSegment) -> list[str]:
    """When BOTH the evidence and the segment it points at carry timestamps,
    the evidence span must fall within the segment's span - an evidence
    range outside its own segment's bounds is an internally inconsistent
    reference, not a legitimate sub-span. When the segment has no
    timestamps at all (true for every Day 1 transcript today), there is
    nothing to check against, so this never fires - it does not invent a
    requirement Day 1 data can't satisfy."""
    if segment.start_time is None or segment.end_time is None:
        return []
    if evidence.start_time is None and evidence.end_time is None:
        return []

    errors: list[str] = []
    if evidence.start_time is not None and not (segment.start_time <= evidence.start_time <= segment.end_time):
        errors.append(
            f"evidence start_time {evidence.start_time} for segment '{segment.segment_id}' "
            f"falls outside the segment's own span [{segment.start_time}, {segment.end_time}]"
        )
    if evidence.end_time is not None and not (segment.start_time <= evidence.end_time <= segment.end_time):
        errors.append(
            f"evidence end_time {evidence.end_time} for segment '{segment.segment_id}' "
            f"falls outside the segment's own span [{segment.start_time}, {segment.end_time}]"
        )
    if evidence.start_time is not None and evidence.end_time is not None and evidence.start_time > evidence.end_time:
        errors.append(f"evidence start_time {evidence.start_time} is after end_time {evidence.end_time}")
    return errors


def _validate_temporal(temporal: TemporalInfo) -> list[str]:
    errors: list[str] = []
    p = temporal.precision

    if p == TemporalPrecision.EXACT_TIMESTAMP:
        if not temporal.timestamp:
            errors.append("occurred_at.timestamp is required when precision is exact_timestamp")
        if temporal.date or temporal.expression:
            errors.append("occurred_at must not set date/expression when precision is exact_timestamp")
    elif p == TemporalPrecision.DATE:
        if not temporal.date:
            errors.append("occurred_at.date is required when precision is date")
        if temporal.timestamp or temporal.expression:
            errors.append("occurred_at must not set timestamp/expression when precision is date")
    elif p == TemporalPrecision.RELATIVE:
        if not temporal.expression or not temporal.expression.strip():
            errors.append("occurred_at.expression is required when precision is relative")
        if temporal.timestamp or temporal.date:
            errors.append("occurred_at must not set timestamp/date when precision is relative")
    elif p == TemporalPrecision.UNKNOWN:
        if temporal.timestamp or temporal.date or temporal.expression:
            errors.append("occurred_at must not set timestamp/date/expression when precision is unknown")

    return errors


def assert_valid_care_event(event: CareEvent, document: TranscriptDocument) -> None:
    errors = validate_care_event(event, document)
    if errors:
        raise SchemaValidationError(errors)
