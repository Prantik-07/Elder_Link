"""Evaluation-harness-specific types.

CareEvent and TranscriptDocument are NOT redefined here - they're imported
from backend.core.care_event, the one canonical schema (see Phase 2). This
module only adds GoldenCase, which is purely a test-harness concept (a
transcript paired with the events it *should* produce) with no reason to
exist outside evaluation.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.core.care_event import CareEvent, TranscriptDocument

# Re-exported for convenience so callers can do `from evaluation.models
# import CareEvent, EventType, ...` without knowing the canonical package
# lives under backend.core.care_event.
from backend.core.care_event import (  # noqa: F401
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


@dataclass
class GoldenCase:
    case_id: str
    document: TranscriptDocument
    expected_events: list[CareEvent]
    notes: str

    @classmethod
    def from_dict(cls, data: dict) -> "GoldenCase":
        required = ("case_id", "document", "expected_events", "notes")
        missing = [k for k in required if k not in data]
        if missing:
            raise ValueError(f"Golden case missing required fields: {missing}")

        document = TranscriptDocument.from_dict(data["document"])
        segment_ids = document.segment_ids

        expected_events = [CareEvent.from_dict(e) for e in data["expected_events"]]
        for event in expected_events:
            unknown = set(event.evidence_segment_ids) - segment_ids
            if unknown:
                raise ValueError(
                    f"Case '{data['case_id']}': expected event references "
                    f"unknown segment id(s) {unknown}"
                )

        return cls(
            case_id=data["case_id"],
            document=document,
            expected_events=expected_events,
            notes=data["notes"],
        )
