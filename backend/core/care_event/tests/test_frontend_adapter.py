from backend.core.care_event import (
    ClaimStance,
    FrontendCareEventStatus,
    ReviewState,
    SourceType,
    to_frontend_status,
)


class TestFrontendMapping:
    def test_verified_maps_to_verified(self):
        status = to_frontend_status(ReviewState.VERIFIED, ClaimStance.ASSERTED, SourceType.FIRSTHAND)
        assert status == FrontendCareEventStatus.VERIFIED

    def test_verified_maps_to_verified_regardless_of_claim_stance_or_source(self):
        # review_state is the authority here - it only ever becomes VERIFIED
        # through a real review action, never through extraction alone.
        status = to_frontend_status(ReviewState.VERIFIED, ClaimStance.UNCERTAIN, SourceType.SECONDHAND)
        assert status == FrontendCareEventStatus.VERIFIED

    def test_needs_verification_maps_to_needs_verification(self):
        status = to_frontend_status(ReviewState.NEEDS_VERIFICATION, ClaimStance.ASSERTED, SourceType.FIRSTHAND)
        assert status == FrontendCareEventStatus.NEEDS_VERIFICATION

    def test_unreviewed_uncertain_maps_to_uncertain(self):
        status = to_frontend_status(ReviewState.UNREVIEWED, ClaimStance.UNCERTAIN, SourceType.FIRSTHAND)
        assert status == FrontendCareEventStatus.UNCERTAIN

    def test_unreviewed_secondhand_maps_to_needs_verification(self):
        status = to_frontend_status(ReviewState.UNREVIEWED, ClaimStance.ASSERTED, SourceType.SECONDHAND)
        assert status == FrontendCareEventStatus.NEEDS_VERIFICATION

    def test_unreviewed_asserted_firsthand_maps_to_needs_verification_not_verified(self):
        # The critical safety property: extraction succeeding cleanly must
        # never present as "verified" to the frontend.
        status = to_frontend_status(ReviewState.UNREVIEWED, ClaimStance.ASSERTED, SourceType.FIRSTHAND)
        assert status == FrontendCareEventStatus.NEEDS_VERIFICATION
        assert status != FrontendCareEventStatus.VERIFIED

    def test_unreviewed_negated_firsthand_maps_to_needs_verification(self):
        status = to_frontend_status(ReviewState.UNREVIEWED, ClaimStance.NEGATED, SourceType.FIRSTHAND)
        assert status == FrontendCareEventStatus.NEEDS_VERIFICATION
