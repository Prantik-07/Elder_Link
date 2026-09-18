"""Read-only Lambda: GET /care-recipients/{care_recipient_id}/timeline

Phase 7's one API endpoint. This is intentionally thin: validate the path
parameter, call the existing CareEventRepository.get_timeline (Access
pattern A - CareTimelineIndex, newest first), map each CareEventRecord to
the frontend-safe DTO (backend.core.persistence.frontend_dto), and return
JSON. It does not re-implement any DynamoDB access, does not scan the
table, and does not run extraction or validation - those all remain
CareEventRepository's and backend.core.extraction's jobs, untouched.

DEMO-ONLY: no authentication or authorization is applied. Any caller who
can reach this URL can read any care_recipient_id's timeline. That is
acceptable for a hackathon demo behind an unguessable/soon-to-be-torn-down
API URL, and unacceptable in production - see the Phase 7 report.

IAM: the execution role backing this function must be granted
dynamodb:Query only (see infra/template.yaml) - no PutItem/UpdateItem/
DeleteItem. This handler makes no write calls.
"""

from __future__ import annotations

import json
import os
from typing import Any

from botocore.exceptions import BotoCoreError, ClientError

from backend.core.persistence import CareEventRepository
from backend.core.persistence.frontend_dto import care_event_to_dto

DEFAULT_TIMELINE_LIMIT = 50

# Demo-only CORS: one configured origin (or "*" if unset), never a
# reflected/wildcarded credentialed origin - this API issues no cookies or
# auth headers, so a bare Allow-Origin is sufficient and does not need
# Allow-Credentials.
CORS_ALLOW_ORIGIN = os.getenv("ELDERLINK_CORS_ORIGIN", "*")


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": CORS_ALLOW_ORIGIN,
        "Access-Control-Allow-Methods": "GET,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _response(status_code: int, body: dict) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    path_params = event.get("pathParameters") or {}
    care_recipient_id = (path_params.get("care_recipient_id") or "").strip()

    if not care_recipient_id:
        return _response(400, {"error": "care_recipient_id path parameter is required"})

    try:
        repo = CareEventRepository()
    except ValueError as e:
        # Misconfiguration (CARE_EVENTS_TABLE_NAME unset) - never exposed
        # to the caller in detail, but logged for operators.
        print(f"Configuration error: {e}")
        return _response(500, {"error": "Server misconfiguration"})

    try:
        records = repo.get_timeline(care_recipient_id, limit=DEFAULT_TIMELINE_LIMIT)
    except (BotoCoreError, ClientError) as e:
        print(f"DynamoDB query failure for care_recipient_id={care_recipient_id!r}: {e}")
        return _response(502, {"error": "Failed to load timeline"})

    # An empty list is a perfectly valid, successful result (a recipient
    # with no persisted events yet) - not an error, and not distinguished
    # from "not found" since care_recipient_id has no separate existence
    # check (see Phase 7 report on care-recipient identity).
    events = [care_event_to_dto(record) for record in records]
    return _response(200, {"care_recipient_id": care_recipient_id, "events": events})
