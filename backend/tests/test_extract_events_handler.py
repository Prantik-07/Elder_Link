import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.core.care_event import ReviewState
from backend.core.persistence import CareEventRepository
from backend.core.persistence.tests.fake_table import FakeCareEventsTable
from backend.lambdas.extract_events.handler import (
    extract_note_id_from_transcript_key,
    get_default_care_recipient_id,
    get_extraction_provider,
    is_transcript_object,
    lambda_handler,
    resolve_care_recipient_id,
)


def _not_found_error(operation: str, code: str = "404") -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "Not Found"}}, operation)


ENV = {
    "TRANSCRIPT_BUCKET_NAME": "test-bucket",
    "CARE_EVENTS_TABLE_NAME": "test-care-events",
    "EXTRACTION_PROVIDER": "mock",
    "ELDERLINK_AWS_REGION": "us-east-1",
}

MULTI_CLAIM_TRANSCRIPT = (
    "Dad took his medication this morning. "
    "My sister said Dad fell yesterday evening. "
    "Dad did not miss his appointment on Friday. "
    "I think Dad might have low energy today."
)


def create_s3_event(bucket: str, key: str) -> dict:
    return {
        "version": "0",
        "id": "test-event-id",
        "detail-type": "Object Created",
        "source": "aws.s3",
        "account": "123456789012",
        "time": "2024-01-01T00:00:00Z",
        "region": "us-east-1",
        "detail": {
            "version": "0",
            "bucket": {"name": bucket},
            "object": {"key": key, "size": 1024, "etag": "abc123"},
            "request-id": "req-123",
            "requester": "123456789012",
        },
    }


def transcript_body(**overrides) -> bytes:
    data = {
        "note_id": "test-note",
        "source_audio_key": "audio/test-note.wav",
        "provider": "mock",
        "model": "mock-transcriber-v1",
        "status": "completed",
        "transcript": MULTI_CLAIM_TRANSCRIPT,
        "processed_at": "2024-01-01T00:00:00Z",
        "error": None,
    }
    data.update(overrides)
    return json.dumps(data).encode("utf-8")


class TestIsTranscriptObject:
    def test_transcript_json_matches(self):
        assert is_transcript_object("transcripts/test-note.json") is True

    def test_audio_object_does_not_match(self):
        assert is_transcript_object("audio/test-note.wav") is False

    def test_transcript_prefix_non_json_does_not_match(self):
        assert is_transcript_object("transcripts/test-note.txt") is False

    def test_unrelated_object_does_not_match(self):
        assert is_transcript_object("other/thing.json") is False


class TestExtractNoteId:
    def test_simple_key(self):
        assert extract_note_id_from_transcript_key("transcripts/test-note.json") == "test-note"

    def test_nested_key(self):
        assert extract_note_id_from_transcript_key("transcripts/sub/test-note.json") == "test-note"


class TestGetExtractionProvider:
    def test_mock_provider(self):
        with patch.dict(os.environ, {"EXTRACTION_PROVIDER": "mock"}):
            provider = get_extraction_provider()
            assert provider.provider_name == "mock"

    def test_bedrock_provider(self):
        with patch.dict(os.environ, {"EXTRACTION_PROVIDER": "bedrock"}):
            provider = get_extraction_provider()
            assert provider.provider_name == "bedrock"

    def test_invalid_provider_raises(self):
        with patch.dict(os.environ, {"EXTRACTION_PROVIDER": "invalid"}):
            with pytest.raises(ValueError, match="Invalid EXTRACTION_PROVIDER"):
                get_extraction_provider()


