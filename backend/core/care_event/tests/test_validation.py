from backend.core.care_event import (
    CareEvent,
    ClaimStance,
    Evidence,
    EventType,
    ReviewState,
    SourceType,
    TemporalInfo,
    TemporalPrecision,
    TranscriptDocument,
    TranscriptSegment,
    VerificationReason,
    VerificationReasonCode,
    validate_care_event,
)


def make_document() -> TranscriptDocument:
    return TranscriptDocument(
        transcript_id="t1",
        full_text="Dad took his pills. He has an appointment Friday.",
        segments=[
            TranscriptSegment("s1", "Dad took his pills."),
            TranscriptSegment("s2", "He has an appointment Friday."),
        ],
    )


def make_event(**overrides) -> CareEvent:
    defaults = dict(
        event_id="e1",
        event_type=EventType.MEDICATION,
        subject="Dad",
        summary="Dad took his medicine",
        claim_stance=ClaimStance.ASSERTED,
        source_type=SourceType.FIRSTHAND,
        review_state=ReviewState.UNREVIEWED,
        occurred_at=TemporalInfo.unknown(),
        evidence=[Evidence("s1")],
    )
    defaults.update(overrides)
    return CareEvent(**defaults)


class TestValidEvent:
    def test_well_formed_event_has_no_errors(self):
        errors = validate_care_event(make_event(), make_document())
        assert errors == []


class TestMissingEventId:
    def test_empty_event_id_rejected(self):
        errors = validate_care_event(make_event(event_id=""), make_document())
        assert any("event_id" in e for e in errors)

    def test_whitespace_only_event_id_rejected(self):
        errors = validate_care_event(make_event(event_id="   "), make_document())
        assert any("event_id" in e for e in errors)


class TestMissingEvidence:
    def test_empty_evidence_list_rejected(self):
        errors = validate_care_event(make_event(evidence=[]), make_document())
        assert any("evidence" in e for e in errors)


class TestInvalidEvidenceId:
    def test_evidence_referencing_nonexistent_segment_rejected(self):
        errors = validate_care_event(make_event(evidence=[Evidence("s99")]), make_document())
        assert any("nonexistent segment" in e for e in errors)

    def test_one_valid_one_invalid_still_flags_the_invalid_one(self):
        errors = validate_care_event(make_event(evidence=[Evidence("s1"), Evidence("s99")]), make_document())
        assert any("s99" in e for e in errors)


class TestImpossibleTemporalStructures:
    def test_exact_timestamp_precision_without_timestamp_rejected(self):
        t = TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP)
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert any("timestamp is required" in e for e in errors)

    def test_date_precision_without_date_rejected(self):
        t = TemporalInfo(precision=TemporalPrecision.DATE)
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert any("date is required" in e for e in errors)

    def test_relative_precision_without_expression_rejected(self):
        t = TemporalInfo(precision=TemporalPrecision.RELATIVE)
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert any("expression is required" in e for e in errors)

    def test_unknown_precision_with_stray_expression_rejected(self):
        t = TemporalInfo(precision=TemporalPrecision.UNKNOWN, expression="this morning")
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert any("unknown" in e for e in errors)

    def test_exact_timestamp_with_extra_date_field_rejected(self):
        t = TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP, timestamp="2026-01-01T08:00:00Z", date="2026-01-01")
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert any("must not set date" in e for e in errors)

    def test_valid_relative_temporal_has_no_errors(self):
        t = TemporalInfo(precision=TemporalPrecision.RELATIVE, expression="this morning")
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert errors == []

    def test_valid_exact_timestamp_has_no_errors(self):
        t = TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP, timestamp="2026-01-01T08:00:00Z")
        errors = validate_care_event(make_event(occurred_at=t), make_document())
        assert errors == []


