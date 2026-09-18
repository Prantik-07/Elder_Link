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
from backend.core.persistence import CareContext, from_item, to_item


def make_event(**overrides) -> CareEvent:
    defaults = dict(
        event_id="ce_abc123",
        event_type=EventType.MEDICATION,
        subject="Dad",
        summary="Dad took his medicine",
        claim_stance=ClaimStance.ASSERTED,
        source_type=SourceType.FIRSTHAND,
        review_state=ReviewState.UNREVIEWED,
        occurred_at=TemporalInfo(precision=TemporalPrecision.RELATIVE, expression="8am"),
        evidence=[Evidence("s1")],
    )
    defaults.update(overrides)
    return CareEvent(**defaults)


def make_context(**overrides) -> CareContext:
    defaults = dict(care_recipient_id="patient-1", transcript_id="transcript-1", caregiver_id=None)
    defaults.update(overrides)
    return CareContext(**defaults)


class TestRoundTrip:
    def test_plain_event_round_trips(self):
        event = make_event()
        context = make_context()
        item = to_item(event, context, "care_event_v2", created_at="2026-01-01T00:00:00Z", updated_at="2026-01-01T00:00:00Z")
        record = from_item(item)
        assert record.event == event
        assert record.context == context
        assert record.extraction_version == "care_event_v2"

    def test_secondhand_event_with_reported_by_round_trips(self):
        event = make_event(
            event_type=EventType.CONCERN,
            source_type=SourceType.SECONDHAND,
            reported_by="sister",
            review_state=ReviewState.NEEDS_VERIFICATION,
            verification_reason=VerificationReason(VerificationReasonCode.SECONDHAND_REPORT, detail="via sister"),
        )
        context = make_context()
        item = to_item(event, context, "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.reported_by == "sister"
        assert record.event.verification_reason.code == VerificationReasonCode.SECONDHAND_REPORT
        assert record.event.verification_reason.detail == "via sister"

    def test_none_verification_reason_round_trips_as_none(self):
        event = make_event(verification_reason=None)
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.verification_reason is None

    def test_multi_segment_evidence_preserved_in_order(self):
        event = make_event(evidence=[Evidence("s2"), Evidence("s1"), Evidence("s2")])
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        # Order AND duplicates preserved exactly - deduplication is an
        # identity-fingerprint concern (Phase 4.1), not a persistence one.
        assert [e.segment_id for e in record.event.evidence] == ["s2", "s1", "s2"]

    def test_evidence_timestamps_survive_decimal_conversion(self):
        event = make_event(evidence=[Evidence("s1", start_time=1.5, end_time=3.25)])
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.evidence[0].start_time == 1.5
        assert record.event.evidence[0].end_time == 3.25
        assert isinstance(record.event.evidence[0].start_time, float)

    def test_evidence_without_timestamps_round_trips_as_none(self):
        event = make_event(evidence=[Evidence("s1")])
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.evidence[0].start_time is None
        assert record.event.evidence[0].end_time is None

    def test_exact_timestamp_precision_round_trips(self):
        event = make_event(occurred_at=TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP, timestamp="2026-01-01T08:00:00Z"))
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.occurred_at.precision == TemporalPrecision.EXACT_TIMESTAMP
        assert record.event.occurred_at.timestamp == "2026-01-01T08:00:00Z"

    def test_date_precision_round_trips(self):
        event = make_event(occurred_at=TemporalInfo(precision=TemporalPrecision.DATE, date="2026-01-01"))
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.occurred_at.precision == TemporalPrecision.DATE
        assert record.event.occurred_at.date == "2026-01-01"

    def test_unknown_precision_round_trips_with_no_stray_fields(self):
        event = make_event(occurred_at=TemporalInfo.unknown())
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.occurred_at.precision == TemporalPrecision.UNKNOWN
        assert record.event.occurred_at.timestamp is None
        assert record.event.occurred_at.date is None
        assert record.event.occurred_at.expression is None

    def test_negated_claim_stance_round_trips(self):
        event = make_event(claim_stance=ClaimStance.NEGATED, summary="Dad did not miss his medication")
        item = to_item(event, make_context(), "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.event.claim_stance == ClaimStance.NEGATED

    def test_care_context_with_caregiver_id_round_trips(self):
        context = make_context(caregiver_id="caregiver-42")
        item = to_item(make_event(), context, "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.context.caregiver_id == "caregiver-42"

    def test_care_context_without_caregiver_id_round_trips_as_none(self):
        context = make_context(caregiver_id=None)
        item = to_item(make_event(), context, "care_event_v2", "t1", "t1")
        record = from_item(item)
        assert record.context.caregiver_id is None


class TestItemKeys:
    def test_item_key_derived_from_context_and_event_id(self):
        item = to_item(make_event(event_id="ce_xyz"), make_context(care_recipient_id="p1"), "care_event_v2", "t1", "t1")
        assert item["pk"] == "PATIENT#p1"
        assert item["sk"] == "EVENT#ce_xyz"

    def test_transcript_id_and_event_id_are_top_level_for_gsi(self):
        item = to_item(make_event(event_id="ce_xyz"), make_context(transcript_id="transcript-9"), "care_event_v2", "t1", "t1")
        assert item["transcript_id"] == "transcript-9"
        assert item["event_id"] == "ce_xyz"
