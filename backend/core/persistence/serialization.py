"""Deterministic, lossless serialization between the canonical CareEvent
and a DynamoDB item.

Round-trip rule: CareEvent -> item -> CareEvent must preserve every
field's meaning and value exactly. Nothing here performs a semantic
transformation - the only conversions are representation changes forced
by DynamoDB's type system:

  - enums are stored as their canonical string .value (never a display
    label, never re-cased).
  - TemporalInfo is stored as a Map with all four sub-fields, so precision
    and whichever value field is populated both survive intact - and
    absent fields are None. Deserializing gives back the exact same
    TemporalPrecision + value combination.
  - Evidence is stored as a List of Maps, order preserved, one entry per
    Evidence - never deduplicated or reordered (deduplication only ever
    happens in the Phase 4.1 identity fingerprint, not here).
  - float `start_time`/`end_time` on Evidence become Decimal for storage
    (DynamoDB's Number type has no native float, and boto3's Table
    resource rejects a plain Python float outright) and Decimal -> float
    on the way back. This is a type-system requirement, not a precision
    change: str(float) round-trips through Decimal exactly for the
    ordinary timestamp values this schema uses.
  - verification_reason is stored as a Map ({code, detail}) or omitted
    entirely when None - never a bare string, matching the Phase 4
    structured VerificationReason.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from backend.core.care_event import (
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
)

from .context import CareContext
from .keys import event_sk, patient_pk


@dataclass
class CareEventRecord:
    """A CareEvent as persisted: the canonical event, the context it was
    persisted under, the extraction version that produced it, and the two
    audit timestamps. Not identical to a DynamoDB item (see to_item) -
    this is the Python-side shape callers work with."""

    event: CareEvent
    context: CareContext
    extraction_version: str
    created_at: str
    updated_at: str


def _float_to_decimal(value: Optional[float]) -> Optional[Decimal]:
    return None if value is None else Decimal(str(value))


def _decimal_to_float(value) -> Optional[float]:
    return None if value is None else float(value)


def _evidence_to_item(evidence: list[Evidence]) -> list[dict]:
    return [
        {
            "segment_id": e.segment_id,
            "start_time": _float_to_decimal(e.start_time),
            "end_time": _float_to_decimal(e.end_time),
        }
        for e in evidence
    ]


def _evidence_from_item(items: list[dict]) -> list[Evidence]:
    return [
        Evidence(
            segment_id=i["segment_id"],
            start_time=_decimal_to_float(i.get("start_time")),
            end_time=_decimal_to_float(i.get("end_time")),
        )
        for i in items
    ]


def _temporal_to_item(t: TemporalInfo) -> dict:
    return {
        "precision": t.precision.value,
        "timestamp": t.timestamp,
        "date": t.date,
        "expression": t.expression,
    }


def _temporal_from_item(item: dict) -> TemporalInfo:
    return TemporalInfo(
        precision=TemporalPrecision(item["precision"]),
        timestamp=item.get("timestamp"),
        date=item.get("date"),
        expression=item.get("expression"),
    )


def _verification_reason_to_item(vr: Optional[VerificationReason]) -> Optional[dict]:
    if vr is None:
        return None
    return {"code": vr.code.value, "detail": vr.detail}


def verification_reason_to_item(vr: Optional[VerificationReason]) -> Optional[dict]:
    """Public alias of _verification_reason_to_item, for callers outside
    this module that need to serialize a single field (e.g.
    CareEventRepository.update_review_state's targeted UpdateItem) without
    round-tripping a whole CareEvent through to_item."""
    return _verification_reason_to_item(vr)


def _verification_reason_from_item(item: Optional[dict]) -> Optional[VerificationReason]:
    if item is None:
        return None
    return VerificationReason(code=VerificationReasonCode(item["code"]), detail=item.get("detail"))


def to_item(
    event: CareEvent,
    context: CareContext,
    extraction_version: str,
    created_at: str,
    updated_at: str,
) -> dict:
    return {
        "pk": patient_pk(context.care_recipient_id),
        "sk": event_sk(event.event_id),
        "event_id": event.event_id,
        "care_recipient_id": context.care_recipient_id,
        "transcript_id": context.transcript_id,
        "caregiver_id": context.caregiver_id,
        "extraction_version": extraction_version,
        "event_type": event.event_type.value,
        "subject": event.subject,
        "summary": event.summary,
        "claim_stance": event.claim_stance.value,
        "source_type": event.source_type.value,
        "reported_by": event.reported_by,
        "review_state": event.review_state.value,
        "occurred_at": _temporal_to_item(event.occurred_at),
        "evidence": _evidence_to_item(event.evidence),
        "verification_reason": _verification_reason_to_item(event.verification_reason),
        "created_at": created_at,
        "updated_at": updated_at,
    }


def from_item(item: dict) -> CareEventRecord:
    event = CareEvent(
        event_id=item["event_id"],
        event_type=EventType(item["event_type"]),
        subject=item["subject"],
        summary=item["summary"],
        claim_stance=ClaimStance(item["claim_stance"]),
        source_type=SourceType(item["source_type"]),
        review_state=ReviewState(item["review_state"]),
        occurred_at=_temporal_from_item(item["occurred_at"]),
        evidence=_evidence_from_item(item["evidence"]),
        reported_by=item.get("reported_by"),
        verification_reason=_verification_reason_from_item(item.get("verification_reason")),
    )
    context = CareContext(
        care_recipient_id=item["care_recipient_id"],
        transcript_id=item["transcript_id"],
        caregiver_id=item.get("caregiver_id"),
    )
    return CareEventRecord(
        event=event,
        context=context,
        extraction_version=item["extraction_version"],
        created_at=item["created_at"],
        updated_at=item["updated_at"],
    )
