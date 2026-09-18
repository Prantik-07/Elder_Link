from backend.core.care_event import ReviewState, TranscriptDocument, TranscriptSegment, VerificationReasonCode
from backend.core.extraction import ExtractionErrorKind, ExtractionResult, MockExtractionProvider, run_extraction_pipeline
from backend.core.extraction.service import ExtractionProvider


class FakeProvider(ExtractionProvider):
    """A test double that returns whatever candidate dicts / failure it's
    constructed with - lets pipeline behavior be tested independent of the
    mock rule engine's own extraction logic."""

    def __init__(self, result: ExtractionResult):
        self._result = result

    @property
    def provider_name(self) -> str:
        return self._result.provider

    @property
    def model_id(self) -> str:
        return self._result.model

    def extract(self, document: TranscriptDocument) -> ExtractionResult:
        return self._result


def document() -> TranscriptDocument:
    return TranscriptDocument(
        transcript_id="t1",
        full_text="Dad took his pills. He has an appointment Friday.",
        segments=[
            TranscriptSegment("s1", "Dad took his pills."),
            TranscriptSegment("s2", "He has an appointment Friday."),
        ],
    )


def valid_candidate(**overrides) -> dict:
    base = {
        "event_id": "e1",
        "event_type": "medication",
        "subject": "Dad",
        "summary": "Dad took his pills",
        "claim_stance": "asserted",
        "source_type": "firsthand",
        "review_state": "unreviewed",
        "occurred_at": {"precision": "unknown"},
        "evidence": [{"segment_id": "s1"}],
    }
    base.update(overrides)
    return base


class TestValidCandidatePassesThrough:
    def test_well_formed_candidate_is_validated(self):
        provider = FakeProvider(ExtractionResult.success_result([valid_candidate()], "fake", "fake-1"))
        result = run_extraction_pipeline(document(), provider)
        assert len(result.validated_events) == 1
        assert result.rejected == []
        assert not result.extraction_failed


