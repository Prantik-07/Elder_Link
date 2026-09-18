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
from backend.core.persistence.context import CareContext
from backend.core.persistence.frontend_dto import care_event_to_dto
from backend.core.persistence.serialization import CareEventRecord


def _record(**event_overrides) -> CareEventRecord:
    defaults = dict(
        event_id="ce_test123",
        event_type=EventType.MEDICATION,
        subject="Dad",
        summary="Dad may have missed his morning medication.",
        claim_stance=ClaimStance.UNCERTAIN,
        source_type=SourceType.FIRSTHAND,
        review_state=ReviewState.UNREVIEWED,
        occurred_at=TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP, timestamp="2024-01-01T06:32:00Z"),
        evidence=[Evidence(segment_id="test-note-seg-01", start_time=0.0, end_time=18.0)],
        reported_by="Anita",
    )
    defaults.update(event_overrides)
    event = CareEvent(**defaults)
    context = CareContext(care_recipient_id="demo-dad", transcript_id="test-note")
    return CareEventRecord(
        event=event,
        context=context,
        extraction_version="v1",
        created_at="2024-01-01T06:33:00Z",
        updated_at="2024-01-01T06:33:00Z",
    )


class TestCareEventToDto:
    def test_maps_core_fields(self):
        dto = care_event_to_dto(_record())
        assert dto["id"] == "ce_test123"
        assert dto["type"] == "medication"
        assert dto["title"] == "Dad may have missed his morning medication."
        assert dto["summary"] == "Dad may have missed his morning medication."
        assert dto["whatHappened"] == "Dad may have missed his morning medication."
        assert dto["reportedBy"] == "Anita"

    def test_missing_reported_by_falls_back_to_caregiver(self):
        dto = care_event_to_dto(_record(reported_by=None))
        assert dto["reportedBy"] == "Caregiver"

    def test_exact_timestamp_occurred_at_used_as_is(self):
        dto = care_event_to_dto(_record())
        assert dto["occurredAt"] == "2024-01-01T06:32:00Z"

    def test_date_precision_occurred_at_widened_to_midnight_utc(self):
        record = _record(occurred_at=TemporalInfo(precision=TemporalPrecision.DATE, date="2024-02-05"))
        dto = care_event_to_dto(record)
        assert dto["occurredAt"] == "2024-02-05T00:00:00Z"

    def test_unknown_precision_falls_back_to_created_at(self):
        record = _record(occurred_at=TemporalInfo.unknown())
        dto = care_event_to_dto(record)
        assert dto["occurredAt"] == "2024-01-01T06:33:00Z"

    def test_relative_precision_falls_back_to_created_at(self):
        record = _record(
            occurred_at=TemporalInfo(precision=TemporalPrecision.RELATIVE, expression="this morning")
        )
        dto = care_event_to_dto(record)
        assert dto["occurredAt"] == "2024-01-01T06:33:00Z"

    def test_evidence_maps_first_segment_with_duration(self):
        dto = care_event_to_dto(_record())
        assert dto["evidence"] == {
            "transcript": "Dad may have missed his morning medication.",
            "segmentId": "test-note-seg-01",
            "startTime": 0.0,
            "endTime": 18.0,
            "durationSeconds": 18.0,
        }

    def test_no_evidence_maps_to_none(self):
        dto = care_event_to_dto(_record(evidence=[]))
        assert dto["evidence"] is None

    def test_verification_reason_prefers_detail_over_code(self):
        record = _record(
            verification_reason=VerificationReason(
                code=VerificationReasonCode.EXPLICIT_UNCERTAINTY, detail="caregiver hedged"
            )
        )
        dto = care_event_to_dto(record)
        assert dto["verificationReason"] == "caregiver hedged"

    def test_verification_reason_falls_back_to_code_when_no_detail(self):
        record = _record(
            verification_reason=VerificationReason(code=VerificationReasonCode.SECONDHAND_REPORT)
        )
        dto = care_event_to_dto(record)
        assert dto["verificationReason"] == "secondhand report"

    def test_no_verification_reason_maps_to_none(self):
        dto = care_event_to_dto(_record(verification_reason=None))
        assert dto["verificationReason"] is None

    def test_status_uses_existing_frontend_adapter(self):
        # review_state=UNREVIEWED + claim_stance=UNCERTAIN -> "uncertain",
        # per to_frontend_status - this module must never invent its own
        # verification semantics.
        dto = care_event_to_dto(_record())
        assert dto["status"] == "uncertain"

    def test_review_state_verified_maps_to_verified_status(self):
        dto = care_event_to_dto(_record(review_state=ReviewState.VERIFIED))
        assert dto["status"] == "verified"

    def test_canonical_type_not_in_frontend_vocabulary_gets_category_label_override(self):
        dto = care_event_to_dto(_record(event_type=EventType.SYMPTOM))
        assert dto["type"] == "observation"
        assert dto["categoryLabel"] == "Symptom"

    def test_care_action_maps_to_routine_with_override_label(self):
        dto = care_event_to_dto(_record(event_type=EventType.CARE_ACTION))
        assert dto["type"] == "routine"
        assert dto["categoryLabel"] == "Care action"

    def test_type_already_in_frontend_vocabulary_has_no_category_label_override(self):
        dto = care_event_to_dto(_record(event_type=EventType.CONCERN))
        assert dto["type"] == "concern"
        assert dto["categoryLabel"] is None

    def test_dto_never_leaks_internal_persistence_fields(self):
        dto = care_event_to_dto(_record())
        leaked_fields = {
            "claim_stance",
            "source_type",
            "review_state",
            "extraction_version",
            "caregiver_id",
            "transcript_id",
            "pk",
            "sk",
        }
        assert not leaked_fields & dto.keys()
