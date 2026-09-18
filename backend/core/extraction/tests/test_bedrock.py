"""Tests the plumbing (JSON parsing, error classification) with a mocked
boto3 client. None of these exercise a live model - see bedrock.py's module
docstring: Bedrock access for this account is still pending verification,
and that remains true regardless of what these mocks return.
"""

import json
from unittest.mock import MagicMock, patch

from botocore.exceptions import ClientError

from backend.core.care_event import TranscriptDocument, TranscriptSegment
from backend.core.extraction import BedrockExtractionProvider, ExtractionErrorKind


def document() -> TranscriptDocument:
    return TranscriptDocument(
        transcript_id="t1", full_text="Dad took his pills.", segments=[TranscriptSegment("s1", "Dad took his pills.")]
    )


class TestProviderIdentity:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_provider_name(self, mock_boto_client):
        provider = BedrockExtractionProvider()
        assert provider.provider_name == "bedrock"
        assert provider.model_id


class TestVerificationPending:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_access_denied_with_verification_message_is_not_available(self, mock_boto_client):
        mock_client = MagicMock()
        mock_client.converse.side_effect = ClientError(
            {"Error": {"Code": "AccessDeniedException", "Message": "account verification pending"}}, "Converse"
        )
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        result = provider.extract(document())

        assert result.success is False
        assert result.error_kind == ExtractionErrorKind.NOT_AVAILABLE
        assert "verification" in result.error.lower()


class TestMalformedModelJson:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_non_json_response_text_is_invalid_json_error(self, mock_boto_client):
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": "sure, here are the events: not actually json"}]}}
        }
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        result = provider.extract(document())

        assert result.success is False
        assert result.error_kind == ExtractionErrorKind.INVALID_JSON

    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_json_without_events_key_is_invalid_json_error(self, mock_boto_client):
        mock_client = MagicMock()
        mock_client.converse.return_value = {
            "output": {"message": {"content": [{"text": json.dumps({"not_events": []})}]}}
        }
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        result = provider.extract(document())

        assert result.success is False
        assert result.error_kind == ExtractionErrorKind.INVALID_JSON


class TestProviderFailure:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_generic_client_error_is_provider_failure(self, mock_boto_client):
        mock_client = MagicMock()
        mock_client.converse.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "rate limited"}}, "Converse"
        )
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        result = provider.extract(document())

        assert result.success is False
        assert result.error_kind == ExtractionErrorKind.PROVIDER_FAILURE


class TestWellFormedResponseParsesIntoCandidates:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_valid_json_events_list_is_returned_as_candidates(self, mock_boto_client):
        # Tests only that a well-formed response is parsed correctly - not
        # a claim that a live model produces output like this.
        payload = {
            "events": [
                {
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
            ]
        }
        mock_client = MagicMock()
        mock_client.converse.return_value = {"output": {"message": {"content": [{"text": json.dumps(payload)}]}}}
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        result = provider.extract(document())

        assert result.success is True
        assert result.candidate_events == payload["events"]


class TestEmptyDocument:
    @patch("backend.core.extraction.bedrock.boto3.client")
    def test_no_segments_short_circuits_without_calling_bedrock(self, mock_boto_client):
        mock_client = MagicMock()
        mock_boto_client.return_value = mock_client

        provider = BedrockExtractionProvider()
        empty_doc = TranscriptDocument(transcript_id="t", full_text="", segments=[])
        result = provider.extract(empty_doc)

        assert result.success is True
        assert result.candidate_events == []
        mock_client.converse.assert_not_called()