class TestInvalidEvidence:
    def test_candidate_citing_nonexistent_segment_is_rejected(self):
        provider = FakeProvider(
            ExtractionResult.success_result([valid_candidate(evidence=[{"segment_id": "s99"}])], "fake", "fake-1")
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert len(result.rejected) == 1
        assert result.rejected[0].stage == "validation"
        assert "nonexistent segment" in result.rejected[0].reason

    def test_candidate_with_no_evidence_is_rejected(self):
        provider = FakeProvider(ExtractionResult.success_result([valid_candidate(evidence=[])], "fake", "fake-1"))
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert "evidence" in result.rejected[0].reason


class TestInvalidEventType:
    def test_unknown_event_type_is_rejected_at_parse_stage(self):
        provider = FakeProvider(
            ExtractionResult.success_result([valid_candidate(event_type="not_a_real_type")], "fake", "fake-1")
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert result.rejected[0].stage == "parse"


class TestFabricatedTimestampRejection:
    def test_impossible_temporal_structure_is_rejected(self):
        provider = FakeProvider(
            ExtractionResult.success_result(
                [valid_candidate(occurred_at={"precision": "exact_timestamp"})], "fake", "fake-1"
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert "timestamp is required" in result.rejected[0].reason


class TestVerifiedStateRejection:
    def test_fresh_extraction_cannot_claim_verified(self):
        provider = FakeProvider(
            ExtractionResult.success_result([valid_candidate(review_state="verified")], "fake", "fake-1")
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert any("review_state=verified" in r.reason for r in result.rejected)


class TestConflictingClaimsAsSeparateEvents:
    def test_two_conflicting_candidates_both_validate_as_separate_events(self):
        provider = FakeProvider(
            ExtractionResult.success_result(
                [
                    valid_candidate(event_id="e1", summary="Dad took his medicine at 8am", claim_stance="asserted"),
                    valid_candidate(
                        event_id="e2",
                        summary="Speaker is no longer sure Dad took his medicine",
                        claim_stance="uncertain",
                        evidence=[{"segment_id": "s2"}],
                    ),
                ],
                "fake",
                "fake-1",
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert len(result.validated_events) == 2
        stances = {e.claim_stance.value for e in result.validated_events}
        assert stances == {"asserted", "uncertain"}


class TestEmptyResult:
    def test_provider_returning_no_candidates_yields_empty_validated_list(self):
        provider = FakeProvider(ExtractionResult.success_result([], "fake", "fake-1"))
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert result.rejected == []
        assert not result.extraction_failed


class TestMalformedCandidate:
    def test_candidate_missing_required_field_is_rejected_at_parse_stage(self):
        malformed = valid_candidate()
        del malformed["claim_stance"]
        provider = FakeProvider(ExtractionResult.success_result([malformed], "fake", "fake-1"))
        result = run_extraction_pipeline(document(), provider)
        assert result.validated_events == []
        assert result.rejected[0].stage == "parse"


class TestProviderFailure:
    def test_provider_failure_surfaces_as_extraction_error_not_a_crash(self):
        provider = FakeProvider(
            ExtractionResult.failure_result(
                "fake", "fake-1", "network exploded", ExtractionErrorKind.PROVIDER_FAILURE
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.extraction_failed
        assert result.extraction_error == "network exploded"
        assert result.extraction_error_kind == ExtractionErrorKind.PROVIDER_FAILURE
        assert result.validated_events == []

    def test_not_available_kind_surfaces_distinctly(self):
        provider = FakeProvider(
            ExtractionResult.failure_result(
                "bedrock", "claude", "AWS account verification pending", ExtractionErrorKind.NOT_AVAILABLE
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert result.extraction_error_kind == ExtractionErrorKind.NOT_AVAILABLE


class TestReviewPolicyOverridesProviderSelfAssessment:
    def test_candidate_claiming_unreviewed_but_actually_uncertain_is_corrected_to_needs_verification(self):
        # The provider claims "unreviewed" for an UNCERTAIN claim - the
        # pipeline must not trust that self-assessment; the deterministic
        # policy overrides it regardless of what the candidate proposed.
        provider = FakeProvider(
            ExtractionResult.success_result(
                [valid_candidate(claim_stance="uncertain", review_state="unreviewed")], "fake", "fake-1"
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert len(result.validated_events) == 1
        event = result.validated_events[0]
        assert event.review_state == ReviewState.NEEDS_VERIFICATION
        assert event.verification_reason.code == VerificationReasonCode.EXPLICIT_UNCERTAINTY


class TestConflictFlaggedThroughReviewState:
    def test_conflicting_pair_both_end_up_needing_verification(self):
        provider = FakeProvider(
            ExtractionResult.success_result(
                [
                    valid_candidate(event_id="e1", claim_stance="asserted", summary="Dad took his medicine"),
                    valid_candidate(
                        event_id="e2",
                        claim_stance="negated",
                        summary="Dad did not take his medicine",
                        evidence=[{"segment_id": "s2"}],
                    ),
                ],
                "fake",
                "fake-1",
            )
        )
        result = run_extraction_pipeline(document(), provider)
        assert len(result.validated_events) == 2
        for event in result.validated_events:
            assert event.review_state == ReviewState.NEEDS_VERIFICATION


class TestDeterministicEventIdsAcrossPipelineRuns:
    def test_repeated_extraction_of_same_transcript_yields_same_event_ids(self):
        provider = MockExtractionProvider()
        doc = TranscriptDocument(
            transcript_id="same-transcript",
            full_text="Dad took his blood pressure medicine at 8am.",
            segments=[TranscriptSegment("s1", "Dad took his blood pressure medicine at 8am.")],
        )

        first = run_extraction_pipeline(doc, provider)
        second = run_extraction_pipeline(doc, provider)

        first_ids = [e.event_id for e in first.validated_events]
        second_ids = [e.event_id for e in second.validated_events]
        assert first_ids == second_ids
        assert len(first_ids) > 0

    def test_different_transcripts_yield_different_event_ids(self):
        provider = MockExtractionProvider()
        doc_a = TranscriptDocument(
            transcript_id="transcript-a",
            full_text="Dad took his medicine.",
            segments=[TranscriptSegment("s1", "Dad took his medicine.")],
        )
        doc_b = TranscriptDocument(
            transcript_id="transcript-b",
            full_text="Dad took his medicine.",
            segments=[TranscriptSegment("s1", "Dad took his medicine.")],
        )

        result_a = run_extraction_pipeline(doc_a, provider)
        result_b = run_extraction_pipeline(doc_b, provider)

        assert result_a.validated_events[0].event_id != result_b.validated_events[0].event_id


class TestReorderedExtractionYieldsSameIds:
    def test_reordered_candidates_from_provider_produce_same_ids_per_logical_event(self):
        # Phase 4.1's actual complaint: two providers (or two runs) that
        # emit the SAME logical events in a DIFFERENT array order must not
        # get different ids for the corresponding events.
        doc = TranscriptDocument(
            transcript_id="t1",
            full_text="Dad took his pills. He has an appointment Friday.",
            segments=[
                TranscriptSegment("s1", "Dad took his pills."),
                TranscriptSegment("s2", "He has an appointment Friday."),
            ],
        )
        medication = valid_candidate(event_id="a", event_type="medication", evidence=[{"segment_id": "s1"}])
        appointment = valid_candidate(event_id="b", event_type="appointment", evidence=[{"segment_id": "s2"}])

        forward = FakeProvider(ExtractionResult.success_result([medication, appointment], "fake", "fake-1"))
        backward = FakeProvider(ExtractionResult.success_result([appointment, medication], "fake", "fake-1"))

        result_forward = run_extraction_pipeline(doc, forward)
        result_backward = run_extraction_pipeline(doc, backward)

        ids_forward = {e.event_type: e.event_id for e in result_forward.validated_events}
        ids_backward = {e.event_type: e.event_id for e in result_backward.validated_events}

        assert ids_forward == ids_backward
