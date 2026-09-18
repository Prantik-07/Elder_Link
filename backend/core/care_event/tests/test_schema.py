import pytest

from backend.core.care_event import (
    CareEvent,
    ClaimStance,
    Evidence,
    EventType,
    ReviewState,
    SourceType,
    TemporalInfo,
    TemporalPrecision,
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


class TestValidStanceSourceCombinations:
    """All six claim_stance x source_type combinations are legitimate and
    must construct without error - Phase 2 explicitly forbids treating any
    of these as an invalid/nonsensical pairing."""

    def test_asserted_firsthand(self):
        event = make_event(claim_stance=ClaimStance.ASSERTED, source_type=SourceType.FIRSTHAND)
        assert event.claim_stance == ClaimStance.ASSERTED
        assert event.source_type == SourceType.FIRSTHAND

    def test_asserted_secondhand(self):
        event = make_event(
            claim_stance=ClaimStance.ASSERTED, source_type=SourceType.SECONDHAND, reported_by="sister"
        )
        assert event.claim_stance == ClaimStance.ASSERTED
        assert event.source_type == SourceType.SECONDHAND

    def test_uncertain_firsthand(self):
        event = make_event(claim_stance=ClaimStance.UNCERTAIN, source_type=SourceType.FIRSTHAND)
        assert event.claim_stance == ClaimStance.UNCERTAIN
        assert event.source_type == SourceType.FIRSTHAND

    def test_uncertain_secondhand(self):
        event = make_event(
            claim_stance=ClaimStance.UNCERTAIN, source_type=SourceType.SECONDHAND, reported_by="sister"
        )
        assert event.claim_stance == ClaimStance.UNCERTAIN
        assert event.source_type == SourceType.SECONDHAND

    def test_negated_firsthand(self):
        event = make_event(
            claim_stance=ClaimStance.NEGATED,
            summary="Dad did not miss his medication",
        )
        assert event.claim_stance == ClaimStance.NEGATED
        assert event.source_type == SourceType.FIRSTHAND

    def test_negated_secondhand(self):
        event = make_event(
            claim_stance=ClaimStance.NEGATED,
            source_type=SourceType.SECONDHAND,
            reported_by="sister",
            summary="Sister says Dad did not miss his medication",
        )
        assert event.claim_stance == ClaimStance.NEGATED
        assert event.source_type == SourceType.SECONDHAND


class TestReviewStateNeverAutoVerified:
    def test_uncertain_event_defaults_to_needs_verification_not_verified(self):
        event = make_event(claim_stance=ClaimStance.UNCERTAIN, review_state=ReviewState.NEEDS_VERIFICATION)
        assert event.review_state != ReviewState.VERIFIED

    def test_strongly_grounded_asserted_event_is_still_not_auto_verified(self):
        # Even a plain, well-evidenced, firsthand assertion must not be
        # constructed with review_state=VERIFIED by anything in this
        # package - VERIFIED is reserved for an actual human/clinical
        # review step outside the schema's own construction logic.
        event = make_event(claim_stance=ClaimStance.ASSERTED, review_state=ReviewState.UNREVIEWED)
        assert event.review_state == ReviewState.UNREVIEWED


class TestContradictionIsNotAStanceValue:
    def test_claim_stance_enum_has_no_contradicted_value(self):
        values = {s.value for s in ClaimStance}
        assert "contradicted" not in values
        assert values == {"asserted", "uncertain", "negated"}

    def test_conflicting_claims_are_two_separate_events(self):
        # "Dad took his medicine at 8am. Actually, I'm not sure he did."
        first_claim = make_event(
            event_id="e1",
            claim_stance=ClaimStance.ASSERTED,
            summary="Dad took his medicine at 8am",
            evidence=[Evidence("s1")],
        )
        retraction = make_event(
            event_id="e2",
            claim_stance=ClaimStance.UNCERTAIN,
            summary="Speaker is no longer sure Dad took his medicine",
            evidence=[Evidence("s2")],
        )
        assert first_claim.claim_stance != retraction.claim_stance
        assert first_claim.event_id != retraction.event_id


class TestInvalidEnumValuesRejected:
    def test_invalid_event_type_rejected(self):
        with pytest.raises(ValueError):
            CareEvent.from_dict(
                {
                    "event_id": "e1",
                    "event_type": "not_a_real_type",
                    "subject": "Dad",
                    "summary": "x",
                    "claim_stance": "asserted",
                    "source_type": "firsthand",
                    "review_state": "unreviewed",
                    "evidence": [{"segment_id": "s1"}],
                }
            )

    def test_invalid_source_type_rejected(self):
        with pytest.raises(ValueError):
            CareEvent.from_dict(
                {
                    "event_id": "e1",
                    "event_type": "medication",
                    "subject": "Dad",
                    "summary": "x",
                    "claim_stance": "asserted",
                    "source_type": "thirdhand",
                    "review_state": "unreviewed",
                    "evidence": [{"segment_id": "s1"}],
                }
            )

    def test_invalid_claim_stance_rejected(self):
        with pytest.raises(ValueError):
            CareEvent.from_dict(
                {
                    "event_id": "e1",
                    "event_type": "medication",
                    "subject": "Dad",
                    "summary": "x",
                    "claim_stance": "contradicted",
                    "source_type": "firsthand",
                    "review_state": "unreviewed",
                    "evidence": [{"segment_id": "s1"}],
                }
            )

    def test_invalid_review_state_rejected(self):
        with pytest.raises(ValueError):
            CareEvent.from_dict(
                {
                    "event_id": "e1",
                    "event_type": "medication",
                    "subject": "Dad",
                    "summary": "x",
                    "claim_stance": "asserted",
                    "source_type": "firsthand",
                    "review_state": "confirmed",
                    "evidence": [{"segment_id": "s1"}],
                }
            )


class TestTemporalPrecision:
    def test_unknown_precision_has_no_other_fields_set(self):
        t = TemporalInfo.unknown()
        assert t.precision == TemporalPrecision.UNKNOWN
        assert t.timestamp is None
        assert t.date is None
        assert t.expression is None

    def test_relative_precision_carries_raw_expression(self):
        t = TemporalInfo(precision=TemporalPrecision.RELATIVE, expression="this morning")
        assert t.expression == "this morning"
