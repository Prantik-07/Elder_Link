"""Write Lambda: PATCH /care-recipients/{care_recipient_id}/care-events/{event_id}

Added to fix a real gap the frontend forensic audit found: the caregiver's
"Mark as Verified" / "Keep Uncertain" actions previously only updated
client-side React state, so every one of those decisions was silently lost
on the next refresh. This is the smallest backend path that makes them
durable.

Narrow by design. The only thing a caller can change is the frontend-facing
`status`, and only to one of two values:

  "verified"  -> review_state = VERIFIED, verification_reason cleared.
  "uncertain" -> review_state = NEEDS_VERIFICATION, verification_reason set
                 to a fixed, structured reason recording that a caregiver
                 reviewed the claim and chose to keep it flagged rather
                 than confirm it.

Every other canonical CareEvent field (event_type, summary, claim_stance,
source_type, evidence, occurred_at, reported_by) is immutable via this
endpoint - CareEventRepository.update_review_state enforces that at the
persistence layer by construction (its UpdateExpression only ever touches
review_state/verification_reason/updated_at), not merely by this handler
choosing not to expose the other fields.

There is no `review_state`-shaped request body accepted here on purpose:
the frontend only ever needs to express its own two caregiver actions, not
the backend's three-value ReviewState vocabulary, so the request contract
mirrors frontend/src/data/types.ts's CareEventStatus rather than
backend.core.care_event.schema.ReviewState directly.

DEMO-ONLY: no authentication or authorization is applied, matching
get_timeline's existing, documented demo posture (see that handler's
docstring and the Phase 7 report) - anyone who can reach this URL can
verify any event for any care_recipient_id. Acceptable for a hackathon demo
behind an unguessable/soon-to-be-torn-down API URL, not for production.

IAM: the execution role backing this function is granted dynamodb:UpdateItem
only, scoped to the base table by primary key (see infra/template.yaml) -
no Query/Scan/PutItem/DeleteItem, no GSI/LSI access, no S3 access.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

from botocore.exceptions import BotoCoreError, ClientError

from backend.core.care_event import ReviewState, VerificationReason, VerificationReasonCode
from backend.core.persistence import CareEventNotFoundError, CareEventRepository
from backend.core.persistence.frontend_dto import care_event_to_dto

# Demo-only CORS: one configured origin (or "*" if unset), matching
# get_timeline's own convention exactly - see that handler for the full
# rationale.
CORS_ALLOW_ORIGIN = os.getenv("ELDERLINK_CORS_ORIGIN", "*")

# The only two caregiver-initiated status transitions this endpoint
# supports, keyed by the exact frontend CareEventStatus string the request
# body sends. "needs_verification" is deliberately not a valid input here:
# it's the default/no-action-taken state, never something a caregiver
# click sets directly.
_STATUS_TO_REVIEW_STATE = {
    "verified": ReviewState.VERIFIED,
    "uncertain": ReviewState.NEEDS_VERIFICATION,
}


def _cors_headers() -> dict[str, str]:
    return {
        "Access-Control-Allow-Origin": CORS_ALLOW_ORIGIN,
        "Access-Control-Allow-Methods": "PATCH,OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type",
    }


def _response(status_code: int, body: dict) -> dict[str, Any]:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


def _verification_reason_for(status: str) -> Optional[VerificationReason]:
    if status == "uncertain":
        return VerificationReason(
            code=VerificationReasonCode.OTHER,
            detail="Caregiver reviewed and kept this flagged for verification.",
        )
    return None


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    path_params = event.get("pathParameters") or {}
    care_recipient_id = (path_params.get("care_recipient_id") or "").strip()
    event_id = (path_params.get("event_id") or "").strip()

    if not care_recipient_id or not event_id:
        return _response(400, {"error": "care_recipient_id and event_id path parameters are required"})

    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Request body must be valid JSON"})

    if not isinstance(body, dict):
        return _response(400, {"error": "Request body must be a JSON object"})

    status = body.get("status")
    if status not in _STATUS_TO_REVIEW_STATE:
        allowed = sorted(_STATUS_TO_REVIEW_STATE)
        return _response(400, {"error": f"status must be one of {allowed}"})

    try:
        repo = CareEventRepository()
    except ValueError as e:
        # Misconfiguration (CARE_EVENTS_TABLE_NAME unset) - never exposed
        # to the caller in detail, but logged for operators.
        print(f"Configuration error: {e}")
        return _response(500, {"error": "Server misconfiguration"})

    review_state = _STATUS_TO_REVIEW_STATE[status]
    verification_reason = _verification_reason_for(status)

    try:
        record = repo.update_review_state(care_recipient_id, event_id, review_state, verification_reason)
    except CareEventNotFoundError:
        return _response(404, {"error": "Care event not found"})
    except (BotoCoreError, ClientError) as e:
        print(f"DynamoDB update failure for event_id={event_id!r}: {e}")
        return _response(502, {"error": "Failed to update verification status"})

    try:
        dto = care_event_to_dto(record)
    except Exception as e:
        # Mirrors get_timeline's own defensive catch-all around DTO mapping
        # - a mapping bug here must still return CORS headers and a
        # readable error, never an opaque, header-less Lambda crash.
        print(f"Failed to map updated care event to frontend DTO: {e}")
        return _response(500, {"error": "Server error while formatting response"})

    return _response(200, dto)
