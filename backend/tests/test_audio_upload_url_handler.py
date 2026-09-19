import json
import os
from unittest.mock import MagicMock, patch

import pytest
from botocore.exceptions import ClientError

from backend.lambdas.audio_upload_url.handler import (
    CONTENT_TYPE_EXTENSIONS,
    build_object_key,
    get_default_care_recipient_id,
    lambda_handler,
    sanitize_care_recipient_id,
)

ENV = {
    "AUDIO_BUCKET_NAME": "test-audio-bucket",
    "ELDERLINK_AWS_REGION": "us-east-1",
}


def _api_event(body: dict) -> dict:
    return {"body": json.dumps(body)}


class TestSanitizeCareRecipientId:
    def test_valid_id_passed_through(self):
        assert sanitize_care_recipient_id("demo-dad") == "demo-dad"

    def test_missing_falls_back_to_default(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-dad"}):
            assert sanitize_care_recipient_id(None) == "demo-dad"
            assert sanitize_care_recipient_id("") == "demo-dad"
            assert sanitize_care_recipient_id("   ") == "demo-dad"

    def test_unsafe_characters_fall_back_to_default(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-dad"}):
            assert sanitize_care_recipient_id("../../etc/passwd") == "demo-dad"
            assert sanitize_care_recipient_id("demo dad") == "demo-dad"
            assert sanitize_care_recipient_id("demo/dad") == "demo-dad"
            assert sanitize_care_recipient_id("a" * 100) == "demo-dad"

    def test_default_is_configurable(self):
        with patch.dict(os.environ, {"DEFAULT_CARE_RECIPIENT_ID": "demo-mom"}):
            assert get_default_care_recipient_id() == "demo-mom"
            assert sanitize_care_recipient_id(None) == "demo-mom"


class TestBuildObjectKey:
    def test_key_is_under_audio_prefix(self):
        key = build_object_key("demo-dad", "webm")
        assert key.startswith("audio/demo-dad-")
        assert key.endswith(".webm")

    def test_two_calls_never_collide(self):
        keys = {build_object_key("demo-dad", "webm") for _ in range(20)}
        assert len(keys) == 20


class TestValidUploadRequest:
    def test_valid_webm_request_returns_presigned_url(self):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://example-bucket.s3.amazonaws.com/signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(
                    _api_event({"care_recipient_id": "demo-dad", "content_type": "audio/webm"}), None
                )

        assert result["statusCode"] == 200
        body = json.loads(result["body"])
        assert body["upload_url"] == "https://example-bucket.s3.amazonaws.com/signed"
        assert body["object_key"].startswith("audio/demo-dad-")
        assert body["object_key"].endswith(".webm")
        assert body["method"] == "PUT"
        assert body["headers"] == {"Content-Type": "audio/webm"}
        assert body["care_recipient_id"] == "demo-dad"

    def test_presigned_url_scoped_to_audio_prefix_and_content_type(self):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                lambda_handler(_api_event({"content_type": "audio/mp4"}), None)

            _, kwargs = mock_s3.generate_presigned_url.call_args
            assert kwargs["Params"]["Bucket"] == "test-audio-bucket"
            assert kwargs["Params"]["Key"].startswith("audio/")
            assert kwargs["Params"]["ContentType"] == "audio/mp4"

    @pytest.mark.parametrize("content_type,extension", sorted(CONTENT_TYPE_EXTENSIONS.items()))
    def test_every_allowed_content_type_produces_matching_extension(self, content_type, extension):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(_api_event({"content_type": content_type}), None)

        body = json.loads(result["body"])
        assert body["object_key"].endswith(f".{extension}")


class TestDefaultDemoIdentity:
    def test_missing_care_recipient_id_falls_back_to_demo_dad(self):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(_api_event({"content_type": "audio/webm"}), None)

        body = json.loads(result["body"])
        assert body["care_recipient_id"] == "demo-dad"
        assert body["object_key"].startswith("audio/demo-dad-")


class TestInvalidInput:
    def test_missing_content_type_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler(_api_event({"care_recipient_id": "demo-dad"}), None)
        assert result["statusCode"] == 400

    def test_unsupported_content_type_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler(_api_event({"content_type": "video/mp4"}), None)
        assert result["statusCode"] == 400

    def test_malformed_json_body_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler({"body": "{not valid json"}, None)
        assert result["statusCode"] == 400

    def test_missing_body_returns_400(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler({}, None)
        assert result["statusCode"] == 400

    def test_arbitrary_client_supplied_key_is_ignored(self):
        # Even if a caller tries to smuggle a path via an unexpected field,
        # the handler only ever reads care_recipient_id/content_type - no
        # field lets the client choose the object key directly.
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(
                    _api_event(
                        {
                            "content_type": "audio/webm",
                            "object_key": "../../transcripts/evil.json",
                            "key": "audio/../../evil",
                        }
                    ),
                    None,
                )

        body = json.loads(result["body"])
        assert ".." not in body["object_key"]
        assert body["object_key"].startswith("audio/")


class TestPermissionScope:
    def test_s3_client_failure_returns_502_not_raised(self):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.side_effect = ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "not allowed"}}, "GeneratePresignedUrl"
            )
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(_api_event({"content_type": "audio/webm"}), None)

        assert result["statusCode"] == 502

    def test_missing_bucket_env_var_returns_500(self):
        with patch.dict(os.environ, {}, clear=True):
            result = lambda_handler(_api_event({"content_type": "audio/webm"}), None)
        assert result["statusCode"] == 500


class TestCors:
    def test_cors_header_present_on_success(self):
        with patch("backend.lambdas.audio_upload_url.handler.boto3.client") as mock_boto:
            mock_s3 = MagicMock()
            mock_s3.generate_presigned_url.return_value = "https://signed"
            mock_boto.return_value = mock_s3

            with patch.dict(os.environ, ENV):
                result = lambda_handler(_api_event({"content_type": "audio/webm"}), None)

        assert result["headers"]["Access-Control-Allow-Origin"]
        assert "POST" in result["headers"]["Access-Control-Allow-Methods"]

    def test_cors_header_present_on_error(self):
        with patch.dict(os.environ, ENV):
            result = lambda_handler(_api_event({"content_type": "bad/type"}), None)
        assert result["headers"]["Access-Control-Allow-Origin"]
