import json
import os
import urllib.parse
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError


# Must stay in sync with VoxtralProvider.SUPPORTED_FORMATS, EXCEPT for
# ".webm" - added for Day 4 (real browser voice ingestion): Chrome/Firefox's
# MediaRecorder defaults to audio/webm and there is no in-browser way to
# force wav/mp3 output without extra encoding libraries. VoxtralProvider
# does NOT support webm; a real (non-mock) transcription attempt on a
# browser-recorded upload will fail explicitly with "Unsupported audio
# format: webm" (see voxtral.py) rather than silently mistranscribing -
# that is a documented, accepted gap for this phase, not something worked
# around with a transcoding service. MockTranscriptionProvider ignores
# audio format entirely, so the mock E2E path is unaffected either way.
SUPPORTED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".webm"}
MAX_AUDIO_SIZE = int(os.getenv("MAX_AUDIO_SIZE_BYTES", "10485760"))
TRANSCRIPTION_PROVIDER = os.getenv("TRANSCRIPTION_PROVIDER", "mock")
AWS_REGION = os.getenv("ELDERLINK_AWS_REGION", "us-east-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "mistral.voxtral-mini-3b-2507")


def get_audio_bucket() -> str:
    bucket = os.getenv("AUDIO_BUCKET_NAME")
    if not bucket:
        raise ValueError("AUDIO_BUCKET_NAME environment variable not set")
    return bucket


def get_provider() -> "TranscriptionProvider":
    from core.transcription import MockTranscriptionProvider, TranscriptionResult, VoxtralProvider

    provider_type = os.getenv("TRANSCRIPTION_PROVIDER", "mock")
    if provider_type == "mock":
        return MockTranscriptionProvider()
    elif provider_type == "voxtral":
        return VoxtralProvider(model_id=BEDROCK_MODEL_ID, region=AWS_REGION)
    else:
        raise ValueError(
            f"Invalid TRANSCRIPTION_PROVIDER: '{provider_type}'. "
            f"Allowed values: 'mock', 'voxtral'"
        )


def extract_note_id(object_key: str) -> str:
    filename = object_key.split("/")[-1]
    return filename.rsplit(".", 1)[0]


def get_audio_format(object_key: str) -> str:
    filename = object_key.split("/")[-1]
    if "." not in filename:
        return filename
    return filename.split(".")[-1].lower()


def is_valid_audio_object(object_key: str) -> bool:
    if not object_key.startswith("audio/"):
        return False
    ext = "." + object_key.lower().split(".")[-1]
    return ext in SUPPORTED_AUDIO_EXTENSIONS


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    print(f"Received event: {json.dumps(event, default=str)}")

    try:
        detail = event.get("detail", {})
        bucket = detail.get("bucket", {}).get("name")
        object_key = detail.get("object", {}).get("key")

        if not bucket or not object_key:
            print("Missing bucket or object key in event")
            return {"statusCode": 400, "body": "Invalid event structure"}

        object_key = urllib.parse.unquote(object_key)
        print(f"Processing: s3://{bucket}/{object_key}")

        if not is_valid_audio_object(object_key):
            print(f"Ignoring non-audio object: {object_key}")
            return {"statusCode": 200, "body": "Ignored non-audio object"}

        if bucket != get_audio_bucket():
            print(f"Bucket mismatch: expected {get_audio_bucket()}, got {bucket}")
            return {"statusCode": 400, "body": "Bucket mismatch"}

        s3_client = boto3.client("s3", region_name=AWS_REGION)

        try:
            head_response = s3_client.head_object(Bucket=bucket, Key=object_key)
            content_length = head_response.get("ContentLength", 0)
            if content_length > MAX_AUDIO_SIZE:
                error_msg = f"Audio file too large: {content_length} bytes (max {MAX_AUDIO_SIZE})"
                print(error_msg)
                return {"statusCode": 413, "body": error_msg}
        except ClientError as e:
            print(f"Failed to head object: {e}")
            return {"statusCode": 404, "body": "Audio object not found"}

        note_id = extract_note_id(object_key)
        transcript_key = f"transcripts/{note_id}.json"

        # Defensive de-dup guard: S3/EventBridge deliver events at-least-once,
        # so the same upload can legitimately invoke this Lambda more than
        # once. Skip work we've already done rather than re-transcribing.
        try:
            s3_client.head_object(Bucket=bucket, Key=transcript_key)
            print(f"Transcript already exists at s3://{bucket}/{transcript_key}, skipping")
            return {"statusCode": 200, "body": "Already processed"}
        except ClientError as e:
            # S3 returns 403 (not 404) for HeadObject on a missing key when
            # the caller lacks s3:ListBucket, to avoid leaking object
            # existence to callers without list access. This role is
            # intentionally scoped to GetObject/PutObject only (no
            # ListBucket), so 403 here means "doesn't exist", not "denied".
            error_code = e.response.get("Error", {}).get("Code")
            if error_code not in ("404", "403"):
                raise

        response = s3_client.get_object(Bucket=bucket, Key=object_key)
        audio_bytes = response["Body"].read()

        audio_format = get_audio_format(object_key)

        provider = get_provider()
        print(f"Using transcription provider: {provider.provider_name} ({provider.model_id})")

        from core.transcription import TranscriptionResult

        result: TranscriptionResult = provider.transcribe(audio_bytes, audio_format)

        transcript_data = {
            "note_id": note_id,
            "source_audio_key": object_key,
            "provider": result.provider,
            "model": result.model,
            "status": "completed" if result.success else "failed",
            "transcript": result.text if result.success else "",
            "processed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "error": result.error,
        }

        s3_client.put_object(
            Bucket=bucket,
            Key=transcript_key,
            Body=json.dumps(transcript_data, ensure_ascii=False).encode("utf-8"),
            ContentType="application/json",
        )

        print(f"Transcript written to s3://{bucket}/{transcript_key}")
        return {"statusCode": 200, "body": json.dumps(transcript_data)}

    except ValueError as e:
        # Misconfiguration (e.g. bad TRANSCRIPTION_PROVIDER, missing env var).
        # Re-raise so Lambda records it as an execution error (CloudWatch
        # Errors metric, default async-invoke retry) instead of it silently
        # looking like a successful invocation.
        print(f"Configuration error: {e}")
        raise

    except (BotoCoreError, ClientError) as e:
        print(f"AWS error: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise