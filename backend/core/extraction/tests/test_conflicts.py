from backend.core.care_event import (
    CareEvent,
    ClaimStance,
    Evidence,
    EventType,
    ReviewState,
    SourceType,
    TemporalInfo,
)
from backend.core.extraction import find_conflicting_event_ids


def make_event(event_id, event_type=EventType.MEDICATION, subject="Dad", claim_stance=ClaimStance.ASSERTED) -> CareEvent:
    return CareEvent(
        event_id=event_id,
        event_type=event_type,
        subject=subject,
        summary="summary",
        claim_stance=claim_stance,
        source_type=SourceType.FIRSTHAND,
        review_state=ReviewState.UNREVIEWED,
        occurred_at=TemporalInfo.unknown(),
        evidence=[Evidence("s1")],
    )


class TestConflictDetection:
    def test_same_type_subject_different_stance_conflicts(self):
        a = make_event("e1", claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", claim_stance=ClaimStance.NEGATED)
        assert find_conflicting_event_ids([a, b]) == {"e1", "e2"}

    def test_same_stance_does_not_conflict(self):
        a = make_event("e1", claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", claim_stance=ClaimStance.ASSERTED)
        assert find_conflicting_event_ids([a, b]) == set()

    def test_different_subject_does_not_conflict(self):
        a = make_event("e1", subject="Dad", claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", subject="Mom", claim_stance=ClaimStance.NEGATED)
        assert find_conflicting_event_ids([a, b]) == set()

    def test_different_event_type_does_not_conflict(self):
        a = make_event("e1", event_type=EventType.MEDICATION, claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", event_type=EventType.APPOINTMENT, claim_stance=ClaimStance.NEGATED)
        assert find_conflicting_event_ids([a, b]) == set()

    def test_subject_comparison_is_case_insensitive(self):
        a = make_event("e1", subject="dad", claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", subject="Dad", claim_stance=ClaimStance.UNCERTAIN)
        assert find_conflicting_event_ids([a, b]) == {"e1", "e2"}

    def test_three_way_conflict_flags_all_involved(self):
        a = make_event("e1", claim_stance=ClaimStance.ASSERTED)
        b = make_event("e2", claim_stance=ClaimStance.NEGATED)
        c = make_event("e3", claim_stance=ClaimStance.UNCERTAIN)
        assert find_conflicting_event_ids([a, b, c]) == {"e1", "e2", "e3"}

    def test_single_event_never_conflicts_with_itself(self):
        a = make_event("e1")
        assert find_conflicting_event_ids([a]) == set()

    def test_empty_list(self):
        assert find_conflicting_event_ids([]) == set()
