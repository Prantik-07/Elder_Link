"""A minimal in-memory double for the boto3 DynamoDB Table resource.

Not a general-purpose DynamoDB emulator - moto isn't installed in this
project (see the Phase 5 report), and the project's existing test
convention (backend/tests/test_lambda_handler.py,
backend/core/extraction/tests/test_bedrock.py) is to mock boto3 calls
directly rather than pull in a heavier test dependency. This double
implements exactly the subset of `update_item`/`query` semantics
CareEventRepository actually relies on - most importantly,
`if_not_exists(created_at, :value)` inside an UpdateItem SET clause,
since that's the mechanism the repository's idempotency depends on.
"""

from __future__ import annotations

import re
import threading

_SIMPLE_CLAUSE_RE = re.compile(r"^(#\w+) = (:\w+)$")
_IF_NOT_EXISTS_RE = re.compile(r"^(#\w+) = if_not_exists\((#\w+), (:\w+)\)$")


def _split_top_level_clauses(expression: str) -> list[str]:
    """Splits on ', ' but not inside parentheses (if_not_exists(...) itself
    contains a ', ') - a tiny paren-depth-aware split, not a general
    DynamoDB expression parser."""
    clauses = []
    depth = 0
    current = []
    i = 0
    while i < len(expression):
        ch = expression[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            clauses.append("".join(current).strip())
            current = []
            i += 1
            continue
        current.append(ch)
        i += 1
    if current:
        clauses.append("".join(current).strip())
    return clauses


class FakeCareEventsTable:
    def __init__(self):
        self.items: dict[tuple, dict] = {}
        self.update_item_calls = 0
        self._lock = threading.Lock()

    def update_item(self, Key, UpdateExpression, ExpressionAttributeNames, ExpressionAttributeValues, ReturnValues="NONE"):
        with self._lock:
            self.update_item_calls += 1
            key = (Key["pk"], Key["sk"])
            existing = self.items.get(key, {})
            new_item = dict(existing)
            new_item["pk"] = Key["pk"]
            new_item["sk"] = Key["sk"]

            assert UpdateExpression.startswith("SET "), f"unsupported UpdateExpression: {UpdateExpression!r}"
            clauses = _split_top_level_clauses(UpdateExpression[len("SET "):])
            for clause in clauses:
                m = _IF_NOT_EXISTS_RE.match(clause)
                if m:
                    name_ph, existing_name_ph, value_ph = m.groups()
                    attr = ExpressionAttributeNames[name_ph]
                    if attr in existing:
                        new_item[attr] = existing[attr]
                    else:
                        new_item[attr] = ExpressionAttributeValues[value_ph]
                    continue

                m = _SIMPLE_CLAUSE_RE.match(clause)
                if m:
                    name_ph, value_ph = m.groups()
                    attr = ExpressionAttributeNames[name_ph]
                    new_item[attr] = ExpressionAttributeValues[value_ph]
                    continue

                raise AssertionError(f"FakeCareEventsTable cannot interpret clause: {clause!r}")

            self.items[key] = new_item
            return {"Attributes": dict(new_item)}

    def query(self, IndexName, KeyConditionExpression, ExpressionAttributeValues, ScanIndexForward=True, Limit=None):
        if IndexName == "CareTimelineIndex":
            pk_value = ExpressionAttributeValues[":pk"]
            matches = [item for item in self.items.values() if item["pk"] == pk_value]
            matches.sort(key=lambda i: i["created_at"], reverse=not ScanIndexForward)
        elif IndexName == "TranscriptIndex":
            transcript_value = ExpressionAttributeValues[":transcript_id"]
            matches = [item for item in self.items.values() if item["transcript_id"] == transcript_value]
        else:
            raise AssertionError(f"FakeCareEventsTable has no index named {IndexName!r}")

        if Limit is not None:
            matches = matches[:Limit]
        return {"Items": [dict(m) for m in matches]}
