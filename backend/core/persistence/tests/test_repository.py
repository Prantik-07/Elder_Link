import threading

import pytest
from botocore.exceptions import ClientError

from backend.core.care_event import (
    CareEvent,
    ClaimStance,
    Evidence,
    EventType,
    ReviewState,
    SourceType,
    TemporalInfo,
    VerificationReason,
    VerificationReasonCode,
)
from backend.core.persistence import (
    CareContext,
    CareEventNotFoundError,
    CareEventRepository,
    PersistenceValidationError,
)

from .fake_table import FakeCareEventsTable


def make_event(**overrides) -> CareEvent:
    defaults = dict(
        event_id="ce_abc",
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


def make_context(**overrides) -> CareContext:
    defaults = dict(care_recipient_id="patient-1", transcript_id="transcript-1")
    defaults.update(overrides)
    return CareContext(**defaults)


def make_repository(table=None) -> tuple[CareEventRepository, FakeCareEventsTable]:
    table = table if table is not None else FakeCareEventsTable()
    return CareEventRepository(table=table), table


class TestPutEventBasic:
    def test_put_event_persists_and_returns_record(self):
        repo, table = make_repository()
        record = repo.put_event(make_event(), make_context(), "care_event_v2")
        assert record.event.event_id == "ce_abc"
        assert record.extraction_version == "care_event_v2"
        assert len(table.items) == 1

    def test_created_at_and_updated_at_set_on_first_write(self):
        repo, _table = make_repository()
        record = repo.put_event(make_event(), make_context(), "care_event_v2")
        assert record.created_at
        assert record.updated_at
        assert record.created_at == record.updated_at


class TestIdempotentUpsert:
    def test_repeated_write_of_same_event_does_not_duplicate(self):
        repo, table = make_repository()
        repo.put_event(make_event(), make_context(), "care_event_v2")
        repo.put_event(make_event(), make_context(), "care_event_v2")
        repo.put_event(make_event(), make_context(), "care_event_v2")
        assert len(table.items) == 1

    def test_repeated_write_preserves_original_created_at(self):
        repo, _table = make_repository()
        first = repo.put_event(make_event(), make_context(), "care_event_v2")
        second = repo.put_event(make_event(), make_context(), "care_event_v2")
        assert first.created_at == second.created_at

    def test_repeated_write_advances_updated_at_or_stays_consistent(self):
        # updated_at legitimately reflects "processed again" - the
        # invariant that matters is created_at staying fixed, checked above.
        repo, _table = make_repository()
        first = repo.put_event(make_event(), make_context(), "care_event_v2")
        second = repo.put_event(make_event(), make_context(), "care_event_v2")
        assert second.updated_at >= first.updated_at

    def test_write_uses_update_item_not_check_then_write(self):
        # The idempotency mechanism itself must be a single atomic call,
        # not an application-side get-then-put around it.
        repo, table = make_repository()
        repo.put_event(make_event(), make_context(), "care_event_v2")
        repo.put_event(make_event(), make_context(), "care_event_v2")
        assert table.update_item_calls == 2

    def test_content_update_on_repeated_write_is_reflected(self):
        repo, _table = make_repository()
        repo.put_event(make_event(summary="original summary"), make_context(), "care_event_v2")
        updated = repo.put_event(make_event(summary="revised summary"), make_context(), "care_event_v2")
        assert updated.event.summary == "revised summary"


class TestConcurrentWrites:
    def test_concurrent_writes_of_same_event_do_not_duplicate_or_corrupt(self):
        repo, table = make_repository()
        errors = []

        def write():
            try:
                repo.put_event(make_event(), make_context(), "care_event_v2")
            except Exception as e:  # pragma: no cover - surfaced via `errors`
                errors.append(e)

        threads = [threading.Thread(target=write) for _ in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
        assert len(table.items) == 1
        record = repo.get_by_transcript("transcript-1")
        assert len(record) == 1


class TestNMinusOneExtraction:
    def test_stale_event_is_preserved_not_deleted(self):
        repo, table = make_repository()
        context = make_context()
        a = make_event(event_id="ce_a", evidence=[Evidence("s1")])
        b = make_event(event_id="ce_b", evidence=[Evidence("s2")])
        c = make_event(event_id="ce_c", evidence=[Evidence("s3")])

        for e in (a, b, c):
            repo.put_event(e, context, "care_event_v2")
        assert len(table.items) == 3

        original_a = repo.get_by_transcript(context.transcript_id)

        # Re-extraction only produces A and B (C is "missing" this time).
        for e in (a, b):
            repo.put_event(e, context, "care_event_v2")

        current = repo.get_by_transcript(context.transcript_id)
        assert len(current) == 3  # C was never deleted
        ids = {r.event.event_id for r in current}
        assert ids == {"ce_a", "ce_b", "ce_c"}

        a_before = next(r for r in original_a if r.event.event_id == "ce_a")
        a_after = next(r for r in current if r.event.event_id == "ce_a")
        assert a_before.created_at == a_after.created_at


class TestNPlusOneExtraction:
    def test_new_event_gets_its_own_id_existing_ids_unchanged(self):
        repo, table = make_repository()
        context = make_context()
        a = make_event(event_id="ce_a", evidence=[Evidence("s1")])
        b = make_event(event_id="ce_b", evidence=[Evidence("s2")])
        c = make_event(event_id="ce_c", evidence=[Evidence("s3")])
        x = make_event(event_id="ce_x", evidence=[Evidence("s4")])

        for e in (a, b, c):
            repo.put_event(e, context, "care_event_v2")
        before = {r.event.event_id: r.created_at for r in repo.get_by_transcript(context.transcript_id)}

        # Re-extraction produces A, X, B, C - X is new, order reshuffled.
        for e in (a, x, b, c):
            repo.put_event(e, context, "care_event_v2")

        after = repo.get_by_transcript(context.transcript_id)
        assert len(after) == 4
        after_by_id = {r.event.event_id: r for r in after}

        assert after_by_id["ce_a"].created_at == before["ce_a"]
        assert after_by_id["ce_b"].created_at == before["ce_b"]
        assert after_by_id["ce_c"].created_at == before["ce_c"]
        assert "ce_x" in after_by_id


class TestDifferentExtractionVersions:
    def test_same_event_id_under_different_versions_is_tracked_by_caller_not_conflated(self):
        # The repository itself keys purely on (care_recipient_id,
        # event_id) - it does not fold extraction_version into the DynamoDB
        # key. Phase 4.1's identity already guarantees different versions
        # produce different event_ids for the same logical content, so this
        # is not expected to collide in practice; this test just documents
        # that extraction_version is stored and returned, not silently
        # dropped, so a caller CAN distinguish runs after the fact.
        repo, _table = make_repository()
        context = make_context()
        event = make_event(event_id="ce_same")
        repo.put_event(event, context, "care_event_v2")
        updated = repo.put_event(event, context, "care_event_v3")
        assert updated.extraction_version == "care_event_v3"


class TestCareTimelineQuery:
    def test_newest_first_ordering(self):
        repo, table = make_repository()
        context = make_context()
        repo.put_event(make_event(event_id="ce_1"), context, "care_event_v2")
        # Force distinct created_at values deterministically for the test
        # (real writes are naturally offset in time).
        table.items[("PATIENT#patient-1", "EVENT#ce_1")]["created_at"] = "2026-01-01T00:00:00Z"
        repo.put_event(make_event(event_id="ce_2"), context, "care_event_v2")
        table.items[("PATIENT#patient-1", "EVENT#ce_2")]["created_at"] = "2026-01-02T00:00:00Z"
        repo.put_event(make_event(event_id="ce_3"), context, "care_event_v2")
        table.items[("PATIENT#patient-1", "EVENT#ce_3")]["created_at"] = "2026-01-03T00:00:00Z"

        timeline = repo.get_timeline(context.care_recipient_id)
        assert [r.event.event_id for r in timeline] == ["ce_3", "ce_2", "ce_1"]

    def test_only_events_for_the_requested_recipient(self):
        repo, _table = make_repository()
        repo.put_event(make_event(event_id="ce_a"), make_context(care_recipient_id="patient-1"), "care_event_v2")
        repo.put_event(make_event(event_id="ce_b"), make_context(care_recipient_id="patient-2"), "care_event_v2")

        timeline = repo.get_timeline("patient-1")
        assert [r.event.event_id for r in timeline] == ["ce_a"]

    def test_limit_is_respected(self):
        repo, _table = make_repository()
        context = make_context()
        for i in range(5):
            repo.put_event(make_event(event_id=f"ce_{i}"), context, "care_event_v2")

        timeline = repo.get_timeline(context.care_recipient_id, limit=2)
        assert len(timeline) == 2


class TestTranscriptQuery:
    def test_returns_only_events_from_the_requested_transcript(self):
        repo, _table = make_repository()
        repo.put_event(make_event(event_id="ce_a"), make_context(transcript_id="t1"), "care_event_v2")
        repo.put_event(make_event(event_id="ce_b"), make_context(transcript_id="t2"), "care_event_v2")

        events = repo.get_by_transcript("t1")
        assert [r.event.event_id for r in events] == ["ce_a"]


class TestMissingCareContext:
    def test_empty_care_recipient_id_rejected(self):
        repo, table = make_repository()
        with pytest.raises(PersistenceValidationError, match="care_recipient_id"):
            repo.put_event(make_event(), make_context(care_recipient_id=""), "care_event_v2")
        assert table.update_item_calls == 0

    def test_empty_transcript_id_rejected(self):
        repo, table = make_repository()
        with pytest.raises(PersistenceValidationError, match="transcript_id"):
            repo.put_event(make_event(), make_context(transcript_id=""), "care_event_v2")
        assert table.update_item_calls == 0


class TestInvalidCanonicalEventRejection:
    def test_missing_event_id_rejected(self):
        repo, table = make_repository()
        with pytest.raises(PersistenceValidationError, match="event_id"):
            repo.put_event(make_event(event_id=""), make_context(), "care_event_v2")
        assert table.update_item_calls == 0

    def test_empty_evidence_rejected(self):
        repo, table = make_repository()
        with pytest.raises(PersistenceValidationError, match="evidence"):
            repo.put_event(make_event(evidence=[]), make_context(), "care_event_v2")
        assert table.update_item_calls == 0


class TestUpdateReviewState:
    def test_valid_status_update_persists_review_state(self):
        repo, _table = make_repository()
        repo.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")

        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)
        assert updated.event.review_state == ReviewState.VERIFIED

    def test_verification_reason_is_persisted_when_provided(self):
        repo, _table = make_repository()
        repo.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")

        reason = VerificationReason(code=VerificationReasonCode.OTHER, detail="kept flagged")
        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.NEEDS_VERIFICATION, reason)
        assert updated.event.verification_reason == reason

    def test_verification_reason_is_cleared_when_not_provided(self):
        repo, _table = make_repository()
        repo.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")
        reason = VerificationReason(code=VerificationReasonCode.OTHER, detail="kept flagged")
        repo.update_review_state("patient-1", "ce_1", ReviewState.NEEDS_VERIFICATION, reason)

        # Marking verified afterwards clears the now-stale reason.
        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)
        assert updated.event.verification_reason is None

    def test_nonexistent_event_raises_not_found(self):
        repo, _table = make_repository()
        with pytest.raises(CareEventNotFoundError):
            repo.update_review_state("patient-1", "does-not-exist", ReviewState.VERIFIED)

    def test_nonexistent_event_does_not_create_a_new_item(self):
        repo, table = make_repository()
        with pytest.raises(CareEventNotFoundError):
            repo.update_review_state("patient-1", "does-not-exist", ReviewState.VERIFIED)
        assert len(table.items) == 0

    def test_only_review_state_and_verification_reason_change(self):
        # The canonical fields extraction produced must be untouched by a
        # review action - this is the "cannot arbitrarily mutate the
        # canonical CareEvent" guarantee at the persistence layer.
        repo, _table = make_repository()
        original = repo.put_event(
            make_event(event_id="ce_1", summary="original summary", subject="Dad"),
            make_context(),
            "care_event_v2",
        )
        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)

        assert updated.event.summary == original.event.summary
        assert updated.event.subject == original.event.subject
        assert updated.event.event_type == original.event.event_type
        assert updated.event.claim_stance == original.event.claim_stance
        assert updated.event.source_type == original.event.source_type
        assert updated.event.evidence == original.event.evidence
        assert updated.context.transcript_id == original.context.transcript_id

    def test_created_at_is_not_changed_by_a_review_action(self):
        repo, _table = make_repository()
        original = repo.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")
        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)
        assert updated.created_at == original.created_at

    def test_updated_at_advances_on_a_review_action(self):
        repo, table = make_repository()
        repo.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")
        table.items[("PATIENT#patient-1", "EVENT#ce_1")]["updated_at"] = "2020-01-01T00:00:00Z"
        updated = repo.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)
        assert updated.updated_at > "2020-01-01T00:00:00Z"

    def test_round_trip_survives_a_fresh_repository_instance(self):
        # Simulates "survives browser refresh": a brand new repository
        # object (as a fresh Lambda invocation would construct) reading
        # back what a previous invocation wrote.
        table = FakeCareEventsTable()
        writer = CareEventRepository(table=table)
        writer.put_event(make_event(event_id="ce_1"), make_context(), "care_event_v2")
        writer.update_review_state("patient-1", "ce_1", ReviewState.VERIFIED)

        reader = CareEventRepository(table=table)
        timeline = reader.get_timeline("patient-1")
        assert timeline[0].event.review_state == ReviewState.VERIFIED


class TestDynamoDbErrorPropagation:
    def test_client_error_from_update_item_propagates(self):
        table = FakeCareEventsTable()

        def raise_error(*args, **kwargs):
            raise ClientError({"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}}, "UpdateItem")

        table.update_item = raise_error
        repo, _table = make_repository(table)

        with pytest.raises(ClientError):
            repo.put_event(make_event(), make_context(), "care_event_v2")

    def test_error_is_not_swallowed_into_a_successful_looking_result(self):
        # put_event must either return a CareEventRecord or raise - it must
        # never catch the AWS error and return e.g. None/a partial record
        # that looks like success.
        table = FakeCareEventsTable()

        def raise_error(*args, **kwargs):
            raise ClientError({"Error": {"Code": "InternalServerError", "Message": "boom"}}, "UpdateItem")

        table.update_item = raise_error
        repo, _table = make_repository(table)

        with pytest.raises(ClientError):
            repo.put_event(make_event(), make_context(), "care_event_v2")
