"""Maps a persisted CareEventRecord to the frontend's CareEvent DTO shape
(frontend/src/data/types.ts).

This is the one place a canonical, persisted CareEvent becomes JSON the
read API hands to the frontend. It lives in `persistence`, not
`care_event`, because it needs CareEventRecord (event + CareContext +
audit timestamps) - importing that back into `care_event` would create a
cycle, since `persistence` already depends on `care_event`.

The frontend's CareEvent is a presentation simplification of the canonical
model (see care_event/frontend_adapter.py for the status collapse this
module reuses) - this module extends that same one-directional,
lossy-by-design mapping to the rest of the fields the frontend needs,
rather than exposing the raw DynamoDB item or canonical dataclasses
directly.

Known, deliberate limitations (see the Phase 7 report for the full
rationale - not fixed here because they require real product decisions
outside this phase's scope):

  - The canonical CareEvent has one `summary` field; the frontend
    distinguishes `title` / `summary` / `whatHappened`. All three are
    populated from the same canonical `summary` until extraction produces
    genuinely distinct copy for each.
  - Evidence.segment_id points into a TranscriptDocument that this
    persistence layer never stores a copy of (see serialization.py) - the
    literal transcript quote is not available from DynamoDB alone. The
    `transcript` field on the DTO's evidence is therefore populated with
    the event's own `summary` as an honest best-effort stand-in, not a
    verbatim quote.
"""

from __future__ import annotations

from typing import Optional

from backend.core.care_event import EventType, TemporalPrecision, to_frontend_status

from .serialization import CareEventRecord

# Canonical EventType -> frontend CareEventType (frontend/src/data/types.ts).
# The frontend's vocabulary is a strict subset of the canonical one, so
# every canonical type must map to *something* the frontend already knows
# how to render - never a value outside CareEventType.
_FRONTEND_TYPE = {
    EventType.MEDICATION: "medication",
    EventType.OBSERVATION: "observation",
    EventType.CONCERN: "concern",
    EventType.APPOINTMENT: "appointment",
    EventType.VITAL: "vital",
    EventType.ROUTINE: "routine",
    EventType.SYMPTOM: "observation",
    EventType.CARE_ACTION: "routine",
    EventType.OTHER: "observation",
}

# Only set for canonical types the frontend vocabulary collapses into a
# broader bucket above - gives the UI's categoryLabel override a chance to
# show the more specific canonical type instead of just "Observation" /
# "Routine". Types that already map 1:1 (medication, concern, ...) get no
# override; CATEGORY_META's default label is already correct for them.
_CATEGORY_LABEL_OVERRIDE = {
    EventType.SYMPTOM: "Symptom",
    EventType.CARE_ACTION: "Care action",
    EventType.OTHER: "Other",
}


def _occurred_at_iso(record: CareEventRecord) -> str:
    """The frontend's `occurredAt` is sorted and formatted as a real
    instant (see lib/format.ts, CareEventsContext's sort), so it must
    always be a valid ISO 8601 datetime - never a bare date, a relative
    phrase, or "unknown". EXACT_TIMESTAMP is used as-is.

    DATE is widened to *noon* UTC on that date, not midnight UTC. Midnight
    UTC shifts to the PREVIOUS calendar day once rendered in any timezone
    west of UTC (most of the Americas), which misrepresents a known date
    as a different date in the caregiver's own browser - exactly the
    "DATE precision must not shift the user's calendar day" bug the
    forensic audit found. Noon UTC keeps the same calendar date across the
    entire practically-occurring timezone range (UTC-11 through UTC+12,
    i.e. every real-world timezone) when rendered locally - it is still an
    approximation of "some time on this date", never a claim that the
    event happened at exactly noon, but it no longer corrupts the date
    itself, which is the one thing DATE precision actually promises.

    RELATIVE/UNKNOWN (where the canonical model genuinely doesn't know a
    real-world instant) falls back to this record's own `created_at` -
    always a well-formed instant, assigned once at first persistence -
    rather than fabricating a fake occurred_at. See occurred_at_precision()
    below: that fallback is now flagged in the DTO rather than left
    indistinguishable from a real reported time.
    """
    occurred_at = record.event.occurred_at
    if occurred_at.precision == TemporalPrecision.EXACT_TIMESTAMP and occurred_at.timestamp:
        return occurred_at.timestamp
    if occurred_at.precision == TemporalPrecision.DATE and occurred_at.date:
        return f"{occurred_at.date}T12:00:00Z"
    return record.created_at


def _occurred_at_precision(record: CareEventRecord) -> str:
    """Companion signal to `occurredAt`: which canonical TemporalPrecision
    actually produced that ISO string, so "exact_timestamp"/"date" (a real
    reported time) can be told apart from "relative"/"unknown" (a
    fallback to processing time, not a reported time) without the
    frontend having to guess from the ISO string alone. Sourced directly
    from the canonical TemporalPrecision enum - never fabricated, never
    collapsed - so this never claims more precision than extraction
    actually captured."""
    return record.event.occurred_at.precision.value


def _evidence_dto(record: CareEventRecord) -> Optional[dict]:
    if not record.event.evidence:
        return None
    evidence = record.event.evidence[0]
    duration_seconds = None
    if evidence.start_time is not None and evidence.end_time is not None:
        duration_seconds = evidence.end_time - evidence.start_time
    return {
        "transcript": record.event.summary,
        "segmentId": evidence.segment_id,
        "startTime": evidence.start_time,
        "endTime": evidence.end_time,
        "durationSeconds": duration_seconds,
    }


def _verification_reason_dto(record: CareEventRecord) -> Optional[str]:
    reason = record.event.verification_reason
    if reason is None:
        return None
    return reason.detail or reason.code.value.replace("_", " ")


def care_event_to_dto(record: CareEventRecord) -> dict:
    """The canonical -> frontend mapping. Returns a plain JSON-serializable
    dict matching frontend/src/data/types.ts's CareEvent shape exactly -
    never a raw DynamoDB item, never internal-only fields (extraction_version,
    caregiver_id, transcript_id, claim_stance, source_type, review_state are
    all deliberately left out; `status` is the frontend's one collapsed view
    of the latter three, produced by the existing to_frontend_status adapter)."""
    event = record.event
    status = to_frontend_status(event.review_state, event.claim_stance, event.source_type)
    return {
        "id": event.event_id,
        "type": _FRONTEND_TYPE[event.event_type],
        "categoryLabel": _CATEGORY_LABEL_OVERRIDE.get(event.event_type),
        "title": event.summary,
        "summary": event.summary,
        "whatHappened": event.summary,
        "occurredAt": _occurred_at_iso(record),
        "occurredAtPrecision": _occurred_at_precision(record),
        "reportedBy": event.reported_by or "Caregiver",
        "status": status.value,
        "evidence": _evidence_dto(record),
        "verificationReason": _verification_reason_dto(record),
    }
