import json

import pytest

from backend.core.care_event import ClaimStance, EventType, SourceType
from evaluation.dataset import load_dataset
from evaluation.models import GoldenCase


class TestLoadDataset:
    def test_loads_bundled_golden_dataset(self):
        cases = load_dataset()
        assert len(cases) >= 12

    def test_all_case_ids_unique(self):
        cases = load_dataset()
        ids = [c.case_id for c in cases]
        assert len(ids) == len(set(ids))

    def test_cases_have_notes_describing_failure_mode(self):
        cases = load_dataset()
        for case in cases:
            assert case.notes.strip(), f"{case.case_id} has empty notes"

    def test_no_care_event_cases_have_empty_expected_events(self):
        cases = {c.case_id: c for c in load_dataset()}
        assert cases["07_no_care_event"].expected_events == []
        assert cases["12_irrelevant_casual"].expected_events == []

    def test_uncertain_firsthand_case(self):
        cases = {c.case_id: c for c in load_dataset()}
        event = cases["05_uncertain_firsthand"].expected_events[0]
        assert event.claim_stance == ClaimStance.UNCERTAIN
        assert event.source_type == SourceType.FIRSTHAND
        assert "may have" in event.summary.lower()

    def test_uncertain_secondhand_case_coexistence(self):
        cases = {c.case_id: c for c in load_dataset()}
        event = cases["16_uncertain_secondhand"].expected_events[0]
        assert event.claim_stance == ClaimStance.UNCERTAIN
        assert event.source_type == SourceType.SECONDHAND
        assert event.reported_by == "sister"

    def test_asserted_secondhand_case(self):
        cases = {c.case_id: c for c in load_dataset()}
        event = cases["10_attribution_asserted_secondhand"].expected_events[0]
        assert event.claim_stance == ClaimStance.ASSERTED
        assert event.source_type == SourceType.SECONDHAND
        assert event.reported_by == "sister"

    def test_negated_case_produces_a_real_event_not_an_empty_set(self):
        cases = {c.case_id: c for c in load_dataset()}
        case = cases["08_negative_statement"]
        assert len(case.expected_events) == 1
        assert case.expected_events[0].claim_stance == ClaimStance.NEGATED

    def test_conflicting_information_is_two_separate_events(self):
        cases = {c.case_id: c for c in load_dataset()}
        events = cases["09_conflicting_information"].expected_events
        assert len(events) == 2
        stances = {e.claim_stance for e in events}
        assert ClaimStance.ASSERTED in stances
        assert ClaimStance.UNCERTAIN in stances
        # "contradicted" must not appear anywhere - it isn't a claim_stance value.
        assert all(e.claim_stance != "contradicted" for e in events)

    def test_multi_segment_evidence_case_cites_both_segments(self):
        cases = {c.case_id: c for c in load_dataset()}
        event = cases["14_evidence_multi_segment"].expected_events[0]
        assert set(event.evidence_segment_ids) == {"s1", "s2"}

    def test_document_full_text_and_segments_present(self):
        cases = {c.case_id: c for c in load_dataset()}
        case = cases["01_simple_medication"]
        assert case.document.full_text
        assert case.document.segments
        assert case.document.segment_ids == {"s1"}

    def test_all_event_types_in_dataset_are_from_the_controlled_vocabulary(self):
        cases = load_dataset()
        for case in cases:
            for event in case.expected_events:
                assert isinstance(event.event_type, EventType)


class TestGoldenCaseValidation:
    def _base_case_dict(self) -> dict:
        return {
            "case_id": "test_case",
            "document": {
                "transcript_id": "test_case",
                "full_text": "Dad took his pills.",
                "segments": [{"segment_id": "s1", "text": "Dad took his pills."}],
            },
            "expected_events": [],
            "notes": "test",
        }

    def _base_event_dict(self) -> dict:
        return {
            "event_id": "e1",
            "event_type": "medication",
            "subject": "Dad",
            "summary": "Dad took his pills",
            "claim_stance": "asserted",
            "source_type": "firsthand",
            "review_state": "unreviewed",
            "evidence": [{"segment_id": "s1"}],
        }

    def test_rejects_missing_required_field(self):
        data = self._base_case_dict()
        del data["notes"]
        with pytest.raises(ValueError, match="missing required fields"):
            GoldenCase.from_dict(data)

    def test_rejects_event_referencing_unknown_segment(self):
        data = self._base_case_dict()
        event = self._base_event_dict()
        event["evidence"] = [{"segment_id": "s99"}]
        data["expected_events"] = [event]
        with pytest.raises(ValueError, match="unknown segment"):
            GoldenCase.from_dict(data)

    def test_rejects_duplicate_case_ids(self, tmp_path):
        data = [self._base_case_dict(), self._base_case_dict()]
        path = tmp_path / "dupes.json"
        path.write_text(json.dumps(data))
        with pytest.raises(ValueError, match="Duplicate case_id"):
            load_dataset(path)

    def test_rejects_duplicate_segment_ids(self):
        data = self._base_case_dict()
        data["document"]["segments"].append({"segment_id": "s1", "text": "duplicate"})
        with pytest.raises(ValueError, match="Duplicate segment_id"):
            GoldenCase.from_dict(data)

    def test_parses_valid_case(self):
        data = self._base_case_dict()
        data["expected_events"] = [self._base_event_dict()]
        case = GoldenCase.from_dict(data)
        assert case.expected_events[0].event_type == EventType.MEDICATION
