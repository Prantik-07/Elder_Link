"""Extraction Lambda: transcript S3 object -> validated CareEvents in DynamoDB.

Triggered by the same EventBridge "S3 Object Created" notification stream
Day 1 already enables on AudioBucket, filtered (at the rule level, and
defensively again here) to `transcripts/*.json` objects only - never
`audio/*` objects, and never anything this Lambda itself writes, since it
writes only to DynamoDB and produces no S3 objects. That structural fact is
what rules out the kind of duplicate-trigger loop Day 1 hit with a
SAM-generated `Events:` block: there is no object this function could ever
write that would cause EventBridge to invoke it again.

This Lambda is pure orchestration. It does not reimplement any part of the
Phase 3/4/4.1 extraction pipeline (parsing, review policy, identity,
validation all live in backend.core.extraction / backend.core.care_event
untouched) and it does not implement any part of DynamoDB idempotency
itself (that's backend.core.persistence.CareEventRepository.put_event's
job, via if_not_exists - see repository.py). Its only jobs are: locate and
load the transcript object, build a TranscriptDocument, run the pipeline,
and persist whatever comes out the other end as validated.

CareContext.care_recipient_id: Day 1's transcript JSON carries no
patient/care-recipient identifier at all - that concept does not exist yet
anywhere in this system (confirmed by inspection: no Day 1 code, table, or
frontend component keys anything by such an id). Until that concept is
introduced, this Lambda uses the transcript's own note_id as the
care_recipient_id, i.e. one note = one recipient's timeline. This is a
known, documented simplification - see the Phase 6 report - not a
guess made silently.

extraction_version: intentionally NOT an independently configurable
environment variable. backend.core.extraction.identity.assign_event_ids
(via run_extraction_pipeline) always computes ids under
EXTRACTION_SCHEMA_VERSION - there is no parameter to make it use anything
else. Persisting a different, env-supplied "extraction_version" string
here would just be a label that doesn't match how the ids were actually
computed, which is worse than no version field at all. So this Lambda
imports and persists the one true constant the pipeline itself used.
"""

from __future__ import annotations

import json
import os
import time
import urllib.parse
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from backend.core.care_event import from_day1_transcript
from backend.core.extraction import (
    EXTRACTION_SCHEMA_VERSION,
    BedrockExtractionProvider,
    ExtractionProvider,
    MockExtractionProvider,
    run_extraction_pipeline,
)
from backend.core.persistence import CareContext, CareEventRepository

AWS_REGION = os.getenv("ELDERLINK_AWS_REGION", "us-east-1")


def get_transcript_bucket() -> str:
    bucket = os.getenv("TRANSCRIPT_BUCKET_NAME")
    if not bucket:
        raise ValueError("TRANSCRIPT_BUCKET_NAME environment variable not set")
    return bucket


def get_extraction_provider() -> ExtractionProvider:
    provider_type = os.getenv("EXTRACTION_PROVIDER", "mock")
    if provider_type == "mock":
        return MockExtractionProvider()
    elif provider_type == "bedrock":
        return BedrockExtractionProvider(
            model_id=os.getenv("BEDROCK_EXTRACTION_MODEL_ID"),
            region=AWS_REGION,
        )
    else:
        raise ValueError(
            f"Invalid EXTRACTION_PROVIDER: '{provider_type}'. "
            f"Allowed values: 'mock', 'bedrock'"
        )


def is_transcript_object(object_key: str) -> bool:
    return object_key.startswith("transcripts/") and object_key.endswith(".json")


