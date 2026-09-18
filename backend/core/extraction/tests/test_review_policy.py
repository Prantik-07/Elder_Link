from backend.core.care_event import (
    ClaimStance,
    Evidence,
    ReviewState,
    SourceType,
    TranscriptDocument,
    TranscriptSegment,
    VerificationReasonCode,
)
from backend.core.extraction import derive_review_state


def document(segment_text: str = "Dad took his blood pressure medicine at 8am.") -> TranscriptDocument:
    return TranscriptDocument(transcript_id="t", full_text=segment_text, segments=[TranscriptSegment("s1", segment_text)])


class TestUncertainRoutesToNeedsVerification:
    def test_uncertain_claim_needs_verification_with_explicit_uncertainty_reason(self):
        review_state, reason = derive_review_state(
            ClaimStance.UNCERTAIN, SourceType.FIRSTHAND, [Evidence("s1")], document()
        )
        assert review_state == ReviewState.NEEDS_VERIFICATION
        assert reason.code == VerificationReasonCode.EXPLICIT_UNCERTAINTY


class TestSecondhandRoutesToNeedsVerification:
    def test_secondhand_source_needs_verification_with_secondhand_reason(self):
        review_state, reason = derive_review_state(
            ClaimStance.ASSERTED, SourceType.SECONDHAND, [Evidence("s1")], document()
        )
        assert review_state == ReviewState.NEEDS_VERIFICATION
        assert reason.code == VerificationReasonCode.SECONDHAND_REPORT


class TestConflictRoutesToNeedsVerification:
    def test_conflicting_sibling_needs_verification_with_conflicting_reason(self):
        review_state, reason = derive_review_state(
            ClaimStance.ASSERTED, SourceType.FIRSTHAND, [Evidence("s1")], document(), has_conflict=True
        )
        assert review_state == ReviewState.NEEDS_VERIFICATION
        assert reason.code == VerificationReasonCode.CONFLICTING_INFORMATION


class TestWeakEvidenceRoutesToNeedsVerification:
    def test_very_short_supporting_text_is_insufficient_evidence(self):
        doc = document(segment_text="Ok.")
        review_state, reason = derive_review_state(
            ClaimStance.ASSERTED, SourceType.FIRSTHAND, [Evidence("s1")], doc
        )
        assert review_state == ReviewState.NEEDS_VERIFICATION
        assert reason.code == VerificationReasonCode.INSUFFICIENT_EVIDENCE


class TestPlainConfidentClaimStaysUnreviewed:
    def test_asserted_firsthand_strong_evidence_no_conflict_is_unreviewed(self):
        review_state, reason = derive_review_state(
            ClaimStance.ASSERTED, SourceType.FIRSTHAND, [Evidence("s1")], document()
        )
        assert review_state == ReviewState.UNREVIEWED
        assert reason is None

    def test_negated_firsthand_strong_evidence_is_also_unreviewed(self):
        # A confident negation is not automatically suspect - it only needs
        # review if it's hedged, secondhand, conflicting, or weakly grounded.
        review_state, reason = derive_review_state(
            ClaimStance.NEGATED, SourceType.FIRSTHAND, [Evidence("s1")], document()
        )
        assert review_state == ReviewState.UNREVIEWED
        assert reason is None


class TestPolicyNeverProducesVerified:
    def test_no_combination_of_inputs_yields_verified(self):
        combinations = [
            (ClaimStance.ASSERTED, SourceType.FIRSTHAND, False),
            (ClaimStance.UNCERTAIN, SourceType.SECONDHAND, True),
            (ClaimStance.NEGATED, SourceType.UNKNOWN, False),
        ]
        for claim_stance, source_type, has_conflict in combinations:
            review_state, _reason = derive_review_state(
                claim_stance, source_type, [Evidence("s1")], document(), has_conflict=has_conflict
            )
            assert review_state != ReviewState.VERIFIED
