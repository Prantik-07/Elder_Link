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
from backend.lambdas.get_timeline.handler import lambda_handler

ENV = {
    "CARE_EVENTS_TABLE_NAME": "test-care-events",
    "ELDERLINK_AWS_REGION": "us-east-1",
}


def _event(event_id: str) -> CareEvent:
    return CareEvent(
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


def _api_event(path_params: dict) -> dict:
    return {"pathParameters": path_params}


def _invoke_with_table(fake_table, path_params):
    with patch(
        "backend.lambdas.get_timeline.handler.CareEventRepository"
    ) as mock_repo_cls, patch.dict(os.environ, ENV):
        mock_repo_cls.return_value = CareEventRepository(table=fake_table)
        return lambda_handler(_api_event(path_params), None)


class TestValidGetTimeline:
    def test_returns_persisted_events_for_recipient(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")
        repo.put_event(_event("ce_2"), CareContext("demo-dad", "note-2"), "v1")
        repo.put_event(_event("ce_3"), CareContext("someone-else", "note-3"), "v1")

        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"})

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["care_recipient_id"] == "demo-dad"
        assert {e["id"] for e in body["events"]} == {"ce_1", "ce_2"}

    def test_response_shape_matches_frontend_care_event_dto(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"})
        body = json.loads(result["body"])
        event = body["events"][0]
        assert set(event.keys()) == {
            "id",
            "type",
            "categoryLabel",
            "title",
            "summary",
            "whatHappened",
            "occurredAt",
            "reportedBy",
            "status",
            "evidence",
            "verificationReason",
        }

    def test_no_raw_dynamodb_attribute_value_leakage(self):
        fake_table = FakeCareEventsTable()
        repo = CareEventRepository(table=fake_table)
        repo.put_event(_event("ce_1"), CareContext("demo-dad", "note-1"), "v1")

        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"})
        body_text = result["body"]
        # Raw DynamoDB item/attribute-value keys must never appear in the
        # response body - only the frontend DTO's own field names.
        for leaked in ("pk", "sk", '"S":', '"N":', 'AttributeValue', 'claim_stance', 'review_state'):
            assert leaked not in body_text

    def test_cors_header_present(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"})
        assert result["headers"]["Access-Control-Allow-Origin"]


class TestEmptyTimeline:
    def test_empty_timeline_returns_empty_list_not_error(self):
        fake_table = FakeCareEventsTable()
        result = _invoke_with_table(fake_table, {"care_recipient_id": "nobody-yet"})
        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["events"] == []


class TestInvalidCareRecipientId:
    def test_missing_path_parameter_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler({"pathParameters": None}, None)
        assert result["statusCode"] == 400

    def test_blank_path_parameter_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler(_api_event({"care_recipient_id": "   "}), None)
        assert result["statusCode"] == 400


class TestRepositoryFailure:
    def test_dynamodb_query_failure_returns_502(self):
        fake_table = FakeCareEventsTable()

        def failing_query(*args, **kwargs):
            raise ClientError(
                {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}},
                "Query",
            )

        fake_table.query = failing_query
        result = _invoke_with_table(fake_table, {"care_recipient_id": "demo-dad"})
        assert result["statusCode"] == 502

    def test_missing_table_env_var_returns_500(self):
        with patch.dict(os.environ, {}, clear=True):
            result = lambda_handler(_api_event({"care_recipient_id": "demo-dad"}), None)
        assert result["statusCode"] == 500


class TestUsesCareTimelineIndex:
    def test_repository_get_timeline_called_not_a_scan(self):
        fake_table = MagicMock()
        fake_table.query.return_value = {"Items": []}
        with patch(
            "backend.lambdas.get_timeline.handler.CareEventRepository"
        ) as mock_repo_cls, patch.dict(os.environ, ENV):
            mock_repo_cls.return_value = CareEventRepository(table=fake_table)
            lambda_handler(_api_event({"care_recipient_id": "demo-dad"}), None)

        fake_table.query.assert_called_once()
        _, kwargs = fake_table.query.call_args
        assert kwargs["IndexName"] == "CareTimelineIndex"
        fake_table.scan.assert_not_called()
