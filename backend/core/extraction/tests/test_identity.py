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
from backend.core.extraction import EXTRACTION_SCHEMA_VERSION, assign_event_ids, event_fingerprint


def make_event(
    event_id="e",
    event_type=EventType.MEDICATION,
    subject="Dad",
    summary="Dad took his medicine",
    claim_stance=ClaimStance.ASSERTED,
    source_type=SourceType.FIRSTHAND,
    review_state=ReviewState.UNREVIEWED,
    occurred_at=None,
    evidence_segment_ids=None,
    reported_by=None,
) -> CareEvent:
    return CareEvent(
        event_id=event_id,
        event_type=event_type,
        subject=subject,
        summary=summary,
        claim_stance=claim_stance,
        source_type=source_type,
        review_state=review_state,
        occurred_at=occurred_at if occurred_at is not None else TemporalInfo.unknown(),
        evidence=[Evidence(sid) for sid in (evidence_segment_ids if evidence_segment_ids is not None else ["s1"])],
        reported_by=reported_by,
    )


def relative_time(expression: str) -> TemporalInfo:
    return TemporalInfo(precision=TemporalPrecision.RELATIVE, expression=expression)


class TestEventFingerprint:
    def test_same_event_same_transcript_same_version_same_fingerprint(self):
        a = event_fingerprint(make_event(), "t1")
        b = event_fingerprint(make_event(), "t1")
        assert a == b

    def test_different_transcript_id_different_fingerprint(self):
        a = event_fingerprint(make_event(), "t1")
        b = event_fingerprint(make_event(), "t2")
        assert a != b

    def test_different_extraction_version_different_fingerprint(self):
        a = event_fingerprint(make_event(), "t1", extraction_version="care_event_v2")
        b = event_fingerprint(make_event(), "t1", extraction_version="care_event_v3")
        assert a != b

    def test_different_subject_different_fingerprint(self):
        a = event_fingerprint(make_event(subject="Dad"), "t1")
        b = event_fingerprint(make_event(subject="Mom"), "t1")
        assert a != b

    def test_different_event_type_different_fingerprint(self):
        a = event_fingerprint(make_event(event_type=EventType.MEDICATION), "t1")
        b = event_fingerprint(make_event(event_type=EventType.APPOINTMENT), "t1")
        assert a != b

    def test_different_claim_stance_different_fingerprint(self):
        a = event_fingerprint(make_event(claim_stance=ClaimStance.ASSERTED), "t1")
        b = event_fingerprint(make_event(claim_stance=ClaimStance.NEGATED), "t1")
        assert a != b

    def test_different_temporal_identity_different_fingerprint(self):
        a = event_fingerprint(make_event(occurred_at=relative_time("8am")), "t1")
        b = event_fingerprint(make_event(occurred_at=relative_time("9am")), "t1")
        assert a != b

    def test_different_evidence_different_fingerprint(self):
        a = event_fingerprint(make_event(evidence_segment_ids=["s1"]), "t1")
        b = event_fingerprint(make_event(evidence_segment_ids=["s2"]), "t1")
        assert a != b

    def test_evidence_order_does_not_affect_fingerprint(self):
        a = event_fingerprint(make_event(evidence_segment_ids=["s1", "s2"]), "t1")
        b = event_fingerprint(make_event(evidence_segment_ids=["s2", "s1"]), "t1")
        assert a == b

    def test_duplicate_evidence_ids_do_not_affect_fingerprint(self):
        a = event_fingerprint(make_event(evidence_segment_ids=["s1", "s2"]), "t1")
        b = event_fingerprint(make_event(evidence_segment_ids=["s1", "s1", "s2"]), "t1")
        assert a == b

    def test_subject_normalization_ignores_case_and_whitespace(self):
        a = event_fingerprint(make_event(subject="Dad"), "t1")
        b = event_fingerprint(make_event(subject="  dad  "), "t1")
        assert a == b

    def test_summary_text_does_not_affect_fingerprint(self):
        # Wording may legitimately vary between equivalent extractions of
        # the same real event - identity must not change because of it.
        a = event_fingerprint(make_event(summary="Dad took his medicine"), "t1")
        b = event_fingerprint(make_event(summary="Dad took medicine this morning, apparently"), "t1")
        assert a == b

    def test_event_id_itself_does_not_affect_fingerprint(self):
        a = event_fingerprint(make_event(event_id="whatever-1"), "t1")
        b = event_fingerprint(make_event(event_id="something-else"), "t1")
        assert a == b