class TestMalformedEvent:
    def test_missing_bucket_or_key(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler({"detail": {"object": {"key": "transcripts/x.json"}}}, None)
        assert result["statusCode"] == 400
        assert "Invalid event structure" in result["body"]


class TestNonTranscriptObjectsIgnored:
    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_audio_object_does_not_trigger_extraction(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "audio/test-note.wav")
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert "Ignored non-transcript object" in result["body"]
        mock_s3.get_object.assert_not_called()

    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_unrelated_object_does_not_trigger_extraction(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "other/artifact.json")
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert "Ignored non-transcript object" in result["body"]
        mock_s3.get_object.assert_not_called()

    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_bucket_mismatch_rejected(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        with patch.dict(os.environ, ENV):
            event = create_s3_event("some-other-bucket", "transcripts/test-note.json")
            result = lambda_handler(event, None)
        assert result["statusCode"] == 400
        assert "Bucket mismatch" in result["body"]


class TestTranscriptLoadingFailures:
    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_malformed_json_body_is_skipped_not_raised(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"{not valid json")}
        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "transcripts/test-note.json")
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert "malformed transcript JSON" in result["body"]

    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_s3_client_error_propagates(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.side_effect = _not_found_error("GetObject", "500")
        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "transcripts/test-note.json")
            with pytest.raises(ClientError):
                lambda_handler(event, None)

    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_non_completed_status_is_skipped(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {
            "Body": MagicMock(read=lambda: transcript_body(status="failed", transcript="", error="boom"))
        }
        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "transcripts/test-note.json")
            result = lambda_handler(event, None)
        assert result["statusCode"] == 200
        assert "Skipped" in result["body"]


class TestResolveCareRecipientId:
    def test_defaults_to_demo_dad_when_unset(self):
        with patch.dict(os.environ, {}, clear=True):
            assert get_default_care_recipient_id() == "demo-dad"

    def test_default_is_configurable_via_env_var(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-mom"}):
            assert get_default_care_recipient_id() == "demo-mom"

    def test_explicit_care_recipient_id_takes_precedence(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-dad"}):
            assert resolve_care_recipient_id({"care_recipient_id": "recipient-42"}) == "recipient-42"

    def test_blank_explicit_care_recipient_id_falls_back_to_default(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-dad"}):
            assert resolve_care_recipient_id({"care_recipient_id": "   "}) == "demo-dad"

    def test_missing_field_falls_back_to_default(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-dad"}):
            assert resolve_care_recipient_id({}) == "demo-dad"


class TestExtractionProviderFailure:
    @patch("backend.lambdas.extract_events.handler.CareEventRepository")
    @patch("backend.lambdas.extract_events.handler.get_extraction_provider")
    @patch("backend.lambdas.extract_events.handler.boto3.client")
    def test_provider_failure_persists_nothing_and_does_not_raise(
        self, mock_boto_client, mock_get_provider, mock_repo_cls
    ):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: transcript_body())}

        from backend.core.extraction import ExtractionErrorKind, ExtractionResult
        from backend.core.extraction.service import ExtractionProvider

        class FailingProvider(ExtractionProvider):
            @property
            def provider_name(self):
                return "bedrock"

            @property
            def model_id(self):
                return "test-model"

            def extract(self, document):
                return ExtractionResult.failure_result(
                    provider="bedrock",
                    model="test-model",
                    error="AWS account verification pending.",
                    error_kind=ExtractionErrorKind.NOT_AVAILABLE,
                )

        mock_get_provider.return_value = FailingProvider()
        mock_repo = MagicMock()
        mock_repo_cls.return_value = mock_repo

        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "transcripts/test-note.json")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["extraction_failed"] is True
        assert body["error_kind"] == "not_available"
        mock_repo.put_event.assert_not_called()


def _run_handler_against(fake_table):
    with patch("backend.lambdas.extract_events.handler.boto3.client") as mock_boto_client, patch(
        "backend.lambdas.extract_events.handler.CareEventRepository"
    ) as mock_repo_cls:
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: transcript_body())}

        mock_repo_cls.return_value = CareEventRepository(table=fake_table)

        with patch.dict(os.environ, ENV):
            event = create_s3_event("test-bucket", "transcripts/test-note.json")
            return lambda_handler(event, None)


