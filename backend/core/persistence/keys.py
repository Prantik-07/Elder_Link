"""Table & key design for CareEvent persistence.

Documented before any key was chosen, per the Phase 5 spec. Exactly two
access patterns are supported - nothing speculative:

  A. List care events for one care recipient, newest first.
  B. List events generated from one transcript.

These two patterns partition along different dimensions (care recipient
vs. transcript), so no single DynamoDB partition key can serve both
efficiently. That's why this design needs one index beyond the base table
for each of them - not because more indexes feel "complete."

  Base table
    PK (pk) = PATIENT#<care_recipient_id>
    SK (sk) = EVENT#<event_id>

    `event_id` is the Phase 4.1 deterministic identity - never array
    position, never a random UUID. Keying the base table on it directly is
    what makes CareEventRepository.put_event a true idempotent upsert:
    writing the same (care_recipient_id, event_id) pair always addresses
    the exact same item, so a duplicate is structurally impossible, not
    just avoided by application logic.

  LSI: CareTimelineIndex
    PK = pk (same partition key as the base table)
    SK = created_at

    Answers pattern A. A Local Secondary Index, not a second GSI, because
    it shares the base table's partition key and only needs a *different
    sort order* within that same partition - the idiomatic DynamoDB tool
    for exactly that need. Query with ScanIndexForward=False for
    newest-first.

    Ordered by `created_at` (a persistence-time timestamp), not by the
    event's own `occurred_at`: occurred_at may be RELATIVE ("this
    morning") or UNKNOWN and is not reliably sortable, while created_at is
    always a well-formed ISO 8601 instant assigned once, at first write,
    and never changed afterward (see repository.py's if_not_exists usage).

  GSI: TranscriptIndex
    PK = transcript_id
    SK = event_id

    Answers pattern B. This genuinely requires a full Global Secondary
    Index, not an LSI, because its partition key (transcript_id) differs
    from the base table's (care_recipient_id) - an LSI cannot change the
    partition key, only the sort key. This is the one GSI Phase 5 adds,
    and it exists because pattern B is one of exactly two explicitly
    required access patterns.

No other indexes exist. Anything outside patterns A/B - querying across
all patients, filtering by event_type, full-text search - is out of scope
for this phase and was not built speculatively.
"""

from __future__ import annotations


def patient_pk(care_recipient_id: str) -> str:
    return f"PATIENT#{care_recipient_id}"


def event_sk(event_id: str) -> str:
    return f"EVENT#{event_id}"
