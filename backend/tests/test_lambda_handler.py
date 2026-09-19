import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError


def _not_found_error(operation: str, code: str = "404") -> ClientError:
    # S3 HeadObject on a missing key returns 403 (not 404) when the caller
    # lacks s3:ListBucket - both codes mean "doesn't exist" for our purposes.
    return ClientError(
        {"Error": {"Code": code, "Message": "Not Found"}}, operation
    )

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Don't mock core.transcription at module level - let the tests patch the handler's imports directly
# We need to ensure core.transcription can be imported
if "core.transcription" not in sys.modules:
    mock_transcription = MagicMock()
    mock_transcription.MockTranscriptionProvider = MagicMock()
    mock_transcription.VoxtralProvider = MagicMock()
    mock_transcription.TranscriptionResult = MagicMock()
    sys.modules["core.transcription"] = mock_transcription

from backend.lambdas.process_audio.handler import (
    extract_note_id,
    get_audio_format,
    get_provider,
    is_valid_audio_object,
    lambda_handler,
)


class TestExtractNoteId:
    def test_simple_filename(self):
        assert extract_note_id("audio/test-note.wav") == "test-note"

    def test_filename_with_multiple_dots(self):
        assert extract_note_id("audio/my.note.v2.wav") == "my.note.v2"

    def test_filename_without_extension(self):
        assert extract_note_id("audio/note123") == "note123"

    def test_nested_path(self):
        assert extract_note_id("audio/subdir/note.wav") == "note"


class TestGetAudioFormat:
    def test_wav(self):
        assert get_audio_format("audio/test.wav") == "wav"

    def test_mp3(self):
        assert get_audio_format("audio/test.mp3") == "mp3"

    def test_uppercase_extension(self):
        assert get_audio_format("audio/test.WAV") == "wav"

    def test_no_extension(self):
        assert get_audio_format("audio/test") == "test"


class TestIsValidAudioObject:
    def test_valid_wav_in_audio_prefix(self):
        assert is_valid_audio_object("audio/note.wav") is True

    def test_valid_mp3_in_audio_prefix(self):
        assert is_valid_audio_object("audio/note.mp3") is True

    def test_valid_flac_in_audio_prefix(self):
        assert is_valid_audio_object("audio/note.flac") is True

    def test_valid_ogg_in_audio_prefix(self):
        assert is_valid_audio_object("audio/note.ogg") is True

    def test_valid_m4a_in_audio_prefix(self):
        assert is_valid_audio_object("audio/note.m4a") is True

    def test_valid_webm_in_audio_prefix(self):
        # Day 4: Chrome/Firefox's MediaRecorder default output format for
        # real browser voice ingestion - see the module docstring on
        # SUPPORTED_AUDIO_EXTENSIONS for why this isn't in
        # VoxtralProvider.SUPPORTED_FORMATS too.
        assert is_valid_audio_object("audio/note.webm") is True

    def test_aiff_rejected_not_supported_by_provider(self):
        # aiff is not part of the Bedrock Converse AudioFormat enum, so it
        # must not be accepted here even though older code once allowed it.
        assert is_valid_audio_object("audio/note.aiff") is False

    def test_invalid_outside_audio_prefix(self):
        assert is_valid_audio_object("transcripts/note.json") is False

    def test_invalid_root_level(self):
        assert is_valid_audio_object("note.wav") is False

    def test_invalid_extension(self):
        assert is_valid_audio_object("audio/note.txt") is False

    def test_invalid_transcript_object(self):
        assert is_valid_audio_object("transcripts/test-note.json") is False


