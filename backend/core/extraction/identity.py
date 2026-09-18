"""Deterministic, order-independent event identity.

Phase 4's first identity scheme was `hash(version, transcript_id, array
index)`. It was deterministic but tied to the PROVIDER's output *order*,
not to the logical event itself: reordering an otherwise-identical
extraction, or a provider implementation change that emits the same
events in a different sequence, would change every id. That is not
sufficient for production idempotency, so Phase 4.1 replaces it: identity
is now a pure function of an event's own semantic/evidence fields, never
its position in any list.

Formula:

    fingerprint = extraction_version | transcript_id | event_type
                | normalized(subject) | claim_stance
                | temporal_identity(occurred_at)
                | sorted(unique(evidence_segment_ids))

    event_id = "ce_" + sha256(fingerprint)[:16]              (no collision)
    event_id = "ce_" + sha256(fingerprint + "#" + n)[:16]    (nth member of
                                                                a collision
                                                                group, n >= 1)

Two candidates whose fingerprint is identical are a genuine identity
collision under this schema - same type, same (normalized) person, same
claim stance, same temporal identity, same evidence set. See
assign_event_ids for how those are disambiguated deterministically without
relying on provider output order.

Summary text is deliberately EXCLUDED from the fingerprint: wording can
legitimately vary between two equivalent extractions of the same real
event, and the id must not change just because a rephrasing changed. It
is, however, used - along with a couple of other full-content fields - as
a tie-breaker to order a genuine collision group (see
_collision_tie_break_key): within such a group there is, by definition,
nothing else left in the identity fields to distinguish members, but
sorting by full content is still entirely independent of where each
candidate happened to sit in the provider's output array, which is the
property that actually matters here.

Migration implications of extraction_version: bumping it (as this revision
does, care_event_v1 -> care_event_v2, since the identity FORMULA itself
changed here) means every id computed under the old version is guaranteed
never to collide with one computed under the new version, even for the
"same" transcript. That is intentional: v1 ids were computed from a
different, order-dependent formula and were never a reliable logical
identity in the first place, so treating them as unrelated to v2 ids - not
attempting to reconcile or migrate them - is the safe default. Any future
persistence layer that stored v1 ids will need to be point-in-time-aware
of the id scheme (or wiped/re-extracted) before adopting v2; this module
only defines the id functions, so it does not perform such a migration
itself.
"""

from __future__ import annotations

import hashlib

from backend.core.care_event import CareEvent, temporal_display_key
from backend.core.care_event.normalization import normalize_subject

EXTRACTION_SCHEMA_VERSION = "care_event_v2"


def _normalized_subject_key(subject: str) -> str:
    """Identity-specific: also lowercases, unlike normalize_subject() on
    its own (which preserves case for storage/display, where "Dad" vs
    "dad" may matter to a reader). Two events about "Dad" and "dad" are
    the same logical event for identity purposes even if display casing
    should be preserved elsewhere."""
    return normalize_subject(subject).lower()


def _temporal_identity_key(event: CareEvent) -> str:
    key = temporal_display_key(event.occurred_at)
    return key if key is not None else f"unknown:{event.occurred_at.precision.value}"


def _evidence_identity_key(event: CareEvent) -> str:
    return ",".join(sorted(set(event.evidence_segment_ids)))


def event_fingerprint(
    event: CareEvent, transcript_id: str, extraction_version: str = EXTRACTION_SCHEMA_VERSION
) -> str:
    """The canonical, order-independent identity signal for one CareEvent.
    A pure function of the event's own fields and the transcript/version
    it came from - never of its position in any list."""
    parts = [
        extraction_version,
        transcript_id,
        event.event_type.value,
        _normalized_subject_key(event.subject),
        event.claim_stance.value,
        _temporal_identity_key(event),
        _evidence_identity_key(event),
    ]
    return "|".join(parts)


def _hash_id(fingerprint: str, occurrence: int) -> str:
    basis = fingerprint if occurrence == 0 else f"{fingerprint}#{occurrence}"
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]
    return f"ce_{digest}"


def _collision_tie_break_key(event: CareEvent) -> tuple:
    """Orders a genuine collision group deterministically. Used ONLY here,
    never folded into the fingerprint/identity itself - see module
    docstring. Full-content, not position-based, so it stays stable
    regardless of how the provider ordered its output."""
    return (event.summary, event.reported_by or "", event.review_state.value)


def assign_event_ids(
    events: list[CareEvent],
    transcript_id: str,
    extraction_version: str = EXTRACTION_SCHEMA_VERSION,
) -> list[str]:
    """Returns event ids aligned 1:1 with `events`, entirely independent of
    the order `events` is given in.

    Grouping is by fingerprint (a pure function of each event's own
    fields, not its list position). Within a fingerprint group (a
    collision - see module docstring), occurrence order is decided by a
    full-content sort, not by list position. Reordering the input list, or
    a provider implementation change that emits the same logical events in
    a different sequence, produces exactly the same set of ids.
    """
    fingerprints = [event_fingerprint(e, transcript_id, extraction_version) for e in events]

    groups: dict[str, list[int]] = {}
    for i, fp in enumerate(fingerprints):
        groups.setdefault(fp, []).append(i)

    ids: list[str] = [""] * len(events)
    for fp, indices in groups.items():
        ordered = sorted(indices, key=lambda i: _collision_tie_break_key(events[i]))
        for occurrence, i in enumerate(ordered):
            ids[i] = _hash_id(fp, occurrence)

    return ids
