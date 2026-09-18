"""DynamoDB-backed CareEventRepository.

Persists only validated CareEvents - callers are expected to have already
run them through the full chain in the Phase 5 architecture diagram
(extraction -> validation -> review policy -> deterministic identity).
This repository does not re-run that validation (it has no
TranscriptDocument to check evidence segment ids against); it enforces
only the narrower, persistence-level invariants it can check on its own -
see _check_persistable.

Idempotency: put_event issues a single atomic DynamoDB UpdateItem call
keyed on (care_recipient_id, event_id) - the Phase 4.1 deterministic
identity, never array position or a random id. `created_at` is set via
`if_not_exists(created_at, :new_created_at)` inside that SAME UpdateItem
call, so "does this item already exist" is resolved atomically, server
side, within one write - not by an application-side GetItem-then-PutItem
race. Repeated or concurrent calls with the same key are safe: the item
converges to the same content, `created_at` is fixed at first write and
never overwritten by a later call, and `updated_at` legitimately advances
on every call (that's the correct signal that this event was processed
again, not a bug).

Historical events are never deleted by this repository. A later
extraction that produces fewer events than a previous one does not remove
the events that are now "missing" - see get_by_transcript's docstring and
the Phase 5 report for why (no reconciliation policy exists yet; building
one is explicitly out of scope this phase).

AWS errors (ClientError, BotoCoreError) are never caught here - they
propagate to the caller, who decides whether/how to retry. This mirrors
backend/lambdas/process_audio/handler.py's convention of re-raising rather
than swallowing AWS errors.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Optional

import boto3

from backend.core.care_event import CareEvent

from .context import CareContext
from .keys import patient_pk
from .serialization import CareEventRecord, from_item, to_item


class PersistenceValidationError(ValueError):
    def __init__(self, errors: list[str]):
        self.errors = errors
        super().__init__("; ".join(errors))


def _check_persistable(event: CareEvent, context: CareContext) -> list[str]:
    errors: list[str] = []
    if not event.event_id or not event.event_id.strip():
        errors.append("event_id is required")
    if not event.evidence:
        errors.append("at least one evidence segment is required - an ungrounded event cannot become trusted persistent context")
    if not context.care_recipient_id or not context.care_recipient_id.strip():
        errors.append("care_recipient_id is required")
    if not context.transcript_id or not context.transcript_id.strip():
        errors.append("transcript_id is required")
    return errors


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class CareEventRepository:
    def __init__(
        self,
        table_name: Optional[str] = None,
        region: Optional[str] = None,
        resource=None,
        table=None,
    ):
        if table is not None:
            self._table = table
            return

        self._table_name = table_name or os.getenv("CARE_EVENTS_TABLE_NAME")
        if not self._table_name:
            raise ValueError("CARE_EVENTS_TABLE_NAME environment variable not set")
        self._region = region or os.getenv("ELDERLINK_AWS_REGION", "us-east-1")
        resource = resource or boto3.resource("dynamodb", region_name=self._region)
        self._table = resource.Table(self._table_name)

    def put_event(self, event: CareEvent, context: CareContext, extraction_version: str) -> CareEventRecord:
        errors = _check_persistable(event, context)
        if errors:
            raise PersistenceValidationError(errors)

        now = _now_iso()
        item = to_item(event, context, extraction_version, created_at=now, updated_at=now)

        # Every field except the key itself and created_at is a plain SET;
        # created_at alone gets if_not_exists so a repeat/concurrent write
        # never overwrites the original persistence timestamp. All names go
        # through ExpressionAttributeNames placeholders unconditionally -
        # standard defensive practice against DynamoDB's large reserved-word
        # list, not because any specific field name here is known reserved.
        settable_fields = [k for k in item if k not in ("pk", "sk", "created_at")]
        names = {f"#{k}": k for k in settable_fields}
        names["#created_at"] = "created_at"
        values = {f":{k}": item[k] for k in settable_fields}
        values[":created_at"] = now

        set_clauses = [f"#{k} = :{k}" for k in settable_fields]
        set_clauses.append("#created_at = if_not_exists(#created_at, :created_at)")
        update_expression = "SET " + ", ".join(set_clauses)

        response = self._table.update_item(
            Key={"pk": item["pk"], "sk": item["sk"]},
            UpdateExpression=update_expression,
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=values,
            ReturnValues="ALL_NEW",
        )
        return from_item(response["Attributes"])

    def get_timeline(self, care_recipient_id: str, limit: int = 50) -> list[CareEventRecord]:
        """Access pattern A: care events for one recipient, newest first."""
        response = self._table.query(
            IndexName="CareTimelineIndex",
            KeyConditionExpression="pk = :pk",
            ExpressionAttributeValues={":pk": patient_pk(care_recipient_id)},
            ScanIndexForward=False,
            Limit=limit,
        )
        return [from_item(i) for i in response.get("Items", [])]

    def get_by_transcript(self, transcript_id: str) -> list[CareEventRecord]:
        """Access pattern B: every event generated from one transcript.

        Includes events from every extraction run of that transcript,
        across every extraction_version - this repository never deletes a
        previously persisted event just because a later run of the same
        transcript didn't reproduce it (see module docstring). Callers
        that need only the latest run's events should filter by
        extraction_version themselves.
        """
        response = self._table.query(
            IndexName="TranscriptIndex",
            KeyConditionExpression="transcript_id = :transcript_id",
            ExpressionAttributeValues={":transcript_id": transcript_id},
        )
        return [from_item(i) for i in response.get("Items", [])]
