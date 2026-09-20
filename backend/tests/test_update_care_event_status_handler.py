import json
import os
from unittest.mock import MagicMock, patch

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
    TemporalPrecision,
)
from backend.core.persistence import CareContext, CareEventRepository
from backend.core.persistence.tests.fake_table import FakeCareEventsTable
from backend.lambdas.update_care_event_status.handler import lambda_handler

ENV = {
    "CARE_EVENTS_TABLE_NAME": "test-care-events",
    "ELDERLINK_AWS_REGION": "us-east-1",
}


def _event(event_id: str, **overrides) -> CareEvent:
    defaults = dict(
        event_id=event_id,
        event_type=EventType.MEDICATION,
        subject="Dad",
        summary="Dad took his morning medication.",
        claim_stance=ClaimStance.ASSERTED,
        source_type=SourceType.FIRSTHAND,
        review_state=ReviewState.UNREVIEWED,
        occurred_at=TemporalInfo(precision=TemporalPrecision.EXACT_TIMESTAMP, timestamp="2024-01-01T08:00:00Z"),
        evidence=[Evidence(segment_id="seg-01")],
        reported_by="Priya",
    )
    defaults.update(overrides)
    return CareEvent(**defaults)


def _api_event(path_params: dict, body: dict | None = None) -> dict:
    return {
        "pathParameters": path_params,
        "body": json.dumps(body) if body is not None else None,
    }


def _invoke_with_table(fake_table, path_params, body):
    with patch(
        "backend.lambdas.update_care_event_status.handler.CareEventRepository"
    ) as mock_repo_cls, patch.dict(os.environ, ENV):
        mock_repo_cls.return_value = CareEventRepository(table=fake_table)
        return lambda_handler(_api_event(path_params, body), None)


class TestValidStatusUpdate:
    def test_mark_verified_returns_200_and_updated_status(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["id"] == "ce_1"
        assert body["status"] == "verified"
        assert body["verificationReason"] is None

    def test_keep_uncertain_returns_200_and_needs_verification_status(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "uncertain"}
        )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "needs_verification"
        assert body["verificationReason"]

    def test_response_matches_frontend_care_event_dto_shape(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}
        )
        body = json.loads(result["body"])
        assert set(body.keys()) == {
            "id",
            "type",
            "categoryLabel",
            "title",
            "summary",
            "whatHappened",
            "occurredAt",
            "occurredAtPrecision",
            "reportedBy",
            "status",
            "evidence",
            "verificationReason",
        }

    def test_cors_header_present_on_success(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}
        )
        assert result["headers"]["Access-Control-Allow-Origin"]


class TestPersistenceRoundTrip:
    def test_status_survives_a_fresh_read(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"})

        # A brand new repository instance reading the same underlying
        # table simulates a page refresh hitting a fresh Lambda
        # invocation - the write must be durable, not held in any
        # in-memory state this handler owns.
        fresh_repo = CareEventRepository(table=fake_table)
        timeline = fresh_repo.get_timeline("demo-dad")
        assert timeline[0].event.review_state == ReviewState.VERIFIED


class TestNonexistentEvent:
    def test_unknown_event_id_returns_404(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "does-not-exist"}, {"status": "verified"}
        )
        assert result["statusCode"] == 404
        body = json.loads(result["body"])
        assert "error" in body

    def test_unknown_event_id_does_not_create_a_new_item(self):
        fake_table = FakeCareEventsTable()
        _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "does-not-exist"}, {"status": "verified"}
        )
        assert len(fake_table.items) == 0