def extract_note_id_from_transcript_key(object_key: str) -> str:
    filename = object_key.split("/")[-1]
    return filename[: -len(".json")]


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    print(f"Received event: {json.dumps(event, default=str)}")
    start = time.monotonic()

    try:
        detail = event.get("detail", {})
        bucket = detail.get("bucket", {}).get("name")
        object_key = detail.get("object", {}).get("key")

        if not bucket or not object_key:
            print("Missing bucket or object key in event")
            return {"statusCode": 400, "body": "Invalid event structure"}

        object_key = urllib.parse.unquote(object_key)
        print(f"Processing: s3://{bucket}/{object_key}")

        if not is_transcript_object(object_key):
            print(f"Ignoring non-transcript object: {object_key}")
            return {"statusCode": 200, "body": "Ignored non-transcript object"}

        if bucket != get_transcript_bucket():
            print(f"Bucket mismatch: expected {get_transcript_bucket()}, got {bucket}")
            return {"statusCode": 400, "body": "Bucket mismatch"}

        s3_client = boto3.client("s3", region_name=AWS_REGION)

        # S3/EventBridge failures here (throttling, transient network,
        # permission drift) are not this Lambda's to resolve - propagate so
        # Lambda's built-in retry can run the whole handler again. That
        # retry is safe: nothing has been written yet at this point.
        try:
            response = s3_client.get_object(Bucket=bucket, Key=object_key)
            raw_body = response["Body"].read()
        except (BotoCoreError, ClientError) as e:
            print(f"S3 read failure for s3://{bucket}/{object_key}: {e}")
            raise

        try:
            transcript_data = json.loads(raw_body)
        except json.JSONDecodeError as e:
            # Deterministic bad data, not a transient failure - retrying
            # won't produce a different result, so this is reported and
            # swallowed rather than raised (no raw output reaches DynamoDB
            # either way, since nothing downstream ever ran).
            print(f"Transcript parse failure (invalid JSON) for s3://{bucket}/{object_key}: {e}")
            return {"statusCode": 200, "body": f"Skipped: malformed transcript JSON ({e})"}

        note_id = transcript_data.get("note_id") or extract_note_id_from_transcript_key(object_key)
        status = transcript_data.get("status")
        transcript_text = transcript_data.get("transcript", "")

        if status != "completed":
            print(f"Skipping transcript '{note_id}': status={status!r} (not completed)")
            return {"statusCode": 200, "body": f"Skipped: transcript status is {status!r}"}

        document = from_day1_transcript(note_id, transcript_text)

        provider = get_extraction_provider()
        print(f"Using extraction provider: {provider.provider_name} ({provider.model_id})")

        pipeline_result = run_extraction_pipeline(document, provider)

        if pipeline_result.extraction_failed:
            # An explicit, honest failure (e.g. Bedrock access still
            # pending) - never a silent fallback to another provider, and
            # nothing is persisted. Not raised: the provider itself already
            # distinguished transient-vs-not (see ExtractionErrorKind), and
            # a config/availability failure retrying immediately would just
            # fail identically.
            error_kind = pipeline_result.extraction_error_kind
            print(
                f"Extraction provider failure for transcript '{document.transcript_id}' "
                f"[{error_kind.value if error_kind else 'unknown'}]: {pipeline_result.extraction_error}"
            )
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "transcript_id": document.transcript_id,
                        "provider": pipeline_result.provider,
                        "extraction_failed": True,
                        "error_kind": error_kind.value if error_kind else None,
                        "error": pipeline_result.extraction_error,
                    }
                ),
            }

        # Only validated CareEvents ever reach the repository - raw
        # candidate dicts and anything RejectedCandidate collected never do.
        repo = CareEventRepository()
        care_context = CareContext(care_recipient_id=note_id, transcript_id=document.transcript_id)

        persisted = 0
        for validated_event in pipeline_result.validated_events:
            # Not caught: a DynamoDB failure partway through this loop must
            # propagate so Lambda retries the whole invocation. That retry
            # is safe - put_event is an idempotent upsert keyed on the
            # Phase 4.1 deterministic event_id, so events already written in
            # this attempt are not duplicated on the next one.
            repo.put_event(validated_event, care_context, EXTRACTION_SCHEMA_VERSION)
            persisted += 1

        duration_ms = round((time.monotonic() - start) * 1000, 1)
        summary = {
            "transcript_id": document.transcript_id,
            "extraction_version": EXTRACTION_SCHEMA_VERSION,
            "provider": pipeline_result.provider,
            "candidates": len(pipeline_result.validated_events) + len(pipeline_result.rejected),
            "accepted": len(pipeline_result.validated_events),
            "rejected": len(pipeline_result.rejected),
            "persisted": persisted,
            "duration_ms": duration_ms,
        }
        print(f"Extraction complete: {json.dumps(summary)}")
        return {"statusCode": 200, "body": json.dumps(summary)}

    except ValueError as e:
        # Misconfiguration (bad EXTRACTION_PROVIDER, missing env var) -
        # re-raise so Lambda records it as an execution error instead of a
        # silently-successful-looking invocation.
        print(f"Configuration error: {e}")
        raise

    except (BotoCoreError, ClientError) as e:
        print(f"AWS error: {e}")
        raise

    except Exception as e:
        print(f"Unexpected error: {e}")
        raise
