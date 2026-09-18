"""Lightweight, deterministic conflict flagging between CareEvents produced
from the same transcript.

This is explicitly NOT longitudinal conflict resolution (comparing against
prior extractions, deciding which claim is "right", merging events) - that
is out of scope for Phase 4 and noted as future work. This is just enough
to notice, within one extraction batch, that two claims disagree, so they
can be routed to review instead of silently sitting there as if nothing
was wrong. Conflicting claims are kept as separate CareEvents - never
merged into a single event with a fabricated "contradicted" stance.
"""

from __future__ import annotations

from backend.core.care_event import CareEvent
from backend.core.care_event.normalization import normalize_subject


def find_conflicting_event_ids(events: list[CareEvent]) -> set[str]:
    """Two events conflict when they're about the same kind of thing
    (same event_type) and the same person (same normalized subject) but
    disagree on whether it happened (different claim_stance) - e.g. one
    event asserts a medication was taken, another negates or hedges the
    same medication claim for the same person. Returns the ids of every
    event involved in at least one such pair; does not attempt to decide
    which claim is correct."""
    conflicting: set[str] = set()
    for i, a in enumerate(events):
        for b in events[i + 1 :]:
            if (
                a.event_type == b.event_type
                and normalize_subject(a.subject).lower() == normalize_subject(b.subject).lower()
                and a.claim_stance != b.claim_stance
            ):
                conflicting.add(a.event_id)
                conflicting.add(b.event_id)
    return conflicting