class TestInvalidStatus:
    def test_missing_status_returns_400(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {})
        assert result["statusCode"] == 400

    def test_unsupported_status_value_returns_400(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "deleted"}
        )
        assert result["statusCode"] == 400

    def test_needs_verification_is_not_a_directly_settable_status(self):
        # "needs_verification" is the default/no-action state, never
        # something a caregiver click sets directly - only "verified" and
        # "uncertain" are valid caregiver-initiated transitions.
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "needs_verification"}
        )
        assert result["statusCode"] == 400

    def test_malformed_json_body_returns_400(self):
        fake_table = FakeCareEventsTable()
        with patch(
            "backend.lambdas.update_care_event_status.handler.CareEventRepository"
        ) as mock_repo_cls, patch.dict(os.environ, ENV):
            mock_repo_cls.return_value = CareEventRepository(table=fake_table)
            result = lambda_handler(
                {"pathParameters": {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, "body": "{not json"},
                None,
            )
        assert result["statusCode"] == 400

    def test_missing_path_parameters_returns_400(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"}, {"status": "verified"})
        assert result["statusCode"] == 400


class TestAuthorizationBoundaryConsistentWithDemoModel:
    """This endpoint intentionally applies no authentication/authorization,
    matching get_timeline's existing, documented demo posture - the same
    unguessable-URL-only security boundary the rest of this API already
    uses. These tests document that boundary rather than assert on an
    auth mechanism that doesn't exist by design."""

    def test_any_caller_can_update_any_known_care_recipients_event(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("some-other-recipient", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "some-other-recipient", "event_id": "ce_1"}, {"status": "verified"}
        )
        assert result["statusCode"] == 200

    def test_mismatched_care_recipient_id_is_treated_as_not_found_not_leaked(self):
        # Attempting to verify a real event_id under the WRONG
        # care_recipient_id must behave identically to a nonexistent
        # event (404), never silently succeed or reveal that the event_id
        # exists under a different recipient - the base table key is
        # (care_recipient_id, event_id) together, not event_id alone.
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "someone-else", "event_id": "ce_1"}, {"status": "verified"}
        )
        assert result["statusCode"] == 404


class TestRepositoryFailure:
    def test_dynamodb_update_failure_returns_502(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        def failing_update(*args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}},
                "UpdateItem",
            )

        fake_table.update_item = failing_update
        result = _invoke_with_table(
            fake_table, {"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}
        )
        assert result["statusCode"] == 502

    def test_missing_table_env_var_returns_500(self):
        with patch.dict(os.environ, {}, clear=True):
            result = lambda_handler(
                _api_event({"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}), None
            )
        assert result["statusCode"] == 500


class TestUsesTargetedUpdateNotAScanOrQuery:
    def test_update_item_called_directly_by_key(self):
        fake_table = MagicMock()
        fake_table.update_item.return_value = {
            "Attributes": {
                **_event_item_stub(),
            }
        }
        with patch(
            "backend.lambdas.update_care_event_status.handler.CareEventRepository"
        ) as mock_repo_cls, patch.dict(os.environ, ENV):
            mock_repo_cls.return_value = CareEventRepository(table=fake_table)
            lambda_handler(
                _api_event({"care_recipient_id": "demo-dad", "event_id": "ce_1"}, {"status": "verified"}), None
            )
        fake_table.update_item.assert_called_once()
        fake_table.query.assert_not_called()


def _event_item_stub() -> dict:
    return {
        "pk": "PATIENT#demo-dad",
        "sk": "EVENT#ce_1",
        "event_id": "ce_1",
        "care_recipient_id": "demo-dad",
        "transcript_id": "note-1",
        "caregiver_id": None,
        "extraction_version": "v1",
        "event_type": "medication",
        "subject": "Dad",
        "summary": "Dad took his morning medication.",
        "claim_stance": "asserted",
        "source_type": "firsthand",
        "reported_by": "Priya",
        "review_state": "verified",
        "occurred_at": {"precision": "exact_timestamp", "timestamp": "2024-01-01T08:00:00Z", "date": None, "expression": None},
        "evidence": [{"segment_id": "seg-01", "start_time": None, "end_time": None}],
        "verification_reason": None,
        "created_at": "2024-01-01T08:01:00Z",
        "updated_at": "2024-01-01T08:01:00Z",
    }
