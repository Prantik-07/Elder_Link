from backend.core.care_event import (
    ClaimStance,
    EventType,
    SourceType,
    TemporalPrecision,
    TranscriptDocument,
    TranscriptSegment,
)
from backend.core.extraction import MockExtractionProvider


def document(text: str, transcript_id: str = "t") -> TranscriptDocument:
    return TranscriptDocument(transcript_id=transcript_id, full_text=text, segments=[TranscriptSegment("s1", text)])


def multi_segment_document(*texts: str, transcript_id: str = "t") -> TranscriptDocument:
    segments = [TranscriptSegment(f"s{i + 1}", t) for i, t in enumerate(texts)]
    return TranscriptDocument(transcript_id=transcript_id, full_text=" ".join(texts), segments=segments)


class TestProviderIdentity:
    def test_provider_name_and_model_id(self):
        provider = MockExtractionProvider()
        assert provider.provider_name == "mock"
        assert provider.model_id


class TestSimpleMedicationExtraction:
    def test_extracts_asserted_firsthand_medication_event(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("Dad took his blood pressure medicine at 8am."))
        assert result.success
        assert len(result.candidate_events) == 1
        event = result.candidate_events[0]
        assert event["event_type"] == "medication"
        assert event["subject"] == "Dad"
        assert event["claim_stance"] == "asserted"
        assert event["source_type"] == "firsthand"
        assert event["evidence"] == [{"segment_id": "s1"}]


class TestSymptomExtraction:
    def test_extracts_observation_event(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("Mom seemed a bit more tired than usual this afternoon."))
        assert len(result.candidate_events) == 1
        assert result.candidate_events[0]["event_type"] == "observation"
        assert result.candidate_events[0]["subject"] == "Mom"


class TestMultipleEvents:
    def test_extracts_one_event_per_qualifying_segment(self):
        provider = MockExtractionProvider()
        doc = multi_segment_document(
            "Dad took his morning pills around 8.",
            "Also, don't forget he has his eye doctor appointment on Friday.",
        )
        result = provider.extract(doc)
        assert len(result.candidate_events) == 2
        types = {e["event_type"] for e in result.candidate_events}
        assert types == {"medication", "appointment"}
        segment_ids = {e["evidence"][0]["segment_id"] for e in result.candidate_events}
        assert segment_ids == {"s1", "s2"}


class TestNoEventTranscript:
    def test_casual_conversation_returns_empty(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("Hey, just checking in, hope you're having a good day!"))
        assert result.success
        assert result.candidate_events == []

    def test_incomplete_statement_returns_empty(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("Dad's blood pres-"))
        assert result.candidate_events == []

    def test_bare_question_returns_empty(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("I was wondering whether Dad's blood pressure was checked?"))
        assert result.candidate_events == []


class TestUncertaintyPreservation:
    def test_hedged_statement_is_uncertain_not_asserted(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("I think Dad may have missed his morning medicine."))
        assert len(result.candidate_events) == 1
        event = result.candidate_events[0]
        assert event["claim_stance"] == "uncertain"
        # review_state/verification_reason are never this provider's call -
        # review_policy.derive_review_state (exercised via the pipeline)
        # is the sole authority; see test_review_policy.py.
        assert event["review_state"] == "unreviewed"

    def test_a_broad_range_of_hedge_phrasings_are_all_uncertain(self):
        # Phase 4 section 8: the exact phrase "I think" must not be required.
        hedged_texts = [
            "I think Dad may have missed his medicine.",
            "Maybe he missed his medicine.",
            "Dad might have missed his medicine.",
            "Probably he took his medicine.",
            "I'm not sure he took his medicine.",
            "It seems like Dad might have missed his dose.",
            "I believe Dad may have skipped his medicine.",
        ]
        provider = MockExtractionProvider()
        for text in hedged_texts:
            result = provider.extract(document(text))
            assert len(result.candidate_events) == 1, f"expected one event for: {text!r}"
            assert result.candidate_events[0]["claim_stance"] == "uncertain", f"expected uncertain for: {text!r}"


class TestNegationPreservation:
    def test_explicit_negation_is_negated_not_asserted(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("No, Dad did not miss his medication today, I already checked."))
        assert len(result.candidate_events) == 1
        event = result.candidate_events[0]
        assert event["claim_stance"] == "negated"
        # Must not silently become "Medication missed" - the raw statement
        # (still describing what was NOT true) survives, paired with the
        # negated stance, not an inverted asserted summary.
        assert "did not" in event["summary"].lower()

    def test_never_missed_is_negated(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("He never missed his evening dose."))
        assert len(result.candidate_events) == 1
        assert result.candidate_events[0]["claim_stance"] == "negated"

    def test_no_he_took_it_never_produces_a_positive_missed_dose_claim(self):
        # "No, he took it." is a genuinely hard case for a keyword-based
        # system: it has no medication keyword of its own and no explicit
        # negation cue for "took". The safe behavior is to not invent a
        # specific medication claim from it at all - what matters is that
        # it must never surface as an asserted "medication missed" event.
        provider = MockExtractionProvider()
        result = provider.extract(document("No, he took it."))
        assert not any(
            e["claim_stance"] == "asserted" and "missed" in e["summary"].lower() for e in result.candidate_events
        )


class TestSecondhandSource:
    def test_secondhand_report_sets_source_type_and_reported_by(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("My sister told me Dad fell yesterday evening in the kitchen."))
        assert len(result.candidate_events) == 1
        event = result.candidate_events[0]
        assert event["source_type"] == "secondhand"
        assert event["reported_by"] == "sister"
        assert event["subject"] == "Dad"

    def test_uncertain_and_secondhand_coexist(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("My sister thinks Dad may have missed his medication this morning."))
        assert len(result.candidate_events) == 1
        event = result.candidate_events[0]
        assert event["claim_stance"] == "uncertain"
        assert event["source_type"] == "secondhand"
        assert event["reported_by"] == "sister"


class TestSubjectAttribution:
    def test_subject_is_the_person_the_note_is_about(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("She seemed tired after the medication."))
        assert len(result.candidate_events) == 1
        assert result.candidate_events[0]["subject"] == "She"


class TestUnsupportedCausalInference:
    def test_never_emits_a_second_causal_event(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("She seemed tired after the medication."))
        # Exactly one event - the observation itself - never a second event
        # asserting the medication caused the tiredness.
        assert len(result.candidate_events) == 1
        summaries = " ".join(e["summary"].lower() for e in result.candidate_events)
        assert "caused" not in summaries


class TestNoFabricatedTimestamps:
    def test_relative_phrase_never_becomes_exact_timestamp_or_date(self):
        provider = MockExtractionProvider()
        cases = [
            "Dad took his blood pressure medicine at 8am.",
            "Dad has a doctor's appointment in two days.",
            "My sister told me Dad fell yesterday evening in the kitchen.",
        ]
        for text in cases:
            result = provider.extract(document(text))
            for event in result.candidate_events:
                assert event["occurred_at"]["precision"] in ("relative", "unknown")

    def test_no_temporal_phrase_yields_unknown_precision(self):
        provider = MockExtractionProvider()
        result = provider.extract(document("She seemed tired after the medication."))
        assert result.candidate_events[0]["occurred_at"]["precision"] == "unknown"


class TestEmptyResult:
    def test_document_with_no_segments_returns_empty(self):
        provider = MockExtractionProvider()
        empty_doc = TranscriptDocument(transcript_id="t", full_text="", segments=[])
        result = provider.extract(empty_doc)
        assert result.success
        assert result.candidate_events == []