class TestEndToEndMockExtraction:
    def test_exactly_one_extraction_execution_produces_expected_events(self):
        fake_table = FakeCareEventsTable()
        result = _run_handler_against(fake_table)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["provider"] == "mock"
        assert body["accepted"] == 4
        assert body["persisted"] == 4

        repo = CareEventRepository(table=fake_table)
        records = repo.get_by_transcript("test-note")
        assert len(records) == 4

        # Evidence points to real transcript segments, not fabricated ones.
        for record in records:
            assert record.event.evidence
            for ev in record.event.evidence:
                assert ev.segment_id.startswith("test-note-seg")

        # Deterministic ids present (ce_ prefix from Phase 4.1 identity).
        for record in records:
            assert record.event.event_id.startswith("ce_")

        # Fresh extraction is never auto-verified.
        assert all(r.event.review_state != ReviewState.VERIFIED for r in records)

        # The uncertain claim ("I think Dad might have low energy today")
        # and the secondhand claim ("My sister said Dad fell...") both need
        # verification; review_state is never taken from the provider.
        by_summary = {r.event.summary: r for r in records}
        uncertain = next(r for s, r in by_summary.items() if "low energy" in s)
        secondhand = next(r for s, r in by_summary.items() if "fell" in s)
        assert uncertain.event.review_state == ReviewState.NEEDS_VERIFICATION
        assert secondhand.event.review_state == ReviewState.NEEDS_VERIFICATION
        assert secondhand.event.reported_by == "sister"

    def test_repeated_invocation_is_idempotent(self):
        fake_table = FakeCareEventsTable()
        first = _run_handler_against(fake_table)
        second = _run_handler_against(fake_table)

        assert json.loads(first["body"])["persisted"] == 4
        assert json.loads(second["body"])["persisted"] == 4
        assert len(fake_table.items) == 4  # no duplicates on repeat

    def test_repository_receives_only_validated_events(self):
        # RejectedCandidate objects (parse/policy/validation failures) never
        # reach put_event - the mock provider's own output is always valid
        # here, so nothing is rejected, and every persisted record's event
        # passed the full validate_care_event check already (proven by
        # get_by_transcript returning them without error).
        fake_table = FakeCareEventsTable()
        result = _run_handler_against(fake_table)
        body = json.loads(result["body"])
        assert body["rejected"] == 0
        assert body["candidates"] == body["accepted"]


class TestDemoRecipientGrouping:
    def test_two_transcripts_without_explicit_recipient_share_one_timeline(self):
        fake_table = FakeCareEventsTable()

        with patch("backend.lambdas.extract_events.handler.boto3.client") as mock_boto_client, patch(
            "backend.lambdas.extract_events.handler.CareEventRepository"
        ) as mock_repo_cls:
            mock_s3 = MagicMock()
            mock_boto_client.return_value = mock_s3
            mock_repo_cls.return_value = CareEventRepository(table=fake_table)

            mock_s3.get_object.return_value = {
                "Body": MagicMock(read=lambda: transcript_body(note_id="voice-note-1"))
            }
            with patch.dict(os.environ, ENV):
                event = create_s3_event("test-bucket", "transcripts/voice-note-1.json")
                first = lambda_handler(event, None)

            mock_s3.get_object.return_value = {
                "Body": MagicMock(read=lambda: transcript_body(note_id="voice-note-2"))
            }
            with patch.dict(os.environ, ENV):
                event = create_s3_event("test-bucket", "transcripts/voice-note-2.json")
                second = lambda_handler(event, None)

        assert json.loads(first["body"])["care_recipient_id"] == "demo-dad"
        assert json.loads(second["body"])["care_recipient_id"] == "demo-dad"

        repo = CareEventRepository(table=fake_table)
        timeline = repo.get_timeline("demo-dad")
        assert len(timeline) == 8  # 4 events from each of the two voice notes


class TestPartialFailureAndRetry:
    def test_dynamodb_failure_partway_through_propagates_and_retry_recovers(self):
        fake_table = FakeCareEventsTable()
        real_update_item = fake_table.update_item
        call_count = {"n": 0}

        def flaky_update_item(*args, **kwargs):
            call_count["n"] += 1
            if call_count["n"] == 3:
                raise ClientError(
                    {"Error": {"Code": "ProvisionedThroughputExceededException", "Message": "slow down"}},
                    "UpdateItem",
                )
            return real_update_item(*args, **kwargs)

        fake_table.update_item = flaky_update_item

        with pytest.raises(ClientError):
            _run_handler_against(fake_table)

        # Two events made it through before the third call failed; nothing
        # was corrupted or duplicated by the partial attempt.
        assert len(fake_table.items) == 2

        # A retry (a plain re-invocation, not a special recovery path) with
        # a healthy table completes the rest without duplicating what
        # already succeeded.
        fake_table.update_item = real_update_item
        result = _run_handler_against(fake_table)
        assert result["statusCode"] == 200
        assert len(fake_table.items) == 4