class TestGetProvider:
    def test_mock_provider(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "mock"}):
            # Just test that it doesn't raise an error and returns a provider
            # The actual provider classes are imported from core.transcription
            # which is mocked at module level
            provider = get_provider()
            assert provider is not None

    def test_voxtral_provider(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "voxtral"}):
            provider = get_provider()
            assert provider is not None

    def test_invalid_provider_raises_error(self):
        with patch.dict(os.environ, {"TRANSCRIPTION_PROVIDER": "invalid"}):
            with pytest.raises(ValueError) as exc_info:
                get_provider()
            assert "Invalid TRANSCRIPTION_PROVIDER" in str(exc_info.value)
            assert "mock" in str(exc_info.value)
            assert "voxtral" in str(exc_info.value)


class TestLambdaHandler:
    def create_s3_event(self, bucket: str, key: str) -> dict:
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

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    @patch("backend.lambdas.process_audio.handler.get_provider")
    def test_valid_event_mock_provider_success(
        self, mock_get_provider, mock_boto_client
    ):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        # First head_object = audio size check (exists). Second = transcript
        # idempotency check (must not exist yet, so raise 404).
        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024},
            _not_found_error("HeadObject"),
        ]
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fake audio")}

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_id = "mock-transcriber-v1"
        mock_provider.transcribe.return_value = MagicMock(
            success=True,
            text="Test transcript",
            provider="mock",
            model="mock-transcriber-v1",
            error=None,
        )
        mock_get_provider.return_value = mock_provider

        with patch.dict(os.environ, {
            "TRANSCRIPTION_PROVIDER": "mock",
            "AUDIO_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/test-note.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["note_id"] == "test-note"
        assert body["status"] == "completed"
        assert body["transcript"] == "Test transcript"
        assert body["provider"] == "mock"

        mock_s3.put_object.assert_called_once()
        call_args = mock_s3.put_object.call_args
        assert call_args[1]["Bucket"] == "test-bucket"
        assert call_args[1]["Key"] == "transcripts/test-note.json"

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_invalid_event_missing_bucket(self, mock_boto_client):
        with patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "test-bucket"}):
            event = {"detail": {"object": {"key": "audio/test.wav"}}}
            result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        assert "Invalid event structure" in result["body"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_object_outside_audio_prefix_ignored(self, mock_boto_client):
        with patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "test-bucket"}):
            event = self.create_s3_event("test-bucket", "transcripts/test-note.json")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        assert "Ignored non-audio object" in result["body"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_unsupported_extension_rejected(self, mock_boto_client):
        with patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "test-bucket"}):
            event = self.create_s3_event("test-bucket", "audio/test.txt")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        assert "Ignored non-audio object" in result["body"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    @patch("backend.lambdas.process_audio.handler.get_provider")
    def test_mock_provider_failure_handled(
        self, mock_get_provider, mock_boto_client
    ):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024},
            _not_found_error("HeadObject"),
        ]
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fake audio")}

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_id = "mock-transcriber-v1"
        mock_provider.transcribe.return_value = MagicMock(
            success=False,
            text="",
            provider="mock",
            model="mock-transcriber-v1",
            error="Transcription failed",
        )
        mock_get_provider.return_value = mock_provider

        with patch.dict(os.environ, {
            "TRANSCRIPTION_PROVIDER": "mock",
            "AUDIO_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/test-note.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["status"] == "failed"
        assert body["error"] == "Transcription failed"

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_file_too_large_rejected(self, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.return_value = {"ContentLength": 20000000}

        with patch.dict(os.environ, {
            "AUDIO_BUCKET_NAME": "test-bucket",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/large.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 413
        assert "too large" in result["body"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_bucket_mismatch_rejected(self, mock_boto_client):
        with patch.dict(os.environ, {"AUDIO_BUCKET_NAME": "expected-bucket"}):
            event = self.create_s3_event("wrong-bucket", "audio/test.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 400
        assert "Bucket mismatch" in result["body"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    @patch("backend.lambdas.process_audio.handler.get_provider")
    def test_transcript_json_structure(self, mock_get_provider, mock_boto_client):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024},
            _not_found_error("HeadObject"),
        ]
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"audio")}

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_id = "mock-transcriber-v1"
        mock_provider.transcribe.return_value = MagicMock(
            success=True,
            text="Test transcript",
            provider="mock",
            model="mock-transcriber-v1",
            error=None,
        )
        mock_get_provider.return_value = mock_provider

        with patch.dict(os.environ, {
            "TRANSCRIPTION_PROVIDER": "mock",
            "AUDIO_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/note123.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        body = json.loads(result["body"])

        required_fields = [
            "note_id", "source_audio_key", "provider", "model",
            "status", "transcript", "processed_at", "error"
        ]
        for field in required_fields:
            assert field in body, f"Missing field: {field}"

        assert body["note_id"] == "note123"
        assert body["source_audio_key"] == "audio/note123.wav"
        assert body["provider"] == "mock"
        assert body["model"] == "mock-transcriber-v1"
        assert body["status"] == "completed"
        assert body["transcript"] == "Test transcript"
        assert body["error"] is None
        assert "T" in body["processed_at"]

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    @patch("backend.lambdas.process_audio.handler.get_provider")
    def test_duplicate_event_skips_reprocessing(
        self, mock_get_provider, mock_boto_client
    ):
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3

        # Both head_object calls succeed: the audio object exists AND a
        # transcript for it already exists (e.g. an at-least-once redelivery
        # of the same S3 event). The handler must not reprocess.
        mock_s3.head_object.return_value = {"ContentLength": 1024}

        with patch.dict(os.environ, {
            "TRANSCRIPTION_PROVIDER": "mock",
            "AUDIO_BUCKET_NAME": "test-bucket",
            "AWS_REGION": "us-east-1",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/test-note.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        assert "Already processed" in result["body"]
        mock_s3.get_object.assert_not_called()
        mock_s3.put_object.assert_not_called()
        mock_get_provider.assert_not_called()

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    @patch("backend.lambdas.process_audio.handler.get_provider")
    def test_transcript_head_object_403_is_treated_as_not_found(
        self, mock_get_provider, mock_boto_client
    ):
        # Regression test: this role has no s3:ListBucket, so S3 returns 403
        # (not 404) for HeadObject on a transcript key that doesn't exist yet.
        # That must NOT be mistaken for a real permissions failure.
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024},
            _not_found_error("HeadObject", code="403"),
        ]
        mock_s3.get_object.return_value = {"Body": MagicMock(read=lambda: b"fake audio")}

        mock_provider = MagicMock()
        mock_provider.provider_name = "mock"
        mock_provider.model_id = "mock-transcriber-v1"
        mock_provider.transcribe.return_value = MagicMock(
            success=True, text="Test transcript", provider="mock",
            model="mock-transcriber-v1", error=None,
        )
        mock_get_provider.return_value = mock_provider

        with patch.dict(os.environ, {
            "TRANSCRIPTION_PROVIDER": "mock",
            "AUDIO_BUCKET_NAME": "test-bucket",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/test-note.wav")
            result = lambda_handler(event, None)

        assert result["statusCode"] == 200
        mock_s3.put_object.assert_called_once()

    @patch("backend.lambdas.process_audio.handler.boto3.client")
    def test_unexpected_s3_error_propagates(self, mock_boto_client):
        # A genuine AWS/infra failure (not a 404 on the idempotency check)
        # must propagate so Lambda records it as an execution error instead
        # of it looking like a successful invocation.
        mock_s3 = MagicMock()
        mock_boto_client.return_value = mock_s3
        mock_s3.head_object.side_effect = [
            {"ContentLength": 1024},
            ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "denied"}},
                "HeadObject",
            ),
        ]

        with patch.dict(os.environ, {
            "AUDIO_BUCKET_NAME": "test-bucket",
            "MAX_AUDIO_SIZE_BYTES": "10485760",
        }):
            event = self.create_s3_event("test-bucket", "audio/test-note.wav")
            with pytest.raises(ClientError):
                lambda_handler(event, None)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])