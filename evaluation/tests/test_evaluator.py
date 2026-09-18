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
)
from evaluation.evaluator import (
    Verdict,
    compute_evidence_scores,
    evaluate_case,
    match_events,
)
from evaluation.models import GoldenCase


def make_event(
    event_type=EventType.MEDICATION,
    subject="Dad",
    summary="Dad took his medicine",
    claim_stance=ClaimStance.ASSERTED,
    source_type=SourceType.FIRSTHAND,
    review_state=ReviewState.UNREVIEWED,
    evidence_segment_ids=None,
    occurred_at=None,
    reported_by=None,
    event_id="e",
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


def make_case(expected_events, segment_ids=("s1", "s2")) -> GoldenCase:
    document = TranscriptDocument(
        transcript_id="test",
        full_text="irrelevant",
        segments=[TranscriptSegment(sid, "text") for sid in segment_ids],
    )
    return GoldenCase(case_id="test", document=document, expected_events=expected_events, notes="test case")


class TestEvidenceScores:
    def test_all_valid_full_recall(self):
        scores = compute_evidence_scores(["s1", "s2"], ["s1", "s2"], {"s1", "s2", "s3"})
        assert scores.validity == 1.0
        assert scores.precision == 1.0
        assert scores.recall == 1.0
        assert scores.has_valid_evidence

    def test_invalid_id_lowers_validity_not_recall(self):
        scores = compute_evidence_scores(["s1"], ["s1", "s99"], {"s1", "s2"})
        assert scores.validity == 0.5
        assert scores.recall == 1.0
        assert scores.invalid_ids == ["s99"]
        assert scores.has_valid_evidence

    def test_extra_valid_segment_lowers_precision_not_recall(self):
        scores = compute_evidence_scores(["s1"], ["s1", "s2"], {"s1", "s2"})
        assert scores.recall == 1.0
        assert scores.precision == 0.5
        assert scores.validity == 1.0

    def test_no_evidence_cited_is_not_valid(self):
        scores = compute_evidence_scores(["s1"], [], {"s1", "s2"})
        assert scores.has_valid_evidence is False
        assert scores.recall == 0.0

    def test_all_ids_invalid(self):
        scores = compute_evidence_scores(["s1"], ["s99"], {"s1", "s2"})
        assert scores.has_valid_evidence is False
        assert scores.validity == 0.0

    def test_no_expected_evidence_recall_is_none(self):
        scores = compute_evidence_scores([], ["s1"], {"s1"})
        assert scores.recall is None


class TestEventMatching:
    def test_matches_by_type_and_evidence_overlap(self):
        expected = [make_event(evidence_segment_ids=["s1"])]
        generated = [make_event(evidence_segment_ids=["s1"])]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert len(pairs) == 1
        assert not unmatched_e
        assert not unmatched_g

    def test_no_match_when_types_differ_even_with_everything_else_identical(self):
        expected = [make_event(event_type=EventType.MEDICATION, evidence_segment_ids=["s1"])]
        generated = [make_event(event_type=EventType.APPOINTMENT, evidence_segment_ids=["s1"])]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert not pairs
        assert len(unmatched_e) == 1
        assert len(unmatched_g) == 1

    def test_matches_via_subject_and_temporal_without_evidence_overlap(self):
        # Different transcript segmentation (evidence ids don't overlap at
        # all) must not by itself prevent a match when subject/temporal
        # agree - evidence overlap is a strong signal, not the sole one.
        expected = [make_event(subject="Dad", occurred_at=relative_time("8am"), evidence_segment_ids=["s1"])]
        generated = [make_event(subject="Dad", occurred_at=relative_time("8am"), evidence_segment_ids=["different-seg"])]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert len(pairs) == 1

    def test_no_match_when_no_signal_agrees_at_all(self):
        expected = [make_event(subject="Dad", summary="Dad took pills", evidence_segment_ids=["s1"])]
        generated = [make_event(subject="Mom", summary="totally unrelated text", evidence_segment_ids=["s2"])]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert not pairs

    def test_each_generated_event_matches_at_most_one_expected(self):
        expected = [make_event(evidence_segment_ids=["s1"]), make_event(evidence_segment_ids=["s2"])]
        generated = [make_event(evidence_segment_ids=["s1", "s2"])]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert len(pairs) == 1
        assert len(unmatched_e) == 1
        assert not unmatched_g

    def test_one_to_one_matching_prefers_better_candidate(self):
        expected = [make_event(subject="Dad", evidence_segment_ids=["s1"])]
        generated = [
            make_event(subject="Mom", evidence_segment_ids=["s1"]),  # weaker: subject mismatch
            make_event(subject="Dad", evidence_segment_ids=["s1"]),  # stronger: full agreement
        ]
        pairs, unmatched_e, unmatched_g = match_events(expected, generated)
        assert len(pairs) == 1
        matched_generated = pairs[0][1]
        assert matched_generated.subject == "Dad"
        assert len(unmatched_g) == 1


class TestMissingAndExtraEvents:
    def test_missing_event_when_nothing_generated(self):
        case = make_case([make_event()])
        result = evaluate_case(case, [])
        assert [c.verdict for c in result.comparisons] == [Verdict.MISSING]

    def test_extra_generated_event_is_unsupported(self):
        case = make_case([])
        result = evaluate_case(case, [make_event()])
        assert [c.verdict for c in result.comparisons] == [Verdict.UNSUPPORTED]

    def test_empty_expected_and_empty_generated_yields_no_comparisons(self):
        case = make_case([])
        result = evaluate_case(case, [])
        assert result.comparisons == []
        assert result.is_fully_correct


class TestExactMatch:
    def test_identical_events_are_correct(self):
        case = make_case([make_event()])
        result = evaluate_case(case, [make_event()])
        assert result.comparisons[0].verdict == Verdict.CORRECT


class TestNoEvidence:
    def test_generated_event_with_no_evidence_is_unsupported(self):
        expected = make_event(evidence_segment_ids=["s1"])
        generated = make_event(evidence_segment_ids=[])
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.UNSUPPORTED

    def test_generated_event_with_only_invalid_evidence_is_unsupported(self):
        expected = make_event(evidence_segment_ids=["s1"])
        generated = make_event(evidence_segment_ids=["s99"])
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.UNSUPPORTED


class TestInvalidEvidenceIds:
    def test_matched_pair_with_invalid_id_alongside_valid_one_is_partial(self):
        expected = make_event(evidence_segment_ids=["s1"])
        generated = make_event(evidence_segment_ids=["s1", "s99"])
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        comparison = result.comparisons[0]
        assert comparison.verdict == Verdict.PARTIAL
        assert comparison.evidence.invalid_ids == ["s99"]


class TestExtraValidEvidence:
    def test_extra_valid_supporting_segment_does_not_break_correctness(self):
        expected = make_event(evidence_segment_ids=["s1"])
        generated = make_event(evidence_segment_ids=["s1", "s2"])
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        comparison = result.comparisons[0]
        assert comparison.verdict == Verdict.CORRECT
        assert comparison.evidence.precision == 0.5
        assert comparison.evidence.recall == 1.0


class TestSubjectSafety:
    def test_explicit_subject_mismatch_is_contradictory(self):
        expected = make_event(subject="Dad", evidence_segment_ids=["s1"])
        generated = make_event(subject="Mom", evidence_segment_ids=["s1"])
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.CONTRADICTORY
        assert "subject mismatch" in result.comparisons[0].reason


class TestSafetyCritical:
    """Direct translations of the Phase 1 Step 6 'BAD' extraction examples,
    expressed with the Phase 2 canonical claim_stance/source_type/review_state
    split."""

    def test_hedged_uncertainty_flattened_to_fact_is_contradictory(self):
        expected = make_event(
            summary="Dad may have missed his morning medicine",
            claim_stance=ClaimStance.UNCERTAIN,
        )
        generated = make_event(
            summary="Dad missed his medicine",
            claim_stance=ClaimStance.ASSERTED,
        )
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.CONTRADICTORY

    def test_unsupported_causal_inference_is_not_matched_as_correct(self):
        expected = make_event(
            event_type=EventType.OBSERVATION,
            subject="She",
            summary="She seemed tired after taking the medication",
        )
        causal_hallucination = make_event(
            event_type=EventType.CONCERN,
            subject="She",
            summary="The medication caused her fatigue",
        )
        case = make_case([expected])
        result = evaluate_case(case, [causal_hallucination])
        verdicts = {c.verdict for c in result.comparisons}
        assert Verdict.CORRECT not in verdicts
        assert Verdict.MISSING in verdicts or Verdict.UNSUPPORTED in verdicts

    def test_negated_event_contradicted_by_a_wrongly_asserted_generated_event(self):
        # "No, Dad did not miss his medication." expected as claim_stance=negated.
        # A generated event that instead asserts it WAS missed, on the same
        # evidence, must collide with the negated event during matching and
        # be flagged as a claim_stance contradiction.
        expected = make_event(
            summary="Dad did not miss his medication",
            claim_stance=ClaimStance.NEGATED,
            evidence_segment_ids=["s1"],
        )
        hallucinated = make_event(
            summary="Dad missed his medication",
            claim_stance=ClaimStance.ASSERTED,
            evidence_segment_ids=["s1"],
        )
        case = make_case([expected])
        result = evaluate_case(case, [hallucinated])
        assert result.comparisons[0].verdict == Verdict.CONTRADICTORY

    def test_hallucination_unrelated_to_any_expected_negation_is_plain_unsupported(self):
        expected = make_event(
            summary="Dad did not miss his medication",
            claim_stance=ClaimStance.NEGATED,
            evidence_segment_ids=["s1"],
        )
        unrelated = make_event(
            event_type=EventType.APPOINTMENT,
            summary="Dad has a checkup",
            evidence_segment_ids=["s2"],
        )
        case = make_case([expected])
        result = evaluate_case(case, [unrelated])
        verdicts = {c.verdict for c in result.comparisons}
        assert Verdict.UNSUPPORTED in verdicts
        assert Verdict.MISSING in verdicts

    def test_invented_vital_event_is_unsupported(self):
        case = make_case([])
        invented = make_event(
            event_type=EventType.VITAL,
            summary="Dad's blood pressure was recorded",
            evidence_segment_ids=["s1"],
        )
        result = evaluate_case(case, [invented])
        assert result.comparisons[0].verdict == Verdict.UNSUPPORTED


class TestClaimStanceMismatch:
    def test_asserted_downgraded_to_uncertain_is_contradictory(self):
        expected = make_event(claim_stance=ClaimStance.ASSERTED)
        generated = make_event(claim_stance=ClaimStance.UNCERTAIN)
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.CONTRADICTORY

    def test_claim_stance_enum_has_no_contradicted_value(self):
        assert not hasattr(ClaimStance, "CONTRADICTED")
        assert {s.value for s in ClaimStance} == {"asserted", "uncertain", "negated"}


class TestUncertainSecondhandCoexistence:
    def test_uncertain_and_secondhand_together_matches_correctly(self):
        event = make_event(
            claim_stance=ClaimStance.UNCERTAIN,
            source_type=SourceType.SECONDHAND,
            review_state=ReviewState.NEEDS_VERIFICATION,
            reported_by="sister",
        )
        case = make_case([event])
        result = evaluate_case(
            case,
            [
                make_event(
                    claim_stance=ClaimStance.UNCERTAIN,
                    source_type=SourceType.SECONDHAND,
                    review_state=ReviewState.NEEDS_VERIFICATION,
                    reported_by="sister",
                )
            ],
        )
        assert result.comparisons[0].verdict == Verdict.CORRECT

    def test_dropping_secondhand_source_while_keeping_claim_stance_is_partial_not_contradictory(self):
        expected = make_event(
            claim_stance=ClaimStance.UNCERTAIN,
            source_type=SourceType.SECONDHAND,
            reported_by="sister",
        )
        generated = make_event(
            claim_stance=ClaimStance.UNCERTAIN,
            source_type=SourceType.FIRSTHAND,
            reported_by=None,
        )
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.PARTIAL


class TestProvenanceIsNotAutomaticContradiction:
    def test_attribution_dropped_but_claim_stance_preserved_is_partial(self):
        expected = make_event(
            event_type=EventType.CONCERN,
            summary="Dad fell, as reported by sister",
            claim_stance=ClaimStance.ASSERTED,
            source_type=SourceType.SECONDHAND,
            reported_by="sister",
        )
        generated = make_event(
            event_type=EventType.CONCERN,
            summary="Dad fell",
            claim_stance=ClaimStance.ASSERTED,
            source_type=SourceType.FIRSTHAND,
            reported_by=None,
        )
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        assert result.comparisons[0].verdict == Verdict.PARTIAL


class TestEventTypeMismatch:
    def test_type_mismatch_prevents_matching_leading_to_missing_and_unsupported(self):
        expected = make_event(event_type=EventType.MEDICATION)
        generated = make_event(event_type=EventType.APPOINTMENT)
        case = make_case([expected])
        result = evaluate_case(case, [generated])
        verdicts = sorted(c.verdict for c in result.comparisons)
        assert verdicts == sorted([Verdict.MISSING, Verdict.UNSUPPORTED])


class TestSegmentationMismatch:
    def test_disjoint_evidence_ids_can_still_match_and_score_correct_via_other_signals(self):
        expected = make_event(subject="Dad", occurred_at=relative_time("8am"), evidence_segment_ids=["s1"])
        generated = make_event(subject="Dad", occurred_at=relative_time("8am"), evidence_segment_ids=["s2"])
        case = make_case([expected], segment_ids=("s1", "s2"))
        result = evaluate_case(case, [generated])
        comparison = result.comparisons[0]
        assert comparison.verdict != Verdict.MISSING
        assert comparison.evidence.recall == 0.0


class TestEmptyEventSet:
    def test_both_sides_empty_is_trivially_correct(self):
        case = make_case([])
        result = evaluate_case(case, [])
        assert result.is_fully_correct
        assert result.verdict_counts == {v.value: 0 for v in Verdict}
