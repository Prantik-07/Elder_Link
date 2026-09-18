"""Explicit persistence-time context, kept separate from the canonical
CareEvent.

Phase 2 established that the canonical schema stays focused on the event
itself and does not absorb patient/caregiver infrastructure unless a
compelling existing model requires it - none does yet. CareContext is how
persistence attaches "whose care timeline is this" and "which transcript
produced it" to a CareEvent without pulling those concerns into the
schema that extraction/evaluation depend on.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class CareContext:
    care_recipient_id: str
    transcript_id: str
    caregiver_id: Optional[str] = None
