"""POST /notifications/flag - tell the rest of a Care Circle that an update was flagged.

When a caregiver flags a Care Event for review, everyone else in that
patient's Care Circle should hear about it; the person who flagged it should
not be notified about their own action. The frontend owns the Care Circle
(there is no backend caregiver store yet), so it sends the already-filtered
recipient list and this Lambda only delivers.

Delivery uses one shared SNS topic with a per-recipient subscription filter:
each email is subscribed once with FilterPolicy {"recipient": [email]}, and
every publish carries a matching `recipient` message attribute. That gives
one-to-one delivery without a topic per person. The first time an address is
used SNS sends it a confirmation email; until it is confirmed nothing can be
delivered, so the response reports that state per recipient instead of
claiming success.

This Lambda's role can only Publish/Subscribe/ListSubscriptionsByTopic on
that one topic (see infra/template.yaml). No audio, transcripts, or medical
detail beyond the event title are sent.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

TOPIC_ARN_ENV = "FLAG_NOTIFICATIONS_TOPIC_ARN"
CORS_ALLOW_ORIGIN_ENV = "ELDERLINK_CORS_ORIGIN"

MAX_RECIPIENTS = 10
_EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")


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


def _clean(value: Any, limit: int) -> str:
    """Single-line, length-bounded text: SNS subjects reject newlines/non-ASCII."""
    text = value if isinstance(value, str) else ""
    return " ".join(text.split())[:limit]


def _subject_safe(text: str) -> str:
    return text.encode("ascii", "ignore").decode("ascii")


def find_subscription(sns_client: Any, topic_arn: str, email: str) -> str | None:
    """Return the subscription ARN for this email ("PendingConfirmation" if
    unconfirmed), or None if the address was never subscribed."""
    paginator = sns_client.get_paginator("list_subscriptions_by_topic")
    for page in paginator.paginate(TopicArn=topic_arn):
        for sub in page.get("Subscriptions", []):
            if sub.get("Protocol") == "email" and sub.get("Endpoint", "").lower() == email.lower():
                return sub.get("SubscriptionArn", "")
    return None


def notify_recipient(
    sns_client: Any, topic_arn: str, email: str, subject: str, message: str
) -> str:
    """Returns "notified", "pending_confirmation" or "confirmation_sent"."""
    existing = find_subscription(sns_client, topic_arn, email)

    if existing is None:
        sns_client.subscribe(
            TopicArn=topic_arn,
            Protocol="email",
            Endpoint=email,
            Attributes={"FilterPolicy": json.dumps({"recipient": [email.lower()]})},
        )
        return "confirmation_sent"

    if existing == "PendingConfirmation":
        return "pending_confirmation"

    sns_client.publish(
        TopicArn=topic_arn,
        Subject=subject,
        Message=message,
        MessageAttributes={"recipient": {"DataType": "String", "StringValue": email.lower()}},
    )
    return "notified"


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    try:
        body = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _response(400, {"error": "Request body must be valid JSON"})
    if not isinstance(body, dict):
        return _response(400, {"error": "Request body must be a JSON object"})

    event_title = _clean(body.get("event_title"), 200)
    flagged_by = _clean(body.get("flagged_by"), 80)
    patient_name = _clean(body.get("patient_name"), 80)
    if not event_title or not flagged_by or not patient_name:
        return _response(400, {"error": "patient_name, flagged_by and event_title are required"})

    raw_recipients = body.get("recipients")
    if not isinstance(raw_recipients, list) or not raw_recipients:
        return _response(400, {"error": "recipients must be a non-empty list"})
    if len(raw_recipients) > MAX_RECIPIENTS:
        return _response(400, {"error": f"At most {MAX_RECIPIENTS} recipients per request"})

    recipients: list[dict[str, str]] = []
    for r in raw_recipients:
        email = r.get("email") if isinstance(r, dict) else None
        if not isinstance(email, str) or not _EMAIL_RE.match(email.strip()):
            return _response(400, {"error": "Every recipient needs a valid email"})
        recipients.append({"name": _clean(r.get("name"), 80), "email": email.strip()})

    topic_arn = os.getenv(TOPIC_ARN_ENV)
    if not topic_arn:
        print(f"Configuration error: {TOPIC_ARN_ENV} not set")
        return _response(500, {"error": "Server misconfiguration"})

    subject = _subject_safe(f"ElderLink: update flagged for {patient_name}")[:100]
    message = (
        f"{flagged_by} flagged an update for {patient_name} for review:\n\n"
        f'  "{event_title}"\n\n'
        "Please open ElderLink to check it before the next handoff."
    )

    sns_client = boto3.client("sns", region_name=os.getenv("ELDERLINK_AWS_REGION", "us-east-1"))
    results = []
    for r in recipients:
        try:
            status = notify_recipient(sns_client, topic_arn, r["email"], subject, message)
        except (BotoCoreError, ClientError) as e:
            print(f"Failed to notify {r['email']}: {e}")
            status = "failed"
        results.append({"name": r["name"], "email": r["email"], "status": status})

    return _response(200, {"results": results})