class TestAssignEventIds:
    def test_same_events_same_ids(self):
        events = [make_event(event_type=EventType.MEDICATION), make_event(event_type=EventType.SYMPTOM)]
        first = assign_event_ids(events, "t1")
        second = assign_event_ids(events, "t1")
        assert first == second

    def test_ids_are_not_random_uuids(self):
        events = [make_event()]
        first = assign_event_ids(events, "t1")
        second = assign_event_ids(events, "t1")
        assert first == second  # reproducible, not merely unique

    def test_reordering_events_preserves_id_per_logical_event(self):
        medication = make_event(event_id="a", event_type=EventType.MEDICATION, evidence_segment_ids=["s1"])
        symptom = make_event(event_id="b", event_type=EventType.SYMPTOM, evidence_segment_ids=["s2"])

        extraction_a = [medication, symptom]
        extraction_b = [symptom, medication]

        ids_a = dict(zip([e.event_type for e in extraction_a], assign_event_ids(extraction_a, "t1")))
        ids_b = dict(zip([e.event_type for e in extraction_b], assign_event_ids(extraction_b, "t1")))

        assert ids_a[EventType.MEDICATION] == ids_b[EventType.MEDICATION]
        assert ids_a[EventType.SYMPTOM] == ids_b[EventType.SYMPTOM]
        assert ids_a[EventType.MEDICATION] != ids_a[EventType.SYMPTOM]

    def test_different_transcript_ids_yield_different_ids(self):
        events = [make_event()]
        ids_t1 = assign_event_ids(events, "t1")
        ids_t2 = assign_event_ids(events, "t2")
        assert ids_t1 != ids_t2

    def test_different_extraction_versions_yield_different_ids(self):
        events = [make_event()]
        ids_v2 = assign_event_ids(events, "t1", extraction_version="care_event_v2")
        ids_v3 = assign_event_ids(events, "t1", extraction_version="care_event_v3")
        assert ids_v2 != ids_v3

    def test_default_version_matches_module_constant(self):
        events = [make_event()]
        default = assign_event_ids(events, "t1")
        explicit = assign_event_ids(events, "t1", extraction_version=EXTRACTION_SCHEMA_VERSION)
        assert default == explicit


class TestCollisionHandling:
    def test_two_genuinely_identical_events_get_distinct_ids(self):
        a = make_event(summary="First version of the note")
        b = make_event(summary="Second version of the note")
        ids = assign_event_ids([a, b], "t1")
        assert ids[0] != ids[1]
        assert len(set(ids)) == 2

    def test_collision_disambiguation_is_order_independent(self):
        a = make_event(summary="Alpha")
        b = make_event(summary="Beta")
        forward = assign_event_ids([a, b], "t1")
        backward = assign_event_ids([b, a], "t1")
        # The SET of ids assigned to the collision group is identical
        # either way, and each event's own id follows it regardless of
        # which position it was passed in.
        assert set(forward) == set(backward)
        id_for_a_forward = forward[0]
        id_for_a_backward = backward[1]
        assert id_for_a_forward == id_for_a_backward

    def test_three_way_collision_all_distinct(self):
        events = [make_event(summary=f"Version {i}") for i in range(3)]
        ids = assign_event_ids(events, "t1")
        assert len(set(ids)) == 3

    def test_non_colliding_events_unaffected_by_a_collision_elsewhere_in_the_batch(self):
        colliding_a = make_event(event_type=EventType.MEDICATION, summary="First")
        colliding_b = make_event(event_type=EventType.MEDICATION, summary="Second")
        unrelated = make_event(event_type=EventType.APPOINTMENT, evidence_segment_ids=["s2"])

        with_collision = assign_event_ids([colliding_a, colliding_b, unrelated], "t1")
        without_collision = assign_event_ids([unrelated], "t1")

        assert with_collision[2] == without_collision[0]
