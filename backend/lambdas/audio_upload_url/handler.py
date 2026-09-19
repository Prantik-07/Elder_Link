"""Day 4: the ingestion bridge Lambda - POST /audio/upload-url.

This is the ONLY new piece of infrastructure Day 4 adds. It does not touch
audio bytes, transcription, or extraction: it signs a short-lived S3
PutObject URL under the existing audio/ prefix so the browser's
VoiceRecorder can upload a real recording directly to S3, without the
browser ever holding an AWS credential. Once the object lands in S3, the
already-verified pipeline (EventBridge -> process_audio -> transcripts/ ->
EventBridge -> extract_events -> DynamoDB -> GetTimeline API) takes over
completely unchanged.

Security posture:
  - The browser never receives an AWS access key/secret/session token -
    only a presigned URL scoped to one specific object key, one specific
    Content-Type, and a 5-minute expiry.
  - This Lambda's own IAM role (see infra/template.yaml) can only
    s3:PutObject under audio/* - the same prefix ProcessAudioRole is
    already scoped to read from. It cannot GetObject, ListBucket, or write
    anywhere else in the bucket.
  - The object key is ALWAYS generated server-side under audio/ - the
    browser supplies only a care_recipient_id (sanitized against a strict
    allowlist pattern, falling back to the demo recipient on anything that
    doesn't match) and a content_type (checked against a fixed allowlist).
    No client-supplied path ever reaches the S3 key.

Known, accepted limitation: audio/webm (this endpoint's most common real
content type, since that's what Chrome/Firefox's MediaRecorder produces by
default) is NOT in VoxtralProvider.SUPPORTED_FORMATS. Real Bedrock/Voxtral
transcription of a browser-recorded upload would fail with an explicit
"Unsupported audio format" result (see voxtral.py) - this is a documented
gap, not silently worked around with a transcoding service. The mock
transcription/extraction path (used for all real E2E verification of this
feature - see the Day 4 report) does not care about audio format at all.
"""

from __future__ import annotations

import json
import os
import re
import time
import uuid
from typing import Any, Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

DEFAULT_CARE_RECIPIENT_ID_ENV = "DEFAULT_CARE_RECIPIENT_ID"
UPLOAD_URL_TTL_SECONDS = 300  # long enough to record + upload; short enough to bound exposure of a signed URL

CORS_ALLOW_ORIGIN_ENV = "ELDERLINK_CORS_ORIGIN"

# The only content types this endpoint will ever sign for - a superset of
# process_audio's SUPPORTED_AUDIO_EXTENSIONS covering what browser
# MediaRecorder implementations actually produce (audio/webm is Chrome/
# Firefox's default; audio/mp4 is Safari's). Never derived from anything
# the client sends beyond this exact lookup - there is no path from
# arbitrary client input to an arbitrary extension.
CONTENT_TYPE_EXTENSIONS = {
    "audio/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}

_SAFE_RECIPIENT_RE = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def get_default_care_recipient_id() -> str:
    return os.getenv(DEFAULT_CARE_RECIPIENT_ID_ENV, "demo-dad")


def sanitize_care_recipient_id(value: Optional[str]) -> str:
    """Never trust the client's care_recipient_id for anything beyond a
    cosmetic S3-key component - if it doesn't match a strict, safe
    allowlist pattern, fall back to the configured demo recipient rather
    than rejecting the whole request outright (this is a hackathon-demo
    ingestion endpoint, not a multi-tenant identity boundary - see
    extract_events/handler.py's own resolve_care_recipient_id for the same
    posture on the extraction side)."""
    if not value or not value.strip():
        return get_default_care_recipient_id()
    value = value.strip()
    if not _SAFE_RECIPIENT_RE.match(value):
        return get_default_care_recipient_id()
    return value


def build_object_key(care_recipient_id: str, extension: str) -> str:
    """The ONLY place an upload object key is constructed. Always under
    audio/ (the one prefix EventBridgeRule/ProcessAudioRole are scoped
    to), always server-generated - never a client-supplied path. The
    embedded timestamp + short uuid make concurrent uploads from the same
    or different recipients collision-safe, and the recipient prefix keeps
    keys human-debuggable in the S3 console/CloudWatch logs."""
    return f"audio/{care_recipient_id}-{int(time.time())}-{uuid.uuid4().hex[:8]}.{extension}"


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": os.getenv(CORS_ALLOW_ORIGIN_ENV, "*"),
        "Access-Control-Allow-Methods": "POST,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _response(status_code: int, body: dict) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def get_audio_bucket() -> str:
    bucket = os.getenv("AUDIO_BUCKET_NAME")
    if not bucket:
        raise ValueError("AUDIO_BUCKET_NAME environment variable not set")
    return bucket


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Request body must be valid JSON"})

    if not isinstance(body, dict):
        return _response(400, {"error": "Request body must be a JSON object"})

    content_type = body.get("content_type")
    if not content_type or content_type not in CONTENT_TYPE_EXTENSIONS:
        return _response(
            400,
            {
                "error": (
                    "content_type is required and must be one of: "
                    + ", ".join(sorted(CONTENT_TYPE_EXTENSIONS))
                )
            },
        )

    care_recipient_id = sanitize_care_recipient_id(body.get("care_recipient_id"))
    extension = CONTENT_TYPE_EXTENSIONS[content_type]
    object_key = build_object_key(care_recipient_id, extension)

    try:
        bucket = get_audio_bucket()
    except ValueError as e:
        print(f"Configuration error: {e}")
        return _response(500, {"error": "Server misconfiguration"})

    try:
        s3_client = boto3.client("s3", region_name=os.getenv("ELDERLINK_AWS_REGION", "us-east-1"))
        upload_url = s3_client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": object_key, "ContentType": content_type},
            ExpiresIn=UPLOAD_URL_TTL_SECONDS,
        )
    except (BotoCoreError, ClientError) as e:
        print(f"Failed to generate presigned URL for s3://{bucket}/{object_key}: {e}")
        return _response(502, {"error": "Failed to create upload URL"})

    return _response(
        200,
        {
            "object_key": object_key,
            "upload_url": upload_url,
            "method": "PUT",
            "headers": {"Content-Type": content_type},
            "care_recipient_id": care_recipient_id,
            "expires_in": UPLOAD_URL_TTL_SECONDS,
        },
    )