class TestVerificationReasonRequiredForNeedsVerification:
    def test_needs_verification_without_reason_rejected(self):
        errors = validate_care_event(
            make_event(review_state=ReviewState.NEEDS_VERIFICATION, verification_reason=None),
            make_document(),
        )
        assert any("verification_reason.code is required" in e for e in errors)

    def test_needs_verification_with_reason_is_valid(self):
        errors = validate_care_event(
            make_event(
                review_state=ReviewState.NEEDS_VERIFICATION,
                verification_reason=VerificationReason(VerificationReasonCode.EXPLICIT_UNCERTAINTY),
            ),
            make_document(),
        )
        assert errors == []

    def test_unreviewed_without_reason_is_valid(self):
        errors = validate_care_event(
            make_event(review_state=ReviewState.UNREVIEWED, verification_reason=None),
            make_document(),
        )
        assert errors == []

    def test_verification_reason_carries_optional_detail(self):
        reason = VerificationReason(VerificationReasonCode.SECONDHAND_REPORT, detail="reported by sister, not witnessed directly")
        errors = validate_care_event(
            make_event(review_state=ReviewState.NEEDS_VERIFICATION, verification_reason=reason),
            make_document(),
        )
        assert errors == []

    def test_from_dict_accepts_bare_code_string(self):
        reason = VerificationReason.from_dict("explicit_uncertainty")
        assert reason.code == VerificationReasonCode.EXPLICIT_UNCERTAINTY
        assert reason.detail is None

    def test_from_dict_accepts_code_and_detail_object(self):
        reason = VerificationReason.from_dict({"code": "secondhand_report", "detail": "via sister"})
        assert reason.code == VerificationReasonCode.SECONDHAND_REPORT
        assert reason.detail == "via sister"

    def test_invalid_code_rejected(self):
        import pytest

        with pytest.raises(ValueError):
            VerificationReason.from_dict("not_a_real_code")


class TestEvidenceTimestampConsistency:
    def _document_with_timed_segment(self) -> TranscriptDocument:
        return TranscriptDocument(
            transcript_id="t1",
            full_text="Dad took his pills.",
            segments=[TranscriptSegment("s1", "Dad took his pills.", start_time=10.0, end_time=20.0)],
        )

    def test_evidence_span_within_segment_span_is_valid(self):
        errors = validate_care_event(
            make_event(evidence=[Evidence("s1", start_time=12.0, end_time=18.0)]),
            self._document_with_timed_segment(),
        )
        assert errors == []

    def test_evidence_start_before_segment_start_rejected(self):
        errors = validate_care_event(
            make_event(evidence=[Evidence("s1", start_time=5.0, end_time=15.0)]),
            self._document_with_timed_segment(),
        )
        assert any("falls outside" in e for e in errors)

    def test_evidence_end_after_segment_end_rejected(self):
        errors = validate_care_event(
            make_event(evidence=[Evidence("s1", start_time=12.0, end_time=25.0)]),
            self._document_with_timed_segment(),
        )
        assert any("falls outside" in e for e in errors)

    def test_evidence_start_after_end_rejected(self):
        errors = validate_care_event(
            make_event(evidence=[Evidence("s1", start_time=18.0, end_time=12.0)]),
            self._document_with_timed_segment(),
        )
        assert any("is after end_time" in e for e in errors)

    def test_no_timestamps_on_segment_skips_check(self):
        # make_document()'s segments carry no timestamps - Day 1's current
        # reality - so evidence timestamps (if any were set) can't be
        # checked against anything and must not be rejected for that reason.
        errors = validate_care_event(
            make_event(evidence=[Evidence("s1", start_time=999.0, end_time=1000.0)]),
            make_document(),
        )
        assert errors == []


class TestDoesNotRejectValidUncertainty:
    def test_negated_secondhand_is_valid(self):
        errors = validate_care_event(
            make_event(
                claim_stance=ClaimStance.NEGATED,
                source_type=SourceType.SECONDHAND,
                reported_by="sister",
            ),
            make_document(),
        )
        assert errors == []

    def test_secondhand_without_reported_by_is_still_valid(self):
        # A caregiver may legitimately not know exactly who told them -
        # reported_by is not required just because source_type is secondhand.
        errors = validate_care_event(
            make_event(source_type=SourceType.SECONDHAND, reported_by=None),
            make_document(),
        )
        assert errors == []
